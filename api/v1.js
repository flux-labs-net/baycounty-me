// BayCounty.me public API, v1. Read-only, no key needed. All data is public record.
// Routes (vercel.json rewrites /api/v1/<path> -> /api/v1?path=<path>):
//   GET /api/v1                         index and links
//   GET /api/v1/datasets                catalog of every dataset with columns
//   GET /api/v1/datasets/{id}           rows, with filtering, search, sorting, paging, CSV
//   GET /api/v1/datasets/{id}/schema    columns and types
//   GET /api/v1/governments[/{slug}]    one profile per government
//   GET /api/v1/search?q=               search every page on the site
//   GET /api/v1/openapi.json            OpenAPI 3.1 description
const SITE = 'https://baycounty.me';
const cache = new Map();
const hits = new Map();

async function load(req, path) {
  const c = cache.get(path);
  if (c && Date.now() - c.t < 300e3) return c.v;
  const host = req.headers['x-forwarded-host'] || req.headers.host || 'baycounty.me';
  const r = await fetch(`https://${host}${path}`);
  if (!r.ok) throw Object.assign(new Error('not found'), {status: r.status === 404 ? 404 : 502});
  const v = await r.json(); cache.set(path, {t: Date.now(), v}); return v;
}

const RESERVED = new Set(['q', 'fields', 'sort', 'limit', 'offset', 'format', 'path']);
function filterRows(rows, query) {
  const q = String(query.q || '').trim().toLowerCase();
  const conds = Object.entries(query).filter(([k]) => !RESERVED.has(k));
  let out = rows.filter(r => {
    for (const [k0, v0] of conds) {
      const v = String(Array.isArray(v0) ? v0[0] : v0);
      const m = k0.match(/^(.+?)_(min|max|from|to|contains)$/);
      const k = m && !(k0 in r) ? m[1] : k0, op = m && !(k0 in r) ? m[2] : 'eq';
      if (!(k in r)) return false;
      const x = r[k];
      if (op === 'min' && !(Number(x) >= Number(v))) return false;
      if (op === 'max' && !(Number(x) <= Number(v))) return false;
      if (op === 'from' && !(String(x || '') >= v)) return false;
      if (op === 'to' && !(String(x || '') <= v + '￿')) return false;
      if (op === 'contains' && !String(x ?? '').toLowerCase().includes(v.toLowerCase())) return false;
      if (op === 'eq') {
        const opts = v.toLowerCase().split(',');
        if (!opts.includes(String(x ?? '').toLowerCase())) return false;
      }
    }
    return !q || JSON.stringify(r).toLowerCase().includes(q);
  });
  if (query.sort) {
    const keys = String(query.sort).split(',').map(s => s.trim()).filter(Boolean);
    out = [...out].sort((a, b) => {
      for (const s of keys) {
        const d = s.startsWith('-') ? -1 : 1, k = s.replace(/^[-+]/, '');
        const x = a[k], y = b[k];
        if (x == null && y == null) continue; if (x == null) return 1; if (y == null) return -1;
        const c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y));
        if (c) return c * d;
      }
      return 0;
    });
  }
  return out;
}

