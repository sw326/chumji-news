package main

import (
	"context"
	"database/sql"
	"fmt"
	"html"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

type HistoryConfig struct {
	Enabled        bool   `json:"enabled"`
	DatabaseFile   string `json:"database_file"`
	SummaryEnabled bool   `json:"summary_enabled"`
	SummaryWeekday int    `json:"summary_weekday"`
	SummaryHour    int    `json:"summary_hour"`
	SummaryMinute  int    `json:"summary_minute"`
	Timezone       string `json:"timezone"`
}

type AlertMeta struct {
	Source     string
	EventID    string
	Action     string
	Severity   string
	OccurredAt time.Time
}

type alertMetaKey struct{}

type HistoryStore struct {
	db *sql.DB
}

type SummaryCount struct {
	Source string
	Count  int
}

func withAlertMeta(ctx context.Context, meta AlertMeta) context.Context {
	return context.WithValue(ctx, alertMetaKey{}, meta)
}

func alertMetaFromContext(ctx context.Context) AlertMeta {
	meta, _ := ctx.Value(alertMetaKey{}).(AlertMeta)
	if meta.Source == "" {
		meta.Source = "unknown"
	}
	if meta.Action == "" {
		meta.Action = "alert"
	}
	return meta
}

func OpenHistoryStore(path string) (*HistoryStore, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("history database_file is empty")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	db, err := sql.Open("sqlite", path)
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(1)
	for _, statement := range []string{
		`PRAGMA journal_mode=WAL`,
		`PRAGMA busy_timeout=5000`,
		`CREATE TABLE IF NOT EXISTS alert_events (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			source TEXT NOT NULL,
			event_id TEXT NOT NULL DEFAULT '',
			action TEXT NOT NULL,
			severity TEXT NOT NULL DEFAULT '',
			occurred_at TEXT,
			received_at TEXT NOT NULL,
			message_html TEXT NOT NULL
		)`,
		`CREATE INDEX IF NOT EXISTS idx_alert_events_received ON alert_events(received_at)`,
		`CREATE INDEX IF NOT EXISTS idx_alert_events_source_event ON alert_events(source, event_id)`,
		`CREATE TABLE IF NOT EXISTS sent_summaries (
			period_key TEXT PRIMARY KEY,
			sent_at TEXT NOT NULL
		)`,
	} {
		if _, err := db.Exec(statement); err != nil {
			_ = db.Close()
			return nil, fmt.Errorf("initialize history database: %w", err)
		}
	}
	for _, databasePath := range []string{path, path + "-wal", path + "-shm"} {
		if err := os.Chmod(databasePath, 0o600); err != nil && !os.IsNotExist(err) {
			_ = db.Close()
			return nil, fmt.Errorf("secure history database permissions: %w", err)
		}
	}
	return &HistoryStore{db: db}, nil
}

func (store *HistoryStore) Close() error {
	return store.db.Close()
}

func (store *HistoryStore) Record(meta AlertMeta, message string, receivedAt time.Time) error {
	if meta.Action == "test" {
		return nil
	}
	var occurred any
	if !meta.OccurredAt.IsZero() {
		occurred = meta.OccurredAt.UTC().Format(time.RFC3339Nano)
	}
	_, err := store.db.Exec(
		`INSERT INTO alert_events(source,event_id,action,severity,occurred_at,received_at,message_html)
		 VALUES(?,?,?,?,?,?,?)`,
		meta.Source, meta.EventID, meta.Action, meta.Severity, occurred,
		receivedAt.UTC().Format(time.RFC3339Nano), message,
	)
	return err
}

func (store *HistoryStore) Summary(start, end time.Time) (string, int, error) {
	rows, err := store.db.Query(
		`SELECT source, COUNT(*) FROM alert_events
		 WHERE received_at >= ? AND received_at < ? AND source != 'summary'
		 GROUP BY source`,
		start.UTC().Format(time.RFC3339Nano), end.UTC().Format(time.RFC3339Nano),
	)
	if err != nil {
		return "", 0, err
	}
	defer rows.Close()
	var counts []SummaryCount
	total := 0
	for rows.Next() {
		var count SummaryCount
		if err := rows.Scan(&count.Source, &count.Count); err != nil {
			return "", 0, err
		}
		counts = append(counts, count)
		total += count.Count
	}
	if err := rows.Err(); err != nil {
		return "", 0, err
	}
	if total == 0 {
		return "", 0, nil
	}
	sort.Slice(counts, func(i, j int) bool {
		if counts[i].Count == counts[j].Count {
			return counts[i].Source < counts[j].Source
		}
		return counts[i].Count > counts[j].Count
	})
	kst := time.FixedZone("KST", 9*60*60)
	var lines []string
	for _, count := range counts {
		lines = append(lines, fmt.Sprintf("• %s  %d건", html.EscapeString(sourceLabel(count.Source)), count.Count))
	}
	return fmt.Sprintf(
		"<b>📚 주간 알림 허브 요약 · %d건</b>\n\n<b>기간</b>  %s ~ %s\n\n%s\n\n<i>AI 없이 저장된 알림 이력을 집계했습니다.</i>",
		total,
		start.In(kst).Format("2006-01-02"),
		end.In(kst).Add(-time.Second).Format("2006-01-02"),
		strings.Join(lines, "\n"),
	), total, nil
}

func (store *HistoryStore) SummarySent(periodKey string) (bool, error) {
	var found string
	err := store.db.QueryRow(`SELECT period_key FROM sent_summaries WHERE period_key = ?`, periodKey).Scan(&found)
	if err == sql.ErrNoRows {
		return false, nil
	}
	return err == nil, err
}

func (store *HistoryStore) MarkSummarySent(periodKey string, sentAt time.Time) error {
	_, err := store.db.Exec(
		`INSERT OR REPLACE INTO sent_summaries(period_key,sent_at) VALUES(?,?)`,
		periodKey, sentAt.UTC().Format(time.RFC3339Nano),
	)
	return err
}

func runSummaryScheduler(ctx context.Context, cfg Config, token string, dryRun bool) {
	location, err := time.LoadLocation(cfg.History.Timezone)
	if err != nil {
		log.Printf("summary scheduler disabled: %v", err)
		return
	}
	for {
		next := nextWeeklySummary(time.Now(), location, cfg.History.SummaryWeekday, cfg.History.SummaryHour, cfg.History.SummaryMinute)
		timer := time.NewTimer(time.Until(next))
		select {
		case <-ctx.Done():
			timer.Stop()
			return
		case <-timer.C:
			end := next
			start := end.AddDate(0, 0, -7)
			periodKey := start.Format("2006-01-02") + "/" + end.Format("2006-01-02")
			sent, err := historyStore.SummarySent(periodKey)
			if err != nil || sent {
				if err != nil {
					log.Printf("summary state check failed: %v", err)
				}
				continue
			}
			message, count, err := historyStore.Summary(start, end)
			if err != nil {
				log.Printf("summary generation failed: %v", err)
				continue
			}
			if count == 0 {
				_ = historyStore.MarkSummarySent(periodKey, time.Now())
				continue
			}
			if dryRun {
				log.Printf("SUMMARY DRY RUN\n%s", message)
			} else {
				summaryCtx := withAlertMeta(ctx, AlertMeta{Source: "summary", EventID: periodKey, Action: "weekly"})
				if err := sendTelegram(summaryCtx, token, cfg.TelegramChatID, message); err != nil {
					log.Printf("summary delivery failed: %v", err)
					continue
				}
			}
			if err := historyStore.MarkSummarySent(periodKey, time.Now()); err != nil {
				log.Printf("summary state write failed: %v", err)
			}
		}
	}
}

func nextWeeklySummary(now time.Time, location *time.Location, weekday, hour, minute int) time.Time {
	local := now.In(location)
	days := (weekday - int(local.Weekday()) + 7) % 7
	next := time.Date(local.Year(), local.Month(), local.Day()+days, hour, minute, 0, 0, location)
	if !next.After(local) {
		next = next.AddDate(0, 0, 7)
	}
	return next
}

func sourceLabel(source string) string {
	if label := map[string]string{
		"emsc": "지진", "gdacs": "세계 재난", "tsunami": "쓰나미",
		"swpc": "우주기상", "kma": "수도권 특보", "typhoon": "태풍",
	}[source]; label != "" {
		return label
	}
	return source
}
