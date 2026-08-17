import crypto from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';

const FIELD_KINDS = new Set(['secret', 'token', 'username', 'password', 'text']);
const RETENTIONS = new Set(['persistent', 'session', 'one_time']);
const NAME_RE = /^[a-z][a-z0-9_]{0,47}$/;

function b64url(bytes = 24) {
  return crypto.randomBytes(bytes).toString('base64url');
}

function sha256(value) {
  return crypto.createHash('sha256').update(value, 'utf8').digest('hex');
}

function safeJson(value) {
  return JSON.stringify(value);
}

function assertString(value, name, max = 200) {
  if (typeof value !== 'string' || value.length === 0 || value.length > max) {
    throw new Error(`${name} must be a non-empty string up to ${max} characters`);
  }
  return value;
}

export function normalizeSchema(input) {
  if (!input || !Array.isArray(input.fields) || input.fields.length < 1 || input.fields.length > 10) {
    throw new Error('schema.fields must contain 1 to 10 fields');
  }
  const names = new Set();
  const fields = input.fields.map((field) => {
    const name = assertString(field.name, 'field.name', 48);
    if (!NAME_RE.test(name) || names.has(name)) throw new Error(`invalid or duplicate field name: ${name}`);
    names.add(name);
    const kind = field.kind ?? 'secret';
    if (!FIELD_KINDS.has(kind)) throw new Error(`unsupported field kind: ${kind}`);
    const minLength = Number.isInteger(field.minLength) ? field.minLength : 1;
    const maxLength = Number.isInteger(field.maxLength) ? field.maxLength : 4096;
    if (minLength < 0 || maxLength < 1 || maxLength > 16384 || minLength > maxLength) {
      throw new Error(`invalid length bounds for ${name}`);
    }
    return {
      name,
      label: assertString(field.label ?? name, 'field.label', 80),
      kind,
      required: field.required !== false,
      minLength,
      maxLength,
      autocomplete: typeof field.autocomplete === 'string' && field.autocomplete.length <= 80
        ? field.autocomplete : undefined,
      help: typeof field.help === 'string' && field.help.length <= 160 ? field.help : undefined,
    };
  });
  return { fields };
}

function validateValues(schema, values) {
  if (!values || typeof values !== 'object' || Array.isArray(values)) throw new Error('values must be an object');
  const allowed = new Set(schema.fields.map((field) => field.name));
  for (const key of Object.keys(values)) if (!allowed.has(key)) throw new Error(`unexpected field: ${key}`);
  const normalized = {};
  for (const field of schema.fields) {
    const value = values[field.name];
    if ((value === undefined || value === '') && !field.required) continue;
    if (typeof value !== 'string') throw new Error(`${field.label} is required`);
    if (value.length < field.minLength || value.length > field.maxLength) {
      throw new Error(`${field.label} has an invalid length`);
    }
    normalized[field.name] = value;
  }
  return normalized;
}

function encryptJson(key, value, aad) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);
  cipher.setAAD(Buffer.from(aad));
  const encrypted = Buffer.concat([cipher.update(safeJson(value), 'utf8'), cipher.final()]);
  return safeJson({
    v: 1,
    iv: iv.toString('base64'),
    tag: cipher.getAuthTag().toString('base64'),
    data: encrypted.toString('base64'),
  });
}

function decryptJson(key, envelope, aad) {
  const parsed = JSON.parse(envelope);
  if (parsed.v !== 1) throw new Error('unsupported encrypted payload version');
  const decipher = crypto.createDecipheriv('aes-256-gcm', key, Buffer.from(parsed.iv, 'base64'));
  decipher.setAAD(Buffer.from(aad));
  decipher.setAuthTag(Buffer.from(parsed.tag, 'base64'));
  const clear = Buffer.concat([
    decipher.update(Buffer.from(parsed.data, 'base64')),
    decipher.final(),
  ]);
  return JSON.parse(clear.toString('utf8'));
}

