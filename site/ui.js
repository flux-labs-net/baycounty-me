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
  const q = root.querySelector('[data-dir-q]'), g = root.querySelector('[data-dir-g]'), s = root.querySelector('[data-dir-s]'), t = root.querySelector('[data-dir-t]');
  const chips = [...root.querySelectorAll('.ui-chip[data-k]')], count = root.querySelector('[data-dir-count]'), none = root.querySelector('[data-dir-none]');
  const cards = [...grid.children];
  let kind = '';
  const words = t => (t || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '').split(/\s+/).filter(Boolean);
  const run = () => {
    const w = words(q && q.value), gv = g ? g.value : '', tv = t ? t.value : '';
    cards.forEach(c => {
      const ok = w.every(x => (c.dataset.s || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').includes(x))
        && (!kind || (' ' + c.dataset.k + ' ').includes(' ' + kind + ' ')) && (!gv || (' ' + c.dataset.gv + ' ').includes(' ' + gv + ' ')) && (!tv || c.dataset.t === tv);
      c.classList.toggle('ui-off', !ok);
    });
    const by = s ? s.value : 'c';
    heads.forEach(h => h.remove()); heads.length = 0;
    cards.slice().sort((a, b) => by === 'gov' ? (+a.dataset.o - +b.dataset.o) : by === 'name' ? a.dataset.n.localeCompare(b.dataset.n) : by === 'az' ? last(a.dataset.n).localeCompare(last(b.dataset.n)) || a.dataset.n.localeCompare(b.dataset.n)
      : (+b.dataset.c - +a.dataset.c) || a.dataset.n.localeCompare(b.dataset.n)).forEach(c => grid.appendChild(c));
    if (by === 'gov') groups();
    count_();
  };
  // 'gov' sort: a heading (with how many are shown) above each government's cards and a smaller one above each
  // sub-group inside it (Current, Past); a heading hides when none of its cards are shown.
  const heads = [];
  const last = n => { const w = n.replace(/,/g, ' ').split(/\s+/).filter(x => x && !/^(jr|sr|ii|iii|iv)\.?$/i.test(x)); return (w.pop() || n).toLowerCase(); };
  const groups = () => {
    let g = null, sg = null;
    const head = (tag, cls, text, c) => {
      const h = document.createElement(tag); h.className = cls; h.dataset.g = text;
      h.innerHTML = '<span></span><b></b>'; h.firstChild.textContent = text;
      grid.insertBefore(h, c); heads.push(h);
    };
    [...grid.children].forEach(c => {
      if (c.dataset.gh !== g) { g = c.dataset.gh; sg = null; head('h3', 'ui-dir-h', g, c); }
      if (c.dataset.sh && c.dataset.sh !== sg) { sg = c.dataset.sh; head('h4', 'ui-dir-h ui-dir-sub', sg, c); }
    });
  };
  const countHeads = () => heads.forEach(h => {
    let n = 0;
    const sub = h.classList.contains('ui-dir-sub');  // a group heading counts past its sub-headings, a sub-heading stops at the next heading
    for (let c = h.nextElementSibling; c && !(c.classList.contains('ui-dir-h') && (sub || !c.classList.contains('ui-dir-sub'))); c = c.nextElementSibling)
      if (!c.classList.contains('ui-dir-h') && !c.hidden && !c.classList.contains('ui-off')) n++;
    if (h.hidden !== !n) h.hidden = !n;  // only on change: the observer below watches hidden
    h.lastChild.textContent = n.toLocaleString('en-US');
  });
  const count_ = () => {
    countHeads();
    const n = cards.filter(c => !c.hidden && !c.classList.contains('ui-off')).length;
    if (count) count.textContent = n === cards.length ? `${cards.length.toLocaleString('en-US')} shown` : `${n.toLocaleString('en-US')} of ${cards.length.toLocaleString('en-US')} shown`;
    if (none) none.hidden = n > 0;
  };
  chips.forEach(b => b.addEventListener('click', () => { kind = b.dataset.k; chips.forEach(x => x.setAttribute('aria-pressed', x === b)); run(); }));
  [q, g, s, t].forEach(el => el && el.addEventListener(el.tagName === 'INPUT' ? 'input' : 'change', run));
  const csvBtn = root.querySelector('[data-dir-csv]');
  if (csvBtn) csvBtn.addEventListener('click', () => {
    const rows = cards.filter(c => !c.hidden && !c.classList.contains('ui-off')).map(c => { const a = c.querySelector('.ui-dc-a'); return [a.textContent.trim(), (c.querySelector('small') || {}).textContent || '', ((c.querySelector('.ui-dc-w') || {}).textContent || '').trim(), c.dataset.c, a.href]; });
    if (window.TT) window.TT.csv(csvBtn.dataset.dirCsv, csvBtn.dataset.head.split(','), rows);
  });
  new MutationObserver(ms => { if (ms.some(m => !m.target.classList.contains('ui-dir-h'))) count_(); }).observe(grid, {subtree: true, attributes: true, attributeFilter: ['hidden']});  // the government bar hides cards too
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
/* Long ingested text (legal notices, alert details): BC.longText(text, facts) -> paragraphs with the key facts up top,
   a short lede and the rest behind "Read the full notice". Paragraph breaks come from site/longtext.py; html() there
   makes the same markup for pages built server side. */
(() => {
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const URL = /(?:https?:\/\/[^\s<>"']+|www\.[^\s<>"']+|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov|com|org|net|us|edu)(?:\/[^\s<>"']*)?)/gi;
const PHONE = /\(?(\d{3})\)?[\s.-]{0,2}(\d{3})[\s.-](\d{4})/g;
const trim = u => { while (/[.,;:!?)\]}'"”’]$/.test(u) && !(u.endsWith(')') && (u.match(/\(/g) || []).length > (u.match(/\)/g) || []).length - 1)) u = u.slice(0, -1); return u; };
const href = u => /^https?:\/\//i.test(u) ? u : 'https://' + u;
const short = u => u.replace(/^https?:\/\/(www\.)?/i, '').replace(/^www\./i, '').replace(/\/$/, '');
const wordy = c => c && /[\w@.]/.test(c);
function inline(p) {
  const marks = [], hit = (s, e) => marks.some(m => s < m[1] && m[0] < e);
  let m;
  for (EMAIL.lastIndex = 0; (m = EMAIL.exec(p));) marks.push([m.index, m.index + m[0].length, `<a href="mailto:${esc(m[0])}">${esc(m[0])}</a>`]);
  for (URL.lastIndex = 0; (m = URL.exec(p));) { const u = trim(m[0]); if (wordy(p[m.index - 1]) || /[\w@]/.test(p[m.index + m[0].length] || '') || hit(m.index, m.index + u.length)) continue;
    marks.push([m.index, m.index + u.length, `<a href="${esc(href(u))}" target="_blank" rel="noopener">${esc(u)}</a>`]); }
  for (PHONE.lastIndex = 0; (m = PHONE.exec(p));) { if (/[\d-]/.test(p[m.index - 1] || '') || /[\d-]/.test(p[m.index + m[0].length] || '') || hit(m.index, m.index + m[0].length)) continue;
    marks.push([m.index, m.index + m[0].length, `<a href="tel:+1${m[1]}${m[2]}${m[3]}">${esc(m[0])}</a>`]); }
  marks.sort((a, b) => a[0] - b[0]);
  let out = '', i = 0;
  marks.forEach(([s, e, a]) => { if (s < i) return; out += esc(p.slice(i, s)) + a; i = e; });
  out += esc(p.slice(i));
  const lab = p.match(/^((?:[A-Z][A-Z&/'’-]*\s){0,2}[A-Z][A-Z&/'’-]+):\s/);
  if (lab && lab[1].replace(/[^A-Za-z]/g, '').length >= 3) { const n = esc(lab[0]).length; out = `<b class="lt-lab">${out.slice(0, n).trim()}</b> ${out.slice(n)}`; }
  return out.replace(/\n/g, '<br>');
}
const FIELD = /^[A-Z][\w #/.()-]{0,28}:\s\S.{0,90}$/;
const isHead = p => p.length <= 160 && !/[a-z]/.test(p) && p.split(/\s+/).length >= 2 && !/[:,]$/.test(p.trim());
function para(p) {
  if (isHead(p)) return `<p class="lt-h">${esc(p)}</p>`;
  const lines = p.split('\n');
  if (lines.length > 1 && lines.every(l => FIELD.test(l)))
    return `<dl class="lt-f">${lines.map(l => { const k = l.indexOf(':'); return `<div><dt>${esc(l.slice(0, k))}</dt><dd>${inline(l.slice(k + 1).trim())}</dd></div>`; }).join('')}</dl>`;
  return `<p>${inline(p)}</p>`;
}
function split(text) {
  const t = String(text || '').replace(/\r\n?/g, '\n').trim();
  if (!t) return [];
  if (/\n\s*\n/.test(t) || t.length < 600) return t.split(/\n\s*\n/).map(s => s.trim()).filter(Boolean);
  // not split yet (live rows from older syncs): about three sentences a paragraph
  const out = []; let cur = '';
  const flat = t.replace(/\s+/g, ' '), ss = [], re = /[.!?][”"’)]?\s+(?=[“"(]?[A-Z])/g; let m, i = 0;
  while ((m = re.exec(flat))) { ss.push(flat.slice(i, m.index + m[0].length).trim()); i = m.index + m[0].length; }
  ss.push(flat.slice(i).trim());
  ss.filter(Boolean).forEach(s => { if (cur && cur.length + s.length > 300) { out.push(cur); cur = s; } else cur = (cur + ' ' + s).trim(); });
  if (cur) out.push(cur);
  return out;
}
const list = s => String(s || '').split(';').map(x => x.trim()).filter(Boolean);
function facts(f) {
  if (!f) return '';
  const items = [];
  if (f.reference) items.push(['Number', esc(f.reference)]);
  const em = list(f.emails), ph = list(f.phones), ln = list(f.links);
  if (em.length) items.push([em.length > 1 ? 'Emails' : 'Email', em.slice(0, 3).map(e => `<a href="mailto:${esc(e)}">${esc(e)}</a>`).join('<br>')]);
  if (ph.length) items.push([ph.length > 1 ? 'Phones' : 'Phone', ph.slice(0, 2).map(p => `<a href="tel:+1${p.replace(/\D/g, '')}">${esc(p)}</a>`).join('<br>')]);
  if (ln.length) items.push([ln.length > 1 ? 'Links' : 'Link', ln.slice(0, 3).map(u => `<a href="${esc(href(u))}" target="_blank" rel="noopener">${esc(short(u))}</a>`).join('<br>')]);
  return items.length ? `<dl class="lt-facts">${items.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>` : '';
}
function longText(text, f, o = {}) {
  const ps = split(text), more = o.more || 'Read the full notice';
  if (!ps.length) return facts(f);
  const words = String(text).split(/\s+/).length, mins = Math.max(1, Math.round(words / 230));
  const body = ps.map(para).join('');
  const li = ps.findIndex(p => !isHead(p));
  if (words < 90 || li < 0) return `<div class="lt">${facts(f)}<div class="lt-body">${body}</div></div>`;
  return `<div class="lt">${facts(f)}<p class="lt-lede">${inline(ps[li])}</p>
    <details class="lt-more"><summary><span class="o">${esc(more)}</span><span class="c">Show less</span> <small>${mins} min read</small></summary><div class="lt-body">${body}</div></details></div>`;
}
window.BC = Object.assign(window.BC || {}, {longText, longTextFacts: facts, longTextBody: t => split(t).map(para).join('')});
})();
