package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"
	"sort"
	"strings"
	"time"
)

const (
	maxUSGSSeen               = 2000
	maxEarthquakeRecords      = 2000
	crossSourceTimeWindow     = 30 * time.Second
	crossSourceDistanceKM     = 100.0
	crossSourceMagnitudeDelta = 1.5
)

type USGSConfig struct {
	Enabled         bool   `json:"enabled"`
	URL             string `json:"url"`
	IntervalMinutes int    `json:"interval_minutes"`
}

type usgsCollection struct {
	Features []usgsFeature `json:"features"`
}

type usgsFeature struct {
	ID         string         `json:"id"`
	Properties usgsProperties `json:"properties"`
	Geometry   usgsGeometry   `json:"geometry"`
}

type usgsProperties struct {
	Magnitude *float64 `json:"mag"`
	Place     string   `json:"place"`
	Time      int64    `json:"time"`
	Updated   int64    `json:"updated"`
	URL       string   `json:"url"`
	Detail    string   `json:"detail"`
}

type usgsGeometry struct {
	Coordinates []float64 `json:"coordinates"`
}

func pollUSGS(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, cfg.USGS.URL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/geo+json, application/json")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	stateMu.Lock()
	lastModified := state.USGSLastModified
	stateMu.Unlock()
	if lastModified != "" {
		req.Header.Set("If-Modified-Since", lastModified)
	}
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("request USGS earthquake feed: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotModified {
		return nil
	}
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("USGS earthquake feed status %d", resp.StatusCode)
	}
	var collection usgsCollection
	if err := json.NewDecoder(io.LimitReader(resp.Body, 2<<20)).Decode(&collection); err != nil {
		return fmt.Errorf("parse USGS earthquake feed: %w", err)
	}
	return processUSGS(ctx, cfg, state, token, dryRun, collection, resp.Header.Get("Last-Modified"), time.Now())
}

func processUSGS(ctx context.Context, cfg Config, state *State, token string, dryRun bool,
	collection usgsCollection, lastModified string, now time.Time,
) error {
	events := make([]NormalizedEvent, 0, len(collection.Features))
	for _, feature := range collection.Features {
		event, err := normalizeUSGS(feature, cfg.Filters)
		if err != nil {
			log.Printf("USGS event skipped: %v", err)
			continue
		}
		events = append(events, event)
	}
	sort.Slice(events, func(i, j int) bool { return events[i].Time.Before(events[j].Time) })

	stateMu.Lock()
	defer stateMu.Unlock()
	validatorChanged := lastModified != "" && lastModified != state.USGSLastModified
	if lastModified != "" {
		state.USGSLastModified = lastModified
	}
	if !state.USGSInitialized {
		for _, event := range events {
			rememberUSGS(state, event)
			if event.Tier != "" {
				rememberEarthquakeRecord(state, event, false, false)
			}
		}
		state.USGSInitialized = true
		if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
			return err
		}
		fmt.Printf("USGS baseline initialized with %d events; no historical alerts sent\n", len(events))
		return nil
	}

	changed := false
	for _, event := range events {
		if previous, ok := state.USGSSeen[event.SourceID]; ok && previous == event.Fingerprint {
			continue
		}
		previous, hasPrevious := state.USGSSnapshots[event.SourceID]
		if event.Tier == "" || !usgsFresh(event, now) {
			rememberUSGS(state, event)
			changed = true
			continue
		}
		event.Action = "create"
		if hasPrevious && snapshotTier(previous, cfg.Filters) != "" {
			event.Action = "update"
		}
		_, eventChanged, err := processEarthquakeLocked(ctx, cfg, state, token, dryRun, event)
		if err != nil {
			return err
		}
		changed = changed || eventChanged
	}
	if changed || validatorChanged {
		return writeJSONAtomic(cfg.StateFile, state, 0o600)
	}
	return nil
}

