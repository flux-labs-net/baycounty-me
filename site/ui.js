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
