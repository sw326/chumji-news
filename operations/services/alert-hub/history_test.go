package main

import (
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestHistoryRecordAndSummary(t *testing.T) {
	store, err := OpenHistoryStore(filepath.Join(t.TempDir(), "history.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	start := time.Date(2026, 7, 20, 0, 0, 0, 0, time.UTC)
	if err := store.Record(AlertMeta{Source: "emsc", EventID: "a", Action: "create"}, "one", start.Add(time.Hour)); err != nil {
		t.Fatal(err)
	}
	if err := store.Record(AlertMeta{Source: "kma", EventID: "b", Action: "notice"}, "two", start.Add(2*time.Hour)); err != nil {
		t.Fatal(err)
	}
	message, count, err := store.Summary(start, start.AddDate(0, 0, 7))
	if err != nil {
		t.Fatal(err)
	}
	if count != 2 || !strings.Contains(message, "지진") || !strings.Contains(message, "수도권 특보") {
		t.Fatalf("unexpected summary count=%d message=%s", count, message)
	}
}

func TestHistorySkipsTestNotification(t *testing.T) {
	store, err := OpenHistoryStore(filepath.Join(t.TempDir(), "history.sqlite3"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	now := time.Now()
	if err := store.Record(AlertMeta{Source: "system", Action: "test"}, "test", now); err != nil {
		t.Fatal(err)
	}
	_, count, err := store.Summary(now.Add(-time.Minute), now.Add(time.Minute))
	if err != nil || count != 0 {
		t.Fatalf("test message was archived: count=%d err=%v", count, err)
	}
}

func TestNextWeeklySummary(t *testing.T) {
	location, _ := time.LoadLocation("Asia/Seoul")
	monday := time.Date(2026, 7, 27, 9, 0, 0, 0, location)
	next := nextWeeklySummary(monday, location, 0, 20, 0)
	if next.Weekday() != time.Sunday || next.Hour() != 20 || next.Day() != 2 {
		t.Fatalf("unexpected next summary: %s", next)
	}
}
