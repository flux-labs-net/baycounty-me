/* BayCounty.me tables: every list on the site can be sorted, filtered and exported.

   Any <table> on a page is enhanced automatically:
     - click a column heading to sort it (click again to reverse)
     - a filter box and drop-down filters (for columns with a handful of values)
     - "Download CSV" of the rows on screen, in the order shown
   Default order: newest first by the table's date column, then A to Z by its first
   text column. Tables with no date column open A to Z.

   Group rows (tr.grp, or one cell spanning the row) keep their rows under them;
   totals rows stay at the bottom. Rows hidden by a page's own filters (the hidden
   attribute) are respected and left out of the count and the CSV. If a page script
   re-renders a table, the current sort and filters are applied again.

   Opt out:   <table data-tt="off">   (charts drawn as tables, e.g. heat maps)
   Own data:  <table data-tt="own">   page script sorts its own data (paginated ledgers);
              it calls TT.attach() for the sortable headings and TT.csv() to export.
   Search:    <table data-tt-search="off">   page already has its own search box for this table.
   Headings:  <table data-cols="Name|Amount"> names columns for a table with no <thead>.
   Order:     <table data-tt-sort="2:desc"> overrides the default order.
   Year:      a table with a date column covering several years gets a Year picker that opens on the
              newest year with records (never past the current fiscal year), with "All years" one tap
              away. ?year=2024 or ?year=all in the link picks for every table. <table data-tt-year="off">
              opts out; tables with about one row per year (a yearly series) are left showing every year. */
