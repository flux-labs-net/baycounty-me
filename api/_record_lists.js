// Record lists a government sends that aren't accounting files (Records submission, Phase 2): payroll by job title,
// board appointments and fee or rate changes. Each is read from the government's own spreadsheet (or one short form),
// kept in gov.submissions until staff confirm the preview, then published to its public table with origin 'gov'
// (the site sync never touches those rows). Contract lists live in api/_records.js and follow the same steps.
//
// Privacy (CLAUDE.md): payroll is published by job title only; every employee name in the file is dropped and the
// actual salaries are kept as an unnamed list. Appointments name the appointee only (no address, phone or email).
const crypto = require('crypto');
const {mapColumns} = require('./_finance/detect');
const {money, date: toDate} = require('./_finance/normalize');
const cutoff = require('./_cutoff');

const clean = (v, n = 300) => { if (v === null || v === undefined) return null; const s = (v instanceof Date ? v.toISOString().slice(0, 10) : String(v)).replace(/\s+/g, ' ').trim(); return s ? s.slice(0, n) : null; };
const https = v => { const s = clean(v, 500); return s && /^https:\/\/[^\s<>"]+$/i.test(s) ? s : null; };
const hash = (...p) => crypto.createHash('sha1').update(p.map(x => String(x ?? '')).join('|')).digest('hex');
const yearOf = d => (d ? Number(String(d).slice(0, 4)) : null);
const HOURS_PER_YEAR = 2080;
// Bay County governments' fiscal years start Oct 1: FY2027 = Oct 2026 to Sep 2027.
const fiscalYearOf = (d = new Date()) => d.getUTCFullYear() + (d.getUTCMonth() >= 9 ? 1 : 0);
const GOV_KIND = {county: 'county', schools: 'schools', sheriff: 'constitutional', clerk: 'constitutional', property_appraiser: 'constitutional',
  tax_collector: 'constitutional', soe: 'constitutional'};

const FEE_CATEGORIES = ['utility', 'permit', 'parks', 'trash', 'impact', 'license', 'other'];
const feeCategory = v => {
  const s = String(v || '').toLowerCase();
  if (/water|sewer|utilit|stormwater|electric|gas/.test(s)) return 'utility';
  if (/trash|garbage|solid waste|sanitation|recycl/.test(s)) return 'trash';
  if (/permit|inspection|building|zoning|plan review/.test(s)) return 'permit';
  if (/park|recreation|pool|rental|field|pavilion/.test(s)) return 'parks';
  if (/impact/.test(s)) return 'impact';
  if (/licen|business tax|registration/.test(s)) return 'license';
  return FEE_CATEGORIES.includes(s) ? s : 'other';
};

/* Each kind: the column names it understands, which are required, how one row becomes a record (or a skip reason),
   an optional finish step, and the public table it publishes to. */
const LISTS = {
  payroll: {
    label: 'Payroll (job titles and pay)', every: 'year', table: 'salary_positions', dataset: 'salary-positions',
    hint: 'A payroll or position list: job title and pay at least (annual salary, hourly rate or pay range). Names are removed before anything is published.',
    template: ['Job Title', 'Department', 'Pay Grade', 'Pay Minimum', 'Pay Maximum', 'Annual Salary', 'Hourly Rate', 'Budgeted Positions'],
    fields: {
      title: ['job title', 'title', 'position', 'position title', 'classification', 'job', 'job class', 'job classification'],
      department: ['department', 'dept', 'division', 'office', 'cost center'],
      grade: ['pay grade', 'grade', 'range', 'pay range', 'step'],
      salary: ['annual salary', 'salary', 'annual pay', 'base pay', 'base salary', 'annual rate', 'annual', 'pay', 'amount', 'gross pay'],
      hourly: ['hourly rate', 'hourly', 'rate per hour', 'hourly pay', 'rate'],
      pay_min: ['pay minimum', 'minimum', 'min', 'range minimum', 'pay min', 'salary minimum'],
      pay_max: ['pay maximum', 'maximum', 'max', 'range maximum', 'pay max', 'salary maximum'],
      fte: ['budgeted positions', 'positions', 'fte', 'budgeted fte', 'count', 'headcount', 'number of positions'],
      name: ['name', 'employee', 'employee name', 'full name', 'last name', 'first name', 'employee id'],
    },
    required: [['title'], ['salary', 'hourly', 'pay_min', 'pay_max', 'fte']],
    row(get) {
      const title = clean(get('title'), 200);
      if (!title) return null;
      if (/^(grand )?totals?\b/i.test(title)) return null;
      const salary = money(get('salary')), hourly = money(get('hourly'));
      const annual = salary > 0 ? salary : hourly > 0 ? Math.round(hourly * HOURS_PER_YEAR) : null;
      const r = {title, department: clean(get('department'), 160), grade: clean(get('grade'), 40), annual, pay_min: money(get('pay_min')),
        pay_max: money(get('pay_max')), fte: money(get('fte')), named: Boolean(clean(get('name'), 5))};
      if (!(r.annual > 0) && !(r.pay_min > 0) && !(r.pay_max > 0) && !(r.fte > 0)) return 'no pay or position count';
      return r;
    },
    // One row per job title and department: unnamed salaries listed, pay range kept, positions counted.
    finish(rows) {
      const by = new Map();
      for (const r of rows) {
        const k = `${r.title.toLowerCase()}|${(r.department || '').toLowerCase()}`;
        const g = by.get(k) || {title: r.title, department: r.department, grade: r.grade, salaries: [], pay_min: null, pay_max: null, fte: 0, people: 0, names_removed: 0};
        if (r.annual > 0) { g.salaries.push(r.annual); g.people += 1; }
        if (r.pay_min > 0) g.pay_min = g.pay_min === null ? r.pay_min : Math.min(g.pay_min, r.pay_min);
        if (r.pay_max > 0) g.pay_max = g.pay_max === null ? r.pay_max : Math.max(g.pay_max, r.pay_max);
        if (r.fte > 0) g.fte += r.fte;
        if (r.named) g.names_removed += 1;
        if (!g.grade && r.grade) g.grade = r.grade;
        by.set(k, g);
      }
      return [...by.values()].map(g => ({title: g.title, department: g.department, grade: g.grade, salaries: g.salaries.sort((a, b) => a - b),
        pay_min: g.pay_min, pay_max: g.pay_max, budgeted_fte: g.fte || (g.people || null), names_removed: g.names_removed}));
    },
    total: rows => rows.reduce((a, r) => a + r.salaries.reduce((x, y) => x + y, 0), 0),
    cols: ['employer', 'employer_id', 'government', 'fiscal_year', 'title', 'department', 'category', 'grade', 'pay_min', 'pay_max', 'pay_basis',
      'actual_salaries', 'budgeted_fte', 'source_url', 'notes'],
    toRow: (r, sub, ws, sent) => ({employer: ws.name, employer_id: ws.id, government: GOV_KIND[ws.id] || 'city', fiscal_year: `FY${fiscalYearOf(new Date(sent + 'T12:00:00Z'))}`,
      title: r.title, department: r.department, category: null, grade: r.grade, pay_min: r.pay_min, pay_max: r.pay_max, pay_basis: 'annual',
      actual_salaries: JSON.stringify(r.salaries), budgeted_fte: r.budgeted_fte, source_url: null,
      notes: `Sent by ${ws.name} on ${sent} (${sub.original_name}). Names removed; salaries listed without names.`,
      key: [r.title, r.department]}),
  },

  appointments: {
    label: 'Board appointments', every: 'change', table: 'board_appointments', dataset: 'board-appointments',
    hint: 'Who sits on each advisory board or authority you appoint: board, member and term at least. Excel or CSV.',
    template: ['Board', 'Seat', 'Member', 'Appointed By', 'Term Start', 'Term End', 'Notes'],
    fields: {
      board: ['board', 'board name', 'committee', 'commission', 'authority', 'council', 'advisory board'],
      seat: ['seat', 'position', 'district', 'seat name', 'role', 'office'],
      person: ['member', 'name', 'appointee', 'member name', 'person', 'board member'],
      appointed_by: ['appointed by', 'appointing authority', 'nominated by', 'appointed'],
      term_start: ['term start', 'start', 'appointed on', 'appointment date', 'start date', 'term begins', 'from'],
      term_end: ['term end', 'end', 'expires', 'expiration', 'end date', 'term expires', 'to'],
      notes: ['notes', 'note', 'comments'],
      link: ['link', 'url', 'document', 'resolution link', 'source'],
    },
    required: [['board'], ['person']],
    row(get) {
      const board = clean(get('board'), 160), person = clean(get('person'), 120);
      if (!board && !person) return null;
      if (!board) return 'no board';
      if (!person) return 'no member name';
      if (/^vacan/i.test(person)) return 'vacant seat';
      const start = toDate(get('term_start')), end = toDate(get('term_end'));
      if (end && yearOf(end) < cutoff.FIRST_YEAR) return 'term ended before 2016';
      return {board, seat: clean(get('seat'), 120), person, appointed_by: clean(get('appointed_by'), 160), term_start: start, term_end: end,
        notes: clean(get('notes'), 400), source_url: https(get('link'))};
    },
    cols: ['government', 'board', 'seat', 'person', 'appointed_by', 'term_start', 'term_end', 'notes', 'source_url', 'source_title', 'gov_id'],
    toRow: (r, sub, ws, sent) => ({government: ws.name, board: r.board, seat: r.seat, person: r.person, appointed_by: r.appointed_by,
      term_start: r.term_start, term_end: r.term_end, notes: r.notes, source_url: r.source_url, source_title: `Sent by ${ws.name} on ${sent}`,
      gov_id: ws.id, key: [r.board, r.seat, r.person, r.term_start]}),
  },

  fees: {
    label: 'Fee or rate changes', every: 'change', table: 'fee_changes', dataset: 'fee-changes',
    hint: 'A new or changed fee or utility rate: what it is, the new amount and when it starts. Excel or CSV.',
    template: ['Fee', 'Category', 'Old Amount', 'New Amount', 'Unit', 'Effective Date', 'Adopted By', 'Document Link'],
    fields: {
      fee: ['fee', 'fee name', 'rate', 'rate name', 'item', 'service', 'description', 'charge'],
      category: ['category', 'type', 'department', 'fee type'],
      old_amount: ['old amount', 'old rate', 'current amount', 'current rate', 'previous', 'old', 'current', 'from'],
      new_amount: ['new amount', 'new rate', 'proposed', 'adopted amount', 'new', 'amount', 'to'],
      unit: ['unit', 'per', 'basis', 'unit of measure', 'billing unit'],
      effective: ['effective date', 'effective', 'starts', 'start date', 'date'],
      adopted_by: ['adopted by', 'ordinance', 'resolution', 'approved by', 'ordinance or resolution'],
      link: ['document link', 'link', 'url', 'document', 'source'],
    },
    required: [['fee'], ['new_amount']],
    row(get) {
      const fee = clean(get('fee'), 200);
      const amt = money(get('new_amount'));
      if (!fee && amt === null) return null;
      if (!fee) return 'no fee name';
      if (amt === null) return 'no new amount';
      const eff = toDate(get('effective'));
      if (eff && yearOf(eff) < cutoff.FIRST_YEAR) return 'before 2016';
      return {fee, category: feeCategory(get('category') || fee), old_amount: money(get('old_amount')), new_amount: amt, unit: clean(get('unit'), 80),
        effective_date: eff, adopted_by: clean(get('adopted_by'), 200), source_url: https(get('link'))};
    },
    cols: ['government', 'fee', 'category', 'old_amount', 'new_amount', 'unit', 'effective_date', 'adopted_by', 'source_url', 'source_title', 'gov_id'],
    toRow: (r, sub, ws, sent) => ({government: ws.name, fee: r.fee, category: r.category, old_amount: r.old_amount, new_amount: r.new_amount,
      unit: r.unit, effective_date: r.effective_date, adopted_by: r.adopted_by, source_url: r.source_url, source_title: `Sent by ${ws.name} on ${sent}`,
      gov_id: ws.id, key: [r.fee, r.unit, r.new_amount, r.effective_date]}),
  },
};

// Pure: a grid of cells -> {ok, missing, headers, mapping, rows, skipped, reasons} for one list kind.
function readList(kind, grid) {
  const spec = LISTS[kind];
  let best = null;
  grid.slice(0, 40).forEach((row, idx) => {
    if (row.filter(v => typeof v === 'string' && /[a-z]/i.test(v)).length < 2) return;
    const headers = row.map(v => (typeof v === 'string' ? v : v instanceof Date ? '' : String(v ?? '')));
    const m = mapColumns(headers, spec.fields), ok = spec.required.every(a => a.some(f => m[f] !== undefined));
    const score = (ok ? 100 : 0) + Object.keys(m).length;
    if (!best || score > best.score) best = {score, idx, headers, m, ok};
  });
  if (!best) return {ok: false, missing: ['a header row'], headers: [], mapping: {}, rows: [], skipped: 0, reasons: {}};
  const missing = spec.required.filter(a => !a.some(f => best.m[f] !== undefined)).map(a => a.map(f => f.replace(/_/g, ' ')).join(' or '));
  const mapping = Object.fromEntries(Object.entries(best.m).map(([f, i]) => [f, best.headers[i]]));
  if (missing.length) return {ok: false, missing, headers: best.headers, mapping, rows: [], skipped: 0, reasons: {}};
  const rows = [], reasons = {};
  for (const r of grid.slice(best.idx + 1)) {
    const got = spec.row(f => (best.m[f] === undefined ? undefined : r[best.m[f]]));
    if (got === null) continue;
    if (typeof got === 'string') { reasons[got] = (reasons[got] || 0) + 1; continue; }
    rows.push(got);
  }
  const out = spec.finish ? spec.finish(rows) : rows;
  return {ok: true, missing: [], headers: best.headers, mapping, rows: out, skipped: Object.values(reasons).reduce((a, n) => a + n, 0), reasons};
}

// Pure: one short form (an object of field -> value) -> the same result as a one-row file.
// Pure: a submission's rows -> rows for the kind's public table.
function listRows(kind, sub, ws) {
  const spec = LISTS[kind];
  const sent = String(sub.submitted_at instanceof Date ? sub.submitted_at.toISOString() : sub.submitted_at || new Date().toISOString()).slice(0, 10);
  return (sub.rows || []).map(r => {
    const {key, ...row} = spec.toRow(r, sub, ws, sent);
    return {...row, gov_id: ws.id, record_hash: `gov:${sub.id}:${hash(...key)}`};
  });
}

module.exports = {LISTS, FEE_CATEGORIES, readList, listRows, feeCategory, fiscalYearOf};
