/* BayCounty.me shared page helpers, exposed as window.BCM. Bundled into /assets/site.js.

   URL state     data-param="x" on a <select>, text <input>, checkbox, or a chip group
                 (an element holding buttons with data-value and aria-pressed) is read from ?x= on
                 load and written back with history.replaceState when it changes (text is debounced).
                 Select values match by value, label, or loosely ("City of Lynn Haven" = "Lynn Haven";
                 extra names can go in data-alias="pc panama-city"). Options added later by a page
                 script are picked up (retried for ~9 s). A checkbox writes 1/0 only when it differs
                 from its starting state.
                 Pages with their own JS state use BCM.urlState.get(k) / .set({k: v}) / .setLater().
   Sorting       BCM.sortable(table, {onSort(key, dir, col, type)}) turns header cells into real buttons
                 with aria-sort (key = th[data-k] or the column index; onSort may return 1 or -1 to pick
                 the direction itself; a th that starts with aria-sort counts as the current sort).
                 With no onSort the rows are sorted in place (numbers with $ , % K M B,
                 dates, or text are detected per column; rows under a tr.grp group header stay in their
                 group). Call it again after re-rendering a table to re-apply the sort. Tables with
                 data-sortable are set up on load; th[data-nosort] stays plain.
   CSV           table[data-csv="file-name"] gets a "Download this view (CSV)" button that exports the
                 rows currently shown. BCM.toCSV(rows) / BCM.csvCell(v) quote values and neutralize
                 spreadsheet formulas (a leading = + - @ gets a ' prefix).
   Announce      BCM.announce(text) speaks a short status to screen readers.

   site.js is a deferred script in <head>, so deferred page scripts (in the body) can use BCM at
   start-up. Inline page scripts run earlier, while the page parses: wrap them in DOMContentLoaded. */
(() => {
const B = window.BCM = window.BCM || {};
const T = (k, d) => (window.BCM_I18N && window.BCM_I18N[k]) || d; // label override (Spanish pages set window.BCM_I18N)

/* ---------- URL state ---------- */
let pend = {}, pendT = null;
const urlState = B.urlState = {
  get: k => new URLSearchParams(location.search).get(k),
  all: () => Object.fromEntries(new URLSearchParams(location.search)),
  set(obj) {
    const u = new URL(location.href);
    Object.entries(obj).forEach(([k, v]) => {
      delete pend[k];
      if (Array.isArray(v)) v = v.join(',');
      if (v == null || v === '' || v === false) u.searchParams.delete(k); else u.searchParams.set(k, String(v));
    });
    const next = u.pathname + u.search + u.hash;
    if (next !== location.pathname + location.search + location.hash) history.replaceState(history.state, '', next);
  },
  setLater(obj, ms = 350) { Object.assign(pend, obj); clearTimeout(pendT); pendT = setTimeout(urlState.flush, ms); },
  flush() { clearTimeout(pendT); const p = pend; pend = {}; if (Object.keys(p).length) urlState.set(p); },
};

const loose = s => String(s || '').toLowerCase().replace(/^city of /, '').replace(/ bocc$/, '').replace(/[^a-z0-9]+/g, ' ').trim();
B.findOption = (sel, v) => {
  const os = [...sel.options], n = loose(v);
  return os.find(o => o.value === v) || os.find(o => o.textContent.trim() === v) ||
    (n ? os.find(o => (o.value && loose(o.value) === n) || loose(o.textContent) === n || (o.dataset.alias || '').split(/\s+/).includes(v)) : null);
};
const kindOf = el => el.tagName === 'SELECT' ? 'select' : el.type === 'checkbox' ? 'check' : /^(INPUT|TEXTAREA)$/.test(el.tagName) ? 'text' : 'chips';
const fire = el => { el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); };
const scrollToHash = () => { const t = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1))); if (t) t.scrollIntoView(); };

