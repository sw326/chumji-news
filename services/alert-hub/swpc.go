package main

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const maxSWPCSeen = 1000

var (
	swpcCodePattern   = regexp.MustCompile(`(?im)^Space Weather Message Code:\s*(\S+)`)
	swpcSerialPattern = regexp.MustCompile(`(?im)^Serial Number:\s*(\d+)`)
	swpcScalePattern  = regexp.MustCompile(`(?i)NOAA Scale:\s*([GSR])([1-5])\s*-\s*([^\r\n]+)`)
)

type swpcProduct struct {
	ProductID     string `json:"product_id"`
	IssueDatetime string `json:"issue_datetime"`
	Message       string `json:"message"`
}

type SWPCEvent struct {
	ID            string
	ProductID     string
	Code          string
	Serial        string
	IssueDatetime string
	Category      string
	Level         int
	LevelText     string
	Action        string
	Detail        map[string]string
}

func pollSWPC(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.SWPC.URL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	stateMu.Lock()
	etag, lastModified := state.SWPCETag, state.SWPCLastModified
	stateMu.Unlock()
	if etag != "" {
		req.Header.Set("If-None-Match", etag)
	}
	if lastModified != "" {
		req.Header.Set("If-Modified-Since", lastModified)
	}
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("request NOAA SWPC alerts: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotModified {
		return nil
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("NOAA SWPC status %d", resp.StatusCode)
	}
	var products []swpcProduct
	if err := json.NewDecoder(io.LimitReader(resp.Body, 2<<20)).Decode(&products); err != nil {
		return fmt.Errorf("parse NOAA SWPC alerts: %w", err)
	}
	return processSWPC(ctx, cfg, state, token, dryRun, products,
		resp.Header.Get("ETag"), resp.Header.Get("Last-Modified"))
}

func processSWPC(ctx context.Context, cfg Config, state *State, token string, dryRun bool,
	products []swpcProduct, etag, lastModified string,
) error {
	events := make([]SWPCEvent, 0)
	for _, product := range products {
		if event, ok := normalizeSWPC(product); ok {
			events = append(events, event)
		}
	}
	sort.Slice(events, func(i, j int) bool {
		return events[i].IssueDatetime < events[j].IssueDatetime
	})

	stateMu.Lock()
	defer stateMu.Unlock()
	state.SWPCETag = etag
	state.SWPCLastModified = lastModified
	if !state.SWPCInitialized {
		for _, event := range events {
			rememberSWPC(state, event.ID)
		}
		state.SWPCInitialized = true
		if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
			return err
		}
		fmt.Printf("NOAA SWPC baseline initialized with %d strong-scale messages; no historical alerts sent\n", len(events))
		return nil
	}

	for _, event := range events {
		if state.SWPCSeen[event.ID] {
			continue
		}
		if !swpcFresh(event, time.Now()) {
			rememberSWPC(state, event.ID)
			continue
		}
		message := formatSWPCAlert(event)
		if dryRun {
			fmt.Printf("SWPC DRY RUN\n%s\n", message)
		} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
			Source: "swpc", EventID: event.ID, Action: event.Action,
			Severity: fmt.Sprintf("%s%d", event.Category, event.Level),
		}), token, cfg.TelegramChatID, message); err != nil {
			return err
		}
		rememberSWPC(state, event.ID)
	}
	return writeJSONAtomic(cfg.StateFile, state, 0o600)
}

func swpcFresh(event SWPCEvent, now time.Time) bool {
	for _, layout := range []string{"2006-01-02 15:04:05.000", "2006-01-02 15:04:05"} {
		issued, err := time.ParseInLocation(layout, event.IssueDatetime, time.UTC)
		if err == nil {
			age := now.Sub(issued)
			return age >= -5*time.Minute && age <= 24*time.Hour
		}
	}
	return false
}

func normalizeSWPC(product swpcProduct) (SWPCEvent, bool) {
	scale := swpcScalePattern.FindStringSubmatch(product.Message)
	if len(scale) != 4 {
		return SWPCEvent{}, false
	}
	level, err := strconv.Atoi(scale[2])
	if err != nil || level < 3 {
		return SWPCEvent{}, false
	}
	code := firstSWPCMatch(swpcCodePattern, product.Message)
	serial := firstSWPCMatch(swpcSerialPattern, product.Message)
	if code == "" || serial == "" || product.IssueDatetime == "" {
		return SWPCEvent{}, false
	}
	action := "updated"
	upper := strings.ToUpper(product.Message)
	switch {
	case strings.Contains(upper, "CANCEL WARNING") || strings.Contains(upper, "CANCEL WATCH"):
		action = "resolved"
	case strings.Contains(upper, "SUMMARY:"):
		action = "summary"
	case strings.Contains(upper, "WARNING:") || strings.Contains(upper, "WATCH:"):
		action = "forecast"
	case strings.Contains(upper, "ALERT:"):
		action = "observed"
	}
	id := strings.Join([]string{product.ProductID, code, serial, product.IssueDatetime}, "|")
	return SWPCEvent{
		ID: id, ProductID: product.ProductID, Code: code, Serial: serial,
		IssueDatetime: product.IssueDatetime, Category: scale[1], Level: level,
		LevelText: strings.TrimSpace(scale[3]), Action: action,
		Detail: parseSWPCDetails(product.Message),
	}, true
}

