package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"html"
	"io"
	"log"
	"math"
	"math/rand/v2"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

const (
	defaultWebSocketURL = "wss://www.seismicportal.eu/standing_order/websocket"
	maxSeenEvents       = 2000
)

type Config struct {
	WebSocketURL      string        `json:"websocket_url"`
	TelegramChatID    string        `json:"telegram_chat_id"`
	TelegramTokenFile string        `json:"telegram_token_file"`
	StateFile         string        `json:"state_file"`
	HealthFile        string        `json:"health_file"`
	USGS              USGSConfig    `json:"usgs"`
	GDACS             GDACSConfig   `json:"gdacs"`
	Tsunami           TsunamiConfig `json:"tsunami"`
	SWPC              SWPCConfig    `json:"swpc"`
	KMA               KMAConfig     `json:"kma"`
	Typhoon           TyphoonConfig `json:"typhoon"`
	History           HistoryConfig `json:"history"`
	Filters           FilterConfig  `json:"filters"`
}

type GDACSConfig struct {
	Enabled         bool   `json:"enabled"`
	URL             string `json:"url"`
	RSSFallbackURL  string `json:"rss_fallback_url"`
	IntervalMinutes int    `json:"interval_minutes"`
}

type TsunamiConfig struct {
	Enabled               bool   `json:"enabled"`
	URL                   string `json:"url"`
	IdleIntervalMinutes   int    `json:"idle_interval_minutes"`
	ActiveIntervalMinutes int    `json:"active_interval_minutes"`
}

type SWPCConfig struct {
	Enabled         bool   `json:"enabled"`
	URL             string `json:"url"`
	IntervalMinutes int    `json:"interval_minutes"`
}

type KMAConfig struct {
	Enabled         bool   `json:"enabled"`
	URL             string `json:"url"`
	Station         string `json:"station"`
	IntervalMinutes int    `json:"interval_minutes"`
}

type TyphoonConfig struct {
	Enabled          bool    `json:"enabled"`
	URLTemplate      string  `json:"url_template"`
	IntervalMinutes  int     `json:"interval_minutes"`
	KoreaInfluenceKM float64 `json:"korea_influence_km"`
	KoreaNearbyKM    float64 `json:"korea_nearby_km"`
	TrackShiftKM     float64 `json:"track_shift_km"`
}

type FilterConfig struct {
	KoreaCenterLat       float64 `json:"korea_center_lat"`
	KoreaCenterLon       float64 `json:"korea_center_lon"`
	KoreaRadiusKM        float64 `json:"korea_radius_km"`
	KoreaMinMagnitude    float64 `json:"korea_min_magnitude"`
	RegionalRadiusKM     float64 `json:"regional_radius_km"`
	RegionalMinMagnitude float64 `json:"regional_min_magnitude"`
	GlobalMinMagnitude   float64 `json:"global_min_magnitude"`
	UrgentMinMagnitude   float64 `json:"urgent_min_magnitude"`
}

type Envelope struct {
	Action string  `json:"action"`
	Data   Feature `json:"data"`
}

type Feature struct {
	Properties Event `json:"properties"`
}

type Event struct {
	Auth       string      `json:"auth"`
	SourceID   string      `json:"unid"`
	Time       string      `json:"time"`
	Magnitude  json.Number `json:"mag"`
	Latitude   json.Number `json:"lat"`
	Longitude  json.Number `json:"lon"`
	Depth      json.Number `json:"depth"`
	Region     string      `json:"flynn_region"`
	LastUpdate string      `json:"lastupdate"`
}

type NormalizedEvent struct {
	Source      string
	Action      string
	SourceID    string
	Time        time.Time
	Magnitude   float64
	Latitude    float64
	Longitude   float64
	Depth       float64
	Region      string
	DistanceKM  float64
	Tier        string
	Urgent      bool
	Fingerprint string
	DetailURL   string
}

