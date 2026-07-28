package main

import (
	"context"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"
	"unicode/utf8"
)

const maxKMASeen = 1000

var (
	kmaOptionPattern    = regexp.MustCompile(`(?s)<option\s+value="(met:[^"]+)"[^>]*>(.*?)</option>`)
	kmaAreaPattern      = regexp.MustCompile(`(?s)<strong>\s*□\s*해당구역\s*</strong>\s*<p>(.*?)</p>`)
	kmaEffectivePattern = regexp.MustCompile(`(?s)<strong>\s*□\s*발효시각\s*</strong>\s*<p>(.*?)</p>`)
	kmaTagPattern       = regexp.MustCompile(`<[^>]+>`)
	kmaBreakPattern     = regexp.MustCompile(`(?i)<br\s*/?>`)
)

type KMANotice struct {
	ID            string
	Date          string
	Title         string
	Areas         string
	EffectiveTime string
	DetailURL     string
}

func pollKMA(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	kst := time.FixedZone("KST", 9*60*60)
	today := time.Now().In(kst)
	dates := []string{today.AddDate(0, 0, -1).Format("2006-01-02"), today.Format("2006-01-02")}
	noticesByID := map[string]KMANotice{}
	for _, date := range dates {
		notices, err := fetchKMAList(ctx, cfg.KMA, date)
		if err != nil {
			return err
		}
		for _, notice := range notices {
			noticesByID[notice.ID] = notice
		}
	}
	notices := make([]KMANotice, 0, len(noticesByID))
	for _, notice := range noticesByID {
		notices = append(notices, notice)
	}
	sort.Slice(notices, func(i, j int) bool { return notices[i].ID < notices[j].ID })

	stateMu.Lock()
	if !state.KMAInitialized {
		for _, notice := range notices {
			rememberKMA(state, notice.ID)
		}
		state.KMAInitialized = true
		err := writeJSONAtomic(cfg.StateFile, state, 0o600)
		stateMu.Unlock()
		if err != nil {
			return err
		}
		fmt.Printf("KMA capital warning baseline initialized with %d notices; no historical alerts sent\n", len(notices))
		return nil
	}
	stateMu.Unlock()

	for _, notice := range notices {
		stateMu.Lock()
		seen := state.KMASeen[notice.ID]
		stateMu.Unlock()
		if seen {
			continue
		}
		detail, err := fetchKMADetail(ctx, cfg.KMA, notice)
		if err != nil {
			return err
		}
		stateMu.Lock()
		if state.KMASeen[detail.ID] {
			stateMu.Unlock()
			continue
		}
		message := formatKMAAlert(detail)
		if dryRun {
			fmt.Printf("KMA DRY RUN\n%s\n", message)
		} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
			Source: "kma", EventID: detail.ID, Action: "notice", Severity: detail.Title,
		}), token, cfg.TelegramChatID, message); err != nil {
			stateMu.Unlock()
			return err
		}
		rememberKMA(state, detail.ID)
		err = writeJSONAtomic(cfg.StateFile, state, 0o600)
		stateMu.Unlock()
		if err != nil {
			return err
		}
	}
	return nil
}

func fetchKMAList(ctx context.Context, cfg KMAConfig, date string) ([]KMANotice, error) {
	query := url.Values{"stn": {cfg.Station}, "kind": {"met"}, "date": {date}}
	raw, err := fetchKMAHTML(ctx, cfg.URL+"?"+query.Encode())
	if err != nil {
		return nil, err
	}
	return parseKMAList(raw, cfg.URL, cfg.Station, date), nil
}

func fetchKMADetail(ctx context.Context, cfg KMAConfig, notice KMANotice) (KMANotice, error) {
	raw, err := fetchKMAHTML(ctx, notice.DetailURL)
	if err != nil {
		return notice, err
	}
	notice.Areas = extractKMASection(raw, kmaAreaPattern)
	notice.EffectiveTime = extractKMASection(raw, kmaEffectivePattern)
	return notice, nil
}

