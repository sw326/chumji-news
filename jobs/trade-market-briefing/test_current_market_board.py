import unittest
from datetime import date

from current_market_board import (
    assemble_market_board, build_market_signals, build_review_gate, collect_eu_cumulative, collect_korea_cumulative,
    collect_us_cumulative, latest_published_month, shift_month,
)


class CurrentMarketBoardTest(unittest.TestCase):
    def test_shift_month_crosses_year(self):
        self.assertEqual("202512", shift_month("202601", -1))

    def test_latest_month_requires_an_evidenced_non_total_row(self):
        def fake_fetcher(key, country, start, end, code, timeout):
            if start == "202606" and country == "US" and code == "A":
                return [{"hsCd": "A", "year": "2026.06"}]
            return []
        result = latest_published_month(
            "key", fetcher=fake_fetcher, today=date(2026, 8, 6),
            probe_countries=("US",), probe_codes=("A",),
        )
        self.assertEqual("202606", result["period"])
        self.assertEqual(["202608", "202607", "202606"], result["checked_periods"])

    def test_cumulative_periods_are_aligned_year_to_date(self):
        calls = []
        def fake_fetcher(key, country, start, end, code, timeout):
            calls.append((start, end))
            value = 120 if start == "202601" else 100
            return [{
                "hsCd": code, "statCd": country, "statKor": "품목", "statCdCntnKor1": country,
                "expDlr": value, "impDlr": 0, "expWgt": 10, "impWgt": 0,
            }]
        result = collect_korea_cumulative(
            "key", "202606", countries=("US",), codes=("2841909020",), fetcher=fake_fetcher,
        )
        self.assertIn(("202601", "202606"), calls)
        self.assertIn(("202501", "202506"), calls)
        self.assertAlmostEqual(0.2, result["period_comparison"]["growth_rate"])
        self.assertEqual("high", result["source"]["quality_grade"])

    def test_korea_monthly_series_keeps_same_month_comparison(self):
        def fake_fetcher(key, country, start, end, code, timeout):
            year = start[:4]
            base = 100 if year == "2025" else 120
            return [
                {"hsCd": code, "statCd": country, "statKor": "품목", "statCdCntnKor1": country,
                 "year": f"{year}.01", "expDlr": base, "impDlr": 0, "expWgt": 1, "impWgt": 0},
                {"hsCd": code, "statCd": country, "statKor": "품목", "statCdCntnKor1": country,
                 "year": f"{year}.02", "expDlr": base * 2, "impDlr": 0, "expWgt": 1, "impWgt": 0},
            ]
        result = collect_korea_cumulative(
            "key", "202602", countries=("US",), codes=("2841909020",), fetcher=fake_fetcher,
        )
        self.assertEqual(["2026-01", "2026-02"], [point["period"] for point in result["monthly_series"]])
        self.assertAlmostEqual(.2, result["monthly_series"][0]["growth_rate"])

    def test_us_uses_census_ytd_value(self):
        def fake_fetcher(period, country, code):
            return [{"GEN_VAL_YR": "120" if period == "2026-06" else "100"}]
        result = collect_us_cumulative("202606", hs6_codes=("284190",), fetcher=fake_fetcher)
        self.assertEqual(120, result["value"])
        self.assertAlmostEqual(.2, result["growth_rate"])

    def test_us_monthly_series_uses_month_value_not_ytd(self):
        def fake_fetcher(period, country, code):
            if period.startswith("from"):
                year = period.split()[1][:4]
                value = "12" if year == "2026" else "10"
                return [{"time": f"{year}-01", "GEN_VAL_MO": value}]
            return [{"GEN_VAL_YR": "12" if period == "2026-01" else "10"}]
        result = collect_us_cumulative("202601", hs6_codes=("284190",), fetcher=fake_fetcher)
        self.assertEqual(12, result["monthly_series"][0]["value"])
        self.assertAlmostEqual(.2, result["monthly_series"][0]["growth_rate"])

    def test_eu_uses_latest_common_month_and_previous_same_month(self):
        def fake_fetcher(country, partner, code, year, flow):
            values = {
                ("2026", "KR", "M"): [("2026-04", 10), ("2026-05", 20)],
                ("2026", "WORLD", "X"): [("2026-04", 5), ("2026-05", 10)],
                ("2025", "KR", "M"): [("2025-04", 8), ("2025-05", 12), ("2025-06", 99)],
            }[(year, partner, flow)]
            return {"observations": [{"period": p, "value": v} for p, v in values]}
        result = collect_eu_cumulative("HU", "2026", hs6_codes=("284190",), fetcher=fake_fetcher)
        self.assertEqual("2026-05", result["period"])
        self.assertEqual(30, result["value"])
        self.assertEqual(20, result["previous_value"])
        self.assertEqual("high", result["reexport_signal"])

    def test_board_refuses_cross_period_or_cross_currency_gap(self):
        korea = {"period": {"end": "202606"}, "rows": [{"country_code": "HU", "export_usd": 20}]}
        board = assemble_market_board(korea, [{"country_code": "HU", "period": "2026-05", "currency": "EUR", "value": 30}], as_of="2026-08-06")
        row = board["partner_statistics"][0]
        self.assertFalse(row["mirror_comparable"])
        self.assertIsNone(row["mirror_gap_usd"])

    def test_board_refuses_partial_code_scope_gap(self):
        korea = {"period": {"end": "202606"}, "rows": [{"country_code": "CN", "export_usd": 20}]}
        board = assemble_market_board(korea, [{"country_code": "CN", "period": "2026-06", "currency": "USD", "value": 3, "scope_comparable": False}], as_of="2026-08-06")
        row = board["partner_statistics"][0]
        self.assertFalse(row["mirror_comparable"])
        self.assertIsNone(row["mirror_gap_usd"])

    def test_signal_ignores_small_base_and_noncomparable_mirror(self):
        series = [{
            "country_code": "KR", "currency": "USD",
            "points": [{"period": "2026-01", "value": 100, "previous_value": 1, "growth_rate": 99}],
        }]
        comparisons = [{
            "country_code": "HU", "period": "2026-05", "currency": "EUR", "value": 30_000_000,
            "korea_reported_export_usd": 10_000_000, "mirror_comparable": False, "mirror_gap_usd": None,
        }]
        self.assertEqual([], build_market_signals(series, comparisons))

    def test_signal_flags_material_yoy_change_and_comparable_mirror_gap(self):
        series = [{
            "country_code": "US", "currency": "USD",
            "points": [{"period": "2026-06", "value": 30_000_000, "previous_value": 10_000_000, "growth_rate": 2}],
        }]
        comparisons = [{
            "country_code": "US", "period": "2026-06", "currency": "USD", "value": 40_000_000,
            "korea_reported_export_usd": 70_000_000, "mirror_comparable": True, "mirror_gap_usd": -30_000_000,
        }]
        signals = build_market_signals(series, comparisons)
        self.assertEqual({"year-over-year-surge", "mirror-gap"}, {signal["type"] for signal in signals})

    def test_gate_preserves_broad_code_blocker_and_manual_china_step(self):
        board = {
            "latest_periods": {"korea_customs": "2026-06"},
            "korea": {"rows": [{}], "classification_precision": {"total_value_usd": 100, "broad_value_usd": 30}},
            "partner_statistics": [{"country_code": "US", "data_status": "available", "mirror_comparable": True}],
        }
        gate = build_review_gate(board)
        self.assertEqual("blocked", gate["status"])
        self.assertEqual("2026-06", gate["china_manual_check"]["target_period"])

    def test_gate_treats_china_as_manual_not_automated_source(self):
        board = {
            "latest_periods": {"korea_customs": "2026-07"},
            "korea": {"rows": [{}], "classification_precision": {"total_value_usd": 100, "broad_value_usd": 10}},
            "partner_statistics": [
                {"country_code": code, "data_status": "available", "mirror_comparable": True}
                for code in ("US", "HU", "PL")
            ] + [{"country_code": "CN", "data_status": "not-manually-verified", "mirror_comparable": False}],
        }
        gate = build_review_gate(board)
        self.assertTrue(gate["automated_sources_complete"])
        self.assertEqual([], gate["blockers"])
        self.assertEqual("pending-one-time-verification", gate["china_manual_check"]["status"])


if __name__ == "__main__":
    unittest.main()