type State struct {
	Seen               map[string]string          `json:"seen"`
	Snapshots          map[string]EventSnapshot   `json:"snapshots,omitempty"`
	USGSSeen           map[string]string          `json:"usgs_seen,omitempty"`
	USGSSnapshots      map[string]EventSnapshot   `json:"usgs_snapshots,omitempty"`
	USGSOrder          []string                   `json:"usgs_order,omitempty"`
	USGSInitialized    bool                       `json:"usgs_initialized,omitempty"`
	USGSLastModified   string                     `json:"usgs_last_modified,omitempty"`
	Earthquakes        []EarthquakeRecord         `json:"earthquakes,omitempty"`
	GDACS              map[string]GDACSSnapshot   `json:"gdacs,omitempty"`
	GDACSInitialized   bool                       `json:"gdacs_initialized,omitempty"`
	Tsunami            TsunamiSnapshot            `json:"tsunami,omitempty"`
	TsunamiInitialized bool                       `json:"tsunami_initialized,omitempty"`
	SWPCSeen           map[string]bool            `json:"swpc_seen,omitempty"`
	SWPCOrder          []string                   `json:"swpc_order,omitempty"`
	SWPCInitialized    bool                       `json:"swpc_initialized,omitempty"`
	SWPCETag           string                     `json:"swpc_etag,omitempty"`
	SWPCLastModified   string                     `json:"swpc_last_modified,omitempty"`
	KMASeen            map[string]bool            `json:"kma_seen,omitempty"`
	KMAOrder           []string                   `json:"kma_order,omitempty"`
	KMAInitialized     bool                       `json:"kma_initialized,omitempty"`
	Typhoons           map[string]TyphoonSnapshot `json:"typhoons,omitempty"`
	TyphoonInitialized bool                       `json:"typhoon_initialized,omitempty"`
	Order              []string                   `json:"order"`
}

type EventSnapshot struct {
	Magnitude  float64 `json:"magnitude"`
	Latitude   float64 `json:"latitude"`
	Longitude  float64 `json:"longitude"`
	Depth      float64 `json:"depth"`
	Region     string  `json:"region"`
	OccurredAt string  `json:"occurred_at"`
}

type EarthquakeRecord struct {
	Sources  map[string]string `json:"sources"`
	Snapshot EventSnapshot     `json:"snapshot"`
	Notified bool              `json:"notified"`
}

type Health struct {
	Status            string    `json:"status"`
	UpdatedAt         time.Time `json:"updated_at"`
	ConnectedAt       time.Time `json:"connected_at,omitempty"`
	LastMessageAt     time.Time `json:"last_message_at,omitempty"`
	LastAlertAt       time.Time `json:"last_alert_at,omitempty"`
	LastUSGSPollAt    time.Time `json:"last_usgs_poll_at,omitempty"`
	LastUSGSError     string    `json:"last_usgs_error,omitempty"`
	LastGDACSPollAt   time.Time `json:"last_gdacs_poll_at,omitempty"`
	LastGDACSError    string    `json:"last_gdacs_error,omitempty"`
	LastTsunamiPollAt time.Time `json:"last_tsunami_poll_at,omitempty"`
	LastTsunamiError  string    `json:"last_tsunami_error,omitempty"`
	LastSWPCPollAt    time.Time `json:"last_swpc_poll_at,omitempty"`
	LastSWPCError     string    `json:"last_swpc_error,omitempty"`
	LastKMAPollAt     time.Time `json:"last_kma_poll_at,omitempty"`
	LastKMAError      string    `json:"last_kma_error,omitempty"`
	LastTyphoonPollAt time.Time `json:"last_typhoon_poll_at,omitempty"`
	LastTyphoonError  string    `json:"last_typhoon_error,omitempty"`
	ReconnectAttempts int       `json:"reconnect_attempts"`
	Error             string    `json:"error,omitempty"`
}

var stateMu sync.Mutex
var historyStore *HistoryStore

