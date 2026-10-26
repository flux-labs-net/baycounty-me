// Progress of the data backfill: how many minutes files each board's archive lists per year, how many we have
// captured, read and checked. Counts only. Read from the public view minutes_progress (db/migrations/0055) and the
// public ingest_runs log. Used by GET /api/v1/import-progress (the live section on /data-sources) and, with costs
// added, by the /admin "Import progress" tab. Files starting with _ are not routes.
const FIRST_YEAR = 2016;
const PER_RUN = 150;          // read_minutes.py MINUTES_SUBMIT_MAX default
const RUNS_PER_DAY = 8;       // .github/workflows/read-minutes.yml runs every 3 hours
const COST_PER_FILE = 0.04;   // read_minutes.estimate() for a typical 15-page file at batch prices, until real reads exist

// Board id -> [government id, name]. Same ids as data/minutes/match.py BOARDS.
const BOARDS = {
  county: ['county', 'Bay County Commission'], schools: ['schools', 'Bay District School Board'],
  pc: ['pc', 'Panama City Commission'], 'pc-cra': ['pc', 'Panama City CRA Board'], pcb: ['pcb', 'Panama City Beach Council'],
  lh: ['lh', 'Lynn Haven Commission'], 'lh-cra': ['lh', 'Lynn Haven CRA Board'], cw: ['cw', 'Callaway Commission'],
  'cw-cra': ['cw', 'Callaway CRA Board'], sp: ['sp', 'Springfield Commission'], parker: ['parker', 'Parker Council'],
  mb: ['mb', 'Mexico Beach Council'],
};

// What we know about years that aren't online (checked 2026-10-26, data/minutes/README_minutes.md).
const NOTES = {
  schools: 'Minutes before 2022 aren’t online; a records request is needed.',
  lh: 'No 2016–2017 commission minutes are posted.',
  pcb: '2019 and 2022–2024 are mostly missing online; they’re printed as drafts in the next meeting’s agenda packet.',
  mb: 'Minutes before 2022 aren’t posted.',
  parker: '2016 and 2017 are one file per year.',
  sp: 'Minutes online start in 2018.',
  pc: '2016–2019 files are scans, read with OCR.',
  cw: 'Scanned files, read with OCR.',
};

const n = v => Number(v) || 0;
const pct = (a, b) => (b > 0 ? Math.min(100, Math.round((a / b) * 1000) / 10) : 0);
const latest = xs => xs.filter(Boolean).map(x => new Date(x).toISOString()).sort().pop() || null;

function runKind(r) {
  if (r.dataset === 'minutes_votes') return 'read';
  if (/minutes backfill/.test(r.notes || '')) return 'crawl';
  return null;
}

