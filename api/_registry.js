// Business registry research for the "Owners" tab on /admin (admin only). Reads the private `registry` schema
// (migration 0031, loaded by db/scripts/load_registry.py from data/sunbiz): who runs which registered businesses,
// and groups of businesses that share a person and gave to the same candidate. Officer and agent names live only
// here; public pages and /api/v1 get business-level data (dataset business-donor-sunbiz). Files starting with _ are
// not routes.
const db = require('./_db');
const bulk = require('./_bulk');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const COUNTY = /^[a-z][a-z_]{1,30}$/;
const REVIEW = ['unreviewed', 'confirmed', 'rejected'];

// Pure: a county key from the query, or 'bay'.
function cleanCounty(v) {
  const s = String(v ?? '').trim().toLowerCase();
  return COUNTY.test(s) ? s : 'bay';
}

// Pure: search text -> {kind, term}. Sunbiz document numbers (L12000012345, P98000001234, N05000001234 ...) look up an
// entity; anything else is a name, matched against people (LAST FIRST, either order) and business names.
function cleanQuery(v) {
  const s = String(v ?? '').trim().replace(/\s+/g, ' ').slice(0, 80);
  if (s.length < 3) throw bad('Type at least 3 characters.');
  if (/^[A-Z]\d{8,11}$/i.test(s) || /^\d{5,12}$/.test(s)) return {kind: 'doc', term: s.toUpperCase()};
  const words = s.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').split(' ').filter(Boolean);
  if (!words.length) throw bad('Type a name or a Sunbiz document number.');
  return {kind: 'name', term: words.join(' '), words};
}

async function summary(county) {
  const [load] = await db.q(`select loaded_at, git_sha, entities, people, roles, gifts, groups, summary from registry.loads
      where county = $1 order by id desc limit 1`, [county]);
  const review = await db.q(`select review_status, count(*)::int n, coalesce(sum(combined_amount), 0)::float dollars
      from registry.shared_owner_groups where county = $1 group by 1`, [county]);
  return {county, load: load || null, review};
}

async function groups({county = 'bay', status = '', candidate = ''} = {}) {
  county = cleanCounty(county);
  const p = [county]; let w = 'g.county = $1';
  if (REVIEW.includes(status)) { p.push(status); w += ` and g.review_status = $${p.length}`; }
  if (candidate) { p.push(String(candidate).slice(0, 80)); w += ` and g.candidate = $${p.length}`; }
  const rows = await db.q(`select g.group_id, g.candidate, g.office, g.government_key, g.election, g.n_businesses, g.n_checks, g.n_people,
      g.combined_amount::float combined_amount, g.all_at_1000, g.same_day, g.businesses, g.report_url, g.review_status, g.reviewed_by, g.reviewed_at,
      coalesce((select json_agg(json_build_object('person_key', pe.person_key, 'name', pe.display_name, 'city', pe.city, 'resident', pe.resident,
        'active_entities', pe.active_entities_as_officer) order by pe.display_name)
        from registry.people pe where pe.county = g.county and g.person_keys ? pe.person_key), '[]') people
    from registry.shared_owner_groups g where ${w} order by g.combined_amount desc, g.candidate limit 500`, p);
  return {...await summary(county), groups: rows};
}

// One person: every business they're listed on, and that business's matched campaign gifts.
async function person(county, key) {
  county = cleanCounty(county);
  if (!/^p_[0-9a-f]{12}$/.test(String(key || ''))) throw bad('Unknown person.');
  const [p] = await db.q('select * from registry.people where county = $1 and person_key = $2', [county, key]);
  if (!p) throw bad('Unknown person.', 404);
  const businesses = await db.q(`select e.doc_number, e.name, e.status, e.filing_type, e.principal_city, string_agg(distinct r.title, ', ') titles,
      (select coalesce(sum(gm.amount), 0)::float from registry.gift_matches gm where gm.county = e.county and gm.doc_number = e.doc_number and gm.amount > 0) gifts_total,
      (select coalesce(json_agg(distinct gm.candidate), '[]') from registry.gift_matches gm where gm.county = e.county and gm.doc_number = e.doc_number and gm.amount > 0) candidates
    from registry.roles r join registry.entities e on e.county = r.county and e.doc_number = r.doc_number
    where r.county = $1 and r.person_key = $2 group by e.county, e.doc_number order by e.status, e.name`, [county, key]);
  return {person: p, businesses};
}

