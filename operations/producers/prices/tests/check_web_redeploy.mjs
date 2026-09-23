#!/usr/bin/env node
// Integration check against a local REST fixture, never the production database.
// Usage: node .../check_web_redeploy.mjs ARCHIVE_ROOT
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { inventory } from '../../../../scripts/price-artifacts.mjs';

const rows = inventory({ archive: process.argv[2], staticRoot: 'public/fresh-food' });
let dbDown = false;
const db = http.createServer((request, response) => {
  if (dbDown) { response.writeHead(503); response.end(); return; }
  const url = new URL(request.url, 'http://localhost');
  if (request.method !== 'GET') { response.writeHead(405); response.end(); return; }
  let found = rows;
  if (url.searchParams.has('date')) found = rows.filter(row => `eq.${row.date}` === url.searchParams.get('date'));
  if (url.searchParams.get('order') === 'date.desc') found = rows.slice().reverse();
  response.setHeader('Content-Type', 'application/json');
  response.end(JSON.stringify(found.slice(0, 1)));
});
await new Promise(resolve => db.listen(0, '127.0.0.1', resolve));
const env = { ...process.env, NEXT_PUBLIC_SUPABASE_URL: `http://127.0.0.1:${db.address().port}`,
  NEXT_PUBLIC_SUPABASE_ANON_KEY: 'offline-fixture-no-credential', NEXT_TELEMETRY_DISABLED: '1' };
let app;
async function stopApp() {
  if (app && app.exitCode === null) { app.kill('SIGTERM'); await once(app, 'exit'); }
  app = null;
}
try {
  for (let build = 1; build <= 2; build++) {
    const builder = spawn('npm', ['run', 'build'], { env, stdio: 'inherit' });
    const [code] = await once(builder, 'exit');
    assert.equal(code, 0, 'build failed');
    app = spawn(process.execPath, ['node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '0'], { env });
    let output = '';
    const base = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('server start timeout')), 30000);
      app.on('exit', code => { clearTimeout(timeout); reject(new Error(`server exited ${code}: ${output}`)); });
      const onData = chunk => {
        output += chunk;
        const match = output.match(/http:\/\/127\.0\.0\.1:\d+/);
        if (match && output.includes('Ready')) { clearTimeout(timeout); resolve(match[0]); }
      };
      app.stdout.on('data', onData); app.stderr.on('data', onData);
    });
    for (const row of rows) {
      const response = await fetch(`${base}/fresh-food/${row.date}/index.html`, { redirect: 'error' });
      assert.equal(response.status, 200, `${build}: ${row.date}`);
      assert.equal(await response.text(), row.html, `bytes differ: ${row.date}`);
    }
    const latest = await fetch(`${base}/fresh-food/index.html`, { redirect: 'error' });
    assert.equal(latest.status, 200);
    assert.equal(await latest.text(), rows.at(-1).html);
    for (const date of ['2026-02-30', '2099-01-01']) {
      assert.equal((await fetch(`${base}/fresh-food/${date}/index.html`)).status, 404);
    }
    dbDown = true;
    assert.equal((await fetch(`${base}/fresh-food/${rows.at(-1).date}/index.html`)).status, 503);
    dbDown = false;
    assert.equal((await fetch(`${base}/fresh-food/${rows.at(-1).date}/index.html`)).status, 200);
    console.log(`BUILD ${build}: ${rows.length} dated graphs byte-identical; latest/missing/failure/recovery passed`);
    await stopApp();
  }
} finally {
  await stopApp();
  db.closeAllConnections();
  await new Promise(resolve => db.close(resolve));
}