func firstSWPCMatch(pattern *regexp.Regexp, value string) string {
	match := pattern.FindStringSubmatch(value)
	if len(match) < 2 {
		return ""
	}
	return strings.TrimSpace(match[1])
}

func parseSWPCDetails(message string) map[string]string {
	wanted := map[string]bool{
		"Valid From": true, "Valid To": true, "Threshold Reached": true,
		"Begin Time": true, "Maximum Time": true, "End Time": true,
		"Xray Class": true, "Location": true,
	}
	details := map[string]string{}
	for _, line := range strings.Split(strings.ReplaceAll(message, "\r", ""), "\n") {
		key, value, ok := strings.Cut(line, ":")
		key, value = strings.TrimSpace(key), strings.TrimSpace(value)
		if ok && wanted[key] && value != "" {
			details[key] = value
		}
	}
	return details
}

func rememberSWPC(state *State, id string) {
	if state.SWPCSeen[id] {
		return
	}
	state.SWPCSeen[id] = true
	state.SWPCOrder = append(state.SWPCOrder, id)
	for len(state.SWPCOrder) > maxSWPCSeen {
		oldest := state.SWPCOrder[0]
		state.SWPCOrder = state.SWPCOrder[1:]
		delete(state.SWPCSeen, oldest)
	}
}

func formatSWPCAlert(event SWPCEvent) string {
	categoryName := map[string]string{
		"G": "지자기폭풍", "S": "태양복사폭풍", "R": "전파장애",
	}[event.Category]
	actionName := map[string]string{
		"forecast": "🔭 예보", "observed": "🆕 발생",
		"updated": "🔄 갱신", "summary": "✅ 종료 요약", "resolved": "✅ 취소/종료",
	}[event.Action]
	emoji := map[int]string{3: "🟠", 4: "🔴", 5: "🚨"}[event.Level]
	message := fmt.Sprintf(
		"<b>%s 우주기상 · %s%d %s · %s</b>\n\n<b>유형</b>  %s\n<b>강도</b>  %s%d · %s\n<b>발표</b>  %s",
		emoji, event.Category, event.Level, html.EscapeString(event.LevelText),
		actionName, html.EscapeString(categoryName), event.Category, event.Level,
		html.EscapeString(event.LevelText), html.EscapeString(formatSWPCTime(event.IssueDatetime)),
	)
	for _, key := range []string{"Valid From", "Valid To", "Threshold Reached", "Begin Time", "Maximum Time", "End Time", "Xray Class", "Location"} {
		if value := event.Detail[key]; value != "" {
			message += "\n<b>" + html.EscapeString(swpcDetailName(key)) + "</b>  " + html.EscapeString(value)
		}
	}
	message += "\n\n" + html.EscapeString(swpcImpact(event.Category, event.Level))
	message += "\n\n<a href=\"https://www.swpc.noaa.gov/products/alerts-watches-and-warnings\">NOAA SWPC에서 보기</a>"
	message += "\n<code>SWPC " + html.EscapeString(event.Code+" · serial "+event.Serial) + "</code>"
	return message
}

func swpcDetailName(key string) string {
	return map[string]string{
		"Valid From": "유효 시작", "Valid To": "유효 종료",
		"Threshold Reached": "임계 도달", "Begin Time": "시작",
		"Maximum Time": "최대", "End Time": "종료",
		"Xray Class": "플레어 등급", "Location": "태양 활동 위치",
	}[key]
}

func swpcImpact(category string, level int) string {
	switch category {
	case "G":
		if level >= 4 {
			return "전력망·위성·GPS·무선통신에 광범위한 장애 가능성이 있습니다."
		}
		return "전력망 전압 보정, 위성·GPS·HF 무선통신 장애 가능성이 있습니다."
	case "S":
		if level >= 4 {
			return "극지방 HF 통신 두절과 우주비행사·위성의 방사선 위험이 커질 수 있습니다."
		}
		return "극지방 HF 통신 저하와 위성·항공 방사선 영향 가능성이 있습니다."
	default:
		if level >= 4 {
			return "지구의 햇빛을 받는 넓은 지역에서 HF 무선통신 장애가 발생할 수 있습니다."
		}
		return "지구의 햇빛을 받는 지역에서 약 1시간의 광범위한 HF 무선통신 장애가 발생할 수 있습니다."
	}
}

func formatSWPCTime(value string) string {
	for _, layout := range []string{"2006-01-02 15:04:05.000", "2006-01-02 15:04:05"} {
		if parsed, err := time.ParseInLocation(layout, value, time.UTC); err == nil {
			return parsed.In(time.FixedZone("KST", 9*60*60)).Format("2006-01-02 15:04 KST")
		}
	}
	return value
}
