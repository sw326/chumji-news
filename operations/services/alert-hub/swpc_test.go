package main

import (
	"strings"
	"testing"
)

func TestNormalizeSWPCStrongAlert(t *testing.T) {
	product := swpcProduct{
		ProductID: "K07A", IssueDatetime: "2026-07-04 05:10:10.740",
		Message: "Space Weather Message Code: ALTK07\r\nSerial Number: 218\r\n" +
			"ALERT: Geomagnetic K-index of 7\r\nThreshold Reached: 2026 Jul 04 0509 UTC\r\n" +
			"Noaa Scale: G3 - Strong",
	}
	event, ok := normalizeSWPC(product)
	if !ok || event.Category != "G" || event.Level != 3 || event.Action != "observed" ||
		event.Detail["Threshold Reached"] != "2026 Jul 04 0509 UTC" {
		t.Fatalf("unexpected event: %+v ok=%v", event, ok)
	}
}

func TestNormalizeSWPCExcludesModerate(t *testing.T) {
	product := swpcProduct{
		ProductID: "XM5A", IssueDatetime: "2026-07-05 18:00:26.950",
		Message: "Space Weather Message Code: ALTXMF\nSerial Number: 539\n" +
			"ALERT: X-Ray Flux exceeded M5\nNOAA Scale: R2 - Moderate",
	}
	if _, ok := normalizeSWPC(product); ok {
		t.Fatal("R2 message should be excluded")
	}
}

func TestNormalizeSWPCActions(t *testing.T) {
	tests := []struct {
		line string
		want string
	}{
		{"WARNING: Geomagnetic K-index expected", "forecast"},
		{"ALERT: Geomagnetic K-index reached", "observed"},
		{"SUMMARY: X-ray Event exceeded X1", "summary"},
		{"CANCEL WARNING: Geomagnetic K-index expected", "resolved"},
	}
	for i, test := range tests {
		product := swpcProduct{
			ProductID: "test", IssueDatetime: "2026-07-04 05:10:10.740",
			Message: "Space Weather Message Code: TEST\nSerial Number: " +
				string(rune('1'+i)) + "\n" + test.line + "\nNOAA Scale: G3 - Strong",
		}
		event, ok := normalizeSWPC(product)
		if !ok || event.Action != test.want {
			t.Fatalf("%q action=%q ok=%v", test.line, event.Action, ok)
		}
	}
}

func TestNormalizeSWPCUnclassifiedMessageIsRoutineUpdate(t *testing.T) {
	product := swpcProduct{
		ProductID: "test", IssueDatetime: "2026-07-04 05:10:10.740",
		Message: "Space Weather Message Code: TEST\nSerial Number: 9\n" +
			"Corrected timing details\nNOAA Scale: G3 - Strong",
	}
	event, ok := normalizeSWPC(product)
	if !ok || event.Action != "updated" {
		t.Fatalf("routine update action=%q ok=%v", event.Action, ok)
	}
}

func TestNormalizeSWPCCancelWithInlineScale(t *testing.T) {
	product := swpcProduct{
		ProductID: "K07W", IssueDatetime: "2026-07-05 00:27:14.067",
		Message: "Space Weather Message Code: WARK07\nSerial Number: 152\n" +
			"CANCEL WARNING: Geomagnetic K-index of 7 or greater expected\n" +
			"Wrong date in original warning. NOAA Scale: G3 - Greater",
	}
	event, ok := normalizeSWPC(product)
	if !ok || event.Action != "resolved" || event.Level != 3 {
		t.Fatalf("unexpected event: %+v ok=%v", event, ok)
	}
}

func TestFormatSWPCAlert(t *testing.T) {
	event := SWPCEvent{
		Code: "SUMX01", Serial: "220", IssueDatetime: "2026-07-04 21:16:21.380",
		Category: "R", Level: 3, LevelText: "Strong", Action: "summary",
		Detail: map[string]string{
			"Begin Time": "2026 Jul 04 2029 UTC", "Xray Class": "X1.3",
		},
	}
	message := formatSWPCAlert(event)
	for _, expected := range []string{
		"🟠 우주기상 · R3 Strong · ✅ 종료 요약", "전파장애",
		"2026-07-05 06:16 KST", "X1.3", "NOAA SWPC에서 보기", "SUMX01 · serial 220",
	} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}

func TestRememberSWPCBounds(t *testing.T) {
	state := &State{SWPCSeen: map[string]bool{}}
	for i := 0; i < maxSWPCSeen+10; i++ {
		rememberSWPC(state, string(rune(i+1)))
	}
	if len(state.SWPCSeen) != maxSWPCSeen || len(state.SWPCOrder) != maxSWPCSeen {
		t.Fatalf("state not bounded: seen=%d order=%d", len(state.SWPCSeen), len(state.SWPCOrder))
	}
}