function bindParam(el) {
  if (el._bcmParam) return; el._bcmParam = true;
  const k = el.dataset.param, t = kindOf(el);
  const val = () => t === 'check' ? (el.checked ? '1' : '0') : t === 'chips'
    ? [...el.querySelectorAll('[data-value][aria-pressed="true"]')].map(b => b.dataset.value).filter(Boolean).join(',') : el.value;
  const def = t === 'check' ? val() : (el.dataset.default || '');
  const write = later => { const v = val(), o = {[k]: v === def ? '' : v}; if (later) urlState.setLater(o); else urlState.set(o); };
  if (t === 'chips') el.addEventListener('click', e => { if (e.target.closest('[data-value]')) setTimeout(() => write(false)); });
  else { el.addEventListener('input', () => write(t === 'text')); el.addEventListener('change', () => write(false)); }
  const want = urlState.get(k);
  if (want == null || want === '') return;
  const apply = () => {
    if (t === 'select') { const o = B.findOption(el, want); if (!o) return false; if (el.value !== o.value) { el.value = o.value; fire(el); } return true; }
    if (t === 'check') { const c = want === '1' || want === 'true'; if (el.checked !== c) { el.checked = c; fire(el); } return true; }
    if (t === 'text') { if (el.value !== want) { el.value = want; fire(el); } return true; }
    const bs = want.split(',').map(v => [...el.querySelectorAll('[data-value]')].find(b => b.dataset.value === v));
    if (!bs.length || bs.some(b => !b)) return false;
    bs.forEach(b => { if (b.getAttribute('aria-pressed') !== 'true') b.click(); });
    return bs.every(b => b.isConnected ? b.getAttribute('aria-pressed') === 'true' : true); // page may re-render chips on click
  };
  if (apply()) return;
  let n = 0; const iv = setInterval(() => { if (apply()) { clearInterval(iv); scrollToHash(); } else if (++n > 60) clearInterval(iv); }, 150);
}
B.bindParams = (root = document) => root.querySelectorAll('[data-param]').forEach(bindParam);

