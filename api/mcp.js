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
   description: 'Profile of a Bay County local government: population, budget, tax rate, debt, audit findings, votes recorded, staff, utility bill and FEMA money. Omit slug to list all.',
   inputSchema: {type: 'object', additionalProperties: false, properties: {slug: {type: 'string', description: 'bay-county, bay-district-schools, panama-city, panama-city-beach, lynn-haven, callaway, springfield, parker or mexico-beach'}}},
   annotations: {readOnlyHint: true}},
  {name: 'search_site', title: 'Search BayCounty.me',
   description: 'Full-text search across every page and record on BayCounty.me. Returns titles, summaries and links.',
   inputSchema: {type: 'object', required: ['q'], additionalProperties: false, properties: {q: {type: 'string'}, limit: {type: 'integer', minimum: 1, maximum: 50, default: 10}}},
   annotations: {readOnlyHint: true}},
];

async function call(req, name, a = {}) {
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

const ok = (id, result) => ({jsonrpc: '2.0', id, result});
const err = (id, code, message) => ({jsonrpc: '2.0', id, error: {code, message}});

async function handle(req, msg) {
  const {id, method, params = {}} = msg || {};
  if (!method) return err(id ?? null, -32600, 'Invalid request');
  if (id === undefined || id === null) return null; // notifications (e.g. notifications/initialized) get no response
  if (method === 'initialize') {
    const v = VERSIONS.includes(params.protocolVersion) ? params.protocolVersion : VERSIONS[0];
    return ok(id, {protocolVersion: v, capabilities: {tools: {listChanged: false}},
      serverInfo: {name: 'baycounty-me', title: 'BayCounty.me', version: '1.0.0', websiteUrl: SITE},
      instructions: 'Public records for Bay County, Florida: local budgets, property taxes and exemptions, recorded votes, contracts, campaign money, 2026 candidates, public salaries, debt, audits and Hurricane Michael recovery. Use list_datasets, then query_dataset. Always cite the source link on each row. BayCounty.me is neutral and does not endorse candidates.'});
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
  if (method === 'resources/list') return ok(id, {resources: []});
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
  const first = Array.isArray(body) ? null : body || {};
  const p = (first && first.params) || {};
  const info = {endpoint: !first ? 'batch' : first.method === 'tools/call' ? `tools/call:${p.name}` : first.method,
    dataset: first && first.method === 'tools/call' && p.arguments ? p.arguments.id || p.arguments.slug || null : null,
    query: first && first.method === 'tools/call' ? JSON.stringify(p.arguments || {}).replace(/"api_key":"[^"]*"/, '') : null};
  const isNote = first && (first.id === undefined || first.id === null);
  const ctx = await gate(req, res, 'mcp');
  if (!isNote) instrument(res, ctx, info);
  if (!ctx.ok) return res.status(ctx.status).json(err(first ? first.id ?? null : null, ctx.status === 429 ? -32029 : -32001, ctx.message || 'Request not allowed.'));
  if (Array.isArray(body)) {
    const out = (await Promise.all(body.map(m => handle(req, m)))).filter(Boolean);
    return out.length ? res.status(200).json(out) : res.status(202).end();
  }
  const out = await handle(req, body);
  if (req._rows != null) info.rows = req._rows;
  return out ? res.status(200).json(out) : res.status(202).end();
};