// One business: everyone listed on it, and its matched gifts.
async function entity(county, doc) {
  county = cleanCounty(county);
  doc = String(doc || '').toUpperCase();
  if (!/^[A-Z0-9]{5,12}$/.test(doc)) throw bad('Unknown document number.');
  const [e] = await db.q('select * from registry.entities where county = $1 and doc_number = $2', [county, doc]);
  if (!e) throw bad('Unknown document number.', 404);
  const people = await db.q(`select pe.person_key, pe.display_name, pe.city, pe.resident, pe.active_entities_as_officer, pe.corporate_officer, pe.agent_service,
      string_agg(distinct r.title, ', ') titles
    from registry.roles r join registry.people pe on pe.county = r.county and pe.person_key = r.person_key
    where r.county = $1 and r.doc_number = $2 group by pe.county, pe.person_key order by pe.display_name`, [county, doc]);
  const gifts = await db.q(`select candidate, office, contributor, amount::float amount, gift_date, match_method, report_url from registry.gift_matches
    where county = $1 and doc_number = $2 order by gift_date`, [county, doc]);
  return {entity: e, people, gifts};
}

async function search(county, q) {
  county = cleanCounty(county);
  const s = cleanQuery(q);
  if (s.kind === 'doc') return {people: [], entities: await db.q('select doc_number, name, status, principal_city from registry.entities where county = $1 and doc_number = $2', [county, s.term])};
  const rev = s.words.length > 1 ? [...s.words.slice(1), s.words[0]].join(' ') : s.term;
  const people = await db.q(`select person_key, display_name, city, resident, entities_as_officer, active_entities_as_officer, entities_as_agent, corporate_officer, agent_service
    from registry.people where county = $1 and (name_key like $2 or name_key like $3)
    order by active_entities_as_officer desc, display_name limit 50`, [county, s.term + '%', rev + '%']);
  const entities = await db.q(`select doc_number, name, status, principal_city from registry.entities where county = $1 and name_key like $2
    order by status, name limit 50`, [county, '%' + s.term + '%']);
  return {people, entities};
}

// Pure: the groups named in a review body (one, or `items` for a bulk change). No candidate means every candidate of that group.
function cleanGroups(body) {
  return bulk.items(body, x => {
    const gid = String(x.group_id || '');
    if (!/^g_[0-9a-f]{10}$/.test(gid)) throw bad('Unknown group.');
    return {group_id: gid, candidate: x.candidate ? String(x.candidate).slice(0, 200) : null};
  });
}

async function review(body, admin) {
  const county = cleanCounty(body.county);
  const status = String(body.status || '');
  if (!REVIEW.includes(status)) throw bad('Unknown review status.');
  const groups = cleanGroups(body);
  const rows = await db.q(`update registry.shared_owner_groups g set review_status = $1, reviewed_by = $2, reviewed_at = now()
    from jsonb_to_recordset($4::jsonb) as x(group_id text, candidate text)
    where g.county = $3 and g.group_id = x.group_id and (x.candidate is null or g.candidate = x.candidate)
    returning g.group_id, g.candidate, g.review_status`, [status, admin || null, county, JSON.stringify(groups)]);
  if (!rows.length) throw bad('Unknown group.', 404);
  // confirmed groups appear on /connections/shared-owners (business names only); anything else is taken down.
  // One group is rewritten on its own; a bulk change rewrites the county's public rows in one call.
  let published = 0;
  if (rows.length === 1) {
    const [x] = await db.q('select registry.publish_group($1, $2, $3) n', [county, rows[0].group_id, rows[0].candidate]);
    published = Number(x && x.n) || 0;
  } else {
    const [x] = await db.q('select registry.publish_all($1) n', [county]);
    published = Number(x && x.n) || 0;
  }
  return {updated: rows.length, published, by: admin, rows};
}