func main() {
	var configPath string
	var dryRun bool
	var fixturePath string
	var testNotification bool
	flag.StringVar(&configPath, "config", "", "path to configuration JSON")
	flag.BoolVar(&dryRun, "dry-run", false, "log alerts without sending Telegram messages")
	flag.StringVar(&fixturePath, "fixture", "", "process one local EMSC JSON fixture and exit")
	flag.BoolVar(&testNotification, "test-notification", false, "send one clearly marked Telegram test message and exit")
	flag.Parse()

	if configPath == "" {
		log.Fatal("-config is required")
	}
	cfg, err := loadConfig(configPath)
	if err != nil {
		log.Fatal(err)
	}
	state, err := loadState(cfg.StateFile)
	if err != nil {
		log.Fatal(err)
	}
	if cfg.History.Enabled {
		historyStore, err = OpenHistoryStore(cfg.History.DatabaseFile)
		if err != nil {
			log.Printf("history disabled after database open failure: %v", err)
		} else {
			defer historyStore.Close()
		}
	}

	token := ""
	if !dryRun {
		token, err = readSecret(cfg.TelegramTokenFile)
		if err != nil {
			log.Fatal(err)
		}
	}

	if testNotification {
		message := "<b>🧪 지진 알림 테스트</b>\n\nEMSC WebSocket 연결 및 Telegram 전송 경로가 정상입니다.\n<i>실제 지진 경보가 아닙니다.</i>"
		if dryRun {
			log.Printf("DRY RUN\n%s", message)
			return
		}
		testCtx := withAlertMeta(context.Background(), AlertMeta{Source: "system", EventID: "test", Action: "test"})
		if err := sendTelegram(testCtx, token, cfg.TelegramChatID, message); err != nil {
			log.Fatal(err)
		}
		log.Print("test notification sent")
		return
	}

	if fixturePath != "" {
		raw, readErr := os.ReadFile(fixturePath)
		if readErr != nil {
			log.Fatal(readErr)
		}
		if _, err := processMessage(context.Background(), cfg, state, token, dryRun, raw); err != nil {
			log.Fatal(err)
		}
		return
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := run(ctx, cfg, state, token, dryRun); err != nil && !errors.Is(err, context.Canceled) {
		log.Fatal(err)
	}
}

func loadConfig(path string) (Config, error) {
	var cfg Config
	raw, err := os.ReadFile(path)
	if err != nil {
		return cfg, fmt.Errorf("read config: %w", err)
	}
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return cfg, fmt.Errorf("parse config: %w", err)
	}
	if cfg.WebSocketURL == "" {
		cfg.WebSocketURL = defaultWebSocketURL
	}
	if cfg.TelegramChatID == "" || cfg.StateFile == "" || cfg.HealthFile == "" {
		return cfg, errors.New("telegram_chat_id, state_file, and health_file are required")
	}
	if cfg.Filters.KoreaRadiusKM <= 0 || cfg.Filters.RegionalRadiusKM <= 0 ||
		cfg.Filters.KoreaMinMagnitude <= 0 || cfg.Filters.RegionalMinMagnitude <= 0 ||
		cfg.Filters.GlobalMinMagnitude <= 0 {
		return cfg, errors.New("all filter radii and magnitude thresholds must be positive")
	}
	if cfg.USGS.Enabled && (cfg.USGS.URL == "" || cfg.USGS.IntervalMinutes <= 0) {
		return cfg, errors.New("usgs.url and positive usgs.interval_minutes are required when USGS is enabled")
	}
	if cfg.GDACS.Enabled && (cfg.GDACS.URL == "" || cfg.GDACS.RSSFallbackURL == "" || cfg.GDACS.IntervalMinutes <= 0) {
		return cfg, errors.New("gdacs.url, gdacs.rss_fallback_url, and positive gdacs.interval_minutes are required when GDACS is enabled")
	}
	if cfg.Tsunami.Enabled && (cfg.Tsunami.URL == "" || cfg.Tsunami.IdleIntervalMinutes <= 0 ||
		cfg.Tsunami.ActiveIntervalMinutes <= 0) {
		return cfg, errors.New("tsunami.url and positive tsunami intervals are required when tsunami is enabled")
	}
	if cfg.SWPC.Enabled && (cfg.SWPC.URL == "" || cfg.SWPC.IntervalMinutes <= 0) {
		return cfg, errors.New("swpc.url and positive swpc.interval_minutes are required when SWPC is enabled")
	}
	if cfg.KMA.Enabled && (cfg.KMA.URL == "" || cfg.KMA.Station == "" || cfg.KMA.IntervalMinutes <= 0) {
		return cfg, errors.New("kma.url, kma.station, and positive kma.interval_minutes are required when KMA is enabled")
	}
	if cfg.Typhoon.Enabled && (cfg.Typhoon.URLTemplate == "" || !strings.Contains(cfg.Typhoon.URLTemplate, "%d") ||
		cfg.Typhoon.IntervalMinutes <= 0 || cfg.Typhoon.KoreaInfluenceKM <= 0 ||
		cfg.Typhoon.KoreaNearbyKM <= 0 || cfg.Typhoon.TrackShiftKM <= 0) {
		return cfg, errors.New("typhoon URL template and positive interval/distance thresholds are required when typhoon is enabled")
	}
	if cfg.History.Enabled {
		if cfg.History.DatabaseFile == "" {
			return cfg, errors.New("history.database_file is required when history is enabled")
		}
		if cfg.History.Timezone == "" {
			cfg.History.Timezone = "Asia/Seoul"
		}
		if cfg.History.SummaryHour < 0 || cfg.History.SummaryHour > 23 ||
			cfg.History.SummaryMinute < 0 || cfg.History.SummaryMinute > 59 ||
			cfg.History.SummaryWeekday < 0 || cfg.History.SummaryWeekday > 6 {
			return cfg, errors.New("history summary weekday/hour/minute are outside valid ranges")
		}
		if _, err := time.LoadLocation(cfg.History.Timezone); err != nil {
			return cfg, fmt.Errorf("invalid history timezone: %w", err)
		}
	}
	return cfg, nil
}

func readSecret(path string) (string, error) {
	info, err := os.Stat(path)
	if err != nil {
		return "", fmt.Errorf("stat Telegram token file: %w", err)
	}
	if info.Mode().Perm()&0o077 != 0 {
		return "", fmt.Errorf("Telegram token file permissions must be 0600 or stricter: %s", info.Mode().Perm())
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("read Telegram token file: %w", err)
	}
	token := strings.TrimSpace(string(raw))
	if token == "" {
		return "", errors.New("Telegram token file is empty")
	}
	return token, nil
}

