#!/usr/bin/env python3
"""Validated manual snapshots from the official China Customs statistics UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_SNAPSHOT = Path(__file__).with_name("data") / "gacc_official_snapshots.json"


def load_gacc_snapshot(
    hs6: str,
    year: str,
    *,
    partner_code: str = "133",
    path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any] | None:
    """Return a complete, provenance-bearing GACC row for an HS6/year/partner.

    A full-year row is returned directly. Two verified half-year rows are
    aggregated only when both halves exist, so partial coverage is never
    mistaken for an annual total.
    """
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        dict(row)
        for row in payload.get("rows", [])
        if (
            str(row.get("hs8", ""))[:6] == str(hs6)
            and str(row.get("year")) == str(year)
            and str(row.get("partner_code")) == str(partner_code)
        )
    ]
    for row in matches:
        if row.get("coverage") == "full-year":
            return row

    halves = {row.get("coverage"): row for row in matches}
    if {"first-half", "second-half"} <= halves.keys():
        first = halves["first-half"]
        second = halves["second-half"]
        combined = dict(first)
        combined.update(
            period=f"January to December {year}",
            coverage="full-year-aggregated",
            quantity=sum(int(row.get("quantity") or 0) for row in (first, second)),
            value=sum(int(row.get("value") or 0) for row in (first, second)),
            data_status=(
                "reported-zero"
                if all((row.get("data_status") == "reported-zero") for row in (first, second))
                else "available"
            ),
            component_periods=[first["period"], second["period"]],
        )
        return combined
    return None


def load_gacc_period_snapshot(
    hs8: str,
    year: str,
    coverage: str,
    *,
    partner_code: str = "133",
    path: Path = DEFAULT_SNAPSHOT,
) -> dict[str, Any] | None:
    """Return one manually verified period without promoting it to a full year."""
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return next((
        dict(row) for row in payload.get("rows", [])
        if str(row.get("hs8")) == str(hs8)
        and str(row.get("year")) == str(year)
        and str(row.get("coverage")) == str(coverage)
        and str(row.get("partner_code")) == str(partner_code)
    ), None)
