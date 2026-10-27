// Entity profiles: every company, official, candidate, nonprofit, board member, business and government on the site,
// with every documented connection (site/entity_graph.py builds the entity-profiles and entity-connections datasets).
// Used by GET /api/v1/entities, GET /api/v1/entities/{id}, the MCP tools find_entity / get_entity, and the profile
// pages (site/profile.js).
//
// Connections from the database-only datasets are added here, because their rows reach the database only after an
// admin confirms a match: officials on nonprofit boards (nonprofit-officials), officials' businesses and business ties
// (official-businesses, official-business-links) and shared-owner campaign gifts (shared-owner-groups). Individual
// campaign donors are never in any of these datasets.
const {datasetRows, rest} = require('./_data');
const {nameCase} = require('./_names');

const SUNBIZ_SEARCH = 'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults';
// Sunbiz record pages need an internal id the state files don't carry, so link the entity-name search (business listed
// first). Same rule as data/entities/ids.py sunbiz_url().
const sunbizUrl = (name, doc) => {
  const nm = String(name || '').trim().replace(/\s+/g, ' ');
  if (!nm) return doc ? `${SUNBIZ_SEARCH}?inquiryType=DocumentNumber&searchTerm=${encodeURIComponent(String(doc).trim().toUpperCase())}` : null;
  const enc = s => encodeURIComponent(s).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
  return /[\/\\&*%:<>?]/.test(nm) ? `${SUNBIZ_SEARCH}?inquiryType=EntityName&searchTerm=${enc(nm)}` : `${SUNBIZ_SEARCH}/EntityName/${enc(nm)}/Page1`;
};

const RELATION = {
  paid: ['paid', 'was paid by'],
  gift: ['gave to the campaign of', 'got campaign gifts from'],
  voted: ['voted on contracts with', 'had contracts voted on by'],
  serves: ['serves', 'is served by'],
  served: ['served', 'was served by'],
  candidate: ['is a candidate for office in', 'has candidates for office'],
  ran: ['ran for office in', 'had on the ballot'],
  board: ['sits on the board of', 'has on its board'],
  runs: ['runs', 'is run by'],
  grant: ['gave a grant to', 'got a grant from'],
  related: ['is connected to', 'is connected to'],
  same: ['is the same organization as', 'is the same organization as'],
  works: ['works at', 'has on its staff'],
  hired: ['hired', 'was hired by'],
  charter: ['runs a charter school for', 'has a charter school run by'],
};
const KIND_LABEL = {gov: 'Government', vendor: 'Company', person: 'Official or candidate', nonprofit: 'Nonprofit', member: 'Nonprofit board member', owner: 'Business owner',
  business: 'Business', committee: 'Committee or PAC'};
