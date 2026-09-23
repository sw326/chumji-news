import { createHash } from "node:crypto";

export function validPriceDate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) &&
    new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;
}

// Export the actual route implementation for deterministic, network-free tests.
export async function priceArtifactResponse(date, {
  url = process.env.NEXT_PUBLIC_SUPABASE_URL,
  key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  fetchImpl = fetch,
} = {}) {
  const fail = (status) => new Response("Price graph unavailable", {
    status, headers: { "Cache-Control": "no-store" },
  });
  if (date !== "latest" && !validPriceDate(date)) return fail(404);
  if (!url || !key) return fail(503);
  try {
    const endpoint = new URL("/rest/v1/price_snapshot_artifacts", url);
    endpoint.searchParams.set("select", "date,html,sha256");
    endpoint.searchParams.set("limit", "1");
    if (date === "latest") endpoint.searchParams.set("order", "date.desc");
    else endpoint.searchParams.set("date", `eq.${date}`);
    const result = await fetchImpl(endpoint, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (!result.ok) return fail(503);
    const rows = await result.json();
    if (!Array.isArray(rows)) return fail(503);
    if (!rows.length) return fail(404);
    const row = rows[0];
    if (!validPriceDate(row.date) || (date !== "latest" && row.date !== date) ||
        typeof row.html !== "string" || !row.html.length ||
        createHash("sha256").update(row.html).digest("hex") !== row.sha256) return fail(503);
    return new Response(row.html, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Price-Snapshot-Date": row.date,
        ETag: `"${row.sha256}"`,
      },
    });
  } catch {
    return fail(503);
  }
}
