import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, test } from 'node:test';
import { SecretVault } from '../src/vault.mjs';
import { createSecretHandoffServer } from '../src/server.mjs';

let now;
let vault;
let server;
let base;

beforeEach(async () => {
  now = 1_800_000_000_000;
  vault = new SecretVault({ masterKey: Buffer.alloc(32, 7), now: () => now });
  server = createSecretHandoffServer({
    vault,
    publicBaseUrl: 'http://127.0.0.1',
    controlToken: 'test-control-token',
    secureCookie: false,
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});

afterEach(async () => {
  await new Promise((resolve) => server.close(resolve));
  vault.close();
});

async function request(path, options = {}) {
  const response = await fetch(`${base}${path}`, { redirect: 'manual', ...options });
  const text = await response.text();
  return { response, text };
}

async function create(spec) {
  const { response, text } = await request('/api/v1/requests', {
    method: 'POST',
    headers: { Authorization: 'Bearer test-control-token', 'Content-Type': 'application/json' },
    body: JSON.stringify(spec),
  });
  assert.equal(response.status, 201, text);
  return JSON.parse(text);
}

async function submitForm(created, values, ownerCode = null) {
  const entry = new URL(created.entryUrl);
  const first = await request(`${entry.pathname}${entry.search}`);
  assert.equal(first.response.status, 303);
  assert.equal(first.response.headers.get('location'), '/enter');
  const cookie = first.response.headers.get('set-cookie').split(';')[0];
  const page = await request('/enter', { headers: { Cookie: cookie } });
  assert.equal(page.response.status, 200);
  assert.ok(!page.text.includes(entry.searchParams.get('token')));
  const csrf = /name="_csrf" value="([^"]+)"/.exec(page.text)[1];
  const body = new URLSearchParams({ _csrf: csrf, ...(ownerCode ? { _owner_code: ownerCode } : {}), ...values });
  const submitted = await request('/enter', {
    method: 'POST', headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' }, body,
  });
  assert.equal(submitted.response.status, 200, submitted.text);
  return cookie;
}

const baseSpec = {
  ownerId: 'telegram:7800641846',
  requesterAgent: 'fin',
  purpose: '테스트 자격정보 등록',
  allowedDomains: ['api.example.test'],
  ttlSeconds: 900,
};

test('single API key is accepted and only a SecretRef is exposed over status API', async () => {
  const created = await create({
    ...baseSpec,
    schema: { fields: [{ name: 'api_key', label: 'API Key', kind: 'token' }] },
  });
  assert.ok(!created.entryUrl.includes('super-secret'));
  await submitForm(created, { api_key: 'super-secret' });
  const status = await request(`/api/v1/requests/${created.requestId}/status`, {
    headers: { Authorization: 'Bearer test-control-token' },
  });
  assert.equal(status.response.status, 200);
  assert.ok(!status.text.includes('super-secret'));
  const parsed = JSON.parse(status.text);
  assert.equal(parsed.status, 'completed');
  assert.equal(parsed.controlCard.state, 'completed');
  assert.equal(parsed.credentialRefs.api_key.source, 'exec');
  assert.deepEqual(vault.resolveRefs([parsed.credentialRefs.api_key.id]), {
    [parsed.credentialRefs.api_key.id]: 'super-secret',
  });
});

test('username and password schema resolves both values as one batch', async () => {
  const created = await create({
    ...baseSpec,
    schema: { fields: [
      { name: 'username', label: '아이디', kind: 'username' },
      { name: 'password', label: '비밀번호', kind: 'password', minLength: 4 },
    ] },
  });
  await submitForm(created, { username: 'user@example.test', password: 'p@ssword' });
  const status = vault.requestStatus(created.requestId);
  const ids = Object.values(status.credentialRefs).map((ref) => ref.id);
  assert.deepEqual(vault.resolveRefs(ids), {
    [status.credentialRefs.username.id]: 'user@example.test',
    [status.credentialRefs.password.id]: 'p@ssword',
  });
});

