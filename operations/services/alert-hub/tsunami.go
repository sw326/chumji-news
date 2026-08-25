package main

import (
	"context"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type tsunamiTEX struct {
	Bulletin tsunamiBulletin `xml:"TWCBulletin"`
}

type tsunamiBulletin struct {
	EventID        string `xml:"TWCEventID"`
	BulletinNumber int    `xml:"bulletinNumber"`
	BulletinName   string `xml:"bulletinName"`
	IssuingCenter  string `xml:"issuingCenter"`
	IssueTime      string `xml:"bulletinIssueTime"`
	Body           string `xml:"tsunamiBulletinBody"`
	TestMessage    bool   `xml:"testMessage"`
	Seismic        struct {
		Magnitude  float64 `xml:"magnitude"`
		OriginTime string  `xml:"originTime"`
		Depth      float64 `xml:"depth"`
		Latitude   float64 `xml:"lat"`
		Longitude  float64 `xml:"long"`
		Location   string  `xml:"locationName"`
	} `xml:"preliminarySeismicInformation"`
}

type TsunamiSnapshot struct {
	EventID        string  `json:"event_id,omitempty"`
	BulletinNumber int     `json:"bulletin_number,omitempty"`
	Level          string  `json:"level,omitempty"`
	IssueTime      string  `json:"issue_time,omitempty"`
	OriginTime     string  `json:"origin_time,omitempty"`
	Location       string  `json:"location,omitempty"`
	Magnitude      float64 `json:"magnitude,omitempty"`
	Depth          float64 `json:"depth,omitempty"`
	Latitude       float64 `json:"latitude,omitempty"`
	Longitude      float64 `json:"longitude,omitempty"`
	Final          bool    `json:"final,omitempty"`
	BulletinURL    string  `json:"bulletin_url,omitempty"`
}

func pollTsunami(ctx context.Context, cfg Config, state *State, token string, dryRun bool) (bool, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.Tsunami.URL, nil)
	if err != nil {
		return false, err
	}
	req.Header.Set("Accept", "application/xml, text/xml")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return false, fmt.Errorf("request PTWC tsunami feed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return false, fmt.Errorf("PTWC status %d", resp.StatusCode)
	}
	var feed tsunamiTEX
	if err := xml.NewDecoder(io.LimitReader(resp.Body, 2<<20)).Decode(&feed); err != nil {
		return false, fmt.Errorf("parse PTWC tsunami feed: %w", err)
	}
	current, ok := normalizeTsunami(feed.Bulletin, cfg.Tsunami.URL)
	if !ok {
		return false, nil
	}
	return processTsunami(ctx, cfg, state, token, dryRun, current)
}

func normalizeTsunami(b tsunamiBulletin, sourceURL string) (TsunamiSnapshot, bool) {
	if b.TestMessage || strings.TrimSpace(b.EventID) == "" || b.BulletinNumber <= 0 {
		return TsunamiSnapshot{}, false
	}
	body := strings.ToUpper(b.Body)
	level := tsunamiLevel(body)
	final := strings.Contains(body, "FINAL TSUNAMI") ||
		strings.Contains(body, "THREAT FROM THIS EARTHQUAKE HAS NOW PASSED") ||
		strings.Contains(body, "NO LONGER A TSUNAMI THREAT")
	if final {
		level = "none"
	}
	return TsunamiSnapshot{
		EventID: strings.TrimSpace(b.EventID), BulletinNumber: b.BulletinNumber,
		Level: level, IssueTime: strings.TrimSpace(b.IssueTime),
		OriginTime: strings.TrimSpace(b.Seismic.OriginTime),
		Location:   strings.Join(strings.Fields(b.Seismic.Location), " "),
		Magnitude:  b.Seismic.Magnitude, Depth: b.Seismic.Depth,
		Latitude: b.Seismic.Latitude, Longitude: b.Seismic.Longitude,
		Final: final, BulletinURL: sourceURL,
	}, true
}

func tsunamiLevel(body string) string {
	switch {
	case strings.Contains(body, "TSUNAMI WARNING"):
		return "warning"
	case strings.Contains(body, "TSUNAMI ADVISORY"):
		return "advisory"
	case strings.Contains(body, "TSUNAMI WATCH"):
		return "watch"
	case strings.Contains(body, "TSUNAMI THREAT"):
		return "threat"
	default:
		return "information"
	}
}

