// Step two of records intake: never take a government's file as the true source. Every file a government confirms
// is checked against records BayCounty.me collects on its own (contracts and votes read from agendas and minutes,
// adopted budgets, the state's annual financial report figures, published pay, scraped check registers). We assume
// numbers are missing and look for them until we can't confirm something.
//
// Each check is {check, status, detail, expected?, found?, source_url?}:
//   match        our own record agrees with the file
//   mismatch     our own record disagrees (the difference is in detail/expected/found)
//   missing      something our records say should be in the file isn't
//   unconfirmed  we found nothing to check it against, so it isn't verified
// A file is 'verified' only when every check is a match; any mismatch or missing makes it 'discrepancies'; otherwise
// it's 'unverified'. Only verified files publish on their own; the rest wait for the BayCounty.me admin.
// Pure scoring functions take the file's rows and the reference rows, so they can be tested without a database.

const BIG_PAYMENT = 25000;          // payments this size or more need an approval we can find
const AMOUNT_TOLERANCE = 0.01;      // 1%: amounts within this are the same figure
const TOTAL_TOLERANCE = 0.02;       // 2% for totals that are rounded or defined slightly differently
const DATE_WINDOW_DAYS = 120;       // an award and its approval can be this far apart
const MAX_LISTED = 25;              // individual findings listed per check before summarizing

const norm = s => String(s || '').toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9 ]+/g, ' ')
  .replace(/\b(inc|llc|l l c|co|corp|corporation|company|ltd|lp|llp|pllc|pa|the|of|dba)\b/g, ' ').replace(/\s+/g, ' ').trim();
const tokens = s => new Set(norm(s).split(' ').filter(w => w.length > 2));
function sameName(a, b) {
  const A = tokens(a), B = tokens(b);
  if (!A.size || !B.size) return false;
  let n = 0;
  for (const w of A) if (B.has(w)) n++;
  return n / Math.min(A.size, B.size) >= 0.6;
}
const num = v => (v === null || v === undefined || v === '' ? null : Number(v));
const close = (a, b, tol = AMOUNT_TOLERANCE) => a !== null && b !== null && Math.abs(a - b) <= Math.max(1, Math.abs(b) * tol);
const days = (a, b) => Math.abs((new Date(a) - new Date(b)) / 864e5);
const usd = n => (n === null || n === undefined ? '' : '$' + Math.round(Number(n)).toLocaleString('en-US'));
const sum = (rows, f) => rows.reduce((a, r) => a + (Number(f(r)) || 0), 0);

function summarize(checks) {
  const counts = {match: 0, mismatch: 0, missing: 0, unconfirmed: 0};
  for (const c of checks) counts[c.status] = (counts[c.status] || 0) + 1;
  const status = !checks.length ? 'unverified' : counts.mismatch || counts.missing ? 'discrepancies' : counts.unconfirmed ? 'unverified' : 'verified';
  return {status, counts, checks};
}
// Many findings of one kind become the first MAX_LISTED plus one line saying how many more.
function capped(list, label) {
  if (list.length <= MAX_LISTED) return list;
  const more = list.length - MAX_LISTED, st = list[MAX_LISTED].status;
  return [...list.slice(0, MAX_LISTED), {check: label, status: st, detail: `${more} more like this`}];
}

