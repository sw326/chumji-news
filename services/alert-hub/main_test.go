package main

import (
	"strings"
	"testing"
	"time"
)

var testFilters = FilterConfig{
	KoreaCenterLat: 36.3, KoreaCenterLon: 127.8,
	KoreaRadiusKM: 500, KoreaMinMagnitude: 3.0,
	RegionalRadiusKM: 1800, RegionalMinMagnitude: 4.5,
	GlobalMinMagnitude: 6.0, UrgentMinMagnitude: 7.0,
}

func TestClassify(t *testing.T) {
	tests := []struct {
		name                string
		distance, magnitude float64
		region, want        string
	}{
		{"small Korea event suppressed", 100, 2.9, "SOUTH KOREA", ""},
		{"Korea event", 100, 3.0, "SOUTH KOREA", "한국 주변"},
		{"nearby Kyushu aftershock suppressed", 450, 3.9, "KYUSHU, JAPAN", ""},
		{"nearby Kyushu event", 450, 4.5, "KYUSHU, JAPAN", "동아시아"},
		{"small global event", 3000, 5.9, "CENTRAL PACIFIC", ""},
		{"regional event", 1000, 4.5, "EASTERN CHINA", "동아시아"},
		{"large global event", 9000, 6.0, "CHILE", "세계"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := classify(test.distance, test.magnitude, test.region, testFilters); got != test.want {
				t.Fatalf("classify()=%q want %q", got, test.want)
			}
		})
	}
}

func TestNormalizeAndFormat(t *testing.T) {
	raw := []byte(`{
	  "action":"create",
	  "data":{"properties":{
	    "auth":"EMSC","unid":"20260728_test","time":"2026-07-28T07:42:00Z",
	    "mag":6.4,"lat":38.1,"lon":142.5,"depth":35,
	    "flynn_region":"NEAR EAST COAST OF HONSHU, JAPAN","lastupdate":"2026-07-28T07:43:00Z"
	  }}
	}`)
	event, err := normalize(raw, testFilters)
	if err != nil {
		t.Fatal(err)
	}
	if event.Tier != "동아시아" || event.Magnitude != 6.4 {
		t.Fatalf("unexpected event: %+v", event)
	}
	message := formatAlert(event, EventSnapshot{}, false)
	for _, expected := range []string{"<b>🌏 지진 · 🆕 신규 · 규모 6.4</b>", "HONSHU", "2026-07-28 16:42:00 KST", "지도에서 보기", "<code>EMSC"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}

func TestRememberDeduplicatesAndBounds(t *testing.T) {
	state := &State{Seen: map[string]string{}, Snapshots: map[string]EventSnapshot{}}
	event := NormalizedEvent{SourceID: "one", Fingerprint: "v1", Magnitude: 1}
	remember(state, event)
	event.Fingerprint = "v2"
	event.Magnitude = 2
	remember(state, event)
	if len(state.Order) != 1 || state.Seen["one"] != "v2" || state.Snapshots["one"].Magnitude != 2 {
		t.Fatalf("unexpected state: %+v", state)
	}
	for i := 0; i < maxSeenEvents+10; i++ {
		remember(state, NormalizedEvent{
			SourceID: time.Unix(int64(i), 0).String(), Fingerprint: "v",
		})
	}
	if len(state.Order) != maxSeenEvents || len(state.Seen) != maxSeenEvents || len(state.Snapshots) != maxSeenEvents {
		t.Fatalf("state not bounded: order=%d seen=%d snapshots=%d", len(state.Order), len(state.Seen), len(state.Snapshots))
	}
}

func TestFormatUpdateChanges(t *testing.T) {
	event := NormalizedEvent{
		Action: "update", SourceID: "event-1", Time: time.Date(2026, 7, 28, 7, 27, 0, 0, time.UTC),
		Magnitude: 6.8, Latitude: 32.67, Longitude: 130.75, Depth: 10,
		Region: "KYUSHU, JAPAN", DistanceKM: 500, Tier: "동아시아",
	}
	previous := EventSnapshot{
		Magnitude: 6.6, Latitude: 32.60, Longitude: 130.70, Depth: 12,
		Region: "KYUSHU, JAPAN",
	}
	message := formatAlert(event, previous, true)
	for _, expected := range []string{"🔄 수정", "규모 6.6 → 6.8", "깊이 12.0km → 10.0km", "진앙 위치 약"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("update message missing %q:\n%s", expected, message)
		}
	}
}

func TestEarthquakeEscalationPolicy(t *testing.T) {
	previous := EventSnapshot{
		Magnitude: 6.4, Latitude: 35.0, Longitude: 140.0, Region: "HONSHU, JAPAN",
	}
	routine := NormalizedEvent{Magnitude: 6.6, Latitude: 35.0, Longitude: 140.0, Tier: "동아시아"}
	if earthquakeEscalated(previous, routine, testFilters) {
		t.Fatal("routine magnitude revision should be suppressed")
	}
	urgent := routine
	urgent.Magnitude = 7.0
	urgent.Urgent = true
	if !earthquakeEscalated(previous, urgent, testFilters) {
		t.Fatal("urgent threshold crossing should notify")
	}
	closer := routine
	closer.Tier = "한국 주변"
	if !earthquakeEscalated(previous, closer, testFilters) {
		t.Fatal("more Korea-relevant tier should notify")
	}
}

func TestSnapshotFromFingerprint(t *testing.T) {
	snapshot, ok := snapshotFromFingerprint("update|6.80|32.6741|130.7504|10.0|2026-07-28T08:46:01Z")
	if !ok || snapshot.Magnitude != 6.8 || snapshot.Depth != 10 {
		t.Fatalf("unexpected snapshot: %+v ok=%v", snapshot, ok)
	}
}

func TestHaversine(t *testing.T) {
	distance := haversineKM(37.5665, 126.9780, 35.6762, 139.6503)
	if distance < 1100 || distance > 1200 {
		t.Fatalf("Seoul-Tokyo distance out of range: %.1f", distance)
	}
}
