#!/usr/bin/env python3
"""Small official Eurostat Comext adapter for EU mirror-trade fallbacks."""

from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"


def fetch_comext_value(
    reporter: str, partner: str, hs6: str, year: str, flow: str, timeout: float = 30,
) -> dict[str, Any]:
    if flow not in {"M", "X"}:
        raise ValueError("flow는 M 또는 X여야 합니다.")
    flow_code = "1" if flow == "M" else "2"
    indicator = "VALUE_IN_EUROS"
    key = f"M.{reporter}.{partner}.{hs6}.{flow_code}.{indicator}"
    query = urllib.parse.urlencode({
        "startPeriod": f"{year}-01", "endPeriod": f"{year}-12",
        "format": "SDMX_2.1_STRUCTURED",
    })
    request = urllib.request.Request(f"{BASE_URL}/{key}?{query}", headers={"User-Agent": "trade-market-briefing/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Eurostat Comext 호출 실패: {exc}") from exc
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError("Eurostat Comext XML 응답을 해석할 수 없습니다.") from exc
    observations = []
    for node in root.iter():
        if node.tag.endswith("Obs") and "OBS_VALUE" in node.attrib:
            observations.append({
                "period": node.attrib.get("TIME_PERIOD", ""),
                "value": float(node.attrib["OBS_VALUE"]),
            })
    return {
        "reporter": reporter, "partner": partner, "hs6": hs6, "year": year,
        "flow": flow, "currency": "EUR", "value": sum(row["value"] for row in observations),
        "observations": observations,
        "source_url": "https://ec.europa.eu/eurostat/web/international-trade-in-goods/database",
    }