/* ---------- contracts ---------- */
// ref: contracts and votes we read from agendas/minutes (origin not 'gov'), emergency purchases, change orders.
function checkContracts(rows, ref, period) {
  const out = [], used = new Set();
  for (const r of rows) {
    const cands = ref.contracts.filter(c => sameName(c.vendor, r.vendor) && (!r.date || !c.date || days(c.date, r.date) <= DATE_WINDOW_DAYS));
    const exact = cands.find(c => close(num(c.amount), r.amount));
    if (exact) { used.add(exact.id); out.push({check: 'Contract approved on an agenda', status: 'match', detail: `${r.vendor}, ${usd(r.amount)}`, source_url: exact.source_url}); continue; }
    if (cands.length) {
      const c = cands[0]; used.add(c.id);
      out.push({check: 'Contract approved on an agenda', status: 'mismatch', detail: `${r.vendor}: the file says ${usd(r.amount)}, the approval says ${usd(c.amount)}`,
        expected: num(c.amount), found: r.amount, source_url: c.source_url});
      continue;
    }
    const v = ref.votes.find(x => close(num(x.amount), r.amount) && (sameName(x.headline, r.vendor) || sameName(x.summary, r.vendor)) && (!r.date || days(x.date, r.date) <= DATE_WINDOW_DAYS));
    if (v) { out.push({check: 'Contract approved on an agenda', status: 'match', detail: `${r.vendor}, ${usd(r.amount)} (vote on ${v.date})`, source_url: v.source_url}); continue; }
    const e = ref.emergency.find(x => sameName(x.vendor, r.vendor) && close(num(x.amount), r.amount));
    if (e) { out.push({check: 'Emergency purchase on record', status: 'match', detail: `${r.vendor}, ${usd(r.amount)}`, source_url: e.source_url}); continue; }
    out.push({check: 'Contract approved on an agenda', status: 'unconfirmed', detail: `${r.vendor}, ${usd(r.amount)}${r.date ? ' on ' + r.date : ''}: no approval found in the agendas or minutes we have`});
  }
  // Hunt for what isn't there: approvals in the file's dates that the file leaves out.
  const missing = period.start && period.end ? ref.contracts.filter(c => !used.has(c.id) && c.date >= period.start && c.date <= period.end
    && !rows.some(r => sameName(c.vendor, r.vendor) && close(num(c.amount), r.amount))) : [];
  const res = capped(out.filter(c => c.status !== 'match'), 'Contract approved on an agenda').concat(out.filter(c => c.status === 'match'));
  return res.concat(capped(missing.map(c => ({check: 'Approved contract not in the file', status: 'missing',
    detail: `${c.vendor}, ${usd(c.amount)}, approved ${c.date}${c.purpose ? ': ' + String(c.purpose).slice(0, 120) : ''}`, expected: num(c.amount), source_url: c.source_url})), 'Approved contract not in the file'));
}

