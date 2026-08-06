export interface MarketQuality {
  score: number;
  maximum: number;
  grade: string;
  limitations: string[];
}

export interface PartnerStatistic {
  country_code: string;
  period: string | null;
  previous_period: string | null;
  value: number;
  previous_value: number | null;
  growth_rate: number | null;
  currency: string;
  source: string;
  data_status: string;
  quality: MarketQuality;
  mirror_comparable: boolean;
  mirror_gap_usd: number | null;
  comparison_notice: string;
  reexport_signal?: string;
}

export interface MarketSeriesPoint {
  period: string;
  value: number;
  previous_period: string;
  previous_value: number | null;
  growth_rate: number | null;
}

export interface MarketTimeSeries {
  country_code: string;
  source: string;
  currency: string;
  classification: string;
  measure: "monthly-export" | "monthly-import";
  points: MarketSeriesPoint[];
}

export interface CathodeMarketBoard {
  title: string;
  as_of: string;
  latest_periods: Record<string, string | null>;
  aggregation_policy: string;
  time_series?: MarketTimeSeries[];
  korea: {
    period: { start: string; end: string };
    totals: { export_usd: number; previous_export_usd: number };
    period_comparison: { change_usd: number; growth_rate: number | null };
    classification_precision: {
      dedicated_share: number;
      broad_value_usd: number;
    };
  };
  partner_statistics: PartnerStatistic[];
  review_gate: {
    status: string;
    automated_sources_complete: boolean;
    china_manual_check: {
      status: string;
      target_period: string | null;
      instruction: string;
    };
    blockers: string[];
    warnings: string[];
  };
}