func processTsunami(ctx context.Context, cfg Config, state *State, token string, dryRun bool, current TsunamiSnapshot) (bool, error) {
	stateMu.Lock()
	defer stateMu.Unlock()

	if !state.TsunamiInitialized {
		state.Tsunami = current
		state.TsunamiInitialized = true
		if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
			return false, err
		}
		fmt.Printf("PTWC tsunami baseline initialized at event %s bulletin %d; no historical alert sent\n",
			current.EventID, current.BulletinNumber)
		return tsunamiActionable(current), nil
	}

	previous := state.Tsunami
	kind := tsunamiTransition(previous, current)
	if kind != "" {
		message := formatTsunamiAlert(kind, previous, current)
		if dryRun {
			fmt.Printf("TSUNAMI DRY RUN\n%s\n", message)
		} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
			Source: "tsunami", EventID: current.EventID, Action: kind, Severity: current.Level,
		}), token, cfg.TelegramChatID, message); err != nil {
			return tsunamiActionable(previous), err
		}
	}
	state.Tsunami = current
	if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
		return tsunamiActionable(current), err
	}
	return tsunamiActionable(current), nil
}

func tsunamiTransition(previous, current TsunamiSnapshot) string {
	if previous.EventID == current.EventID && previous.BulletinNumber == current.BulletinNumber {
		return ""
	}
	currentActionable := tsunamiActionable(current)
	previousActionable := tsunamiActionable(previous)
	if current.EventID != previous.EventID {
		if currentActionable {
			return "new"
		}
		return ""
	}
	if previousActionable && !currentActionable {
		return "resolved"
	}
	if !previousActionable && currentActionable {
		return "new"
	}
	if currentActionable && tsunamiRank(current.Level) > tsunamiRank(previous.Level) {
		return "escalated"
	}
	return ""
}

func tsunamiActionable(snapshot TsunamiSnapshot) bool {
	return !snapshot.Final && tsunamiRank(snapshot.Level) > 0
}

func tsunamiRank(level string) int {
	switch level {
	case "warning":
		return 4
	case "advisory":
		return 3
	case "threat":
		return 2
	case "watch":
		return 1
	default:
		return 0
	}
}

func formatTsunamiAlert(kind string, previous, current TsunamiSnapshot) string {
	action := map[string]string{
		"new": "🆕 발령", "escalated": "⬆️ 상향", "updated": "🔄 갱신", "resolved": "✅ 해제",
	}[kind]
	levelName := map[string]string{
		"warning": "경보", "advisory": "주의보", "watch": "감시", "threat": "위협", "none": "위협 종료",
	}[current.Level]
	emoji := "🌊"
	if current.Level == "warning" {
		emoji = "🚨"
	}
	if kind == "resolved" {
		emoji = "✅"
		levelName = "위협 종료"
	}
	message := fmt.Sprintf(
		"<b>%s 쓰나미 %s · %s</b>\n\n<b>진원 지역</b>  %s\n<b>지진 규모</b>  %.1f\n<b>발생</b>  %s\n<b>발표</b>  %s\n<b>상태</b>  %s",
		emoji, html.EscapeString(levelName), html.EscapeString(action),
		html.EscapeString(current.Location), current.Magnitude,
		html.EscapeString(formatTsunamiTime(current.OriginTime)),
		html.EscapeString(formatTsunamiTime(current.IssueTime)),
		html.EscapeString(levelName),
	)
	if kind == "escalated" {
		message += "\n\n<b>단계 변경</b>  " + html.EscapeString(tsunamiLevelName(previous.Level)) +
			" → " + html.EscapeString(tsunamiLevelName(current.Level))
	}
	if current.Depth > 0 {
		message += "\n<b>깊이</b>  " + strconv.FormatFloat(current.Depth, 'f', 0, 64) + "km"
	}
	message += "\n\n<a href=\"" + html.EscapeString(current.BulletinURL) + "\">PTWC 공식 발표 보기</a>"
	message += fmt.Sprintf("\n<code>PTWC %s · bulletin %d</code>",
		html.EscapeString(current.EventID), current.BulletinNumber)
	return message
}

func tsunamiLevelName(level string) string {
	return map[string]string{
		"warning": "경보", "advisory": "주의보", "watch": "감시",
		"threat": "위협", "information": "정보", "none": "위협 종료",
	}[level]
}

func formatTsunamiTime(value string) string {
	if parsed, err := time.Parse(time.RFC3339, value); err == nil {
		return parsed.In(time.FixedZone("KST", 9*60*60)).Format("2006-01-02 15:04 KST")
	}
	return value
}
