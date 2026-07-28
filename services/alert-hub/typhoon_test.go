package main

import (
	"strings"
	"testing"
	"time"
)

func TestNormalizeTyphoon(t *testing.T) {
	report := jmaTyphoon{
		ReportDateTime: "2026/07/28 18:45", Name: "DOLPHIN", Number: "2613",
		MeteorologicalInfo: []jmaTyphoonInfo{{DateTime: "2026/07/28 18:00"}},
	}
	first := &report.MeteorologicalInfo[0]
	first.Class.TyphoonClass = "TY"
	first.Class.Intensity = "강한 태풍"
	first.Center.Latitude, first.Center.Longitude = "13.3N", "171.2E"
	first.Center.Pressure, first.Center.Direction, first.Center.SpeedKMH = "975", "서", "20"
	first.Wind.SpeedMS, first.Wind.GustSpeedMS = "35", "50"
	cfg := Config{
		Filters: FilterConfig{KoreaCenterLat: 36.3, KoreaCenterLon: 127.8},
		Typhoon: TyphoonConfig{KoreaInfluenceKM: 800},
	}
	snapshot, ok := normalizeTyphoon(report, cfg, 60, time.Date(2026, 7, 28, 20, 0, 0, 0, time.FixedZone("KST", 9*3600)))
	if !ok || snapshot.Number != "2613" || snapshot.WindMS != 35 ||
		snapshot.CurrentLatitude != 13.3 || snapshot.KoreaInfluence {
		t.Fatalf("unexpected snapshot: %+v ok=%v", snapshot, ok)
	}
}

func TestTyphoonTransitions(t *testing.T) {
	cfg := TyphoonConfig{KoreaInfluenceKM: 800, KoreaNearbyKM: 2000, TrackShiftKM: 200}
	current := TyphoonSnapshot{Number: "2613", Intensity: "강한 태풍", ReportDateTime: "new"}
	if kind, _ := typhoonTransition(TyphoonSnapshot{}, false, current, cfg); kind != "new" {
		t.Fatalf("new kind=%q", kind)
	}
	previous := current
	previous.ReportDateTime = "old"
	previous.Intensity = "강한 태풍"
	previous.Pressure = 960
	previous.WindMS = 40
	current.Intensity = "매우 강한 태풍"
	current.Pressure = 940
	current.WindMS = 50
	if kind, changes := typhoonTransition(previous, true, current, cfg); kind != "strengthened" || len(changes) < 2 {
		t.Fatalf("strengthened kind=%q changes=%v", kind, changes)
	}
	previous = current
	previous.ReportDateTime = "old2"
	previous.KoreaInfluence = false
	current.KoreaInfluence = true
	current.KoreaClearanceKM = 500
	if kind, _ := typhoonTransition(previous, true, current, cfg); kind != "korea" {
		t.Fatalf("Korea transition kind=%q", kind)
	}
}

func TestMaxTyphoonTrackShift(t *testing.T) {
	previous := []TyphoonPoint{{DateTime: "2026/08/01 15:00", Latitude: 30, Longitude: 130}}
	current := []TyphoonPoint{{DateTime: "2026/08/01 15:00", Latitude: 30, Longitude: 133}}
	shift := maxTyphoonTrackShift(previous, current)
	if shift < 280 || shift > 300 {
		t.Fatalf("unexpected shift %.1f", shift)
	}
}

func TestParseTyphoonCoordinate(t *testing.T) {
	tests := map[string]float64{"13.3N": 13.3, "171.2E": 171.2, "12.5S": -12.5, "70.0W": -70}
	for input, want := range tests {
		got, ok := parseTyphoonCoordinate(input)
		if !ok || got != want {
			t.Fatalf("%s => %.1f ok=%v want %.1f", input, got, ok, want)
		}
	}
}

func TestFormatTyphoonAlert(t *testing.T) {
	snapshot := TyphoonSnapshot{
		Number: "2613", Name: "DOLPHIN", ReportDateTime: "2026/07/28 18:45",
		Intensity: "강한 태풍", Pressure: 975, WindMS: 35,
		Direction: "서", SpeedKMH: 20, KoreaClearanceKM: 2300,
		ClosestAt: "2026/08/02 15:00", DetailURL: "https://example.com",
	}
	message := formatTyphoonAlert("new", nil, snapshot)
	for _, expected := range []string{"태풍 제13호 DOLPHIN · 🆕 발생", "975hPa", "35m/s", "JMA 태풍정보 보기", "JMA T2613"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}