const ID_RE = /^(gov|vendor|person|nonprofit|member|owner|business|committee):[A-Za-z0-9_.-]{1,100}$/;
const q = v => '"' + String(v).replace(/["\\]/g, '') + '"';
const PROFILE_COLS = 'entity_id,kind,kind_label,name,subtitle,page_url,aliases,connections,amount_received,amount_given,gov_id,county,source_url';
const LINK_COLS = 'link_id,from_id,from_name,from_kind,from_url,to_id,to_name,to_kind,to_url,relation,relation_label,amount,records,first_date,last_date,detail,source_url,county';

// The profile URL rule (same as site/entity_graph.py page_url) for entities the build didn't list, e.g. a business
// that only appears in a confirmed database-only row.
function urlFor(id, known) {
  if (known && known.has(id)) return known.get(id);
  const i = id.indexOf(':'), k = id.slice(0, i), v = id.slice(i + 1);
  return k === 'person' ? `/people/${v}` : `/profile/${k}/${v}`;
}

function shape(id, rows, labels = new Map()) {
  // one connection, from this entity's side
  return rows.map(r => {
    const out = r.from_id === id;
    const rel = r.relation;
    return {link_id: r.link_id, relation: rel, label: (RELATION[rel] || [rel, rel])[out ? 0 : 1], direction: out ? 'out' : 'in',
      other: {entity_id: out ? r.to_id : r.from_id, name: nameCase(out ? r.to_name : r.from_name, out ? r.to_kind : r.from_kind), kind: out ? r.to_kind : r.from_kind,
        kind_label: labels.get(out ? r.to_id : r.from_id) || KIND_LABEL[out ? r.to_kind : r.from_kind] || null, page_url: out ? r.to_url : r.from_url},
      amount: r.amount ?? null, records: r.records ?? null, first_date: r.first_date || null, last_date: r.last_date || null, detail: r.detail || null,
      source_url: r.source_url || null, dataset: r.dataset || 'entity-connections', checked_by_hand: r.checked_by_hand || undefined,
      merged_from: r.merged_from || undefined};
  });
}

const meta = (catalog, id) => catalog.datasets.find(d => d.id === id);

// Rows of a dataset matching one column, from the database (one targeted read) or, if it can't be reached, the file.
async function rowsWhere(req, catalog, did, filters) {
  const m = meta(catalog, did);
  if (!m) return [];
  const table = did.replace(/-/g, '_'), cols = m.columns.map(c => c.name).join(',');
  const where = Object.entries(filters).map(([k, v]) => Array.isArray(v) ? `or=(${v.map(x => `${k}.eq.${q(x)}`).join(',')})` : `${k}=eq.${encodeURIComponent(v)}`).join('&');
  try { return (await rest(`${table}?select=${cols}&${where}&limit=5000`, {timeout: 6000})).rows; }
  catch (e) {
    const {rows} = await datasetRows(req, m);
    return rows.filter(r => Object.entries(filters).every(([k, v]) => (Array.isArray(v) ? v : [v]).includes(r[k])));
  }
}

// Connections from the database-only datasets, as entity-connections rows.
async function liveConnections(req, catalog, ent) {
  const [kind, key] = [ent.kind, ent.entity_id.slice(ent.kind.length + 1)];
  const out = [], tasks = [];
  const add = r => out.push({county: r.county, checked_by_hand: true, records: 1, ...r});
  if (kind === 'person' || kind === 'nonprofit') {
    tasks.push(rowsWhere(req, catalog, 'nonprofit-officials', kind === 'person' ? {official_id: key} : {nonprofit_id: key}).then(rs => rs.forEach(r => r.official_id && add({
      // official_id is the official's person id; person_id in this table is the board-member key (b_...)
      link_id: 'no:' + r.official_id + ':' + r.nonprofit_id, from_id: 'person:' + r.official_id, from_name: r.official, from_kind: 'person', from_url: `/people/${r.official_id}`,
      to_id: 'nonprofit:' + r.nonprofit_id, to_name: r.nonprofit, to_kind: 'nonprofit', to_url: `/profile/nonprofit/${r.nonprofit_id}`, relation: 'board',
      first_date: r.first_year ? String(r.first_year) : null, last_date: r.last_year ? String(r.last_year) : null,
      detail: [r.titles, r.current ? 'current' : null].filter(Boolean).join(' · ') || null, source_url: r.source_url, dataset: 'nonprofit-officials',
      same_as: r.person_id ? 'member:' + r.person_id : null}))));
  }
  if (kind === 'person' || kind === 'business') {
    tasks.push(rowsWhere(req, catalog, 'official-businesses', kind === 'person' ? {person_id: key} : {sunbiz_doc_number: [key.toUpperCase(), key]}).then(rs => rs.forEach(r => r.person_id && r.sunbiz_doc_number && add({
      link_id: 'ob:' + r.person_id + ':' + r.sunbiz_doc_number, from_id: 'person:' + r.person_id, from_name: r.official, from_kind: 'person', from_url: `/people/${r.person_id}`,
      to_id: 'business:' + r.sunbiz_doc_number.toLowerCase(), to_name: r.business, to_kind: 'business', to_url: `/profile/business/${r.sunbiz_doc_number.toLowerCase()}`,
      relation: 'runs', first_date: r.filed_date || null, detail: [r.titles, r.business_status].filter(Boolean).join(' · ') || null, source_url: r.source_url, dataset: 'official-businesses'}))));
  }
  if (kind === 'person') {
    tasks.push(rowsWhere(req, catalog, 'official-business-links', {person_id: key}).then(rs => rs.forEach(r => {
      const other = r.other_person_id ? {id: 'person:' + r.other_person_id, name: r.other_official, kind: 'person'}
        : r.sunbiz_doc_number ? {id: 'business:' + r.sunbiz_doc_number.toLowerCase(), name: r.business, kind: 'business'} : null;
      if (other) add({link_id: 'obl:' + [r.link_type, r.person_id, other.id, r.candidate || r.payer || ''].join(':'), from_id: 'person:' + r.person_id, from_name: r.official, from_kind: 'person',
        from_url: `/people/${r.person_id}`, to_id: other.id, to_name: other.name, to_kind: other.kind, to_url: urlFor(other.id), relation: 'related', amount: r.amount ?? null,
        records: r.items || 1, first_date: r.first_date || null, last_date: r.last_date || null, detail: r.detail || r.link_type, source_url: r.source_url || r.report_url, dataset: 'official-business-links'});
    })));
    tasks.push(rowsWhere(req, catalog, 'shared-owner-groups', {candidate: [ent.name, ...(ent.aliases || [])]}).then(rs => rs.forEach(r => r.sunbiz_doc_number && add({
      link_id: 'sog:' + r.group_id + ':' + r.sunbiz_doc_number, from_id: 'business:' + r.sunbiz_doc_number.toLowerCase(), from_name: r.business, from_kind: 'business',
      from_url: `/profile/business/${r.sunbiz_doc_number.toLowerCase()}`, to_id: ent.entity_id, to_name: ent.name, to_kind: 'person', to_url: ent.page_url, relation: 'gift',
      amount: r.business_amount ?? null, detail: `One of ${r.group_businesses} businesses that share an owner or officer and gave ${r.group_total != null ? '$' + Number(r.group_total).toLocaleString('en-US') : ''} in all`,
      source_url: r.campaign_report_url || r.source_url, dataset: 'shared-owner-groups'}))));
  }
  if (kind === 'business') {
    tasks.push(rowsWhere(req, catalog, 'shared-owner-groups', {sunbiz_doc_number: [key.toUpperCase(), key]}).then(async rs => {
      const names = [...new Set(rs.map(r => r.candidate).filter(Boolean))];
      const ppl = names.length ? (await rowsWhere(req, catalog, 'entity-profiles', {name: names})).filter(p => p.kind === 'person') : [];
      const pid = new Map(ppl.map(p => [p.name, p]));
      rs.forEach(r => pid.has(r.candidate) && add({
      link_id: 'sog:' + r.group_id + ':' + r.sunbiz_doc_number + ':' + r.candidate, from_id: ent.entity_id, from_name: ent.name, from_kind: 'business', from_url: ent.page_url,
      to_id: pid.get(r.candidate).entity_id, to_name: r.candidate, to_kind: 'person', to_url: pid.get(r.candidate).page_url, relation: 'gift', amount: r.business_amount ?? null,
      detail: `${r.office || ''}: one of ${r.group_businesses} businesses that share an owner or officer and gave to this candidate`, source_url: r.campaign_report_url || r.source_url,
      dataset: 'shared-owner-groups'}));
    }));
  }
  await Promise.all(tasks.map(t => t.catch(() => null)));
  return out;
}

// A name in the build-time rows (a nonprofit board member, or a board member or business owner on a company's Sunbiz
// filing) and a hand-checked official are often the same person on the same record. Show one row: the official's,
// which links to their person page, keeping the amount and dates from the build row. A board seat merges when the
// confirmed row names that board-member key; a business row merges when the names match on the same company's filing.
const nameKey = s => { const w = String(s || '').toLowerCase().replace(/[^a-z\s]/g, ' ').split(/\s+/).filter(x => x && !/^(jr|sr|ii|iii|iv)$/.test(x)); return w.length > 1 ? w[0] + ' ' + w[w.length - 1] : w.join(''); };
function mergeConfirmed(links, live) {
  const seen = new Set(links.map(r => r.from_id + '|' + r.to_id + '|' + r.relation));
  const add = live.filter(r => !seen.has(r.from_id + '|' + r.to_id + '|' + r.relation));
  const drop = new Set();
  for (const r of add) {
    if (r.from_kind !== 'person') continue;
    const twin = links.find(l => !drop.has(l) && l.relation === r.relation && l.to_id === r.to_id && l.from_id !== r.from_id &&
      (r.same_as ? l.from_id === r.same_as : ['member', 'owner'].includes(l.from_kind) && nameKey(l.from_name) === nameKey(r.from_name)));
    if (!twin) continue;
    drop.add(twin);
    for (const k of ['amount', 'first_date', 'last_date', 'detail', 'source_url']) if (r[k] == null && twin[k] != null) r[k] = twin[k];
    if (twin.records > (r.records || 0)) r.records = twin.records;
    r.merged_from = twin.from_id;
  }
  return links.filter(l => !drop.has(l)).concat(add);
}

// What each linked person is ("Elected official", "Department leader", "Candidate", "Former official"), from their
// profile row, so a list says more than "Official or candidate".
async function personLabels(req, pm, links, id, source) {
  const ids = [...new Set(links.flatMap(r => [r.from_id, r.to_id]).filter(x => x !== id && String(x).startsWith('person:')))].slice(0, 300);
  if (!ids.length) return new Map();
  let rows = [];
  try {
    if (source !== 'database') throw new Error('file');
    rows = (await rest(`entity_profiles?select=entity_id,kind_label&entity_id=in.(${ids.map(x => encodeURIComponent(q(x))).join(',')})`, {timeout: 6000})).rows;
  } catch (e) {
    const want = new Set(ids);
    rows = await datasetRows(req, pm).then(r => r.rows.filter(p => want.has(p.entity_id))).catch(() => []);
  }
  return new Map(rows.map(r => [r.entity_id, r.kind_label]));
}

// A board member an editor confirmed as an official: the profile says so and links the official's page.
async function withOfficial(req, catalog, ent) {
  const rs = await rowsWhere(req, catalog, 'nonprofit-officials', {person_id: ent.entity_id.slice(7)}).catch(() => []);
  const r = rs.find(x => x.official_id);
  return r ? {...ent, same_as: {entity_id: 'person:' + r.official_id, name: r.official, kind: 'person', page_url: `/people/${r.official_id}`}} : ent;
}

async function getEntity(req, catalog, id) {
  if (!ID_RE.test(id)) throw Object.assign(new Error('An entity id looks like kind:key, e.g. person:douglas-moore or vendor:dewberry.'), {status: 400, expose: true});
  const pm = meta(catalog, 'entity-profiles'), lm = meta(catalog, 'entity-connections');
  if (!pm || !lm) throw Object.assign(new Error('Entity profiles are not published yet.'), {status: 404, expose: true});
  let ent, links, source = 'database';
  try {
    ent = (await rest(`entity_profiles?select=${PROFILE_COLS}&entity_id=eq.${encodeURIComponent(id)}`, {timeout: 6000})).rows[0];
    links = ent ? (await rest(`entity_connections?select=${LINK_COLS}&or=(from_id.eq.${encodeURIComponent(q(id))},to_id.eq.${encodeURIComponent(q(id))})&limit=10000`, {timeout: 8000})).rows : [];
  } catch (e) {
    source = 'file';
    ent = (await datasetRows(req, pm)).rows.find(r => r.entity_id === id);
    links = ent ? (await datasetRows(req, lm)).rows.filter(r => r.from_id === id || r.to_id === id) : [];
  }
  let live;
  if (!ent && id.startsWith('business:')) {  // a business named only in a hand-checked, database-only row
    const kind = 'business', stub = {entity_id: id, kind, kind_label: KIND_LABEL[kind], name: id.slice(9).toUpperCase(), subtitle: 'Registered business', page_url: urlFor(id),
      aliases: null, connections: 0, amount_received: null, amount_given: null, gov_id: null, county: null,
      source_url: sunbizUrl(null, id.slice(9))};
    live = await liveConnections(req, catalog, stub);
    if (live.length) { ent = stub; const r = live[0]; ent.name = r.from_id === id ? r.from_name : r.to_name; ent.source_url = sunbizUrl(ent.name, id.slice(9)); ent.connections = live.length; }
  }
  if (!ent) throw Object.assign(new Error(`No entity "${id}".`), {status: 404, expose: true});
  live = live || await liveConnections(req, catalog, ent);
  if (ent.kind === 'member') ent = await withOfficial(req, catalog, ent);
  if (ent.kind === 'person') {  // the official photo their government publishes (official-photos), when there is one
    const ph = (await rowsWhere(req, catalog, 'official-photos', {entity_id: id}).catch(() => []))[0];
    if (ph) ent = {...ent, photo: {url: ph.photo_url, credit: ph.credit, source_url: ph.source_url}};
  }
  const all = mergeConfirmed(links, live);
  const labels = await personLabels(req, pm, all, id, source);
  const connections = shape(id, all, labels).sort((a, b) => (b.amount || 0) - (a.amount || 0) || String(a.other.name).localeCompare(String(b.other.name)));
  if (live.length) ent = {...ent, connections: connections.length};
  const counts = {};
  connections.forEach(c => { counts[c.relation] = (counts[c.relation] || 0) + 1; });
  ent = {...ent, name: nameCase(ent.name, ent.kind)};  // database-only rows keep names as filed, often in all caps
  return {entity: ent, connections, counts, data_source: source,
    note: 'Connections come from public records, each with its source. A connection is a fact in two records; it does not show why anything happened. Individual campaign donors are never named.'};
}

async function searchEntities(req, catalog, {q: text = '', kind = '', limit = 20} = {}) {
  const pm = meta(catalog, 'entity-profiles');
  if (!pm) return [];
  const t = String(text).trim().slice(0, 80), k = String(kind || '').trim();
  if (!t) throw Object.assign(new Error('Add ?q= with a name, e.g. ?q=dewberry.'), {status: 400, expose: true});
  const lim = Math.min(Math.max(parseInt(limit, 10) || 20, 1), 100);
  let rows;
  try {
    const like = encodeURIComponent('*' + t.replace(/[*,()"]/g, ' ') + '*');
    rows = (await rest(`entity_profiles?select=${PROFILE_COLS}&name=ilike.${like}${k ? `&kind=eq.${encodeURIComponent(k)}` : ''}&order=connections.desc&limit=${lim}`, {timeout: 6000})).rows;
  } catch (e) {
    const words = t.toLowerCase().split(/\s+/);
    rows = (await datasetRows(req, pm)).rows.filter(r => (!k || r.kind === k) && words.every(w => (r.name + ' ' + (r.aliases || []).join(' ')).toLowerCase().includes(w)))
      .sort((a, b) => (b.connections || 0) - (a.connections || 0)).slice(0, lim);
  }
  return rows;
}

module.exports = {getEntity, searchEntities, mergeConfirmed, shape, RELATION, KIND_LABEL, ID_RE};
