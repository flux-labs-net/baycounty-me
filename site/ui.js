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
