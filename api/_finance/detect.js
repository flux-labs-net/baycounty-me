// Recognizes what kind of export a file is and which column holds which field.
// Each shape lists the column names finance systems commonly use for a field (Tyler Incode/Munis, Caselle,
// Springbrook, Edmunds, QuickBooks, bank CSV downloads). Matching is on normalized header text.
const crypto = require('crypto');

const SHAPES = {
  budget: {
    label: 'Budget vs. actual',
    fields: {
      fund: ['fund', 'fund name', 'fund description', 'fund no', 'fund number'],
      department: ['department', 'dept', 'department name', 'division', 'function', 'activity', 'cost center', 'org', 'organization'],
      account: ['account', 'account number', 'account no', 'acct', 'acct no', 'gl account', 'gl number', 'account code', 'object', 'object code', 'line item'],
      description: ['description', 'account description', 'account name', 'acct description', 'desc', 'line item description', 'title'],
      type: ['type', 'account type', 'category', 'rev exp', 'revenue expense'],
      original_budget: ['original budget', 'adopted budget', 'original', 'adopted', 'original appropriation'],
      amended_budget: ['amended budget', 'revised budget', 'current budget', 'final budget', 'amended', 'revised', 'budget', 'appropriation', 'current appropriation'],
      actual_ytd: ['ytd actual', 'actual ytd', 'year to date actual', 'ytd expended', 'ytd expenditures', 'actual', 'actuals', 'expended', 'ytd activity', 'ytd'],
      encumbered: ['encumbered', 'encumbrance', 'encumbrances', 'open po', 'open encumbrances', 'ytd encumbrances', 'committed'],
    },
    required: [['account', 'description'], ['amended_budget', 'original_budget'], ['actual_ytd']],
    amountField: 'actual_ytd',
  },
  disbursements: {
    label: 'Check register / payments',
    fields: {
      paid_on: ['check date', 'payment date', 'paid date', 'issue date', 'date', 'trans date', 'transaction date', 'posting date'],
      doc_no: ['check no', 'check number', 'check', 'check num', 'payment number', 'payment no', 'reference', 'ref', 'eft number', 'document number', 'doc no', 'num'],
      payee: ['vendor', 'vendor name', 'payee', 'payee name', 'name', 'paid to', 'remit to'],
      amount: ['check amount', 'payment amount', 'amount', 'net amount', 'amount paid', 'paid amount', 'total'],
      invoice_no: ['invoice', 'invoice number', 'invoice no', 'inv no', 'invoice num'],
      fund: ['fund', 'fund name'],
      account: ['account', 'gl account', 'account number', 'expense account', 'distribution account'],
      description: ['description', 'memo', 'invoice description', 'purpose', 'comment'],
      status: ['status', 'void', 'void status', 'check status', 'cleared'],
      method: ['payment type', 'type', 'method', 'payment method', 'check type'],
    },
    required: [['payee'], ['amount'], ['paid_on']],
    amountField: 'amount',
  },
  bank_transactions: {
    label: 'Bank statement transactions',
    fields: {
      posted_on: ['posting date', 'posted date', 'post date', 'date', 'transaction date', 'effective date', 'as of date'],
      amount: ['amount', 'transaction amount', 'net amount'],
      debit: ['debit', 'debits', 'withdrawal', 'withdrawals', 'debit amount', 'payments'],
      credit: ['credit', 'credits', 'deposit', 'deposits', 'credit amount'],
      check_no: ['check number', 'check no', 'check', 'serial number', 'serial', 'check num'],
      description: ['description', 'memo', 'details', 'transaction description', 'payee', 'narrative'],
      account: ['account', 'account number', 'account no', 'acct', 'account name'],
      balance: ['balance', 'running balance', 'ledger balance'],
    },
    required: [['posted_on'], ['amount', 'debit', 'credit'], ['description', 'check_no']],
    amountField: 'amount',
  },
  bank_recs: {
    label: 'Bank reconciliation summary',
    fields: {
      account: ['account', 'bank account', 'account number', 'account name', 'cash account'],
      period_end: ['period end', 'statement date', 'month end', 'period ending', 'as of', 'statement ending', 'month'],
      statement_balance: ['statement balance', 'bank balance', 'ending bank balance', 'balance per bank', 'bank statement balance'],
      book_balance: ['book balance', 'gl balance', 'ledger balance', 'balance per books', 'general ledger balance', 'books'],
      outstanding_checks: ['outstanding checks', 'outstanding', 'o s checks', 'checks outstanding', 'less outstanding checks'],
      deposits_in_transit: ['deposits in transit', 'dit', 'deposit in transit', 'plus deposits in transit'],
      other_adjustments: ['other adjustments', 'adjustments', 'reconciling items', 'other'],
      reconciled_on: ['date reconciled', 'reconciled on', 'reconciled', 'completed', 'date completed', 'prepared date'],
      prepared_by: ['prepared by', 'reconciled by', 'preparer'],
      approved_by: ['approved by', 'reviewed by', 'reviewer', 'approver'],
    },
    required: [['statement_balance'], ['book_balance'], ['period_end']],
    amountField: 'book_balance',
  },
};