/* ---------- check register ---------- */
// ref: contracts, votes, emergency, change orders, vendor payments (scraped registers by fiscal year), the year's figures.
function checkCheckbook(rows, ref, period) {
  const out = [];
  const live = rows.filter(r => !r.is_void);
  // 1. Check numbers that skip: a missing number is a payment we haven't been shown.
  const nums = [...new Set(live.map(r => String(r.doc_no || '').trim()).filter(s => /^\d{3,9}$/.test(s)).map(Number))].sort((a, b) => a - b);
  const voided = new Set(rows.filter(r => r.is_void).map(r => Number(r.doc_no)));
  const gaps = [];
  for (let i = 1; i < nums.length; i++) {
    const d = nums[i] - nums[i - 1];
    if (d > 1 && d <= 200) for (let n = nums[i - 1] + 1; n < nums[i]; n++) if (!voided.has(n)) gaps.push(n);
  }
  if (nums.length >= 2) {
    out.push(gaps.length
      ? {check: 'Check numbers run in order', status: 'missing', detail: `${gaps.length} check number${gaps.length === 1 ? '' : 's'} skipped between ${nums[0]} and ${nums[nums.length - 1]}: ${gaps.slice(0, 40).join(', ')}${gaps.length > 40 ? '…' : ''}`, expected: gaps.length, found: 0}
      : {check: 'Check numbers run in order', status: 'match', detail: `${nums.length} checks, ${nums[0]} to ${nums[nums.length - 1]}, none skipped`});
  } else out.push({check: 'Check numbers run in order', status: 'unconfirmed', detail: 'The file has no check numbers to follow'});

  // 2. Big payments need an approval we can find (a contract, a vote, an emergency purchase or a change order).
  const byPayee = new Map();
  for (const r of live) { const k = norm(r.payee); if (!byPayee.has(k)) byPayee.set(k, {payee: r.payee, total: 0, n: 0, big: []}); const p = byPayee.get(k); p.total += Number(r.amount) || 0; p.n++; if (Number(r.amount) >= BIG_PAYMENT) p.big.push(r); }
  const approvals = payee => [...ref.contracts.filter(c => sameName(c.vendor, payee)).map(c => ({amount: num(c.amount), url: c.source_url, date: c.date})),
    ...ref.change_orders.filter(c => sameName(c.vendor, payee)).map(c => ({amount: num(c.change_amount), url: c.source_url, date: c.date})),
    ...ref.emergency.filter(c => sameName(c.vendor, payee)).map(c => ({amount: num(c.amount), url: c.source_url, date: c.date})),
    ...ref.votes.filter(v => sameName(v.headline, payee) || sameName(v.summary, payee)).map(v => ({amount: num(v.amount), url: v.source_url, date: v.date}))];
  const bigs = [];
  for (const p of byPayee.values()) {
    if (!p.big.length) continue;
    const a = approvals(p.payee);
    if (!a.length) { bigs.push({check: 'Large payment has an approval', status: 'unconfirmed', detail: `${p.payee}: ${p.big.length} payment${p.big.length === 1 ? '' : 's'} of ${usd(BIG_PAYMENT)} or more (${usd(sum(p.big, r => r.amount))}) with no contract, vote or emergency purchase on record`}); continue; }
    const approved = a.reduce((x, y) => x + (y.amount || 0), 0);
    if (approved && p.total > approved * (1 + AMOUNT_TOLERANCE)) bigs.push({check: 'Paid within what was approved', status: 'mismatch',
      detail: `${p.payee}: paid ${usd(p.total)} in this file, more than the ${usd(approved)} approved on record`, expected: approved, found: Math.round(p.total * 100) / 100, source_url: a[0].url});
    else bigs.push({check: 'Large payment has an approval', status: 'match', detail: `${p.payee}: ${usd(p.total)} paid, approvals on record ${usd(approved)}`, source_url: a[0].url});
  }
  out.push(...capped(bigs.filter(b => b.status !== 'match'), 'Large payment has an approval'), ...bigs.filter(b => b.status === 'match'));

  // 3. Payees in registers we already collected for the same fiscal year must appear with the same total.
  if (period.fullYear) {
    for (const v of ref.vendor_payments) {
      const p = [...byPayee.values()].find(x => sameName(x.payee, v.vendor));
      if (!p) out.push({check: 'Matches the check register we already have', status: 'missing', detail: `${v.vendor}: ${usd(v.total)} paid in ${v.fiscal_year} by our records, not in this file`, expected: num(v.total), source_url: v.source_url});
      else if (!close(p.total, num(v.total))) out.push({check: 'Matches the check register we already have', status: 'mismatch', detail: `${v.vendor}: ${usd(p.total)} in this file, ${usd(v.total)} in our records`, expected: num(v.total), found: Math.round(p.total * 100) / 100, source_url: v.source_url});
      else out.push({check: 'Matches the check register we already have', status: 'match', detail: `${v.vendor}: ${usd(v.total)}`, source_url: v.source_url});
    }
    // 4. A whole year of payments should come near the year's reported spending.
    const y = ref.year;
    if (y && num(y.actual_spending)) {
      const total = sum(live, r => r.amount), want = num(y.actual_spending);
      out.push(close(total, want, 0.10)
        ? {check: 'Year total near reported spending', status: 'match', detail: `${usd(total)} paid; ${usd(want)} reported for ${y.fiscal_year}`, source_url: y.actuals_source_url}
        : {check: 'Year total near reported spending', status: total < want ? 'missing' : 'mismatch', detail: `${usd(total)} paid in this file; ${usd(want)} reported for ${y.fiscal_year} (${usd(Math.abs(want - total))} ${total < want ? 'not accounted for' : 'more than reported'})`, expected: want, found: Math.round(total), source_url: y.actuals_source_url});
    }
  } else out.push({check: 'Matches the check register we already have', status: 'unconfirmed', detail: 'Only whole fiscal years can be compared with the registers and yearly figures we have'});
  return out;
}

