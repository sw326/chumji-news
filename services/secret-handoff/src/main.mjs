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

function loadMasterKey(spec) {
  let encoded;
  if (spec.provider === 'keychain') {
    const result = spawnSync('/usr/bin/security', [
      'find-generic-password', '-s', spec.service, '-a', spec.account, '-w',
    ], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    if (result.status !== 0) throw new Error('unable to load master key from macOS Keychain');
    encoded = result.stdout.trim();
  } else if (spec.provider === 'file') {
    const linkStat = fs.lstatSync(spec.path);
    if (!linkStat.isFile() || linkStat.isSymbolicLink()) throw new Error('master key path must be a regular file, not a symlink');
    const stat = fs.statSync(spec.path);
    if ((stat.mode & 0o077) !== 0) throw new Error('master key file must not be accessible by group or others');
    if (typeof process.getuid === 'function' && stat.uid !== process.getuid()) throw new Error('master key file must be owned by the service user');
    encoded = fs.readFileSync(spec.path, 'utf8').trim();
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

const command = process.argv[2];
const config = loadConfig();
process.umask(0o077);
const vault = new SecretVault({ dbPath: config.dbPath, masterKey: loadMasterKey(config.masterKey) });

if (command === 'serve') {
  const controlToken = process.env[config.controlTokenEnv];
  if (!controlToken) throw new Error(`missing control token environment variable: ${config.controlTokenEnv}`);
  const server = createSecretHandoffServer({
    vault,
    publicBaseUrl: config.publicBaseUrl,
    controlToken,
    secureCookie: config.secureCookie !== false,
    trustProxy: config.trustProxy === true,
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
