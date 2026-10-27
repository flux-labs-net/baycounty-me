window.BCM_CITIES=[{"k":"county","s":"Bay County","slug":"bay-county","kind":"county","cra":"","al":["bay","bay county","bay county board","bay county board of county commissioners","bay county clerk of court","bay county clerk of court and comptroller","bay county commission","bay county general","bay county per dor classification","bay county property appraiser","bay county sheriff s office","bay county supervisor of elections","bay county tax collector","bay county utility services","clerk","clerk of circuit court and comptroller","clerk of court","county","county fire mstu","county fire service","county mosquito control","county planning","destination panama city","destination panama city cdc","destination pc","mb cdc","mexico beach cdc","mexico beach community development council","mexico beach community development council bay county tdc","panama city beach convention and visitors bureau","panama city beach convention and visitors bureau bay county tdc","panama city beach convention and visitors bureau inc","panama city beach cvb fy2026 budget","panama city community development council","panama city community development council bay county tdc","property appraiser","sheriff","soe","supervisor of elections","tax collector","visit panama city beach","visit pcb","visit pcb cvb"]},{"k":"schools","s":"Bay District Schools","slug":"bay-district-schools","kind":"schools","cra":"","al":["bay county district school board","bay district school board","bay district schools","bds board","school board","school board of bay county","school board of bay county florida","school capital outlay","school discretionary","school rle","schools","schools buildings and buses","schools local operating","schools state required rate","superintendent of schools"]},{"k":"pc","s":"Panama City","slug":"panama-city","kind":"city","cra":"pc","al":["city panama city","downtown improvement board","panama city","panama city community redevelopment agency","panama city community redevelopment agency board","panama city cra","panama city downtown improvement board","panama city port authority","panama city port authority dependent special district component unit of city of panama city","panama city primary","pc","pc commission","pc cra","pc downtown improvement board","port","port authority"]},{"k":"pcb","s":"Panama City Beach","slug":"panama-city-beach","kind":"city","cra":"pcb","al":["city panama city beach","front beach cra","front beach road cra","panama city beach","panama city beach community redevelopment agency","panama city beach cra","pcb","pcb council","pier park cra"]},{"k":"lh","s":"Lynn Haven","slug":"lynn-haven","kind":"city","cra":"lh","al":["city lynn haven","lh","lh commission","lh cra","lynn haven","lynn haven city commission","lynn haven community redevelopment agency","lynn haven cra"]},{"k":"cw","s":"Callaway","slug":"callaway","kind":"city","cra":"cw","al":["callaway","callaway community redevelopment agency","callaway cra","city callaway","cw","cw commission","cw cra"]},{"k":"sp","s":"Springfield","slug":"springfield","kind":"city","cra":"sf","al":["city springfield","sf","sp","sp commission","springfield","springfield community redevelopment agency","springfield cra"]},{"k":"parker","s":"Parker","slug":"parker","kind":"city","cra":"pk","al":["city parker","parker","parker community redevelopment agency","parker council","parker cra","pk"]},{"k":"mb","s":"Mexico Beach","slug":"mexico-beach","kind":"city","cra":"","al":["city mexico beach","mb","mb council","mexico beach"]}];
// Display casing for names that arrive in all caps (Sunbiz, check registers, IRS filings, the elections office).
// The same rules as data/entities/ids.py biz_case and person_case, so a name reads the same in the build, the API and
// the page scripts. api/__tests__/names.test.js checks the two agree on every name in the published entity list.
// Display only: matching keys and stored records keep the name as filed.
// Loaded by the API (require) and bundled into /assets/site.js (window.BCNames, BC.bizCase, BC.personCase, BC.nameCase).
(function (root) {
  const set = s => new Set(s.split(' '));
  const UPPER_KEEP = set('LLC LLP LP PA PLLC PC NA USA US FL II III IV ADP AT&T FPL CSX UPS HVAC AC TV FM AM DBA GIS IT PCB PCBH EMR EMS RV ' +
    'ACH CPA PE DDA PMT ECSC CRI MWB USFA WSL EPCI EJHG FTS NCMC JDF RDK CK JS&S PBS&J YMCA YWCA NAACP AARP PTA PTO VFW CDC CRA FSU UWF ' +
    'GCSC TDC FDOT FEMA HUD');
  const LOWER = set('and of the for in on at to by a an or de');
  const WORDS3 = set('bay sea oak sun pro air one new top ace all big red car art law lab dog day way old gas oil ice tax box van bus cab fix ' +
    'net web map pet eye joe bob tom jim ann sam dan ray lee kim fun hot joy key max mix now own pay run sky tee toy two six ' +
    'ten bar inn spa tan tin mr dr st mt ft go my we me so up oh hi ma');
  const FIXED = {INC: 'Inc', CO: 'Co', CORP: 'Corp', LTD: 'Ltd', MGM: 'Mgmt', MGMT: 'Mgmt', SVCS: 'Svcs', AMEX: 'Amex', VISA: 'Visa',
    MCDONALD: 'McDonald', MCKIM: 'McKim', MCMAHON: 'McMahon'};
  const NAME_UPPER = set('II III IV VI VII VIII MD DDS DMD DVM CPA ESQ PA PE RN USN USAF USMC JD LCSW CFP MBA APRN ARNP CRNA LPN BSN MSN ' +
    'DNP FNP MPH MSW MSA MHA LMHC LMFT AIA CFA CLU CHFC CPCU CCIM GRI PMP SPHR CFRE FACS FACP RPH AICP LEED CGC CBC CPM CMA EA USA USCG');
  const TITLED_CRED = set('MD DDS DMD DVM CPA ESQ APRN ARNP CRNA LCSW LMHC LMFT MBA MPH MSW JD RN');
  const NAME_UPPER_LATE = set('DO OD DC NP MA MS BS PT OT');
  const NAME_FIXED = {JR: 'Jr', SR: 'Sr', PHD: 'PhD', EDD: 'EdD', PSYD: 'PsyD', PHARMD: 'PharmD', DMIN: 'DMin', RET: 'Ret', MR: 'Mr', MRS: 'Mrs', DR: 'Dr'};
  const MAC = set('macdonald macdougall macgregor mackenzie mackinnon mackay maclean macleod macmillan macneil macpherson macarthur ' +
    'macaulay macfarlane macintosh macinnis macrae macqueen maclaren macintyre maclachlan macnamara macdonell maccallum mackintosh macivor');

  const cap = s => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  const replaceAll = (s, a, b) => s.split(a).join(b);
  const isUpper = s => /[A-Za-z]/.test(s) && s === s.toUpperCase();
  const isLower = s => /[A-Za-z]/.test(s) && s === s.toLowerCase();

  function namePiece(p) {
    const lo = p.toLowerCase();
    if (lo.length > 2 && lo.startsWith('mc')) return 'Mc' + cap(lo.slice(2));
    if (MAC.has(lo)) return 'Mac' + cap(lo.slice(3));
    return cap(lo);
  }

  function caseWord(w, first) {
    if (/^[WK][A-Z]{2,3}-(TV|FM|AM),?$/.test(w)) return w;  // call signs: WJHG-TV
    const core = w.replace(/[^A-Za-z&]/g, ''), up = core.toUpperCase();
    if (!core) return w;
    if (up in FIXED) return replaceAll(w, core, FIXED[up]);
    if (/^\d+(ST|ND|RD|TH)(\W*)$/.test(w)) return w.toLowerCase();  // ordinals: 1ST -> 1st
    if (UPPER_KEEP.has(up) || core.includes('&') || /\d/.test(w)) return w;
    if (!first && LOWER.has(core.toLowerCase())) return w.toLowerCase();
    if (core.length <= 3 && !WORDS3.has(core.toLowerCase())) return w;  // short initials: CW, RJ, GAC
    return w.replace(/[A-Za-z]+/g, namePiece).replace(/'S\b/g, "'s");
  }

  /** 'BALDWIN CONTAINER SYSTEMS INC' -> 'Baldwin Container Systems Inc'. Names with lower-case letters are left alone. */
  function bizCase(name) {
    if (typeof name !== 'string' || !name || /[a-z]/.test(name) || !/[A-Z]/.test(name)) return name;
    const words = name.split(' ');
    if (words.length === 1 && name.replace(/[^A-Z]/g, '').length <= 4) return FIXED[name] || name;  // a lone acronym
    return words.map((w, i) => caseWord(w, i === 0)).join(' ');
  }

  function nameWord(w, first, afterComma) {
    const core = w.replace(/[^A-Za-z]/g, ''), up = core.toUpperCase();
    if (!core) return w;
    if (core.length === 1) return w.toUpperCase();  // an initial
    if (NAME_UPPER_LATE.has(up) && afterComma) return w.replace(new RegExp(core, 'gi'), up);
    if (up === 'MS' && first) return replaceAll(w, core, 'Ms');
    if (up in NAME_FIXED) return replaceAll(w, core, NAME_FIXED[up]);
    if (NAME_UPPER.has(up) && !first) return w.replace(new RegExp(core, 'gi'), up);
    return w.replace(/[A-Za-z]+/g, namePiece).replace(/(?<=[a-z])'S\b/g, "'s");
  }

  /** 'JOHN A MCDANIEL III' -> 'John A McDaniel III'. Mixed-case names keep their casing, apart from words in caps and
      the slips a plain title-casing leaves ('Mcdaniel', 'Iii', "O'neal"). */
  function personCase(name) {
    if (typeof name !== 'string' || !/[A-Za-z]/.test(name)) return name;
    let s = name.replace(/\s+/g, ' ').trim();
    const words = s.split(' '), n = words.length;
    const prev = i => words[(i - 1 + n) % n];
    if (isUpper(s) || isLower(s)) return words.map((w, i) => nameWord(w, i === 0, i > 0 && prev(i).endsWith(','))).join(' ');
    s = words.map((w, i) => /[A-Z]{3}/.test(w) ? nameWord(w, i === 0, prev(i).endsWith(',')) : w).join(' ');
    const count = s.split(' ').filter(Boolean).length;
    s = s.replace(/(?<=\S )([A-Z][a-z]{1,4})\b(\.?)$/, (m, a, b) => TITLED_CRED.has(a.toUpperCase()) && count >= 3 ? a.toUpperCase() + b : m);
    s = s.replace(/\bMc([a-z])/g, (m, a) => 'Mc' + a.toUpperCase());
    s = s.replace(/\b(O|D)'([a-z])/g, (m, a, b) => a + "'" + b.toUpperCase());
    return s.replace(/(?<=\s)(Ii|Iii|Iv)\b/g, m => m.toUpperCase());
  }

  // People (officials, candidates, board members, owners) get name casing; everything else business casing.
  const PEOPLE = new Set(['person', 'member', 'owner', 'candidate', 'official']);
  const nameCase = (name, kind) => PEOPLE.has(String(kind || '').split(':')[0]) ? personCase(name) : bizCase(name);

  const api = {bizCase, personCase, nameCase};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.BCNames = api;
})(typeof window !== 'undefined' ? window : this);

window.BC = Object.assign(window.BC || {}, window.BCNames);
(() => {
  const root = document.documentElement, tb = document.getElementById('themeBtn');
  const I = window.BCM_I18N || {}, NAMES = I.theme || {system: 'System', light: 'Light', dark: 'Dark'}, NEXT = {system: 'light', light: 'dark', dark: 'system'};
  const current = () => root.getAttribute('data-theme') || 'system';
  const show = m => { tb.dataset.mode = m; tb.querySelector('.theme-lbl').textContent = NAMES[m]; tb.setAttribute('aria-label', (I.themeLabel || 'Theme: ') + (m === 'system' ? I.themeSystem || 'match system' : NAMES[m].toLowerCase()) + (I.themeClick || '. Click to change.')); };
  show(current());
  tb.addEventListener('click', () => {
    const m = NEXT[current()];
    if (m === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', m);
    try { if (m === 'system') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    show(m);
  });
  const btn = document.querySelector('.menu-btn'), menu = document.getElementById('site-menu');
  const setMenu = o => { btn.setAttribute('aria-expanded', o); menu.classList.toggle('open', o); document.documentElement.classList.toggle('nav-locked', o); if (o) menu.scrollTop = 0;
    // phone menu: open on the section that holds this page
    const here = o && menu.querySelector('.has-sub.on > .sub-toggle'); if (here && !menu.querySelector('.sub-toggle[aria-expanded="true"]')) here.setAttribute('aria-expanded', 'true'); };
  btn.addEventListener('click', () => setMenu(btn.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', e => { if (e.target.closest('a')) setMenu(false); });
  const mq = matchMedia('(min-width:981px)'), onMq = e => { if (e.matches) setMenu(false); };
  if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  document.querySelectorAll('.sub-toggle').forEach(t => t.addEventListener('click', e => {
    e.stopPropagation(); const o = t.getAttribute('aria-expanded') === 'true';
    document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false'));
    t.setAttribute('aria-expanded', !o); }));
  // Line each mega menu up under its own button, nudged left only if it would run off the right edge.
  const placeMega = li => { const m = li.querySelector('.nav-mega'); if (!m || innerWidth <= 980) return;
    const l = li.getBoundingClientRect().left, w = Math.min(760, innerWidth - 32);
    m.style.setProperty('--mx', Math.max(16 - l, Math.min(0, innerWidth - 16 - w - l)) + 'px'); };
  document.querySelectorAll('.has-sub').forEach(li => ['mouseenter', 'focusin', 'click'].forEach(ev => li.addEventListener(ev, () => placeMega(li))));
  document.addEventListener('click', e => { if (!e.target.closest('.has-sub, .menu-btn')) document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); if (menu.classList.contains('open')) { setMenu(false); btn.focus(); } } });
})();
// Site search: one engine (window.BCSearch) used by the /search page and the full-screen search dialog that the
// header's search icon opens on every page. The index comes in pieces: core.json (pages, sections, glossary) first,
// then page text and each dataset, so the first results show quickly and refresh as the rest lands.
window.BCSearch = window.BCSearch || (() => {
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const norm = s => String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');
  const W = {Page: 6, Section: 4, Glossary: 5};
  const prep = r => ({...r, _t: norm(r.t), _s: norm(r.s), _x: norm(r.x)});
  const subs = new Set();
  let IDX = null, coreP = null, pending = 0;
  function load() {
    if (coreP) return coreP;
    coreP = fetch('/data/search/core.json').then(r => r.json()).then(c => {
      const core = c.rows.map(prep), parts = c.parts.map(() => []);
      const rebuild = () => { IDX = core.concat(...parts); };
      rebuild(); pending = c.parts.length + 1;
      const done = () => { pending--; rebuild(); subs.forEach(f => f()); };
      fetch('/data/search/text.json').then(r => r.json()).then(tx => { let i = 0; core.forEach(r => { if (r.k === 'Page') { r.x = tx[i++] || ''; r._x = norm(r.x); } }); }).catch(() => {}).finally(done);
      c.parts.forEach((n, i) => fetch('/data/search/' + n + '.json').then(r => r.json()).then(p => { parts[i] = p.k ? p.rows.map(([t, s, u]) => prep({k: p.k, t, s, u})) : p.rows.map(prep); }).catch(() => {}).finally(done));
      return IDX;
    });
    return coreP;
  }
  // Every row that has all the words, best first: [score, row].
  function query(q) {
    const words = norm(q).split(/\s+/).filter(Boolean), hits = [];
    if (!words.length || !IDX) return {words, hits};
    for (const r of IDX) {
      let sc = 0, ok = true;
      for (const w of words) { const it = r._t.indexOf(w), is = r._s.indexOf(w), ix = r._x ? r._x.indexOf(w) : -1; if (it < 0 && is < 0 && ix < 0) { ok = false; break; } sc += it >= 0 ? (it === 0 ? 4 : 3) : is >= 0 ? 1 : 0.5; }
      if (ok) hits.push([sc + (W[r.k] || 0), r]);
    }
    hits.sort((a, b) => b[0] - a[0]);
    return {words, hits};
  }
  function hl(s, words) { let h = esc(s); words.forEach(w => { if (w.length > 1) h = h.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig'), '<mark>$1</mark>'); }); return h; }
  return {load, query, hl, esc, norm, pending: () => pending, onUpdate: f => subs.add(f)};
})();

(() => {
  const dlg = document.getElementById('sx');
  if (!dlg) return;
  const S = window.BCSearch, I = (window.BCM_I18N || {}).search || {};
  const inp = document.getElementById('sxq'), res = document.getElementById('sxr'), cnt = document.getElementById('sxn'), empty = document.getElementById('sxe');
  const GROUP = {Person: 'People', Vendor: 'Companies', Glossary: 'Glossary', Section: 'Page sections'};
  const groupName = k => (I.groups || {})[k] || GROUP[k] || k + 's';
  let last = null, t;
  const open = () => {
    if (!dlg.hidden) return;
    last = document.activeElement; dlg.hidden = false;
    document.documentElement.classList.add('sx-open');
    S.load(); inp.focus(); inp.select();
  };
  const close = () => {
    if (dlg.hidden) return;
    dlg.hidden = true; document.documentElement.classList.remove('sx-open');
    if (last && last.focus) last.focus();
  };
  function run() {
    const q = inp.value.trim();
    empty.hidden = !!q;
    if (!q) { res.innerHTML = ''; cnt.textContent = ''; return; }
    const {words, hits} = S.query(q), pend = S.pending();
    // Group by kind; the group with the best hit comes first. Four per group, six groups.
    const groups = new Map();
    for (const [, r] of hits) { if (!groups.has(r.k)) groups.set(r.k, []); groups.get(r.k).push(r); }
    const all = `/search?q=${encodeURIComponent(q)}`;
    cnt.textContent = hits.length ? `${hits.length.toLocaleString()} ${hits.length === 1 ? (I.result || 'result') : (I.results || 'results')}` + (pend ? ` · ${I.loading || 'still loading records…'}` : '')
      : pend ? (I.loadingNone || 'Loading records…') : (I.none || 'No results. Try fewer or different words.');
    res.innerHTML = [...groups].slice(0, 6).map(([k, rows]) => `<section class="sx-g"><h2>${S.esc(groupName(k))}</h2><ul>` +
      rows.slice(0, 4).map(r => `<li><a href="${S.esc(r.u)}"><b>${S.hl(r.t, words)}</b><span>${S.hl(r.s, words)}</span></a></li>`).join('') + '</ul></section>').join('') +
      (hits.length ? `<a class="sx-all" href="${all}">${I.all || 'See all results'} →</a>` : '');
  }
  S.onUpdate(() => { if (!dlg.hidden && inp.value.trim()) run(); });
  inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(run, 120); });
  inp.addEventListener('keydown', e => {
    if (e.key === 'Enter') { const a = res.querySelector('a'); if (a) { e.preventDefault(); location.href = a.href; } }
    if (e.key === 'ArrowDown') { const f = res.querySelector('a') || (!empty.hidden && empty.querySelector('a')); if (f) { e.preventDefault(); f.focus(); } }
  });
  // Arrow keys move through results; Tab stays inside the dialog.
  dlg.addEventListener('keydown', e => {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    const links = [...dlg.querySelectorAll('.sx-body a')].filter(a => a.offsetParent);
    const i = links.indexOf(document.activeElement);
    if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && i >= 0) {
      e.preventDefault();
      const n = i + (e.key === 'ArrowDown' ? 1 : -1);
      (n < 0 ? inp : links[Math.min(n, links.length - 1)]).focus();
    }
    if (e.key === 'Tab') {
      const f = [...dlg.querySelectorAll('button, input, a')].filter(x => x.offsetParent);
      if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
      else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    }
  });
  dlg.querySelector('.sx-x').addEventListener('click', close);
  // The header icon is a link to /search; with scripts on it opens the dialog instead (on /search it focuses the page's box).
  const start = () => { const page = document.getElementById('sq'); if (page) page.focus(); else open(); };
  document.querySelectorAll('.search-btn').forEach(b => b.addEventListener('click', e => { e.preventDefault(); start(); }));
  document.addEventListener('keydown', e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
    if ((e.key === 'k' && (e.ctrlKey || e.metaKey)) || (e.key === '/' && !typing)) {
      e.preventDefault(); start();
    }
  });
})();
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

/* Phone tables: no sideways scrolling. Each body cell gets data-label (its column heading) and the table gets
   class "stk"; site.css turns rows into cards under 640px. Opt out with <table data-stack="off">. */
(() => {
  const colsOf = tr => { const out = []; for (const c of tr.cells) { const n = Math.max(1, c.colSpan || 1); out.push(c); for (let i = 1; i < n; i++) out.push(null); } return out; };
  const label = t => {
    if (t.dataset.stack === 'off' || t.closest('[data-stack="off"]')) return;
    const h = t.tHead && t.tHead.rows.length ? t.tHead.rows[t.tHead.rows.length - 1] : null;
    const names = h ? colsOf(h).map(c => c ? c.textContent.replace(/\s+/g, ' ').trim() : '') : (t.dataset.cols || '').split('|');
    let n = names.length; for (const b of t.tBodies) for (const r of b.rows) n = Math.max(n, colsOf(r).length);
    if (n < 3) { t.classList.add('stk2'); return; }   // two columns fit a phone once they may wrap
    t.classList.add('stk');
    for (const part of [...t.tBodies, t.tFoot].filter(Boolean)) for (const tr of part.rows) {
      const cs = colsOf(tr);
      if (tr.cells.length === 1 && (tr.cells[0].colSpan || 1) > 1) { tr.classList.add('stk-span'); continue; }
      cs.forEach((c, i) => { if (c && !c.hasAttribute('data-label') && names[i]) c.setAttribute('data-label', names[i]); });
      // phones put short values two to a line; long text, lists of links and the first cell keep the full width
      for (const c of tr.cells) if (c !== tr.cells[0] && (c.textContent.trim().length > 32 || c.querySelectorAll('a').length > 1)) c.classList.add('stk-w');
    }
    t.classList.add('stk-g');
  };
  let q = false;
  const run = () => { q = false; document.querySelectorAll('table').forEach(label); };
  const go = () => { run(); new MutationObserver(ms => { if (q) return; if (ms.some(m => m.addedNodes.length)) { q = true; requestAnimationFrame(run); } }).observe(document.body, {childList: true, subtree: true}); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();

/* Shared page pieces (ui.css, ui.py). The compact section bar: shows once the section tiles have scrolled away,
   and marks the section in view. */
(() => {
const go = () => {
  const mini = document.querySelector('.ui-mini'), tiles = document.querySelector('.ui-tiles');
  if (!mini || !tiles) return;
  const top = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--head-h')) || 57;
  new IntersectionObserver(([en]) => { if (en.isIntersecting) mini.setAttribute('data-off', ''); else if (en.boundingClientRect.top < 0) mini.removeAttribute('data-off'); },
    {rootMargin: `-${top}px 0px 0px 0px`}).observe(tiles);
  const links = [...mini.querySelectorAll('a')];
  const io = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) {
    const id = en.target.id || en.target.querySelector('h2[id]')?.id;
    links.forEach(a => a.classList.toggle('on', a.getAttribute('href') === '#' + id)); } }), {rootMargin: '-35% 0px -60% 0px'});
  links.forEach(a => { const t = document.getElementById(a.getAttribute('href').slice(1)); const sec = t && (t.closest('section') || t); if (sec) io.observe(sec); });
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();
/* Directories (ui.directory): search box, government filter, sort, chips and CSV over a grid of cards. */
(() => {
const go = () => document.querySelectorAll('[data-ui-dir]').forEach(grid => {
  const root = grid.closest('section') || grid.parentNode;
  const q = root.querySelector('[data-dir-q]'), g = root.querySelector('[data-dir-g]'), s = root.querySelector('[data-dir-s]');
  const chips = [...root.querySelectorAll('.ui-chip[data-k]')], count = root.querySelector('[data-dir-count]'), none = root.querySelector('[data-dir-none]');
  const cards = [...grid.children];
  let kind = '';
  const words = t => (t || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').split(/\s+/).filter(Boolean);
  const run = () => {
    const w = words(q && q.value), gv = g ? g.value : '';
    cards.forEach(c => {
      const ok = w.every(x => (c.dataset.s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').includes(x))
        && (!kind || (' ' + c.dataset.k + ' ').includes(' ' + kind + ' ')) && (!gv || (' ' + c.dataset.gv + ' ').includes(' ' + gv + ' '));
      c.classList.toggle('ui-off', !ok);
    });
    const by = s ? s.value : 'c';
    cards.slice().sort((a, b) => by === 'name' ? a.dataset.n.localeCompare(b.dataset.n) : by === 'az' ? a.dataset.n.split(' ').pop().localeCompare(b.dataset.n.split(' ').pop()) || a.dataset.n.localeCompare(b.dataset.n)
      : (+b.dataset.c - +a.dataset.c) || a.dataset.n.localeCompare(b.dataset.n)).forEach(c => grid.appendChild(c));
    count_();
  };
  const count_ = () => {
    const n = cards.filter(c => !c.hidden && !c.classList.contains('ui-off')).length;
    if (count) count.textContent = n === cards.length ? `${cards.length.toLocaleString('en-US')} shown` : `${n.toLocaleString('en-US')} of ${cards.length.toLocaleString('en-US')} shown`;
    if (none) none.hidden = n > 0;
  };
  chips.forEach(b => b.addEventListener('click', () => { kind = b.dataset.k; chips.forEach(x => x.setAttribute('aria-pressed', x === b)); run(); }));
  [q, g, s].forEach(el => el && el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', run));
  const csvBtn = root.querySelector('[data-dir-csv]');
  if (csvBtn) csvBtn.addEventListener('click', () => {
    const rows = cards.filter(c => !c.hidden && !c.classList.contains('ui-off')).map(c => { const a = c.querySelector('.ui-dc-a'); return [a.textContent.trim(), (c.querySelector('small') || {}).textContent || '', ((c.querySelector('.ui-dc-w') || {}).textContent || '').trim(), c.dataset.c, a.href]; });
    if (window.TT) window.TT.csv(csvBtn.dataset.dirCsv, csvBtn.dataset.head.split(','), rows);
  });
  new MutationObserver(count_).observe(grid, {subtree: true, attributes: true, attributeFilter: ['hidden']});  // the government bar hides cards too
  run();
});
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();
/* Site-wide data notice (ui.data_notice): the close button hides it in this browser until NOTE_KEY changes. */
(function () {
const go = () => {
  const n = document.getElementById('dataNote');
  const x = n && n.querySelector('.data-note-x');
  if (!x) return;
  x.addEventListener('click', () => { n.hidden = true; try { localStorage.setItem('bcm-note', n.dataset.key); } catch (e) {} });
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();

(() => {
  const URLRE = /https?:\/\/[^\s<>"']+/g, SKIP = new Set(['A','SCRIPT','STYLE','TEXTAREA','TITLE','OPTION','INPUT','SELECT','CODE','PRE']);
  const PATHS = [[/data\/contracts\/contracts\.json/g, '/public-money/contracts', 'the Contracts page'], [/data\/tax\/budgets\.json/g, '/public-money/tax-dollars', 'the Tax Dollars page'],
    [/data\/votes\/votes\.json/g, '/public-money/votes', 'the How They Voted page'], [/data\/campaign\/[a-z_]+\.json/g, '/connections/campaign-gifts', 'the Campaign Gifts page'],
    [/data\/[a-z_]+\/[a-z_0-9]+\.(?:json|csv)/g, '/open-data', "this site's open data"]];
  const host = u => u.replace(/^https?:\/\/(www\.)?/, '').split(/[/?#]/)[0] || 'source';
  function fix(node) {
    const t = node.nodeValue; if (!t || (t.indexOf('http') < 0 && t.indexOf('data/') < 0)) return;
    const marks = [];
    let m; URLRE.lastIndex = 0;
    while ((m = URLRE.exec(t))) { let u = m[0]; while (/[.,;:!?)\]}'"]$/.test(u) && !(u.endsWith(')') && (u.match(/\(/g) || []).length > (u.match(/\)/g) || []).length - 1)) u = u.slice(0, -1); marks.push([m.index, m.index + u.length, u, host(u), true]); }
    PATHS.forEach(([re, href, lbl]) => { re.lastIndex = 0; let p; while ((p = re.exec(t))) if (!marks.some(k => p.index < k[1] && p.index + p[0].length > k[0])) marks.push([p.index, p.index + p[0].length, href, lbl, false]); });
    if (!marks.length) return;
    marks.sort((a, b) => a[0] - b[0]);
    const frag = document.createDocumentFragment(); let i = 0;
    marks.forEach(([s, e, href, lbl, ext]) => { if (s < i) return; frag.appendChild(document.createTextNode(t.slice(i, s))); const a = document.createElement('a'); a.href = href; a.textContent = lbl; if (ext) { a.className = 'src'; a.target = '_blank'; a.rel = 'noopener'; } frag.appendChild(a); i = e; });
    frag.appendChild(document.createTextNode(t.slice(i)));
    node.parentNode.replaceChild(frag, node);
  }
  function walk(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: n => { for (let p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || p.nodeName === 'svg' || (p.hasAttribute && p.hasAttribute('data-nolinkify'))) return NodeFilter.FILTER_REJECT; return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode); list.forEach(fix);
  }
  const main = document.getElementById('main'); if (!main) return;
  walk(main);
  let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => walk(main), 60); }).observe(main, {childList: true, subtree: true});
})();

(() => {
  const R = {"gov":{"county":"bay-county","schools":"bay-district-schools","pc":"panama-city","pcb":"panama-city-beach","lh":"lynn-haven","cw":"callaway","sp":"springfield","parker":"parker","mb":"mexico-beach"},"vp":["814-sand","850-construction","a-c-schultes-florida","aaron-rich-marketing","abentras","accurate-drilling-systems","action-truck-center","ajr-publishing","alan-jay-automotive-management-alan-jay-fleet-sales","american-sand","anderson-columbia","anderson-construction","annett-bus-lines","arris","arrivalist","art-construction-northwest-florida","barge","bay-county-chamber-commerce","bay-point-billfish","bayou-builders","bcl","beard-equipment","behar-peteranecz","bgn","black-veatch","brock-lawn-pest-control","burke-blue","burke-construction-group","carollo-engineers","carr-riggs-ingram","carvertise","cbc","cdr-maguire","charles-white","charlie-coram-s-place","coast-2-coast-printing","coastal-parasail","coastal-protection-engineering","construction-services","core-main","cri","crowdriff","culpepper","cw-roberts","cwr-contracting","dag-architects","davison","destinations-florida","destinations-international","dewberry","disposal-services","dominguez-design-build","ecsc","empire-pipe","emr","energreen-ameri","first-transit","flc","florida-architects","florida-blue-blue-cross-blue-shield-florida","fpl","gac-contractors","gcuc","gortemoller","grand-slam-sports-tournaments","greensouth-solu","gts-entertainment-group","gypsy-belle-photo-bus","hagerty-consulting","halff","hall-contracting","harders","historic-st-andrews-waterfront-partnership","hmx-productions","hutt-insurance-agency","hydra","iheart-media","imageworks","infrastructure-solution-services","ingram-signalization","inland","j-v-gander-distributors","jbj-productions","kemira-water-solutions","l-r-contracting","lamar-companies","lawnscapes","lawnscapes-bay-county","leake-landscapes","madden-media","magnum-engineering","mainline","marsh-usa","marshall-brothers","metric","miles-partnership","mott-macdonald","mr-fence","ncmc","ovivo","panache-tent-event","panama-city-beach-chamber-commerce","panama-city-symphony-orchestra","panhandle-engineering","pcb-entertainment","pcb-map","pg-environmental-fl","pgit","phoenix","pineapple-public-relations","piney-grove-nursery-landscaping","press-print-graphics","public-risk-mgm","pyro-shows","quillian-powell","rategain-adara","razorback","reeves-shaw","regions-bank","reliantsouth","rj-gorman-contracting","rj-gorman-marine","roberts-and-roberts","rotolo-consultants","royal-american","sam-s-club","sj-electro","southeast-tourism-society","southeastern-outdoor","southern-construction","staline-waterworks","styleblueprint","sunbelt-rentals","tb-landmark","telemetry","ten-8","tetra-tech","timmins-consulting","tk-vandy","travelscape","us-relay","visit-florida","volkert","waste-pro","weeks-marine","williams-communications","wjhg-tv","wmbb","world-changers-first-baptist-church-panama-city"]}, VP = new Set(R.vp);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  // the profile URL for an entity id: same rule as site/entity_graph.py page_url()
  function href(id) {
    const i = String(id || '').indexOf(':'); if (i < 0) return null;
    const k = id.slice(0, i), v = id.slice(i + 1);
    if (k === 'gov' && R.gov[v]) return '/governments/' + R.gov[v];
    if (k === 'vendor' && VP.has(v)) return '/public-money/vendors/' + v;
    if (k === 'person') return '/people/' + encodeURIComponent(v);
    return '/profile/' + k + '/' + encodeURIComponent(v);
  }
  const a = (id, text, cls) => {  // names filed in all caps read as names (api/_names.js), as entity_links.a() does at build
    const u = href(id), t = window.BCNames ? BCNames.nameCase(text, id) : text;
    return u ? `<a${cls ? ` class="${cls}"` : ''} href="${esc(u)}">${esc(t)}</a>` : esc(t);
  };
  window.BC = Object.assign(window.BC || {}, {href, a});
  // names in text that page scripts fill in: same rules as entity_links.link_names()
  const main = document.getElementById('main'); if (!main || document.documentElement.lang.startsWith('es')) return;
  const noPeople = /^\/(connections\/nonprofits|profile\/)/.test(location.pathname);
  const SKIP = new Set(['A', 'SCRIPT', 'STYLE', 'TEXTAREA', 'TITLE', 'OPTION', 'INPUT', 'SELECT', 'CODE', 'PRE', 'BUTTON', 'LABEL', 'H1', 'NAV', 'SUMMARY', 'svg']);
  const SMALL = new Set(['of', 'and', 'the', 'for', 'in', 'on', 'at', 'to', 'by', 'a', 'an', 'or', 'de', '&']);
  const proper = s => { const ws = s.match(/[A-Za-z0-9&][A-Za-z0-9&'’.-]*/g) || []; return ws.length > 0 && /^[A-Z0-9]/.test(ws[0]) && ws.every(w => /^[A-Z0-9]/.test(w) || SMALL.has(w.toLowerCase())); };
  const WORD = /[A-Za-z0-9&][A-Za-z0-9&'’.-]*/g, norm = s => (s.match(WORD) || []).map(w => w.toLowerCase().replace(/’/g, "'").replace(/^[.'-]+|[.'-]+$/g, '')).filter(Boolean).join(' ');
  let N = null, busy = false; const done = new WeakSet();
  function fix(node) {
    const t = node.nodeValue; if (!t || t.length < 6) return;
    const ws = []; let m; WORD.lastIndex = 0; while ((m = WORD.exec(t))) ws.push([m.index, m.index + m[0].length]);
    const frag = []; let i = 0, last = 0;
    while (i < ws.length) {
      let hit = 0, id = -1;
      for (let L = Math.min(N.max, ws.length - i); L > 0; L--) {
        const seg = t.slice(ws[i][0], ws[i + L - 1][1]); if (!proper(seg)) continue; const x = N.n[norm(seg)];
        if (x !== undefined && !(noPeople && N.k[x] === 'person')) { hit = L; id = x; break; }
      }
      if (hit && N.u[id] === location.pathname) { i += hit; continue; }  // this page's own name: skip it whole
      if (hit) { let s = ws[i][0], e = ws[i + hit - 1][1]; while (e > s && ".'’-".includes(t[e - 1])) e--; frag.push([last, s, e, id]); last = e; i += hit; } else i++;
    }
    if (!frag.length) return;
    const f = document.createDocumentFragment(); let p = 0;
    frag.forEach(([l, s, e, id]) => { f.appendChild(document.createTextNode(t.slice(p, s))); const el = document.createElement('a'); el.className = 'ent'; el.href = N.u[id]; el.textContent = t.slice(s, e); f.appendChild(el); p = e; });
    f.appendChild(document.createTextNode(t.slice(p)));
    f.childNodes.forEach(c => done.add(c.nodeType === 3 ? c : c.firstChild));
    node.parentNode.replaceChild(f, node);
  }
  function walk() {
    if (!N || busy) return; busy = true;
    const w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {acceptNode: n => {
      if (done.has(n)) return NodeFilter.FILTER_REJECT;
      for (let p = n.parentNode; p && p !== main.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || (p.hasAttribute && p.hasAttribute('data-nolink'))) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode);
    list.forEach(n => { done.add(n); fix(n); });
    busy = false;
  }
  const start = () => fetch('/data/entity-names.json').then(r => r.ok ? r.json() : null).then(d => { N = d; walk(); let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(walk, 120); }).observe(main, {childList: true, subtree: true}); }).catch(() => {});
  if ('requestIdleCallback' in window) requestIdleCallback(start, {timeout: 2500}); else setTimeout(start, 400);
})();

// A clear flag for a business the state lists as inactive (dissolved, revoked or no longer filing). Active returns ''.
window.BCM_bizOff = (status, lastYear) => {
  const s = String(status || '').trim();
  if (!s || /^(a|active)$/i.test(s)) return '';
  const tip = 'Inactive in Florida corporate records (Sunbiz): dissolved, revoked or no longer filing annual reports' + (lastYear ? `. Last filed ${lastYear}.` : '.');
  return `<span class="biz-off" title="${tip}">Inactive${lastYear ? ' since ' + lastYear : ''}</span>`;
};
(() => {
  const ES = (document.documentElement.lang || '').startsWith('es');
  const EN_M = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], ES_M = ['ene','feb','mar','abr','may','jun','jul','ago','sept','oct','nov','dic'];
  const SKIP = new Set(['SCRIPT','STYLE','TEXTAREA','TITLE','OPTION','INPUT','SELECT','CODE','PRE']);
  const ISO = /(^|[^\w\/.-])((?:19|20)\d\d)-(\d\d)-(\d\d)(?:[ T](\d\d):(\d\d)(?::\d\d)?)?(?![\w\/-])/g;
  const MDY = /(^|[^\w\/.-])(\d{1,2})\/(\d{1,2})\/((?:19|20)\d\d)(?![\w\/-])/g;
  function fmt(y, m, d, hh, mm) {
    y = +y; m = +m; d = +d;
    if (!(m >= 1 && m <= 12 && d >= 1 && d <= 31)) return null;
    let s = ES ? `${d} ${ES_M[m - 1]} ${y}` : `${EN_M[m - 1]} ${d}, ${y}`;
    if (hh != null && !(+hh === 0 && +mm === 0)) { const h = +hh; s += ES ? `, ${h}:${mm}` : `, ${(h % 12) || 12}:${mm} ${h < 12 ? 'AM' : 'PM'}`; }
    return s;
  }
  const usDate = window.BCM_usDate = t => String(t ?? '').replace(ISO, (all, pre, y, m, d, hh, mm) => { const f = fmt(y, m, d, hh, mm); return f ? pre + f : all; })
    .replace(MDY, (all, pre, m, d, y) => { const f = fmt(y, m, d); return f ? pre + f : all; });
  function walk(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: n => { for (let p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || p.nodeName === 'svg' || p.isContentEditable) return NodeFilter.FILTER_REJECT; return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode);
    list.forEach(n => { const t = n.nodeValue; if (t && /\d[-\/]\d/.test(t)) { const u = usDate(t); if (u !== t) n.nodeValue = u; } });
  }
  const main = document.getElementById('main'); if (!main) return;
  walk(main);
  let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => walk(main), 60); }).observe(main, {childList: true, subtree: true});
})();

(() => {
  const ES = document.documentElement.lang === 'es', G = ES ? {"cra": {"term": "Agencia de Reurbanización Comunitaria (Community Redevelopment Agency, CRA)", "simple": "Una alcancía para un vecindario que necesita mejoras. Cuando las propiedades del vecindario aumentan de valor, el dinero adicional de impuestos va a la alcancía, y solo se puede gastar en ese vecindario."}, "cra-district": {"term": "Distrito de la CRA (CRA district)", "simple": "La línea dibujada en el mapa alrededor del vecindario que cubre una CRA. El dinero que se recauda dentro de la línea se gasta dentro de la línea."}, "tif": {"term": "Incremento de impuestos (tax increment, TIF)", "simple": "El impuesto a la propiedad adicional que genera un vecindario porque sus propiedades valen más desde que empezó la CRA. Ese adicional es lo que llena la alcancía de la CRA."}, "base-year": {"term": "Año base (base year)", "simple": "La foto inicial de cuánto valían todas las propiedades de una CRA. Solo el crecimiento por encima de esa cifra aporta dinero a la CRA."}, "trust-fund": {"term": "Fondo fiduciario de la CRA (CRA trust fund)", "simple": "La cuenta bancaria propia de la CRA. Ahí entra el incremento de impuestos y, por ley, solo se puede gastar en el plan de esa CRA."}, "sunset": {"term": "Fecha de terminación (sunset date)", "simple": "El día en que está previsto que termine una CRA. Después de esa fecha, el dinero adicional de impuestos vuelve a los presupuestos de la ciudad y del condado."}, "tif-rebate": {"term": "Reembolso de TIF (TIF rebate)", "simple": "Un acuerdo en el que la CRA le devuelve a un constructor parte de los nuevos impuestos que genera su proyecto, durante un número fijo de años, para ayudar a que el proyecto se construya."}, "facade-grant": {"term": "Subvención para fachadas (façade or storefront grant)", "simple": "Dinero que una CRA le da al dueño de un negocio para arreglar el frente de su edificio, por lo general igualando lo que gasta el dueño."}, "ad-valorem": {"term": "Impuesto a la propiedad (ad valorem tax)", "simple": "Un impuesto basado en lo que vale su casa o terreno. Las propiedades de más valor pagan más."}, "taxing-authority": {"term": "Autoridad tributaria (taxing authority)", "simple": "Cualquier gobierno autorizado para poner un impuesto a la propiedad en su factura, como el condado, la junta escolar o su ciudad."}, "millage": {"term": "Tasa en milésimas (millage, mills)", "simple": "La forma en que se escriben las tasas del impuesto a la propiedad. Un \"mill\" significa $1 de impuesto por cada $1,000 del valor sobre el que se cobra impuesto a su propiedad."}, "just-value": {"term": "Valor justo (just value)", "simple": "El cálculo del Tasador de Propiedades (Property Appraiser) de lo que su propiedad se vendería."}, "assessed-value": {"term": "Valor tasado (assessed value)", "simple": "El valor de su propiedad después de aplicar los límites a qué tan rápido puede subir. Para una vivienda principal con exención de homestead, normalmente sube más despacio que el mercado."}, "taxable-value": {"term": "Valor gravable (taxable value)", "simple": "La cifra sobre la que realmente se calcula su impuesto: el valor tasado menos cualquier exención."}, "homestead": {"term": "Exención de vivienda principal (homestead exemption)", "simple": "Un descuento en los impuestos a la propiedad para la casa donde usted vive todo el año, siempre que lo solicite."}, "rolled-back": {"term": "Tasa de reversión (rolled-back rate)", "simple": "La tasa de impuestos que recaudaría el mismo dinero que el año pasado de las mismas propiedades. Si un gobierno escoge una tasa más alta, la ley lo llama un aumento de impuestos, aunque la tasa no haya cambiado."}, "trim": {"term": "Aviso TRIM (TRIM notice)", "simple": "La tarjeta postal que usted recibe cada agosto con sus impuestos propuestos y las fechas de las audiencias públicas."}, "non-ad-valorem": {"term": "Cargo no basado en el valor (non-ad valorem assessment)", "simple": "Una tarifa fija en su factura de impuestos por un servicio, como la recolección de basura o la protección contra incendios. No se basa en lo que vale su propiedad."}, "mstu": {"term": "MSTU", "simple": "Una zona de impuesto adicional del condado que paga servicios en solo una parte del condado, por lo general las zonas fuera de las ciudades."}, "rle": {"term": "Aporte Local Obligatorio (Required Local Effort)", "simple": "La tasa de impuesto escolar que el estado le indica a cada distrito escolar que cobre para poder recibir su parte del dinero estatal para escuelas."}, "save-our-homes": {"term": "Límite Save Our Homes (Save Our Homes cap)", "simple": "Un límite a qué tan rápido puede subir el valor gravado de una vivienda con homestead: 3% al año, o menos si la inflación es menor. Las propiedades de alquiler, los negocios y las segundas viviendas tienen un límite más amplio de 10%."}, "rec": {"term": "Conferencia de Estimación de Ingresos (Revenue Estimating Conference)", "simple": "El equipo de economistas del estado que calcula cuánto dinero sumaría o restaría una nueva ley o enmienda."}, "levy": {"term": "Gravamen (levy)", "simple": "El total de impuesto a la propiedad que un gobierno recauda en un año: su tasa multiplicada por todo el valor gravable de su zona."}, "fiscal-year": {"term": "Año fiscal (fiscal year, FY)", "simple": "El año de presupuesto de un gobierno. En Florida va del 1 de octubre al 30 de septiembre."}, "general-fund": {"term": "Fondo general (general fund)", "simple": "La cuenta corriente principal de un gobierno para los servicios de todos los días, como la policía, los parques y el funcionamiento del ayuntamiento."}, "enterprise-fund": {"term": "Fondo empresarial (enterprise fund)", "simple": "Una cuenta para un servicio que usted paga directamente, como el agua y el alcantarillado. Las facturas que usted paga cubren el servicio."}, "special-revenue": {"term": "Fondo de ingresos especiales (special revenue fund)", "simple": "Dinero que por ley solo se puede gastar en una cosa, como el impuesto a la gasolina para carreteras o el fondo fiduciario de una CRA."}, "state-shared": {"term": "Ingresos compartidos del estado (state shared revenue)", "simple": "Dinero que el estado recauda, sobre todo del impuesto sobre las ventas, y devuelve a las ciudades y los condados."}, "charges-services": {"term": "Cobros por servicios (charges for services)", "simple": "Dinero que un gobierno gana cobrando por cosas que ofrece, como las facturas de agua, la recolección de basura, los permisos y las tarifas de los parques."}, "intergovernmental": {"term": "Ingresos intergubernamentales (intergovernmental revenue)", "simple": "Dinero que un gobierno recibe de otro, como subvenciones federales o ingresos compartidos del estado."}, "constitutional-officers": {"term": "Funcionarios constitucionales (constitutional officers)", "simple": "Los funcionarios electos del condado que nombra la constitución de Florida: el alguacil (sheriff), el tasador de propiedades, el recaudador de impuestos, el secretario del tribunal (clerk of court) y el supervisor de elecciones."}, "audit": {"term": "Auditoría / informe financiero anual (audit / annual financial report)", "simple": "Una revisión anual de las cuentas de un gobierno hecha por contadores externos, para asegurarse de que los números cuadran y de que se siguieron las reglas."}, "spent": {"term": "Gastado (Spent)", "simple": "El registro indica que el dinero realmente se pagó."}, "committed": {"term": "Comprometido (Committed)", "simple": "Se aprobó un contrato o una adjudicación, pero todavía no se ha pagado todo el dinero."}, "budgeted": {"term": "Presupuestado (Budgeted)", "simple": "Dinero apartado en un plan. Puede que se gaste o puede que no."}, "proposed": {"term": "Propuesto (Proposed)", "simple": "Una idea o solicitud que no se ha aprobado."}, "left-out": {"term": "Excluido de los totales (Left out of totals)", "simple": "Se muestra en el sitio, pero no se suma a los totales, para que el mismo dólar nunca se cuente dos veces."}, "change-order": {"term": "Orden de cambio (change order)", "simple": "Un cambio aprobado a un contrato después de firmado, que a menudo agrega costo o tiempo."}, "right-of-way": {"term": "Derecho de vía (right-of-way)", "simple": "El terreno donde está una carretera más la franja a su lado para aceras, servicios públicos y drenaje."}, "eminent-domain": {"term": "Expropiación (eminent domain)", "simple": "Cuando un gobierno compra un terreno privado para un proyecto público aunque el dueño no quiera vender. Un tribunal decide el precio justo."}, "bond": {"term": "Bono (bond)", "simple": "Una forma en que un gobierno pide dinero prestado ahora y lo devuelve con intereses durante muchos años, como una hipoteca."}, "cdd": {"term": "Distrito de Desarrollo Comunitario (Community Development District, CDD)", "simple": "Un gobierno especial creado para un solo desarrollo, para construir y pagar sus calles, tuberías y otros servicios básicos. Los dueños de las propiedades de ahí lo pagan."}, "interlocal": {"term": "Acuerdo interlocal (interlocal agreement)", "simple": "Un contrato entre dos gobiernos, como una ciudad y el condado."}, "public-records": {"term": "Solicitud de registros públicos (public records request)", "simple": "Pedirle a un gobierno que le muestre o le envíe sus registros. En Florida, cualquier persona puede pedirlos, y no tiene que decir por qué."}, "check-register": {"term": "Registro de pagos (check register)", "simple": "La lista de un gobierno de cada pago que hizo: a quién se le pagó, cuánto, cuándo y por qué."}, "exemption": {"term": "Exención (exemption)", "simple": "Una parte del valor de su propiedad sobre la que no paga impuesto. Si tiene una exención de $25,000, le cobran como si su casa valiera $25,000 menos."}, "stormwater": {"term": "Aguas pluviales (stormwater)", "simple": "El agua de lluvia que corre por las calles y los techos. Las ciudades y el condado cobran una tarifa para pagar las zanjas, los tubos y los estanques que la llevan."}, "qualifying": {"term": "Calificar como candidato (qualifying)", "simple": "El paso en que un candidato entrega sus papeles y paga la cuota, o junta firmas, para aparecer en la boleta. Si no lo hace a tiempo, no aparece."}, "in-kind": {"term": "Donación en especie (in-kind contribution)", "simple": "Una donación a una campaña que no es dinero, sino cosas o servicios, como comida para un evento o letreros gratis."}, "recall": {"term": "Elección revocatoria (recall election)", "simple": "Una votación para decidir si un funcionario electo sale de su cargo antes de que termine su período."}, "public-comment": {"term": "Comentario público (public comment)", "simple": "El momento de una reunión del gobierno en que cualquier persona puede hablar a la junta, casi siempre por unos 3 minutos."}} : {"cra": {"term": "Community Redevelopment Agency (CRA)", "simple": "A savings jar for one neighborhood that needs fixing up. When the neighborhood's property gets more valuable, the extra tax money goes into the jar, and it can only be spent in that neighborhood."}, "cra-district": {"term": "CRA district", "simple": "The line drawn on the map around the neighborhood a CRA covers. Money raised inside the line is spent inside the line."}, "tif": {"term": "Tax increment (TIF)", "simple": "The extra property tax a neighborhood brings in because its property became worth more after the CRA started. That extra is what fills the CRA's jar."}, "base-year": {"term": "Base year", "simple": "The starting snapshot of how much all the property in a CRA was worth. Only growth above this number pays into the CRA."}, "trust-fund": {"term": "CRA trust fund", "simple": "The CRA's own bank account. Tax increment goes in, and by law it can only be spent on that CRA's plan."}, "sunset": {"term": "Sunset date", "simple": "The day a CRA is scheduled to end. After that, the extra tax money goes back to the city and county budgets."}, "tif-rebate": {"term": "TIF rebate", "simple": "A deal where the CRA gives a builder back part of the new taxes their project creates, for a set number of years, to help get the project built."}, "facade-grant": {"term": "Façade or storefront grant", "simple": "Money a CRA gives a business owner to fix up the front of their building, usually matching what the owner spends."}, "ad-valorem": {"term": "Property tax (ad valorem tax)", "simple": "A tax based on what your house or land is worth. More valuable property pays more."}, "taxing-authority": {"term": "Taxing authority", "simple": "Any government allowed to put a property tax on your bill, like the county, the school board or your city."}, "millage": {"term": "Millage (mills)", "simple": "How property tax rates are written. One mill means $1 of tax for every $1,000 your property is taxed on."}, "just-value": {"term": "Just value", "simple": "The Property Appraiser's estimate of what your property would sell for."}, "assessed-value": {"term": "Assessed value", "simple": "Your property's value after any limits on how fast it can go up. For a homestead, it usually rises more slowly than the market."}, "taxable-value": {"term": "Taxable value", "simple": "The number your tax is actually figured on: the assessed value minus any exemptions."}, "homestead": {"term": "Homestead exemption", "simple": "A discount on property taxes for the home you live in full time, as long as you apply for it."}, "rolled-back": {"term": "Rolled-back rate", "simple": "The tax rate that would bring in the same money as last year from the same properties. If a government picks a higher rate, the law calls it a tax increase, even if the rate didn't change."}, "trim": {"term": "TRIM notice", "simple": "The postcard you get each August showing your proposed taxes and when the public hearings are."}, "non-ad-valorem": {"term": "Non-ad valorem assessment", "simple": "A flat fee on your tax bill for a service, like garbage pickup or fire protection. It isn't based on what your property is worth."}, "mstu": {"term": "MSTU", "simple": "An extra county tax area that pays for services in only part of the county, usually the areas outside cities."}, "rle": {"term": "Required Local Effort", "simple": "The school tax rate the state tells every school district to charge so it can get its share of state school money."}, "save-our-homes": {"term": "Save Our Homes cap", "simple": "A limit on how fast a homestead's taxed value can go up: 3% a year, or less if inflation is lower. Rentals, businesses and second homes have a looser 10% limit."}, "rec": {"term": "Revenue Estimating Conference", "simple": "The state's team of economists that estimates how much money a new law or amendment would add or take away."}, "levy": {"term": "Levy", "simple": "The total property tax a government collects in a year: its rate times all the taxable value in its area."}, "fiscal-year": {"term": "Fiscal year (FY)", "simple": "A government's budget year. In Florida it runs from October 1 to September 30."}, "general-fund": {"term": "General fund", "simple": "A government's main checking account for everyday services like police, parks and running city hall."}, "enterprise-fund": {"term": "Enterprise fund", "simple": "An account for a service you pay for directly, like water and sewer. The bills you pay cover the service."}, "special-revenue": {"term": "Special revenue fund", "simple": "Money that by law can only be spent on one thing, like gas tax for roads or a CRA's trust fund."}, "state-shared": {"term": "State shared revenue", "simple": "Money the state collects, mostly from sales tax, and sends back to cities and counties."}, "charges-services": {"term": "Charges for services", "simple": "Money a government earns by charging for things it provides, like water bills, garbage pickup, permits and park fees."}, "intergovernmental": {"term": "Intergovernmental revenue", "simple": "Money one government gets from another, like federal grants or state shared revenue."}, "constitutional-officers": {"term": "Constitutional officers", "simple": "The elected county officials named in Florida's constitution: the sheriff, property appraiser, tax collector, clerk of court and supervisor of elections."}, "audit": {"term": "Audit / annual financial report", "simple": "A yearly check of a government's books by outside accountants, to make sure the numbers add up and the rules were followed."}, "spent": {"term": "Spent", "simple": "The record says the money was actually paid out."}, "committed": {"term": "Committed", "simple": "A contract or award has been approved, but not all of the money has been paid yet."}, "budgeted": {"term": "Budgeted", "simple": "Money set aside in a plan. It may or may not be spent."}, "proposed": {"term": "Proposed", "simple": "An idea or request that hasn't been approved."}, "left-out": {"term": "Left out of totals", "simple": "Shown on the site, but not added into the totals, so the same dollar is never counted twice."}, "change-order": {"term": "Change order", "simple": "An approved change to a contract after it is signed, which often adds cost or time."}, "right-of-way": {"term": "Right-of-way", "simple": "The land a road sits on plus the strip alongside it for sidewalks, utilities and drainage."}, "eminent-domain": {"term": "Eminent domain", "simple": "When a government buys private land for a public project even if the owner doesn't want to sell. A court decides the fair price."}, "bond": {"term": "Bond", "simple": "A way for a government to borrow money now and pay it back with interest over many years, like a mortgage."}, "cdd": {"term": "Community Development District (CDD)", "simple": "A special government created for one development to build and pay for its roads, pipes and other basics. The property owners there pay for it."}, "interlocal": {"term": "Interlocal agreement", "simple": "A contract between two governments, like a city and the county."}, "public-records": {"term": "Public records request", "simple": "Asking a government to show you or send you its records. In Florida, anyone can ask, and you don't have to say why."}, "check-register": {"term": "Check register", "simple": "A government's list of every payment it made: who got paid, how much, when and for what."}};
  let pop = null, cur = null, hideT = null, shownAt = 0;
  const ensure = () => {
    if (pop) return pop;
    pop = document.createElement('div'); pop.className = 'term-pop'; pop.id = 'term-pop';
    pop.setAttribute('role', 'tooltip'); pop.hidden = true; document.body.appendChild(pop);
    pop.addEventListener('pointerenter', () => clearTimeout(hideT));
    pop.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') later(); });
    return pop;
  };
  function show(el) {
    const g = G[el.dataset.term]; if (!g) return;
    ensure(); clearTimeout(hideT);
    if (cur && cur !== el) cur.removeAttribute('aria-describedby');
    if (cur !== el || pop.hidden) shownAt = Date.now();
    cur = el;
    pop.innerHTML = '<b></b><p></p><a></a>';
    pop.querySelector('b').textContent = g.term;
    pop.querySelector('p').textContent = g.simple;
    const a = pop.querySelector('a'); a.href = (ES ? '/es/glosario#' : '/glossary#') + el.dataset.term; a.textContent = ES ? 'M\u00e1s en el glosario \u2192' : 'More in the glossary \u2192';
    pop.hidden = false; el.setAttribute('aria-describedby', 'term-pop');
    const r = el.getBoundingClientRect(), w = Math.min(300, innerWidth - 24);
    pop.style.width = w + 'px';
    const x = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 12));
    const h = pop.offsetHeight;
    let y = r.bottom + 8; if (y + h > innerHeight - 8) y = r.top - h - 8;
    pop.style.left = (x + scrollX) + 'px'; pop.style.top = (Math.max(8, y) + scrollY) + 'px';
  }
  function hide() { if (pop) pop.hidden = true; if (cur) cur.removeAttribute('aria-describedby'); cur = null; }
  function later() { clearTimeout(hideT); hideT = setTimeout(hide, 160); }
  const termOf = e => e.target.closest && e.target.closest('.term');
  document.addEventListener('pointerover', e => { if (e.pointerType !== 'mouse') return; const t = termOf(e); if (t) show(t); });
  document.addEventListener('pointerout', e => { if (e.pointerType === 'mouse' && termOf(e)) later(); });
  document.addEventListener('focusin', e => { const t = termOf(e); if (t) show(t); });
  document.addEventListener('focusout', e => { if (termOf(e)) later(); });
  document.addEventListener('click', e => {
    const t = termOf(e);
    if (t) { e.preventDefault(); e.stopPropagation(); if (cur === t && pop && !pop.hidden && Date.now() - shownAt > 500) hide(); else show(t); }
    else if (!(e.target.closest && e.target.closest('.term-pop'))) hide();
  }, true);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hide();
    const t = termOf(e); if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); show(t); }
  });
  addEventListener('scroll', () => { if (cur) show(cur); }, {passive: true});
  const prep = () => document.querySelectorAll('.term:not([tabindex])').forEach(t => { t.tabIndex = 0; t.setAttribute('role', 'button'); });
  prep(); new MutationObserver(prep).observe(document.body, {childList: true, subtree: true});
})();
