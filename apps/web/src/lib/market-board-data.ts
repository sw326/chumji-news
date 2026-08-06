import fixture from "./market-board-fixture.json";
import { supabase } from "./supabase";
import { CathodeMarketBoard } from "./market-board-types";

export async function getCathodeMarketBoard(): Promise<CathodeMarketBoard> {
  if (supabase) {
    const { data, error } = await supabase
      .from("ops_public_snapshots")
      .select("payload")
      .eq("kind", "trade-market")
      .maybeSingle();
    if (!error && data?.payload) {
      return data.payload as CathodeMarketBoard;
    }
  }
  return fixture as CathodeMarketBoard;
}