func normalizeUSGS(feature usgsFeature, filters FilterConfig) (NormalizedEvent, error) {
	if strings.TrimSpace(feature.ID) == "" {
		return NormalizedEvent{}, fmt.Errorf("missing USGS event id")
	}
	if feature.Properties.Magnitude == nil {
		return NormalizedEvent{}, fmt.Errorf("USGS %s missing magnitude", feature.ID)
	}
	if feature.Properties.Time <= 0 || len(feature.Geometry.Coordinates) < 3 {
		return NormalizedEvent{}, fmt.Errorf("USGS %s missing origin data", feature.ID)
	}
	lon, lat, depth := feature.Geometry.Coordinates[0], feature.Geometry.Coordinates[1], feature.Geometry.Coordinates[2]
	if lat < -90 || lat > 90 || lon < -180 || lon > 180 {
		return NormalizedEvent{}, fmt.Errorf("USGS %s has invalid coordinates", feature.ID)
	}
	magnitude := *feature.Properties.Magnitude
	occurred := time.UnixMilli(feature.Properties.Time).UTC()
	distance := haversineKM(filters.KoreaCenterLat, filters.KoreaCenterLon, lat, lon)
	region := strings.TrimSpace(feature.Properties.Place)
	tier := classify(distance, magnitude, region, filters)
	detailURL := strings.TrimSpace(feature.Properties.URL)
	if detailURL == "" {
		detailURL = strings.TrimSpace(feature.Properties.Detail)
	}
	return NormalizedEvent{
		Source: "usgs", SourceID: feature.ID, Time: occurred,
		Magnitude: magnitude, Latitude: lat, Longitude: lon, Depth: depth,
		Region: region, DistanceKM: distance, Tier: tier,
		Urgent:      magnitude >= filters.UrgentMinMagnitude,
		Fingerprint: fmt.Sprintf("%.2f|%.4f|%.4f|%.1f|%d", magnitude, lat, lon, depth, feature.Properties.Updated),
		DetailURL:   detailURL,
	}, nil
}

func usgsFresh(event NormalizedEvent, now time.Time) bool {
	age := now.Sub(event.Time)
	return age >= -5*time.Minute && age <= 90*time.Minute
}

func processEarthquakeLocked(ctx context.Context, cfg Config, state *State, token string, dryRun bool,
	event NormalizedEvent,
) (alerted, changed bool, err error) {
	event.Source = strings.ToLower(strings.TrimSpace(event.Source))
	if event.Source == "" {
		event.Source = "emsc"
	}
	if previous, ok := sourceSeen(state, event.Source, event.SourceID); ok && previous == event.Fingerprint {
		return false, false, nil
	}
	previous, hasPrevious := sourceSnapshot(state, event.Source, event.SourceID)
	recordIndex, sameSource := findEarthquakeRecord(state, event)
	if recordIndex >= 0 && !state.Earthquakes[recordIndex].Notified {
		rememberSourceEvent(state, event)
		rememberEarthquakeRecord(state, event, true, false)
		return false, true, nil
	}
	if recordIndex >= 0 && (!sameSource || len(state.Earthquakes[recordIndex].Sources) > 1) {
		previous = state.Earthquakes[recordIndex].Snapshot
		hasPrevious = true
		if !crossSourceMaterialChange(previous, event, cfg.Filters) {
			rememberSourceEvent(state, event)
			rememberEarthquakeRecord(state, event, false, false)
			return false, true, nil
		}
		event.Action = "update"
	}
	if event.Source == "usgs" && hasPrevious && event.Action == "update" && formatChanges(previous, event) == "" {
		rememberSourceEvent(state, event)
		rememberEarthquakeRecord(state, event, false, false)
		return false, true, nil
	}
	if strings.EqualFold(event.Action, "update") && hasPrevious {
		if !earthquakeEscalated(previous, event, cfg.Filters) {
			rememberSourceEvent(state, event)
			rememberEarthquakeRecord(state, event, false, false)
			return false, true, nil
		}
		event.Action = "escalated"
	}

	message := formatAlert(event, previous, hasPrevious)
	if dryRun {
		log.Printf("%s DRY RUN\n%s", strings.ToUpper(event.Source), message)
	} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
		Source: event.Source, EventID: event.SourceID, Action: event.Action,
		Severity: event.Tier, OccurredAt: event.Time,
	}), token, cfg.TelegramChatID, message); err != nil {
		return false, false, err
	}
	rememberSourceEvent(state, event)
	rememberEarthquakeRecord(state, event, true, true)
	return true, true, nil
}

func sourceSeen(state *State, source, id string) (string, bool) {
	if source == "usgs" {
		value, ok := state.USGSSeen[id]
		return value, ok
	}
	value, ok := state.Seen[id]
	return value, ok
}

func sourceSnapshot(state *State, source, id string) (EventSnapshot, bool) {
	if source == "usgs" {
		value, ok := state.USGSSnapshots[id]
		return value, ok
	}
	value, ok := state.Snapshots[id]
	return value, ok
}

func rememberSourceEvent(state *State, event NormalizedEvent) {
	if event.Source == "usgs" {
		rememberUSGS(state, event)
		return
	}
	remember(state, event)
}

