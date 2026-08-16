package main

import (
	"encoding/xml"
	"strings"
	"testing"
)

func TestNormalizeTsunamiFinalMessage(t *testing.T) {
	raw := []byte(`<?xml version="1.0"?>
<tsunamiEvent xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
  <TWCBulletin>
    <TWCEventID>26209004</TWCEventID>
    <bulletinNumber>2</bulletinNumber>
    <bulletinIssueTime>2026-07-28T08:22:28Z</bulletinIssueTime>
    <preliminarySeismicInformation>
      <magnitude>7.1</magnitude>
      <originTime>2026-07-28T07:28:00Z</originTime>
      <depth>10</depth>
      <geo:lat>32.6</geo:lat><geo:long>130.7</geo:long>
      <locationName>KYUSHU  JAPAN</locationName>
    </preliminarySeismicInformation>
    <tsunamiBulletinBody>...PTWC FINAL TSUNAMI THREAT MESSAGE...
THERE IS NO LONGER A TSUNAMI THREAT FROM THIS EARTHQUAKE.</tsunamiBulletinBody>
    <testMessage>false</testMessage>
  </TWCBulletin>
</tsunamiEvent>`)
	var feed tsunamiTEX
	if err := xml.Unmarshal(raw, &feed); err != nil {
		t.Fatal(err)
	}
	got, ok := normalizeTsunami(feed.Bulletin, "https://www.tsunami.gov/events/xml/PHEBTEX.xml")
	if !ok || !got.Final || got.Level != "none" || got.EventID != "26209004" ||
		got.Location != "KYUSHU JAPAN" || got.Latitude != 32.6 {
		t.Fatalf("unexpected snapshot: %+v ok=%v", got, ok)
	}
}

func TestTsunamiTransitions(t *testing.T) {
	info := TsunamiSnapshot{EventID: "event-1", BulletinNumber: 1, Level: "information"}
	watch := TsunamiSnapshot{EventID: "event-2", BulletinNumber: 1, Level: "watch"}
	if got := tsunamiTransition(info, watch); got != "new" {
		t.Fatalf("new transition=%q", got)
	}
	warning := watch
	warning.BulletinNumber = 2
	warning.Level = "warning"
	if got := tsunamiTransition(watch, warning); got != "escalated" {
		t.Fatalf("escalated transition=%q", got)
	}
	update := warning
	update.BulletinNumber = 3
	if got := tsunamiTransition(warning, update); got != "" {
		t.Fatalf("routine update transition=%q", got)
	}
	final := update
	final.BulletinNumber = 4
	final.Level = "none"
	final.Final = true
	if got := tsunamiTransition(update, final); got != "resolved" {
		t.Fatalf("resolved transition=%q", got)
	}
	if got := tsunamiTransition(final, final); got != "" {
		t.Fatalf("duplicate transition=%q", got)
	}
}

func TestTsunamiIgnoresNewInformationOnlyEvent(t *testing.T) {
	previous := TsunamiSnapshot{EventID: "old", BulletinNumber: 2, Level: "none", Final: true}
	current := TsunamiSnapshot{EventID: "new", BulletinNumber: 1, Level: "information"}
	if got := tsunamiTransition(previous, current); got != "" {
		t.Fatalf("information-only transition=%q", got)
	}
}

func TestFormatTsunamiAlert(t *testing.T) {
	current := TsunamiSnapshot{
		EventID: "26209004", BulletinNumber: 1, Level: "warning",
		IssueTime: "2026-07-28T07:37:20Z", OriginTime: "2026-07-28T07:28:00Z",
		Location: "KYUSHU JAPAN", Magnitude: 7.1, Depth: 10,
		BulletinURL: "https://www.tsunami.gov/events/xml/PHEBTEX.xml",
	}
	message := formatTsunamiAlert("new", TsunamiSnapshot{}, current)
	for _, expected := range []string{
		"🚨 쓰나미 경보 · 🆕 발령", "KYUSHU JAPAN", "2026-07-28 16:28 KST",
		"PTWC 공식 발표 보기", "PTWC 26209004 · bulletin 1",
	} {
		if !strings.Contains(message, expected) {
			t.Fatalf("message missing %q:\n%s", expected, message)
		}
	}
}
