// Votes read from meeting minutes, for the /admin "Votes from minutes" tab (admin only). Tables from
// db/migrations/0055_minutes_votes.sql, written by data/minutes/read_minutes.py: one read per minutes file, one row
// per motion with the printed roll call, the votes matched to officeholders and the checks that failed. Flagged
// motions (and a 1-in-50 sample of passing ones) wait here; approving publishes a flagged motion on the next export
// (data/minutes/export_votes.py, run by the daily meetings refresh), rejecting keeps any motion off the site.
// Files starting with _ are not routes.
const db = require('./_db');
const bulk = require('./_bulk');

const bad = (msg, status = 400) => Object.assign(new Error(msg), {status});
const missing = e => e && (e.code === '42P01' || e.code === '3F000');
const REVIEW = ['unreviewed', 'approved', 'rejected'];
const QUEUES = ['flagged', 'sample', 'passed', 'all'];
const BOARD = /^[a-z][a-z-]{1,15}$/;

// What each check code means, shown next to the motion.
const CHECKS = {
  tally_mismatch: 'Named votes don’t add up to the printed tally',
  unmatched_name: 'A name matched no officeholder',
  off_term: 'A voter wasn’t in office on this date (per officeholder terms)',
  no_vote_detail: 'Minutes give the outcome but no vote count or names',
  no_quorum: 'Fewer than a majority of seats voted',
  too_many_votes: 'More votes than seats',
  outcome_mismatch: 'Outcome disagrees with the count',
  outcome_unclear: 'Outcome isn’t clear',
  no_roster: 'No officeholders on file for this board and date',
  date_mismatch: 'Meeting date differs from the file’s date',
  no_date: 'No meeting date',
};

// Pure: filters -> SQL where clause and params (tested without a database).
function where({queue = 'flagged', board = '', year = '', status = 'unreviewed', q = ''} = {}) {
  const p = []; const w = [];
  if (!QUEUES.includes(queue)) throw bad('Unknown queue.');
  if (queue === 'flagged') w.push(`m.check_status = 'flagged'`);
  if (queue === 'sample') w.push(`m.sampled`);
  if (queue === 'passed') w.push(`m.check_status = 'passed'`);
  if (status) { if (!REVIEW.includes(status)) throw bad('Unknown review status.'); p.push(status); w.push(`m.review_status = $${p.length}`); }
  if (board) { if (!BOARD.test(board)) throw bad('Unknown board.'); p.push(board); w.push(`m.board = $${p.length}`); }
  const y = parseInt(year, 10);
  if (y) { if (y < 2016 || y > 2100) throw bad('Unknown year.'); p.push(y); w.push(`extract(year from m.meeting_date) = $${p.length}`); }
  const term = String(q || '').trim().slice(0, 80);
  if (term) { p.push('%' + term.toLowerCase() + '%'); w.push(`(lower(m.motion) like $${p.length} or lower(coalesce(m.item_title, '')) like $${p.length})`); }
  return {sql: w.length ? w.join(' and ') : 'true', params: p};
}

function cleanIds(body) {
  return bulk.items(body, x => {
    const id = parseInt(x.id != null ? x.id : x.value, 10);
    if (!(id > 0)) throw bad('Unknown motion.');
    return {id};
  });
}

async function report(filters = {}) {
  let totals;
  try {
    [totals] = await db.q(`select
        (select count(*) from agendas.documents where kind = 'minutes')::int files,
        (select count(*) from agendas.minutes_reads where status = 'ok')::int read,
        (select count(*) from agendas.minutes_reads where status = 'submitted')::int waiting,
        (select count(*) from agendas.minutes_reads where status in ('failed', 'no_text'))::int unread,
        (select count(*) from agendas.motions)::int motions,
        (select count(*) from agendas.motions where check_status = 'passed' and review_status <> 'rejected')::int passed,
        (select count(*) from agendas.motions where check_status = 'flagged' and review_status = 'unreviewed')::int flagged,
        (select count(*) from agendas.motions where sampled and review_status = 'unreviewed')::int sample,
        (select count(*) from agendas.motions where review_status = 'approved')::int approved,
        (select count(*) from agendas.motions where review_status = 'rejected')::int rejected,
        (select coalesce(sum(cost_usd), 0) from agendas.minutes_reads)::float cost,
        (select coalesce(sum(est_cost_usd), 0) from agendas.minutes_batches where status = 'in_progress')::float in_flight`);
  } catch (e) {
    if (missing(e)) return {installed: false};
    throw e;
  }
  const coverage = await db.q(`select d.board, extract(year from d.meeting_date)::int yr, count(*)::int files,
      count(r.id) filter (where r.status = 'ok')::int read, coalesce(sum(r.motion_count), 0)::int motions
      from agendas.documents d left join agendas.minutes_reads r on r.document_id = d.id and r.sha256 = d.current_sha256
      where d.kind = 'minutes' and d.meeting_date >= date '2016-01-01' group by 1, 2 order by 1, 2`);
  const checks = await db.q(`select c code, count(*)::int n from agendas.motions m, jsonb_array_elements_text(m.checks) c
      where m.review_status = 'unreviewed' group by 1 order by 2 desc`);
  const batches = await db.q(`select batch_id, status, requests, est_cost_usd::float est, cost_usd::float cost, submitted_at, collected_at
      from agendas.minutes_batches order by id desc limit 10`);
  const w = where(filters);
  const motions = await db.q(`select m.id, m.board, m.meeting_date, m.meeting_type, m.item_number, m.item_title, m.motion, m.summary, m.kind,
      m.consent, m.mover, m.seconder, m.outcome, m.tally_printed, m.tally, m.printed, m.votes, m.vote_method, m.amount, m.page,
      m.unmatched, m.checks, m.check_status, m.sampled, m.review_status, m.review_note, m.reviewed_by, m.reviewed_at,
      d.url, d.title doc_title, (select v.id from agendas.versions v where v.document_id = d.id and v.sha256 = d.current_sha256 limit 1) version_id
      from agendas.motions m join agendas.documents d on d.id = m.document_id
      where ${w.sql} order by m.meeting_date desc nulls last, m.board, m.position limit 300`, w.params);
  return {installed: true, totals, coverage, checks, batches, motions, check_labels: CHECKS};
}

async function review(body, admin) {
  const status = String(body.status || '');
  if (!REVIEW.includes(status)) throw bad('Unknown review status.');
  const ids = cleanIds(body).map(x => x.id);
  const note = body.note == null ? null : String(body.note).slice(0, 500);
  const rows = await db.q(`update agendas.motions set review_status = $1, reviewed_by = $2, reviewed_at = now(),
      review_note = coalesce($4, review_note) where id = any($3::bigint[]) returning id, review_status`,
  [status, status === 'unreviewed' ? null : admin || null, ids, note]);
  if (!rows.length) throw bad('Unknown motion.', 404);
  return {updated: rows.length, by: admin, rows};
}

module.exports = {CHECKS, where, cleanIds, report, review};
