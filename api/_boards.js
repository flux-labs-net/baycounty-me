// Nonprofit board research for the "Nonprofit boards" tab on /admin (admin only). Reads the private `registry` schema
// (migration 0034, loaded by db/scripts/load_registry.py from data/nonprofits): who sits on which nonprofit board, who
// sits on several, which board members match an official by name, and which run businesses that gave to campaigns.
// Board member names live only here; public pages get organization-level data (datasets nonprofits, nonprofit-payments,
// nonprofit-grants) and confirmed official matches (nonprofit-officials). Files starting with _ are not routes.
const db = require('./_db');
const {cleanCounty, cleanQuery} = require('./_registry');
const bulk = require('./_bulk');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const REVIEW = ['unreviewed', 'confirmed', 'rejected'];
const BOARD_KEY = /^b_[0-9a-f]{12}$/;
const NP_ID = /^np-(\d{9}|sb-[a-z0-9]{5,12}|fd-[a-z0-9]{3,12})$/;  // fd-: FDACS-only charities

async function summary(county) {
  const [load] = await db.q(`select loaded_at, git_sha, summary from registry.loads where county = $1 order by id desc limit 1`, [county + ':nonprofits']);
  const review = await db.q(`select review_status, count(*)::int n from registry.board_official_matches where county = $1 group by 1`, [county]);
  return {county, load: load || null, review};
}

// Board members whose name matches an official, department leader or candidate, with their boards.
async function officials({county = 'bay', status = ''} = {}) {
  county = cleanCounty(county);
  const p = [county]; let w = 'm.county = $1';
  if (REVIEW.includes(status)) { p.push(status); w += ` and m.review_status = $${p.length}`; }
  const rows = await db.q(`select m.board_key, m.official_id, m.official_name, m.review_status, m.reviewed_by, m.reviewed_at,
      bp.display_name, bp.official_roles, bp.same_name_people, bp.n_nonprofits, bp.n_current,
      coalesce((select json_agg(x order by x.last_year desc nulls last) from (
        select s.nonprofit_id, max(s.nonprofit_name) nonprofit, string_agg(distinct s.title, ', ') titles, min(s.tax_year) first_year, max(s.tax_year) last_year,
          bool_or(s.current) current, string_agg(distinct s.source, ', ') sources, (array_agg(s.name_as_filed))[1] name_as_filed
        from registry.board_seats s where s.county = m.county and s.board_key = m.board_key and s.board group by s.nonprofit_id) x), '[]') boards
    from registry.board_official_matches m join registry.board_people bp on bp.county = m.county and bp.board_key = m.board_key
    where ${w} order by m.review_status = 'unreviewed' desc, m.official_name, bp.display_name limit 500`, p);
  return {...await summary(county), officials: rows};
}

// People on the most current boards (interlocking boards). Homeowner and condo associations are not counted: a
// developer or management company officer often sits on dozens of them.
async function interlocks(county, min = 2) {
  county = cleanCounty(county);
  min = Math.min(Math.max(parseInt(min, 10) || 2, 2), 20);
  return db.q(`select bp.board_key, bp.display_name, bp.n_current_civic, bp.n_current, bp.n_nonprofits, bp.official_name, bp.n_businesses, bp.n_donor_businesses,
      (select json_agg(distinct s.nonprofit_name) from registry.board_seats s where s.county = bp.county and s.board_key = bp.board_key and s.current and s.board) boards
    from registry.board_people bp where bp.county = $1 and bp.n_current_civic >= $2 order by bp.n_current_civic desc, bp.n_nonprofits desc, bp.display_name limit 200`, [county, min]);
}

// Board members who run (by Sunbiz name match) businesses that gave to local campaigns.
async function donors(county) {
  county = cleanCounty(county);
  return db.q(`select bp.board_key, bp.display_name, bp.n_current, bp.same_name_people, bp.official_name, bp.n_donor_businesses, bp.donor_gifts_total::float donor_gifts_total,
      (select json_agg(b) from jsonb_array_elements(bp.businesses) b where (b->>'gifts_total')::numeric > 0) businesses,
      (select json_agg(distinct s.nonprofit_name) from registry.board_seats s where s.county = bp.county and s.board_key = bp.board_key and s.board) boards
    from registry.board_people bp where bp.county = $1 and bp.n_donor_businesses > 0 order by bp.donor_gifts_total desc limit 300`, [county]);
}