// ---------- gifts over the per-election limit (registry.limit_cases, migration 0038) ----------
const LIMIT_REVIEW = ['unreviewed', 'confirmed', 'resolved', 'rejected'];
const RESOLUTIONS = ['reporting_error', 'amended_report', 'refunded', 'designated_general', 'elections_commission', 'other'];

async function limits({county = 'bay', status = ''} = {}) {
  county = cleanCounty(county);
  const p = [county]; let w = 'county = $1';
  if (LIMIT_REVIEW.includes(status)) { p.push(status); w += ` and review_status = $${p.length}`; }
  const cases = await db.q(`select case_id, candidate, office, election, election_phase, contributor, contributor_type, spellings, n_items,
      gross_amount::float gross_amount, refunds::float refunds, net_amount::float net_amount, over_by::float over_by, possible_double_entry,
      auto_resolution, items, report_url, in_current_data, review_status, resolution, resolution_note, resolution_url, reviewed_by, reviewed_at
    from registry.limit_cases where ${w} order by (review_status = 'unreviewed') desc, over_by desc, candidate limit 500`, p);
  return {county, cases, resolutions: RESOLUTIONS};
}

// Pure: check a review body. A resolved case needs a resolution; the note and link are optional, the link must be http(s).
// `case_ids` names several cases for a bulk change; they all get the same status (and resolution).
function cleanLimitReview(body) {
  const status = String(body.status || '');
  if (!LIMIT_REVIEW.includes(status)) throw bad('Unknown review status.');
  const ids = bulk.items(body, x => {
    const id = String(x.case_id || x.value || '');
    if (!/^l_[0-9a-f]{10}$/.test(id)) throw bad('Unknown case.');
    return id;
  }, 'case_ids');
  let resolution = null, note = null, url = null;
  if (status === 'resolved') {
    resolution = String(body.resolution || '');
    if (!RESOLUTIONS.includes(resolution)) throw bad('Pick how it was resolved.');
    note = String(body.resolution_note || '').trim().slice(0, 600) || null;
    url = String(body.resolution_url || '').trim().slice(0, 500) || null;
    if (url && !/^https?:\/\/[^\s]+$/i.test(url)) throw bad('The source link must start with http:// or https://.');
  }
  return {county: cleanCounty(body.county), status, id: ids[0], ids, resolution, note, url};
}

async function reviewLimit(body, admin) {
  const c = cleanLimitReview(body);
  const rows = await db.q(`update registry.limit_cases set review_status = $1, resolution = $2, resolution_note = $3, resolution_url = $4,
      reviewed_by = $5, reviewed_at = now() where county = $6 and case_id = any($7::text[]) returning case_id, review_status`,
    [c.status, c.resolution, c.note, c.url, admin, c.county, c.ids]);
  if (!rows.length) throw bad('Unknown case.', 404);
  // confirmed and resolved cases appear on /connections/shared-owners; anything else is taken down
  const [x] = rows.length === 1 ? await db.q('select registry.publish_limit_case($1, $2) n', [c.county, rows[0].case_id])
    : await db.q('select registry.publish_limit_all($1) n', [c.county]);
  return {updated: rows.length, published: Number(x && x.n) || 0, by: admin, rows};
}

module.exports = {cleanCounty, cleanQuery, summary, groups, person, entity, search, cleanGroups, review, limits, cleanLimitReview, reviewLimit, RESOLUTIONS};
