/* BayCounty.me shared page helpers, exposed as window.BCM. Bundled into /assets/site.js.

   URL state     data-param="x" on a <select>, text <input>, checkbox, or a chip group
                 (an element holding buttons with data-value and aria-pressed) is read from ?x= on
                 load and written back with history.replaceState when it changes (text is debounced).
                 Select values match by value, label, or loosely ("City of Lynn Haven" = "Lynn Haven";
                 extra names can go in data-alias="pc panama-city"). Options added later by a page
                 script are picked up (retried for ~9 s). A checkbox writes 1/0 only when it differs
                 from its starting state.
                 Pages with their own JS state use BCM.urlState.get(k) / .set({k: v}) / .setLater().
   Tables        sorting, filtering and CSV export are done by /assets/tables.js (window.TT), not here.
   Announce      BCM.announce(text) speaks a short status to screen readers.

   site.js is a deferred script in <head>, so deferred page scripts (in the body) can use BCM at
   start-up. Inline page scripts run earlier, while the page parses: wrap them in DOMContentLoaded. */
(() => {
const B = window.BCM = window.BCM || {};

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

/* ---------- city filter ----------
   One government picker at the top of a page (<select data-city>, written by city_filter.city_bar) sets the city
   for the whole page. Its value is a key (county, schools, pc, pcb, lh, cw, sp, parker, mb), kept in the link as
   ?gov=<key> and remembered, so the next page opens on the same city.
   A page connects to it in one of three ways:
     data-city-link   on the page's own government <select>: BCM sets it to the matching option and fires change.
                      Its options can be keys or any name a dataset uses ("City of Lynn Haven", "sf").
     data-g="pc pcb"  on rows, cards or list items, when the bar has data-city-hide: rows of other cities are hidden.
     data-by='{...}'  on a figure: its text for each city, written by the build ("" is the countywide value).
     BCM.city.on(fn)  fn(key, detail) runs now and on every change; BCM.city.get() is set before page scripts run.
   Controls marked data-scope (a year picker, say) are moved into the bar, so a page's filters sit in one place. */
const CT = window.BCM_CITIES || [];
const cl = s => String(s ?? '').toLowerCase().replace(/&/g, ' and ').replace(/\([^)]*\)/g, ' ').trim()
  .replace(/^city of |, city of$|\bbocc\b/g, ' ').replace(/[^a-z0-9]+/g, ' ').trim();
const CIDX = new Map();
CT.forEach(c => c.al.forEach(a => { if (!CIDX.has(a)) CIDX.set(a, c.k); }));
CT.forEach(c => CIDX.set(cl(c.s), c.k));
const STORE = 'bcm-city';
let cur = '', csel = null, ready = false;
const recall = () => { try { return localStorage.getItem(STORE) || ''; } catch (e) { return ''; } };
const remember = k => { try { if (k) localStorage.setItem(STORE, k); else localStorage.removeItem(STORE); } catch (e) {} };
const city = B.city = {
  list: CT,
  key(v) {
    if (v == null || v === '') return '';
    if (CT.some(c => c.k === v)) return v;
    const n = cl(v);
    return CIDX.get(n) || CIDX.get(n.replace(/ (cra|community redevelopment agency|commission|council|board)$/, '')) || null;
  },
  label: k => (CT.find(c => c.k === k) || {}).s || '',
  cra: k => (CT.find(c => c.k === k) || {}).cra || '',
  /* does a row value (a name, a code, or a list of them) belong to the city k? No city picked: always. */
  has(k, v) { if (!k) return true; return (Array.isArray(v) ? v : [v]).some(x => city.key(x) === k); },
  get: () => cur,
  /* the city the reader last picked on any page ('' if none): for tools with their own government picker and no bar */
  remembered: () => city.key(recall()) || '',
  set(k, why = 'set') { k = city.key(k) || ''; if (!avail(k)) k = ''; remember(k); if (k !== cur || why === 'force') apply(k, why); },
  on(fn) { document.addEventListener('bcm:city', e => fn(e.detail.key, e.detail)); if (ready) fn(cur, detail('now')); },
  /* After the city changes, keep the year picker on a year this city has records for. years: its rows' years. */
  fitYear(sel, years) {
    if (!sel || !sel.value || sel.value === 'all') return false;
    const ys = [...new Set(years.filter(y => y != null).map(Number))];
    if (ys.includes(+sel.value)) return false;
    const T = window.TT, cy = new Date().getFullYear() + (new Date().getMonth() >= 9 ? 1 : 0);
    const want = ys.sort((a, b) => b - a).find(y => y <= cy) ?? ys[0];
    const o = want != null && [...sel.options].find(x => +x.value === want);
    sel.value = o ? o.value : ([...sel.options].find(x => x.value === '' || x.value === 'all') || {}).value ?? '';
    fire(sel);
    return true;
  },
};
const avail = k => !k || !csel || [...csel.options].some(o => o.value === k);
const detail = why => ({key: cur, label: city.label(cur), cra: city.cra(cur), why});
const optFor = (sel, k) => [...sel.options].find(o => k ? (o.value === k || city.key(o.value) === k || city.key(o.textContent.trim()) === k || (o.dataset.alias || '').split(/\s+/).includes(k))
  : (o.value === '' || o.value === 'all'));
function syncLinks(tries = 0) {
  let missing = false;
  document.querySelectorAll('select[data-city-link]').forEach(s => {
    const o = optFor(s, cur);
    if (!o) { missing = true; return; }
    if (s.value !== o.value) { s.value = o.value; fire(s); }
  });
  if (missing && tries < 40) setTimeout(() => syncLinks(tries + 1), 200); // options a page adds after loading its data
}
function hideRows() {
  if (!csel || !csel.hasAttribute('data-city-hide')) return;
  document.querySelectorAll('main [data-g]').forEach(el => {
    if (el.closest('.scope')) return;
    const off = !!cur && el.dataset.g !== '*' && !el.dataset.g.split(/\s+/).includes(cur);
    if (off) { if (!el.hidden) { el.hidden = true; el.dataset.cityOff = '1'; } }
    else if (el.dataset.cityOff) { el.hidden = false; delete el.dataset.cityOff; }
  });
  // a section whose every row belongs to other cities says so instead of going blank
  document.querySelectorAll('main [data-city-empty]').forEach(box => {
    const rows = [...box.querySelectorAll('[data-g]')], none = !!cur && rows.length > 0 && rows.every(r => r.hidden);
    let p = box.querySelector(':scope > .sc-empty');
    if (none && !p) { p = document.createElement('p'); p.className = 'sc-empty muted'; box.appendChild(p); }
    if (p) { p.hidden = !none; p.textContent = none ? (box.dataset.cityEmpty || 'Nothing here for {city}.').replace('{city}', city.label(cur)) : ''; }
  });
}
function apply(k, why) {
  cur = k;
  if (csel && csel.value !== k) csel.value = k;
  if (!csel || !csel.dataset.cityFixed) urlState.set({gov: k});
  document.documentElement.dataset.city = k;
  if (!ready) return;
  hideRows(); syncLinks();
  // figures written per city by the build (city_filter.by_city): {"": countywide, "pc": ..., ...}
  document.querySelectorAll('[data-by]').forEach(el => { try { const m = JSON.parse(el.dataset.by), v = cur && cur in m ? m[cur] : m['']; if (v != null) el.innerHTML = v; } catch (e) {} });
  document.querySelectorAll('[data-city-name]').forEach(el => { el.textContent = k ? city.label(k) : (el.dataset.cityName || 'Bay County'); });
  document.dispatchEvent(new CustomEvent('bcm:city', {detail: detail(why)}));
}
(function initCity() {
  csel = document.querySelector('select[data-city]');
  if (!csel) return;
  const u = new URLSearchParams(location.search);
  let k = city.key(u.get('gov'));
  if (!k) for (const p of (csel.dataset.legacy || '').split(/\s+/).filter(Boolean)) {
    const v = (u.get(p) || '').split(',')[0];
    if (v && (k = city.key(v))) break;
  }
  if (!k && !u.has('gov')) k = city.key(recall()) || '';
  // a government's own page is about one government: it sets the remembered city, and the picker opens another page
  const fixed = csel.dataset.cityFixed;
  if (fixed) { k = fixed; remember(fixed); }
  if (!avail(k)) k = '';
  if (k) remember(k); // a city opened from a link carries on to the next page too
  document.querySelectorAll('[data-city-link]').forEach(s => { delete s.dataset.param; }); // the bar owns ?gov=
  const slot = csel.closest('.scope').querySelector('[data-scope-slot]');
  if (slot) document.querySelectorAll('[data-scope]:not(.scope)').forEach(el => slot.appendChild(el));
  const head = document.querySelector('.site-head');
  if (head) document.documentElement.style.setProperty('--head-h', head.offsetHeight + 'px');
  apply(k, 'init');
  csel.addEventListener('change', () => {
    if (!fixed) return city.set(csel.value, 'user');
    const c = CT.find(x => x.k === csel.value); remember(csel.value);
    location.href = c ? '/governments/' + c.slug : '/governments';
  });
  document.addEventListener('DOMContentLoaded', () => { ready = true; apply(cur, 'init'); });
})();

B.enhance = (root = document) => B.bindParams(root);
B.enhance();
})();