func fetchKMAHTML(ctx context.Context, target string) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("Accept", "text/html")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("request KMA warning page: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("KMA warning page status %d", resp.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
	if err != nil {
		return "", fmt.Errorf("read KMA warning page: %w", err)
	}
	return string(body), nil
}

func parseKMAList(raw, baseURL, station, date string) []KMANotice {
	matches := kmaOptionPattern.FindAllStringSubmatch(raw, -1)
	notices := make([]KMANotice, 0, len(matches))
	for _, match := range matches {
		title := cleanKMAHTML(match[2])
		if !wantedKMAWarning(title) {
			continue
		}
		query := url.Values{
			"stn": {station}, "kind": {"met"}, "date": {date}, "reportId": {match[1]},
		}
		notices = append(notices, KMANotice{
			ID: match[1], Date: date, Title: title, DetailURL: baseURL + "?" + query.Encode(),
		})
	}
	return notices
}

func wantedKMAWarning(title string) bool {
	for _, kind := range []string{"호우", "대설", "강풍", "폭염", "한파", "태풍"} {
		if strings.Contains(title, kind) {
			return true
		}
	}
	return false
}

func extractKMASection(raw string, pattern *regexp.Regexp) string {
	match := pattern.FindStringSubmatch(raw)
	if len(match) < 2 {
		return ""
	}
	return truncateRunes(cleanKMAHTML(match[1]), 1600)
}

func cleanKMAHTML(value string) string {
	value = kmaBreakPattern.ReplaceAllString(value, "\n")
	value = kmaTagPattern.ReplaceAllString(value, " ")
	value = html.UnescapeString(value)
	lines := strings.Split(strings.ReplaceAll(value, "\r", ""), "\n")
	cleaned := make([]string, 0, len(lines))
	for _, line := range lines {
		if line = strings.Join(strings.Fields(line), " "); line != "" {
			cleaned = append(cleaned, line)
		}
	}
	return strings.Join(cleaned, "\n")
}

func truncateRunes(value string, limit int) string {
	if utf8.RuneCountInString(value) <= limit {
		return value
	}
	runes := []rune(value)
	return string(runes[:limit]) + "…"
}

func rememberKMA(state *State, id string) {
	if state.KMASeen[id] {
		return
	}
	state.KMASeen[id] = true
	state.KMAOrder = append(state.KMAOrder, id)
	for len(state.KMAOrder) > maxKMASeen {
		oldest := state.KMAOrder[0]
		state.KMAOrder = state.KMAOrder[1:]
		delete(state.KMASeen, oldest)
	}
}

func formatKMAAlert(notice KMANotice) string {
	action := "🔄 변경"
	hasIssue := strings.Contains(notice.Title, "발표")
	hasClear := strings.Contains(notice.Title, "해제")
	switch {
	case hasIssue && hasClear:
		action = "🔄 발표·해제"
	case hasIssue:
		action = "🆕 발표"
	case hasClear:
		action = "✅ 해제"
	}
	emoji := "🟠"
	if strings.Contains(notice.Title, "경보") {
		emoji = "🔴"
	}
	category := kmaCategory(notice.Title)
	message := fmt.Sprintf(
		"<b>%s 수도권 기상특보 · %s · %s</b>\n\n%s",
		emoji, html.EscapeString(category), action, html.EscapeString(notice.Title),
	)
	if notice.EffectiveTime != "" {
		message += "\n\n<b>발효시각</b>\n" + html.EscapeString(notice.EffectiveTime)
	}
	if notice.Areas != "" {
		message += "\n\n<b>해당구역</b>\n" + html.EscapeString(notice.Areas)
	}
	message += "\n\n<a href=\"" + html.EscapeString(notice.DetailURL) + "\">기상청 통보문 보기</a>"
	message += "\n<code>KMA " + html.EscapeString(notice.ID) + "</code>"
	return message
}

func kmaCategory(title string) string {
	var found []string
	for _, kind := range []string{"호우", "대설", "강풍", "폭염", "한파", "태풍"} {
		if strings.Contains(title, kind) {
			found = append(found, kind)
		}
	}
	if len(found) == 0 {
		return "특보"
	}
	return strings.Join(found, "·")
}
