package main

import (
	"strings"
	"testing"
)

const kmaFixture = `
<select id="select-list" name="reportId">
  <option value="met:202607281600:146" selected="selected">[특보] 제07-146호 : 2026.07.28.16:00/ 폭염경보 변경·열대야주의보 발표</option>
  <option value="met:202607281000:145">[특보] 제07-145호 : 2026.07.28.10:00/ 폭염주의보 발표</option>
  <option value="met:202607280800:144">[특보] 제07-144호 : 2026.07.28.08:00/ 풍랑주의보 발표</option>
</select>
<div class="cmp-view-content">
  <strong>□ 발효시각</strong>
  <p>(1) 폭염경보 변경 : 2026년 07월 29일 11시 00분</p>
  <strong>□ 해당구역</strong>
  <p>(1) 폭염경보 변경 : 경기도(고양, 남양주), 서울(서울동남권, 서울동북권)<br />
  (2) 폭염주의보 발표 : 인천광역시</p>
</div>`

func TestParseKMAListFiltersWantedWarnings(t *testing.T) {
	notices := parseKMAList(kmaFixture, "https://www.weather.go.kr/w/special-report/list.do", "109", "2026-07-28")
	if len(notices) != 2 {
		t.Fatalf("notices=%d want 2: %+v", len(notices), notices)
	}
	if notices[0].ID != "met:202607281600:146" ||
		!strings.Contains(notices[0].DetailURL, "reportId=met%3A202607281600%3A146") {
		t.Fatalf("unexpected notice: %+v", notices[0])
	}
}

func TestExtractKMASections(t *testing.T) {
	areas := extractKMASection(kmaFixture, kmaAreaPattern)
	effective := extractKMASection(kmaFixture, kmaEffectivePattern)
	if !strings.Contains(areas, "경기도(고양, 남양주)") || !strings.Contains(areas, "인천광역시") {
		t.Fatalf("unexpected areas: %q", areas)
	}
	if effective != "(1) 폭염경보 변경 : 2026년 07월 29일 11시 00분" {
		t.Fatalf("unexpected effective time: %q", effective)
	}
}

func TestWantedKMAWarning(t *testing.T) {
	for _, title := range []string{"호우경보 발표", "대설주의보 해제", "강풍주의보", "폭염경보", "한파주의보", "태풍경보"} {
		if !wantedKMAWarning(title) {
			t.Fatalf("should include %q", title)
		}
	}
	for _, title := range []string{"풍랑주의보", "건조주의보", "열대야주의보"} {
		if wantedKMAWarning(title) {
			t.Fatalf("should exclude %q", title)
		}
	}
}

func TestFormatKMAAlert(t *testing.T) {
	notice := KMANotice{
		ID:    "met:202607281600:146",
		Title: "[특보] 제07-146호 : 2026.07.28.16:00/ 폭염경보 변경",
		Areas: "경기도(고양, 남양주), 서울(서울동남권)", EffectiveTime: "2026년 07월 29일 11시 00분",
		DetailURL: "https://www.weather.go.kr/w/special-report/list.do?reportId=example",
	}
	message := formatKMAAlert(notice)
	for _, expected := range []string{
		"🔴 수도권 기상특보 · 폭염 · 🔄 변경", "경기도(고양, 남양주)",
		"기상청 통보문 보기", "KMA met:202607281600:146",
	} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}

func TestRememberKMABounds(t *testing.T) {
	state := &State{KMASeen: map[string]bool{}}
	for i := 0; i < maxKMASeen+10; i++ {
		rememberKMA(state, string(rune(i+1)))
	}
	if len(state.KMASeen) != maxKMASeen || len(state.KMAOrder) != maxKMASeen {
		t.Fatalf("state not bounded: seen=%d order=%d", len(state.KMASeen), len(state.KMAOrder))
	}
}
