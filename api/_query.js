// Pure query helpers shared by the REST API (v1.js) and the MCP server (mcp.js): filtering, sorting and CSV.
// No database or network access here, so they can be tested on their own (see api/__tests__).
const RESERVED = new Set(['q', 'fields', 'sort', 'limit', 'offset', 'format', 'path', 'api_key']);
const CSV_MAX = 10000; // format=csv returns every matching row up to this many
const blank = x => x == null || x === '' || (typeof x === 'string' && !x.trim());
// A number for comparisons, or null when the value is missing or not numeric (so it never matches _min/_max).
const num = x => { if (blank(x) || typeof x === 'boolean') return null; const n = Number(x); return Number.isFinite(n) ? n : null; };
// Every value in a row as lower-case text (keys are left out, so ?q=amount doesn't match every row).
function rowText(v) {
  if (v == null) return '';
  if (Array.isArray(v)) return v.map(rowText).join(' ');
  if (typeof v === 'object') return Object.values(v).map(rowText).join(' ');
  return String(v).toLowerCase();
}
function filterRows(rows, query) {
  const q = String(query.q || '').trim().toLowerCase();
  const conds = Object.entries(query).filter(([k]) => !RESERVED.has(k));
  let out = rows.filter(r => {
    for (const [k0, v0] of conds) {
      const v = String(Array.isArray(v0) ? v0[0] : v0);
      const m = k0.match(/^(.+?)_(min|max|from|to|contains)$/);
      const k = m && !(k0 in r) ? m[1] : k0, op = m && !(k0 in r) ? m[2] : 'eq';
      if (!(k in r)) return false;
      const x = r[k];
      if (op === 'min' || op === 'max') {
        const a = num(x), b = num(v);
        if (a === null || b === null) return false;
        if (op === 'min' ? !(a >= b) : !(a <= b)) return false;
      }
      if (op === 'from' && (blank(x) || !(String(x) >= v))) return false;
      if (op === 'to' && (blank(x) || !(String(x) <= v + '￿'))) return false;
      if (op === 'contains' && !String(x ?? '').toLowerCase().includes(v.toLowerCase())) return false;
      if (op === 'eq') {
        const opts = v.toLowerCase().split(',');
        if (!opts.includes(String(x ?? '').toLowerCase())) return false;
      }
    }
    return !q || rowText(r).includes(q);
  });
  if (query.sort) {
    const keys = String(query.sort).split(',').map(s => s.trim()).filter(Boolean);
    out = [...out].sort((a, b) => {
      for (const s of keys) {
        const d = s.startsWith('-') ? -1 : 1, k = s.replace(/^[-+]/, '');
        const x = a[k], y = b[k];
        if (x == null && y == null) continue; if (x == null) return 1; if (y == null) return -1;
        const c = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y));
        if (c) return c * d;
      }
      return 0;
    });
  }
  return out;
}

// CSV cell. Text that a spreadsheet would run as a formula (starts with = + - @ tab or CR) gets a leading
// single quote. Real numbers are left alone (a negative number isn't a formula, and quoting it would break it).
function csvCell(v) {
  if (v == null) return '';
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : '';
  if (Array.isArray(v)) v = v.join('; '); else if (typeof v === 'object') v = JSON.stringify(v);
  v = String(v);
  if (/^[=+\-@\t\r]/.test(v)) v = "'" + v;
  return /[",\n\r]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}
function toCsv(rows) {
  if (!rows.length) return '';
  const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
  return [keys.map(csvCell).join(','), ...rows.map(r => keys.map(k => csvCell(r[k])).join(','))].join('\n') + '\n';
}

module.exports = {RESERVED, CSV_MAX, filterRows, toCsv, csvCell, rowText, num, blank};
