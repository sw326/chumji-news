"""Canonical trade-flow model and official-source adapter pipeline."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Protocol


EvidenceType = str


@dataclass(frozen=True)
class TradeSource:
    name: str
    url: str = ""
    dataset: str = ""
    retrieved_at: str = ""
    license: str = ""


@dataclass(frozen=True)
class CommodityClassification:
    system: str
    code: str
    version: str
    description: str = ""


@dataclass(frozen=True)
class TradeQuantity:
    value: float
    unit: str


@dataclass(frozen=True)
class TransformationStep:
    stage: str
    input_classification: CommodityClassification | None = None
    output_classification: CommodityClassification | None = None
    method: str = ""
    note: str = ""


@dataclass(frozen=True)
class TradeObservation:
    source: TradeSource
    commodity: CommodityClassification
    evidence: EvidenceType
    period: str
    reporter: str
    partner: str
    flow: str
    value_usd: float | None = None
    quantity: TradeQuantity | None = None
    transformation_steps: tuple[TransformationStep, ...] = field(default_factory=tuple)
    original: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.evidence not in {"observed", "inferred", "hypothesis"}:
            raise ValueError("evidence는 observed/inferred/hypothesis 중 하나여야 합니다.")
        if not self.commodity.version:
            raise ValueError("품목분류 버전이 필요합니다.")
        if not self.period:
            raise ValueError("시점(period)이 필요합니다.")
        if self.value_usd is None and self.quantity is None:
            raise ValueError("금액 또는 수량 중 하나는 필요합니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TradeDataAdapter(Protocol):
    """Common adapter contract for official trade-statistics sources."""

    name: str

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        ...


def normalize_with_adapter(
    adapter: TradeDataAdapter, rows: Iterable[dict[str, Any]]
) -> list[TradeObservation]:
    return adapter.normalize(rows)


def collect_trade_observations(
    jobs: Iterable[tuple[TradeDataAdapter, Iterable[dict[str, Any]]]]
) -> list[TradeObservation]:
    observations: list[TradeObservation] = []
    for adapter, rows in jobs:
        observations.extend(normalize_with_adapter(adapter, rows))
    return observations


def observation_to_graph_edge(observation: TradeObservation) -> dict[str, Any]:
    """Project one canonical observation into the existing supply-chain edge shape."""
    quantity = observation.quantity
    transformations = [asdict(step) for step in observation.transformation_steps]
    stage = transformations[-1]["stage"] if transformations else observation.flow
    return {
        "source": observation.reporter,
        "target": observation.partner,
        "stage": stage,
        "label": f"{observation.reporter} -> {observation.partner} {observation.commodity.code}",
        "product": f"{observation.commodity.system} {observation.commodity.code}",
        "classification": asdict(observation.commodity),
        "period": observation.period,
        "value_usd": observation.value_usd,
        "quantity": asdict(quantity) if quantity else None,
        "evidence": observation.evidence,
        "transformation_steps": transformations,
        "sources": [asdict(observation.source)],
        "observations": [observation.to_dict()],
        "interpretation": "; ".join(observation.notes),
    }


def parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_present(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


class KoreanCustomsAdapter:
    name = "Korea Customs Service"

    def __init__(self, classification_version: str = "HSK") -> None:
        self.classification_version = classification_version
        self.source = TradeSource(
            name="관세청 품목별 국가별 수출입실적",
            url="https://www.data.go.kr/data/15100475/openapi.do",
            dataset="nitemtrade",
        )

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        observations: list[TradeObservation] = []
        for row in rows:
            hs_code = first_present(row, "hsCd", "hs_code")
            country = first_present(row, "statCd", "country_code")
            if not hs_code or hs_code == "-" or not country or country == "-":
                continue
            item_name = first_present(row, "statKor", "item_name")
            period = first_present(row, "year", "period")
            export_usd = parse_number(row.get("expDlr", row.get("export_usd")))
            export_kg = parse_number(row.get("expWgt", row.get("export_kg")))
            import_usd = parse_number(row.get("impDlr", row.get("import_usd")))
            import_kg = parse_number(row.get("impWgt", row.get("import_kg")))
            commodity = CommodityClassification("HSK", hs_code, self.classification_version, item_name)
            if export_usd is not None or export_kg is not None:
                observations.append(
                    TradeObservation(
                        source=self.source,
                        commodity=commodity,
                        evidence="observed",
                        period=period,
                        reporter="KR",
                        partner=country,
                        flow="export",
                        value_usd=export_usd,
                        quantity=TradeQuantity(export_kg, "kg") if export_kg is not None else None,
                        original=dict(row),
                        notes=("수출은 FOB 기준입니다.",),
                    )
                )
            if import_usd is not None or import_kg is not None:
                observations.append(
                    TradeObservation(
                        source=self.source,
                        commodity=commodity,
                        evidence="observed",
                        period=period,
                        reporter="KR",
                        partner=country,
                        flow="import",
                        value_usd=import_usd,
                        quantity=TradeQuantity(import_kg, "kg") if import_kg is not None else None,
                        original=dict(row),
                        notes=("수입은 CIF 기준입니다.",),
                    )
                )
        return observations


class UNComtradeAdapter:
    name = "UN Comtrade"

    def __init__(self, classification_version: str = "HS") -> None:
        self.classification_version = classification_version
        self.source = TradeSource(
            name="UN Comtrade",
            url="https://comtradeplus.un.org/TradeFlow",
            dataset="public preview",
        )

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        observations: list[TradeObservation] = []
        for row in rows:
            code = first_present(row, "cmdCode", "cmdCodeAggr", "commodityCode")
            if not code:
                continue
            commodity = CommodityClassification(
                "HS",
                code,
                first_present(row, "classificationSearchCode") or self.classification_version,
                first_present(row, "cmdDesc", "commodityDesc"),
            )
            flow = first_present(row, "flowCode", "flowDesc", "flow") or "trade"
            observations.append(
                TradeObservation(
                    source=self.source,
                    commodity=commodity,
                    evidence="observed",
                    period=first_present(row, "period", "refPeriodId"),
                    reporter=first_present(row, "reporterCode", "reporterISO", "reporterDesc"),
                    partner=first_present(row, "partnerCode", "partnerISO", "partnerDesc"),
                    flow=flow,
                    value_usd=parse_number(row.get("primaryValue", row.get("fobvalue"))),
                    quantity=(
                        TradeQuantity(parse_number(row.get("qty")) or 0, first_present(row, "qtyUnitAbbr", "qtyUnitCode"))
                        if row.get("qty") not in (None, "")
                        else None
                    ),
                    original=dict(row),
                    notes=("UN Comtrade mirror statistics may differ from national customs releases.",),
                )
            )
        return observations


ROC_YEAR_OFFSET = 1911

VALUE_UNIT_SCALES = {
    "usd": 1.0,
    "thousand_usd": 1_000.0,
    "million_usd": 1_000_000.0,
}


def parse_roc_period(value: Any) -> str:
    """Convert a Republic-of-China calendar period into ISO `YYYY-MM` (or `YYYY`).

    Accepts the shapes the Taiwanese sources actually emit: the integer `11506`
    used by the customs portal JSON and the `104年 10月` / `104年` strings used by
    the MOF statistics CSV.
    """
    if value in (None, ""):
        return ""
    text = str(value).strip()
    match = re.fullmatch(r"(\d{2,3})\s*年\s*(?:(\d{1,2})\s*月)?", text)
    if match:
        year = int(match.group(1)) + ROC_YEAR_OFFSET
        month = match.group(2)
        return f"{year}-{int(month):02d}" if month else str(year)
    # ROC years are two or three digits, so a stamp is YYMM or YYYMM — never wider.
    if re.fullmatch(r"\d{4,5}", text):
        year = int(text[:-2]) + ROC_YEAR_OFFSET
        month = int(text[-2:])
        if 1 <= month <= 12:
            return f"{year}-{month:02d}"
        if month == 0:
            return str(year)
    if re.fullmatch(r"\d{2,3}", text):
        return str(int(text) + ROC_YEAR_OFFSET)
    raise ValueError(f"민국 기준 시점을 해석할 수 없습니다: {value!r}")


class USCensusAdapter:
    name = "US Census International Trade"

    def __init__(self, classification_version: str = "HS") -> None:
        self.classification_version = classification_version
        self.source = TradeSource(
            name="US Census International Trade API",
            url="https://www.census.gov/data/developers/data-sets/international-trade.html",
            dataset="imports/hs",
        )

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        observations: list[TradeObservation] = []
        for row in rows:
            code = first_present(row, "I_COMMODITY", "E_COMMODITY")
            if not code:
                continue
            period = first_present(row, "time")
            if not period:
                year = first_present(row, "YEAR")
                month = first_present(row, "MONTH")
                period = f"{year}-{month.zfill(2)}" if year and month else year
            observations.append(
                TradeObservation(
                    source=self.source,
                    commodity=CommodityClassification(
                        "HS",
                        code,
                        self.classification_version,
                        first_present(row, "I_COMMODITY_LDESC", "E_COMMODITY_LDESC"),
                    ),
                    evidence="observed",
                    period=period,
                    reporter="US",
                    partner=first_present(row, "CTY_CODE", "CTY_NAME"),
                    flow="import",
                    value_usd=parse_number(row.get("GEN_VAL_MO", row.get("GEN_VAL_YR"))),
                    original=dict(row),
                    notes=("US imports are reported by origin and customs value field selected from Census.",),
                )
            )
        return observations


def _taiwan_value_usd(row: dict[str, Any], key: str) -> float | None:
    """Scale a Taiwanese value column into plain USD using the row's declared unit."""
    amount = parse_number(row.get(key))
    if amount is None:
        return None
    # 단위를 기본값으로 때우면 천 달러를 달러로 읽는 실수가 조용히 지나간다.
    unit = first_present(row, "valueUnit", "value_unit")
    if not unit:
        raise ValueError(
            f"대만 행에 금액 단위(valueUnit)가 없습니다: {sorted(row)}. "
            f"{sorted(VALUE_UNIT_SCALES)} 중 하나를 명시하세요."
        )
    scale = VALUE_UNIT_SCALES.get(unit)
    if scale is None:
        raise ValueError(f"대만 금액 단위를 해석할 수 없습니다: {unit!r}")
    return amount * scale


