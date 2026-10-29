/* Share and copy (bundled into /assets/site.js, window.BC.share).

   Page:    a "Share" button in the page header: Copy link, or the phone's share sheet with the page's link (the app
            it goes to draws the preview card from the link).
   Records: every row of a data table, and every item of a list marked data-share-items (or data-tt-list), gets a
            small share button with the same two actions for a link straight to it: the record's own page when the
            row has data-share-url, else this page with
            #r-<key>, where <key> comes from the row's text. Opening that link scrolls to the record and marks it, even
            when the year picker or a filter had hidden it.
   Opt out: <table data-share="off">, or data-share="off" on any element around it. Tables without column headings
            (label/value fact tables) and pages under /admin, /finance, /account and /realtor are left alone. */
(() => {
const ES = (document.documentElement.lang || '').startsWith('es');
const L = ES
  ? {share: 'Compartir', link: 'Copiar enlace', sheet: 'Compartir…', copied: 'Copiado', linkCopied: 'Enlace copiado', rec: 'Compartir este registro', page: 'Compartir esta página', from: 'De', on: 'en BayCounty.me', fail: 'No se pudo copiar'}
  : {share: 'Share', link: 'Copy link', sheet: 'Share…', copied: 'Copied', linkCopied: 'Link copied', rec: 'Share this record', page: 'Share this page', from: 'From', on: 'on BayCounty.me', fail: 'Couldn’t copy'};
const OFF = /^\/(admin|finance|account|realtor)(\/|$)/;
const clean = s => String(s ?? '').replace(/[ \t ]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{2,}/g, '\n').trim();
const ICON = '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M7.5 7.5 12 3l4.5 4.5"/><path d="M5 12v6.5A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V12"/></svg>';
const I_LINK = '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14a4.5 4.5 0 0 0 6.4 0l3-3a4.5 4.5 0 0 0-6.4-6.4l-1 1"/><path d="M14 10a4.5 4.5 0 0 0-6.4 0l-3 3a4.5 4.5 0 0 0 6.4 6.4l1-1"/></svg>';
const canShare = () => typeof navigator.share === 'function';
const meta = p => (document.querySelector(`meta[property="${p}"]`) || {}).content || '';

/* ---------- a short, stable key for a record, from its text ---------- */
function key(text) {
  let h = 0x811c9dc5;
  const s = clean(text).toLowerCase();
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(36);
}

/* ---------- reading a record ---------- */
const TIME = /^(\d{1,2}(:\d\d)?\s?(a\.?m\.?|p\.?m\.?)|all day|todo el día|noon|mediodía)$/i;
const GENERIC = /^(source|sources|summary|pdf|agenda|minutes|link|view|details|record|filing|report|video|document|more|open|fuente|resumen|ver)\b.{0,12}$/i;
// A cell's text: small print and line breaks become " · " so "Name<small>City</small>" reads "Name · City".
function cellText(c) {
  const x = c.cloneNode(true);
  x.querySelectorAll('.bc-sh, .sr, [aria-hidden="true"], script, style, button:not(.tt-h)').forEach(n => n.remove());
  // a link whose words say nothing on their own ("Source", "PDF", "Agenda") is written as its address
  x.querySelectorAll('a[href]').forEach(a => { if (GENERIC.test(clean(a.textContent))) a.textContent = a.href; });
  x.querySelectorAll('small, br, .badge, .pill').forEach(n => n.before(' · '));
  return clean(x.textContent.replace(/\s+/g, ' ')).replace(/^(· )+|( ·)+$/g, '').replace(/( · )+/g, ' · ').replace(/ · $/, '');
}
const colsOf = tr => { const out = []; for (const c of tr.cells) { const n = Math.max(1, c.colSpan || 1); out.push(c); for (let i = 1; i < n; i++) out.push(null); } return out; };
function heads(t) {
  const h = t.tHead && t.tHead.rows.length ? t.tHead.rows[t.tHead.rows.length - 1] : null;
  if (h) return colsOf(h).map(c => c ? cellText(c) : '');
  return t.dataset.cols ? t.dataset.cols.split('|') : null;
}
function rowText(tr) {
  const t = tr.closest('table'), hs = heads(t) || [];
  const cs = colsOf(tr), lines = [];
  cs.forEach((c, i) => {
    if (!c) return;
    const v = cellText(c);
    if (!v || /^(—|–|-)$/.test(v)) return;
    const lab = c.dataset.label || hs[i] || '';
    lines.push(lab ? `${lab}: ${v}` : v);
  });
  return lines.join('\n');
}
// The key reads only the values, so it doesn't change with column headings or phone labels.
const keyText = el => el.tagName === 'TR' ? [...el.cells].map(cellText).join('|') : itemText(el);
// What a list item or card says, line by line, as it reads on screen (innerText follows the layout).
function itemShown(li) {
  if (!li.offsetParent) return itemText(li);
  let ls = (li.innerText || '').split('\n').map(s => clean(s)).filter(Boolean);
  // a date badge drawn as three lines (OCT / 28 / Wed) reads "Wed, Oct 28"
  if (ls.length > 3 && /^[A-Za-z]{3}$/.test(ls[0]) && /^\d{1,2}$/.test(ls[1]) && /^[A-Za-z]{3}$/.test(ls[2]))
    ls = [`${ls[2]}, ${ls[0][0].toUpperCase()}${ls[0].slice(1).toLowerCase()} ${ls[1]}`, ...ls.slice(3)];
  ls = ls.filter(l => !/^(read the full|read more|show less|show more|see more|leer|\d+ min read)/i.test(l));
  // links that only say "Apply" or "Source" are written with their address
  const links = new Map([...li.querySelectorAll('a[href]')].map(a => [clean(a.textContent), a.href]));
  ls = ls.map(l => (GENERIC.test(l) || /^(apply|aplicar)\b/i.test(l)) && links.has(l) ? `${l}: ${links.get(l)}` : l);
  // an ALL-CAPS label on its own line (EMAIL, PHONE) joins the value under it
  const out = [];
  for (let i = 0; i < ls.length; i++) {
    if (/^[A-Z][A-Z ]{2,14}$/.test(ls[i]) && ls[i + 1] && i > 0) { out.push(`${ls[i][0]}${ls[i].slice(1).toLowerCase()}: ${ls[i + 1]}`); i++; }
    else out.push(ls[i]);
  }
  return out.slice(0, 14).join('\n');
}
function itemText(li) {
  const x = li.cloneNode(true);
  x.querySelectorAll('.bc-sh, .sr, script, style, button, details > summary .c').forEach(n => n.remove());
  x.querySelectorAll('br, p, div, li, small, dt, dd, h3, h4, .d').forEach(n => { n.before('\n'); });
  return clean(x.textContent).split('\n').map(s => s.trim()).filter(Boolean).slice(0, 12).join('\n');
}
function sectionName(el) {
  const sec = el.closest('section, .tx-sec, details');
  if (sec && sec.dataset.shareDate) return sec.parentElement ? sectionName(sec.parentElement) : '';  // its day is already in the text
  const h = sec && (sec.querySelector('h2, h3, summary'));
  return h ? cellText(h).replace(/\s*\d[\d,]*$/, '') : '';
}
function pageTitle() { return meta('og:title') || document.title.replace(/ · BayCounty\.me$/, ''); }
function pageUrl() { return (document.querySelector('link[rel="canonical"]') || {}).href || location.origin + location.pathname; }
// a record link keeps the page's current choices (?gov=, ?year=...) so it opens on the same view; tracking tags are dropped
function viewUrl() {
  const q = new URLSearchParams(location.search);
  [...q.keys()].forEach(k => { if (/^(utm_|fbclid|gclid)/.test(k)) q.delete(k); });
  const s = q.toString();
  return pageUrl() + (s ? '?' + s : '');
}
function withYear(el, url) {
  // a record hidden by the year picker opens with every year shown
  const t = el.closest('table, ol, ul'), bar = t && t.previousElementSibling;
  if (!(bar && bar.classList && bar.classList.contains('tt-bar') && bar.querySelector('.tt-ysel')) || /[?&]year=/.test(url)) return url;
  return url.replace(/(#|$)/, (url.includes('?') ? '&' : '?') + 'year=all$1');
}
function recordOf(el) {
  let text = el.tagName === 'TR' ? rowText(el) : itemShown(el);
  // a list grouped by day (data-share-date="2026-10-29" on the group) says which day
  const dd = el.closest('[data-share-date]');
  if (dd) {
    const d = new Date(dd.dataset.shareDate + 'T12:00:00');
    if (!isNaN(d)) {
      const day = d.toLocaleDateString(ES ? 'es-US' : 'en-US', {weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'});
      const ls = text.split('\n');
      if (el.tagName !== 'TR' && TIME.test(ls[0])) ls[0] = `${day}, ${ls[0]}`; else ls.splice(el.tagName === 'TR' ? 1 : 0, 0, day);
      text = ls.join('\n');
    }
  }
  const own = el.dataset.shareUrl || (el.closest('[data-share-url]') || {}).dataset?.shareUrl;
  const url = own ? new URL(own, location.origin).href : withYear(el, viewUrl() + '#r-' + key(keyText(el)));
  const sec = sectionName(el);
  const from = `${L.from} “${sec && sec !== pageTitle() ? sec + ', ' : ''}${pageTitle()}” ${L.on}`;
  const first = el.tagName === 'TR' ? cellText(el.cells[0]) : (text.split('\n').find(l => !TIME.test(l.replace(/^[^,]+, [^,]+, \d{4}, /, '')) && !/^[A-Z][a-z]{2}, [A-Z][a-z]{2} \d{1,2}$/.test(l)) || text.split('\n')[0]);
  return {title: first, text: `${text}\n${from}`, url};
}
function pageRecord() {
  const own = document.querySelector('[data-share-text]');
  const title = pageTitle();
  const text = own ? own.dataset.shareText : `${title}\n${meta('og:description')}`;
  return {title, text: clean(text), url: pageUrl()};
}

/* ---------- copy, toast, menu ---------- */
async function copy(s) {
  try { await navigator.clipboard.writeText(s); return true; }
  catch (e) {
    const ta = document.createElement('textarea'); ta.value = s; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;top:-9999px;opacity:0';
    document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (_) {}
    ta.remove(); return ok;
  }
}
let toastEl, toastT;
function toast(msg) {
  if (!toastEl) { toastEl = document.createElement('div'); toastEl.className = 'bc-toast'; toastEl.setAttribute('role', 'status'); toastEl.setAttribute('aria-live', 'polite'); document.body.appendChild(toastEl); }
  toastEl.textContent = msg; toastEl.classList.add('on');
  clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('on'), 1800);
}
let menu, menuFor;
function closeMenu(focus) {
  if (!menu || menu.hidden) return;
  menu.hidden = true; if (menuFor) { menuFor.setAttribute('aria-expanded', 'false'); if (focus) menuFor.focus(); }
  menuFor = null;
}
function openMenu(btn, rec) {
  if (menuFor === btn) { closeMenu(true); return; }
  if (!menu) {
    menu = document.createElement('div'); menu.className = 'bc-shm'; menu.setAttribute('role', 'menu'); menu.hidden = true;
    document.body.appendChild(menu);
    document.addEventListener('click', e => { if (menu && !menu.hidden && !menu.contains(e.target) && !e.target.closest('.bc-sh, .bc-shp')) closeMenu(); });
    document.addEventListener('keydown', e => {
      if (!menu || menu.hidden) return;
      const items = [...menu.querySelectorAll('button')], i = items.indexOf(document.activeElement);
      if (e.key === 'Escape') { e.preventDefault(); closeMenu(true); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); items[(i + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length].focus(); }
      else if (e.key === 'Tab') closeMenu();
    });
    window.addEventListener('resize', () => closeMenu());
    window.addEventListener('scroll', () => { if (menu && !menu.hidden && menuFor) place(menuFor); }, {passive: true});
  }
  closeMenu();
  menu.innerHTML = `<button type="button" role="menuitem" data-a="link">${I_LINK}<span>${L.link}</span></button>`
    + (canShare() ? `<button type="button" role="menuitem" data-a="share">${ICON}<span>${L.sheet}</span></button>` : '')
    + `<p class="bc-shm-pv"></p>`;
  menu.querySelector('.bc-shm-pv').textContent = rec.url;
  menu.onclick = async e => {
    const b = e.target.closest('button[data-a]'); if (!b) return;
    const a = b.dataset.a;
    closeMenu(true);
    // just the link (with its title): the app it goes to draws the preview card from the link
    if (a === 'share') { try { await navigator.share({title: rec.title, url: rec.url}); } catch (err) {} return; }
    const ok = await copy(rec.url);
    toast(ok ? L.linkCopied : L.fail);
    try { window.va && window.va('event', {name: 'share', data: {how: a, kind: btn.classList.contains('bc-shp') ? 'page' : 'record', path: location.pathname}}); } catch (err) {}
  };
  menu.hidden = false; menuFor = btn; btn.setAttribute('aria-expanded', 'true');
  place(btn);
  menu.querySelector('button').focus({preventScroll: true});
}
function place(btn) {
  const r = btn.getBoundingClientRect(), mw = menu.offsetWidth, mh = menu.offsetHeight, vw = document.documentElement.clientWidth, vh = window.innerHeight;
  let x = Math.min(Math.max(8, r.right - mw), vw - mw - 8), y = r.bottom + 6;
  if (y + mh > vh - 8 && r.top - mh - 6 > 8) y = r.top - mh - 6;
  menu.style.left = x + 'px'; menu.style.top = y + 'px';
}

/* ---------- buttons ---------- */
function recBtn() {
  const b = document.createElement('button');
  b.type = 'button'; b.className = 'bc-sh'; b.innerHTML = ICON;
  b.setAttribute('aria-label', L.rec); b.setAttribute('title', L.rec); b.setAttribute('aria-haspopup', 'menu'); b.setAttribute('aria-expanded', 'false');
  b.dataset.report = 'skip';
  return b;
}
// Records that aren't table rows: list items and cards. Pages can mark their own with data-share-items (on the list)
// or data-share-record (on one record).
const ITEMS = ['[data-share-items] > *', 'ol[data-tt-list] > li', '.ev-list > li', 'ol.findings > li', '.nj-list > .nj-item', '.mil-story', '[data-share-record]']
  .map(s => 'main ' + s).join(', ');
const skip = el => el.closest('[data-share="off"], [data-tt="off"], .ui-pick, header, nav, footer, .sx, .tt-bar, .bc-shm');
function rowOk(tr) {
  if (tr.parentNode.tagName !== 'TBODY' || tr.classList.contains('grp') || tr.classList.contains('stk-span') || tr.dataset.share === 'off') return false;
  const cs = [...tr.cells];
  if (cs.length < 2 || (cs.length === 1 && (cs[0].colSpan || 1) > 1)) return false;
  const first = cellText(cs[0]);
  return first && !/^(total|totals|all |sum\b|nothing|no )/i.test(first);
}
function wireRows() {
  if (OFF.test(location.pathname)) return;
  document.querySelectorAll('main table').forEach(t => {
    if (skip(t)) return;
    const hs = heads(t);
    if (!hs || hs.filter(Boolean).length < 2) return;
    for (const b of t.tBodies) for (const tr of b.rows) {
      if (tr._bcSh || !rowOk(tr)) continue;
      tr._bcSh = true;
      tr.cells[0].classList.add('bc-sh-c');
      tr.cells[0].appendChild(recBtn());
    }
    t.classList.add('bc-sh-t');
  });
  document.querySelectorAll(ITEMS).forEach(it => {
    if (it._bcSh || it.closest('[data-share="off"]') || !clean(it.textContent) || (it.parentElement && it.parentElement.closest('.bc-sh-it'))) return;
    it._bcSh = true; it.classList.add('bc-sh-it'); it.appendChild(recBtn());
  });
}
function pageBtn() {
  if (OFF.test(location.pathname) || location.pathname === '/404' || document.querySelector('.bc-shp')) return;
  const hero = document.querySelector('main .ui-hero') || document.querySelector('main header.tx-top');
  const mk = cls => { const b = document.createElement('button'); b.type = 'button'; b.className = 'bc-shp ' + cls; b.innerHTML = ICON + `<span>${L.share}</span>`;
    b.setAttribute('aria-haspopup', 'menu'); b.setAttribute('aria-expanded', 'false'); b.setAttribute('aria-label', L.page); b.dataset.report = 'skip'; return b; };
  if (!hero) return;
  const pdf = hero.querySelector('.ui-stamp .pdf-btn, .ui-stamp #pdf');
  const stamp = hero.querySelector('.ui-stamp');
  const act = hero.querySelector('.ui-pf-act');
  if (pdf) { const w = document.createElement('div'); w.className = 'bc-shp-pair'; pdf.before(w); w.append(pdf, mk('pdf-btn')); }
  else if (act) act.appendChild(mk('ui-btn'));
  else if (stamp) stamp.appendChild(mk('pdf-btn'));
  else { const hd = hero.querySelector('.ui-hd') || hero; const row = document.createElement('div'); row.className = 'bc-shp-row'; row.dataset.report = 'skip'; row.appendChild(mk('ui-btn')); hd.appendChild(row); }
}
document.addEventListener('click', e => {
  const b = e.target.closest('.bc-sh, .bc-shp'); if (!b) return;
  e.preventDefault(); e.stopPropagation();
  if (b.classList.contains('bc-shp')) { openMenu(b, pageRecord()); return; }
  const rec = b.closest('.bc-sh-it, tr'); if (rec) openMenu(b, recordOf(rec));
}, true);

/* ---------- opening a record link (#r-<key>) ---------- */
let want = /^#r-([0-9a-z]+)$/.exec(location.hash) ? location.hash.slice(3) : null, tries = 0;
function find() {
  if (!want) return;
  const all = [...document.querySelectorAll('main tbody tr, main .bc-sh-it')];
  const hit = all.find(el => key(keyText(el)) === want);
  if (!hit) { if (++tries < 40) setTimeout(find, 300); return; }
  want = null;
  // show it if a year picker, filter or closed section hid it
  const t = hit.closest('table, ol, ul'), bar = t && t.previousElementSibling;
  if ((hit.hidden || hit.classList.contains('tt-off')) && bar && bar.classList && bar.classList.contains('tt-bar')) {
    const y = bar.querySelector('.tt-ysel'); if (y && y.value) { y.value = ''; y.dispatchEvent(new Event('change', {bubbles: true})); }
    const q = bar.querySelector('.tt-q input'); if (q && q.value) { q.value = ''; q.dispatchEvent(new Event('input', {bubbles: true})); }
  }
  for (let d = hit.closest('details'); d; d = d.parentElement && d.parentElement.closest('details')) d.open = true;
  const pane = hit.closest('[hidden]'); if (pane && pane.id) { const tab = document.querySelector(`[aria-controls="${pane.id}"]`); if (tab) tab.click(); }
  setTimeout(() => { hit.scrollIntoView({block: 'center'}); hit.classList.add('bc-hit'); setTimeout(() => hit.classList.remove('bc-hit'), 4000); }, 120);
}

let q = false;
const run = () => { q = false; wireRows(); };
const go = () => {
  pageBtn(); wireRows(); find();
  new MutationObserver(ms => {
    if (q) return;
    if (ms.some(m => [...m.addedNodes].some(n => n.nodeType === 1 && !n.classList.contains('bc-sh') && !n.classList.contains('bc-toast') && !n.classList.contains('bc-shm')))) { q = true; requestAnimationFrame(run); }
  }).observe(document.body, {childList: true, subtree: true});
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
window.BC = Object.assign(window.BC || {}, {share: (rec, btn) => openMenu(btn || document.activeElement, rec), shareRecord: recordOf, shareKey: key});
})();
