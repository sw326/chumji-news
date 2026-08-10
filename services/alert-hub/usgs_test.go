package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestNormalizeUSGS(t *testing.T) {
	mag := 7.2
	feature := usgsFeature{
		ID: "us-test",
		Properties: usgsProperties{
			Magnitude: &mag, Place: "5 km S of San Jose, Colombia",
			Time:    time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC).UnixMilli(),
			Updated: time.Date(2026, 8, 10, 12, 56, 12, 0, time.UTC).UnixMilli(),
			URL:     "https://earthquake.usgs.gov/earthquakes/eventpage/us-test",
		},
		Geometry: usgsGeometry{Coordinates: []float64{-76.2032, 4.8732, 95.2}},
	}
	event, err := normalizeUSGS(feature, testFilters)
	if err != nil {
		t.Fatal(err)
	}
	if event.Source != "usgs" || event.Tier != "세계" || !event.Urgent || event.Magnitude != 7.2 {
		t.Fatalf("unexpected event: %+v", event)
	}
	message := formatAlert(event, EventSnapshot{}, false)
	for _, expected := range []string{"긴급 지진", "USGS에서 보기", "<code>USGS us-test</code>"} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}

func TestSameEarthquakeUsesConservativeWindow(t *testing.T) {
	previous := EventSnapshot{
		Magnitude: 7.2, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
		OccurredAt: "2026-08-10T12:34:27Z",
	}
	same := NormalizedEvent{
		Time:      time.Date(2026, 8, 10, 12, 34, 29, 0, time.UTC),
		Magnitude: 7.4, Latitude: 4.8765, Longitude: -76.2129,
	}
	if !sameEarthquake(previous, same) {
		t.Fatal("matching cross-source solutions were not associated")
	}
	aftershock := same
	aftershock.Time = aftershock.Time.Add(31 * time.Second)
	if sameEarthquake(previous, aftershock) {
		t.Fatal("separate event outside the conservative time window was merged")
	}
}

func TestCrossSourceDuplicateSuppressed(t *testing.T) {
	state := testEarthquakeState()
	cfg := Config{Filters: testFilters}
	occurred := time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC)
	usgs := NormalizedEvent{
		Source: "usgs", Action: "create", SourceID: "us-test", Time: occurred,
		Magnitude: 7.2, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
		Region: "Colombia", Tier: "세계", Urgent: true, Fingerprint: "us-v1",
	}
	alerted, changed, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, usgs)
	if err != nil || !alerted || !changed {
		t.Fatalf("USGS first alert result alerted=%v changed=%v err=%v", alerted, changed, err)
	}
	emsc := NormalizedEvent{
		Source: "emsc", Action: "create", SourceID: "emsc-test", Time: occurred.Add(time.Second),
		Magnitude: 7.3, Latitude: 4.8765, Longitude: -76.2129, Depth: 100,
		Region: "COLOMBIA", Tier: "세계", Urgent: true, Fingerprint: "emsc-v1",
	}
	alerted, changed, err = processEarthquakeLocked(context.Background(), cfg, state, "", true, emsc)
	if err != nil || alerted || !changed {
		t.Fatalf("cross-source duplicate result alerted=%v changed=%v err=%v", alerted, changed, err)
	}
	if len(state.Earthquakes) != 1 || state.Earthquakes[0].Sources["usgs"] != "us-test" ||
		state.Earthquakes[0].Sources["emsc"] != "emsc-test" {
		t.Fatalf("sources were not associated: %+v", state.Earthquakes)
	}
}

