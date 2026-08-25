#!/usr/bin/env python3
"""Build evidence-aware industrial supply-chain maps from official trade APIs."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from trade_data_model import (
    USCensusAdapter,
    UNComtradeAdapter,
    TradeObservation,
    observation_to_graph_edge,
)


COMTRADE_URL = "https://comtradeapi.un.org/public/v1/preview/C/{freq}/HS"
CENSUS_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
COMTRADE_KEYCHAIN_SERVICE = "openclaw.trade-market.comtrade"
COMTRADE_KEYCHAIN_ACCOUNT = "trade-market-briefing"
CENSUS_KEYCHAIN_SERVICE = "openclaw.trade-market.census"
CENSUS_KEYCHAIN_ACCOUNT = "trade-market-briefing"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "trade-market-briefing"


def load_keychain_secret(env_name: str, service: str, account: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value or sys.platform != "darwin":
        return value
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w", "-a", account, "-s", service],
            check=True, capture_output=True, text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def load_comtrade_subscription_key() -> str:
    return load_keychain_secret(
        "COMTRADE_SUBSCRIPTION_KEY", COMTRADE_KEYCHAIN_SERVICE, COMTRADE_KEYCHAIN_ACCOUNT
    )


def load_census_api_key() -> str:
    """Load the Census key from the environment or this Mac's login Keychain."""
    return load_keychain_secret(
        "CENSUS_API_KEY", CENSUS_KEYCHAIN_SERVICE, CENSUS_KEYCHAIN_ACCOUNT
    )


def request_json(
    url: str, params: dict[str, Any], timeout: float = 20,
    headers: dict[str, str] | None = None, retries: int = 0,
) -> Any:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    request = urllib.request.Request(
        f"{url}?{query}", headers={"User-Agent": "trade-market-briefing/0.4", **(headers or {})}
    )
    payload = b""
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                raise RuntimeError(f"API 호출 실패: HTTP {exc.code} {exc.reason}") from exc
            retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
            delay = min(2.0, float(retry_after)) if retry_after.replace(".", "", 1).isdigit() else 0.5 * (attempt + 1)
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt >= retries:
                raise RuntimeError(f"API 호출 실패: {exc}") from exc
            time.sleep(0.5 * (attempt + 1))
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        preview = payload[:160].decode("utf-8", errors="replace")
        raise RuntimeError(f"JSON이 아닌 응답입니다: {preview}") from exc


def fetch_comtrade(
    reporter: int,
    partner: int,
    hs6: str,
    period: str,
    flow: str = "X",
    frequency: str = "A",
    timeout: float = 20,
    cache_dir: Path | None = DEFAULT_CACHE_DIR,
    cache_ttl_seconds: int = 21600,
) -> list[dict[str, Any]]:
    """Fetch normalized bilateral HS6 trade from UN Comtrade's public preview API."""
    params = {
            "period": period,
            "reporterCode": reporter,
            "partnerCode": partner,
            "partner2Code": 0,
            "cmdCode": hs6,
            "flowCode": flow,
            "customsCode": "C00",
            "motCode": 0,
            "maxRecords": 500,
        }
    cache_key = f"comtrade-{frequency}-{reporter}-{partner}-{hs6}-{period}-{flow}.json"
    cache_path = cache_dir / cache_key if cache_dir else None
    if cache_path and cache_path.exists() and time.time() - cache_path.stat().st_mtime <= cache_ttl_seconds:
        cached_rows = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached_rows:
            return cached_rows
    key = load_comtrade_subscription_key()
    headers = {"Ocp-Apim-Subscription-Key": key} if key else {}
    payload = request_json(
        COMTRADE_URL.format(freq=frequency), params, timeout, headers=headers, retries=2
    )
    if payload.get("error"):
        raise RuntimeError(f"UN Comtrade 오류: {payload['error']}")
    rows = payload.get("data", [])
    if cache_path and rows:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def fetch_comtrade_observations(
    reporter: int,
    partner: int,
    hs6: str,
    period: str,
    flow: str = "X",
    frequency: str = "A",
    timeout: float = 20,
) -> list[TradeObservation]:
    rows = fetch_comtrade(reporter, partner, hs6, period, flow, frequency, timeout)
    return UNComtradeAdapter().normalize(rows)


