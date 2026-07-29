#!/usr/bin/env python3
"""
OpenSky Network 분쟁 지역 항공 활동 수집
https://openskynetwork.github.io/opensky-api/rest.html

인증 불필요 (익명: 400req/day, 로그인: 4000req/day).
Output: JSON { zones: {...}, summary: {...} }
"""

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone


BASE_URL = "https://opensky-network.org/api/states/all"

# 분쟁 지역 bounding box (lamin, lomin, lamax, lomax)
ZONES = [
    {"name": "Ukraine/Russia", "bbox": (44.0, 22.0, 52.0, 40.0)},
    {"name": "Middle East", "bbox": (18.0, 28.0, 38.0, 60.0)},
    {"name": "Taiwan Strait", "bbox": (20.0, 118.0, 28.0, 126.0)},
    {"name": "Korean Peninsula", "bbox": (33.0, 124.0, 43.0, 132.0)},
]

def fetch_zone(zone: dict) -> dict:
    lamin, lomin, lamax, lomax = zone["bbox"]
    params = {
        "lamin": lamin, "lomin": lomin,
        "lamax": lamax, "lomax": lomax,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "global-intel/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        states = data.get("states") or []

        aircraft = []
        for s in states:
            # states 필드: [icao24, callsign, origin_country, ...]
            icao = s[0] if s else ""
            callsign = (s[1] or "").strip() if len(s) > 1 else ""
            country = s[2] if len(s) > 2 else ""
            altitude = s[7] if len(s) > 7 else None   # baro_altitude
            velocity = s[9] if len(s) > 9 else None   # velocity m/s
            on_ground = s[8] if len(s) > 8 else True

            if on_ground:
                continue

            aircraft.append({
                "icao": icao,
                "callsign": callsign or "(no callsign)",
                "country": country,
                "altitude_m": round(altitude) if altitude else None,
                "speed_kmh": round(velocity * 3.6) if velocity else None,
            })

        # 무콜사인 항공기 (군용 가능성)
        no_callsign = [a for a in aircraft if a["callsign"] == "(no callsign)"]
        countries = {}
        for a in aircraft:
            c = a["country"]
            countries[c] = countries.get(c, 0) + 1

        return {
            "total_aircraft": len(aircraft),
            "no_callsign_count": len(no_callsign),
            "top_countries": sorted(countries.items(), key=lambda x: -x[1])[:5],
            "notable": no_callsign[:5],  # 무콜사인 최대 5개
        }
    except Exception as e:
        return {"error": str(e), "total_aircraft": 0}


def main():
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "zones": {},
        "summary": [],
    }

    for zone in ZONES:
        data = fetch_zone(zone)
        result["zones"][zone["name"]] = data

        if data.get("total_aircraft", 0) > 0:
            result["summary"].append({
                "zone": zone["name"],
                "aircraft": data["total_aircraft"],
                "no_callsign": data.get("no_callsign_count", 0),
            })

    result["summary"].sort(key=lambda x: -x["aircraft"])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