/* ---------- budget vs actual ---------- */
// ref: the adopted budget lines we collected (budget_years), the year's figures (government_years).
function checkBudget(rows, ref) {
  const out = [];
  const original = sum(rows, r => r.original_budget), amended = sum(rows, r => r.amended_budget);
  const adopted = sum(ref.budget_lines, r => r.amount);
  if (ref.budget_lines.length) {
    const t = original || amended;
    out.push(close(t, adopted, TOTAL_TOLERANCE)
      ? {check: 'Budget matches the adopted budget', status: 'match', detail: `${usd(t)} in the file; ${usd(adopted)} adopted`, source_url: ref.budget_lines[0].source_url}
      : {check: 'Budget matches the adopted budget', status: 'mismatch', detail: `${usd(t)} in the file; ${usd(adopted)} in the adopted budget (off by ${usd(Math.abs(t - adopted))})`, expected: adopted, found: t, source_url: ref.budget_lines[0].source_url});
    // Departments in the adopted budget that the report leaves out.
    const depts = new Set(rows.map(r => norm(r.department)).filter(Boolean));
    const gone = [...new Set(ref.budget_lines.filter(l => l.service || l.name).map(l => l.service || l.name))].filter(n => depts.size && ![...depts].some(d => sameName(d, n)));
    out.push(...capped(gone.map(n => ({check: 'Every budgeted department is reported', status: 'missing', detail: `${n} is in the adopted budget but not in this report`, source_url: ref.budget_lines[0].source_url})), 'Every budgeted department is reported'));
  } else out.push({check: 'Budget matches the adopted budget', status: 'unconfirmed', detail: 'We don’t have this year’s adopted budget lines yet'});
  const y = ref.year;
  if (y && num(y.budget_total)) {
    const t = original || amended;
    out.push(close(t, num(y.budget_total), TOTAL_TOLERANCE)
      ? {check: 'Budget matches the reported total', status: 'match', detail: `${usd(t)}; ${usd(y.budget_total)} reported`, source_url: y.budget_source_url}
      : {check: 'Budget matches the reported total', status: 'mismatch', detail: `${usd(t)} in the file; ${usd(y.budget_total)} reported for ${y.fiscal_year}`, expected: num(y.budget_total), found: t, source_url: y.budget_source_url});
  } else out.push({check: 'Budget matches the reported total', status: 'unconfirmed', detail: 'No reported budget total for this year yet'});
  return out;
}

/* ---------- payroll ---------- */
// ref: department leaders' published pay (salary_leaders), positions from adopted budgets (salary_positions, not 'gov'),
// the year's budgeted staff count.
function checkPayroll(rows, ref) {
  const out = [];
  for (const l of ref.leaders) {
    const r = rows.find(x => sameName(x.title, l.title));
    if (!r) { out.push({check: 'Published leader pay is in the file', status: 'missing', detail: `${l.title}: ${usd(l.salary)} published, no such job in this file`, expected: num(l.salary), source_url: l.source_url}); continue; }
    const hit = (r.salaries || []).some(s => close(Number(s), num(l.salary)));
    out.push(hit ? {check: 'Published leader pay is in the file', status: 'match', detail: `${l.title}: ${usd(l.salary)}`, source_url: l.source_url}
      : {check: 'Published leader pay is in the file', status: 'mismatch', detail: `${l.title}: ${usd(l.salary)} published; the file shows ${(r.salaries || []).map(usd).join(', ') || 'no pay'}`, expected: num(l.salary), source_url: l.source_url});
  }
  for (const p of ref.positions) {
    const r = rows.find(x => sameName(x.title, p.title));
    if (!r || !(r.salaries || []).length) continue;
    const lo = num(p.pay_min), hi = num(p.pay_max), out_of = (r.salaries || []).filter(s => (lo && s < lo * 0.99) || (hi && s > hi * 1.01));
    out.push(out_of.length ? {check: 'Pay within the budgeted range', status: 'mismatch', detail: `${r.title}: ${out_of.length} paid outside ${usd(lo)} to ${usd(hi)}`, expected: hi, found: Math.max(...out_of), source_url: p.source_url}
      : {check: 'Pay within the budgeted range', status: 'match', detail: `${r.title}: within ${usd(lo)} to ${usd(hi)}`, source_url: p.source_url});
  }
  const people = sum(rows, r => (r.salaries || []).length);
  const y = ref.year;
  if (y && num(y.employees_fte)) {
    const want = num(y.employees_fte);
    out.push(Math.abs(people - want) <= Math.max(2, want * 0.1)
      ? {check: 'Head count near budgeted staff', status: 'match', detail: `${people} people; ${want} budgeted`, source_url: y.employees_source_url}
      : {check: 'Head count near budgeted staff', status: people < want ? 'missing' : 'mismatch', detail: `${people} people in the file; ${want} budgeted for ${y.fiscal_year}`, expected: want, found: people, source_url: y.employees_source_url});
  }
  if (!out.length) out.push({check: 'Pay checked against published figures', status: 'unconfirmed', detail: 'We have no published pay or budgeted positions to compare yet'});
  return out;
}