func run(ctx context.Context, cfg Config, state *State, token string, dryRun bool) error {
	if historyStore != nil && cfg.History.SummaryEnabled {
		go runSummaryScheduler(ctx, cfg, token, dryRun)
	}
	backoff := time.Second
	health := Health{Status: "starting", UpdatedAt: time.Now()}
	_ = writeJSONAtomic(cfg.HealthFile, health, 0o600)

	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		conn, _, err := websocket.DefaultDialer.DialContext(ctx, cfg.WebSocketURL, nil)
		if err != nil {
			health.Status = "disconnected"
			health.UpdatedAt = time.Now()
			health.ReconnectAttempts++
			health.Error = err.Error()
			_ = writeJSONAtomic(cfg.HealthFile, health, 0o600)
			delay := backoff + time.Duration(rand.IntN(1000))*time.Millisecond
			log.Printf("WebSocket connect failed; retrying in %s: %v", delay, err)
			if err := waitContext(ctx, delay); err != nil {
				return err
			}
			if backoff < time.Minute {
				backoff *= 2
			}
			continue
		}

		now := time.Now()
		health.Status = "connected"
		health.UpdatedAt = now
		health.ConnectedAt = now
		health.ReconnectAttempts = 0
		health.Error = ""
		_ = writeJSONAtomic(cfg.HealthFile, health, 0o600)
		backoff = time.Second
		log.Printf("connected to %s", cfg.WebSocketURL)

		err = readLoop(ctx, conn, cfg, state, token, dryRun, &health)
		_ = conn.Close()
		if ctx.Err() != nil {
			return ctx.Err()
		}
		health.Status = "disconnected"
		health.UpdatedAt = time.Now()
		health.Error = err.Error()
		_ = writeJSONAtomic(cfg.HealthFile, health, 0o600)
		log.Printf("WebSocket disconnected: %v", err)
	}
}

