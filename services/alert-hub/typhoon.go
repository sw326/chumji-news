package main

import (
	"context"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"math"
	"net/http"
	"strconv"
	"strings"
	"time"
)

type jmaTyphoon struct {
	ReportDateTime     string           `json:"reportDateTime"`
	TargetDateTime     string           `json:"targetDateTime"`
	Name               string           `json:"name"`
	Number             string           `json:"number"`
	MeteorologicalInfo []jmaTyphoonInfo `json:"meteorologicalInfos"`
}

type jmaTyphoonInfo struct {
	DateTime string `json:"dateTime"`
	Class    struct {
		TyphoonClass string `json:"typhoonClass"`
		ClassName    string `json:"typhoonClassName"`
		Intensity    string `json:"intensityAndTyphoonClass"`
	} `json:"classPart"`
	Center struct {
		Latitude          string `json:"coordinateLat"`
		Longitude         string `json:"coordinateLon"`
		Direction         string `json:"direction"`
		SpeedKMH          string `json:"speedKmH"`
		Pressure          string `json:"pressure"`
		ProbabilityCircle *struct {
			BaseLatitude  string `json:"basePointLat"`
			BaseLongitude string `json:"basePointLon"`
			Axis          struct {
				RadiusKM string `json:"radiusKm"`
			} `json:"axis"`
		} `json:"probabilityCircle"`
	} `json:"centerPart"`
	Wind struct {
		SpeedMS     string `json:"windSpeedMS"`
		GustSpeedMS string `json:"windGustSpeedMS"`
	} `json:"windPart"`
}

type TyphoonPoint struct {
	DateTime  string  `json:"date_time"`
	Latitude  float64 `json:"latitude"`
	Longitude float64 `json:"longitude"`
	RadiusKM  float64 `json:"radius_km"`
}

type TyphoonSnapshot struct {
	Number           string         `json:"number"`
	Name             string         `json:"name"`
	ReportDateTime   string         `json:"report_date_time"`
	CurrentLatitude  float64        `json:"current_latitude"`
	CurrentLongitude float64        `json:"current_longitude"`
	Pressure         float64        `json:"pressure"`
	WindMS           float64        `json:"wind_ms"`
	GustMS           float64        `json:"gust_ms"`
	Intensity        string         `json:"intensity"`
	Class            string         `json:"class"`
	Direction        string         `json:"direction"`
	SpeedKMH         float64        `json:"speed_kmh"`
	Forecast         []TyphoonPoint `json:"forecast"`
	KoreaClearanceKM float64        `json:"korea_clearance_km"`
	ClosestAt        string         `json:"closest_at"`
	KoreaInfluence   bool           `json:"korea_influence"`
	DetailURL        string         `json:"detail_url"`
}

func pollTyphoons(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	current := map[string]TyphoonSnapshot{}
	for slot := 60; slot <= 65; slot++ {
		snapshot, ok, err := fetchTyphoon(ctx, cfg, slot)
		if err != nil {
			return err
		}
		if ok {
			current[snapshot.Number] = snapshot
		}
	}

	stateMu.Lock()
	defer stateMu.Unlock()
	if !state.TyphoonInitialized {
		state.Typhoons = current
		state.TyphoonInitialized = true
		if err := writeJSONAtomic(cfg.StateFile, state, 0o600); err != nil {
			return err
		}
		fmt.Printf("JMA typhoon baseline initialized with %d active storms; no historical alerts sent\n", len(current))
		return nil
	}

	for number, snapshot := range current {
		previous, exists := state.Typhoons[number]
		kind, changes := typhoonTransition(previous, exists, snapshot, cfg.Typhoon)
		if kind != "" {
			message := formatTyphoonAlert(kind, changes, snapshot)
			if dryRun {
				fmt.Printf("TYPHOON DRY RUN\n%s\n", message)
			} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
				Source: "typhoon", EventID: snapshot.Number, Action: kind, Severity: snapshot.Intensity,
			}), token, cfg.TelegramChatID, message); err != nil {
				return err
			}
		}
		state.Typhoons[number] = snapshot
	}
	for number, previous := range state.Typhoons {
		if _, exists := current[number]; exists {
			continue
		}
		message := formatTyphoonAlert("resolved", []string{"JMA 활성 태풍 목록에서 종료"}, previous)
		if dryRun {
			fmt.Printf("TYPHOON DRY RUN\n%s\n", message)
		} else if err := sendTelegram(withAlertMeta(ctx, AlertMeta{
			Source: "typhoon", EventID: previous.Number, Action: "resolved", Severity: previous.Intensity,
		}), token, cfg.TelegramChatID, message); err != nil {
			return err
		}
		delete(state.Typhoons, number)
	}
	return writeJSONAtomic(cfg.StateFile, state, 0o600)
}

