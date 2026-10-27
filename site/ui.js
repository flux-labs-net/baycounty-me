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
