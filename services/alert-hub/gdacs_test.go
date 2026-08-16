package main

import (
	"strings"
	"testing"
)

func TestGDACSTransitions(t *testing.T) {
	orange := GDACSSnapshot{EventID: "1", Level: "Orange", IsCurrent: true, EpisodeID: "1"}
	if got := gdacsTransition(GDACSSnapshot{}, false, orange); got != "new" {
		t.Fatalf("new transition=%q", got)
	}
	red := orange
	red.Level = "Red"
	red.EpisodeID = "2"
	if got := gdacsTransition(orange, true, red); got != "escalated" {
		t.Fatalf("escalated transition=%q", got)
	}
	resolved := red
	resolved.IsCurrent = false
	resolved.EpisodeID = "3"
	if got := gdacsTransition(red, true, resolved); got != "resolved" {
		t.Fatalf("resolved transition=%q", got)
	}
	if got := gdacsTransition(orange, true, orange); got != "" {
		t.Fatalf("duplicate transition=%q", got)
	}
	updated := orange
	updated.EpisodeID = "2"
	updated.Severity = 123
	updated.SeverityText = "revised impact estimate"
	if got := gdacsTransition(orange, true, updated); got != "" {
		t.Fatalf("routine update transition=%q", got)
	}
}

func TestNormalizeGDACSExcludesEarthquake(t *testing.T) {
	_, ok := normalizeGDACS(GDACSProperties{EventType: "EQ", EventID: "1"})
	if ok {
		t.Fatal("earthquake should be excluded")
	}
}

func TestFormatGDACSAlert(t *testing.T) {
	current := GDACSSnapshot{
		EventType: "TC", EventID: "1001294", EpisodeID: "13", Name: "Tropical Cyclone NOUL-26",
		Country: "China, Philippines", Level: "Orange", IsCurrent: true,
		SeverityText: "maximum wind speed of 157 km/h", FromDate: "2026-07-23T06:00:00",
		ReportURL: "https://www.gdacs.org/report.aspx?eventid=1001294",
	}
	message := formatGDACSAlert("new", GDACSSnapshot{}, current)
	for _, expected := range []string{"🟠 세계 재난 · 태풍 · 🆕 신규", "157 km/h", "GDACS에서 보기", "TC1001294"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}
