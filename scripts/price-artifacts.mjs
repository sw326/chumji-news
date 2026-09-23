#!/usr/bin/env node
// Dry-run by default. Backfill never changes news summaries or sends messages.
import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
import { validPriceDate } from "../src/lib/price-artifact.mjs";

export function artifact(date, html) {
  if (!validPriceDate(date)) throw new Error("invalid snapshot date");
  if (!/<html[\s>]/i.test(html) || !/<\/html>/i.test(html) ||
      Buffer.byteLength(html) > 2097152) throw new Error(`invalid snapshot HTML: ${date}`);
  return { date, html, sha256: createHash("sha256").update(html).digest("hex") };
}

export function readRun(dir) {
  const status = JSON.parse(fs.readFileSync(path.join(dir, "shadow-status.json"), "utf8"));
  const reportBytes = fs.readFileSync(path.join(dir, "report.json"));
  const report = JSON.parse(reportBytes);
  if (status.collector_exit_code !== 0 || status.error_count !== 0 ||
      status.missing_items?.length || report.errors?.length) throw new Error(`invalid run: ${dir}`);
  // Relocate a backed-up run by basename, never follow the original absolute path.
  const snapshot = path.join(dir, path.basename(status.snapshot_path));
  if (fs.realpathSync(path.dirname(snapshot)) !== fs.realpathSync(dir) ||
      fs.lstatSync(snapshot).isSymbolicLink()) throw new Error("snapshot must be a local regular file");
  const row = artifact(String(report.generatedAt || "").slice(0, 10), fs.readFileSync(snapshot, "utf8"));
  if (row.date !== path.basename(dir) || row.sha256 !== status.snapshot_sha256 ||
      createHash("sha256").update(reportBytes).digest("hex") !== status.report_sha256) {
    throw new Error(`run date/hash mismatch: ${dir}`);
  }
  return row;
}

export function inventory({ run, archive, staticRoot }) {
  const rows = new Map();
  const add = (row) => {
    if (rows.has(row.date) && rows.get(row.date).sha256 !== row.sha256) {
      throw new Error(`conflicting snapshot: ${row.date}`);
    }
    rows.set(row.date, row);
  };
  if (staticRoot) {
    for (const dir of fs.readdirSync(staticRoot).sort().filter(validPriceDate)) {
      add(artifact(dir, fs.readFileSync(path.join(staticRoot, dir, "index.html"), "utf8")));
    }
  }
  if (archive) {
    for (const dir of fs.readdirSync(archive).sort().filter(validPriceDate)) {
      add(readRun(path.join(archive, dir)));
    }
  }
  if (run) add(readRun(run));
  if (!rows.size) throw new Error("no snapshots found");
  return [...rows.values()].sort((a, b) => a.date.localeCompare(b.date));
}

export async function publishArtifact(row, { url, key, fetchImpl = fetch }) {
  if (!url || !key) throw new Error("missing Supabase URL or producer credential");
  const endpoint = new URL("/rest/v1/price_snapshot_artifacts", url);
  const headers = { apikey: key, Authorization: `Bearer ${key}` };
  // An existing date is immutable: retries are safe, conflicting bytes fail closed.
  const saved = await fetchImpl(endpoint, {
    method: "POST", headers: { ...headers, "Content-Type": "application/json",
      Prefer: "resolution=ignore-duplicates,return=minimal" },
    body: JSON.stringify(row), signal: AbortSignal.timeout(15000),
  });
  if (!saved.ok) throw new Error(`artifact save failed: HTTP ${saved.status}`);
  endpoint.searchParams.set("date", `eq.${row.date}`);
  endpoint.searchParams.set("select", "date,html,sha256");
  const check = await fetchImpl(endpoint, { headers, cache: "no-store", signal: AbortSignal.timeout(15000) });
  if (!check.ok) throw new Error(`artifact readback failed: HTTP ${check.status}`);
  const rows = await check.json();
  if (rows.length !== 1 || rows[0].date !== row.date || rows[0].sha256 !== row.sha256 ||
      rows[0].html !== row.html) throw new Error(`artifact conflict/readback mismatch: ${row.date}`);
}

async function main(args) {
  const options = {};
  let publish = false;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--publish") { publish = true; continue; }
    const key = { "--run": "run", "--archive": "archive", "--static-root": "staticRoot" }[args[i]];
    if (!key || !args[i + 1] || args[i + 1].startsWith("--")) {
      throw new Error("usage: price-artifacts.mjs [--run DIR | --archive DIR] [--static-root DIR] [--publish]");
    }
    options[key] = args[++i];
  }
  const rows = inventory(options); // Validate the whole batch before the first write.
  for (const row of rows) {
    if (publish) await publishArtifact(row, {
      url: process.env.NEXT_PUBLIC_SUPABASE_URL, key: process.env.SUPABASE_SERVICE_ROLE_KEY,
    });
    console.log(`${publish ? "saved" : "validated"} ${row.date} ${row.sha256}`);
  }
  console.log(`${rows.length} snapshots; ${publish ? "readback verified" : "dry-run: no writes"}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  main(process.argv.slice(2)).catch((error) => { console.error(error.message); process.exitCode = 1; });
}