func TestCrossSourceMaterialChangeAlerts(t *testing.T) {
	state := testEarthquakeState()
	cfg := Config{Filters: testFilters}
	occurred := time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC)
	usgs := NormalizedEvent{
		Source: "usgs", Action: "create", SourceID: "us-test", Time: occurred,
		Magnitude: 6.8, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
		Region: "Colombia", Tier: "세계", Fingerprint: "us-v1",
	}
	if _, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, usgs); err != nil {
		t.Fatal(err)
	}
	emsc := NormalizedEvent{
		Source: "emsc", Action: "create", SourceID: "emsc-test", Time: occurred.Add(time.Second),
		Magnitude: 7.1, Latitude: 4.8765, Longitude: -76.2129, Depth: 95.2,
		Region: "COLOMBIA", Tier: "세계", Urgent: true, Fingerprint: "emsc-v1",
	}
	alerted, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, emsc)
	if err != nil || !alerted {
		t.Fatalf("material cross-source change alerted=%v err=%v", alerted, err)
	}
	if state.Earthquakes[0].Snapshot.Magnitude != 7.1 {
		t.Fatalf("record was not updated: %+v", state.Earthquakes[0])
	}
}

func TestAssociatedSourceDoesNotRegressCanonicalAlert(t *testing.T) {
	state := testEarthquakeState()
	cfg := Config{Filters: testFilters}
	occurred := time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC)
	usgs := NormalizedEvent{
		Source: "usgs", Action: "create", SourceID: "us-test", Time: occurred,
		Magnitude: 7.2, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
		Region: "Colombia", Tier: "세계", Urgent: true, Fingerprint: "us-v1",
	}
	if _, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, usgs); err != nil {
		t.Fatal(err)
	}
	emsc := NormalizedEvent{
		Source: "emsc", Action: "update", SourceID: "emsc-test", Time: occurred.Add(time.Second),
		Magnitude: 7.4, Latitude: 4.8765, Longitude: -76.2129, Depth: 110,
		Region: "COLOMBIA", Tier: "세계", Urgent: true, Fingerprint: "emsc-v1",
	}
	if alerted, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, emsc); err != nil || !alerted {
		t.Fatalf("EMSC material update alerted=%v err=%v", alerted, err)
	}
	usgs.Magnitude = 7.3
	usgs.Fingerprint = "us-v2"
	if alerted, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, usgs); err != nil || alerted {
		t.Fatalf("stale USGS revision alerted=%v err=%v", alerted, err)
	}
	if state.Earthquakes[0].Snapshot.Magnitude != 7.4 {
		t.Fatalf("canonical snapshot regressed: %+v", state.Earthquakes[0].Snapshot)
	}
}

func TestUSGSBaselineDoesNotReplay(t *testing.T) {
	mag := 7.2
	collection := usgsCollection{Features: []usgsFeature{{
		ID: "us-baseline",
		Properties: usgsProperties{
			Magnitude: &mag, Place: "Colombia",
			Time:    time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC).UnixMilli(),
			Updated: time.Date(2026, 8, 10, 12, 56, 12, 0, time.UTC).UnixMilli(),
		},
		Geometry: usgsGeometry{Coordinates: []float64{-76.2032, 4.8732, 95.2}},
	}}}
	state := testEarthquakeState()
	cfg := Config{StateFile: t.TempDir() + "/state.json", Filters: testFilters}
	if err := processUSGS(context.Background(), cfg, state, "", true, collection, "test-modified",
		time.Date(2026, 8, 10, 13, 0, 0, 0, time.UTC)); err != nil {
		t.Fatal(err)
	}
	if !state.USGSInitialized || len(state.USGSSeen) != 1 || len(state.Earthquakes) != 1 {
		t.Fatalf("unexpected baseline state: %+v", state)
	}
	if state.Earthquakes[0].Notified {
		t.Fatal("baseline-only record must not be marked as notified")
	}
	mag = 7.4
	collection.Features[0].Properties.Updated++
	event, err := normalizeUSGS(collection.Features[0], testFilters)
	if err != nil {
		t.Fatal(err)
	}
	event.Action = "update"
	alerted, _, err := processEarthquakeLocked(context.Background(), cfg, state, "", true, event)
	if err != nil || alerted || state.Earthquakes[0].Notified {
		t.Fatalf("historical baseline update alerted=%v notified=%v err=%v", alerted, state.Earthquakes[0].Notified, err)
	}
}