// One person: every seat on every filing, and the businesses their name matches in Sunbiz.
async function person(county, key) {
  county = cleanCounty(county);
  if (!BOARD_KEY.test(String(key || ''))) throw bad('Unknown person.');
  const [p] = await db.q('select * from registry.board_people where county = $1 and board_key = $2', [county, key]);
  if (!p) throw bad('Unknown person.', 404);
  const seats = await db.q(`select nonprofit_id, nonprofit_name, ein, source, name_as_filed, title, tax_year, board, current, roles, hours::float hours,
      compensation::float compensation, source_url from registry.board_seats where county = $1 and board_key = $2
    order by nonprofit_name, tax_year desc nulls last`, [county, key]);
  return {person: p, seats};
}

// One nonprofit: everyone listed on its filings, newest first.
async function nonprofit(county, id) {
  county = cleanCounty(county);
  id = String(id || '').toLowerCase();
  if (!NP_ID.test(id)) throw bad('Unknown nonprofit.');
  const seats = await db.q(`select s.board_key, bp.display_name, s.source, s.title, s.tax_year, s.board, s.current, s.hours::float hours, s.compensation::float compensation,
      s.source_url, s.nonprofit_name, s.ein, bp.n_current, bp.official_name, bp.n_donor_businesses
    from registry.board_seats s join registry.board_people bp on bp.county = s.county and bp.board_key = s.board_key
    where s.county = $1 and s.nonprofit_id = $2 order by s.current desc, s.tax_year desc nulls last, s.board desc, bp.display_name`, [county, id]);
  if (!seats.length) throw bad('No board listed for that nonprofit.', 404);
  return {nonprofit_id: id, name: seats[0].nonprofit_name, ein: seats[0].ein, seats};
}

async function search(county, q) {
  county = cleanCounty(county);
  const s = /^\s*\d{2}-?\d{7}\s*$/.test(String(q ?? '')) ? {kind: 'doc', term: String(q).replace(/\D/g, '')} : cleanQuery(q);
  if (s.kind === 'doc') {
    const ein = s.term.replace(/\D/g, '');
    return {people: [], nonprofits: await db.q(`select distinct nonprofit_id, nonprofit_name, ein from registry.board_seats where county = $1 and (ein = $2 or nonprofit_id = $3) limit 20`,
      [county, ein, 'np-sb-' + s.term.toLowerCase()])};
  }
  const rev = s.words.length > 1 ? [...s.words.slice(1), s.words[0]].join(' ') : s.term;
  const people = await db.q(`select board_key, display_name, n_current, n_nonprofits, official_name from registry.board_people
    where county = $1 and (name_key like $2 or name_key like $3 or upper(display_name) like $4) order by n_current desc, display_name limit 50`,
  [county, s.term + '%', rev + '%', '%' + s.term + '%']);
  const nonprofits = await db.q(`select nonprofit_id, max(nonprofit_name) nonprofit_name, max(ein) ein, count(distinct board_key)::int people
    from registry.board_seats where county = $1 and upper(nonprofit_name) like $2 group by nonprofit_id order by 2 limit 50`, [county, '%' + s.term + '%']);
  return {people, nonprofits};
}

// Pure: the matches named in a review body (one, or `items` for a bulk change).
function cleanMatches(body) {
  return bulk.items(body, x => {
    const key = String(x.board_key || '');
    if (!BOARD_KEY.test(key)) throw bad('Unknown person.');
    const oid = String(x.official_id || '').slice(0, 80);
    if (!/^[a-z0-9-]{2,80}$/.test(oid)) throw bad('Unknown official.');
    return {board_key: key, official_id: oid};
  });
}

async function review(body, admin) {
  const county = cleanCounty(body.county);
  const status = String(body.status || '');
  if (!REVIEW.includes(status)) throw bad('Unknown review status.');
  const matches = cleanMatches(body);
  const rows = await db.q(`update registry.board_official_matches m set review_status = $1, reviewed_by = $2, reviewed_at = now()
    from jsonb_to_recordset($4::jsonb) as x(board_key text, official_id text)
    where m.county = $3 and m.board_key = x.board_key and m.official_id = x.official_id
    returning m.board_key, m.official_id, m.review_status`, [status, admin || null, county, JSON.stringify(matches)]);
  if (!rows.length) throw bad('Unknown match.', 404);
  // confirmed matches appear on /connections/nonprofits; anything else is taken down
  const [x] = await db.q('select registry.publish_board_officials($1) n', [county]);
  return {updated: rows.length, published: Number(x && x.n) || 0, by: admin, rows};
}

module.exports = {summary, officials, interlocks, donors, person, nonprofit, search, cleanMatches, review};
