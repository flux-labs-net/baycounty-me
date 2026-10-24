// BayCounty.me MCP server (Model Context Protocol, Streamable HTTP transport, JSON responses).
// Lets AI assistants query the same public data as the REST API. Read-only, no auth.
// Add as a remote MCP server / custom connector: https://baycounty.me/api/mcp
const {filterRows} = require('./_query');
const {loadFile: load, datasetRows} = require('./_data');
const {gate, instrument} = require('./_gate');
const SITE = 'https://baycounty.me';
const VERSIONS = ['2025-06-18', '2025-03-26', '2024-11-05'];

const TOOLS = [
  {name: 'list_datasets', title: 'List datasets',
   description: 'List every BayCounty.me dataset (budgets, property taxes, exemptions, votes, contracts, campaign money, 2026 candidates, salaries, debt, audits, Hurricane Michael, meetings...) with row counts and column names. Call this first to find the right dataset id.',
   inputSchema: {type: 'object', properties: {}, additionalProperties: false}, annotations: {readOnlyHint: true}},
  {name: 'query_dataset', title: 'Query a dataset',
   description: 'Get rows from a dataset. Filters match columns exactly (case-insensitive; comma-separated values mean OR). Use column suffixes _min/_max for numbers, _from/_to for dates, _contains for text. Every row includes a source link; cite it. Individual donors and rank-and-file employees are never named.',
   inputSchema: {type: 'object', required: ['id'], additionalProperties: false, properties: {
     id: {type: 'string', description: 'Dataset id from list_datasets, e.g. "votes", "contracts", "salary-positions"'},
     filters: {type: 'object', description: 'Column filters, e.g. {"government": "Bay County", "amount_min": 1000000}', additionalProperties: {type: ['string', 'number', 'boolean']}},
     q: {type: 'string', description: 'Text search across all columns'},
     sort: {type: 'string', description: 'Comma-separated columns; prefix - for descending, e.g. "-amount"'},
     fields: {type: 'string', description: 'Comma-separated columns to return'},
     limit: {type: 'integer', minimum: 1, maximum: 200, default: 25},
     offset: {type: 'integer', minimum: 0, default: 0}}},
   annotations: {readOnlyHint: true}},
  {name: 'get_government', title: 'Government profile',
   description: 'Profile of a Bay County local government: population, budget, tax rate, debt, audit findings, votes recorded, staff, utility bill and FEMA money, plus years: budget, tax rate, audited actuals, residents, debt and staff for each fiscal year on record. Omit slug to list all.',
   inputSchema: {type: 'object', additionalProperties: false, properties: {slug: {type: 'string', description: 'bay-county, bay-district-schools, panama-city, panama-city-beach, lynn-haven, callaway, springfield, parker or mexico-beach'}}},
   annotations: {readOnlyHint: true}},
  {name: 'upcoming_meetings', title: 'Upcoming meetings',
   description: 'Upcoming public meetings of Bay County boards (County Commission, School Board, city commissions, CRA boards), soonest first, with agenda links and agenda item titles where posted. Meetings marked expected=true come from the regular schedule, not an official posting.',
   inputSchema: {type: 'object', additionalProperties: false, properties: {
     gov: {type: 'string', description: 'Government key or board id: county, schools, pc, pcb, lh, cw, sp, parker, mb (or e.g. lh-cra). Omit for all.'},
     days: {type: 'integer', minimum: 1, maximum: 120, default: 30, description: 'How many days ahead'},
     keyword: {type: 'string', description: 'Only meetings whose title or agenda items mention this (e.g. a street name)'},
     limit: {type: 'integer', minimum: 1, maximum: 100, default: 25}}},
   annotations: {readOnlyHint: true}},
  {name: 'member_voting_record', title: 'Board member voting record',
   description: 'How one elected board member voted on recorded money votes: totals (yes/no/absent), the votes where they were in the minority, and the latest votes, each with a source link.',
   inputSchema: {type: 'object', required: ['member'], additionalProperties: false, properties: {
     member: {type: 'string', description: 'Member name, e.g. "Clair Pease" (case-insensitive; partial names work if they match one member)'},
     since: {type: 'string', description: 'Only votes on or after this date (YYYY-MM-DD)'},
     limit: {type: 'integer', minimum: 1, maximum: 200, default: 25}}},
   annotations: {readOnlyHint: true}},
  {name: 'vendor_profile', title: 'Vendor profile',
   description: 'Everything BayCounty.me has on one company by name: contracts, change orders, check-register payment totals, CRA payments, and campaign contributions it made as a business (individual donors are never included). Names are normalized (case, punctuation, Inc/LLC/Co removed). A match between a contribution and a contract does not show why anything happened.',
   inputSchema: {type: 'object', required: ['vendor'], additionalProperties: false, properties: {
     vendor: {type: 'string', description: 'Company name, e.g. "GAC Contractors" or "Roberts & Roberts"'},
     limit: {type: 'integer', minimum: 1, maximum: 200, default: 50, description: 'Rows per section'}}},
   annotations: {readOnlyHint: true}},
  {name: 'official_correspondence', title: 'Letters to officials',
   description: 'Published emails BayCounty.me sent to local officials, and their replies, grouped by letter. Only threads approved for publication are returned.',
   inputSchema: {type: 'object', additionalProperties: false, properties: {
     year: {type: 'string', description: 'A year such as 2026, or "all". Omit for the latest year with letters.'},
     government: {type: 'string', description: 'Only letters to this government (as listed in the governments field of a previous result)'},
     limit: {type: 'integer', minimum: 1, maximum: 100, default: 25, description: 'Conversations to return'}}},
   annotations: {readOnlyHint: true}},
  {name: 'search_site', title: 'Search BayCounty.me',
   description: 'Full-text search across every page and record on BayCounty.me. Returns titles, summaries and links.',
   inputSchema: {type: 'object', required: ['q'], additionalProperties: false, properties: {q: {type: 'string'}, limit: {type: 'integer', minimum: 1, maximum: 50, default: 10}}},
   annotations: {readOnlyHint: true}},
];