(() => {
const ES = (document.documentElement.lang || '').startsWith('es');
const L = ES
  ? {filter: 'Filtrar filas', all: 'Todo', of: 'de', rows: 'filas', row: 'fila', csv: 'Descargar CSV', sort: 'Ordenar por', none: 'Ninguna fila coincide.', clear: 'Borrar', year: 'Año', allYears: 'Todos los años'}
  : {filter: 'Filter rows', all: 'All', of: 'of', rows: 'rows', row: 'row', csv: 'Download CSV', sort: 'Sort by', none: 'No rows match.', clear: 'Clear', year: 'Year', allYears: 'All years'};

/* ---------- values ---------- */
const MON = {jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, sept: 9, oct: 10, nov: 11, dec: 12,
  ene: 1, abr: 4, ago: 8, dic: 12, january: 1, february: 2, march: 3, april: 4, june: 6, july: 7, august: 8, september: 9, october: 10, november: 11, december: 12};
const clean = s => String(s ?? '').replace(/\s+/g, ' ').trim();
const EMPTY = /^(|—|–|-|n\/a|none|not stated|unknown)$/i;

/* A sortable number from text like "$1,234", "−$3.2M", "~$50K", "59.7%", "(1,200)". Null if the text does not start with a number. */
function num(s) {
  s = clean(s);
  const m = s.match(/^[~≈<>+]?\s*(\(|−|-|–)?\s*\$?\s*(\d[\d,]*(?:\.\d+)?|\.\d+)\s*(K|M|B|bn|thousand|million|billion)?\b/i);
  if (!m) return null;
  let v = parseFloat(m[2].replace(/,/g, ''));
  const u = (m[3] || '').toLowerCase();
  if (u === 'k' || u === 'thousand') v *= 1e3; else if (u === 'm' || u === 'million') v *= 1e6; else if (u === 'b' || u === 'bn' || u === 'billion') v *= 1e9;
  return m[1] ? -v : v;
}

/* A sortable date (yyyymmdd.hhmm) from text. When the text names several dates or years,
   the latest one wins ("2008 purchase; final payment FY2022" sorts as 2022). FY2024 sorts
   as Sept 30, 2024, the end of Florida's local fiscal year. */
function dateKey(s) {
  s = clean(s);
  if (!s) return null;
  let best = null;
  const put = (y, m, d, t) => { if (y < 1800 || y > 2200) return; const k = y * 1e4 + (m || 0) * 100 + (d || 0) + (t || 0); if (best == null || k > best) best = k; };
  let r, hit = false;
  const iso = /\b((?:18|19|20|21)\d{2})-(\d{1,2})(?:-(\d{1,2}))?(?:[T ](\d{1,2}):(\d{2}))?/g;
  while ((r = iso.exec(s))) { hit = true; put(+r[1], +r[2], +(r[3] || 0), r[4] ? (+r[4] * 60 + +r[5]) / 1440 : 0); }
  const us = /\b(\d{1,2})\/(\d{1,2})\/((?:19|20)?\d{2})\b/g;
  while ((r = us.exec(s))) { hit = true; let y = +r[3]; if (y < 100) y += 2000; put(y, +r[1], +r[2]); }
  const md = /\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20|21)\d{2})\b/g;
  while ((r = md.exec(s))) { const m = MON[r[1].toLowerCase()]; if (m) { hit = true; put(+r[3], m, +r[2]); } }
  const dm = /\b(\d{1,2})\s+(?:de\s+)?([A-Za-z]{3,9})\.?,?\s+(?:de\s+)?((?:19|20|21)\d{2})\b/g;
  while ((r = dm.exec(s))) { const m = MON[r[2].toLowerCase()]; if (m) { hit = true; put(+r[3], m, +r[1]); } }
  const my = /\b([A-Za-z]{3,9})\.?\s+(?:de\s+)?((?:19|20|21)\d{2})\b/g;
  while ((r = my.exec(s))) { const m = MON[r[1].toLowerCase()]; if (m) { hit = true; put(+r[2], m, 0); } }
  const fy = /\bFY\s?'?((?:19|20)?\d{2})(?:\s?[-–\/]\s?(?:FY\s?)?((?:19|20)?\d{2}))?\b/gi;
  while ((r = fy.exec(s))) { hit = true; const a = +r[1] < 100 ? 2000 + +r[1] : +r[1]; let b = r[2] ? +r[2] : a; if (b < 100) b += Math.floor(a / 100) * 100; put(Math.max(a, b), 9, 30); }
  if (!hit) {
    const yr = /\b((?:18|19|20|21)\d{2})(?:\s?[-–]\s?((?:19|20|21)?\d{2}))?\b/g;
    while ((r = yr.exec(s))) { let b = r[2] ? +r[2] : +r[1]; if (b < 100) b += Math.floor(+r[1] / 100) * 100; put(Math.max(+r[1], b), 12, 31); }
  }
  if (best == null && /[A-Za-z\/]/.test(s) && /\b(18|19|20|21)\d{2}\b/.test(s)) { const t = Date.parse(s); if (!isNaN(t)) { const d = new Date(t); put(d.getFullYear(), d.getMonth() + 1, d.getDate(), (d.getHours() * 60 + d.getMinutes()) / 1440); } }
  return best;
}

/* ---------- years ---------- */
/* Florida local fiscal years start Oct 1, so from October the current fiscal year is next calendar year. */
const curFY = () => { const d = new Date(); return d.getFullYear() + (d.getMonth() >= 9 ? 1 : 0); };
const yearOf = v => { const k = typeof v === 'number' ? v : dateKey(v); return k == null ? null : Math.floor(k / 1e4); };
/* The year a page opens on: the newest year that has records, not past the current fiscal year.
   ?year=2024 or ?year=all in the page link overrides it. '' means all years. */
function startYear(years, counts) {
  const ys = [...years].filter(y => y != null).map(Number).sort((a, b) => b - a);
  const u = new URLSearchParams(location.search).get('year');
  if (u === 'all') return '';
  if (u && ys.includes(+u)) return +u;
  // with counts ({year: rows}), skip a year holding only a few stray records: it needs 3, or a tenth of the busiest year
  const top = counts ? Math.max(...Object.values(counts)) : 0;
  const enough = y => !counts || (counts[y] || 0) >= Math.min(top, Math.max(3, Math.ceil(top / 10)));
  const y = ys.find(x => x <= curFY() && enough(x)) ?? ys.find(x => x <= curFY());
  return y ?? ys[ys.length - 1] ?? '';
}
const countBy = arr => arr.reduce((m, y) => { if (y != null) m[y] = (m[y] || 0) + 1; return m; }, {});
/* Every year a free-text date names: "FY2024-FY2026" is 2024, 2025 and 2026; "2008 purchase; final payment FY2022" is 2008 and 2022. */
function yearsIn(s) {
  s = String(s ?? ''); const out = new Set();
  const rng = /(?:FY\s?)?(?<!\d)((?:19|20)\d{2})\s?(?:-|–|to|through)\s?(?:FY\s?)?((?:19|20)?\d{2})\b/gi; let r;
  while ((r = rng.exec(s))) { const a = +r[1]; let b = +r[2]; if (b < 100) b += Math.floor(a / 100) * 100; if (b >= a && b - a <= 30) for (let y = a; y <= b; y++) out.add(y); }
  (s.match(/(?<!\d)(?:19|20)\d{2}(?!\d)/g) || []).forEach(y => out.add(+y));
  return [...out];
}
/* <select> markup for a year picker; fy labels the years FY2026 instead of 2026. */
const yearOptions = (years, cur, fy) => `<option value="">${L.allYears}</option>` + years.map(y => `<option value="${y}"${cur === y ? ' selected' : ''}>${fy ? 'FY' : ''}${y}</option>`).join('');

const coll = new Intl.Collator(ES ? 'es' : 'en', {numeric: true, sensitivity: 'base'});
/* Compare two values of one type; empty values always sort last, whichever the direction. */
function cmp(a, b, type, dir) {
  const ea = a == null || a === '', eb = b == null || b === '';
  if (ea || eb) return ea === eb ? 0 : ea ? 1 : -1;
  const c = type === 'text' ? coll.compare(a, b) : a - b;
  return dir === 'desc' ? -c : c;
}
/* Sort an array of records. keys: [{get: rec => value, type: 'text'|'num'|'date', dir: 'asc'|'desc'}, ...] in priority order. */
function sortBy(arr, keys) {
  const pre = arr.map((r, i) => ({r, i, v: keys.map(k => { const x = k.get(r); return k.type === 'text' ? clean(x) : (x == null || x === '' ? null : (typeof x === 'number' ? x : (k.type === 'date' ? dateKey(x) : num(x)))); })}));
  pre.sort((A, B) => { for (let j = 0; j < keys.length; j++) { const c = cmp(A.v[j], B.v[j], keys[j].type, keys[j].dir); if (c) return c; } return A.i - B.i; });
  return pre.map(p => p.r);
}

/* ---------- CSV ---------- */
const q = v => { const s = String(v ?? ''); return /[",\n\r]/.test(s) || /^\s|\s$/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
function csv(name, head, rows) {
  const text = '﻿' + [head, ...rows].map(r => r.map(q).join(',')).join('\r\n');
  const u = URL.createObjectURL(new Blob([text], {type: 'text/csv;charset=utf-8'}));
  const a = document.createElement('a'); a.href = u; a.download = name.endsWith('.csv') ? name : name + '.csv';
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 1500);
}
const slug = s => clean(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60);
const pageSlug = () => slug(location.pathname.replace(/^\/|\/$/g, '').replace(/\//g, '-')) || 'home';

/* ---------- cell text ---------- */
const SUB = 'small,.sub,.tt-ar,.sr,.sr-only,svg';
/* The main text of a cell: what it sorts by. Leaves out sub-lines (<small>, .sub) and the open part of <details>. */
function prim(el) {
  if (!el) return '';
  let out = '';
  const walk = n => {
    for (const c of n.childNodes) {
      if (c.nodeType === 3) out += c.nodeValue;
      else if (c.nodeType === 1) {
        if (c.matches(SUB)) continue;
        if (c.tagName === 'BR') { out += ' '; continue; }
        if (c.tagName === 'DETAILS') { const s = c.querySelector(':scope > summary'); if (s) out += ' ' + s.textContent + ' '; continue; }
        walk(c);
      }
    }
  };
  walk(el);
  return clean(out);
}
const subText = el => el ? clean([...el.querySelectorAll('small,.sub')].map(x => x.textContent).join(' · ')) : '';
/* What a cell exports as: a lone short link exports its address; otherwise main text, plus its sub-line. */
function cellOut(el) {
  if (!el) return '';
  const links = el.querySelectorAll('a[href]');
  const p = prim(el);
  if (links.length === 1 && p.length <= 24 && clean(links[0].textContent) === p && !/^#/.test(links[0].getAttribute('href'))) return links[0].href;
  const s = subText(el);
  return s ? (p ? p + ' — ' + s : s) : p;
}

/* ---------- table model ---------- */
const DATE_HEAD = /\b(date|dates|when|time|year|years|fy|fiscal year|issued|added|announced|awarded|signed|first paid|last used|until|final payment|period|term|updated|checked|meeting|held|filed|opened|closed|fecha|año|cuando)\b/i;
const NOT_DATE_HEAD = /\b(rate|amount|cost|total|per|share|count|number|registered|approved|owed|value|tax|aid|award)\b|\$/i;
const TOTAL = /^(total|totals|grand total|all governments|all agencies|sum|combined|todos|suma)\b/i;

function headRow(t) { const h = t.tHead; return h && h.rows.length ? h.rows[h.rows.length - 1] : null; }
/* Cells of a row laid out by column, following colspan. */
function cellsByCol(tr) { const out = []; for (const c of tr.cells) { const n = Math.max(1, c.colSpan || 1); for (let i = 0; i < n; i++) out.push(i ? null : c); } return out; }
function ncols(t) { const h = headRow(t); if (h) return cellsByCol(h).length; let m = 0; for (const b of t.tBodies) for (const r of b.rows) m = Math.max(m, cellsByCol(r).length); return m; }

function kind(tr, n) {
  if (tr.classList.contains('grp') || tr.dataset.ttRole === 'group') return 'group';
  if (tr.cells.length === 1 && (tr.cells[0].colSpan || 1) >= Math.max(2, n)) return tr.cells[0].tagName === 'TH' ? 'group' : 'note';
  if (tr.classList.contains('total') || tr.classList.contains('tot') || tr.dataset.ttRole === 'total') return 'total';
  const first = tr.cells[0];
  if (first && TOTAL.test(prim(first))) return 'total';
  return 'row';
}

/* Make a <thead> for a table that has none, from data-cols or a best guess. */
function ensureHead(t) {
  if (headRow(t)) return true;
  const body = t.tBodies[0]; if (!body || !body.rows.length) return false;
  const n = ncols(t); if (n < 1) return false;
  let names = (t.dataset.cols || '').split('|').map(clean).filter(Boolean);
  if (names.length !== n) {
    const sample = [...body.rows].find(r => cellsByCol(r).length === n);
    names = Array.from({length: n}, (_, i) => {
      const c = sample && cellsByCol(sample)[i];
      if (i === 0) return ES ? 'Nombre' : 'Name';
      return c && (c.classList.contains('num') || num(prim(c)) != null) ? (n === 2 ? (ES ? 'Monto' : 'Amount') : (ES ? 'Valor' : 'Value') + ' ' + i) : (ES ? 'Detalle' : 'Detail') + (n > 2 ? ' ' + i : '');
    });
  }
  const sample = [...body.rows].find(r => cellsByCol(r).length === n);
  const th = t.createTHead(); const tr = th.insertRow();
  names.forEach((x, i) => { const c = document.createElement('th'); c.scope = 'col'; c.textContent = x; const s = sample && cellsByCol(sample)[i]; if (s && s.classList.contains('num')) c.className = 'num'; tr.appendChild(c); });
  t.classList.add('tt-madehead');
  return true;
}

/* ---------- the enhancer ---------- */
const STATE = new WeakMap();
let busy = false;

function columns(t, st) {
  const h = headRow(t); const hc = cellsByCol(h);
  const rows = st.rows.filter(r => r.k === 'row');
  return hc.map((th, i) => {
    if (!th) return null;
    const name = prim(th) || clean(th.getAttribute('aria-label') || '');
    const vals = rows.map(r => r.c[i]).filter(Boolean).map(prim).filter(v => !EMPTY.test(v));
    let type = 'text';
    const nums = vals.filter(v => num(v) != null).length, dates = vals.filter(v => dateKey(v) != null).length;
    const pureDates = vals.filter(v => /^((18|19|20|21)\d{2}-\d{2}(-\d{2})?|[A-Z][a-z]{2,8}\.? \d{1,2}, \d{4}|FY ?\d{4}(-\d{2,4})?)\b/.test(v)).length;
    if (vals.length && ((DATE_HEAD.test(name) && !NOT_DATE_HEAD.test(name) && dates >= vals.length * .6) || pureDates >= vals.length * .8)) type = 'date';
    else if (vals.length && (th.classList.contains('num') || nums >= vals.length * .8) && nums >= vals.length * .6) type = 'num';
    const distinct = new Set(vals);
    return {i, th, name, type, sortable: !!name && vals.length > 0, distinct};
  });
}

function read(t, st) {
  const n = ncols(t); st.n = n;
  const rows = [];
  let grp = null, gi = 0;
  for (const b of t.tBodies) for (const tr of b.rows) {
    const k = kind(tr, n);
    if (k === 'group') { grp = {tr, name: prim(tr.cells[0]), i: gi++}; rows.push({tr, k, g: grp}); continue; }
    rows.push({tr, k, g: grp, c: cellsByCol(tr), body: b});
  }
  rows.forEach((r, i) => r.i = i);
  st.rows = rows;
  st.seen = new WeakSet(rows.map(r => r.tr));
}

function defaultOrder(st) {
  const a = (st.t.dataset.ttSort || '').match(/^(\d+)(?::(asc|desc))?$/);
  if (a && st.cols[+a[1]]) return {col: +a[1], dir: a[2] || 'asc'};
  const d = st.cols.find(c => c && c.sortable && c.type === 'date');
  if (d) return {col: d.i, dir: 'desc'};
  const x = st.cols.find(c => c && c.sortable && c.type === 'text');
  if (x) return {col: x.i, dir: 'asc'};
  return null;
}
/* The tie-break chain: newest first by date, then A to Z by the first text column. */
function chain(st, col, dir) {
  const keys = [];
  const add = (c, d) => { if (c && c.sortable && !keys.some(k => k.i === c.i)) keys.push({i: c.i, type: c.type, dir: d}); };
  if (col != null) add(st.cols[col], dir);
  add(st.cols.find(c => c && c.sortable && c.type === 'date'), 'desc');
  add(st.cols.find(c => c && c.sortable && c.type === 'text'), 'asc');
  return keys;
}

function applySort(st) {
  const {t, sort} = st;
  st.cols.forEach(c => { if (c && c.th) { if (sort && c.i === sort.col) c.th.setAttribute('aria-sort', sort.dir === 'asc' ? 'ascending' : 'descending'); else c.th.removeAttribute('aria-sort'); } });
  if (!sort) return;
  const keys = chain(st, sort.col, sort.dir).map(k => ({...k, get: r => { const c = r.c[k.i]; return c ? prim(c) : ''; }}));
  // sort within each tbody and each group; totals and notes stay at the end of their block
  const blocks = new Map();
  st.rows.forEach(r => { const key = r.k === 'group' ? null : (r.body || r.tr.parentNode); if (!key) return; const id = key; if (!blocks.has(id)) blocks.set(id, new Map()); const gm = blocks.get(id); const g = r.g ? r.g.i : -1; if (!gm.has(g)) gm.set(g, []); gm.get(g).push(r); });
  busy = true;
  for (const [body, gm] of blocks) {
    const frag = document.createDocumentFragment();
    const groups = st.rows.filter(r => r.k === 'group' && (r.tr.parentNode === body));
    const order = [-1, ...groups.map(g => g.g.i)];
    for (const gid of order) {
      const head = groups.find(g => g.g.i === gid);
      if (head) frag.appendChild(head.tr);
      const list = gm.get(gid) || [];
      const rows = sortBy(list.filter(r => r.k === 'row'), keys);
      rows.concat(list.filter(r => r.k === 'total'), list.filter(r => r.k === 'note')).forEach(r => frag.appendChild(r.tr));
    }
    body.appendChild(frag);
  }
  busy = false;
}

function applyFilter(st) {
  const {bar} = st; if (!bar) return;
  const words = clean(st.q).toLowerCase().split(' ').filter(Boolean);
  const sel = st.sel;
  busy = true;
  let shown = 0, total = 0;
  const groupHit = new Map();
  st.rows.forEach(r => {
    if (r.k !== 'row') return;
    if (r.tr.hidden) { r.tr.classList.remove('tt-off'); return; }
    total++;
    let ok = true;
    if (words.length) { const txt = (r.tr.textContent || '').toLowerCase() + ' ' + (r.g ? r.g.name.toLowerCase() : ''); ok = words.every(w => txt.includes(w)); }
    if (ok && st.yr !== '' && st.yr != null && r.y !== st.yr) ok = false;
    if (ok) for (const [i, v] of sel) { if (v && prim(r.c[i]) !== v) { ok = false; break; } }
    r.tr.classList.toggle('tt-off', !ok);
    if (ok) { shown++; if (r.g) groupHit.set(r.g.i, true); }
  });
  const filtering = words.length || [...sel.values()].some(Boolean) || (st.yr !== '' && st.yr != null);
  st.rows.forEach(r => {
    if (r.k === 'group') r.tr.classList.toggle('tt-off', !!filtering && !groupHit.get(r.g.i));
    if (r.k === 'total') r.tr.classList.toggle('tt-off', !!filtering);
  });
  mo.takeRecords();
  if (st.empty) st.empty.hidden = !(filtering && shown === 0);
  busy = false;
  const c = bar.querySelector('.tt-count');
  if (c) c.textContent = filtering ? `${shown.toLocaleString()} ${L.of} ${total.toLocaleString()} ${L.rows}` : `${total.toLocaleString()} ${total === 1 ? L.row : L.rows}`;
  const x = bar.querySelector('.tt-clear'); if (x) x.hidden = !filtering;
}

function buildBar(st) {
  const {t} = st;
  const body = st.rows.filter(r => r.k === 'row');
  const wrap = t.closest('.tablewrap, .tw, .table-wrap') && t.closest('.tablewrap, .tw, .table-wrap').querySelectorAll('table').length === 1 ? t.closest('.tablewrap, .tw, .table-wrap') : t;
  let bar = st.bar;
  if (!bar) {
    bar = document.createElement('div'); bar.className = 'tt-bar'; bar.dataset.report = 'skip';
    wrap.parentNode.insertBefore(bar, wrap);
    st.bar = bar;
  }
  const big = body.length >= 8, search = big && t.dataset.ttSearch !== 'off';
  const label = st.label;
  const filters = big ? st.cols.filter(c => c && c.type === 'text' && c.sortable && c.distinct.size >= 2 && c.distinct.size <= 15 && c.distinct.size < body.length * .7 && [...c.distinct].every(v => v.length <= 60)) : [];
  // year picker: a date column spanning several years, with more than one row per year on average
  const dc = st.cols.find(c => c && c.sortable && c.type === 'date');
  let years = null, fy = false;
  if (dc && big && t.dataset.ttYear !== 'off') {
    body.forEach(r => { r.y = r.c[dc.i] ? yearOf(prim(r.c[dc.i])) : null; });
    const ys = new Set(body.map(r => r.y).filter(y => y != null));
    if (ys.size >= 2 && body.length >= ys.size * 1.5) years = [...ys].sort((a, b) => b - a);
    st.ycount = countBy(body.map(r => r.y));
    fy = [...dc.distinct].filter(v => /\bFY/i.test(v)).length > dc.distinct.size / 2;
  }
  if (!years) st.yr = '';
  else if (st.yr === undefined || (st.yr !== '' && !years.includes(st.yr))) st.yr = startYear(years, st.ycount);
  bar.innerHTML = (years ? `<label class="tt-f tt-y"><span class="sr">${L.year}</span><select class="tt-ysel" aria-label="${L.year}${label ? ': ' + esc(label) : ''}">${yearOptions(years, st.yr, fy)}</select></label>` : '')
    + (search ? `<label class="tt-q"><span class="sr">${L.filter}</span><input type="search" placeholder="${L.filter}" aria-label="${L.filter}${label ? ': ' + esc(label) : ''}" value="${esc(st.q)}"></label>` : '')
    + filters.map(c => `<label class="tt-f"><span class="sr">${esc(c.name)}</span><select data-col="${c.i}" aria-label="${esc(c.name)}"><option value="">${esc(c.name)}: ${L.all}</option>${[...c.distinct].sort(coll.compare).map(v => `<option${st.sel.get(c.i) === v ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`).join('')
    + `<button type="button" class="tt-clear" hidden>${L.clear}</button><span class="tt-count" aria-live="polite"></span><button type="button" class="tt-csv">${L.csv}</button>`;
  // forget a filter whose value is gone after a re-render
  for (const [i, v] of st.sel) { const c = st.cols[i]; if (!c || !c.distinct.has(v) || !filters.includes(c)) st.sel.delete(i); }
  const inp = bar.querySelector('.tt-q input');
  if (inp) inp.addEventListener('input', () => { st.q = inp.value; applyFilter(st); });
  bar.querySelectorAll('select[data-col]').forEach(s => s.addEventListener('change', () => { st.sel.set(+s.dataset.col, s.value); applyFilter(st); }));
  const ysel = bar.querySelector('.tt-ysel');
  if (ysel) ysel.addEventListener('change', () => { st.yr = ysel.value ? +ysel.value : ''; applyFilter(st); });
  bar.querySelector('.tt-clear').addEventListener('click', () => { st.q = ''; st.sel.clear(); st.yr = ''; if (inp) inp.value = ''; bar.querySelectorAll('select').forEach(s => s.value = ''); applyFilter(st); });
  bar.querySelector('.tt-csv').addEventListener('click', () => exportTable(st));
  if (!st.empty) { st.empty = document.createElement('p'); st.empty.className = 'tt-empty muted'; st.empty.textContent = L.none; st.empty.hidden = true; wrap.parentNode.insertBefore(st.empty, wrap.nextSibling); }
}

const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

function labelOf(t) {
  if (t.getAttribute('aria-label')) return clean(t.getAttribute('aria-label'));
  if (t.caption) return prim(t.caption);
  const det = t.closest('details'); const sum = det && det.querySelector(':scope > summary');
  // nearest heading before the table
  let n = t.closest('.tablewrap, .tw') || t;
  for (let up = 0; up < 4 && n; up++, n = n.parentElement) {
    let p = n.previousElementSibling;
    while (p) { const h = p.matches('h1,h2,h3,h4,.sec-hd') ? p : p.querySelector && p.querySelector('h2,h3,h4'); if (h) return clean((h.querySelector('h2,h3,h4') || h).textContent) + (sum ? ' — ' + prim(sum) : ''); p = p.previousElementSibling; }
  }
  return sum ? prim(sum) : '';
}

function exportTable(st) {
  const {t} = st;
  const hc = cellsByCol(headRow(t));
  const idx = hc.map((c, i) => c ? i : -1).filter(i => i >= 0 && clean(prim(hc[i])));
  const grouped = st.rows.some(r => r.k === 'group');
  const head = (grouped ? [ES ? 'Grupo' : 'Group'] : []).concat(idx.map(i => prim(hc[i])));
  const out = [];
  [...t.tBodies].forEach(b => [...b.rows].forEach(tr => {
    const r = st.rows.find(x => x.tr === tr);
    if (!r || r.k === 'group' || r.k === 'note' || tr.hidden || tr.classList.contains('tt-off')) return;
    out.push((grouped ? [r.g ? r.g.name : ''] : []).concat(idx.map(i => cellOut(r.c[i]))));
  }));
  if (t.tFoot) [...t.tFoot.rows].forEach(tr => { const c = cellsByCol(tr); out.push((grouped ? [''] : []).concat(idx.map(i => cellOut(c[i])))); });
  const title = document.querySelector('main h1');
  csv(['baycounty', pageSlug(), slug(st.label || (title && title.textContent) || 'table')].filter((x, i, a) => x && a.indexOf(x) === i).join('-'), head, out);
}

function wireHead(st) {
  st.cols.forEach(c => {
    if (!c || !c.sortable || c.th.querySelector('.tt-h')) return;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'tt-h';
    while (c.th.firstChild) b.appendChild(c.th.firstChild);
    const ar = document.createElement('span'); ar.className = 'tt-ar'; ar.setAttribute('aria-hidden', 'true'); b.appendChild(ar);
    c.th.appendChild(b);
    b.addEventListener('click', () => {
      const i = c.i, s = st.sort;
      st.sort = s && s.col === i ? {col: i, dir: s.dir === 'asc' ? 'desc' : 'asc'} : {col: i, dir: c.type === 'text' ? 'asc' : 'desc'};
      st.user = true; applySort(st); applyFilter(st); mo.takeRecords();
    });
  });
}

function enhance(t) {
  if (t.dataset.tt === 'off' || t.dataset.tt === 'own' || t.closest('[data-tt="off"]')) return;
  if (!ensureHead(t)) return;
  let st = STATE.get(t);
  if (!st) { st = {t, q: '', sel: new Map(), sort: null, user: false}; STATE.set(t, st); }
  read(t, st);
  if (!st.rows.some(r => r.k === 'row')) { if (st.bar) st.bar.hidden = true; return; }
  st.cols = columns(t, st);
  st.label = labelOf(t);
  if (!st.user || !st.sort || !st.cols[st.sort.col] || !st.cols[st.sort.col].sortable) st.sort = defaultOrder(st);
  t.classList.add('tt-on');
  wireHead(st);
  buildBar(st); st.bar.hidden = false;
  applySort(st);
  applyFilter(st);
  mo.takeRecords(); // our own edits are not page re-renders
}

/* Has a page script replaced or added rows since we last looked? */
function stale(t) {
  const st = STATE.get(t); if (!st) return true;
  let n = 0;
  for (const b of t.tBodies) for (const tr of b.rows) { n++; if (!st.seen.has(tr)) return true; }
  return n !== st.rows.length;
}

let queued = false;
function scan() {
  queued = false;
  document.querySelectorAll('main table, .tt-scope table').forEach(t => {
    if (t.dataset.tt === 'off' || t.dataset.tt === 'own') return;
    if (stale(t)) enhance(t);
  });
  document.querySelectorAll('[data-tt-list]').forEach(enhanceList);
}
function refreshCounts() { document.querySelectorAll('table.tt-on').forEach(t => { const st = STATE.get(t); if (st) applyFilter(st); }); }
const queue = () => { if (!queued) { queued = true; requestAnimationFrame(scan); } };
let countQueued = false;
const mo = new MutationObserver(list => {
  if (busy) return;
  let rows = false, attrs = false;
  for (const m of list) {
    if (m.type === 'attributes') { if (m.target.tagName === 'TR') attrs = true; continue; }
    const tg = m.target;
    if (tg.closest && tg.closest('.tt-bar')) continue;
    if (tg.nodeName === 'TBODY' || tg.nodeName === 'TABLE' || tg.nodeName === 'THEAD' || [...m.addedNodes].some(n => n.nodeType === 1 && (n.tagName === 'TABLE' || n.tagName === 'TR' || (n.querySelector && n.querySelector('table'))))) rows = true;
  }
  if (rows) queue();
  else if (attrs && !countQueued) { countQueued = true; requestAnimationFrame(() => { countQueued = false; refreshCounts(); }); }
});

/* ---------- API for pages that sort their own data ---------- */
/* TT.attach(table, {cols: [{key, type}...] (one per heading; null = not sortable), sort: {key, dir}, onSort(sort)})
   Makes the headings sort buttons, keeps aria-sort in step, and calls onSort when one is clicked. */
function attach(t, o) {
  const h = headRow(t); if (!h) return null;
  const hc = cellsByCol(h);
  const api = {sort: o.sort || null, set(s) { api.sort = s; paint(); }};
  const paint = () => hc.forEach((th, i) => { const c = o.cols[i]; if (!th || !c) return; if (api.sort && api.sort.key === c.key) th.setAttribute('aria-sort', api.sort.dir === 'asc' ? 'ascending' : 'descending'); else th.removeAttribute('aria-sort'); });
  hc.forEach((th, i) => {
    const c = o.cols[i]; if (!th || !c || th.querySelector('.tt-h')) return;
    const b = document.createElement('button'); b.type = 'button'; b.className = 'tt-h';
    while (th.firstChild) b.appendChild(th.firstChild);
    const ar = document.createElement('span'); ar.className = 'tt-ar'; ar.setAttribute('aria-hidden', 'true'); b.appendChild(ar);
    th.appendChild(b);
    b.addEventListener('click', () => {
      api.sort = api.sort && api.sort.key === c.key ? {key: c.key, dir: api.sort.dir === 'asc' ? 'desc' : 'asc'} : {key: c.key, dir: c.type === 'text' ? 'asc' : 'desc'};
      paint(); o.onSort && o.onSort(api.sort);
    });
  });
  t.classList.add('tt-on');
  paint();
  return api;
}

/* ---------- lists ----------
   <ol data-tt-list> with <li data-d="2026-10-21" data-n="Title"> items gets the same bar:
   filter, sort (newest first, oldest first, A to Z) and CSV (date, title, text, first link). */
function enhanceList(ol) {
  if (ol.dataset.ttOn) return;
  const items = [...ol.children].filter(li => li.tagName === 'LI');
  if (items.length < 2) return;
  ol.dataset.ttOn = '1';
  const bar = document.createElement('div'); bar.className = 'tt-bar'; bar.dataset.report = 'skip';
  const lab = ol.getAttribute('aria-label') || '';
  items.forEach(li => { li._y = li.dataset.d ? yearOf(li.dataset.d) : null; });
  const ys = [...new Set(items.map(li => li._y).filter(y => y != null))].sort((a, b) => b - a);
  const useY = ys.length >= 2 && items.length >= 8 && items.length >= ys.length * 1.5 && ol.dataset.ttYear !== 'off';
  let yr = useY ? startYear(ys, countBy(items.map(li => li._y))) : '';
  bar.innerHTML = (useY ? `<label class="tt-f tt-y"><span class="sr">${L.year}</span><select class="tt-ysel" aria-label="${L.year}">${yearOptions(ys, yr, false)}</select></label>` : '') + `<label class="tt-q"><span class="sr">${L.filter}</span><input type="search" placeholder="${ES ? 'Filtrar' : 'Filter'}" aria-label="${L.filter}${lab ? ': ' + esc(lab) : ''}"></label>`
    + `<label class="tt-f"><span class="sr">${L.sort}</span><select aria-label="${L.sort}"><option value="new">${ES ? 'Más recientes' : 'Newest first'}</option><option value="old">${ES ? 'Más antiguos' : 'Oldest first'}</option><option value="az">${ES ? 'A a la Z' : 'A to Z'}</option></select></label>`
    + `<span class="tt-count" aria-live="polite"></span><button type="button" class="tt-csv">${L.csv}</button>`;
  ol.parentNode.insertBefore(bar, ol);
  const inp = bar.querySelector('input'), sel = bar.querySelector('select:not(.tt-ysel)'), cnt = bar.querySelector('.tt-count'), ysel = bar.querySelector('.tt-ysel');
  const name = li => li.dataset.n || prim(li.querySelector('b, strong, .vt-h') || li);
  const run = () => {
    const w = clean(inp.value).toLowerCase().split(' ').filter(Boolean); let n = 0;
    items.forEach(li => { const ok = w.every(x => li.textContent.toLowerCase().includes(x)) && (yr === '' || li._y === yr); li.classList.toggle('tt-off', !ok); if (ok) n++; });
    const d = {get: li => li.dataset.d, type: 'date', dir: sel.value === 'old' ? 'asc' : 'desc'}, a = {get: name, type: 'text', dir: 'asc'};
    sortBy(items, sel.value === 'az' ? [a, d] : [d, a]).forEach(li => ol.appendChild(li));
    cnt.textContent = w.length || yr !== '' ? `${n} ${L.of} ${items.length}` : `${items.length}`;
    mo.takeRecords();
  };
  inp.addEventListener('input', run); sel.addEventListener('change', run);
  if (ysel) ysel.addEventListener('change', () => { yr = ysel.value ? +ysel.value : ''; run(); });
  bar.querySelector('.tt-csv').addEventListener('click', () => {
    const rows = [...ol.children].filter(li => li.tagName === 'LI' && !li.classList.contains('tt-off') && !li.hidden).map(li => {
      const a = li.querySelector('a[href]');
      const c = li.cloneNode(true); c.querySelectorAll('.tl-d, .vt-top, .vt-meta, .votes-row, a.src').forEach(x => x.remove());
      return [li.dataset.d || '', name(li), clean(c.textContent), a ? a.href : ''];
    });
    csv(['baycounty', pageSlug(), slug(lab)].filter(Boolean).join('-'), ES ? ['fecha', 'título', 'texto', 'enlace'] : ['date', 'title', 'text', 'link'], rows);
  });
  run();
}

window.TT = {num, dateKey, cmp, sortBy, csv, slug, pageSlug, attach, enhance, enhanceList, prim, L, curFY, yearOf, startYear, yearOptions, yearsIn, countBy};

const start = () => { scan(); mo.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['hidden']}); };
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
