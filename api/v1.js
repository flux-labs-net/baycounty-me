// BayCounty.me public API, v1. Read-only, no key needed. All data is public record.
// Routes (vercel.json rewrites /api/v1/<path> -> /api/v1?path=<path>):
//   GET /api/v1                         index and links
//   GET /api/v1/datasets                catalog of every dataset with columns
//   GET /api/v1/datasets/{id}           rows, with filtering, search, sorting, paging, CSV
//   GET /api/v1/datasets/{id}/schema    columns and types
//   GET /api/v1/governments[/{slug}]    one profile per government
//   GET /api/v1/search?q=               search every page on the site
//   GET /api/v1/openapi.json            OpenAPI 3.1 description
// Dataset rows are read from the BayCounty.me database (see api/_data.js), falling back to the published files.
//   GET /api/v1/status                  per-dataset rows, last database sync and errors
//   GET /api/v1/changes?since=&dataset= records added to the database since a time
//   GET /api/v1/meetings.ics?gov=       calendar of upcoming meetings (one government or all)
// Responses carry an ETag (and Last-Modified when the data's date is known); a matching If-None-Match or
// If-Modified-Since gets 304 Not Modified with no body.
const crypto = require('crypto');
const {loadFile: load, datasetRows, rest} = require('./_data');
const {gate, instrument, cleanQuery} = require('./_gate');
const {CSV_MAX, filterRows, toCsv, csvCell, aggregate} = require('./_query');
const SITE = 'https://baycounty.me';
const bad = msg => Object.assign(new Error(msg), {status: 400, expose: true});