def _taiwan_quantity(row: dict[str, Any]) -> TradeQuantity | None:
    amount = parse_number(row.get("quantity"))
    if amount is None:
        return None
    return TradeQuantity(amount, first_present(row, "quantityUnit", "quantity_unit"))


def _taiwan_observations(
    row: dict[str, Any],
    source: TradeSource,
    commodity: CommodityClassification,
    period: str,
    partner: str,
    notes: tuple[str, ...],
) -> list[TradeObservation]:
    """Emit one observation per flow present in a Taiwanese row.

    Both sources publish export and import side by side in a single row for
    two-way tables, and a single `godValue` column plus an explicit flow for
    one-way tables.
    """
    quantity = _taiwan_quantity(row)
    flows: list[tuple[str, float | None]] = []
    for flow, key in (("export", "exportGodValue"), ("import", "importGodValue")):
        if row.get(key) not in (None, ""):
            flows.append((flow, _taiwan_value_usd(row, key)))
    if not flows:
        flow = first_present(row, "flow") or "trade"
        value = _taiwan_value_usd(row, "godValue")
        if value is None:
            value = _taiwan_value_usd(row, "value")
        flows.append((flow, value))

    observations: list[TradeObservation] = []
    for flow, value_usd in flows:
        if value_usd is None and quantity is None:
            continue
        observations.append(
            TradeObservation(
                source=source,
                commodity=commodity,
                evidence="observed",
                period=period,
                reporter="TW",
                partner=partner,
                flow=flow,
                value_usd=value_usd,
                quantity=quantity,
                original=dict(row),
                notes=notes,
            )
        )
    return observations


