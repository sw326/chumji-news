package main

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"html"
	"io"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type GDACSCollection struct {
	Features []GDACSFeature `json:"features"`
}

type GDACSFeature struct {
	Properties GDACSProperties `json:"properties"`
}

type GDACSProperties struct {
	EventType         string        `json:"eventtype"`
	EventID           json.Number   `json:"eventid"`
	EpisodeID         json.Number   `json:"episodeid"`
	EventName         string        `json:"eventname"`
	Name              string        `json:"name"`
	Description       string        `json:"description"`
	AlertLevel        string        `json:"alertlevel"`
	EpisodeAlertLevel string        `json:"episodealertlevel"`
	IsCurrent         string        `json:"iscurrent"`
	Country           string        `json:"country"`
	FromDate          string        `json:"fromdate"`
	ToDate            string        `json:"todate"`
	DateModified      string        `json:"datemodified"`
	URL               GDACSURLs     `json:"url"`
	Severity          GDACSSeverity `json:"severitydata"`
}

type GDACSURLs struct {
	Report string `json:"report"`
}

type GDACSSeverity struct {
	Value float64 `json:"severity"`
	Text  string  `json:"severitytext"`
	Unit  string  `json:"severityunit"`
}

type GDACSSnapshot struct {
	EventType    string  `json:"event_type"`
	EventID      string  `json:"event_id"`
	EpisodeID    string  `json:"episode_id"`
	Name         string  `json:"name"`
	Country      string  `json:"country"`
	Level        string  `json:"level"`
	IsCurrent    bool    `json:"is_current"`
	Severity     float64 `json:"severity"`
	SeverityText string  `json:"severity_text"`
	FromDate     string  `json:"from_date"`
	ToDate       string  `json:"to_date"`
	DateModified string  `json:"date_modified"`
	ReportURL    string  `json:"report_url"`
}

func pollGDACS(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		if attempt > 0 {
			if err := waitContext(ctx, 10*time.Second); err != nil {
				return err
			}
		}
		lastErr = pollGDACSOnce(ctx, cfg, state, token, dryRun)
		if lastErr == nil {
			return nil
		}
	}
	if err := pollGDACSRSS(ctx, cfg, state, token, dryRun); err != nil {
		return fmt.Errorf("API failed (%v); RSS fallback failed: %w", lastErr, err)
	}
	fmt.Printf("GDACS API unavailable; RSS fallback succeeded\n")
	return nil
}

func pollGDACSOnce(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.GDACS.URL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/geo+json, application/json")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("request GDACS: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return fmt.Errorf("GDACS status %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	decoder := json.NewDecoder(io.LimitReader(resp.Body, 5<<20))
	decoder.UseNumber()
	var collection GDACSCollection
	if err := decoder.Decode(&collection); err != nil {
		return fmt.Errorf("parse GDACS response: %w", err)
	}
	return processGDACSCollection(ctx, cfg, state, token, dryRun, collection)
}

type gdacsRSS struct {
	Channel struct {
		Items []gdacsRSSItem `xml:"item"`
	} `xml:"channel"`
}

type gdacsRSSItem struct {
	Title             string `xml:"title"`
	Link              string `xml:"link"`
	EventType         string `xml:"eventtype"`
	EventID           string `xml:"eventid"`
	EpisodeID         string `xml:"episodeid"`
	AlertLevel        string `xml:"alertlevel"`
	EpisodeAlertLevel string `xml:"episodealertlevel"`
	IsCurrent         string `xml:"iscurrent"`
	EventName         string `xml:"eventname"`
	Country           string `xml:"country"`
	FromDate          string `xml:"fromdate"`
	ToDate            string `xml:"todate"`
	DateModified      string `xml:"datemodified"`
	Severity          struct {
		Value float64 `xml:"value,attr"`
		Unit  string  `xml:"unit,attr"`
		Text  string  `xml:",chardata"`
	} `xml:"severity"`
}

func pollGDACSRSS(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.GDACS.RSSFallbackURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/rss+xml, application/xml")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	client := &http.Client{Timeout: 45 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("request GDACS RSS: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GDACS RSS status %d", resp.StatusCode)
	}
	var feed gdacsRSS
	decoder := xml.NewDecoder(io.LimitReader(resp.Body, 10<<20))
	if err := decoder.Decode(&feed); err != nil {
		return fmt.Errorf("parse GDACS RSS: %w", err)
	}
	collection := GDACSCollection{Features: make([]GDACSFeature, 0, len(feed.Channel.Items))}
	for _, item := range feed.Channel.Items {
		level := canonicalGDACSLevel(item.AlertLevel)
		if level != "Orange" && level != "Red" {
			continue
		}
		collection.Features = append(collection.Features, GDACSFeature{Properties: GDACSProperties{
			EventType: item.EventType, EventID: json.Number(item.EventID), EpisodeID: json.Number(item.EpisodeID),
			EventName: item.EventName, Name: item.Title, Description: item.Title,
			AlertLevel: item.AlertLevel, EpisodeAlertLevel: item.EpisodeAlertLevel,
			IsCurrent: item.IsCurrent, Country: item.Country,
			FromDate: item.FromDate, ToDate: item.ToDate, DateModified: item.DateModified,
			URL:      GDACSURLs{Report: item.Link},
			Severity: GDACSSeverity{Value: item.Severity.Value, Text: strings.TrimSpace(item.Severity.Text), Unit: item.Severity.Unit},
		}})
	}
	return processGDACSCollection(ctx, cfg, state, token, dryRun, collection)
}