// Conditional responses. Wraps res.json/res.send so every 200 gets an ETag (hash of the exact body) and, when
// res.locals.lastModified is set, Last-Modified. Install after instrument(), so a 304 is still logged.
function conditional(req, res) {
  res.locals = res.locals || {};
  const sendOrig = res.send.bind(res);
  const wrap = (m, ser) => {
    const orig = res[m].bind(res);
    res[m] = body => {
      if (res.statusCode !== 200) return orig(body);
      const text = ser(body);
      const tag = '"' + crypto.createHash('sha1').update(text).digest('base64url').slice(0, 27) + '"';
      res.setHeader('ETag', tag);
      const lm = res.locals.lastModified;
      if (lm) res.setHeader('Last-Modified', lm.toUTCString());
      const inm = req.headers['if-none-match'], ims = Date.parse(req.headers['if-modified-since'] || '');
      const fresh = inm ? inm.split(',').map(s => s.trim().replace(/^W\//, '')).includes(tag) || inm.trim() === '*'
        : (lm && Number.isFinite(ims) && Math.floor(lm.getTime() / 1000) <= Math.floor(ims / 1000));
      // 304 goes through the same (logging) path; Node never sends a body with a 304.
      if (fresh) { res.status(304); return (m === 'json' ? sendOrig : orig)(''); }
      return orig(m === 'json' ? body : text);
    };
  };
  wrap('json', b => JSON.stringify(b));
  wrap('send', b => (Buffer.isBuffer(b) ? b.toString() : String(b ?? '')));
}

// Status: rows per dataset, the last successful sync and recent failures, from ingest_runs (public read).
async function status(catalog) {
  let runs = [], dbOk = true;
  try { runs = (await rest('ingest_runs?select=dataset,started_at,finished_at,rows_in,rows_deleted,status,notes,git_sha&order=id.desc&limit=400')).rows; }
  catch (e) { dbOk = false; }
  const by = new Map();
  for (const r of runs) { if (!by.has(r.dataset)) by.set(r.dataset, []); by.get(r.dataset).push(r); }
  const datasets = catalog.datasets.map(d => {
    const rs = by.get(d.id) || [], ok = rs.find(r => r.status === 'ok'), failed = rs.filter(r => r.status === 'failed');
    const lastFail = failed[0];
    return {id: d.id, title: d.title, rows_published: d.rows, rows_in_database: ok ? ok.rows_in : null,
      last_ingest: ok ? ok.finished_at || ok.started_at : null, last_ingest_notes: ok ? ok.notes : null,
      error: lastFail && (!ok || Date.parse(lastFail.started_at) > Date.parse(ok.started_at)) ? {at: lastFail.started_at, message: lastFail.notes || 'failed'} : null,
      stuck: rs[0] && rs[0].status === 'running' && Date.now() - Date.parse(rs[0].started_at) > 3600e3 ? true : undefined};
  });
  const last = runs.find(r => r.status === 'ok');
  return {updated: catalog.updated, database: dbOk ? 'ok' : 'unreachable', last_sync: last ? last.finished_at || last.started_at : null, git_sha: last ? last.git_sha : null,
    errors: datasets.filter(d => d.error).map(d => ({dataset: d.id, ...d.error})), datasets};
}

// Changes: records first seen by the database after `since` (created_at; rows are kept across syncs when unchanged,
// see db/scripts/load.py). A record whose content changed counts as new.
async function changes(catalog, query) {
  const since = Date.parse(String(query.since || ''));
  if (!Number.isFinite(since)) throw bad('Add ?since= with a date or time, e.g. ?since=2026-10-01 or ?since=2026-10-01T12:00:00Z.');
  const iso = new Date(since).toISOString();
  const want = query.dataset ? String(query.dataset).split(',') : null;
  const metas = catalog.datasets.filter(d => !want || want.includes(d.id));
  if (want && !metas.length) throw Object.assign(new Error(`Unknown dataset "${query.dataset}".`), {status: 404, expose: true});
  const limit = Math.min(Math.max(parseInt(query.limit || '500', 10) || 500, 1), 1000);
  const out = [];
  for (const m of metas) {
    const table = m.id.replace(/-/g, '_'), cols = m.columns.map(c => c.name).join(',');
    try {
      const r = await rest(`${table}?select=${cols},created_at,updated_at&created_at=gt.${encodeURIComponent(iso)}&order=created_at.desc&limit=${limit}`, {count: true});
      out.push({dataset: m.id, total: r.total ?? r.rows.length, returned: r.rows.length, data: r.rows});
    } catch (e) { out.push({dataset: m.id, error: 'unavailable'}); }
  }
  return {since: iso, note: 'Records added to the BayCounty.me database since this time. An edited record counts as new; removed records are not listed.',
    total: out.reduce((a, d) => a + (d.total || 0), 0), datasets: out};
}

// iCal for upcoming meetings, optionally one government (?gov=lh or a board id like lh-cra; comma-separated).
function meetingsIcs(meetings, gov) {
  const want = gov ? String(gov).toLowerCase().split(',').filter(Boolean) : null;
  const esc = t => String(t ?? '').replace(/([,;\\])/g, '\\$1').replace(/\r?\n/g, '\\n');
  const fold = l => { const o = []; let s = l; while (s.length > 74) { o.push(s.slice(0, 74)); s = ' ' + s.slice(74); } o.push(s); return o.join('\r\n'); };
  const ut = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const now = ut(new Date());
  const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//BayCounty.me//Meetings API//EN', 'CALSCALE:GREGORIAN', 'METHOD:PUBLISH',
    `X-WR-CALNAME:${esc(want ? 'Bay County meetings: ' + want.join(', ') : 'Bay County public meetings')}`, 'X-WR-TIMEZONE:America/Chicago'];
  for (const m of meetings) {
    const board = String(m.board || ''), g = board.split('-')[0];
    if (m.past || m.cancelled || !m.start) continue;
    if (want && !want.includes(g) && !want.includes(board)) continue;
    const uid = (board + (m.start || '') + (m.title || '')).toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 60) + '@baycounty.me';
    lines.push('BEGIN:VEVENT', `UID:${uid}`, `DTSTAMP:${now}`);
    if (m.start.length > 10) { const d = new Date(m.start); lines.push(`DTSTART:${ut(d)}`, `DTEND:${ut(new Date(d.getTime() + 2 * 3600e3))}`); }
    else { const d = m.start.replace(/-/g, ''), n = new Date(m.start + 'T12:00:00Z'); n.setUTCDate(n.getUTCDate() + 1); lines.push(`DTSTART;VALUE=DATE:${d}`, `DTEND;VALUE=DATE:${n.toISOString().slice(0, 10).replace(/-/g, '')}`); }
    const desc = (m.agenda_url ? `Agenda: ${m.agenda_url}\n` : '') + (m.expected ? 'Expected from the regular schedule; confirm before going.\n' : '') + 'From BayCounty.me/meetings';
    const G = require('./_alerts').GOVS[g];
    const who = G ? G[0] + (/cra/.test(board) ? ' CRA' : /planning/.test(board) ? ' Planning Commission' : '') : board;
    lines.push(`SUMMARY:${esc(`${who}: ${m.title || 'Meeting'}` + (m.expected ? ' (expected)' : ''))}`, `LOCATION:${esc(m.location || '')}`, `DESCRIPTION:${esc(desc)}`);
    if (m.agenda_url) lines.push(`URL:${m.agenda_url}`);
    lines.push('END:VEVENT');
  }
  lines.push('END:VCALENDAR');
  return lines.map(fold).join('\r\n') + '\r\n';
}

