// Officials' business ties for the "Business ties" tab on /admin (admin only). Reads the private `careers` schema
// (migration 0033, loaded by db/scripts/load_careers.py from data/careers): name matches between officials or
// candidates and Sunbiz people, the businesses each match is listed on, and the links those businesses have to
// campaigns and public money. Confirming a match publishes its businesses and links (careers.publish) to the
// official-businesses and official-business-links datasets; rejecting or un-confirming takes them down.
// Files starting with _ are not routes.
const db = require('./_db');
const {cleanCounty} = require('./_registry');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const REVIEW = ['unreviewed', 'confirmed', 'rejected'];
const CONFIDENCE = ['high', 'medium', 'low'];
const PERSON_ID = /^[a-z0-9][a-z0-9-]{1,80}$/;
const PERSON_KEY = /^p_[0-9a-f]{12}$/;

// Pure: a list of {person_id, person_key} pairs from a review body (one pair, or `pairs` for a bulk change).
function cleanPairs(body) {
  const raw = Array.isArray(body.pairs) ? body.pairs : [{person_id: body.person_id, person_key: body.person_key}];
  if (!raw.length || raw.length > 500) throw bad('Send 1 to 500 matches.');
  return raw.map(p => {
    const id = String(p && p.person_id || ''), key = String(p && p.person_key || '');
    if (!PERSON_ID.test(id) || !PERSON_KEY.test(key)) throw bad('Unknown match.');
    return {person_id: id, person_key: key};
  });
}

async function summary(county) {
  const [load] = await db.q(`select loaded_at, git_sha, matches, roles, links, summary from careers.loads where county = $1 order by id desc limit 1`, [county]);
  const review = await db.q(`select review_status, confidence, count(*)::int n from careers.matches where county = $1 group by 1, 2`, [county]);
  const [pub] = await db.q(`select (select count(*)::int from official_businesses where origin = 'careers' and county = $1) businesses,
      (select count(*)::int from official_business_links where origin = 'careers' and county = $1) links`, [county]);
  return {county, load: load || null, review, published: pub || {businesses: 0, links: 0}};
}

// Matches with the Sunbiz person behind each (name, city: private) and the businesses and links that hang off it.
async function matches({county = 'bay', status = '', confidence = '', q = ''} = {}) {
  county = cleanCounty(county);
  const p = [county]; let w = 'm.county = $1';
  if (REVIEW.includes(status)) { p.push(status); w += ` and m.review_status = $${p.length}`; }
  if (CONFIDENCE.includes(confidence)) { p.push(confidence); w += ` and m.confidence = $${p.length}`; }
  const term = String(q || '').trim().slice(0, 80);
  if (term) { p.push('%' + term.toLowerCase() + '%'); w += ` and lower(m.official_name) like $${p.length}`; }
  const rows = await db.q(`select m.person_id, m.person_key, m.official_name, m.label, m.gov_ids, m.score, m.confidence, m.reasons, m.n_businesses,
      m.review_status, m.reviewed_by, m.reviewed_at,
      pe.display_name sunbiz_name, pe.city sunbiz_city, pe.resident, pe.active_entities_as_officer, pe.corporate_officer, pe.agent_service,
      coalesce((select json_agg(json_build_object('doc_number', r.doc_number, 'name', r.entity_name, 'titles', r.titles, 'status', r.entity_status,
          'nonprofit', r.nonprofit, 'city', r.principal_city, 'file_date', r.file_date, 'closed_year', r.closed_year) order by r.entity_status, r.entity_name)
        from careers.roles r where r.county = m.county and r.person_id = m.person_id and r.person_key = m.person_key), '[]') businesses,
      coalesce((select json_agg(json_build_object('link_type', l.link_type, 'detail', l.detail, 'amount', l.amount, 'own_government', l.own_government))
        from careers.links l where l.county = m.county and l.requires ? (m.person_id || '|' || m.person_key)), '[]') links
    from careers.matches m left join registry.people pe on pe.county = m.county and pe.person_key = m.person_key
    where ${w} order by m.official_name, m.score desc limit 1000`, p);
  return {...await summary(county), matches: rows};
}

async function review(body, admin) {
  const county = cleanCounty(body.county);
  const status = String(body.status || '');
  if (!REVIEW.includes(status)) throw bad('Unknown review status.');
  const pairs = cleanPairs(body);
  const rows = await db.q(`update careers.matches m set review_status = $1, reviewed_by = $2, reviewed_at = now()
    from jsonb_to_recordset($4::jsonb) as x(person_id text, person_key text)
    where m.county = $3 and m.person_id = x.person_id and m.person_key = x.person_key
    returning m.person_id, m.person_key, m.review_status`, [status, admin || null, county, JSON.stringify(pairs)]);
  if (!rows.length) throw bad('Unknown match.', 404);
  const [x] = await db.q('select careers.publish($1) n', [county]);
  return {updated: rows.length, published: Number(x && x.n) || 0, by: admin, rows};
}

module.exports = {cleanPairs, summary, matches, review};
