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
//   GET /api/v1/correspondence?year=    published emails with officials (year=all for every year)
//   GET /api/v1/pages[?path=]           which datasets and endpoints hold each site page's data
//   GET /api/v1/entities?q=&kind=       find a company, official, candidate, nonprofit, board member or business
//   GET /api/v1/entities/{id}           one entity's profile and every documented connection (api/_entities.js)
//   GET /api/v1/budget-compare?gov=&from=&to=&basis=   one government's budget in two fiscal years, line by line (api/_budget.js)
//   GET /api/v1/checkbook?gov=&fy=      one government's payments in a fiscal year: by month, payee and fund (api/_openbooks.js)
//   GET /api/v1/budget-actual?gov=&fy=&as_of=   spending and revenue against the budget, by department (api/_openbooks.js)
//   GET /api/v1/officials?gov=&year=&date=  who held each elected seat in a fiscal year or on a date (api/_officials.js)
//   GET /api/v1/import-progress         how far the minutes backfill has got, per board and year (api/_progress.js)
//   GET /api/v1/schools?address=|lat=&lon=  the elementary, middle and high school zoned for a place (api/_schools.js)
//   GET /api/v1/emergency               live weather alerts, evacuation orders, shelters, boil-water notices, road closures (api/_emergency_feed.js)
//   GET /api/v1/emergency-timeline?days=&kind=&gov=  every alert of the last days: started, ended, people reached (api/_emergency_feed.js)
//   GET /api/v1/evacuation-zone?address= (or ?lat=&lng=)  the hurricane evacuation zone for a Bay County address
//   GET /api/v1/utilities?lat=&lon=     water, sewer, power, gas, trash provider and pickup days at an address (api/_utilities.js)
//   GET /api/v1/address-report?address=|lat=&lon=  everything on file for one address, by section (api/_address_report.js)
//   GET /api/v1/nearby?address=|lat=&lon=&radius_mi=  what's happening near a place: alerts, meetings, events, work nearby (api/_nearby.js)
//   GET /api/v1/overlaps?section=&gov=  live overlaps: officials' businesses and nonprofits in their votes, checkbook donors, split purchases (api/_overlaps.js)
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
    info: {title: 'BayCounty.me API', version: '1.2.0', description: 'Read-only access to Bay County, Florida public records compiled by BayCounty.me: budgets, taxes, votes, contracts, campaign money, salaries, elections and more. No key needed. Every row carries a link to its source record. Individual donors and rank-and-file employees are never named. Responses carry an ETag (and Last-Modified where known); send If-None-Match or If-Modified-Since to get 304 Not Modified.', contact: {url: `${SITE}/about#contact`}},
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
      '/governments/{slug}': {get: {operationId: 'getGovernment', summary: 'One government profile, with its budget, tax rate, audited actuals, residents, debt and staff for each fiscal year on record (years)', parameters: [{name: 'slug', in: 'path', required: true, schema: {type: 'string', example: 'lynn-haven'}}], responses: {200: {description: 'Profile'}, 404: {description: 'Unknown government'}}}},
      '/import-progress': {get: {operationId: 'importProgress', summary: 'How far loading every board\'s meeting minutes since 2016 has got: files found in each archive, downloaded, read into motions and checked, per board and year, with the estimated time left',
        responses: {200: {description: '{installed, phase, stages: [...], totals, eta, last, runs: [...], boards: [{board, gov, name, note, totals, years: [{year, listed, found, captured, read, motions, passed, flagged, state}]}]}'}}}},
      '/status': {get: {operationId: 'status', summary: 'Rows per dataset, last database sync and load errors', responses: {200: {description: '{database, last_sync, errors: [...], datasets: [{id, rows_published, rows_in_database, last_ingest, error}]}'}}}},
      '/changes': {get: {operationId: 'changes', summary: 'Records added to the database since a time',
        description: 'Uses each record\'s created_at (when the database first saw it). An edited record counts as new; removed records are not listed.',
        parameters: [{name: 'since', in: 'query', required: true, description: 'ISO date or time, e.g. 2026-10-01 or 2026-10-01T12:00:00Z', schema: {type: 'string'}},
          p('dataset', 'Comma-separated dataset ids (default: all)'), p('limit', 'Records per dataset (default 500, max 1000)', {type: 'integer'})],
        responses: {200: {description: '{since, total, datasets: [{dataset, total, returned, data}]}'}, 400: {description: 'Missing or invalid since'}}}},
      '/meetings.ics': {get: {operationId: 'meetingsCalendar', summary: 'Upcoming meetings as an iCalendar feed',
        parameters: [p('gov', 'Government key(s) or board id(s), comma-separated: county, schools, pc, pcb, lh, cw, sp, parker, mb, or a board such as lh-cra. Default: all')],
        responses: {200: {description: 'text/calendar', content: {'text/calendar': {schema: {type: 'string'}}}}}}},
      '/correspondence': {get: {operationId: 'correspondence', summary: 'Published emails between BayCounty.me and local officials',
        description: 'Each conversation is one letter sent to one or more officials, with every published reply. Unpublished threads are never returned. Defaults to the latest year that has letters.',
        parameters: [p('year', 'A year such as 2026, or all for every year. Default: the latest year with letters'), p('government', 'Only letters to this government, as shown in the governments list of the response')],
        responses: {200: {description: '{year, years, governments, total, conversations: [{subject, sent_at, governments, replies, threads: [{official, seat, government, status, messages: [{direction, text, at}]}]}]}'}}}},
      '/pages': {get: {operationId: 'pages', summary: 'Which datasets and endpoints hold the data behind each page on BayCounty.me',
        parameters: [p('page', 'One page path, e.g. /connections. Omit for every page')],
        responses: {200: {description: '{data: [{page, url, datasets: [{id, api}], endpoints, none, note}]}'}, 404: {description: 'Unknown page'}}}},
      '/entities': {get: {operationId: 'findEntities', summary: 'Find a company, official, candidate, nonprofit, board member, business or government by name',
        parameters: [{name: 'q', in: 'query', required: true, description: 'Part of a name', schema: {type: 'string'}}, p('kind', 'gov, vendor, person, nonprofit, member, owner, business or committee'), p('limit', 'Results (default 20, max 100)', {type: 'integer'})],
        responses: {200: {description: '{data: [{entity_id, kind, name, subtitle, page_url, connections, amount_received, amount_given}]}'}}}},
      '/entities/{id}': {get: {operationId: 'getEntity', summary: 'One entity\'s profile and every documented connection: payments, contracts, campaign gifts from organizations, votes, board seats, businesses, grants',
        description: 'Ids look like kind:key: gov:pc, vendor:dewberry, person:douglas-moore, nonprofit:np-912189932, member:b_082417524d2f, owner:p_386a78b32ad7, business:p20000052616, committee:<slug>. Officials on nonprofit boards, officials\' businesses and shared-owner gifts appear only after an admin checks the match by hand (checked_by_hand). Individual campaign donors are named only when they run a registered business (owner: ids, same name and street address on Sunbiz).',
        parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'string', example: 'vendor:dewberry'}}],
        responses: {200: {description: '{data: {entity (a person or board member with a published photo, from their government or chamber, has entity.photo: {url, credit, source_url}; dataset person-photos), connections: [{relation, label, direction, other: {entity_id, name, kind, page_url, photo (a person\'s photo URL, when there is one)}, amount, records, first_date, last_date, detail, source_url, dataset}], counts}}'}, 404: {description: 'Unknown entity'}}}},
      '/budget-compare': {get: {operationId: 'compareBudgetYears', summary: 'Compare one government\'s budget in two fiscal years: totals, funds, General Fund departments and services (or audited revenue and spending), with dollar and percent changes',
        description: 'Without gov, lists every government and the years on record (adopted_totals, adopted_detail, actual). With gov, compares two years; from and to default to the latest year with line-by-line detail and the one before it. Each line: {key, name, from, to, change, pct, status: both|added|removed}. Lines are matched across years by department or fund number where the budget gives one, else by name. Data: the budget-years dataset.',
        parameters: [p('gov', 'Government id: county, schools, pc, pcb, lh, cw, sp, parker, mb'), p('from', 'Earlier fiscal year, e.g. 2025 (the year the fiscal year ends)', {type: 'integer'}), p('to', 'Later fiscal year, e.g. 2026', {type: 'integer'}),
          p('basis', 'adopted (default): adopted budgets. actual: audited revenue and spending', {type: 'string', enum: ['adopted', 'actual']})],
        responses: {200: {description: '{government, gov_id, basis, from, to, years, detail_years, totals: [line], sections: {department, fund, service} or {spending, revenue}: [line], history: [{fiscal_year, total, general_fund}], biggest_increase, biggest_decrease, notes, sources: {from, to}} or, without gov, {governments: [...]}'},
          400: {description: 'A year with no budget on record'}, 404: {description: 'Unknown government, or fewer than two years on record'}}}},
      '/officials': {get: {operationId: 'officialsInOffice', summary: 'Who held each elected seat on one government in a fiscal year or on a date: mayor, commissioners or council members, school board and superintendent, and the appointed county or city manager',
        description: 'Without gov, lists the governments and their seats. With gov, returns every seat and each person who held it during the period (year = the fiscal year, the year it ends: FY2019 = Oct 2018 to Sep 2019, schools Jul to Jun), on a date, or today when neither is given. part_of_period marks someone who joined or left during the year. vacant true means nobody held the seat; confirmed false is a stretch nobody could confirm from the records found. Each holder has person_id (profile: /people/<id>) and the term\'s source. Data: the officeholder-terms dataset, 2016 on (the first year the site covers); years before 2016 return 400.',
        parameters: [p('gov', 'Government id: county, schools, pc, pcb, lh, cw, sp, parker, mb'), p('year', 'Fiscal year, e.g. 2019 (the year it ends)', {type: 'integer'}), p('date', 'A date (YYYY-MM-DD) instead of a year')],
        responses: {200: {description: '{data: {gov_id, government, body, place_id, fiscal_year, from, to, seats: [{seat, appointed, holders: [{person_name, person_id, vacant, confirmed, start_date, end_date, start_approx, end_approx, how, part_of_period, note, source_title, source_url}]}], note}} or, without gov, {data: [{gov_id, government, body, seats, unconfirmed}]}'},
          400: {description: 'A bad year or date'}, 404: {description: 'Unknown government'}}}},
      '/overlaps': {get: {operationId: 'overlaps', summary: 'Live overlaps between records: an official\'s own business or nonprofit named in a vote they cast, checkbook payees that gave to a campaign, and payments just under a purchasing threshold',
        description: 'Joins that use hand-confirmed matches (official-businesses, nonprofit-officials) or rows only the database holds (checkbook-payments, school-grades, school-spending). Sections: official_business_votes (an official\'s registered business named in a motion they voted on, with what their own government paid it), nonprofit_board_money (a nonprofit with an official on its board: payments from that official\'s government and their votes naming it), checkbook_donors (checkbook payees that gave to a local campaign, or whose owners did), split_purchases (two or more payments to one payee within 30 days, each at least 90% of a common threshold: thresholds lists them) and school_spending_grades. Each section is {rows, error}. Individual donors are never named. The other overlaps are datasets: vote-mentions, donor-votes, agenda-parties, development-companies, bid-trail, shared-owner-vendors, chamber-overlaps, emergency-purchase-donors and campaign-results. A row puts two public records side by side; it is not a finding of wrongdoing.',
        parameters: [p('section', 'One section: official_business_votes, nonprofit_board_money, checkbook_donors, split_purchases or school_spending_grades'), p('gov', 'Only one government: county, schools, pc, pcb, lh, cw, sp, parker, mb')],
        responses: {200: {description: '{data: {official_business_votes: {rows, error}, nonprofit_board_money: {rows, error}, checkbook_donors: {rows, error}, split_purchases: {rows, error}, school_spending_grades: {rows, error}}, thresholds, note}'},
          400: {description: 'Unknown section'}}}},
      '/checkbook': {get: {operationId: 'checkbook', summary: 'One government\'s payments in a fiscal year, from its own check register: total, by month, top payees, by fund and payment method, the largest payments',
        description: 'Without gov, uses the first government that has published its check register; fy defaults to its latest fiscal year. Every payment is in the checkbook-payments dataset (filter it with gov_id and fiscal_year). Voided checks are left out; payments to private individuals are counted but not named. When nothing is published yet, governments is empty.',
        parameters: [p('gov', 'Government id: county, schools, pc, pcb, lh, cw, sp, parker, mb'), p('fy', 'Fiscal year, the year it ends (e.g. 2026 for Oct 2025 to Sep 2026)', {type: 'integer'})],
        responses: {200: {description: '{data: {government, gov_id, fiscal_year, fiscal_years, governments: [{gov_id, government, fiscal_years, through}], from, through, total, payments, payees, by_month: [{month, total, payments}], top_payees: [{payee, payee_entity_id, total, payments, first, last}], by_fund, by_method, individuals: {total, payments}, largest, source_files, note}}'},
          400: {description: 'A fiscal year that is not published'}, 404: {description: 'A government with nothing published'}}}},
      '/budget-actual': {get: {operationId: 'budgetActual', summary: 'One government\'s spending and revenue against its budget, by department, as of a month end, from its own budget-vs-actual report',
        description: 'Spent = spending to date plus open purchase orders. used is spent / budget; elapsed is the share of the fiscal year gone by as_of, so a department whose used runs well past elapsed is spending ahead of the year. months has the totals for every report published that year. Lines: the budget-actuals dataset.',
        parameters: [p('gov', 'Government id: county, schools, pc, pcb, lh, cw, sp, parker, mb'), p('fy', 'Fiscal year, the year it ends', {type: 'integer'}), p('as_of', 'Report date (YYYY-MM-DD). Default: the latest report of that year')],
        responses: {200: {description: '{data: {government, gov_id, fiscal_year, fiscal_years, governments, as_of, as_ofs, elapsed, totals: {original, budget, actual, encumbered, spent, used}, departments: [{name, fund, original, budget, actual, encumbered, spent, used, amended, lines: [...]}], over_budget, running_ahead, revenue: {budget, collected, sources}, months: [{as_of, elapsed, budget, spent, used, revenue_budget, revenue_collected}], source_files, note}}'},
          400: {description: 'A fiscal year or report date that is not published'}, 404: {description: 'A government with nothing published'}}}},
      '/schools': {get: {operationId: 'zonedSchools', summary: 'The elementary, middle and high school zoned for an address or point, with each school\'s latest state grade, enrollment and per-student spending',
        description: 'Give address (a street address in the county: house number and street) or lat and lon. Without either, lists every open public school. Zones come from the school district via the county GIS server (the school-zones dataset); school details from the schools dataset. A point in an MOU zone (covered by a separate agreement) is flagged mou_area. Choice, magnet, charter and virtual schools take students from outside their zone.',
        parameters: [p('address', 'Street address, e.g. 1200 Harrison Ave, Panama City'), p('lat', 'Latitude (decimal degrees)', {type: 'number'}), p('lon', 'Longitude (decimal degrees)', {type: 'number'})],
        responses: {200: {description: '{data: {lat, lon, inside_district, elementary: {zone, zone_id, mou_area, zone_last_edited, school: {school_id, name, level, grades, charter, address, city, phone, enrollment, enrollment_year, latest_grade, latest_grade_year, latest_per_student, latest_spending_year, page_url}}, middle, high, note}, matched_address} or, with no location, {data: [school]}'},
          400: {description: 'A bad location or an address with no house number'}, 404: {description: 'No matching address'}}}},
      '/emergency': {get: {operationId: 'emergencyNow', summary: 'What is happening now: National Weather Service watches and warnings, evacuation orders, open shelters, boil-water notices, road closures and water outages for Bay County',
        description: 'Live notices, checked every 5 minutes from the National Weather Service, the county and city alert centers and news, FL511 and the county shelter page; most serious first. headline is one sentence for the whole county. counts has the number of live notices per kind (evacuation, weather, shelter, boil-water, road, utility, storm). shelters lists every county shelter with its latest posted status. zones lists evacuation zones A to D and whether an order names each. A notice its source posted twice (re-posted with an update) is one notice: the newest version, with first_posted (when the first version was posted) and versions (every version, newest first). Past notices: the emergency-notices dataset.',
        parameters: [p('kind', 'Only one kind of notice: evacuation, weather, shelter, boil-water, road, utility, storm, safety', {type: 'string'})],
        responses: {200: {description: '{place, checked_at, data_source, headline, counts, shelters_open, notices: [{notice_id, kind, source, gov_id, title, summary, instruction, severity, event, area, zones, issued, starts, ends, status, full_closure, roadway, url, page}], shelters: [{shelter_id, name, address, type, group, status, status_as_of, lat, lng, evacuation_zone}], zones: [{zone, where_it_is, when_ordered, plain, ordered}], sources_ok, source_errors, links, note}'}}}},
      '/emergency-timeline': {get: {operationId: 'emergencyTimeline', summary: 'Every emergency alert of the last days (up to 90): when each started and ended, and how many phones and inboxes it was sent to',
        description: 'The alert history behind the timeline on /emergency: weather warnings, evacuation orders, public safety alerts from FEMA IPAWS, shelter openings, boil-water notices, road closures and outages, newest first. reach counts how many people each channel (push, email, sms) sent it to; counts only, nobody is named. gov keeps one government\'s notices plus the countywide ones that reach it (weather, IPAWS, shelters).',
        parameters: [p('days', 'How many days back, 1 to 90 (default 30)', {type: 'integer'}), p('kind', 'One kind: evacuation, weather, shelter, boil-water, road, utility, storm, safety', {type: 'string'}),
          p('gov', 'One government: county, pc, pcb, lh, cw, sp, parker, mb', {type: 'string'})],
        responses: {200: {description: '{place, days, kind, gov, total, counts, labels, governments, reached, items: [{notice_id, kind, label, title, event, severity, source, source_type, gov_id, zones, area, started, ended, active, status, reach: {push, email, sms}, people, url, page}], note}'}}}},
      '/evacuation-zone': {get: {operationId: 'evacuationZone', summary: 'The hurricane evacuation zone (A to D, or none) for a Bay County street address or map point, any evacuation order now in effect for it, and the three nearest shelters',
        description: 'The address is matched to Bay County\'s address points (house number and street; city and ZIP are ignored), then to the county\'s evacuation zone map.',
        parameters: [p('address', 'Street address, e.g. 825 Ohio Ave'), p('lat', 'Latitude (instead of address)', {type: 'number'}), p('lng', 'Longitude', {type: 'number'})],
        responses: {200: {description: '{query, found, address: {address, community, zip, lat, lng}, zone, in_zone, zone_info, what_to_do, orders_now: [{title, zones, includes_you}], nearest_shelters: [{name, address, type, status, miles}], map, source_url, note}'}, 400: {description: 'No address or point given'}}}},
      '/utilities': {get: {operationId: 'utilitiesAtAddress', summary: 'Who provides water, sewer, electricity, natural gas, garbage, yard waste and recycling at an address, its trash pickup days, holiday changes and the rates its utilities charge',
        description: 'Give lat and lon, or address (house number and street). The city comes from the county\'s boundary map; garbage and yard waste routes and days are read live from each city\'s route map where it publishes one (from_map true), otherwise the city\'s rule is returned (for example a private hauler sets the day). An electric co-op is listed only where its mapped territory covers the point; co-op and FPL lines can share a neighborhood, so the bill is the sure answer. Nothing about the search is stored. Rows: utility-providers, trash-pickup, trash-holidays and utility-rates datasets.',
        parameters: [p('lat', 'Latitude, decimal degrees', {type: 'number'}), p('lon', 'Longitude, decimal degrees', {type: 'number'}), p('address', 'A street address instead of lat/lon, e.g. 825 Ohio Ave')],
        responses: {200: {description: '{data: {point: {lat, lon}, address, other_matches, boundary, place_id, area, area_name, gov_id, services: [{service, service_label, providers: [{provider, entity_id, provider_kind, coverage, phone, website, outage_url, notes, source_url}]}], pickup: [{service, service_label, provider, zone, days, zone_area, rule, from_map, notes, source_url}], holidays: [{provider, holiday, when_observed, garbage, yard_waste, source_url}], rates: [{provider, service, charge, amount, unit, applies_to, effective, notes, source_url}], note}}'},
          400: {description: 'Missing or bad lat/lon or address'}, 404: {description: 'No address found, or the point is outside the county'}, 502: {description: 'The county map server did not answer'}}}},
      '/address-report': {get: {operationId: 'addressReport', summary: 'Everything BayCounty.me has for one address: the property and its recent sales, a property tax estimate with every taxing authority, flood and evacuation zones, zoned schools, utilities and trash day, zoning and development nearby, road and sales tax projects nearby, parks and beaches, nearby services, who represents it, and what is coming up',
        description: 'Give address (house number and street; add zip to narrow it) or lat and lon (optionally parcel, the Property Appraiser parcel id). The answer is a list of sections, each with status ok, partial, none (nothing on file), pending (its data is not published yet) or error (a live map server did not answer). Parcel facts, district boundaries and representatives are read live from the county GIS server and the flood zone from FEMA; the tax estimate uses the tax-districts and property-tax-rates datasets. Owner names, mailing addresses and buyer or seller names are never returned, and sales before 2016 are left out. The address you send is not logged. The realtor console at /realtor prints this report as a branded PDF.',
        parameters: [p('address', 'Street address, e.g. 825 Ohio Ave, Lynn Haven'), p('zip', 'ZIP code, to narrow an address'), p('lat', 'Latitude (decimal degrees)', {type: 'number'}), p('lon', 'Longitude (decimal degrees)', {type: 'number'}), p('parcel', 'Property Appraiser parcel id, with lat/lon'), p('place', 'Place id (default fl-bay)')],
        responses: {200: {description: '{data: {place_id, address, city, zip, lat, lon, parcel_id, jurisdiction, generated_at, other_matches, sections: [{id, title, status, data, note, sources: [{label, url}]}], note}}. Section ids: property, tax, hazards, schools, utilities, zoning, roads, outdoors, services, officials.'},
          400: {description: 'No address or a bad location'}, 404: {description: 'No matching address, or a point outside the county'}, 502: {description: 'The county address service did not answer'}}}},
      '/nearby': {get: {operationId: 'nearby', summary: 'What is happening near a place: emergency alerts that reach it, trash day, today\'s beach flag, public meetings of its governments, things to do, building, development, road work and agenda items nearby, public notices, restaurant inspections and new businesses in its ZIP',
        description: 'Give address (house number and street) or lat and lon. The city and evacuation zone come from the county map; alerts include an evacuation order only when it names the zone (or no zone), and boil-water or road notices only from the city or the county. Work nearby is within radius_mi of the point, nearest first. Every item links to its public record. This is what a signed-in resident sees on My home at /account. The address you send is not logged. Rows: meetings, community-events, development-projects, sales-tax-projects, road-contracts, public-notices, restaurant-inspections, restaurants, new-businesses, beach-conditions and beach-access datasets, plus the live emergency feed.',
        parameters: [p('address', 'Street address, e.g. 825 Ohio Ave'), p('lat', 'Latitude (decimal degrees)', {type: 'number'}), p('lon', 'Longitude (decimal degrees)', {type: 'number'}),
          p('radius_mi', 'How far "nearby" reaches: 0.25, 0.5, 1 (default), 2 or 5 miles', {type: 'number'}), p('days', 'Days ahead for meetings and events (default 14, max 31)', {type: 'integer'}),
          p('topics', 'Comma list of sections besides alerts: meetings, events, projects, notices, food, business (default all)')],
        responses: {200: {description: '{data: {place_id, today, city, zip, gov_id, local_government, zone, radius_mi, address, lat, lon, today_card: {trash: [{service, days, provider}], beach: {flag, rip_current_risk, water_temperature, miles_to_beach, url}, alerts}, governments: [{gov_id, name, url}], sections: [{id, title, count?, items: [{kind, title, detail, date, url, miles?, entity_id?}], empty}], note}}. Section ids: alerts, meetings, events, projects, notices, food, business.'},
          400: {description: 'No address or a bad location'}, 404: {description: 'No matching address, or a point outside the county'}}}},
      '/search': {get: {operationId: 'searchSite', summary: 'Search every page on BayCounty.me', parameters: [{name: 'q', in: 'query', required: true, schema: {type: 'string'}}, p('limit', 'Results (default 20, max 100)', {type: 'integer'})], responses: {200: {description: 'Results'}}}},
    },
  };
}

