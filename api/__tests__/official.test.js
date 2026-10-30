// The elected officials' dashboard (api/_official.js): who sits on the board, which meetings are theirs, and how a
// voting record is counted. Pure functions; the database side is in gov-api.test.js.
const test = require('node:test');
const assert = require('node:assert/strict');
const O = require('../_official');

const TERMS = [
  {person_id: 'a', person_name: 'Ann A', seat: 'Mayor', seat_order: 0, body: 'City Commission', start_date: '2022-04-12', end_date: null},
  {person_id: 'b', person_name: 'Bo B', seat: 'Seat 1', seat_order: 1, body: 'City Commission', start_date: '2018-04-10', end_date: '2024-04-09'},
  {person_id: 'c', person_name: 'Cy C', seat: 'Seat 1', seat_order: 1, body: 'City Commission', start_date: '2024-04-09', end_date: null},
  {person_id: null, person_name: null, seat: 'Seat 2', seat_order: 2, body: 'City Commission', start_date: '2025-01-01', end_date: null, vacant: true},
  {person_id: 'd', person_name: 'Di D', seat: 'Seat 3', seat_order: 3, body: 'City Commission', start_date: '2027-01-01', end_date: null},
];

test('the board is who holds a seat today, in seat order', () => {
  assert.deepEqual(O.seats(TERMS, '2026-10-30').map(s => s.person_id), ['a', 'c']);
  assert.deepEqual(O.seats(TERMS, '2020-01-01').map(s => s.person_id), ['b']);
  assert.deepEqual(O.career(TERMS, 'b'), [{seat: 'Seat 1', body: 'City Commission', start: '2018-04-10', end: '2024-04-09', how: null}]);
});

test('meetings: only this government’s boards (and its CRA), coming up in the next 90 days', () => {
  const rows = [
    {board: 'lh', title: 'Regular', start: '2026-11-10T17:00:00-06:00', agenda_url: 'https://x', items: [{title: 'Paving bid', amount: '$84,500.00'}, {title: 'Minutes'}]},
    {board: 'lh-cra', title: 'CRA', start: '2026-11-17', agenda_items: ['Façade grants']},
    {board: 'lh', title: 'Far off', start: '2027-06-01'},
    {board: 'lhx', title: 'Not ours', start: '2026-11-10'},
    {board: 'pc', title: 'Not ours', start: '2026-11-10'},
    {board: 'lh', title: 'Last month', start: '2026-10-14', minutes_url: 'https://m'},
    {board: 'lh', title: 'Cancelled', start: '2026-11-24', cancelled: true},
  ];
  const m = O.meetings(rows, 'lh', '2026-10-30');
  assert.deepEqual(m.upcoming.map(x => x.title), ['Regular', 'CRA', 'Cancelled']);
  assert.equal(m.upcoming[0].money_items, 1);
  assert.equal(m.upcoming[0].money_total, 84500);
  assert.deepEqual(m.upcoming[1].items, [{title: 'Façade grants'}], 'agenda items given as plain text');
  assert.equal(m.upcoming[1].board_name, 'CRA Board');
  assert.equal(m.upcoming[2].status, 'cancelled');
  assert.deepEqual(m.recent.map(x => x.title), ['Last month']);
});

test('voting record: counts, attendance and the losing side of split votes', () => {
  const rows = [
    {date: '2026-09-08', vote: 'yes', headline: 'Budget', vote_id: 'v1'},
    {date: '2026-09-22', vote: 'No', headline: 'Fee increase', vote_id: 'v2'},
    {date: '2026-10-13', vote: 'absent', headline: 'Minutes', vote_id: 'v3'},
    {date: '2025-03-01', vote: 'yes', headline: 'Denied rezoning', vote_id: 'v4'},
    {date: '2025-04-01', vote: 'abstain', headline: 'Own business', vote_id: 'v5'},
  ];
  const meta = [{vote_id: 'v1', outcome: 'passed', split: false}, {vote_id: 'v2', outcome: 'passed', tally: '3-2', split: true},
    {vote_id: 'v3', outcome: 'passed', split: false}, {vote_id: 'v4', outcome: 'failed', tally: '2-3', split: true, amount: '1200000'}];
  const r = O.voteRecord(rows, meta);
  assert.deepEqual(r.count, {votes: 5, yes: 2, no: 1, absent: 1, abstain: 1, split: 2, on_losing_side: 2});
  assert.equal(r.present_rate, 80);
  assert.deepEqual(r.by_year.map(y => [y.year, y.votes]), [[2026, 3], [2025, 2]]);
  assert.equal(r.recent[0].date, '2026-10-13', 'newest first');
  assert.equal(r.split_votes.length, 2);
  assert.equal(r.split_votes.find(v => v.vote_id === 'v4').amount, 1200000);
  assert.equal(r.first, '2025-03-01');
  assert.deepEqual(O.voteRecord([]).count.votes, 0);
});

test('contracts: the last 12 months, newest first, with the total', () => {
  const c = O.contracts([{date: '2026-10-01', vendor: 'A', amount: 100}, {date: '2025-10-29', vendor: 'Old', amount: 5}, {date: '2026-01-05', vendor: 'B', amount: '50.5'}], '2026-10-30');
  assert.deepEqual(c.rows.map(x => x.vendor), ['A', 'B']);
  assert.equal(c.total, 150.5);
  assert.equal(c.from, '2025-10-30');
});

test('budget: adopted totals by year, and the last two compared', () => {
  const row = (fy, section, key, amount, extra = {}) => ({government: 'City of X', gov_id: 'x', fiscal_year: fy, basis: 'adopted', section, line_key: key, name: key, amount, ...extra});
  const b = O.budget([row(2025, 'total', 'total', 100), row(2026, 'total', 'total', 110), row(2026, 'total', 'general_fund', 40),
    row(2025, 'department', 'police', 20), row(2026, 'department', 'police', 25)], 'x');
  assert.deepEqual(b.history, [{fiscal_year: 2025, total: 100}, {fiscal_year: 2026, total: 110, general_fund: 40}]);
  assert.equal(b.compare.from, 2025);
  assert.equal(b.compare.departments[0].change, 5);
  assert.equal(b.compare.by, 'department');
  // A new year with only fund lines compares funds, not departments that would all read as cut to zero.
  const f = O.budget([row(2025, 'total', 'total', 100), row(2026, 'total', 'total', 110), row(2025, 'department', 'police', 20),
    row(2025, 'fund', 'f1', 60, {fund_type: 'general'}), row(2026, 'fund', 'f1', 70, {fund_type: 'general'})], 'x');
  assert.equal(f.compare.by, 'fund');
  assert.equal(f.compare.departments[0].change, 10);
  assert.equal(O.budget([], 'x'), null);
});

test('every report the page offers has a name for the activity log', () => {
  assert.deepEqual(Object.keys(O.REPORTS).sort(), ['agendas', 'briefing', 'numbers', 'votes']);
});