/* ---------- announce ---------- */
let live = null, liveT = null;
B.announce = msg => {
  if (!live) { live = document.createElement('div'); live.className = 'sr'; live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite'); document.body.appendChild(live); }
  clearTimeout(liveT); live.textContent = ''; liveT = setTimeout(() => { live.textContent = msg; }, 60);
};

/* ---------- sorting ---------- */
const SKIPTXT = 'small,details,.badge,.sub,.src,button:not(.th-sort),svg,.vchip,script,style';
function mainText(c) { // the cell's own value, without sub-lines, badges and source links
  if (!c) return '';
  if (c.dataset && c.dataset.sort != null) return c.dataset.sort;
  let s = '';
  const walk = n => n.childNodes.forEach(x => { if (x.nodeType === 3) s += x.nodeValue; else if (x.nodeType === 1 && !x.matches(SKIPTXT)) { walk(x); if (x.tagName === 'BR') s += ' '; } });
  walk(c);
  return s.replace(/\s+/g, ' ').trim() || (c.querySelector('.badge') ? c.textContent.replace(/\s+/g, ' ').trim() : ''); // a cell that is only a badge sorts by it
}
B.cellText = mainText;
B.parseNum = s => {
  const t = String(s).replace(/[\s,]/g, '').replace(/−/g, '-');
  const m = /^(\()?(-)?~?\$?(-)?(\d*\.?\d+)([KMB])?%?(\))?$/i.exec(t);
  if (!m) return null;
  let v = parseFloat(m[4]) * ({K: 1e3, M: 1e6, B: 1e9}[(m[5] || '').toUpperCase()] || 1);
  if (m[2] || m[3] || (m[1] && m[6])) v = -v;
  return v;
};
const MON = {jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11};
B.parseDate = s => {
  let m;
  if ((m = /^(\d{4})-(\d{2})(?:-(\d{2}))?\b/.exec(s)) && +m[2] >= 1 && +m[2] <= 12) return Date.UTC(+m[1], +m[2] - 1, +(m[3] || 1));
  if ((m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})\b/.exec(s))) return Date.UTC(+m[3], +m[1] - 1, +m[2]);
  if ((m = /^([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})\b/.exec(s)) && MON[m[1].toLowerCase()] != null) return Date.UTC(+m[3], MON[m[1].toLowerCase()], +m[2]);
  if ((m = /^([A-Za-z]{3})[a-z]* (\d{4})$/.exec(s)) && MON[m[1].toLowerCase()] != null) return Date.UTC(+m[2], MON[m[1].toLowerCase()], 1);
  if ((m = /^FY ?(\d{4})\b/i.exec(s))) return Date.UTC(+m[1], 0, 1);
  return null;
};
const isBlank = v => !v || /^[—–\-?]$/.test(v) || /^n\/?a$/i.test(v);
B.detectType = vals => {
  const xs = vals.filter(v => !isBlank(v));
  if (!xs.length) return 'text';
  if (xs.every(v => B.parseNum(v) != null)) return 'num';
  if (xs.every(v => B.parseDate(v) != null)) return 'date';
  return 'text';
};
const keyFn = type => type === 'num' ? B.parseNum : type === 'date' ? B.parseDate : v => v.toLowerCase();
const coll = new Intl.Collator('en', {numeric: true, sensitivity: 'base'});
B.compare = (type, dir) => (a, b) => { // a, b: [value, originalIndex]; blanks always last
  const ba = isBlank(a[0]), bb = isBlank(b[0]);
  if (ba || bb) return ba === bb ? a[1] - b[1] : ba ? 1 : -1;
  const f = keyFn(type), x = f(a[0]), y = f(b[0]);
  const c = type === 'text' ? coll.compare(x, y) : x - y;
  return c * dir || a[1] - b[1];
};
function cellAt(row, col) { let i = 0; for (const c of row.cells) { const s = +c.colSpan || 1; if (col < i + s) return c; i += s; } return null; }
function bodyRows(table) { return [...table.tBodies].flatMap(tb => [...tb.rows]); }
function sortRows(table, col, dir, type) {
  const tb = table.tBodies[0]; if (!tb) return;
  const rows = [...tb.rows];
  rows.forEach((r, i) => { if (r._bcmI == null) r._bcmI = i; });
  const segs = [{head: null, rows: []}];
  rows.forEach(r => { if (r.classList.contains('grp')) segs.push({head: r, rows: []}); else segs[segs.length - 1].rows.push(r); });
  type = type || B.detectType(rows.filter(r => !r.classList.contains('grp')).map(r => mainText(cellAt(r, col))));
  const cmp = B.compare(type, dir), frag = document.createDocumentFragment();
  segs.forEach(s => {
    if (s.head) frag.appendChild(s.head);
    s.rows.map(r => [mainText(cellAt(r, col)), r._bcmI, r]).sort(cmp).forEach(x => frag.appendChild(x[2]));
  });
  tb.appendChild(frag);
}
B.sortable = (table, opts) => {
  if (!table || !table.tHead || !table.tHead.rows.length) return table;
  const hr = table.tHead.rows[table.tHead.rows.length - 1];
  if (!table._bcmSort) {
    const st = table._bcmSort = {col: null, dir: 0, opts: opts || {}};
    let ci = 0;
    [...hr.cells].forEach(th => {
      const span = +th.colSpan || 1, idx = ci; ci += span;
      if (th.hasAttribute('data-nosort') || span > 1 || !th.textContent.trim() || th.querySelector('button')) return;
      if (th.hasAttribute('aria-sort')) { st.col = idx; st.dir = th.getAttribute('aria-sort') === 'ascending' ? 1 : -1; } // already sorted this way
      const b = document.createElement('button'); b.type = 'button'; b.className = 'th-sort';
      while (th.firstChild) b.appendChild(th.firstChild);
      th.appendChild(b);
      b.addEventListener('click', () => {
        const type = th.dataset.type || (th.classList.contains('num') && st.opts.onSort ? 'num' : B.detectType(bodyRows(table).filter(r => !r.classList.contains('grp')).map(r => mainText(cellAt(r, idx)))));
        let dir = st.col === idx ? -st.dir : (type === 'text' ? 1 : -1);
        if (st.opts.onSort) { const r = st.opts.onSort(th.dataset.k != null ? th.dataset.k : idx, dir, idx, type); if (r === 1 || r === -1) dir = r; }
        st.col = idx; st.dir = dir; st.type = type;
        [...hr.cells].forEach(c => { if (c === th) c.setAttribute('aria-sort', dir < 0 ? 'descending' : 'ascending'); else c.removeAttribute('aria-sort'); });
        if (!st.opts.onSort) sortRows(table, idx, dir, type);
        B.announce(T('sortedBy', 'Sorted by ') + b.textContent.trim() + ', ' + (dir < 0 ? (type === 'text' ? T('za', 'Z to A') : T('desc', 'largest first')) : (type === 'text' ? T('az', 'A to Z') : T('asc', 'smallest first'))));
      });
    });
  } else if (opts) table._bcmSort.opts = opts;
  const st = table._bcmSort;
  if (st.col != null && !st.opts.onSort) sortRows(table, st.col, st.dir, st.type);
  return table;
};