function openapi(catalog) {
  const ids = catalog.datasets.map(d => d.id);
  const p = (name, desc, schema = {type: 'string'}) => ({name, in: 'query', required: false, description: desc, schema});
  return {
    openapi: '3.1.0',
    info: {title: 'BayCounty.me API', version: '1.1.0', description: 'Read-only access to Bay County, Florida public records compiled by BayCounty.me: budgets, taxes, votes, contracts, campaign money, salaries, elections and more. No key needed. Every row carries a link to its source record. Individual donors and rank-and-file employees are never named. Responses carry an ETag (and Last-Modified where known); send If-None-Match or If-Modified-Since to get 304 Not Modified.', contact: {url: `${SITE}/about#contact`}},
    servers: [{url: `${SITE}/api/v1`}],
    components: {securitySchemes: {bearer: {type: 'http', scheme: 'bearer', description: 'Optional API key (bcm_...) for higher limits'}, apiKey: {type: 'apiKey', in: 'header', name: 'X-API-Key'}}},
    security: [{}, {bearer: []}, {apiKey: []}],
    paths: {
      '/datasets': {get: {operationId: 'listDatasets', summary: 'List every dataset with its columns', responses: {200: {description: 'Catalog'}}}},
      '/datasets/{id}': {get: {operationId: 'queryDataset', summary: 'Rows from one dataset',
        description: 'Filter on any column with ?column=value (comma-separated values mean OR). Suffixes: _min, _max (numbers), _from, _to (dates or text), _contains (text), _ne (not equal to any of the values), _null=true|false (blank or not). Blank values never match _min/_max/_from/_to. Add group_by (and optionally sum) to get totals instead of rows. Example: /datasets/contracts?government=Bay County&amount_min=1000000&sort=-amount',
        parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', enum: ids}}, p('q', 'Text search across the values in every column'), p('fields', 'Comma-separated columns to return'),
          p('group_by', 'Comma-separated columns to group by. Returns one row per group with count (and sum_<col>, n_<col> for each sum column), largest first'), p('sum', 'Comma-separated numeric columns to add up per group (needs group_by)'),
          p('sort', 'Comma-separated columns; prefix with - for descending'), p('limit', 'Rows per page (default 100, max 1000). With format=csv the default is every matching row, up to 10,000', {type: 'integer'}), p('offset', 'Rows to skip', {type: 'integer'}), p('format', 'json (default) or csv', {type: 'string', enum: ['json', 'csv']})],
        responses: {200: {description: '{data: [...], meta: {total, limit, offset, next}}'}, 404: {description: 'Unknown dataset'}}}},
      '/datasets/{id}/schema': {get: {operationId: 'datasetSchema', summary: 'Columns and types for one dataset', parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', enum: ids}}], responses: {200: {description: 'Schema'}}}},
      '/governments': {get: {operationId: 'listGovernments', summary: 'Profile of every local government', responses: {200: {description: 'Profiles'}}}},
      '/governments/{slug}': {get: {operationId: 'getGovernment', summary: 'One government profile', parameters: [{name: 'slug', in: 'path', required: true, schema: {type: 'string', example: 'lynn-haven'}}], responses: {200: {description: 'Profile'}, 404: {description: 'Unknown government'}}}},
      '/status': {get: {operationId: 'status', summary: 'Rows per dataset, last database sync and load errors', responses: {200: {description: '{database, last_sync, errors: [...], datasets: [{id, rows_published, rows_in_database, last_ingest, error}]}'}}}},
      '/changes': {get: {operationId: 'changes', summary: 'Records added to the database since a time',
        description: 'Uses each record\'s created_at (when the database first saw it). An edited record counts as new; removed records are not listed.',
        parameters: [{name: 'since', in: 'query', required: true, description: 'ISO date or time, e.g. 2026-10-01 or 2026-10-01T12:00:00Z', schema: {type: 'string'}},
          p('dataset', 'Comma-separated dataset ids (default: all)'), p('limit', 'Records per dataset (default 500, max 1000)', {type: 'integer'})],
        responses: {200: {description: '{since, total, datasets: [{dataset, total, returned, data}]}'}, 400: {description: 'Missing or invalid since'}}}},
      '/meetings.ics': {get: {operationId: 'meetingsCalendar', summary: 'Upcoming meetings as an iCalendar feed',
        parameters: [p('gov', 'Government key(s) or board id(s), comma-separated: county, schools, pc, pcb, lh, cw, sp, parker, mb, or a board such as lh-cra. Default: all')],
        responses: {200: {description: 'text/calendar', content: {'text/calendar': {schema: {type: 'string'}}}}}}},
      '/search': {get: {operationId: 'searchSite', summary: 'Search every page on BayCounty.me', parameters: [{name: 'q', in: 'query', required: true, schema: {type: 'string'}}, p('limit', 'Results (default 20, max 100)', {type: 'integer'})], responses: {200: {description: 'Results'}}}},
    },
  };
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-API-Key, If-None-Match, If-Modified-Since');
  res.setHeader('Access-Control-Expose-Headers', 'X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Limit-Day, X-RateLimit-Remaining-Day, Retry-After, X-Total-Count, X-Truncated, ETag, Last-Modified');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({error: 'Only GET is supported.'});
  // Not cached at the edge, so every request is counted against its key and logged.
  res.setHeader('Cache-Control', 'private, max-age=60');
  const path = String(req.query.path || '').replace(/^\/+|\/+$/g, '');
  const parts = path ? path.split('/') : [];
  const ctx = await gate(req, res, 'api');
  const info = {endpoint: path || 'index', dataset: parts[0] === 'datasets' ? parts[1] || null : null, query: cleanQuery(req.query)};
  instrument(res, ctx, info);
  conditional(req, res);
  if (!ctx.ok) return res.status(ctx.status).json({error: ctx.message || 'Request not allowed.', reason: ctx.reason, docs: `${SITE}/developers#keys`});
  try {
    const catalog = await load(req, '/downloads/index.json');
    if (catalog.updated) res.locals.lastModified = new Date(catalog.updated + 'T00:00:00Z');
    if (!parts.length) return res.status(200).json({
      name: 'BayCounty.me API', version: 'v1', updated: catalog.updated, docs: `${SITE}/developers`, openapi: `${SITE}/api/v1/openapi.json`, mcp: `${SITE}/api/mcp`,
      endpoints: {datasets: `${SITE}/api/v1/datasets`, governments: `${SITE}/api/v1/governments`, search: `${SITE}/api/v1/search?q=`,
        status: `${SITE}/api/v1/status`, changes: `${SITE}/api/v1/changes?since=`, meetings_calendar: `${SITE}/api/v1/meetings.ics?gov=`},
      license: catalog.license, datasets: catalog.datasets.map(d => ({id: d.id, title: d.title, rows: d.rows, url: `${SITE}/api/v1/datasets/${d.id}`}))});
    if (parts[0] === 'openapi.json') return res.status(200).json(openapi(catalog));
    if (parts[0] === 'status') { res.locals.lastModified = null; return res.status(200).json(await status(catalog)); }
    if (parts[0] === 'changes') { res.locals.lastModified = null; return res.status(200).json(await changes(catalog, req.query)); }
    if (parts[0] === 'meetings.ics') {
      const md = catalog.datasets.find(d => d.id === 'meetings');
      const rows = md ? (await datasetRows(req, md)).rows : await load(req, '/downloads/meetings.json');
      res.setHeader('Content-Type', 'text/calendar; charset=utf-8');
      res.setHeader('Content-Disposition', `inline; filename="meetings${req.query.gov ? '-' + String(req.query.gov).replace(/[^a-z0-9,-]/gi, '') : ''}.ics"`);
      return res.status(200).send(meetingsIcs(rows, req.query.gov));
    }
    if (parts[0] === 'datasets') {
      if (parts.length === 1) return res.status(200).json({updated: catalog.updated, datasets: catalog.datasets});
      const meta = catalog.datasets.find(d => d.id === parts[1]);
      if (!meta) return res.status(404).json({error: `Unknown dataset "${parts[1]}".`, datasets: catalog.datasets.map(d => d.id)});
      if (parts[2] === 'schema') return res.status(200).json(meta);
      const {rows: all, source} = await datasetRows(req, meta);
      const rows = filterRows(all, req.query);
      const csv = req.query.format === 'csv';
      if (req.query.group_by) {
        const groups = aggregate(rows, req.query.group_by, req.query.sum, meta.columns.map(c => c.name));
        info.rows = groups.length;
        if (csv) { res.setHeader('Content-Type', 'text/csv; charset=utf-8'); res.setHeader('Content-Disposition', `inline; filename="${meta.id}-grouped.csv"`); return res.status(200).send(toCsv(groups)); }
        return res.status(200).json({dataset: meta.id, title: meta.title, group_by: String(req.query.group_by), sum: req.query.sum ? String(req.query.sum) : null, data: groups,
          meta: {groups: groups.length, rows_matched: rows.length, updated: catalog.updated, data_source: source, note: 'count is rows per group; sum_<column> adds the numeric values, n_<column> is how many were added. Totals can double-count where a dataset lists overlapping records; see each dataset\'s notes.'}});
      }
      // CSV returns every matching row (up to CSV_MAX) unless a limit is given; JSON pages 100 at a time (max 1,000).
      const maxLim = csv ? CSV_MAX : 1000, defLim = csv ? CSV_MAX : 100;
      const limit = Math.min(Math.max(parseInt(req.query.limit || String(defLim), 10) || defLim, 1), maxLim), offset = Math.max(parseInt(req.query.offset || '0', 10) || 0, 0);
      let page = rows.slice(offset, offset + limit);
      info.rows = page.length;
      if (req.query.fields) { const f = String(req.query.fields).split(',').map(s => s.trim()); page = page.map(r => Object.fromEntries(f.filter(k => k in r).map(k => [k, r[k]]))); }
      if (csv) { res.setHeader('X-Total-Count', String(rows.length)); if (offset + limit < rows.length) res.setHeader('X-Truncated', 'true');
        res.setHeader('Content-Type', 'text/csv; charset=utf-8'); res.setHeader('Content-Disposition', `inline; filename="${meta.id}.csv"`); return res.status(200).send(toCsv(page)); }
      const nextQ = new URLSearchParams(Object.entries(req.query).filter(([k]) => k !== 'path' && k !== 'api_key')); nextQ.set('offset', offset + limit); nextQ.set('limit', limit);
      return res.status(200).json({dataset: meta.id, title: meta.title, data: page,
        meta: {total: rows.length, limit, offset, next: offset + limit < rows.length ? `${SITE}/api/v1/datasets/${meta.id}?${nextQ}` : null, updated: catalog.updated, data_source: source, source_note: 'Each row links to its source record. Check the original before relying on a single figure.'}});
    }
    if (parts[0] === 'governments') {
      const gp = catalog.datasets.find(d => d.id === 'government-profiles');
      const rows = gp ? (await datasetRows(req, gp)).rows : await load(req, '/downloads/government-profiles.json');
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
    if (e.expose) return res.status(e.status).json({error: e.message, docs: `${SITE}/developers`});
    return res.status(e.status || 500).json({error: e.status === 404 ? 'Not found.' : 'Something went wrong. Try again shortly.'});
  }
};
module.exports.filterRows = filterRows;
module.exports.toCsv = toCsv;
module.exports.csvCell = csvCell;
module.exports.openapi = openapi;
module.exports.meetingsIcs = meetingsIcs;
module.exports.conditional = conditional;
