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
      rows.slice(0, 4).map(r => `<li><a href="${S.esc(r.u)}"${r.p ? ' class="sx-ph"' : ''}>${r.p ? `<img src="${S.esc(r.p)}" alt="" width="32" height="32" loading="lazy">` : ''}<b>${S.hl(r.t, words)}</b><span>${S.hl(r.s, words)}</span></a></li>`).join('') + '</ul></section>').join('') +
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
