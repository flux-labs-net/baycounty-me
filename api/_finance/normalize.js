// Turns mapped rows into clean records for one shape, separates printed total rows, and ties the parsed rows
// out to the file's own total. Pure functions.
const crypto = require('crypto');
const {SHAPES} = require('./detect');

// "$1,234.56", "(1,234.56)", "1,234.56-", "-", "" -> number or null.
function money(v) {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return Number.isFinite(v) ? Math.round(v * 100) / 100 : null;
  if (v instanceof Date) return null;
  let s = String(v).trim();
  if (!s || /^[-–—]+$/.test(s)) return null;
  let neg = false;
  if (/^\(.*\)$/.test(s)) { neg = true; s = s.slice(1, -1); }
  if (/-$/.test(s)) { neg = true; s = s.slice(0, -1); }
  if (/^-/.test(s.replace(/^\$/, ''))) { neg = true; }
  if (/\bcr\b/i.test(s)) neg = true;
  s = s.replace(/[$,\s]|cr|dr/gi, '').replace(/^-/, '');
  if (!/^\d*\.?\d+$/.test(s)) return null;
  const n = Math.round(parseFloat(s) * 100) / 100;
  return neg ? -n : n;
}

const pad = n => String(n).padStart(2, '0');
const iso = (y, m, d) => {
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d ? `${y}-${pad(m)}-${pad(d)}` : null;
};

// Date objects (exceljs reads Excel dates as UTC midnight), ISO, M/D/YYYY, M/D/YY, YYYYMMDD, Excel serial numbers,
// "Sep 30, 2026" and "September 2026" (month end) -> 'YYYY-MM-DD' or null.
const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
function date(v) {
  if (v === null || v === undefined || v === '') return null;
  if (v instanceof Date) return isNaN(v) ? null : v.toISOString().slice(0, 10);
  if (typeof v === 'number') {
    if (v > 20000 && v < 80000) return new Date(Date.UTC(1899, 11, 30) + v * 864e5).toISOString().slice(0, 10);
    if (v > 19000101 && v < 21001231) return date(String(v));
    return null;
  }
  const s = String(v).trim();
  let m;
  if ((m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/))) return iso(+m[1], +m[2], +m[3]);
  if ((m = s.match(/^(\d{4})(\d{2})(\d{2})$/))) return iso(+m[1], +m[2], +m[3]);
  if ((m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b/))) {
    let y = +m[3]; if (y < 100) y += y < 70 ? 2000 : 1900;
    return iso(y, +m[1], +m[2]);
  }
  if ((m = s.match(/^([a-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})$/i)) && MONTHS.includes(m[1].toLowerCase())) return iso(+m[3], MONTHS.indexOf(m[1].toLowerCase()) + 1, +m[2]);
  if ((m = s.match(/^([a-z]{3})[a-z]*\.?\s+(\d{4})$/i)) && MONTHS.includes(m[1].toLowerCase())) {
    const y = +m[2], mo = MONTHS.indexOf(m[1].toLowerCase()) + 1;
    return new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
  }
  return null;
}

const text = (v, n = 300) => {
  if (v === null || v === undefined) return null;
  const s = (v instanceof Date ? v.toISOString().slice(0, 10) : String(v)).replace(/\s+/g, ' ').trim();
  return s ? s.slice(0, n) : null;
};
// Numbers that are identifiers (check numbers) come back from Excel as 1234 or 1234.0.
const ident = v => (typeof v === 'number' ? String(Math.trunc(v)) : text(v, 60));

// Vendor names as one key: upper case, no punctuation, no corporate suffixes.
const SUFFIX = /\b(INCORPORATED|INC|LLC|L L C|LLP|LTD|CO|CORP|CORPORATION|COMPANY|PA|PLLC|PC|THE|OF FLORIDA|OF FL)\b/g;
const payeeKey = s => (s ? String(s).toUpperCase().replace(/&/g, ' AND ').replace(/[^A-Z0-9 ]+/g, ' ').replace(SUFFIX, ' ').replace(/\s+/g, ' ').trim() || null : null);

// Bank account numbers are never stored. Label = last 4 digits; hash = HMAC so the same account matches across files.
const hashSecret = () => process.env.FINANCE_HASH_SECRET || process.env.ALERTS_SECRET || 'baycounty.me-finance';
function maskAccount(v) {
  const s = text(v, 80);
  if (!s) return {label: null, hash: null};
  const digits = s.replace(/\D/g, '');
  const base = digits.length >= 4 ? digits : s.toLowerCase();
  const label = digits.length >= 6 ? `…${digits.slice(-4)}` : s.replace(/\d(?=\d{4})/g, '•');
  return {label, hash: crypto.createHmac('sha256', hashSecret()).update(base).digest('hex').slice(0, 24)};
}

