#!/usr/bin/env python3
"""Export a redacted public-status snapshot from local ops runtime data."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sqlite3
import urllib.error
import urllib.request

SCHEMA_VERSION = "ops-public-status/v1"
DEFAULT_MARKET_BOARD = pathlib.Path(
    "/Users/ops/Library/Application Support/chumji-ops/"
    "trade-market-briefing/output/cathode-current-market.json"
)


def plain_text(message: str) -> str:
    text = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", message, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"(?m)^\s*(EMSC|GDACS|KMA|JMA|SWPC|PTWC)\s+\S+\s*$", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def category_for(source: str, message: str) -> str:
    lowered = message.casefold()
    if source == "emsc" or "지진 ·" in message:
        return "earthquake"
    if source == "swpc" or "우주" in message:
        return "space-weather"
    if source in {"tsunami", "ptwc"} or "지진해일" in message:
        return "tsunami"
    if source in {"kma", "typhoon", "gdacs"}:
        return "weather"
    return "system"


def severity_for(source_value: str, message: str) -> str:
    value = f"{source_value} {message}".casefold()
    if any(term in value for term in ("red", "긴급", "매우 강한", "경보")):
        return "critical"
    if any(term in value for term in ("orange", "강한 태풍", "주의보")):
        return "high"
    if any(term in value for term in ("yellow", "규모 4.", "규모 5.")):
        return "medium"
    return "low"


def status_for(action: str) -> str:
    if action in {"resolved", "cancelled", "ended"}:
        return "resolved"
    if action in {"updated", "update", "strengthened", "weakened"}:
        return "monitoring"
    return "open"


def _line_after(label: str, text: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(label)}\s+(.+)$", text)
    return match.group(1).strip() if match else None


def title_for(source: str, text: str) -> str:
    lines = [line.strip(" •") for line in text.splitlines() if line.strip()]
    if not lines:
        return f"{source.upper()} 알림"
    if len(lines) > 1 and source in {"emsc", "gdacs"}:
        return lines[1][:120]
    return lines[0][:120]


def region_for(source: str, text: str, source_value: str) -> str:
    return (
        _line_after("영향 지역", text)
        or _line_after("해당구역", text)
        or (source_value if source == "emsc" else None)
        or ("전 세계" if source in {"gdacs", "swpc"} else "미분류")
    )[:160]


def alerts_from_db(database: pathlib.Path) -> list[dict]:
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT id,source,event_id,action,severity,occurred_at,received_at,message_html
           FROM alert_events ORDER BY received_at ASC"""
    ).fetchall()
    connection.close()

    grouped: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault((row["source"], row["event_id"] or str(row["id"])), []).append(row)

    alerts = []
    for (source, event_id), events in grouped.items():
        latest = events[-1]
        latest_text = plain_text(latest["message_html"])
        observed = events[0]["occurred_at"] or events[0]["received_at"]
        updated = latest["received_at"]
        timeline = []
        for event in events:
            event_text = plain_text(event["message_html"])
            timeline.append(
                {
                    "at": event["received_at"],
                    "actor": f"alert-hub.{source}",
                    "title": event["action"],
                    "note": title_for(source, event_text),
                    "status": status_for(event["action"]),
                }
            )
        alerts.append(
            {
                "id": f"alert-{source}-{event_id}",
                "category": category_for(source, latest_text),
                "severity": severity_for(latest["severity"], latest_text),
                "status": status_for(latest["action"]),
                "title": title_for(source, latest_text),
                "source": source.upper(),
                "region": region_for(source, latest_text, latest["severity"]),
                "observedAt": observed,
                "updatedAt": updated,
                "publicSummary": re.sub(r"\s+", " ", latest_text)[:360],
                "privacyClass": "public-status",
                "timeline": timeline,
            }
        )
    return sorted(alerts, key=lambda item: item["updatedAt"], reverse=True)


def operations_from_health(health_path: pathlib.Path) -> dict:
    health = json.loads(health_path.read_text())
    updated_at = health.get("updated_at") or dt.datetime.now(dt.timezone.utc).isoformat()
    connected = health.get("status") == "connected"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "privacyClass": "public-status-only",
        "runtimes": [
            {
                "id": "alert-hub",
                "kind": "service",
                "name": "실시간 재난 알림 허브",
                "owner": "ops",
                "declaredIn": "com.chumji.earthquake-alert",
                "schedule": "상시 실행",
                "lastRunAt": health.get("connected_at"),
                "nextExpectedAt": None,
                "freshnessMinutes": 0,
                "status": "fresh" if connected else "failing",
                "failureState": "none" if connected else "failed",
                "publicSummary": "공개 재난 소스를 감시하고 Telegram 알림 이력을 저장합니다.",
                "controlPolicy": "read-only-preview",
                "checks": [
                    {
                        "name": "소스 연결",
                        "status": "pass" if connected else "fail",
                        "observedAt": updated_at,
                        "summary": "연결 정상" if connected else "연결 상태 확인 필요",
                    },
                    {
                        "name": "재연결 횟수",
                        "status": "pass" if health.get("reconnect_attempts", 0) == 0 else "warn",
                        "observedAt": updated_at,
                        "summary": f"{health.get('reconnect_attempts', 0)}회",
                    },
                ],
            }
        ],
    }


def load_env_file(path: pathlib.Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def upload_snapshots(payload: dict, env_path: pathlib.Path) -> None:
    environment = load_env_file(env_path)
    base_url = environment.get("NEXT_PUBLIC_SUPABASE_URL", "").rstrip("/")
    service_key = environment.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise ValueError("Supabase URL or service-role SecretRef is missing")
    rows = [
        {
            "kind": "alerts",
            "schema_version": payload["schemaVersion"],
            "payload": payload["alerts"],
            "generated_at": payload["generatedAt"],
            "updated_at": payload["generatedAt"],
        },
        {
            "kind": "operations",
            "schema_version": payload["schemaVersion"],
            "payload": payload["operations"],
            "generated_at": payload["generatedAt"],
            "updated_at": payload["generatedAt"],
        },
    ]
    if payload.get("tradeMarket"):
        rows.append(
            {
                "kind": "trade-market",
                "schema_version": "trade-market-board/v1",
                "payload": payload["tradeMarket"],
                "generated_at": payload["generatedAt"],
                "updated_at": payload["generatedAt"],
            }
        )
    request = urllib.request.Request(
        f"{base_url}/rest/v1/ops_public_snapshots?on_conflict=kind",
        data=json.dumps(rows, ensure_ascii=False).encode(),
        method="POST",
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in {200, 201, 204}:
                raise RuntimeError(f"Supabase upload failed: http_{response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Supabase upload failed: http_{exc.code}") from None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history-db", type=pathlib.Path, required=True)
    parser.add_argument("--health-file", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--market-board", type=pathlib.Path, default=DEFAULT_MARKET_BOARD)
    parser.add_argument("--supabase-env", type=pathlib.Path)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "alerts": alerts_from_db(args.history_db),
        "operations": operations_from_health(args.health_file),
    }
    if args.market_board.exists():
        payload["tradeMarket"] = json.loads(args.market_board.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if args.upload:
        if not args.supabase_env:
            parser.error("--upload requires --supabase-env")
        upload_snapshots(payload, args.supabase_env)
    print(
        json.dumps(
            {
                "alerts": len(payload["alerts"]),
                "schemaVersion": SCHEMA_VERSION,
                "uploaded": args.upload,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