func fetchTyphoon(ctx context.Context, cfg Config, slot int) (TyphoonSnapshot, bool, error) {
	target := fmt.Sprintf(cfg.Typhoon.URLTemplate, slot)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return TyphoonSnapshot{}, false, err
	}
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "chumji-alert-hub/1.0")
	client := &http.Client{Timeout: 20 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return TyphoonSnapshot{}, false, fmt.Errorf("request JMA typhoon slot %d: %w", slot, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		return TyphoonSnapshot{}, false, nil
	}
	if resp.StatusCode != http.StatusOK {
		return TyphoonSnapshot{}, false, fmt.Errorf("JMA typhoon slot %d status %d", slot, resp.StatusCode)
	}
	var report jmaTyphoon
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&report); err != nil {
		return TyphoonSnapshot{}, false, fmt.Errorf("parse JMA typhoon slot %d: %w", slot, err)
	}
	snapshot, ok := normalizeTyphoon(report, cfg, slot, time.Now())
	return snapshot, ok, nil
}

func normalizeTyphoon(report jmaTyphoon, cfg Config, slot int, now time.Time) (TyphoonSnapshot, bool) {
	if report.Number == "" || len(report.MeteorologicalInfo) == 0 {
		return TyphoonSnapshot{}, false
	}
	reported, err := time.ParseInLocation("2006/01/02 15:04", report.ReportDateTime, time.FixedZone("JST", 9*60*60))
	if err != nil || now.Sub(reported) > 24*time.Hour || now.Sub(reported) < -5*time.Minute {
		return TyphoonSnapshot{}, false
	}
	first := report.MeteorologicalInfo[0]
	if !activeTyphoonClass(first.Class.TyphoonClass) {
		return TyphoonSnapshot{}, false
	}
	currentLat, okLat := parseTyphoonCoordinate(first.Center.Latitude)
	currentLon, okLon := parseTyphoonCoordinate(first.Center.Longitude)
	if !okLat || !okLon {
		return TyphoonSnapshot{}, false
	}
	points := make([]TyphoonPoint, 0, len(report.MeteorologicalInfo))
	minClearance := math.Inf(1)
	closestAt := ""
	for _, info := range report.MeteorologicalInfo {
		latText, lonText, radiusText := info.Center.Latitude, info.Center.Longitude, ""
		if info.Center.ProbabilityCircle != nil {
			latText = info.Center.ProbabilityCircle.BaseLatitude
			lonText = info.Center.ProbabilityCircle.BaseLongitude
			radiusText = info.Center.ProbabilityCircle.Axis.RadiusKM
		}
		lat, ok1 := parseTyphoonCoordinate(latText)
		lon, ok2 := parseTyphoonCoordinate(lonText)
		if !ok1 || !ok2 {
			continue
		}
		radius, _ := strconv.ParseFloat(radiusText, 64)
		point := TyphoonPoint{DateTime: info.DateTime, Latitude: lat, Longitude: lon, RadiusKM: radius}
		points = append(points, point)
		clearance := haversineKM(cfg.Filters.KoreaCenterLat, cfg.Filters.KoreaCenterLon, lat, lon) - radius
		if clearance < minClearance {
			minClearance, closestAt = clearance, info.DateTime
		}
	}
	pressure, _ := strconv.ParseFloat(first.Center.Pressure, 64)
	wind, _ := strconv.ParseFloat(first.Wind.SpeedMS, 64)
	gust, _ := strconv.ParseFloat(first.Wind.GustSpeedMS, 64)
	speed, _ := strconv.ParseFloat(first.Center.SpeedKMH, 64)
	return TyphoonSnapshot{
		Number: report.Number, Name: report.Name, ReportDateTime: report.ReportDateTime,
		CurrentLatitude: currentLat, CurrentLongitude: currentLon,
		Pressure: pressure, WindMS: wind, GustMS: gust,
		Intensity: first.Class.Intensity, Class: first.Class.TyphoonClass,
		Direction: first.Center.Direction, SpeedKMH: speed, Forecast: points,
		KoreaClearanceKM: minClearance, ClosestAt: closestAt,
		KoreaInfluence: minClearance <= cfg.Typhoon.KoreaInfluenceKM,
		DetailURL:      fmt.Sprintf("https://www.data.jma.go.jp/multi/cyclone/cyclone_detail.html?id=%d&lang=kr", slot),
	}, true
}

func activeTyphoonClass(class string) bool {
	switch class {
	case "TY", "STS", "TS", "TD", "Tropical Storm", "Tropical Cyclone", "Hurricane":
		return true
	default:
		return false
	}
}

