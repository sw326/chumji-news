import http from 'node:http';
import crypto from 'node:crypto';
import { URL } from 'node:url';

const MAX_BODY = 64 * 1024;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function securityHeaders(res) {
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  res.setHeader('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
}

function sendJson(res, status, value) {
  securityHeaders(res);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(value));
}

function sendHtml(res, status, body) {
  securityHeaders(res);
  res.writeHead(status, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(`<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>보안 입력</title><style>
    body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f4f5f7;color:#17191c;margin:0;padding:24px}.card{max-width:520px;margin:5vh auto;background:white;border-radius:18px;padding:24px;box-shadow:0 8px 32px #0001}h1{font-size:22px;margin:0 0 8px}.meta{color:#5d6470;font-size:14px;line-height:1.55}.field{margin-top:18px}label{font-weight:650;display:block;margin-bottom:7px}input{box-sizing:border-box;width:100%;padding:12px;border:1px solid #c9ced6;border-radius:10px;font-size:16px}small{display:block;color:#69717d;margin-top:6px}button{width:100%;margin-top:22px;border:0;border-radius:11px;background:#1769e0;color:white;padding:13px;font-size:16px;font-weight:700}.warn{background:#fff7e6;border-radius:10px;padding:10px;margin-top:16px;font-size:13px}.error{color:#b42318}</style></head><body>${body}</body></html>`);
}

function parseCookies(req) {
  const out = {};
  for (const part of String(req.headers.cookie ?? '').split(';')) {
    const index = part.indexOf('=');
    if (index > 0) out[part.slice(0, index).trim()] = decodeURIComponent(part.slice(index + 1));
  }
  return out;
}

async function readBody(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) throw new Error('request body too large');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8');
}

function formPage(request, error = '') {
  const fields = request.schema.fields.map((field) => {
    const type = ['secret', 'token', 'password'].includes(field.kind) ? 'password' : 'text';
    const autocomplete = field.autocomplete ?? (field.kind === 'username' ? 'username' : field.kind === 'password' ? 'current-password' : 'off');
    return `<div class="field"><label for="${escapeHtml(field.name)}">${escapeHtml(field.label)}</label><input id="${escapeHtml(field.name)}" name="${escapeHtml(field.name)}" type="${type}" autocomplete="${escapeHtml(autocomplete)}" minlength="${field.minLength}" maxlength="${field.maxLength}" ${field.required ? 'required' : ''}>${field.help ? `<small>${escapeHtml(field.help)}</small>` : ''}</div>`;
  }).join('');
  const scope = request.allowedDomains.length ? request.allowedDomains.map(escapeHtml).join(', ') : '요청된 작업에만 사용';
  const ownerChallenge = request.ownerVerification === 'telegram_dm_code'
    ? '<div class="field"><label for="_owner_code">Telegram DM 확인 코드</label><input id="_owner_code" name="_owner_code" type="text" inputmode="numeric" autocomplete="one-time-code" minlength="8" maxlength="8" required><small>Owner 개인 DM으로 전송된 8자리 코드를 입력하세요.</small></div>' : '';
  return `<main class="card"><h1>보안 정보 입력</h1><div class="meta">용도: ${escapeHtml(request.purpose)}<br>요청 Agent: ${escapeHtml(request.requesterAgent)}<br>허용 대상: ${scope}</div><div class="warn">입력값은 채팅과 Agent 응답에 표시되지 않습니다. 제출 후에는 참조 ID만 반환됩니다.</div>${error ? `<p class="error">${escapeHtml(error)}</p>` : ''}<form method="post" action="/enter"><input type="hidden" name="_csrf" value="${escapeHtml(request.csrf)}">${ownerChallenge}${fields}<button type="submit">안전하게 저장</button></form></main>`;
}

function successPage() {
  return '<main class="card"><h1>입력이 완료되었습니다</h1><p class="meta">이 창을 닫아도 됩니다. 원래 작업이 저장 완료 상태를 확인하고 이어서 진행합니다.</p></main>';
}

function errorPage(message) {
  return `<main class="card"><h1>요청을 처리할 수 없습니다</h1><p class="error">${escapeHtml(message)}</p></main>`;
}

function bearerMatches(req, expected) {
  const header = String(req.headers.authorization ?? '');
  if (!expected) return false;
  const supplied = Buffer.from(header);
  const wanted = Buffer.from(`Bearer ${expected}`);
  return supplied.length === wanted.length && crypto.timingSafeEqual(supplied, wanted);
}

function createRateLimiter({ limit, windowMs, now = () => Date.now() }) {
  const buckets = new Map();
  return (key) => {
    const timestamp = now();
    const current = buckets.get(key);
    if (!current || current.resetAt <= timestamp) {
      buckets.set(key, { count: 1, resetAt: timestamp + windowMs });
      return true;
    }
    current.count += 1;
    return current.count <= limit;
  };
}