// An address lookup never logs where someone lives: lat, lon and address are dropped from the request log.
const PRIVATE_Q = q => Object.fromEntries(Object.entries(q || {}).filter(([k]) => !['lat', 'lon', 'lng', 'address'].includes(k)));
// The four utilities datasets /utilities and the MCP tool read.
async function utilityData(req, catalog) {
  const rows = async id => { const m = catalog.datasets.find(d => d.id === id); return m ? (await datasetRows(req, m)).rows : []; };
  const [providers, trash, holidays, rates] = await Promise.all(['utility-providers', 'trash-pickup', 'trash-holidays', 'utility-rates'].map(rows));
  return {providers, trash, holidays, rates};
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
  // An address report (and a utilities lookup) never logs where someone looked: address, lat, lon and parcel are dropped from the request log.
  const logQuery = parts[0] === 'address-report' || parts[0] === 'nearby' ? Object.fromEntries(Object.entries(req.query || {}).filter(([k]) => !['address', 'lat', 'lon', 'lng', 'parcel', 'zip', 'label'].includes(k))) : parts[0] === 'utilities' ? PRIVATE_Q(req.query) : req.query;
  const info = {endpoint: path || 'index', dataset: parts[0] === 'datasets' ? parts[1] || null : null, query: cleanQuery(logQuery)};
  instrument(res, ctx, info);
  conditional(req, res);
  if (!ctx.ok) return res.status(ctx.status).json({error: ctx.message || 'Request not allowed.', reason: ctx.reason, docs: `${SITE}/developers#keys`});
  try {
    const catalog = await load(req, '/downloads/index.json');
    if (catalog.updated) res.locals.lastModified = new Date(catalog.updated + 'T00:00:00Z');
    if (!parts.length) return res.status(200).json({
      name: 'BayCounty.me API', version: 'v1', updated: catalog.updated, docs: `${SITE}/developers`, openapi: `${SITE}/api/v1/openapi.json`, mcp: `${SITE}/api/mcp`,
      endpoints: {datasets: `${SITE}/api/v1/datasets`, governments: `${SITE}/api/v1/governments`, search: `${SITE}/api/v1/search?q=`,
        entities: `${SITE}/api/v1/entities?q=`, budget_compare: `${SITE}/api/v1/budget-compare?gov=lh&from=2025&to=2026`, checkbook: `${SITE}/api/v1/checkbook?gov=lh`, budget_actual: `${SITE}/api/v1/budget-actual?gov=lh`, officials: `${SITE}/api/v1/officials?gov=lh&year=2019`, schools: `${SITE}/api/v1/schools?address=1200 Harrison Ave`, emergency: `${SITE}/api/v1/emergency`, evacuation_zone: `${SITE}/api/v1/evacuation-zone?address=825+Ohio+Ave`, utilities: `${SITE}/api/v1/utilities?address=825+Ohio+Ave`, address_report: `${SITE}/api/v1/address-report?address=825+Ohio+Ave`, nearby: `${SITE}/api/v1/nearby?address=825+Ohio+Ave`, status: `${SITE}/api/v1/status`, import_progress: `${SITE}/api/v1/import-progress`, changes: `${SITE}/api/v1/changes?since=`, meetings_calendar: `${SITE}/api/v1/meetings.ics?gov=`},
      license: catalog.license, datasets: catalog.datasets.map(d => ({id: d.id, title: d.title, rows: d.rows, url: `${SITE}/api/v1/datasets/${d.id}`}))});
    if (parts[0] === 'openapi.json') return res.status(200).json(openapi(catalog));
    if (parts[0] === 'status') { res.locals.lastModified = null; return res.status(200).json(await status(catalog)); }
    if (parts[0] === 'import-progress') { res.locals.lastModified = null; return res.status(200).json(await require('./_progress').publicProgress(rest)); }
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
      if (g) {  // the profile plus its figures for every fiscal year on record (the page's top cards, by year)
        const gy = catalog.datasets.find(d => d.id === 'government-years');
        const all = gy ? (await datasetRows(req, gy)).rows : await load(req, '/downloads/government-years.json').catch(() => []);
        g.years = (all || []).filter(r => r.gov_id === g.gov_id).sort((a, b) => a.fiscal_year - b.fiscal_year);
      }
      return g ? res.status(200).json({data: g}) : res.status(404).json({error: `Unknown government "${parts[1]}".`, governments: withSlug.map(r => r.slug)});
    }
    if (parts[0] === 'pages') {
      const {PAGES, PREFIXES} = require('./_pages');
      const known = new Set(catalog.datasets.map(d => d.id));
      const one = (page, s) => ({page, url: SITE + page, datasets: (s.datasets || []).filter(id => known.has(id)).map(id => ({id, api: `${SITE}/api/v1/datasets/${id}`})),
        endpoints: (s.endpoints || []).map(e => `${SITE}/api/v1${e}`), none: s.none || null, note: s.note || null});
      const all = [...Object.entries(PAGES), ...Object.entries(PREFIXES).map(([k, v]) => [k + '{slug}', v])].map(([k, v]) => one(k, v));
      const want = String(req.query.page || req.query.p || '').replace(/\/+$/, '') || null;
      if (want) {
        const s = require('./_pages').sourceFor(want);
        return s ? res.status(200).json({data: one(want, s)}) : res.status(404).json({error: `Unknown page "${want}".`});
      }
      return res.status(200).json({data: all});
    }
    if (parts[0] === 'entities') {
      const E = require('./_entities');
      res.locals.lastModified = null;
      if (parts.length === 1) {
        const rows = await E.searchEntities(req, catalog, {q: req.query.q, kind: req.query.kind, limit: req.query.limit});
        info.rows = rows.length;
        return res.status(200).json({query: String(req.query.q || ''), data: rows.map(r => ({...r, url: SITE + r.page_url}))});
      }
      const d = await E.getEntity(req, catalog, decodeURIComponent(parts.slice(1).join('/')));
      info.rows = d.connections.length;
      return res.status(200).json({data: d});
    }
    if (parts[0] === 'budget-compare') {
      const B = require('./_budget');
      const meta = catalog.datasets.find(d => d.id === 'budget-years');
      const rows = meta ? (await datasetRows(req, meta)).rows : await load(req, '/downloads/budget-years.json');
      if (!req.query.gov && !req.query.government) return res.status(200).json({data: B.coverage(rows), note: 'Add ?gov=<gov_id>&from=<year>&to=<year> to compare two years.'});
      try { const r = B.compare(rows, req.query); info.rows = r.sections ? Object.values(r.sections).reduce((a, s) => a + s.length, 0) : 0; return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message, ...e.extra}); throw e; }
    }
    if (parts[0] === 'address-report') {
      res.locals.lastModified = null;
      const A = require('./_address_report');
      const rowsOf = async id => { const m = catalog.datasets.find(d => d.id === id); return m ? (await datasetRows(req, m)).rows : null; };
      try { const r = await A.forRequest(req.query, {catalog, rowsOf, file: f => load(req, f)}); info.rows = r.sections.length; return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message}); throw e; }
    }
    if (parts[0] === 'nearby') {
      res.locals.lastModified = null;
      const rowsOf = async id => { const m = catalog.datasets.find(d => d.id === id); return m ? (await datasetRows(req, m)).rows : null; };
      try { const r = await require('./_nearby').forRequest(req, catalog, req.query, {rowsOf}); info.rows = r.sections.reduce((a, s) => a + s.items.length, 0); return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message}); throw e; }
    }
    if (parts[0] === 'officials') {
      const O = require('./_officials');
      const meta = catalog.datasets.find(d => d.id === 'officeholder-terms');
      const rows = meta ? (await datasetRows(req, meta)).rows : await load(req, '/downloads/officeholder-terms.json');
      if (!req.query.gov && !req.query.government) return res.status(200).json({data: O.governments(rows), note: 'Add ?gov=<gov_id>&year=<fiscal year> (or &date=YYYY-MM-DD) for who held each seat.'});
      try { const r = O.inOffice(rows, req.query); info.rows = r.seats.reduce((a, x) => a + x.holders.length, 0); return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message}); throw e; }
    }
    if (parts[0] === 'schools') {
      const S = require('./_schools');
      const rowsOf = async id => { const m = catalog.datasets.find(d => d.id === id); return m ? (await datasetRows(req, m)).rows : load(req, `/downloads/${id}.json`); };
      const schools = await rowsOf('schools');
      try {
        let lat = req.query.lat, lon = req.query.lon, matched = null;
        if (req.query.address && (lat == null || lon == null)) {
          const hits = await S.geocode(req.query.address);
          if (!hits.length) return res.status(404).json({error: `No address in the county matches "${String(req.query.address).slice(0, 120)}".`});
          ({lat, lon} = hits[0]); matched = hits[0];
        }
        if (lat == null || lon == null) { const list = S.summary(schools); info.rows = list.length; return res.status(200).json({data: list, note: 'Add ?address= or ?lat=&lon= for the zoned schools.'}); }
        const r = S.zonedAt(await rowsOf('school-zones'), schools, lat, lon);
        info.rows = 3;
        return res.status(200).json({data: r, matched_address: matched});
      } catch (e) { if (e.expose) return res.status(e.status).json({error: e.message}); throw e; }
    }
    if (parts[0] === 'utilities') {
      // Who provides each utility at one address, and its trash pickup days. Read live from public map layers; nothing stored.
      res.locals.lastModified = null;
      const U = require('./_utilities');
      if (!req.query.lat && !req.query.lon && !req.query.address) return res.status(200).json({note: 'Add ?lat=&lon= (or ?address=825 Ohio Ave) for one address. Every provider, route and rate is in the utility-providers, trash-pickup, trash-holidays and utility-rates datasets.'});
      const D = await utilityData(req, catalog);
      try { const r = await U.lookup(D, req.query); info.rows = r.services.length + r.pickup.length; return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message}); throw e; }
    }
    if (parts[0] === 'overlaps') {
      res.locals.lastModified = null;
      const r = await require('./_overlaps').overlaps(req.query);
      info.rows = Object.values(r.data).reduce((a, x) => a + x.rows.length, 0);
      return res.status(200).json(r);
    }
    if (parts[0] === 'checkbook' || parts[0] === 'budget-actual') {
      // Each government's own accounting, as published from its finance files. Rows can change any time a file is published.
      const O = require('./_openbooks');
      res.locals.lastModified = null;
      const id = parts[0] === 'checkbook' ? 'checkbook-payments' : 'budget-actuals';
      const meta = catalog.datasets.find(d => d.id === id);
      const rows = meta ? (await datasetRows(req, meta)).rows : [];
      try { const r = parts[0] === 'checkbook' ? O.checkbook(rows, req.query) : O.budgetActual(rows, req.query); return res.status(200).json({data: r}); }
      catch (e) { if (e.expose) return res.status(e.status).json({error: e.message, ...e.extra}); throw e; }
    }
    if (parts[0] === 'emergency') {
      res.locals.lastModified = null;
      const F = require('./_emergency_feed');
      const r = await F.liveFeed(req, catalog, {place: 'fl-bay'});
      if (req.query.kind) r.notices = r.notices.filter(n => n.kind === String(req.query.kind));
      info.rows = r.notices.length;
      return res.status(200).json(r);
    }
    if (parts[0] === 'emergency-timeline') {
      res.locals.lastModified = null;
      const r = await require('./_emergency_feed').timeline(req, catalog, req.query, {place: 'fl-bay'});
      info.rows = r.items.length;
      return res.status(200).json(r);
    }
    if (parts[0] === 'evacuation-zone') {
      res.locals.lastModified = null;
      const r = await require('./_emergency_feed').zoneLookup(req, catalog, req.query, {place: 'fl-bay'});
      return res.status(200).json(r);
    }
    if (parts[0] === 'correspondence') {
      // Published emails between BayCounty.me and officials. Unpublished threads are never returned.
      res.locals.lastModified = null;
      const r = await require('./_correspondence').publicFeed({year: String(req.query.year || ''), government: String(req.query.government || '').slice(0, 120)});
      info.rows = r.conversations.length;
      return res.status(200).json(r);
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
module.exports.utilityData = utilityData;
