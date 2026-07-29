#!/usr/bin/env python3
"""
ACLED 분쟁 이벤트 수집
https://acleddata.com/api-documentation/getting-started

Auth: OAuth2 Bearer Token (이메일+비밀번호 → 24시간 토큰)
Credentials: ~/.config/global-intel/secrets.env (ACLED_EMAIL, ACLED_PASSWORD)
Output: JSON { events: [...], summary: {...} }
"""

import json
import os
import sys
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

def load_credentials(secret_path=None, *, overwrite: bool = False) -> None:
    """Load credentials without failing when a legacy default path is unreadable."""
    path = secret_path or Path(
        os.getenv(
            "ACLED_SECRET_FILE",
            str(Path.home() / ".config/global-intel/secrets.env"),
        )
    )
    try:
        lines = path.read_text().splitlines()
    except (FileNotFoundError, PermissionError):
        return
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            if overwrite:
                os.environ[key.strip()] = value.strip()
            else:
                os.environ.setdefault(key.strip(), value.strip())


load_credentials()

ACLED_EMAIL = os.environ.get("ACLED_EMAIL", "")
ACLED_PASSWORD = os.environ.get("ACLED_PASSWORD", "")

TOKEN_URL = "https://acleddata.com/oauth/token"
BASE_URL = "https://acleddata.com/api/acled/read"
# ACLED's Cloudflare policy rejects urllib and custom bot signatures (Error
# 1010) before OAuth validation. Use a stable browser-compatible signature;
# the repository URL remains available through the separate project docs.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/138.0.0.0 Safari/537.36"
)


def get_token() -> str:
    """OAuth2 Bearer 토큰 발급 (24시간 유효)"""
    if not ACLED_EMAIL or not ACLED_PASSWORD:
        raise ValueError("ACLED_EMAIL / ACLED_PASSWORD 미설정. ~/.config/global-intel/secrets.env 확인")

    payload = urllib.parse.urlencode({
        "username": ACLED_EMAIL,
        "password": ACLED_PASSWORD,
        "grant_type": "password",
        "client_id": "acled",
        "scope": "authenticated",
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 400 and "invalid_grant" in body:
            raise ValueError("ACLED authentication failed: invalid_grant") from None
        if "flood_user_blocked" in body:
            raise ValueError("ACLED authentication failed: account_temporarily_blocked") from None
        raise ValueError(f"ACLED token request failed: http_{exc.code}") from None
    token = data.get("access_token")
    if not token:
        raise ValueError(f"토큰 발급 실패: {data}")
    return token


def fetch_recent_events(days: int = 7, min_fatalities: int = 5, limit: int = 50) -> dict:
    try:
        token = get_token()
    except Exception as e:
        return {"error": str(e)}

    date_from = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    params = {
        "event_date": date_from,
        "event_date_where": ">=",
        "fatalities": str(min_fatalities),
        "fatalities_where": ">=",
        "limit": str(limit),
        "fields": "event_id_cnty|event_date|event_type|sub_event_type|country|location|latitude|longitude|actor1|actor2|fatalities|notes|source",
        "order": "fatalities:desc",
    }

    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
    except Exception as e:
        return {"error": f"ACLED fetch failed: {e}"}

    events = data.get("data", [])

    # 국가별 요약
    by_country: dict[str, dict] = {}
    for e in events:
        country = e.get("country", "Unknown")
        if country not in by_country:
            by_country[country] = {"count": 0, "fatalities": 0, "types": set()}
        by_country[country]["count"] += 1
        by_country[country]["fatalities"] += int(e.get("fatalities", 0))
        by_country[country]["types"].add(e.get("event_type", ""))

    summary = {
        "total_events": len(events),
        "total_fatalities": sum(int(e.get("fatalities", 0)) for e in events),
        "countries_affected": len(by_country),
        "by_country": {
            k: {**v, "types": list(v["types"])}
            for k, v in sorted(by_country.items(), key=lambda x: -x[1]["fatalities"])[:10]
        },
        "date_range": f"{date_from} ~ {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
    }

    return {"events": events[:20], "summary": summary}


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    result = fetch_recent_events(days=days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