// Company names for matching: lower-case, & -> and, punctuation and corporate suffixes removed.
const SUFFIX = /\b(inc|incorporated|llc|l l c|ltd|co|corp|corporation|company|pa|p a|pllc|lp|llp|plc|the|dba|d b a)\b/g;
function normVendor(s) {
  return String(s ?? '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9 ]+/g, ' ').replace(SUFFIX, ' ').replace(/\s+/g, ' ').trim();
}
// A row's name matches when the normalized names are equal, or one contains the other as whole words
// (only when the shorter name has at least two words or 6 letters, so "co" or "abc" don't match everything).
function vendorMatch(name, want) {
  const a = normVendor(name), b = want;
  if (!a || !b) return false;
  if (a === b) return true;
  const [s, l] = a.length < b.length ? [a, b] : [b, a];
  if (s.split(' ').length < 2 && s.length < 6) return false;
  return (' ' + l + ' ').includes(' ' + s + ' ');
}
const sumOf = (rows, k) => Math.round(rows.reduce((t, r) => t + (Number.isFinite(Number(r[k])) && r[k] !== null && r[k] !== '' ? Number(r[k]) : 0), 0) * 100) / 100;

async function rowsOf(req, c, id) {
  const meta = c.datasets.find(d => d.id === id);
  return meta ? (await datasetRows(req, meta)).rows : [];
}

// Business/PAC contributions from data/campaign/vendor_matches.json (built by another script; its shape may change,
// so every field is read defensively and the file being missing or different just gives an empty list).
async function vendorContributions(req, want) {
  let vm;
  try { vm = JSON.parse(require('fs').readFileSync(require('path').join(__dirname, '..', 'data', 'campaign', 'vendor_matches.json'), 'utf8')); }
  catch (e) { try { vm = await load(req, '/data/campaign/vendor_matches.json'); } catch (e2) { return {available: false, rows: []}; } }
  const list = Array.isArray(vm) ? vm : Array.isArray(vm && vm.matches) ? vm.matches : [];
  const rows = [], seen = new Map();
  for (const m of list) {
    if (!m || typeof m !== 'object') continue;
    const names = [m.contributor, m.vendor_entity, ...String(m.vendor || '').split(' / ')].filter(x => typeof x === 'string');
    if (!names.some(n => vendorMatch(n, want))) continue;
    // The file repeats a contribution once per contracting government; list each contribution once.
    const k = JSON.stringify([m.contributor, m.candidate, m.election, m.contribution_amount, m.contribution_dates]);
    if (seen.has(k)) { const r = seen.get(k); if (m.contract_government && !r.contracting_governments.includes(m.contract_government)) r.contracting_governments.push(m.contract_government); continue; }
    const row = {contributor: m.contributor ?? null, candidate: m.candidate ?? null, office: m.office ?? null, election: m.election ?? null,
      amount: typeof m.contribution_amount === 'number' ? m.contribution_amount : null, dates: Array.isArray(m.contribution_dates) ? m.contribution_dates : [],
      contracting_governments: m.contract_government ? [m.contract_government] : [], match_confidence: m.match_confidence ?? null, report_url: m.campaign_report_url ?? null};
    seen.set(k, row); rows.push(row);
  }
  return {available: true, rows};
}

async function call(req, name, a = {}) {
  if (name === 'upcoming_meetings') {
    const c = await load(req, '/downloads/index.json');
    const days = Math.min(Math.max(a.days || 30, 1), 120), lim = Math.min(Math.max(a.limit || 25, 1), 100);
    const now = Date.now(), until = now + days * 864e5, gov = a.gov ? String(a.gov).toLowerCase() : null, kw = a.keyword ? String(a.keyword).toLowerCase() : null;
    const t = s => Date.parse(String(s).length === 10 ? s + 'T23:59:00-05:00' : s);
    let rows = (await rowsOf(req, c, 'meetings')).filter(m => m.start && !m.past && !m.cancelled && t(m.start) >= now - 3 * 3600e3 && t(m.start) <= until);
    if (gov) rows = rows.filter(m => String(m.board) === gov || String(m.board).split('-')[0] === gov);
    if (kw) rows = rows.filter(m => [m.title, ...(Array.isArray(m.agenda_items) ? m.agenda_items : []), ...(Array.isArray(m.items) ? m.items.map(i => i && i.title) : [])].some(x => String(x || '').toLowerCase().includes(kw)));
    rows.sort((x, y) => t(x.start) - t(y.start));
    const page = rows.slice(0, lim).map(m => ({board: m.board, title: m.title, start: m.start, location: m.location, status: m.status, expected: !!m.expected,
      agenda_url: m.agenda_url || null, packet_url: m.packet_url || null, money_items: Array.isArray(m.items) ? m.items : [], agenda_items: Array.isArray(m.agenda_items) ? m.agenda_items.slice(0, 40) : [], source: m.source}));
    return {total: rows.length, returned: page.length, days, meetings: page, calendar: `${SITE}/api/v1/meetings.ics${gov ? '?gov=' + encodeURIComponent(gov) : ''}`,
      note: 'Times are US Central. expected=true means generated from the regular schedule; confirm before going.'};
  }
  if (name === 'official_correspondence') {
    const r = await require('./_correspondence').publicFeed({year: String(a.year || ''), government: String(a.government || '').slice(0, 120)});
    const lim = Math.min(Math.max(a.limit || 25, 1), 100);
    const page = r.conversations.slice(0, lim);
    return {year: r.year, years: r.years, governments: r.governments, total: r.conversations.length, returned: page.length, conversations: page,
      page: `${SITE}/correspondence`};
  }
  if (name === 'member_voting_record') {
    const c = await load(req, '/downloads/index.json');
    const want = String(a.member || '').trim().toLowerCase();
    if (want.length < 3) throw new Error('member is required (at least 3 letters).');
    const all = await rowsOf(req, c, 'member-votes');
    const names = [...new Set(all.map(r => r.member).filter(Boolean))];
    let who = names.filter(n => n.toLowerCase() === want);
    if (!who.length) who = names.filter(n => n.toLowerCase().includes(want));
    if (!who.length) throw new Error(`No recorded votes for "${a.member}". Members with votes: ${names.sort().join(', ')}`);
    if (who.length > 1) throw new Error(`"${a.member}" matches several members: ${who.join(', ')}. Use the full name.`);
    const mine = all.filter(r => r.member === who[0] && (!a.since || String(r.date || '') >= a.since)).sort((x, y) => String(y.date).localeCompare(String(x.date)));
    const tally = {};
    for (const r of mine) tally[r.vote || 'unknown'] = (tally[r.vote || 'unknown'] || 0) + 1;
    // Minority votes: this member voted differently from most members on the same vote (same date + headline + board).
    const key = r => `${r.date}|${r.board}|${r.headline}`;
    const byVote = new Map();
    for (const r of all) if (r.vote === 'yes' || r.vote === 'no') { const k = key(r); if (!byVote.has(k)) byVote.set(k, {yes: 0, no: 0}); byVote.get(k)[r.vote]++; }
    const minority = mine.filter(r => { const v = byVote.get(key(r)); return v && (r.vote === 'yes' || r.vote === 'no') && v[r.vote] < v[r.vote === 'yes' ? 'no' : 'yes']; });
    const lim = Math.min(Math.max(a.limit || 25, 1), 200);
    const pick = r => ({date: r.date, board: r.board, vote: r.vote, headline: r.headline, source_url: r.source_url});
    req._rows = Math.min(mine.length, lim);
    return {member: who[0], boards: [...new Set(mine.map(r => r.board))], votes: mine.length, tally, in_minority: minority.length,
      minority_votes: minority.slice(0, lim).map(pick), latest: mine.slice(0, lim).map(pick),
      note: 'Recorded money votes compiled by BayCounty.me, not every vote the board took. Cite each source_url.'};
  }
  if (name === 'vendor_profile') {
    const want = normVendor(a.vendor);
    if (want.length < 3) throw new Error('vendor is required (at least 3 letters).');
    const c = await load(req, '/downloads/index.json');
    const lim = Math.min(Math.max(a.limit || 50, 1), 200);
    const [contracts, cos, pays, cra, contrib] = await Promise.all([
      rowsOf(req, c, 'contracts'), rowsOf(req, c, 'change-orders'), rowsOf(req, c, 'vendor-payments'), rowsOf(req, c, 'cra-payments'), vendorContributions(req, want)]);
    const ct = contracts.filter(r => vendorMatch(r.vendor, want)), co = cos.filter(r => vendorMatch(r.vendor, want));
    const vp = pays.filter(r => vendorMatch(r.vendor, want)), cp = cra.filter(r => vendorMatch(r.payee, want));
    const names = [...new Set([...ct, ...co, ...vp].map(r => r.vendor).concat(cp.map(r => r.payee)).filter(Boolean))];
    req._rows = ct.length + co.length + vp.length + cp.length + contrib.rows.length;
    return {vendor: a.vendor, normalized: want, names_matched: names,
      contracts: {count: ct.length, total: sumOf(ct, 'amount'), rows: ct.slice(0, lim)},
      change_orders: {count: co.length, total_change: sumOf(co, 'change_amount'), rows: co.slice(0, lim)},
      vendor_payments: {count: vp.length, total: sumOf(vp, 'total'), rows: vp.slice(0, lim)},
      cra_payments: {count: cp.length, total: sumOf(cp, 'amount'), rows: cp.slice(0, lim)},
      campaign_contributions: {available: contrib.available, count: contrib.rows.length, total: sumOf(contrib.rows, 'amount'), rows: contrib.rows.slice(0, lim)},
      note: 'Name matching is automatic and can miss spellings or join different companies with similar names; check names_matched and each source link. Totals can overlap (a contract and its payments). Campaign contributions are from the company itself; individual donors are never included. A contribution and a contract appearing together does not show why anything happened.'};
  }
  if (name === 'list_datasets') {
    const c = await load(req, '/downloads/index.json');
    return {updated: c.updated, datasets: c.datasets.map(d => ({id: d.id, title: d.title, description: d.description, rows: d.rows, columns: d.columns.map(x => x.name),
      filter_values: Object.fromEntries(d.columns.filter(x => x.values).map(x => [x.name, x.values]))}))};
  }
  if (name === 'query_dataset') {
    const c = await load(req, '/downloads/index.json');
    const meta = c.datasets.find(d => d.id === a.id);
    if (!meta) throw new Error(`Unknown dataset "${a.id}". Valid ids: ${c.datasets.map(d => d.id).join(', ')}`);
    const query = {...(a.filters || {}), ...(a.q ? {q: a.q} : {}), ...(a.sort ? {sort: a.sort} : {})};
    for (const k of Object.keys(query)) query[k] = String(query[k]);
    const rows = filterRows((await datasetRows(req, meta)).rows, query);
    const limit = Math.min(Math.max(a.limit || 25, 1), 200), offset = Math.max(a.offset || 0, 0);
    let page = rows.slice(offset, offset + limit);
    if (a.fields) { const f = a.fields.split(',').map(s => s.trim()); page = page.map(r => Object.fromEntries(f.filter(k => k in r).map(k => [k, r[k]]))); }
    return {dataset: meta.id, total: rows.length, offset, returned: page.length, rows: page, note: 'Cite each row\'s source link. Data compiled by BayCounty.me from public records.'};
  }
  if (name === 'get_government') {
    const c = await load(req, '/downloads/index.json'), gp = c.datasets.find(d => d.id === 'government-profiles');
    const rows = (gp ? (await datasetRows(req, gp)).rows : await load(req, '/downloads/government-profiles.json')).map(r => ({slug: (r.page || '').split('/').pop(), ...r}));
    if (!a.slug) return {governments: rows};
    const g = rows.find(r => r.slug === a.slug);
    if (!g) throw new Error(`Unknown government "${a.slug}". Valid: ${rows.map(r => r.slug).join(', ')}`);
    const gy = c.datasets.find(d => d.id === 'government-years');  // budget, tax rate, actuals, residents, debt, staff by fiscal year
    const all = gy ? (await datasetRows(req, gy)).rows : await load(req, '/downloads/government-years.json').catch(() => []);
    g.years = (all || []).filter(r => r.gov_id === g.gov_id).sort((x, y) => x.fiscal_year - y.fiscal_year);
    return g;
  }
  if (name === 'search_site') {
    const idx = await load(req, '/data/search.json');
    const words = String(a.q || '').toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) throw new Error('q is required');
    const hits = idx.filter(it => { const t = JSON.stringify(it).toLowerCase(); return words.every(w => t.includes(w)); })
      .map(it => [words.reduce((a, w) => a + (String(it.t || '').toLowerCase().includes(w) ? 10 : 0) + (String(it.s || '').toLowerCase().includes(w) ? 3 : 0), 0) + (it.u === '/developers' ? -20 : 0), it]).sort((a, b) => b[0] - a[0]).map(x => x[1]);
    return {query: a.q, total: hits.length, results: hits.slice(0, Math.min(a.limit || 10, 50)).map(it => ({type: it.k, title: it.t, summary: it.s, url: /^https?:/.test(it.u) ? it.u : SITE + it.u}))};
  }
  throw new Error(`Unknown tool "${name}"`);
}

