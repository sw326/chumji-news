#!/usr/bin/env python3
"""Comparable market structure metrics for normalized trade rows."""

from __future__ import annotations

from typing import Any


def market_structure(
    rows: list[dict[str, Any]], *, value_key: str, country_key: str, weight_key: str | None = None
) -> dict[str, Any]:
    by_country: dict[str, dict[str, float]] = {}
    for row in rows:
        country = str(row.get(country_key, "unknown"))
        bucket = by_country.setdefault(country, {"value_usd": 0.0, "weight_kg": 0.0})
        bucket["value_usd"] += float(row.get(value_key, 0) or 0)
        if weight_key:
            bucket["weight_kg"] += float(row.get(weight_key, 0) or 0)
    total = sum(row["value_usd"] for row in by_country.values())
    ranking = []
    for country, values in by_country.items():
        share = values["value_usd"] / total if total else 0.0
        item = {"country": country, "value_usd": values["value_usd"], "share": share}
        if values["weight_kg"] > 0:
            item["unit_value_usd_per_kg"] = values["value_usd"] / values["weight_kg"]
        ranking.append(item)
    ranking.sort(key=lambda row: row["value_usd"], reverse=True)
    hhi = sum((row["share"] * 100) ** 2 for row in ranking)
    return {
        "total_value_usd": total,
        "country_count": len(ranking),
        "hhi": hhi,
        "concentration": "high" if hhi >= 2500 else ("moderate" if hhi >= 1500 else "low"),
        "top3_share": sum(row["share"] for row in ranking[:3]),
        "country_ranking": ranking,
        "caveats": [
            "HHI와 점유율은 현재 선택한 국가 집합 안에서 계산된다.",
            "금액/중량은 품질·제품구성 차이를 포함하므로 가격으로 단정하지 않는다.",
        ],
    }


def compare_period_rows(
    current: list[dict[str, Any]], previous: list[dict[str, Any]], *,
    value_key: str, identity_keys: tuple[str, ...]
) -> dict[str, Any]:
    def indexed(rows: list[dict[str, Any]]) -> dict[tuple[str, ...], float]:
        result: dict[tuple[str, ...], float] = {}
        for row in rows:
            key = tuple(str(row.get(field, "")) for field in identity_keys)
            result[key] = result.get(key, 0.0) + float(row.get(value_key, 0) or 0)
        return result
    current_by_key, previous_by_key = indexed(current), indexed(previous)
    comparisons = []
    for key in sorted(set(current_by_key) | set(previous_by_key)):
        current_value, previous_value = current_by_key.get(key, 0.0), previous_by_key.get(key, 0.0)
        comparisons.append({
            "identity": dict(zip(identity_keys, key)),
            "current_value_usd": current_value, "previous_value_usd": previous_value,
            "change_usd": current_value - previous_value,
            "growth_rate": ((current_value / previous_value) - 1) if previous_value else None,
        })
    current_total, previous_total = sum(current_by_key.values()), sum(previous_by_key.values())
    return {
        "current_total_usd": current_total, "previous_total_usd": previous_total,
        "change_usd": current_total - previous_total,
        "growth_rate": ((current_total / previous_total) - 1) if previous_total else None,
        "rows": comparisons,
        "notice": "전년동기 증감은 금액 기준이며 가격·환율·제품 구성 변화와 물량 변화를 함께 포함한다.",
    }