test('multi-field and optional fields are supported', async () => {
  const created = vault.createRequest({
    ...baseSpec,
    schema: { fields: [
      { name: 'client_id', label: 'Client ID', kind: 'text' },
      { name: 'client_secret', label: 'Client Secret', kind: 'secret' },
      { name: 'account', label: 'Account', kind: 'text', required: false },
    ] },
  });
  const { session } = vault.exchangeToken(created.token);
  vault.complete(session, vault.csrfForSession(session), { client_id: 'id', client_secret: 'secret' });
  const status = vault.requestStatus(created.id);
  assert.equal(Object.keys(status.credentialRefs).length, 2);
  assert.equal(status.credentialRefs.account, undefined);
  assert.deepEqual(vault.resolveRefs([
    status.credentialRefs.client_id.id,
    status.credentialRefs.client_secret.id,
  ]), {
    [status.credentialRefs.client_id.id]: 'id',
    [status.credentialRefs.client_secret.id]: 'secret',
  });
});

test('one-time credentials can be resolved exactly once', () => {
  const created = vault.createRequest({
    ...baseSpec, retention: 'one_time',
    schema: { fields: [
      { name: 'username', label: '아이디', kind: 'username' },
      { name: 'password', label: '비밀번호', kind: 'password' },
    ] },
  });
  const { session } = vault.exchangeToken(created.token);
  vault.complete(session, vault.csrfForSession(session), { username: 'one', password: 'shot' });
  const refs = vault.requestStatus(created.id).credentialRefs;
  const ids = [refs.username.id, refs.password.id];
  assert.equal(vault.resolveRefs(ids)[refs.password.id], 'shot');
  assert.throws(() => vault.resolveRefs(ids), /unavailable/);
});

test('expired links, token reuse, and invalid CSRF are rejected', () => {
  const created = vault.createRequest({
    ...baseSpec,
    schema: { fields: [{ name: 'key', label: 'Key', kind: 'secret' }] },
  });
  const { session } = vault.exchangeToken(created.token);
  assert.throws(() => vault.exchangeToken(created.token), /invalid or expired/);
  assert.throws(() => vault.complete(session, 'wrong', { key: 'value' }), /CSRF/);
  now += 901_000;
  assert.throws(() => vault.requestForSession(session), /invalid or expired/);
});

test('session credentials expire', () => {
  const created = vault.createRequest({
    ...baseSpec, retention: 'session', secretTtlSeconds: 120,
    schema: { fields: [{ name: 'key', label: 'Key', kind: 'secret' }] },
  });
  const { session } = vault.exchangeToken(created.token);
  const complete = vault.complete(session, vault.csrfForSession(session), { key: 'value' });
  const id = vault.requestStatus(created.id).credentialRefs.key.id;
  assert.equal(vault.resolveRefs([id])[id], 'value');
  now += 121_000;
  assert.throws(() => vault.resolveRefs([id]), /unavailable/);
});

test('revoked credentials cannot resolve', () => {
  const created = vault.createRequest({
    ...baseSpec,
    schema: { fields: [{ name: 'key', label: 'Key', kind: 'secret' }] },
  });
  const { session } = vault.exchangeToken(created.token);
  const complete = vault.complete(session, vault.csrfForSession(session), { key: 'value' });
  const id = vault.requestStatus(created.id).credentialRefs.key.id;
  vault.revokeCredential(complete.credentialId);
  assert.throws(() => vault.resolveRefs([id]), /unavailable/);
});

test('form submissions are rate-limited without logging submitted values', async () => {
  const created = await create({
    ...baseSpec,
    schema: { fields: [{ name: 'key', label: 'Key', kind: 'secret' }] },
  });
  const entry = new URL(created.entryUrl);
  const first = await request(`${entry.pathname}${entry.search}`);
  const cookie = first.response.headers.get('set-cookie').split(';')[0];
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const response = await request('/enter', {
      method: 'POST',
      headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ _csrf: 'invalid', key: `never-log-${attempt}` }),
    });
    assert.equal(response.response.status, 400);
    assert.ok(!response.text.includes(`never-log-${attempt}`));
  }
  const limited = await request('/enter', {
    method: 'POST',
    headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ _csrf: 'invalid', key: 'never-log-final' }),
  });
  assert.equal(limited.response.status, 429);
  assert.ok(!limited.text.includes('never-log-final'));
});

