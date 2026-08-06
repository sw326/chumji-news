#!/usr/bin/env python3
"""Audit 2022 Customs battery examples against the current HSK reference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path(__file__).with_name("data") / "battery_classification_cases.json"
DEFAULT_HSK = Path(__file__).with_name("data") / "hsk2026_reference.json"


class BatteryClassificationError(ValueError):
    pass


def load_audit(cases_path: Path = DEFAULT_CASES, hsk_path: Path = DEFAULT_HSK) -> dict[str, Any]:
    source = json.loads(cases_path.read_text(encoding="utf-8"))
    current = json.loads(hsk_path.read_text(encoding="utf-8"))
    if source.get("source", {}).get("usage") != "reference-only-noncommercial":
        raise BatteryClassificationError("관세청 지침의 이용 제한 메타데이터가 필요합니다.")
    current_by_code = {str(row["code"]): row for row in current.get("entries", [])}
    audited = []
    ids: set[str] = set()
    for case in source.get("cases", []):
        case_id = str(case.get("id", ""))
        code = str(case.get("hsk2022", ""))
        if not case_id or case_id in ids or len(code) != 10 or not code.isdigit():
            raise BatteryClassificationError("사례 ID가 중복됐거나 HSK10 형식이 아닙니다.")
        ids.add(case_id)
        current_row = current_by_code.get(code)
        status = "code-present" if current_row else "code-retired-or-changed"
        breadth = "dedicated" if current_row and current_row.get("name_ko") not in {"기타", "Other"} else "broad-other"
        audited.append({
            **case,
            "hsk2026": code if current_row else None,
            "hsk2026_name_ko": current_row.get("name_ko", "") if current_row else "",
            "hsk2026_name_en": current_row.get("name_en", "") if current_row else "",
            "migration_status": status,
            "code_breadth": breadth,
            "warning": (
                "2026 코드가 유지되지만 품명이 기타이므로 해당 산업 용도를 분리할 수 없다."
                if breadth == "broad-other" and current_row else
                "2026 HSK에서 동일 코드를 찾지 못했으므로 재분류 확인이 필요하다."
                if not current_row else
                "2026 HSK에 전용 품명이 유지된다. 그래도 실제 물품 성상에 따라 분류가 달라질 수 있다."
            ),
        })
    by_id = {row["id"]: row for row in audited}
    path_specs = [
        {
            "id": "ncm", "label": "NCM 계열", "case_ids": ["raw-sulfate-solution-mix", "pcam-ncm-hydroxide", "cam-ncm"],
            "downstream": {"system": "HSK", "version": "2026", "code": "8507600000", "label": "리튬이온 축전지"},
            "gaps": ["리튬염 투입량", "전구체·활물질의 실제 수율", "셀 용도별 분리"],
        },
        {
            "id": "nca", "label": "NCA 계열", "case_ids": ["pcam-nca-hydroxide", "cam-nca"],
            "downstream": {"system": "HSK", "version": "2026", "code": "8507600000", "label": "리튬이온 축전지"},
            "gaps": ["니켈·코발트·알루미늄 원료 단계", "리튬염 투입량", "셀 용도별 분리"],
        },
        {
            "id": "lfp", "label": "LFP 계열", "case_ids": ["cam-lfp-pure", "cam-lfp-carbon-mix"],
            "downstream": {"system": "HSK", "version": "2026", "code": "8507600000", "label": "리튬이온 축전지"},
            "gaps": ["인산철·리튬염 상류 분류", "순수 LFP와 탄소 혼합·코팅품의 통계 분리", "셀 용도별 분리"],
        },
        {
            "id": "lco", "label": "LCO 계열", "case_ids": ["cam-lco"],
            "downstream": {"system": "HSK", "version": "2026", "code": "8507600000", "label": "리튬이온 축전지"},
            "gaps": ["코발트·리튬 원료와 전구체 단계", "소형 IT용 등 최종 용도 분리"],
        },
    ]
    precision_paths = []
    for path in path_specs:
        case_ids = path["case_ids"]
        precision_paths.append({
            **{key: value for key, value in path.items() if key != "case_ids"},
            "cases": [by_id[case_id] for case_id in case_ids],
        })
    return {
        "version": source["version"],
        "source": source["source"],
        "current_classification": current.get("classification"),
        "current_source_url": current.get("source_url"),
        "cases": audited,
        "precision_paths": precision_paths,
        "summary": {
            "total": len(audited),
            "code_present": sum(row["migration_status"] == "code-present" for row in audited),
            "broad_other": sum(row["code_breadth"] == "broad-other" for row in audited),
            "dedicated": sum(row["code_breadth"] == "dedicated" for row in audited),
        },
    }


def summarize_trade_precision(rows: list[dict[str, Any]], value_key: str) -> dict[str, Any]:
    """Split selected trade value into dedicated vs broad HSK buckets."""
    audit = load_audit()
    breadth_by_code: dict[str, str] = {}
    for case in audit["cases"]:
        code = case["hsk2022"]
        previous = breadth_by_code.get(code)
        breadth_by_code[code] = "broad-other" if "broad-other" in {previous, case["code_breadth"]} else "dedicated"
    totals = {"dedicated_value_usd": 0.0, "broad_value_usd": 0.0, "outside_audit_value_usd": 0.0}
    for row in rows:
        value = float(row.get(value_key, 0) or 0)
        breadth = breadth_by_code.get(str(row.get("hs_code", "")))
        if breadth == "dedicated":
            totals["dedicated_value_usd"] += value
        elif breadth == "broad-other":
            totals["broad_value_usd"] += value
        else:
            totals["outside_audit_value_usd"] += value
    total = sum(totals.values())
    return {
        **totals,
        "total_value_usd": total,
        "dedicated_share": totals["dedicated_value_usd"] / total if total else 0.0,
        "notice": "전용 품명 코드 금액은 비교적 식별력이 높지만 실제 물품 분류를 보증하지 않는다. 기타·광범위 코드 금액은 양극재 금액으로 단정할 수 없다.",
    }


if __name__ == "__main__":
    print(json.dumps(load_audit(), ensure_ascii=False, indent=2))