// Total rows: the word "total" in a text cell. "Grand total" or the last total row is the printed file total.
// A total row also lacks the row's identity (no payment date, no account number), so a vendor called
// "Total Pest Control" is still a payment. "Grand/report total" lines are preferred over subtotals.
const TOTAL_RE = /^\s*(grand\s+|report\s+|fund\s+|department\s+|dept\.?\s+)?totals?\b|\btotals?\s*(for|:)|\b(grand|report)\s+total\b/i;
const GRAND_RE = /\b(grand|report)\s+total|total\s+(all|report)|^\s*totals?\s*:?\s*$/i;
const isTotalRow = row => row.some(v => typeof v === 'string' && TOTAL_RE.test(v) && v.length < 80);
function totalKind(shape, row, mapping) {
  if (!isTotalRow(row)) return null;
  const g = f => (mapping[f] === undefined ? undefined : row[mapping[f]]);
  if (shape === 'disbursements' && date(g('paid_on')) && payeeHasNoTotalWord(row, mapping)) return null;
  if (shape === 'bank_transactions' && date(g('posted_on'))) return null;
  if (shape === 'bank_recs' && date(g('period_end'))) return null;
  if (shape === 'budget' && text(g('account')) && /\d/.test(String(g('account'))) && !TOTAL_RE.test(String(g('account')))) return null;
  return row.some(v => typeof v === 'string' && GRAND_RE.test(v)) ? 'grand' : 'sub';
}
// A dated row is a total only when the total wording is outside the payee column.
function payeeHasNoTotalWord(row, mapping) {
  return row.every((v, i) => i === mapping.payee || !(typeof v === 'string' && TOTAL_RE.test(v)));
}

function pick(row, mapping, field) { const i = mapping[field]; return i === undefined ? undefined : row[i]; }