func readLoop(ctx context.Context, conn *websocket.Conn, cfg Config, state *State, token string, dryRun bool, health *Health) error {
	const pongWait = 45 * time.Second
	const pingEvery = 15 * time.Second
	_ = conn.SetReadDeadline(time.Now().Add(pongWait))
	conn.SetPongHandler(func(string) error {
		return conn.SetReadDeadline(time.Now().Add(pongWait))
	})

	done := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			_ = conn.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""), time.Now().Add(time.Second))
			_ = conn.Close()
		case <-done:
		}
	}()
	defer close(done)

	ticker := time.NewTicker(pingEvery)
	defer ticker.Stop()
	var usgsTicker *time.Ticker
	var usgsTick <-chan time.Time
	var usgsResults chan error
	usgsInFlight := false
	startUSGSPoll := func() {}
	if cfg.USGS.Enabled {
		usgsTicker = time.NewTicker(time.Duration(cfg.USGS.IntervalMinutes) * time.Minute)
		defer usgsTicker.Stop()
		usgsTick = usgsTicker.C
		usgsResults = make(chan error, 1)
		startUSGSPoll = func() {
			if usgsInFlight {
				return
			}
			usgsInFlight = true
			go func() {
				usgsResults <- pollUSGS(ctx, cfg, state, token, dryRun)
			}()
		}
		startUSGSPoll()
	}
	var gdacsTicker *time.Ticker
	var gdacsTick <-chan time.Time
	var gdacsResults chan error
	gdacsInFlight := false
	startGDACSPoll := func() {}
	if cfg.GDACS.Enabled {
		gdacsTicker = time.NewTicker(time.Duration(cfg.GDACS.IntervalMinutes) * time.Minute)
		defer gdacsTicker.Stop()
		gdacsTick = gdacsTicker.C
		gdacsResults = make(chan error, 1)
		startGDACSPoll = func() {
			if gdacsInFlight {
				return
			}
			gdacsInFlight = true
			go func() {
				gdacsResults <- pollGDACS(ctx, cfg, state, token, dryRun)
			}()
		}
		startGDACSPoll()
	}
	var tsunamiTimer *time.Timer
	var tsunamiTick <-chan time.Time
	var tsunamiResults chan tsunamiPollResult
	tsunamiInFlight := false
	startTsunamiPoll := func() {}
	scheduleTsunamiPoll := func(time.Duration) {}
	if cfg.Tsunami.Enabled {
		tsunamiTimer = time.NewTimer(0)
		defer tsunamiTimer.Stop()
		tsunamiTick = tsunamiTimer.C
		tsunamiResults = make(chan tsunamiPollResult, 1)
		scheduleTsunamiPoll = func(delay time.Duration) {
			if !tsunamiTimer.Stop() {
				select {
				case <-tsunamiTimer.C:
				default:
				}
			}
			tsunamiTimer.Reset(delay)
		}
		startTsunamiPoll = func() {
			if tsunamiInFlight {
				return
			}
			tsunamiInFlight = true
			go func() {
				active, err := pollTsunami(ctx, cfg, state, token, dryRun)
				tsunamiResults <- tsunamiPollResult{active: active, err: err}
			}()
		}
	}
	var swpcTicker *time.Ticker
	var swpcTick <-chan time.Time
	var swpcResults chan error
	swpcInFlight := false
	startSWPCPoll := func() {}
	if cfg.SWPC.Enabled {
		swpcTicker = time.NewTicker(time.Duration(cfg.SWPC.IntervalMinutes) * time.Minute)
		defer swpcTicker.Stop()
		swpcTick = swpcTicker.C
		swpcResults = make(chan error, 1)
		startSWPCPoll = func() {
			if swpcInFlight {
				return
			}
			swpcInFlight = true
			go func() {
				swpcResults <- pollSWPC(ctx, cfg, state, token, dryRun)
			}()
		}
		startSWPCPoll()
	}
	var kmaTicker *time.Ticker
	var kmaTick <-chan time.Time
	var kmaResults chan error
	kmaInFlight := false
	startKMAPoll := func() {}
	if cfg.KMA.Enabled {
		kmaTicker = time.NewTicker(time.Duration(cfg.KMA.IntervalMinutes) * time.Minute)
		defer kmaTicker.Stop()
		kmaTick = kmaTicker.C
		kmaResults = make(chan error, 1)
		startKMAPoll = func() {
			if kmaInFlight {
				return
			}
			kmaInFlight = true
			go func() {
				kmaResults <- pollKMA(ctx, cfg, state, token, dryRun)
			}()
		}
		startKMAPoll()
	}
	var typhoonTicker *time.Ticker
	var typhoonTick <-chan time.Time
	var typhoonResults chan error
	typhoonInFlight := false
	startTyphoonPoll := func() {}
	if cfg.Typhoon.Enabled {
		typhoonTicker = time.NewTicker(time.Duration(cfg.Typhoon.IntervalMinutes) * time.Minute)
		defer typhoonTicker.Stop()
		typhoonTick = typhoonTicker.C
		typhoonResults = make(chan error, 1)
		startTyphoonPoll = func() {
			if typhoonInFlight {
				return
			}
			typhoonInFlight = true
			go func() {
				typhoonResults <- pollTyphoons(ctx, cfg, state, token, dryRun)
			}()
		}
		startTyphoonPoll()
	}
	readErr := make(chan error, 1)
	go func() {
		for {
			_, raw, err := conn.ReadMessage()
			if err != nil {
				readErr <- err
				return
			}
			now := time.Now()
			health.LastMessageAt = now
			health.UpdatedAt = now
			alerted, err := processMessage(ctx, cfg, state, token, dryRun, raw)
			if err != nil {
				log.Printf("message processing failed: %v", err)
			} else if alerted {
				health.LastAlertAt = now
			}
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		}
	}()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case err := <-readErr:
			return err
		case <-ticker.C:
			if err := conn.WriteControl(websocket.PingMessage, nil, time.Now().Add(5*time.Second)); err != nil {
				return err
			}
		case <-usgsTick:
			startUSGSPoll()
		case err := <-usgsResults:
			usgsInFlight = false
			if err != nil {
				health.LastUSGSError = err.Error()
				log.Printf("USGS poll failed: %v", err)
			} else {
				health.LastUSGSPollAt = time.Now()
				health.LastUSGSError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		case <-gdacsTick:
			startGDACSPoll()
		case err := <-gdacsResults:
			gdacsInFlight = false
			if err != nil {
				health.LastGDACSError = err.Error()
				log.Printf("GDACS poll failed: %v", err)
			} else {
				health.LastGDACSPollAt = time.Now()
				health.LastGDACSError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		case <-tsunamiTick:
			startTsunamiPoll()
		case result := <-tsunamiResults:
			tsunamiInFlight = false
			interval := cfg.Tsunami.IdleIntervalMinutes
			if result.active {
				interval = cfg.Tsunami.ActiveIntervalMinutes
			}
			scheduleTsunamiPoll(time.Duration(interval) * time.Minute)
			if result.err != nil {
				health.LastTsunamiError = result.err.Error()
				log.Printf("tsunami poll failed: %v", result.err)
			} else {
				health.LastTsunamiPollAt = time.Now()
				health.LastTsunamiError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		case <-swpcTick:
			startSWPCPoll()
		case err := <-swpcResults:
			swpcInFlight = false
			if err != nil {
				health.LastSWPCError = err.Error()
				log.Printf("SWPC poll failed: %v", err)
			} else {
				health.LastSWPCPollAt = time.Now()
				health.LastSWPCError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		case <-kmaTick:
			startKMAPoll()
		case err := <-kmaResults:
			kmaInFlight = false
			if err != nil {
				health.LastKMAError = err.Error()
				log.Printf("KMA poll failed: %v", err)
			} else {
				health.LastKMAPollAt = time.Now()
				health.LastKMAError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		case <-typhoonTick:
			startTyphoonPoll()
		case err := <-typhoonResults:
			typhoonInFlight = false
			if err != nil {
				health.LastTyphoonError = err.Error()
				log.Printf("typhoon poll failed: %v", err)
			} else {
				health.LastTyphoonPollAt = time.Now()
				health.LastTyphoonError = ""
			}
			health.UpdatedAt = time.Now()
			_ = writeJSONAtomic(cfg.HealthFile, *health, 0o600)
		}
	}
}

type tsunamiPollResult struct {
	active bool
	err    error
}

func processMessage(ctx context.Context, cfg Config, state *State, token string, dryRun bool, raw []byte) (bool, error) {
	stateMu.Lock()
	defer stateMu.Unlock()
	event, err := normalize(raw, cfg.Filters)
	if err != nil {
		return false, err
	}
	if event.Tier == "" {
		return false, nil
	}
	alerted, changed, err := processEarthquakeLocked(ctx, cfg, state, token, dryRun, event)
	if err != nil {
		return false, err
	}
	if changed {
		err = writeJSONAtomic(cfg.StateFile, state, 0o600)
	}
	return alerted, err
}

func normalize(raw []byte, filters FilterConfig) (NormalizedEvent, error) {
	var envelope Envelope
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&envelope); err != nil {
		return NormalizedEvent{}, fmt.Errorf("parse EMSC message: %w", err)
	}
	p := envelope.Data.Properties
	mag, err := number(p.Magnitude, "magnitude")
	if err != nil {
		return NormalizedEvent{}, err
	}
	lat, err := number(p.Latitude, "latitude")
	if err != nil {
		return NormalizedEvent{}, err
	}
	lon, err := number(p.Longitude, "longitude")
	if err != nil {
		return NormalizedEvent{}, err
	}
	depth, _ := p.Depth.Float64()
	occurred, err := parseEventTime(p.Time)
	if err != nil {
		return NormalizedEvent{}, err
	}
	if p.SourceID == "" {
		return NormalizedEvent{}, errors.New("missing EMSC unid")
	}
	distance := haversineKM(filters.KoreaCenterLat, filters.KoreaCenterLon, lat, lon)
	tier := classify(distance, mag, p.Region, filters)
	fingerprint := fmt.Sprintf("%s|%.2f|%.4f|%.4f|%.1f|%s", envelope.Action, mag, lat, lon, depth, p.LastUpdate)
	return NormalizedEvent{
		Source: "emsc", Action: envelope.Action, SourceID: p.SourceID, Time: occurred,
		Magnitude: mag, Latitude: lat, Longitude: lon, Depth: depth,
		Region: strings.TrimSpace(p.Region), DistanceKM: distance, Tier: tier,
		Urgent: mag >= filters.UrgentMinMagnitude, Fingerprint: fingerprint,
	}, nil
}

func number(n json.Number, name string) (float64, error) {
	if n == "" {
		return 0, fmt.Errorf("missing %s", name)
	}
	value, err := n.Float64()
	if err != nil {
		return 0, fmt.Errorf("invalid %s: %w", name, err)
	}
	return value, nil
}

func parseEventTime(value string) (time.Time, error) {
	for _, layout := range []string{time.RFC3339Nano, "2006-01-02T15:04:05.999999Z", "2006-01-02T15:04:05Z"} {
		if parsed, err := time.Parse(layout, value); err == nil {
			return parsed, nil
		}
	}
	return time.Time{}, fmt.Errorf("unsupported event time %q", value)
}

func classify(distance, magnitude float64, region string, filters FilterConfig) string {
	if isForeignEastAsia(region) {
		switch {
		case distance <= filters.RegionalRadiusKM && magnitude >= filters.RegionalMinMagnitude:
			return "동아시아"
		case magnitude >= filters.GlobalMinMagnitude:
			return "세계"
		default:
			return ""
		}
	}
	switch {
	case distance <= filters.KoreaRadiusKM && magnitude >= filters.KoreaMinMagnitude:
		return "한국 주변"
	case distance <= filters.RegionalRadiusKM && magnitude >= filters.RegionalMinMagnitude:
		return "동아시아"
	case magnitude >= filters.GlobalMinMagnitude:
		return "세계"
	default:
		return ""
	}
}

func isForeignEastAsia(region string) bool {
	upper := strings.ToUpper(region)
	for _, marker := range []string{
		"JAPAN", "KYUSHU", "HONSHU", "SHIKOKU", "HOKKAIDO", "RYUKYU", "NANKAI",
		"CHINA", "RUSSIA", "TAIWAN", "PHILIPPINE",
	} {
		if strings.Contains(upper, marker) {
			return true
		}
	}
	return false
}

func formatAlert(event NormalizedEvent, previous EventSnapshot, hasPrevious bool) string {
	prefix := "🌏 지진"
	if event.Urgent {
		prefix = "🚨 긴급 지진"
	}
	action := map[string]string{
		"create": "🆕 신규", "update": "🔄 수정", "escalated": "⬆️ 상향", "delete": "❌ 취소",
	}[strings.ToLower(event.Action)]
	if action == "" {
		action = "ℹ️ " + event.Action
	}
	region := html.EscapeString(event.Region)
	if region == "" {
		region = "지역 정보 없음"
	}
	kst := event.Time.In(time.FixedZone("KST", 9*60*60))
	mapURL := "https://www.openstreetmap.org/?mlat=" + strconv.FormatFloat(event.Latitude, 'f', 4, 64) +
		"&mlon=" + strconv.FormatFloat(event.Longitude, 'f', 4, 64) + "#map=6/" +
		strconv.FormatFloat(event.Latitude, 'f', 4, 64) + "/" + strconv.FormatFloat(event.Longitude, 'f', 4, 64)
	message := fmt.Sprintf(
		"<b>%s · %s · 규모 %.1f</b>\n\n%s\n\n<b>발생</b>  %s\n<b>깊이</b>  %.1fkm\n<b>한국과 거리</b>  약 %.0fkm\n<b>분류</b>  %s",
		html.EscapeString(prefix), html.EscapeString(action), event.Magnitude, region,
		kst.Format("2006-01-02 15:04:05 KST"), event.Depth, event.DistanceKM,
		html.EscapeString(event.Tier),
	)
	if (strings.EqualFold(event.Action, "update") || strings.EqualFold(event.Action, "escalated")) && hasPrevious {
		if changes := formatChanges(previous, event); changes != "" {
			message += "\n\n<b>변경 사항</b>\n" + changes
		}
	}
	message += fmt.Sprintf("\n\n<a href=\"%s\">지도에서 보기</a>", html.EscapeString(mapURL))
	if event.DetailURL != "" {
		message += fmt.Sprintf(" · <a href=\"%s\">%s에서 보기</a>",
			html.EscapeString(event.DetailURL), html.EscapeString(earthquakeSourceLabel(event.Source)))
	}
	return message + fmt.Sprintf("\n<code>%s %s</code>",
		html.EscapeString(earthquakeSourceLabel(event.Source)), html.EscapeString(event.SourceID))
}

func formatChanges(previous EventSnapshot, current NormalizedEvent) string {
	var changes []string
	if math.Abs(previous.Magnitude-current.Magnitude) >= 0.05 {
		changes = append(changes, fmt.Sprintf("• 규모 %.1f → %.1f", previous.Magnitude, current.Magnitude))
	}
	if math.Abs(previous.Depth-current.Depth) >= 0.5 {
		changes = append(changes, fmt.Sprintf("• 깊이 %.1fkm → %.1fkm", previous.Depth, current.Depth))
	}
	moved := haversineKM(previous.Latitude, previous.Longitude, current.Latitude, current.Longitude)
	if moved >= 1 {
		changes = append(changes, fmt.Sprintf("• 진앙 위치 약 %.0fkm 조정", moved))
	}
	if previous.Region != "" && current.Region != "" && previous.Region != current.Region {
		changes = append(changes, fmt.Sprintf("• 지역 %s → %s", html.EscapeString(previous.Region), html.EscapeString(current.Region)))
	}
	return strings.Join(changes, "\n")
}

func sendTelegram(ctx context.Context, token, chatID, text string) error {
	body, _ := json.Marshal(map[string]any{
		"chat_id":                  chatID,
		"text":                     text,
		"parse_mode":               "HTML",
		"disable_web_page_preview": true,
	})
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, "https://api.telegram.org/bot"+token+"/sendMessage", bytes.NewReader(body))
		if err != nil {
			return err
		}
		req.Header.Set("Content-Type", "application/json")
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Do(req)
		if err == nil {
			responseBody, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
			_ = resp.Body.Close()
			if resp.StatusCode >= 200 && resp.StatusCode < 300 {
				if historyStore != nil {
					if err := historyStore.Record(alertMetaFromContext(ctx), text, time.Now()); err != nil {
						log.Printf("history record failed: %v", err)
					}
				}
				return nil
			}
			err = fmt.Errorf("Telegram status %d: %s", resp.StatusCode, strings.TrimSpace(string(responseBody)))
		}
		lastErr = err
		if err := waitContext(ctx, time.Duration(attempt+1)*time.Second); err != nil {
			return err
		}
	}
	return fmt.Errorf("send Telegram alert: %w", lastErr)
}