func parseTyphoonCoordinate(value string) (float64, bool) {
	value = strings.TrimSpace(value)
	if len(value) < 2 {
		return 0, false
	}
	direction := value[len(value)-1]
	number, err := strconv.ParseFloat(value[:len(value)-1], 64)
	if err != nil {
		return 0, false
	}
	if direction == 'S' || direction == 'W' {
		number = -number
	}
	return number, direction == 'N' || direction == 'S' || direction == 'E' || direction == 'W'
}

func typhoonTransition(previous TyphoonSnapshot, exists bool, current TyphoonSnapshot, cfg TyphoonConfig) (string, []string) {
	if !exists {
		return "new", nil
	}
	if previous.ReportDateTime == current.ReportDateTime {
		return "", nil
	}
	var changes []string
	kind := ""
	if !previous.KoreaInfluence && current.KoreaInfluence {
		kind = "korea"
		changes = append(changes, fmt.Sprintf("한국 영향 가능권 진입 · 최근접 약 %.0fkm", math.Max(0, current.KoreaClearanceKM)))
	}
	if typhoonIntensityRank(current.Intensity) > typhoonIntensityRank(previous.Intensity) {
		if kind == "" {
			kind = "strengthened"
		}
		changes = append(changes, previous.Intensity+" → "+current.Intensity)
	}
	if previous.Pressure-current.Pressure >= 20 {
		if kind == "" {
			kind = "strengthened"
		}
		changes = append(changes, fmt.Sprintf("중심기압 %.0f → %.0fhPa", previous.Pressure, current.Pressure))
	}
	if current.WindMS-previous.WindMS >= 10 {
		if kind == "" {
			kind = "strengthened"
		}
		changes = append(changes, fmt.Sprintf("최대풍속 %.0f → %.0fm/s", previous.WindMS, current.WindMS))
	}
	shift := maxTyphoonTrackShift(previous.Forecast, current.Forecast)
	if shift >= cfg.TrackShiftKM && current.KoreaClearanceKM <= cfg.KoreaNearbyKM {
		if kind == "" {
			kind = "track"
		}
		changes = append(changes, fmt.Sprintf("예상 경로 최대 약 %.0fkm 조정", shift))
	}
	return kind, changes
}

func typhoonIntensityRank(value string) int {
	switch {
	case strings.Contains(value, "맹렬"):
		return 4
	case strings.Contains(value, "매우 강"):
		return 3
	case strings.Contains(value, "강한"):
		return 2
	default:
		return 1
	}
}

func maxTyphoonTrackShift(previous, current []TyphoonPoint) float64 {
	previousByTime := map[string]TyphoonPoint{}
	for _, point := range previous {
		previousByTime[point.DateTime] = point
	}
	var maximum float64
	for _, point := range current {
		if old, ok := previousByTime[point.DateTime]; ok {
			shift := haversineKM(old.Latitude, old.Longitude, point.Latitude, point.Longitude)
			if shift > maximum {
				maximum = shift
			}
		}
	}
	return maximum
}

func formatTyphoonAlert(kind string, changes []string, current TyphoonSnapshot) string {
	action := map[string]string{
		"new": "🆕 발생", "strengthened": "⬆️ 강화", "track": "🔄 진로 변경",
		"korea": "🇰🇷 한국 영향 가능", "resolved": "✅ 종료",
	}[kind]
	name := "제" + typhoonDisplayNumber(current.Number) + "호 " + current.Name
	message := fmt.Sprintf(
		"<b>🌀 태풍 %s · %s</b>\n\n<b>강도</b>  %s\n<b>중심기압</b>  %.0fhPa\n<b>최대풍속</b>  %.0fm/s\n<b>이동</b>  %s %.0fkm/h\n<b>발표</b>  %s",
		html.EscapeString(name), action, html.EscapeString(current.Intensity),
		current.Pressure, current.WindMS, html.EscapeString(current.Direction), current.SpeedKMH,
		html.EscapeString(current.ReportDateTime+" KST"),
	)
	if !math.IsInf(current.KoreaClearanceKM, 0) {
		message += fmt.Sprintf("\n<b>한국 최근접 전망</b>  약 %.0fkm · %s",
			math.Max(0, current.KoreaClearanceKM), html.EscapeString(current.ClosestAt+" KST"))
	}
	if len(changes) > 0 {
		message += "\n\n<b>주요 변화</b>\n• " + html.EscapeString(strings.Join(changes, "\n• "))
	}
	message += "\n\n<a href=\"" + html.EscapeString(current.DetailURL) + "\">JMA 태풍정보 보기</a>"
	message += "\n<code>JMA T" + html.EscapeString(current.Number) + "</code>"
	return message
}

func typhoonDisplayNumber(number string) string {
	if len(number) >= 2 {
		if value, err := strconv.Atoi(number[len(number)-2:]); err == nil {
			return strconv.Itoa(value)
		}
	}
	return number
}