test('Telegram owner challenge is delivered out-of-band and required by the form', async () => {
  await new Promise((resolve) => server.close(resolve));
  let delivered;
  server = createSecretHandoffServer({
    vault,
    publicBaseUrl: 'http://127.0.0.1',
    controlToken: 'test-control-token',
    secureCookie: false,
    deliverOwnerChallenge: async (challenge) => { delivered = challenge; },
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
  const created = await create({
    ...baseSpec,
    ownerVerification: 'telegram_dm_code',
    schema: { fields: [{ name: 'key', label: 'Key', kind: 'secret' }] },
  });
  assert.equal(created.ownerVerification, 'telegram_dm_code');
  assert.equal(created.ownerCode, undefined);
  assert.equal(delivered.ownerId, baseSpec.ownerId);
  assert.match(delivered.code, /^\d{8}$/);
  assert.equal(created.controlCard.state, 'needs_auth');
  assert.equal(created.controlCard.actions[0].kind, 'url');
  const entry = new URL(created.entryUrl);
  const first = await request(`${entry.pathname}${entry.search}`);
  const cookie = first.response.headers.get('set-cookie').split(';')[0];
  const page = await request('/enter', { headers: { Cookie: cookie } });
  const csrf = /name="_csrf" value="([^"]+)"/.exec(page.text)[1];
  const wrongOwnerCode = delivered.code === '00000000' ? '11111111' : '00000000';
  const wrong = await request('/enter', {
    method: 'POST',
    headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ _csrf: csrf, _owner_code: wrongOwnerCode, key: 'never-store-this' }),
  });
  assert.equal(wrong.response.status, 400);
  assert.ok(!wrong.text.includes('never-store-this'));
  assert.equal(vault.requestStatus(created.requestId).status, 'opened');
  const accepted = await request('/enter', {
    method: 'POST',
    headers: { Cookie: cookie, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ _csrf: csrf, _owner_code: delivered.code, key: 'owner-bound-secret' }),
  });
  assert.equal(accepted.response.status, 200);
  const status = vault.requestStatus(created.requestId);
  assert.equal(status.status, 'completed');
});

test('resolver CLI implements the OpenClaw exec SecretRef JSON protocol', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'secret-handoff-test-'));
  try {
    const dbPath = path.join(tempDir, 'vault.sqlite3');
    const keyPath = path.join(tempDir, 'master-key');
    const configPath = path.join(tempDir, 'config.json');
    const masterKey = Buffer.alloc(32, 11);
    fs.writeFileSync(keyPath, masterKey.toString('base64'), { mode: 0o600 });
    fs.writeFileSync(configPath, JSON.stringify({
      dbPath,
      masterKey: { provider: 'file', path: keyPath },
    }), { mode: 0o600 });
    const persistent = new SecretVault({ dbPath, masterKey });
    const created = persistent.createRequest({
      ...baseSpec,
      schema: { fields: [
        { name: 'username', label: '아이디', kind: 'username' },
        { name: 'password', label: '비밀번호', kind: 'password' },
      ] },
    });
    const { session } = persistent.exchangeToken(created.token);
    persistent.complete(session, persistent.csrfForSession(session), { username: 'exec-user', password: 'exec-password' });
    const refs = persistent.requestStatus(created.id).credentialRefs;
    persistent.close();
    const ids = [refs.username.id, refs.password.id];
    const result = spawnSync(process.execPath, [
      path.resolve('src/main.mjs'), 'resolve', '--config', configPath,
    ], {
      cwd: path.resolve('.'),
      encoding: 'utf8',
      input: JSON.stringify({ protocolVersion: 1, provider: 'secret-handoff', ids }),
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.deepEqual(JSON.parse(result.stdout), {
      protocolVersion: 1,
      values: {
        [refs.username.id]: 'exec-user',
        [refs.password.id]: 'exec-password',
      },
    });
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
});