func loadState(path string) (*State, error) {
	state := &State{
		Seen: map[string]string{}, Snapshots: map[string]EventSnapshot{},
		USGSSeen: map[string]string{}, USGSSnapshots: map[string]EventSnapshot{},
		GDACS: map[string]GDACSSnapshot{}, SWPCSeen: map[string]bool{}, KMASeen: map[string]bool{},
		Typhoons: map[string]TyphoonSnapshot{},
	}
	raw, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return state, nil
	}
	if err != nil {
		return nil, fmt.Errorf("read state: %w", err)
	}
	if err := json.Unmarshal(raw, state); err != nil {
		return nil, fmt.Errorf("parse state: %w", err)
	}
	if state.Seen == nil {
		state.Seen = map[string]string{}
	}
	if state.Snapshots == nil {
		state.Snapshots = map[string]EventSnapshot{}
	}
	if state.USGSSeen == nil {
		state.USGSSeen = map[string]string{}
	}
	if state.USGSSnapshots == nil {
		state.USGSSnapshots = map[string]EventSnapshot{}
	}
	if state.GDACS == nil {
		state.GDACS = map[string]GDACSSnapshot{}
	}
	if state.SWPCSeen == nil {
		state.SWPCSeen = map[string]bool{}
	}
	if state.KMASeen == nil {
		state.KMASeen = map[string]bool{}
	}
	if state.Typhoons == nil {
		state.Typhoons = map[string]TyphoonSnapshot{}
	}
	for id, fingerprint := range state.Seen {
		if _, exists := state.Snapshots[id]; exists {
			continue
		}
		if snapshot, ok := snapshotFromFingerprint(fingerprint); ok {
			state.Snapshots[id] = snapshot
		}
	}
	if len(state.Earthquakes) == 0 {
		for id, snapshot := range state.Snapshots {
			if snapshot.OccurredAt == "" {
				continue
			}
			state.Earthquakes = append(state.Earthquakes, EarthquakeRecord{
				Sources: map[string]string{"emsc": id}, Snapshot: snapshot, Notified: true,
			})
		}
	}
	for i := range state.Earthquakes {
		if state.Earthquakes[i].Sources == nil {
			state.Earthquakes[i].Sources = map[string]string{}
		}
	}
	return state, nil
}

