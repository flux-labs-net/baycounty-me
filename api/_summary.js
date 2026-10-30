// Counts for the To do page on /admin: how much is waiting in each review queue, outreach list and problem list.
// One query per count; a count whose table isn't there (or fails) comes back null so the rest still show.
// Keys match MENU in site/admin_page.py and TODO in site/admin.js. Files starting with _ are not routes.
const db = require('./_db');

const COUNTS = {
  owners: `select count(*)::int n from registry.shared_owner_groups where county = 'bay' and review_status = 'unreviewed'`,
  limits: `select count(*)::int n from registry.limit_cases where county = 'bay' and review_status = 'unreviewed'`,
  boards: `select count(*)::int n from registry.board_official_matches where county = 'bay' and review_status = 'unreviewed'`,
  ties: `select count(*)::int n from careers.matches where county = 'bay' and review_status = 'unreviewed'`,
  accounting: `select count(*)::int n from ingest.staging where review_status = 'pending'`,
  replies: `select ((select count(*) from corr.threads where status = 'replied')
            + (select count(*) from corr.messages where thread_id is null and direction = 'in'))::int n`,
  records: `select count(*)::int n from corr.records_requests where status = 'draft'`,
  syncs: `select count(*)::int n from (select distinct on (dataset) status from ingest_runs where dataset is not null
            and started_at > now() - interval '60 days' order by dataset, id desc) x where status = 'failed'`,
  agendas: `select count(*)::int n from agendas.errors where resolved_at is null and at > now() - interval '14 days'`,
  minutes: `select count(*)::int n from agendas.motions where review_status = 'unreviewed' and (check_status = 'flagged' or sampled)`,
  govflags: `select count(*)::int n from gov.flags where status = 'open'`,
};

// q: the query function (db.q), passed in so tests can fake it.
async function summary(q = db.q) {
  const keys = Object.keys(COUNTS);
  const vals = await Promise.all(keys.map(k => q(COUNTS[k]).then(rows => Number(rows[0] && rows[0].n) || 0, () => null)));
  return {counts: Object.fromEntries(keys.map((k, i) => [k, vals[i]])), checked_at: new Date().toISOString()};
}

module.exports = {summary, COUNTS};