def fetch_us_imports(
    time: str,
    country_code: str,
    hs_code: str,
    api_key: str | None = None,
    timeout: float = 20,
) -> list[dict[str, str]]:
    """Fetch US imports by origin and HS code from the Census trade API."""
    key = api_key or load_census_api_key()
    if not key:
        raise RuntimeError("CENSUS_API_KEY 또는 macOS Keychain 등록 키가 필요합니다.")
    payload = request_json(
        CENSUS_URL,
        {
            "get": "GEN_VAL_YR,GEN_VAL_MO,I_COMMODITY,I_COMMODITY_LDESC,CTY_NAME",
            "time": time,
            "CTY_CODE": country_code,
            "I_COMMODITY": hs_code,
            "key": key,
        },
        timeout,
    )
    if not isinstance(payload, list) or not payload:
        return []
    headers = payload[0]
    return [dict(zip(headers, values)) for values in payload[1:]]


def fetch_us_import_observations(
    time: str,
    country_code: str,
    hs_code: str,
    api_key: str | None = None,
    timeout: float = 20,
) -> list[TradeObservation]:
    rows = fetch_us_imports(time, country_code, hs_code, api_key, timeout)
    return USCensusAdapter().normalize(rows)


def graph_from_observations(
    observations: list[TradeObservation], title: str = "산업 공급망 지도"
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    for observation in observations:
        nodes.setdefault(observation.reporter, {"id": observation.reporter, "label": observation.reporter})
        nodes.setdefault(observation.partner, {"id": observation.partner, "label": observation.partner})
    return {
        "title": title,
        "nodes": list(nodes.values()),
        "edges": [observation_to_graph_edge(observation) for observation in observations],
    }


def validate_graph(graph: dict[str, Any]) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    ids = {node.get("id") for node in nodes}
    if None in ids or len(ids) != len(nodes):
        raise ValueError("노드 id가 없거나 중복됐습니다.")
    for edge in edges:
        if edge.get("source") not in ids or edge.get("target") not in ids:
            raise ValueError(f"존재하지 않는 노드를 참조하는 경로: {edge}")
        if edge.get("evidence") not in {"observed", "inferred", "hypothesis"}:
            raise ValueError("evidence는 observed/inferred/hypothesis 중 하나여야 합니다.")
        if not edge.get("sources"):
            raise ValueError("모든 경로에는 최소 하나의 출처가 필요합니다.")
        if not edge.get("period"):
            raise ValueError("모든 경로에는 시점(period)이 필요합니다.")
        if edge.get("evidence") != "hypothesis" and edge.get("value_usd") is None and edge.get("quantity") is None:
            raise ValueError("모든 경로에는 금액(value_usd) 또는 수량(quantity)이 필요합니다.")
        classification = edge.get("classification")
        if classification and not classification.get("version"):
            raise ValueError("품목분류 버전이 필요합니다.")
        observations = edge.get("observations", [])
        if observations and not isinstance(observations, list):
            raise ValueError("observations는 목록이어야 합니다.")
        for observation in observations:
            commodity = observation.get("commodity", {})
            if not commodity.get("version"):
                raise ValueError("관측값에는 품목분류 버전이 필요합니다.")
            if observation.get("evidence") not in {"observed", "inferred", "hypothesis"}:
                raise ValueError("관측값 evidence가 올바르지 않습니다.")
            if not observation.get("period"):
                raise ValueError("관측값에는 시점(period)이 필요합니다.")
            if (
                observation.get("evidence") != "hypothesis"
                and observation.get("value_usd") is None
                and observation.get("quantity") is None
            ):
                raise ValueError("관측값에는 금액 또는 수량이 필요합니다.")


def render_html(graph: dict[str, Any]) -> str:
    validate_graph(graph)
    data = json.dumps(graph, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(graph.get("title", "산업 공급망 지도"))
    template = Path(__file__).with_name("supply_chain_map_template.html").read_text(
        encoding="utf-8"
    )
    return template.replace("{{TITLE}}", title).replace("{{GRAPH_JSON}}", data)


def main() -> int:
    parser = argparse.ArgumentParser(description="근거 기반 산업 공급망 지도 생성")
    parser.add_argument("--input", type=Path, required=True, help="공급망 그래프 JSON")
    parser.add_argument("--output", type=Path, required=True, help="생성할 HTML")
    args = parser.parse_args()
    graph = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(graph), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