func snapshotFromFingerprint(fingerprint string) (EventSnapshot, bool) {
	parts := strings.Split(fingerprint, "|")
	if len(parts) != 6 {
		return EventSnapshot{}, false
	}
	values := make([]float64, 4)
	for i := range values {
		value, err := strconv.ParseFloat(parts[i+1], 64)
		if err != nil {
			return EventSnapshot{}, false
		}
		values[i] = value
	}
	return EventSnapshot{
		Magnitude: values[0], Latitude: values[1], Longitude: values[2], Depth: values[3],
	}, true
}

func remember(state *State, event NormalizedEvent) {
	if _, exists := state.Seen[event.SourceID]; !exists {
		state.Order = append(state.Order, event.SourceID)
	}
	state.Seen[event.SourceID] = event.Fingerprint
	state.Snapshots[event.SourceID] = snapshotFromEvent(event)
	for len(state.Order) > maxSeenEvents {
		oldest := state.Order[0]
		state.Order = state.Order[1:]
		delete(state.Seen, oldest)
		delete(state.Snapshots, oldest)
	}
}

func writeJSONAtomic(path string, value any, mode os.FileMode) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	temp, err := os.CreateTemp(filepath.Dir(path), ".tmp-*")
	if err != nil {
		return err
	}
	tempName := temp.Name()
	defer os.Remove(tempName)
	if err := temp.Chmod(mode); err != nil {
		_ = temp.Close()
		return err
	}
	if _, err := temp.Write(append(raw, '\n')); err != nil {
		_ = temp.Close()
		return err
	}
	if err := temp.Sync(); err != nil {
		_ = temp.Close()
		return err
	}
	if err := temp.Close(); err != nil {
		return err
	}
	return os.Rename(tempName, path)
}

func haversineKM(lat1, lon1, lat2, lon2 float64) float64 {
	const earthRadiusKM = 6371.0088
	toRad := math.Pi / 180
	dLat := (lat2 - lat1) * toRad
	dLon := (lon2 - lon1) * toRad
	a := math.Sin(dLat/2)*math.Sin(dLat/2) +
		math.Cos(lat1*toRad)*math.Cos(lat2*toRad)*math.Sin(dLon/2)*math.Sin(dLon/2)
	return 2 * earthRadiusKM * math.Asin(math.Sqrt(a))
}

func waitContext(ctx context.Context, duration time.Duration) error {
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}
