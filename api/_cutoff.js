// The site's earliest year: nothing from before fiscal year 2016 (or calendar 2016 for dated records) is shown,
// published or loaded. Python ingestion uses data/entities/cutoff.py; api/__tests__/cutoff.test.js keeps the two equal.
const FIRST_YEAR = 2016;

// The year a value points at: 2015 for 2015, 'FY2015', '2015-09-30'. null when there is none.
function yearOf(v) {
  if (v === null || v === undefined || v === '' || typeof v === 'boolean') return null;
  if (typeof v === 'number') return v >= 1900 && v <= 2200 ? Math.trunc(v) : null;
  const ys = String(v).match(/(?<!\d)(19|20)\d\d(?!\d)/g);
  return ys ? Math.max(...ys.map(Number)) : null;
}

// True when the value is FIRST_YEAR or later, or has no year.
const keep = v => { const y = yearOf(v); return y === null || y >= FIRST_YEAR; };

module.exports = {FIRST_YEAR, yearOf, keep};
