import { priceArtifactResponse } from "@/lib/price-artifact.mjs";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ date: string }> },
) {
  const { date } = await params;
  return priceArtifactResponse(date);
}
