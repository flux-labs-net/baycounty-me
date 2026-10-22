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

B.enhance = (root = document) => B.bindParams(root);
B.enhance();
})();