function toCsv(rows) {
  if (!rows.length) return '';
  const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
  const cell = v => { if (v == null) return ''; if (Array.isArray(v)) v = v.join('; '); else if (typeof v === 'object') v = JSON.stringify(v); v = String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  return [keys.join(','), ...rows.map(r => keys.map(k => cell(r[k])).join(','))].join('\n') + '\n';
}

function openapi(catalog) {
  const ids = catalog.datasets.map(d => d.id);
  const p = (name, desc, schema = {type: 'string'}) => ({name, in: 'query', required: false, description: desc, schema});
  return {
    openapi: '3.1.0',
    info: {title: 'BayCounty.me API', version: '1.0.0', description: 'Read-only access to Bay County, Florida public records compiled by BayCounty.me: budgets, taxes, votes, contracts, campaign money, salaries, elections and more. No key needed. Every row carries a link to its source record. Individual donors and rank-and-file employees are never named.', contact: {url: `${SITE}/about#contact`}},
    servers: [{url: `${SITE}/api/v1`}],
    paths: {
      '/datasets': {get: {operationId: 'listDatasets', summary: 'List every dataset with its columns', responses: {200: {description: 'Catalog'}}}},
      '/datasets/{id}': {get: {operationId: 'queryDataset', summary: 'Rows from one dataset',
        description: 'Filter on any column with ?column=value (comma-separated values mean OR). Suffixes: _min, _max (numbers), _from, _to (dates or text), _contains (text). Example: /datasets/contracts?government=Bay County&amount_min=1000000&sort=-amount',
        parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', enum: ids}}, p('q', 'Text search across all columns'), p('fields', 'Comma-separated columns to return'),
          p('sort', 'Comma-separated columns; prefix with - for descending'), p('limit', 'Rows per page (default 100, max 1000)', {type: 'integer'}), p('offset', 'Rows to skip', {type: 'integer'}), p('format', 'json (default) or csv', {type: 'string', enum: ['json', 'csv']})],
        responses: {200: {description: '{data: [...], meta: {total, limit, offset, next}}'}, 404: {description: 'Unknown dataset'}}}},
      '/datasets/{id}/schema': {get: {operationId: 'datasetSchema', summary: 'Columns and types for one dataset', parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', enum: ids}}], responses: {200: {description: 'Schema'}}}},
      '/governments': {get: {operationId: 'listGovernments', summary: 'Profile of every local government', responses: {200: {description: 'Profiles'}}}},
      '/governments/{slug}': {get: {operationId: 'getGovernment', summary: 'One government profile', parameters: [{name: 'slug', in: 'path', required: true, schema: {type: 'string', example: 'lynn-haven'}}], responses: {200: {description: 'Profile'}, 404: {description: 'Unknown government'}}}},
      '/search': {get: {operationId: 'searchSite', summary: 'Search every page on BayCounty.me', parameters: [{name: 'q', in: 'query', required: true, schema: {type: 'string'}}, p('limit', 'Results (default 20, max 100)', {type: 'integer'})], responses: {200: {description: 'Results'}}}},
    },
  };
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({error: 'Only GET is supported.'});
  const ip = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim() || 'x', now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 60e3); recent.push(now); hits.set(ip, recent);
  if (recent.length > 120) return res.status(429).json({error: 'Too many requests. Limit is 120 per minute; download /downloads/<id>.json for bulk use.'});
  res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=3600');
  const path = String(req.query.path || '').replace(/^\/+|\/+$/g, '');
  const parts = path ? path.split('/') : [];
  try {
    const catalog = await load(req, '/downloads/index.json');
    if (!parts.length) return res.status(200).json({
      name: 'BayCounty.me API', version: 'v1', updated: catalog.updated, docs: `${SITE}/developers`, openapi: `${SITE}/api/v1/openapi.json`, mcp: `${SITE}/api/mcp`,
      endpoints: {datasets: `${SITE}/api/v1/datasets`, governments: `${SITE}/api/v1/governments`, search: `${SITE}/api/v1/search?q=`},
      license: catalog.license, datasets: catalog.datasets.map(d => ({id: d.id, title: d.title, rows: d.rows, url: `${SITE}/api/v1/datasets/${d.id}`}))});
    if (parts[0] === 'openapi.json') return res.status(200).json(openapi(catalog));
    if (parts[0] === 'datasets') {
      if (parts.length === 1) return res.status(200).json({updated: catalog.updated, datasets: catalog.datasets});
      const meta = catalog.datasets.find(d => d.id === parts[1]);
      if (!meta) return res.status(404).json({error: `Unknown dataset "${parts[1]}".`, datasets: catalog.datasets.map(d => d.id)});
      if (parts[2] === 'schema') return res.status(200).json(meta);
      const rows = filterRows(await load(req, meta.json), req.query);
      const limit = Math.min(Math.max(parseInt(req.query.limit || '100', 10) || 100, 1), 1000), offset = Math.max(parseInt(req.query.offset || '0', 10) || 0, 0);
      let page = rows.slice(offset, offset + limit);
      if (req.query.fields) { const f = String(req.query.fields).split(',').map(s => s.trim()); page = page.map(r => Object.fromEntries(f.filter(k => k in r).map(k => [k, r[k]]))); }
      if (req.query.format === 'csv') { res.setHeader('Content-Type', 'text/csv; charset=utf-8'); res.setHeader('Content-Disposition', `inline; filename="${meta.id}.csv"`); return res.status(200).send(toCsv(page)); }
      const nextQ = new URLSearchParams(Object.entries(req.query).filter(([k]) => k !== 'path')); nextQ.set('offset', offset + limit); nextQ.set('limit', limit);
      return res.status(200).json({dataset: meta.id, title: meta.title, data: page,
        meta: {total: rows.length, limit, offset, next: offset + limit < rows.length ? `${SITE}/api/v1/datasets/${meta.id}?${nextQ}` : null, updated: catalog.updated, source_note: 'Each row links to its source record. Check the original before relying on a single figure.'}});
    }
    if (parts[0] === 'governments') {
      const rows = await load(req, '/downloads/government-profiles.json');
      const withSlug = rows.map(r => ({slug: (r.page || '').split('/').pop(), ...r}));
      if (parts.length === 1) return res.status(200).json({data: withSlug});
      const g = withSlug.find(r => r.slug === parts[1]);
      return g ? res.status(200).json({data: g}) : res.status(404).json({error: `Unknown government "${parts[1]}".`, governments: withSlug.map(r => r.slug)});
    }
    if (parts[0] === 'search') {
      const q = String(req.query.q || '').trim().toLowerCase();
      if (!q) return res.status(400).json({error: 'Add ?q=your search.'});
      const idx = await load(req, '/data/search.json');
      const items = Array.isArray(idx) ? idx : (idx.items || idx.entries || []);
      const words = q.split(/\s+/);
      const scored = items.map(it => { const t = JSON.stringify(it).toLowerCase(), ti = String(it.t || '').toLowerCase(); if (!words.every(w => t.includes(w))) return null; return [words.reduce((a, w) => a + (ti.includes(w) ? 10 : 0) + (String(it.s || '').toLowerCase().includes(w) ? 3 : 0), 0) + (it.u === '/developers' ? -20 : 0), it]; }).filter(Boolean).sort((a, b) => b[0] - a[0]);
      const limit = Math.min(parseInt(req.query.limit || '20', 10) || 20, 100);
      return res.status(200).json({query: q, total: scored.length, data: scored.slice(0, limit).map(([, it]) => ({type: it.k, title: it.t, summary: it.s, url: it.u ? (/^https?:/.test(it.u) ? it.u : SITE + it.u) : null}))});
    }
    return res.status(404).json({error: 'Unknown endpoint.', docs: `${SITE}/developers`});
  } catch (e) {
    return res.status(e.status || 500).json({error: e.status === 404 ? 'Not found.' : 'Something went wrong. Try again shortly.'});
  }
};
module.exports.filterRows = filterRows;
module.exports.toCsv = toCsv;
module.exports.openapi = openapi;
