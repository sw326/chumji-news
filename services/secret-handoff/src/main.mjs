import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { SecretVault } from './vault.mjs';
import { createSecretHandoffServer } from './server.mjs';

function argValue(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function loadConfig() {
  const path = argValue('--config');
  if (!path) throw new Error('--config is required');
  return JSON.parse(fs.readFileSync(path, 'utf8'));
}

function loadStrictFileValue(path, label) {
  const linkStat = fs.lstatSync(path);
  if (!linkStat.isFile() || linkStat.isSymbolicLink()) throw new Error(`${label} path must be a regular file, not a symlink`);
  const stat = fs.statSync(path);
  if ((stat.mode & 0o077) !== 0) throw new Error(`${label} file must not be accessible by group or others`);
  if (typeof process.getuid === 'function' && stat.uid !== process.getuid()) throw new Error(`${label} file must be owned by the service user`);
  const value = fs.readFileSync(path, 'utf8').trim();
  if (!value) throw new Error(`${label} file is empty`);
  return value;
}

function loadSecretInput(spec, legacyEnvName, label) {
  if (spec?.provider === 'file') return loadStrictFileValue(spec.path, label);
  if (spec?.provider === 'env') {
    const value = process.env[spec.name];
    if (!value) throw new Error(`missing ${label} environment variable: ${spec.name}`);
    return value;
  }
  if (legacyEnvName) {
    const value = process.env[legacyEnvName];
    if (!value) throw new Error(`missing ${label} environment variable: ${legacyEnvName}`);
    return value;
  }
  throw new Error(`unsupported ${label} provider`);
}

function loadMasterKey(spec) {
  let encoded;
  if (spec.provider === 'keychain') {
    const result = spawnSync('/usr/bin/security', [
      'find-generic-password', '-s', spec.service, '-a', spec.account, '-w',
    ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    if (result.status !== 0) throw new Error('unable to load master key from macOS Keychain');
    encoded = result.stdout.trim();
  } else if (spec.provider === 'file') {
    encoded = loadStrictFileValue(spec.path, 'master key');
  } else if (spec.provider === 'env' && process.env.NODE_ENV === 'test') {
    encoded = process.env[spec.name];
  } else {
    throw new Error('unsupported master key provider');
  }
  const key = Buffer.from(encoded, 'base64');
  if (key.length !== 32) throw new Error('master key must decode to 32 bytes');
  return key;
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString('utf8');
}

function createTelegramChallengeDeliverer(spec) {
  if (!spec) return null;
  const token = loadSecretInput(spec.botToken, spec.botTokenEnv, 'Telegram bot token');
  return async ({ ownerId, requestId, purpose, expiresAt, code }) => {
    const match = /^telegram:(\d+)$/.exec(ownerId);
    if (!match) throw new Error('invalid Telegram ownerId');
    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        chat_id: match[1],
        text: `[Secret Handoff]\n요청: ${purpose}\n확인 코드: ${code}\n요청 ID: ${requestId}\n만료: ${new Date(expiresAt).toISOString()}\n\n이 코드는 자격정보가 아니며 보안 입력 폼에서만 사용하세요.`,
        disable_web_page_preview: true,
      }),
      signal: AbortSignal.timeout(spec.timeoutMs ?? 5000),
    });
    if (!response.ok) throw new Error('Telegram challenge delivery failed');
    const result = await response.json();
    if (!result.ok) throw new Error('Telegram challenge delivery rejected');
  };
}

const command = process.argv[2];
const config = loadConfig();
process.umask(0o077);
const vault = new SecretVault({ dbPath: config.dbPath, masterKey: loadMasterKey(config.masterKey) });

if (command === 'serve') {
  const controlToken = loadSecretInput(config.controlToken, config.controlTokenEnv, 'control token');
  const server = createSecretHandoffServer({
    vault,
    publicBaseUrl: config.publicBaseUrl,
    controlToken,
    secureCookie: config.secureCookie !== false,
    trustProxy: config.trustProxy === true,
    deliverOwnerChallenge: createTelegramChallengeDeliverer(config.telegramChallenge),
  });
  server.listen(config.listen.port, config.listen.host, () => {
    process.stderr.write(`secret-handoff listening on ${config.listen.host}:${config.listen.port}\n`);
  });
} else if (command === 'resolve') {
  const input = JSON.parse(await readStdin());
  if (input.protocolVersion !== 1 || input.provider !== 'secret-handoff' || !Array.isArray(input.ids)) {
    throw new Error('invalid exec SecretRef request');
  }
  const values = vault.resolveRefs(input.ids);
  process.stdout.write(`${JSON.stringify({ protocolVersion: 1, values })}\n`);
  vault.close();
} else {
  vault.close();
  throw new Error('command must be serve or resolve');
}
