import fixture from "./market-board-fixture.json";
import { supabase } from "./supabase";
import { CathodeMarketBoard } from "./market-board-types";

export type MarketBoardOrigin = "supabase" | "fallback";

export interface MarketBoardLoadResult {
  board: CathodeMarketBoard;
  origin: MarketBoardOrigin;
}

function applyRehearsalOverrides(board: CathodeMarketBoard): CathodeMarketBoard {
  if (process.env.MARKET_BOARD_REHEARSAL_GACC_PENDING !== "1") return board;
  return {
    ...board,
    review_gate: {
      ...board.review_gate,
      china_manual_check: {
        ...board.review_gate.china_manual_check,
        status: "pending-one-time-verification",
        instruction: "새 기준월의 GACC 공식 누계를 수동 검증해야 합니다.",
      },
    },
  };
}

export async function getCathodeMarketBoard(): Promise<MarketBoardLoadResult> {
  const forceFallback = process.env.MARKET_BOARD_FORCE_FALLBACK === "1";
  if (supabase && !forceFallback) {
    const { data, error } = await supabase
      .from("ops_public_snapshots")
      .select("payload")
      .eq("kind", "trade-market")
      .maybeSingle();
    if (!error && data?.payload) {
      return { board: applyRehearsalOverrides(data.payload as CathodeMarketBoard), origin: "supabase" };
    }
  }
  return { board: applyRehearsalOverrides(fixture as CathodeMarketBoard), origin: "fallback" };
}