/* ---------- board appointments ---------- */
function checkAppointments(rows, ref) {
  return rows.map(r => {
    const last = String(r.person || '').trim().split(/\s+/).pop().toLowerCase();
    const v = last.length > 2 && ref.votes.find(x => /appoint|reappoint/i.test(`${x.headline} ${x.summary}`) && `${x.headline} ${x.summary}`.toLowerCase().includes(last)
      && (!r.term_start || days(x.date, r.term_start) <= 365));
    return v ? {check: 'Appointment voted in the minutes', status: 'match', detail: `${r.person}, ${r.board} (vote on ${v.date})`, source_url: v.source_url}
      : {check: 'Appointment voted in the minutes', status: 'unconfirmed', detail: `${r.person}, ${r.board}: no appointment vote found in the minutes we have`};
  });
}

/* ---------- fee changes ---------- */
function checkFees(rows, ref) {
  return rows.map(r => {
    const v = r.adopted_by && ref.votes.find(x => `${x.headline} ${x.agenda_item || ''}`.toLowerCase().includes(String(r.adopted_by).toLowerCase().replace(/^(ordinance|resolution)\s*/i, '').trim()));
    const f = ref.fees.find(x => sameName(x.name, r.fee));
    if (f && close(num(f.amount), r.new_amount)) return {check: 'Fee matches the published rate', status: 'match', detail: `${r.fee}: ${usd(r.new_amount)}`, source_url: f.source_url};
    if (f && r.old_amount !== null && close(num(f.amount), r.old_amount)) return {check: 'Fee matches the published rate', status: v ? 'match' : 'unconfirmed',
      detail: `${r.fee}: our records still show the old ${usd(f.amount)}${v ? `; the change was voted on ${v.date}` : ''}`, source_url: v ? v.source_url : f.source_url};
    if (f) return {check: 'Fee matches the published rate', status: 'mismatch', detail: `${r.fee}: the file says ${usd(r.new_amount)}, the published rate is ${usd(f.amount)}`, expected: num(f.amount), found: r.new_amount, source_url: f.source_url};
    if (v) return {check: 'Fee change voted in the minutes', status: 'match', detail: `${r.fee}: ${r.adopted_by} (vote on ${v.date})`, source_url: v.source_url};
    return {check: 'Fee checked against published rates', status: 'unconfirmed', detail: `${r.fee}: no published rate or vote found`};
  });
}