func processGDACSCollection(ctx context.Context, cfg Config, state *State, token string, dryRun bool, collection GDACSCollection) error {
	stateMu.Lock()
	defer stateMu.Unlock()

	snapshots := make([]GDACSSnapshot, 0, len(collection.Features))
	for _, feature := range collection.Features {
		snapshot, ok := normalizeGDACS(feature.Properties)
		if ok {
			snapshots = append(snapshots, snapshot)
		}
	}

	if !state.GDACSInitialized {
		for _, snapshot := range snapshots {
			state.GDACS[snapshot.EventID] = snapshot
		}
		state.GDACSInitialized = true
		if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
			return err
		}
		logGDACSBaseline(len(snapshots))
		return nil
	}

	for _, current := range snapshots {
		previous, exists := state.GDACS[current.EventID]
		kind := gdacsTransition(previous, exists, current)
		if kind != "" {
			message := formatGDACSAlert(kind, previous, current)
			if dryRun {
				fmt.Printf("GDACS DRY RUN\n%s\n", message)
			} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
				Source: "gdacs", EventID: current.EventID, Action: kind, Severity: current.Level,
			}), token, cfg.TelegramChatID, message); err != nil {
				return err
			}
		}
		state.GDACS[current.EventID] = current
	}
	return writeJSONAtomic(cfg.StateFile, state, 0o600)
}

func normalizeGDACS(p GDACSProperties) (GDACSSnapshot, bool) {
	eventType := strings.ToUpper(strings.TrimSpace(p.EventType))
	if eventType == "EQ" || !allowedGDACSType(eventType) {
		return GDACSSnapshot{}, false
	}
	eventID := p.EventID.String()
	if eventID == "" {
		return GDACSSnapshot{}, false
	}
	level := canonicalGDACSLevel(p.EpisodeAlertLevel)
	if level == "" {
		level = canonicalGDACSLevel(p.AlertLevel)
	}
	isCurrent, _ := strconv.ParseBool(p.IsCurrent)
	name := strings.TrimSpace(p.Name)
	if name == "" {
		name = strings.TrimSpace(p.Description)
	}
	return GDACSSnapshot{
		EventType: eventType, EventID: eventID, EpisodeID: p.EpisodeID.String(),
		Name: name, Country: strings.TrimSpace(p.Country), Level: level, IsCurrent: isCurrent,
		Severity: p.Severity.Value, SeverityText: strings.TrimSpace(p.Severity.Text),
		FromDate: p.FromDate, ToDate: p.ToDate, DateModified: p.DateModified,
		ReportURL: p.URL.Report,
	}, true
}

func allowedGDACSType(value string) bool {
	switch value {
	case "TC", "FL", "VO", "WF", "DR":
		return true
	default:
		return false
	}
}

func canonicalGDACSLevel(value string) string {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "red":
		return "Red"
	case "orange":
		return "Orange"
	case "green":
		return "Green"
	default:
		return ""
	}
}

func gdacsTransition(previous GDACSSnapshot, exists bool, current GDACSSnapshot) string {
	currentActionable := current.IsCurrent && gdacsRank(current.Level) >= gdacsRank("Orange")
	if !exists {
		if currentActionable {
			return "new"
		}
		return ""
	}
	previousActionable := previous.IsCurrent && gdacsRank(previous.Level) >= gdacsRank("Orange")
	if previousActionable && !currentActionable {
		return "resolved"
	}
	if currentActionable && gdacsRank(current.Level) > gdacsRank(previous.Level) {
		return "escalated"
	}
	return ""
}

func gdacsRank(level string) int {
	switch level {
	case "Red":
		return 3
	case "Orange":
		return 2
	case "Green":
		return 1
	default:
		return 0
	}
}

func formatGDACSAlert(kind string, previous, current GDACSSnapshot) string {
	levelEmoji := map[string]string{"Red": "🔴", "Orange": "🟠", "Green": "🟢"}[current.Level]
	action := map[string]string{
		"new": "🆕 신규", "escalated": "⬆️ 상향", "updated": "🔄 갱신", "resolved": "✅ 해제",
	}[kind]
	typeName := map[string]string{
		"TC": "태풍", "FL": "홍수", "VO": "화산", "WF": "산불", "DR": "가뭄",
	}[current.EventType]
	if kind == "resolved" {
		levelEmoji = "🟢"
	}
	message := fmt.Sprintf(
		"<b>%s 세계 재난 · %s · %s</b>\n\n%s\n<b>영향 지역</b>  %s\n<b>상태</b>  %s %s",
		levelEmoji, html.EscapeString(typeName), html.EscapeString(action),
		html.EscapeString(current.Name), html.EscapeString(current.Country),
		levelEmoji, html.EscapeString(current.Level),
	)
	if current.SeverityText != "" {
		message += "\n<b>규모/영향</b>  " + html.EscapeString(current.SeverityText)
	}
	if current.FromDate != "" {
		message += "\n<b>시작</b>  " + html.EscapeString(formatGDACSTime(current.FromDate))
	}
	if kind == "escalated" {
		message += fmt.Sprintf("\n\n<b>등급 변경</b>  %s → %s",
			html.EscapeString(previous.Level), html.EscapeString(current.Level))
	}
	if current.ReportURL != "" {
		message += "\n\n<a href=\"" + html.EscapeString(current.ReportURL) + "\">GDACS에서 보기</a>"
	}
	message += "\n<code>GDACS " + html.EscapeString(current.EventType+current.EventID) + "</code>"
	return message
}

func formatGDACSTime(value string) string {
	for _, layout := range []string{"2006-01-02T15:04:05", time.RFC3339} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed.In(time.FixedZone("KST", 9*60*60)).Format("2006-01-02 15:04 KST")
		}
	}
	return value
}

func logGDACSBaseline(count int) {
	fmt.Printf("GDACS baseline initialized with %d events; no historical alerts sent\n", count)
}