export function createSecretHandoffServer({ vault, publicBaseUrl, controlToken, secureCookie = true, trustProxy = false, deliverOwnerChallenge = null }) {
  const base = new URL(publicBaseUrl);
  if (secureCookie && base.protocol !== 'https:') throw new Error('publicBaseUrl must use HTTPS when secureCookie is enabled');
  const cookieName = secureCookie ? '__Host-secret_handoff' : 'secret_handoff_dev';
  const allowTokenExchange = createRateLimiter({ limit: 10, windowMs: 15 * 60 * 1000 });
  const allowSubmission = createRateLimiter({ limit: 5, windowMs: 15 * 60 * 1000 });
  const clientAddress = (req) => trustProxy
    ? String(req.headers['x-forwarded-for'] ?? '').split(',')[0].trim() || req.socket.remoteAddress
    : req.socket.remoteAddress;
  return http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, base);
      if (req.method === 'POST' && url.pathname === '/api/v1/requests') {
        if (!bearerMatches(req, controlToken)) return sendJson(res, 401, { error: 'unauthorized' });
        const spec = JSON.parse(await readBody(req));
        const created = vault.createRequest(spec);
        if (created.ownerVerification === 'telegram_dm_code') {
          if (typeof deliverOwnerChallenge !== 'function') {
            vault.cancelRequest(created.id);
            throw new Error('owner challenge delivery is unavailable');
          }
          try {
            await deliverOwnerChallenge({
              ownerId: spec.ownerId,
              requestId: created.id,
              purpose: spec.purpose,
              expiresAt: created.expiresAt,
              code: created.ownerCode,
            });
          } catch (error) {
            vault.cancelRequest(created.id);
            throw new Error('owner challenge delivery failed');
          }
        }
        const entryUrl = new URL(`/enter?token=${encodeURIComponent(created.token)}`, base).toString();
        return sendJson(res, 201, {
          requestId: created.id,
          entryUrl,
          expiresAt: new Date(created.expiresAt).toISOString(),
          ownerVerification: created.ownerVerification,
          controlCard: {
            state: 'needs_auth',
            title: '보안 입력 필요',
            purpose: spec.purpose,
            requesterAgent: spec.requesterAgent,
            allowedDomains: spec.allowedDomains ?? [],
            actions: [
              { id: 'open_secret_form', label: '보안 입력', kind: 'url', url: entryUrl },
              { id: 'cancel_secret_handoff', label: '취소', kind: 'callback', requestId: created.id },
            ],
          },
        });
      }
      const statusMatch = /^\/api\/v1\/requests\/([^/]+)\/status$/.exec(url.pathname);
      if (req.method === 'GET' && statusMatch) {
        if (!bearerMatches(req, controlToken)) return sendJson(res, 401, { error: 'unauthorized' });
        const status = vault.requestStatus(decodeURIComponent(statusMatch[1]));
        return status ? sendJson(res, 200, status) : sendJson(res, 404, { error: 'not_found' });
      }
      const cancelMatch = /^\/api\/v1\/requests\/([^/]+)\/cancel$/.exec(url.pathname);
      if (req.method === 'POST' && cancelMatch) {
        if (!bearerMatches(req, controlToken)) return sendJson(res, 401, { error: 'unauthorized' });
        return sendJson(res, vault.cancelRequest(decodeURIComponent(cancelMatch[1])) ? 200 : 409, { status: 'cancelled' });
      }
      const revokeMatch = /^\/api\/v1\/credentials\/([^/]+)\/revoke$/.exec(url.pathname);
      if (req.method === 'POST' && revokeMatch) {
        if (!bearerMatches(req, controlToken)) return sendJson(res, 401, { error: 'unauthorized' });
        return sendJson(res, vault.revokeCredential(decodeURIComponent(revokeMatch[1])) ? 200 : 404, { status: 'revoked' });
      }
      if (req.method === 'GET' && url.pathname === '/enter' && url.searchParams.has('token')) {
        if (!allowTokenExchange(`exchange:${clientAddress(req)}`)) return sendHtml(res, 429, errorPage('잠시 후 다시 시도해 주세요.'));
        const { session, request } = vault.exchangeToken(url.searchParams.get('token'));
        const remainingSeconds = Math.max(1, Math.min(900, Math.floor((request.expiresAt - Date.now()) / 1000)));
        const flags = [`${cookieName}=${encodeURIComponent(session)}`, 'Path=/', 'HttpOnly', 'SameSite=Strict', `Max-Age=${remainingSeconds}`];
        if (secureCookie) flags.push('Secure');
        securityHeaders(res);
        res.writeHead(303, { Location: '/enter', 'Set-Cookie': flags.join('; ') });
        return res.end();
      }
      if (req.method === 'GET' && url.pathname === '/enter') {
        const session = parseCookies(req)[cookieName];
        if (!session) return sendHtml(res, 400, errorPage('유효한 보안 입력 세션이 없습니다.'));
        return sendHtml(res, 200, formPage(vault.requestForSession(session)));
      }
      if (req.method === 'POST' && url.pathname === '/enter') {
        if (!allowSubmission(`submit:${clientAddress(req)}`)) return sendHtml(res, 429, errorPage('입력 시도 횟수를 초과했습니다. 잠시 후 다시 시도해 주세요.'));
        const session = parseCookies(req)[cookieName];
        if (!session) return sendHtml(res, 400, errorPage('유효한 보안 입력 세션이 없습니다.'));
        const params = new URLSearchParams(await readBody(req));
        const request = vault.requestForSession(session);
        const values = {};
        for (const field of request.schema.fields) if (params.has(field.name)) values[field.name] = params.get(field.name);
        try {
          vault.complete(session, params.get('_csrf'), values, params.get('_owner_code'));
        } catch (error) {
          return sendHtml(res, 400, formPage(request, error.message));
        }
        securityHeaders(res);
        res.setHeader('Set-Cookie', `${cookieName}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0${secureCookie ? '; Secure' : ''}`);
        return sendHtml(res, 200, successPage());
      }
      return sendJson(res, 404, { error: 'not_found' });
    } catch (error) {
      const status = /invalid|expired|must|required|unsupported|unexpected|length|too large|JSON/.test(error.message) ? 400 : 500;
      if (req.url?.startsWith('/enter')) return sendHtml(res, status, errorPage(status === 500 ? '내부 오류가 발생했습니다.' : error.message));
      return sendJson(res, status, { error: status === 500 ? 'internal_error' : error.message });
    }
  });
}