func rememberUSGS(state *State, event NormalizedEvent) {
	if state.USGSSeen == nil {
		state.USGSSeen = map[string]string{}
	}
	if state.USGSSnapshots == nil {
		state.USGSSnapshots = map[string]EventSnapshot{}
	}
	if _, exists := state.USGSSeen[event.SourceID]; !exists {
		state.USGSOrder = append(state.USGSOrder, event.SourceID)
	}
	state.USGSSeen[event.SourceID] = event.Fingerprint
	state.USGSSnapshots[event.SourceID] = snapshotFromEvent(event)
	for len(state.USGSOrder) > maxUSGSSeen {
		oldest := state.USGSOrder[0]
		state.USGSOrder = state.USGSOrder[1:]
		delete(state.USGSSeen, oldest)
		delete(state.USGSSnapshots, oldest)
	}
}

func findEarthquakeRecord(state *State, event NormalizedEvent) (index int, sameSource bool) {
	for i := range state.Earthquakes {
		record := &state.Earthquakes[i]
		if record.Sources[event.Source] == event.SourceID {
			return i, true
		}
	}
	for i := range state.Earthquakes {
		record := &state.Earthquakes[i]
		if _, alreadyAssociated := record.Sources[event.Source]; alreadyAssociated {
			continue
		}
		if sameEarthquake(record.Snapshot, event) {
			return i, false
		}
	}
	return -1, false
}

func sameEarthquake(previous EventSnapshot, current NormalizedEvent) bool {
	occurred, err := parseEventTime(previous.OccurredAt)
	if err != nil || math.Abs(current.Time.Sub(occurred).Seconds()) > crossSourceTimeWindow.Seconds() {
		return false
	}
	if math.Abs(previous.Magnitude-current.Magnitude) > crossSourceMagnitudeDelta {
		return false
	}
	return haversineKM(previous.Latitude, previous.Longitude, current.Latitude, current.Longitude) <= crossSourceDistanceKM
}

func crossSourceMaterialChange(previous EventSnapshot, current NormalizedEvent, filters FilterConfig) bool {
	if strings.EqualFold(current.Action, "delete") {
		return false
	}
	if math.Abs(previous.Magnitude-current.Magnitude) >= 0.2 {
		return true
	}
	if (previous.Magnitude >= filters.UrgentMinMagnitude) != current.Urgent {
		return true
	}
	if snapshotTier(previous, filters) != current.Tier {
		return true
	}
	if previous.Depth > 0 && current.Depth > 0 && math.Abs(previous.Depth-current.Depth) >= 20 {
		return true
	}
	return haversineKM(previous.Latitude, previous.Longitude, current.Latitude, current.Longitude) >= 25
}

func snapshotTier(snapshot EventSnapshot, filters FilterConfig) string {
	distance := haversineKM(filters.KoreaCenterLat, filters.KoreaCenterLon, snapshot.Latitude, snapshot.Longitude)
	return classify(distance, snapshot.Magnitude, snapshot.Region, filters)
}

func earthquakeEscalated(previous EventSnapshot, current NormalizedEvent, filters FilterConfig) bool {
	previousUrgent := previous.Magnitude >= filters.UrgentMinMagnitude
	if !previousUrgent && current.Urgent {
		return true
	}
	if earthquakeTierRank(current.Tier) > earthquakeTierRank(snapshotTier(previous, filters)) {
		return true
	}
	return current.Magnitude-previous.Magnitude >= 0.5
}

func earthquakeTierRank(tier string) int {
	switch tier {
	case "한국 주변":
		return 3
	case "동아시아":
		return 2
	case "세계":
		return 1
	default:
		return 0
	}
}

func rememberEarthquakeRecord(state *State, event NormalizedEvent, updateSnapshot, markNotified bool) {
	index, _ := findEarthquakeRecord(state, event)
	if index < 0 {
		state.Earthquakes = append(state.Earthquakes, EarthquakeRecord{
			Sources: map[string]string{event.Source: event.SourceID}, Snapshot: snapshotFromEvent(event),
			Notified: markNotified,
		})
	} else {
		if state.Earthquakes[index].Sources == nil {
			state.Earthquakes[index].Sources = map[string]string{}
		}
		state.Earthquakes[index].Sources[event.Source] = event.SourceID
		if updateSnapshot {
			state.Earthquakes[index].Snapshot = snapshotFromEvent(event)
		}
		if markNotified {
			state.Earthquakes[index].Notified = true
		}
	}
	for len(state.Earthquakes) > maxEarthquakeRecords {
		state.Earthquakes = state.Earthquakes[1:]
	}
}

func snapshotFromEvent(event NormalizedEvent) EventSnapshot {
	return EventSnapshot{
		Magnitude: event.Magnitude, Latitude: event.Latitude, Longitude: event.Longitude,
		Depth: event.Depth, Region: event.Region, OccurredAt: event.Time.Format(time.RFC3339Nano),
	}
}

func earthquakeSourceLabel(source string) string {
	if strings.EqualFold(source, "usgs") {
		return "USGS"
	}
	return "EMSC"
}