/* ---------- CSV ---------- */
B.csvCell = v => {
  let s = v == null ? '' : String(v);
  if (/^[=+\-@\t\r]/.test(s) && !/^-?\d+(\.\d+)?$/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};
B.toCSV = rows => rows.map(r => r.map(B.csvCell).join(',')).join('\r\n');
const squash = s => String(s || '').replace(/\s+/g, ' ').trim();
function exportText(c) {
  const main = mainText(c), only = !c.childNodes.length || c.textContent.replace(/\s+/g, ' ').trim() === main;
  if (only) return main;
  const extra = [...c.querySelectorAll('small, .sub, .badge')].filter(x => !x.closest('details')).map(x => squash(x.textContent)).filter(Boolean);
  const det = [...c.querySelectorAll('details li')].map(x => squash(x.textContent)).filter(Boolean);
  return main + (extra.length ? (main ? ' (' : '') + extra.join('; ') + (main ? ')' : '') : '') + (det.length ? (main || extra.length ? ': ' : '') + det.join('; ') : '');
}
const shown = r => !r.hidden && !r.closest('[hidden]') && r.style.display !== 'none';
B.tableToRows = table => {
  const hr = table.tHead && table.tHead.rows.length ? table.tHead.rows[table.tHead.rows.length - 1] : null;
  const rows = bodyRows(table).concat(table.tFoot ? [...table.tFoot.rows] : []);
  const grouped = rows.some(r => r.classList.contains('grp'));
  const ncol = Math.max(0, ...rows.concat(hr ? [hr] : []).map(r => [...r.cells].reduce((a, c) => a + (+c.colSpan || 1), 0)));
  const spread = r => { const o = []; [...r.cells].forEach(c => { o.push(exportText(c)); for (let i = 1; i < (+c.colSpan || 1); i++) o.push(''); }); while (o.length < ncol) o.push(''); return o; };
  const out = []; let g = '', anyLink = false;
  rows.forEach(r => {
    if (r.classList.contains('grp')) { g = mainText(r.cells[0]); return; }
    if (!shown(r)) return;
    const links = [...new Set([...r.querySelectorAll('a[href]')].map(a => a.href).filter(h => /^https?:/i.test(h)))];
    if (links.length) anyLink = true;
    out.push({cells: (grouped ? [g] : []).concat(spread(r)), links});
  });
  const head = hr ? (grouped ? [T('group', 'Group')] : []).concat(spread(hr).map((h, i) => h || (i === 0 ? T('item', 'Item') : ''))) : null;
  if (anyLink && head) head.push(T('links', 'Links'));
  return (head ? [head] : []).concat(out.map(o => anyLink ? o.cells.concat(o.links.join(' ')) : o.cells));
};
B.download = (name, text, type = 'text/csv;charset=utf-8') => {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['﻿' + text], {type})); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
B.csv = (table, name) => { const rows = B.tableToRows(table); B.download(/\.csv$/.test(name) ? name : name + '.csv', B.toCSV(rows)); B.announce(T('downloaded', 'Downloaded ') + (rows.length - 1) + T('rows', ' rows')); };
function csvButton(table) {
  if (table._bcmCsv) return; table._bcmCsv = true;
  const p = document.createElement('p'); p.className = 'csv-line print-hide'; p.setAttribute('data-report', 'skip');
  const b = document.createElement('button'); b.type = 'button'; b.className = 'linkbtn'; b.textContent = T('csv', 'Download this view (CSV)');
  b.addEventListener('click', () => B.csv(table, table.dataset.csv || 'baycounty-table'));
  p.appendChild(b); (table.closest('.tablewrap') || table).after(p);
}
B.enhance = (root = document) => {
  B.bindParams(root);
  root.querySelectorAll('table[data-sortable]').forEach(t => B.sortable(t));
  root.querySelectorAll('table[data-csv]').forEach(csvButton);
};
B.enhance();
})();