class TaiwanCustomsPortalAdapter:
    """財政部關務署 海關進出口統計 interactive-dashboard rows.

    Values arrive as partner groups (A01~A09) crossed with the eleven official
    goods groups, so the commodity codes are not HS codes and must not be joined
    to HS-based series without an explicit mapping.
    """

    name = "Taiwan Customs Administration trade statistics"

    def __init__(self, classification_version: str = "MOF-GOODS-GROUP-2026") -> None:
        self.classification_version = classification_version
        self.source = TradeSource(
            name="財政部關務署 海關進出口統計",
            url="https://portal.sw.nat.gov.tw/APGA/GA35",
            dataset="GA28_getChartData",
            license="政府資料開放授權條款 第1版 (출처표시)",
        )

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        observations: list[TradeObservation] = []
        for row in rows:
            period = parse_roc_period(first_present(row, "yyymm", "period", "rocPeriod"))
            if not period:
                continue
            partner = first_present(row, "partnerKey", "partner")
            if not partner:
                continue
            code = first_present(row, "goodsTypeKey") or "ALL"
            commodity = CommodityClassification(
                "MOF-GOODS-GROUP",
                code,
                self.classification_version,
                first_present(row, "goodsType") or "總計",
            )
            observations.extend(
                _taiwan_observations(
                    row,
                    self.source,
                    commodity,
                    period,
                    partner,
                    (
                        "관무서 대시보드는 국가군(A01~A09)과 11대 화품분류 기준이며 HS 코드가 아닙니다.",
                        "수출은 FOB, 수입은 CIF 기준입니다.",
                    ),
                )
            )
        return observations


class TaiwanMofStatsAdapter:
    """財政部統計資料庫 국별·화품세분류 교차표 rows.

    The MOF database publishes its own `貨品細分類` codes, not HS codes, and the
    trade section stops at the ROC 104/12 (2015-12) release.
    """

    name = "Taiwan MOF statistics database trade tables"

    def __init__(self, classification_version: str = "MOF-ITEM") -> None:
        self.classification_version = classification_version
        self.source = TradeSource(
            name="財政部統計資料庫 貿易統計",
            url="https://web02.mof.gov.tw/njswww/webMain.aspx",
            dataset="njswww sys=220",
        )

    def normalize(self, rows: Iterable[dict[str, Any]]) -> list[TradeObservation]:
        observations: list[TradeObservation] = []
        for row in rows:
            period = parse_roc_period(first_present(row, "rocPeriod", "period"))
            if not period:
                continue
            partner = first_present(row, "countryCode", "countryName")
            if not partner:
                continue
            commodity = CommodityClassification(
                "MOF-ITEM",
                first_present(row, "itemCode") or "0",
                self.classification_version,
                first_present(row, "itemName"),
            )
            observations.extend(
                _taiwan_observations(
                    row,
                    self.source,
                    commodity,
                    period,
                    partner,
                    (
                        "재정부 통계DB 화품세분류는 HS 코드가 아닙니다.",
                        "재정부 무역통계 구간은 민국 104년 12월(2015-12)에서 끝납니다.",
                    ),
                )
            )
        return observations
