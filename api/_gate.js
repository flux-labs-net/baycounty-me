// API keys, throttles and request logging for /api/v1 and /api/mcp.
// Every request is checked by apiadmin.check_request (one database call) and logged to apiadmin.requests.
// Keys can be sent as `Authorization: Bearer <key>`, an `X-API-Key` header, or `?api_key=`.
// If the database can't be reached the API stays up with a per-instance limit and nothing is logged.
const crypto = require('crypto');
const {q} = require('./_db');

const derive = label => crypto.createHmac('sha256', process.env.ALERTS_SECRET || 'baycounty.me').update(label).digest();
const sha256 = s => crypto.createHash('sha256').update(s).digest('hex');
const ipOf = req => String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'unknown';
const ipHash = req => crypto.createHmac('sha256', derive('bcm-ip-v1')).update(ipOf(req)).digest('hex').slice(0, 24);

function keyFrom(req) {
  const h = req.headers || {};
  let k = h['x-api-key'];
  const auth = String(h.authorization || '');
  if (!k && /^Bearer\s+/i.test(auth)) k = auth.replace(/^Bearer\s+/i, '');
  if (!k && req.query && req.query.api_key) k = Array.isArray(req.query.api_key) ? req.query.api_key[0] : req.query.api_key;
  k = String(k || '').trim();
  return k || null;
}

const MESSAGES = {
  invalid_key: 'That API key isn’t valid. Check it, or leave it off to use the free, keyless limits.',
  key_required: 'An API key is required. Request one at https://baycounty.me/about#contact.',
  key_disabled: 'This API key is paused. Contact BayCounty.me to turn it back on.',
  key_revoked: 'This API key has been revoked.',
  key_expired: 'This API key has expired.',
  rate_limited: 'Too many requests this minute. Slow down, or download /downloads/<id>.json for bulk use.',
  daily_quota: 'This key has used its daily request allowance. It resets at midnight Central time.',
};

const fallback = new Map();
function memLimit(h) {
  const now = Date.now(), rec = (fallback.get(h) || []).filter(t => now - t < 60e3);
  rec.push(now); fallback.set(h, rec);
  return rec.length > 120 ? {ok: false, status: 429, reason: 'rate_limited', retry_after: 60} : {ok: true};
}

// Returns a context with .ok, .status, .message and .log(fields). Sets rate-limit headers on res.
async function gate(req, res, surface) {
  const t0 = Date.now(), key = keyFrom(req), ih = ipHash(req);
  let r, offline = false;
  try {
    r = (await q('select apiadmin.check_request($1, $2) as r', [key ? sha256(key) : null, ih]))[0].r;
  } catch (e) {
    console.error('gate: database unavailable', e.message);
    offline = true;
    r = memLimit(ih);
  }
  if (r.limit != null) { res.setHeader('X-RateLimit-Limit', String(r.limit)); res.setHeader('X-RateLimit-Remaining', String(Math.max(0, r.remaining ?? 0))); }
  if (r.limit_day != null) { res.setHeader('X-RateLimit-Limit-Day', String(r.limit_day)); res.setHeader('X-RateLimit-Remaining-Day', String(Math.max(0, r.remaining_day ?? 0))); }
  if (r.retry_after) res.setHeader('Retry-After', String(Math.max(1, r.retry_after)));
  const ctx = {ok: !!r.ok, status: r.status || 200, reason: r.reason, message: MESSAGES[r.reason] || null, keyId: r.key_id || null, keyName: r.key_name || null};
  ctx.log = async (f = {}) => {
    if (offline) return;
    try {
      await q(`insert into apiadmin.requests (key_id, ip_hash, surface, endpoint, dataset, query, status, rows_returned, ms, user_agent)
               values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
        [ctx.keyId, ih, surface, f.endpoint || null, f.dataset || null, f.query ? String(f.query).slice(0, 500) : null,
         f.status ?? null, f.rows ?? null, Date.now() - t0, String(req.headers['user-agent'] || '').slice(0, 200) || null]);
    } catch (e) { console.error('gate: log failed', e.message); }
  };
  return ctx;
}

// Query string for the log, without the key.
function cleanQuery(query) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query || {})) if (k !== 'path' && k !== 'api_key') p.set(k, Array.isArray(v) ? v[0] : String(v));
  return p.toString();
}

// Logs once, right before the response goes out (work after the response may never run on Vercel).
function instrument(res, ctx, info) {
  for (const m of ['json', 'send']) {
    const orig = res[m].bind(res);
    res[m] = body => {
      if (info.logged) return orig(body);
      info.logged = true;
      return ctx.log({...info, status: res.statusCode}).then(() => orig(body));
    };
  }
}

module.exports = {gate, instrument, cleanQuery, sha256, derive, MESSAGES};