const MAX_BATCH = 20;
// What a request is, for the request log.
function describe(m) {
  const p = (m && m.params) || {};
  return {endpoint: m && m.method === 'tools/call' ? `tools/call:${p.name}` : (m && m.method) || null,
    dataset: m && m.method === 'tools/call' && p.arguments ? p.arguments.id || p.arguments.slug || p.arguments.vendor || p.arguments.member || p.arguments.gov || null
      : m && m.method === 'resources/read' ? String(p.uri || '').replace(/^baycounty:\/\/datasets\//, '').slice(0, 80) || null : null,
    query: m && m.method === 'tools/call' ? JSON.stringify(p.arguments || {}).replace(/"api_key":"[^"]*"/, '') : null};
}

const ok = (id, result) => ({jsonrpc: '2.0', id, result});
const err = (id, code, message) => ({jsonrpc: '2.0', id, error: {code, message}});

// Any unexpected failure (e.g. the catalog can't be loaded) becomes a JSON-RPC error, not a 500.
async function handle(req, msg) {
  try { return await handle0(req, msg); }
  catch (e) { console.error('mcp', msg && msg.method, e.message); return err((msg && msg.id) ?? null, -32603, 'Internal error. Try again shortly.'); }
}

async function handle0(req, msg) {
  const {id, method, params = {}} = msg || {};
  if (!method) return err(id ?? null, -32600, 'Invalid request');
  if (id === undefined || id === null) return null; // notifications (e.g. notifications/initialized) get no response
  if (method === 'initialize') {
    const v = VERSIONS.includes(params.protocolVersion) ? params.protocolVersion : VERSIONS[0];
    return ok(id, {protocolVersion: v, capabilities: {tools: {listChanged: false}, resources: {listChanged: false, subscribe: false}},
      serverInfo: {name: 'baycounty-me', title: 'BayCounty.me', version: '1.0.0', websiteUrl: SITE},
      instructions: 'Public records for Bay County, Florida: local budgets, property taxes and exemptions, recorded votes, contracts, campaign money, 2026 candidates, public salaries, debt, audits and Hurricane Michael recovery. Use list_datasets, then query_dataset; upcoming_meetings, member_voting_record, vendor_profile and official_correspondence answer common questions directly, and each dataset is also a resource (baycounty://datasets/<id>). Always cite the source link on each row. BayCounty.me is neutral and does not endorse candidates.'});
  }
  if (method === 'ping') return ok(id, {});
  if (method === 'tools/list') return ok(id, {tools: TOOLS});
  if (method === 'tools/call') {
    try {
      const out = await call(req, params.name, params.arguments || {});
      if (out && typeof out.returned === 'number') req._rows = out.returned;
      return ok(id, {content: [{type: 'text', text: JSON.stringify(out)}], structuredContent: out, isError: false});
    } catch (e) {
      return ok(id, {content: [{type: 'text', text: e.message}], isError: true});
    }
  }
  if (method === 'resources/list') {
    const c = await load(req, '/downloads/index.json');
    return ok(id, {resources: c.datasets.map(d => ({uri: `baycounty://datasets/${d.id}`, name: d.id, title: d.title,
      description: `${d.description} (${d.rows} rows; columns: ${d.columns.map(x => x.name).join(', ')})`, mimeType: 'application/json'}))});
  }
  if (method === 'resources/templates/list') return ok(id, {resourceTemplates: [{uriTemplate: 'baycounty://datasets/{id}', name: 'dataset', title: 'A BayCounty.me dataset', description: 'Every row of one dataset (up to 2,000) as JSON. Use list_datasets for ids.', mimeType: 'application/json'}]});
  if (method === 'resources/read') {
    const m = String(params.uri || '').match(/^baycounty:\/\/datasets\/([a-z0-9-]+)$/);
    if (!m) return err(id, -32602, 'Unknown resource. Use baycounty://datasets/<id>.');
    const c = await load(req, '/downloads/index.json'), meta = c.datasets.find(d => d.id === m[1]);
    if (!meta) return err(id, -32002, `Resource not found: ${params.uri}`);
    const rows = (await datasetRows(req, meta)).rows, MAXR = 2000;
    req._rows = Math.min(rows.length, MAXR);
    return ok(id, {contents: [{uri: params.uri, mimeType: 'application/json', text: JSON.stringify({dataset: meta.id, title: meta.title, total: rows.length,
      truncated: rows.length > MAXR, full_download: `${SITE}${meta.json}`, rows: rows.slice(0, MAXR)})}]});
  }
  if (method === 'prompts/list') return ok(id, {prompts: []});
  return err(id, -32601, `Method not found: ${method}`);
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, DELETE');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version, Authorization');
  res.setHeader('Access-Control-Expose-Headers', 'Mcp-Session-Id');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method === 'GET') {
    if (String(req.headers.accept || '').includes('text/event-stream')) return res.status(405).json({error: 'This server does not offer a server-sent event stream.'});
    return res.status(200).json({name: 'BayCounty.me MCP server', transport: 'streamable-http', url: `${SITE}/api/mcp`, tools: TOOLS.map(t => t.name), docs: `${SITE}/developers#mcp`});
  }
  if (req.method === 'DELETE') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({error: 'Use POST'});
  let body = req.body;
  if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) { return res.status(400).json(err(null, -32700, 'Parse error')); } }
  // JSON-RPC batches: protocol 2025-06-18 removed them, but this server still accepts 2025-03-26 clients, which may
  // send them. Each request in a batch goes through the gate on its own (counted, throttled and logged like a single
  // request), so a batch can't be used to get around the limits. Batches are capped at MAX_BATCH requests.
  if (Array.isArray(body)) {
    if (!body.length) return res.status(400).json(err(null, -32600, 'Invalid request: empty batch'));
    if (body.length > MAX_BATCH) return res.status(400).json(err(null, -32600, `Batches are limited to ${MAX_BATCH} requests.`));
    const out = [];
    for (const m of body) {
      const isReq = m && m.method && m.id !== undefined && m.id !== null;
      if (!isReq) { const r = await handle(req, m); if (r) out.push(r); continue; } // notifications and invalid items do no work
      const ctx = await gate(req, res, 'mcp'), inf = describe(m);
      if (!ctx.ok) { await ctx.log({...inf, status: ctx.status}); out.push(err(m.id, ctx.status === 429 ? -32029 : -32001, ctx.message || 'Request not allowed.')); continue; }
      req._rows = null;
      const r = await handle(req, m);
      await ctx.log({...inf, status: 200, rows: req._rows});
      if (r) out.push(r);
    }
    return out.length ? res.status(200).json(out) : res.status(202).end();
  }
  const first = body || {};
  const info = describe(first);
  const isNote = first.id === undefined || first.id === null;
  const ctx = await gate(req, res, 'mcp');
  if (!isNote) instrument(res, ctx, info);
  if (!ctx.ok) return res.status(ctx.status).json(err(first.id ?? null, ctx.status === 429 ? -32029 : -32001, ctx.message || 'Request not allowed.'));
  const out = await handle(req, body);
  if (req._rows != null) info.rows = req._rows;
  return out ? res.status(200).json(out) : res.status(202).end();
};
module.exports.normVendor = normVendor;
module.exports.vendorMatch = vendorMatch;
module.exports.call = call;
module.exports.handle = handle;