/* ---------- loading what we check against ---------- */
async function reference(q, ws, kind, period) {
  const gov = ws.id, safe = p => p.catch(() => []);
  const ref = {contracts: [], votes: [], emergency: [], change_orders: [], vendor_payments: [], budget_lines: [], leaders: [], positions: [], fees: [], year: null};
  const from = period.start ? new Date(new Date(period.start) - DATE_WINDOW_DAYS * 864e5).toISOString().slice(0, 10) : '2016-01-01';
  const to = period.end ? new Date(+new Date(period.end) + DATE_WINDOW_DAYS * 864e5).toISOString().slice(0, 10) : '2100-01-01';
  if (['contracts', 'checkbook'].includes(kind)) {
    ref.contracts = await safe(q(`select id, vendor, amount, purpose, date::text date, source_url from contracts where government_key = $1 and origin <> 'gov' and date between $2 and $3`, [gov, from, to]));
    ref.emergency = await safe(q(`select vendor, amount, date::text date, source_url from emergency_purchases where government_key = $1 and date between $2 and $3`, [gov, from, to]));
    ref.change_orders = await safe(q(`select vendor, change_amount, date::text date, source_url from change_orders where government_key = $1 and date between $2 and $3`, [gov, from, to]));
  }
  if (['contracts', 'checkbook', 'appointments', 'fees'].includes(kind)) {
    ref.votes = await safe(q(`select date::text date, headline, summary, amount, agenda_item, source_url from votes where government_key = $1 and date between $2 and $3`, [gov, from, to]));
  }
  if (period.fiscal_year) {
    const fy = period.fiscal_year;
    [ref.year] = await safe(q(`select * from government_years where government_key = $1 and (fy = $2 or fiscal_year = $3) limit 1`, [gov, fy, 'FY' + fy]));
    if (kind === 'checkbook') ref.vendor_payments = await safe(q(`select vendor, total, $2::text fiscal_year, null::text source_url from vendor_payments where government_key = $1`, [gov, 'FY' + fy])).then(r => (period.fullYear ? r : []));
    if (kind === 'budget') ref.budget_lines = await safe(q(`select name, service, amount, source_url from budget_years where government_key = $1 and fy = $2 and in_total and basis = 'adopted'`, [gov, fy]));
  }
  if (kind === 'payroll') {
    ref.leaders = await safe(q(`select title, salary, source_url from salary_leaders where (employer_id = $1 or government_key = $1) and origin <> 'gov' and salary is not null`, [gov]));
    ref.positions = await safe(q(`select title, pay_min, pay_max, source_url from salary_positions where (employer_id = $1 or government_key = $1) and origin <> 'gov' and (pay_min is not null or pay_max is not null)`, [gov]));
  }
  if (kind === 'fees') {
    ref.fees = [...await safe(q(`select name, residential_single_family_amount amount, source_url from fees_assessments where government_key = $1`, [gov])),
      ...await safe(q(`select charge as name, amount, source_url from utility_rates where government_key = $1 or gov_id = $1`, [gov]))];
  }
  return ref;
}

// A fiscal year starts Oct 1. fullYear when the file covers Oct 1 through Sep 30 of one year.
function periodOf(start, end, fyHint) {
  const p = {start: start || null, end: end || null, fiscal_year: fyHint || null, fullYear: false};
  if (end) {
    const e = new Date(end + 'T12:00:00Z'), fy = e.getUTCMonth() >= 9 ? e.getUTCFullYear() + 1 : e.getUTCFullYear();
    p.fiscal_year = p.fiscal_year || fy;
    p.fullYear = Boolean(start && start <= `${fy - 1}-10-01` && end >= `${fy}-09-30`);
  }
  return p;
}

// Load the file's rows and what we check them against, run the checks for its kind, and return the summary.
async function verifyFile(q, ws, file) {
  const period = periodOf(file.period_start, file.period_end, file.fiscal_year);
  const ref = await reference(q, ws, file.kind, period);
  const run = {contracts: checkContracts, checkbook: checkCheckbook, budget: checkBudget, payroll: checkPayroll, appointments: checkAppointments, fees: checkFees}[file.kind];
  if (!run) return summarize([]);
  return summarize(run(file.rows || [], ref, period));
}

module.exports = {verifyFile, reference, summarize, periodOf, sameName, norm,
  checkContracts, checkCheckbook, checkBudget, checkPayroll, checkAppointments, checkFees, BIG_PAYMENT};