const normHeader = h => String(h ?? '').toLowerCase().replace(/#/g, ' no ').replace(/[^a-z0-9]+/g, ' ').trim();

// Best column for each field: an exact synonym match beats a "contains" match; earlier synonyms beat later ones.
// A column is used for at most one field.
function mapColumns(headers, shape) {
  const spec = SHAPES[shape].fields, H = headers.map(normHeader), used = new Set(), mapping = {};
  const cands = [];
  for (const [field, syns] of Object.entries(spec)) {
    syns.forEach((s, rank) => H.forEach((h, i) => {
      if (!h) return;
      if (h === s) cands.push({field, i, score: 1000 - rank});
      else if (s.length >= 4 && (h.startsWith(s + ' ') || h.endsWith(' ' + s) || h.includes(' ' + s + ' '))) cands.push({field, i, score: 500 - rank - (h.length - s.length)});
    }));
  }
  cands.sort((a, b) => b.score - a.score);
  for (const c of cands) {
    if (mapping[c.field] !== undefined || used.has(c.i)) continue;
    mapping[c.field] = c.i; used.add(c.i);
  }
  return mapping; // field -> column index
}

const satisfies = (mapping, shape) => SHAPES[shape].required.every(alts => alts.some(f => mapping[f] !== undefined));

// Header row = within the first 40 rows, the row that maps the most fields for any shape (reports often start with
// a title, the city name and a date range above the real header).
function findHeader(rows) {
  let best = null;
  rows.slice(0, 40).forEach((row, idx) => {
    const texts = row.filter(v => typeof v === 'string' && /[a-z]/i.test(v));
    if (texts.length < 2) return;
    const headers = row.map(v => (typeof v === 'string' ? v : v instanceof Date ? '' : String(v ?? '')));
    for (const shape of Object.keys(SHAPES)) {
      const m = mapColumns(headers, shape), n = Object.keys(m).length, ok = satisfies(m, shape);
      const score = (ok ? 100 : 0) + n;
      if (!best || score > best.score) best = {score, idx, shape, ok, mapping: m, headers};
    }
  });
  return best;
}

// Returns {shape, ok, headerIndex, headers, mapping, alternatives}. A caller-chosen shape or mapping wins.
function detect(rows, {shape, mapping} = {}) {
  const h = findHeader(rows);
  if (!h) return {ok: false, shape: shape || null, headerIndex: -1, headers: [], mapping: {}, missing: ['a header row']};
  let useShape = shape && SHAPES[shape] ? shape : h.shape;
  let m = shape && SHAPES[shape] ? mapColumns(h.headers, shape) : h.mapping;
  if (mapping && typeof mapping === 'object') {
    for (const [field, col] of Object.entries(mapping)) {
      if (!(field in SHAPES[useShape].fields)) continue;
      if (col === null || col === '') { delete m[field]; continue; }
      const idx = typeof col === 'number' ? col : h.headers.findIndex(x => normHeader(x) === normHeader(col));
      if (idx >= 0) m[field] = idx;
    }
  }
  const missing = SHAPES[useShape].required.filter(alts => !alts.some(f => m[f] !== undefined)).map(alts => alts.join(' or '));
  return {ok: missing.length === 0, shape: useShape, label: SHAPES[useShape].label, headerIndex: h.idx, headers: h.headers, mapping: m, missing};
}

// Mapping as {field: "Column name"} for display and saving.
const namedMapping = (headers, mapping) => Object.fromEntries(Object.entries(mapping).map(([f, i]) => [f, headers[i]]));
const headerSignature = headers => crypto.createHash('sha256').update(headers.map(normHeader).filter(Boolean).join('|')).digest('hex').slice(0, 32);

module.exports = {SHAPES, detect, mapColumns, normHeader, namedMapping, headerSignature};