// Pure: view rows + run log -> the dashboard. opts.cost (admin only) = {spent, in_flight, avg, budget}.
function summarize(rows, runs = [], opts = {}) {
  const now = opts.now ? new Date(opts.now) : new Date();
  const lastYear = Math.max(now.getUTCFullYear(), ...rows.map(r => n(r.year)));
  const years = [];
  for (let y = FIRST_YEAR; y <= lastYear; y++) years.push(y);
  const byBoard = new Map();
  for (const r of rows) {
    if (n(r.year) < FIRST_YEAR || !r.board) continue;
    if (!byBoard.has(r.board)) byBoard.set(r.board, new Map());
    byBoard.get(r.board).set(n(r.year), r);
  }
  const order = Object.keys(BOARDS).filter(b => byBoard.has(b)).concat([...byBoard.keys()].filter(b => !BOARDS[b]).sort());
  const T = {found: 0, listed: 0, captured: 0, read: 0, reading: 0, unreadable: 0, motions: 0, passed: 0, flagged: 0, reviewed: 0,
    pages: 0, ocr_pages: 0, read_7d: 0, failed: 0, gaps: 0, boards: order.length, listed_boards: 0};
  const boards = order.map(b => {
    const m = byBoard.get(b);
    const t = {found: 0, captured: 0, read: 0, motions: 0, passed: 0, flagged: 0};
    let listedAny = false;
    const cells = years.map(y => {
      const r = m.get(y) || {};
      const listed = r.listed == null ? null : n(r.listed);
      if (listed != null) listedAny = true;
      const c = {year: y, listed, captured: n(r.captured), read: n(r.read), reading: n(r.reading), unreadable: n(r.unreadable),
        motions: n(r.motions), passed: n(r.passed), flagged: n(r.flagged), year_files: n(r.year_files)};
      c.found = Math.max(listed || 0, c.captured);
      c.state = c.found === 0 ? (listed === 0 ? 'none_online' : 'not_listed')
        : c.read + c.unreadable >= c.found ? (c.flagged ? 'reviewing' : 'done')
          : c.read || c.reading ? 'reading' : c.captured ? 'captured' : 'found';
      for (const k of ['found', 'captured', 'read', 'motions', 'passed', 'flagged']) t[k] += c[k];
      for (const k of ['captured', 'read', 'reading', 'unreadable', 'motions', 'passed', 'flagged']) T[k] += c[k];
      T.found += c.found; T.listed += listed || 0;
      T.reviewed += n(r.reviewed); T.pages += n(r.pages); T.ocr_pages += n(r.ocr_pages); T.read_7d += n(r.read_7d); T.failed += n(r.failed);
      if (c.state === 'none_online') T.gaps += 1;
      return c;
    });
    if (listedAny) T.listed_boards += 1;
    const [gov, name] = BOARDS[b] || [null, b];
    return {board: b, gov, name, note: NOTES[b] || null, totals: {...t, pct_read: pct(t.read, t.found)}, years: cells};
  });

  const done = T.read + T.unreadable;
  const checked = T.passed + T.reviewed;
  const stages = [
    {key: 'found', label: 'Found in the archives', value: T.found, of: null, pct: T.listed_boards ? 100 : 0,
      detail: T.listed_boards ? `${T.listed_boards} of ${T.boards || Object.keys(BOARDS).length} boards’ archives counted` : 'Archives not counted yet'},
    {key: 'captured', label: 'Downloaded and stored', value: T.captured, of: T.found, pct: pct(T.captured, T.found),
      detail: T.failed ? `${T.failed} downloads failed; retried on the next crawl` : null},
    {key: 'read', label: 'Read into motions', value: done, of: T.captured, pct: pct(done, T.captured),
      detail: T.reading ? `${T.reading} being read now` : null},
    {key: 'checked', label: 'Votes checked', value: checked, of: T.motions, pct: pct(checked, T.motions),
      detail: T.flagged ? `${T.flagged} waiting for a person to review` : null},
  ];
  for (const s of stages) s.state = s.pct >= 100 ? 'done' : s.value > 0 || s.pct > 0 ? 'active' : 'waiting';

  let phase;
  if (!T.found) phase = {key: 'not_started', text: 'Not started yet. The first step counts the minutes files in each government’s archive.'};
  else if (T.captured < T.found) phase = {key: 'capturing', text: `Downloading minutes: ${T.captured.toLocaleString('en-US')} of ${T.found.toLocaleString('en-US')} files stored.`};
  else if (done < T.captured) phase = {key: 'reading', text: `Reading minutes: ${done.toLocaleString('en-US')} of ${T.captured.toLocaleString('en-US')} files read.`};
  else if (T.flagged) phase = {key: 'reviewing', text: `Every file is read. ${T.flagged.toLocaleString('en-US')} votes are waiting for a person to check them.`};
  else phase = {key: 'current', text: 'Up to date. New minutes are read as governments post them.'};

  const left = Math.max(0, T.found - done);
  const paced = T.read_7d > 0;
  const perDay = paced ? Math.round(T.read_7d / 7) || 1 : PER_RUN * RUNS_PER_DAY;
  const eta = {files_left: left, per_day: perDay, basis: paced ? 'pace' : 'schedule',
    days: left ? Math.ceil(left / perDay) : 0,
    note: paced ? 'At the pace of the last 7 days.' : `At the scheduled pace of up to ${PER_RUN} files every 3 hours.`};

  const mine = runs.map(r => ({...r, kind: runKind(r)})).filter(r => r.kind).slice(0, 12)
    .map(r => ({kind: r.kind, started_at: r.started_at, finished_at: r.finished_at, status: r.status, rows: r.rows_in ?? null}));
  const last = {listed_at: latest(rows.map(r => r.listed_at)), captured_at: latest(rows.map(r => r.last_captured_at)),
    read_at: latest(rows.map(r => r.last_read_at)), crawl: mine.find(r => r.kind === 'crawl') || null, read: mine.find(r => r.kind === 'read') || null};

  const out = {installed: true, as_of: now.toISOString(), first_year: FIRST_YEAR, years, phase, stages,
    totals: {...T, pct_read: pct(T.read, T.found), ocr_share: pct(T.ocr_pages, T.pages)}, eta, last, runs: mine, boards,
    method: 'Counts come from the BayCounty.me database. “Found” is the number of minutes files each archive lists, or the number we have stored when that’s higher. A file is read when our automated reader has turned it into motions and roll calls; a vote is checked when the names add up to the printed tally and every voter held the seat that day, or a person reviewed it. Checked votes reach the votes data the next morning.'};
  if (opts.cost) {
    const c = opts.cost, avg = c.avg > 0 ? c.avg : COST_PER_FILE;
    const unsent = Math.max(0, T.found - done - T.reading);
    out.cost = {spent: n(c.spent), in_flight: n(c.in_flight), avg_per_file: Math.round(avg * 10000) / 10000, avg_basis: c.avg > 0 ? 'actual' : 'estimate',
      left: Math.round(unsent * avg * 100) / 100, budget: n(c.budget) || null};
    out.cost.total = Math.round((out.cost.spent + out.cost.in_flight + out.cost.left) * 100) / 100;
  }
  return out;
}

const RUNS_QUERY = 'ingest_runs?select=dataset,started_at,finished_at,status,rows_in,notes&dataset=in.(minutes_votes,agenda_documents)&order=id.desc&limit=200';

// Public: through the database's REST API (anon key), like the rest of /api/v1.
async function publicProgress(rest) {
  let rows;
  try { rows = (await rest('minutes_progress?select=*&limit=2000')).rows; }
  catch (e) { if (e.status === 502 || e.status === 400) return {installed: false, note: 'Progress numbers aren’t available right now.'}; throw e; }
  let runs = [];
  try { runs = (await rest(RUNS_QUERY)).rows; } catch (e) { runs = []; }
  return summarize(rows, runs);
}

module.exports = {summarize, publicProgress, BOARDS, NOTES, PER_RUN, RUNS_PER_DAY, COST_PER_FILE, FIRST_YEAR};
