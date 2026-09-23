#!/usr/bin/env node
import fs from "node:fs";
import { createHash } from "node:crypto";
import { validPriceDate } from "../src/lib/price-artifact.mjs";

const [base, date, file] = process.argv.slice(2);
try {
  if (!base || !validPriceDate(date) || !file) throw new Error("usage: verify-price-artifact.mjs BASE DATE HTML_FILE");
  const url = new URL(`/fresh-food/${date}/index.html`, base);
  const response = await fetch(url, { redirect: "error", cache: "no-store", signal: AbortSignal.timeout(15000) });
  if (!response.ok || !response.headers.get("content-type")?.includes("text/html")) {
    throw new Error(`graph unavailable: HTTP ${response.status}`);
  }
  const digest = (data) => createHash("sha256").update(data).digest("hex");
  if (digest(Buffer.from(await response.arrayBuffer())) !== digest(fs.readFileSync(file))) {
    throw new Error("public graph hash mismatch");
  }
  console.log(`verified public graph: ${date}`);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