function toRecord(shape, row, mapping, ctx) {
  const g = f => pick(row, mapping, f);
  if (shape === 'budget') {
    return {fund: text(g('fund')), department: text(g('department')), account: text(g('account'), 80), description: text(g('description')),
      type: text(g('type'), 40), original_budget: money(g('original_budget')), amended_budget: money(g('amended_budget')),
      actual_ytd: money(g('actual_ytd')), encumbered: money(g('encumbered'))};
  }
  if (shape === 'disbursements') {
    const status = String(g('status') ?? '').toLowerCase(), amount = money(g('amount'));
    const methodRaw = String(g('method') ?? '').toLowerCase(), doc = ident(g('doc_no'));
    const method = /ach|eft|direct/.test(methodRaw) ? 'ach' : /wire/.test(methodRaw) ? 'wire' : /card|p-?card/.test(methodRaw) ? 'card'
      : /check|chk/.test(methodRaw) || (doc && /^\d+$/.test(doc)) ? 'check' : methodRaw ? 'other' : null;
    const payee = text(g('payee'));
    return {paid_on: date(g('paid_on')), doc_no: doc, method, payee, payee_key: payeeKey(payee), amount, invoice_no: ident(g('invoice_no')),
      fund: text(g('fund')), account: text(g('account'), 80), description: text(g('description')),
      is_void: /void|cancel|stop/.test(status) || /\bvoid\b/i.test(payee || '')};
  }
  if (shape === 'bank_transactions') {
    let amount = money(g('amount'));
    if (amount === null) {
      const d = money(g('debit')), c = money(g('credit'));
      if (d !== null || c !== null) amount = Math.round(((c || 0) - Math.abs(d || 0)) * 100) / 100;
    }
    const acct = maskAccount(g('account') ?? ctx.account);
    let check = ident(g('check_no'));
    if (!check) { const m = String(g('description') ?? '').match(/\bCHE?C?K\s*#?\s*(\d{3,})\b/i); if (m) check = m[1]; }
    return {account_label: acct.label, account_hash: acct.hash, posted_on: date(g('posted_on')), amount, check_no: check, description: text(g('description'))};
  }
  if (shape === 'bank_recs') {
    const acct = maskAccount(g('account') ?? ctx.account);
    return {account_label: acct.label, account_hash: acct.hash, period_end: date(g('period_end')),
      statement_balance: money(g('statement_balance')), book_balance: money(g('book_balance')),
      outstanding_checks: money(g('outstanding_checks')), deposits_in_transit: money(g('deposits_in_transit')),
      other_adjustments: money(g('other_adjustments')), reconciled_on: date(g('reconciled_on')),
      prepared_by: text(g('prepared_by'), 80), approved_by: text(g('approved_by'), 80)};
  }
  throw new Error('Unknown shape ' + shape);
}

// A row is data when its key fields parse. Blank lines, page headers and subtotal lines are skipped.
function usable(shape, r) {
  if (shape === 'budget') return (r.account || r.description) && (r.amended_budget !== null || r.original_budget !== null || r.actual_ytd !== null);
  if (shape === 'disbursements') return r.amount !== null && (r.payee || r.doc_no) && r.paid_on;
  if (shape === 'bank_transactions') return r.amount !== null && r.posted_on;
  if (shape === 'bank_recs') return r.period_end && (r.statement_balance !== null || r.book_balance !== null);
  return false;
}

const round2 = n => Math.round(n * 100) / 100;

// Builds records from the grid. Returns {records, printedTotal, parsedTotal, tie, skipped, warnings, periodStart, periodEnd}.
// printedTotal: the caller's control total when given, else the file's total row (last one wins).
function normalize(shape, rows, det, opts = {}) {
  const field = SHAPES[shape].amountField, records = [], warnings = [];
  let printed = null, skipped = 0, grandSeen = false;
  const subtotals = [];
  for (let i = det.headerIndex + 1; i < rows.length; i++) {
    const row = rows[i];
    const kind = totalKind(shape, row, det.mapping);
    if (kind) {
      const r = toRecord(shape, row, det.mapping, opts);
      let v = r[field];
      if (v === null) { // total sits in another column: take the last number on the row
        const nums = row.filter(x => !(x instanceof Date)).map(money).filter(n => n !== null);
        if (nums.length) v = nums[nums.length - 1];
      }
      if (v !== null && (kind === 'grand' || !grandSeen)) { printed = v; if (kind === 'grand') grandSeen = true; else subtotals.push(v); }
      continue;
    }
    const r = toRecord(shape, row, det.mapping, opts);
    if (!usable(shape, r)) { if (row.filter(v => v !== '' && v !== null).length > 1) skipped++; continue; }
    // Budget reports repeat subtotal lines by department; drop lines whose description says total.
    if (shape === 'budget' && /\btotal\b/i.test(`${r.description || ''} ${r.account || ''}`)) { skipped++; continue; }
    r.source_row = i + 1;
    records.push(r);
  }
  let fromSubtotals = !grandSeen && subtotals.length > 0;
  if (!grandSeen && subtotals.length > 1) printed = round2(subtotals.reduce((a, b) => a + b, 0));
  if (opts.printedTotal !== undefined && opts.printedTotal !== null && opts.printedTotal !== '') { printed = money(opts.printedTotal); fromSubtotals = false; }
  const parsed = round2(records.reduce((s, r) => s + (r[field] || 0), 0));
  let tie;
  if (printed === null) tie = {status: 'no_total', difference: null};
  else {
    const diff = round2(parsed - printed);
    // Voids are sometimes printed as positives and netted in the total; accept either convention.
    const altParsed = shape === 'disbursements' ? round2(records.reduce((s, r) => s + (r.is_void ? -Math.abs(r.amount) : r.amount), 0)) : parsed;
    const ok = Math.abs(diff) < 0.005 || Math.abs(round2(altParsed - printed)) < 0.005;
    tie = {status: ok ? 'ties' : 'mismatch', difference: ok ? 0 : diff};
    // Only subtotal lines and no grand total: nesting (department inside fund) makes their sum unreliable,
    // so a miss is reported as "no total" rather than holding the file.
    if (!ok && fromSubtotals) {
      tie = {status: 'no_total', difference: null};
      warnings.push('The file has subtotal lines but no grand total. Enter the report total to tie it out.');
    }
  }
  if (!records.length) warnings.push('No data rows were found under the header row.');
  if (skipped) warnings.push(`${skipped} row${skipped === 1 ? '' : 's'} skipped (blank amounts, missing dates or subtotal lines).`);
  const dates = records.map(r => r.paid_on || r.posted_on || r.period_end).filter(Boolean).sort();
  if (shape === 'disbursements' && records.some(r => !r.paid_on)) warnings.push('Some payments have no date.');
  return {records, printedTotal: printed, parsedTotal: parsed, tie, skipped, warnings,
    periodStart: dates[0] || null, periodEnd: dates[dates.length - 1] || null};
}

// Fiscal year for a date when the year starts in fyStartMonth (10 = October): Oct 1, 2025 -> FY2026.
const fiscalYear = (d, fyStartMonth = 10) => { const y = +d.slice(0, 4), m = +d.slice(5, 7); return fyStartMonth > 1 && m >= fyStartMonth ? y + 1 : y; };

module.exports = {money, date, text, payeeKey, maskAccount, isTotalRow, totalKind, normalize, toRecord, fiscalYear, round2};
