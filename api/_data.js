// Shared data access for the API and MCP server.
// Dataset rows come from the Supabase database (public read-only access, the same rows anyone can read),
// so records added there appear without a site rebuild. If the database can't be reached, falls back
// to the published /downloads/<id>.json file so the API stays up.
const DB_URL = process.env.SUPABASE_URL || 'https://azdgwljijievtsrydxsp.supabase.co';
// Publishable key: safe to ship, it only allows what the tables' public-read policies allow.
const DB_KEY = process.env.SUPABASE_PUBLISHABLE_KEY || 'sb_publishable_Z2KjpNqiFYGhcXEA0j-ODw_2fa9xopr';
const PAGE = 1000;
const TTL = 300e3;
const cache = new Map();
// Published files are always fetched from this fixed origin, never from the request's Host or
// X-Forwarded-Host headers (which a caller controls; using them would let one request poison the cache).
const SITE_URL = String(process.env.SITE_URL || 'https://baycounty.me').replace(/\/+$/, '');

async function loadFile(req, path) {
  const c = cache.get(path);
  if (c && Date.now() - c.t < TTL) return c.v;
  const r = await fetch(`${SITE_URL}${path}`);
  if (!r.ok) throw Object.assign(new Error(`Could not load ${path}`), {status: r.status === 404 ? 404 : 502});
  const v = await r.json(); cache.set(path, {t: Date.now(), v}); return v;
}

async function fromDb(meta) {
  const table = meta.id.replace(/-/g, '_');
  const select = meta.columns.map(c => c.name).join(',');
  const out = [];
  for (let from = 0; ; from += PAGE) {
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 8000);
    let r;
    try {
      r = await fetch(`${DB_URL}/rest/v1/${table}?select=${select}&order=id`, {signal: ctl.signal,
        headers: {apikey: DB_KEY, Range: `${from}-${from + PAGE - 1}`, 'Range-Unit': 'items'}});
    } finally { clearTimeout(timer); }
    if (!r.ok && r.status !== 206) throw new Error(`database ${r.status}`);
    const page = await r.json();
    out.push(...page);
    if (page.length < PAGE) break;
  }
  return out;
}

// Rows for one catalog entry. Returns {rows, source: 'database' | 'file'}.
async function datasetRows(req, meta) {
  const key = 'db:' + meta.id;
  const c = cache.get(key);
  if (c && Date.now() - c.t < TTL) return c.v;
  let v;
  if (process.env.API_SOURCE !== 'files') {
    try { v = {rows: await fromDb(meta), source: 'database'}; }
    catch (e) { console.error('db read failed, using file', meta.id, e.message); }
  }
  if (!v) v = {rows: await loadFile(req, meta.json), source: 'file'};
  cache.set(key, {t: Date.now(), v});
  return v;
}

module.exports = {loadFile, datasetRows, SITE_URL};