func TestUSGSBaselineAssociatesMigratedEMSCState(t *testing.T) {
	occurred := time.Date(2026, 8, 10, 12, 34, 27, 0, time.UTC)
	path := t.TempDir() + "/state.json"
	legacy := State{
		Seen: map[string]string{"emsc-test": "create|7.20|4.8732|-76.2032|95.2|v1"},
		Snapshots: map[string]EventSnapshot{"emsc-test": {
			Magnitude: 7.2, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
			Region: "COLOMBIA", OccurredAt: occurred.Format(time.RFC3339),
		}},
	}
	if err := writeJSONAtomic(path, legacy, 0o600); err != nil {
		t.Fatal(err)
	}
	state, err := loadState(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(state.Earthquakes) != 1 || state.Earthquakes[0].Sources["emsc"] != "emsc-test" ||
		!state.Earthquakes[0].Notified {
		t.Fatalf("legacy state was not migrated: %+v", state.Earthquakes)
	}
	mag := 7.3
	collection := usgsCollection{Features: []usgsFeature{{
		ID:         "us-test",
		Properties: usgsProperties{Magnitude: &mag, Place: "Colombia", Time: occurred.Add(time.Second).UnixMilli(), Updated: occurred.Add(time.Minute).UnixMilli()},
		Geometry:   usgsGeometry{Coordinates: []float64{-76.2129, 4.8765, 100}},
	}}}
	cfg := Config{StateFile: path, Filters: testFilters}
	if err := processUSGS(context.Background(), cfg, state, "", true, collection, "modified", occurred.Add(2*time.Minute)); err != nil {
		t.Fatal(err)
	}
	if len(state.Earthquakes) != 1 || state.Earthquakes[0].Sources["usgs"] != "us-test" {
		t.Fatalf("USGS baseline did not associate with EMSC: %+v", state.Earthquakes)
	}
}

func TestUSGSConditionalRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		if got := req.Header.Get("If-Modified-Since"); got != "Mon, 10 Aug 2026 15:36:50 GMT" {
			t.Errorf("If-Modified-Since=%q", got)
		}
		w.WriteHeader(http.StatusNotModified)
	}))
	defer server.Close()
	state := testEarthquakeState()
	state.USGSLastModified = "Mon, 10 Aug 2026 15:36:50 GMT"
	cfg := Config{USGS: USGSConfig{Enabled: true, URL: server.URL, IntervalMinutes: 1}}
	if err := pollUSGS(context.Background(), cfg, state, "", true); err != nil {
		t.Fatal(err)
	}
}

func TestCrossSourceMaterialThresholds(t *testing.T) {
	previous := EventSnapshot{
		Magnitude: 6.8, Latitude: 4.8732, Longitude: -76.2032, Depth: 95.2,
		Region: "Colombia", OccurredAt: "2026-08-10T12:34:27Z",
	}
	minor := NormalizedEvent{
		Magnitude: 6.9, Latitude: 4.8765, Longitude: -76.2129, Depth: 100,
		Region: "COLOMBIA", Tier: "세계",
	}
	if crossSourceMaterialChange(previous, minor, testFilters) {
		t.Fatal("minor cross-source differences should be suppressed")
	}
	urgent := minor
	urgent.Magnitude = 7.0
	urgent.Urgent = true
	if !crossSourceMaterialChange(previous, urgent, testFilters) {
		t.Fatal("urgent threshold crossing should alert")
	}
}

func testEarthquakeState() *State {
	return &State{
		Seen: map[string]string{}, Snapshots: map[string]EventSnapshot{},
		USGSSeen: map[string]string{}, USGSSnapshots: map[string]EventSnapshot{},
	}
}
