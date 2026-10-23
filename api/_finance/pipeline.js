// One uploaded file -> a preview or a set of rows ready to insert. Pure: no database or storage access, so the whole
// import path is testable with plain buffers.
const crypto = require('crypto');
const {readGrid} = require('./parse');
const {detect, namedMapping, headerSignature, SHAPES} = require('./detect');
const {normalize, date, fiscalYear} = require('./normalize');

// A budget report's "as of" date is usually in its title lines ("Period ending 03/31/2026", "Through March 2026").
function asOfFromTitle(rows, headerIndex) {
  const found = [];
  for (const row of rows.slice(0, Math.max(0, headerIndex))) for (const v of row) {
    if (v instanceof Date) { found.push(date(v)); continue; }
    const s = String(v ?? '');
    for (const m of s.matchAll(/\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b[A-Z][a-z]{2,8}\.?\s+(?:\d{1,2},?\s+)?\d{4}\b/g)) {
      const d = date(m[0]); if (d) found.push(d);
    }
  }
  return found.filter(Boolean).sort().pop() || null;
}

const sha256 = buf => crypto.createHash('sha256').update(buf).digest('hex');
const safeName = n => String(n || 'upload').split(/[\\/]/).pop().replace(/[^A-Za-z0-9._ -]+/g, '_').replace(/\s+/g, '_').slice(0, 120) || 'upload';

// opts: {shape, mapping, printedTotal, asOf, fiscalYear, account, saved: {shape, mapping: {field: header}}}
async function prepare(buffer, filename, opts = {}) {
  const grid = await readGrid(filename, buffer);
  let det = detect(grid.rows, {shape: opts.shape, mapping: opts.mapping});
  let usedSaved = false;
  // A saved mapping for this exact header row (same system, same report) is applied unless the caller chose one.
  if (opts.saved && !opts.mapping && (!opts.shape || opts.shape === opts.saved.shape)) {
    const d2 = detect(grid.rows, {shape: opts.saved.shape, mapping: opts.saved.mapping});
    if (d2.ok) { det = d2; usedSaved = true; }
  }
  const out = {sheet: grid.sheet || null, shape: det.shape, label: det.shape ? SHAPES[det.shape].label : null, ok: det.ok,
    missing: det.missing || [], headers: det.headers, headerRow: det.headerIndex + 1, mapping: det.shape ? namedMapping(det.headers, det.mapping) : {},
    signature: det.headers.length ? headerSignature(det.headers) : null, usedSavedMapping: usedSaved,
    available: det.shape ? Object.keys(SHAPES[det.shape].fields) : [], records: [], warnings: []};
  if (!det.ok) return out;

  const n = normalize(det.shape, grid.rows, det, {printedTotal: opts.printedTotal, account: opts.account});
  Object.assign(out, {printedTotal: n.printedTotal, parsedTotal: n.parsedTotal, tie: n.tie, skipped: n.skipped, warnings: n.warnings,
    periodStart: n.periodStart, periodEnd: n.periodEnd, records: n.records});

  if (det.shape === 'budget') {
    const asOf = date(opts.asOf) || asOfFromTitle(grid.rows, det.headerIndex);
    if (!asOf) { out.ok = false; out.missing = ['the report’s “as of” date (enter it, e.g. 03/31/2026)']; }
    const fy = Number(opts.fiscalYear) || (asOf ? fiscalYear(asOf, opts.fyStartMonth || 10) : null);
    for (const r of n.records) { r.as_of = asOf; r.fiscal_year = fy; }
    out.periodEnd = asOf; out.fiscalYear = fy;
  }
  if ((det.shape === 'bank_transactions' || det.shape === 'bank_recs') && n.records.some(r => !r.account_hash)) {
    out.ok = false; out.missing = ['the bank account (no account column: enter the account number or name)'];
  }
  return out;
}

module.exports = {prepare, asOfFromTitle, sha256, safeName};