export class SecretVault {
  constructor({ dbPath = ':memory:', masterKey, now = () => Date.now() }) {
    if (!Buffer.isBuffer(masterKey) || masterKey.length !== 32) throw new Error('masterKey must be 32 bytes');
    this.encryptionKey = Buffer.from(crypto.hkdfSync('sha256', masterKey, Buffer.alloc(0), 'secret-handoff/encryption/v1', 32));
    this.csrfKey = Buffer.from(crypto.hkdfSync('sha256', masterKey, Buffer.alloc(0), 'secret-handoff/csrf/v1', 32));
    this.now = now;
    this.db = new DatabaseSync(dbPath);
    this.db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON;');
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS handoff_requests (
        id TEXT PRIMARY KEY,
        token_hash TEXT UNIQUE NOT NULL,
        session_hash TEXT UNIQUE,
        owner_id TEXT NOT NULL,
        requester_agent TEXT NOT NULL,
        purpose TEXT NOT NULL,
        allowed_domains TEXT NOT NULL,
        schema_json TEXT NOT NULL,
        retention TEXT NOT NULL,
        expires_at INTEGER NOT NULL,
        secret_expires_at INTEGER,
        exchanged_at INTEGER,
        completed_at INTEGER,
        cancelled_at INTEGER,
        credential_id TEXT
      );
      CREATE TABLE IF NOT EXISTS credentials (
        id TEXT PRIMARY KEY,
        owner_id TEXT NOT NULL,
        requester_agent TEXT NOT NULL,
        purpose TEXT NOT NULL,
        allowed_domains TEXT NOT NULL,
        schema_json TEXT NOT NULL,
        retention TEXT NOT NULL,
        present_fields TEXT NOT NULL,
        encrypted_payload TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        expires_at INTEGER,
        consumed_at INTEGER,
        revoked_at INTEGER
      );
      CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_at INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        request_id TEXT,
        credential_id TEXT,
        result TEXT NOT NULL
      );
    `);
  }

  audit(eventType, { requestId = null, credentialId = null, result = 'ok' } = {}) {
    this.db.prepare(`INSERT INTO audit_events(event_at,event_type,request_id,credential_id,result)
      VALUES(?,?,?,?,?)`).run(this.now(), eventType, requestId, credentialId, result);
  }

  createRequest(spec) {
    const schema = normalizeSchema(spec.schema);
    const retention = spec.retention ?? 'persistent';
    if (!RETENTIONS.has(retention)) throw new Error('invalid retention');
    const ttlSeconds = Number.isInteger(spec.ttlSeconds) ? spec.ttlSeconds : 900;
    if (ttlSeconds < 60 || ttlSeconds > 3600) throw new Error('ttlSeconds must be between 60 and 3600');
    const secretTtlSeconds = spec.secretTtlSeconds;
    if (retention === 'session' && (!Number.isInteger(secretTtlSeconds) || secretTtlSeconds < 60)) {
      throw new Error('session retention requires secretTtlSeconds >= 60');
    }
    const ownerId = assertString(spec.ownerId, 'ownerId', 100);
    const requesterAgent = assertString(spec.requesterAgent, 'requesterAgent', 100);
    const purpose = assertString(spec.purpose, 'purpose', 300);
    const allowedDomains = Array.isArray(spec.allowedDomains)
      ? spec.allowedDomains.map((domain) => assertString(domain, 'allowedDomain', 253)) : [];
    const id = `req_${b64url(15)}`;
    const token = b64url(32);
    const now = this.now();
    this.db.prepare(`INSERT INTO handoff_requests(
      id,token_hash,owner_id,requester_agent,purpose,allowed_domains,schema_json,retention,
      expires_at,secret_expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)`).run(
      id, sha256(token), ownerId, requesterAgent, purpose, safeJson(allowedDomains), safeJson(schema),
      retention, now + ttlSeconds * 1000,
      Number.isInteger(secretTtlSeconds) ? now + secretTtlSeconds * 1000 : null,
    );
    this.audit('request_created', { requestId: id });
    return { id, token, expiresAt: now + ttlSeconds * 1000 };
  }

  exchangeToken(token) {
    const now = this.now();
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const row = this.db.prepare('SELECT * FROM handoff_requests WHERE token_hash=?').get(sha256(token));
      if (!row || row.exchanged_at || row.completed_at || row.cancelled_at || row.expires_at <= now) {
        throw new Error('invalid or expired handoff link');
      }
      const session = b64url(32);
      this.db.prepare('UPDATE handoff_requests SET session_hash=?, exchanged_at=? WHERE id=?')
        .run(sha256(session), now, row.id);
      this.db.exec('COMMIT');
      this.audit('token_exchanged', { requestId: row.id });
      return { session, request: this.publicRequest(row) };
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  csrfForSession(session) {
    return crypto.createHmac('sha256', this.csrfKey).update(`csrf:${session}`).digest('base64url');
  }

  requestForSession(session) {
    const row = this.db.prepare('SELECT * FROM handoff_requests WHERE session_hash=?').get(sha256(session));
    if (!row || row.completed_at || row.cancelled_at || row.expires_at <= this.now()) {
      throw new Error('invalid or expired handoff session');
    }
    return { ...this.publicRequest(row), csrf: this.csrfForSession(session) };
  }

  publicRequest(row) {
    return {
      id: row.id,
      ownerId: row.owner_id,
      requesterAgent: row.requester_agent,
      purpose: row.purpose,
      allowedDomains: JSON.parse(row.allowed_domains),
      schema: JSON.parse(row.schema_json),
      retention: row.retention,
      expiresAt: row.expires_at,
    };
  }

  complete(session, csrf, values) {
    const expectedCsrf = this.csrfForSession(session);
    const provided = Buffer.from(String(csrf ?? ''));
    const expected = Buffer.from(expectedCsrf);
    if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) throw new Error('invalid CSRF token');
    const now = this.now();
    this.db.exec('BEGIN IMMEDIATE');
    try {
      const row = this.db.prepare('SELECT * FROM handoff_requests WHERE session_hash=?').get(sha256(session));
      if (!row || row.completed_at || row.cancelled_at || row.expires_at <= now) {
        throw new Error('invalid or expired handoff session');
      }
      const schema = JSON.parse(row.schema_json);
      const normalized = validateValues(schema, values);
      const credentialId = `cred_${b64url(18)}`;
      const aad = `secret-handoff:v1:${credentialId}:${row.owner_id}:${row.requester_agent}`;
      const encrypted = encryptJson(this.encryptionKey, normalized, aad);
      this.db.prepare(`INSERT INTO credentials(
        id,owner_id,requester_agent,purpose,allowed_domains,schema_json,retention,present_fields,
        encrypted_payload,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)`).run(
        credentialId, row.owner_id, row.requester_agent, row.purpose, row.allowed_domains,
        row.schema_json, row.retention, safeJson(Object.keys(normalized)), encrypted, now, row.secret_expires_at,
      );
      this.db.prepare('UPDATE handoff_requests SET completed_at=?, credential_id=?, session_hash=NULL WHERE id=?')
        .run(now, credentialId, row.id);
      this.db.exec('COMMIT');
      this.audit('secret_stored', { requestId: row.id, credentialId });
      return { requestId: row.id, credentialId };
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  requestStatus(id) {
    const row = this.db.prepare('SELECT * FROM handoff_requests WHERE id=?').get(id);
    if (!row) return null;
    let status = 'pending';
    if (row.cancelled_at) status = 'cancelled';
    else if (row.completed_at) status = 'completed';
    else if (row.expires_at <= this.now()) status = 'expired';
    else if (row.exchanged_at) status = 'opened';
    const refs = {};
    if (row.credential_id) {
      const credential = this.db.prepare('SELECT present_fields FROM credentials WHERE id=?').get(row.credential_id);
      const present = new Set(credential ? JSON.parse(credential.present_fields) : []);
      for (const field of JSON.parse(row.schema_json).fields) {
        if (!present.has(field.name)) continue;
        refs[field.name] = {
          source: 'exec',
          provider: 'secret-handoff',
          id: `${row.credential_id}/${field.name}`,
        };
      }
    }
    return { id: row.id, status, credentialRefs: refs };
  }

  cancelRequest(id) {
    const changed = this.db.prepare(`UPDATE handoff_requests SET cancelled_at=?
      WHERE id=? AND completed_at IS NULL AND cancelled_at IS NULL`).run(this.now(), id).changes;
    if (changed) this.audit('request_cancelled', { requestId: id });
    return changed > 0;
  }

  revokeCredential(id) {
    const changed = this.db.prepare('UPDATE credentials SET revoked_at=? WHERE id=? AND revoked_at IS NULL')
      .run(this.now(), id).changes;
    if (changed) this.audit('credential_revoked', { credentialId: id });
    return changed > 0;
  }

  resolveRefs(ids) {
    if (!Array.isArray(ids) || ids.length < 1 || ids.length > 50) throw new Error('ids must contain 1 to 50 references');
    const grouped = new Map();
    for (const id of ids) {
      if (typeof id !== 'string') throw new Error('invalid credential reference');
      const match = /^(cred_[A-Za-z0-9_-]+)\/([a-z][a-z0-9_]{0,47})$/.exec(id);
      if (!match) throw new Error(`invalid credential reference: ${id}`);
      const [, credentialId, field] = match;
      if (!grouped.has(credentialId)) grouped.set(credentialId, []);
      grouped.get(credentialId).push({ id, field });
    }
    const result = {};
    const now = this.now();
    this.db.exec('BEGIN IMMEDIATE');
    try {
      for (const [credentialId, requested] of grouped) {
        const row = this.db.prepare('SELECT * FROM credentials WHERE id=?').get(credentialId);
        if (!row || row.revoked_at || (row.expires_at && row.expires_at <= now) || row.consumed_at) {
          throw new Error(`credential is unavailable: ${credentialId}`);
        }
        const aad = `secret-handoff:v1:${credentialId}:${row.owner_id}:${row.requester_agent}`;
        const values = decryptJson(this.encryptionKey, row.encrypted_payload, aad);
        for (const item of requested) {
          if (!Object.hasOwn(values, item.field)) throw new Error(`unknown credential field: ${item.field}`);
          result[item.id] = values[item.field];
        }
        if (row.retention === 'one_time') {
          this.db.prepare('UPDATE credentials SET consumed_at=? WHERE id=?').run(now, credentialId);
        }
        this.audit('credential_resolved', { credentialId });
      }
      this.db.exec('COMMIT');
      return result;
    } catch (error) {
      this.db.exec('ROLLBACK');
      throw error;
    }
  }

  close() {
    this.db.close();
  }
}
