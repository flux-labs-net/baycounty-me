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

const RELATION = {
  paid: ['paid', 'was paid by'],
  gift: ['gave to the campaign of', 'got campaign gifts from'],
  voted: ['voted on contracts with', 'had contracts voted on by'],
  serves: ['serves', 'is served by'],
  board: ['sits on the board of', 'has on its board'],
  runs: ['runs', 'is run by'],
  grant: ['gave a grant to', 'got a grant from'],
  related: ['is connected to', 'is connected to'],
  same: ['is the same organization as', 'is the same organization as'],
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

function shape(id, rows) {
  // one connection, from this entity's side
  return rows.map(r => {
    const out = r.from_id === id;
    const rel = r.relation;
    return {link_id: r.link_id, relation: rel, label: (RELATION[rel] || [rel, rel])[out ? 0 : 1], direction: out ? 'out' : 'in',
      other: {entity_id: out ? r.to_id : r.from_id, name: out ? r.to_name : r.from_name, kind: out ? r.to_kind : r.from_kind,
        kind_label: KIND_LABEL[out ? r.to_kind : r.from_kind] || null, page_url: out ? r.to_url : r.from_url},
      amount: r.amount ?? null, records: r.records ?? null, first_date: r.first_date || null, last_date: r.last_date || null, detail: r.detail || null,
      source_url: r.source_url || null, dataset: r.dataset || 'entity-connections', checked_by_hand: r.checked_by_hand || undefined};
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
    tasks.push(rowsWhere(req, catalog, 'nonprofit-officials', kind === 'person' ? {person_id: key} : {nonprofit_id: key}).then(rs => rs.forEach(r => r.person_id && add({
      link_id: 'no:' + (r.official_id || r.person_id + r.nonprofit_id), from_id: 'person:' + r.person_id, from_name: r.official, from_kind: 'person', from_url: `/people/${r.person_id}`,
      to_id: 'nonprofit:' + r.nonprofit_id, to_name: r.nonprofit, to_kind: 'nonprofit', to_url: `/profile/nonprofit/${r.nonprofit_id}`, relation: 'board',
      first_date: r.first_year ? String(r.first_year) : null, last_date: r.last_year ? String(r.last_year) : null,
      detail: [r.titles, r.current ? 'current' : null].filter(Boolean).join(' · ') || null, source_url: r.source_url, dataset: 'nonprofit-officials'}))));
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
      source_url: `https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResultDetail?inquirytype=DocumentNumber&directionType=Initial&searchTerm=${encodeURIComponent(id.slice(9).toUpperCase())}`};
    live = await liveConnections(req, catalog, stub);
    if (live.length) { ent = stub; const r = live[0]; ent.name = r.from_id === id ? r.from_name : r.to_name; ent.connections = live.length; }
  }
  if (!ent) throw Object.assign(new Error(`No entity "${id}".`), {status: 404, expose: true});
  live = live || await liveConnections(req, catalog, ent);
  const seen = new Set(links.map(r => r.from_id + '|' + r.to_id + '|' + r.relation));
  const all = links.concat(live.filter(r => !seen.has(r.from_id + '|' + r.to_id + '|' + r.relation)));
  const connections = shape(id, all).sort((a, b) => (b.amount || 0) - (a.amount || 0) || String(a.other.name).localeCompare(String(b.other.name)));
  const counts = {};
  connections.forEach(c => { counts[c.relation] = (counts[c.relation] || 0) + 1; });
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

module.exports = {getEntity, searchEntities, RELATION, KIND_LABEL, ID_RE};
