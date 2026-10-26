// Adds the live "Votes from minutes" share to each government's data-completeness percent and status table.
// The other portions are drawn by the server (site/completeness.py); minutes progress comes from /api/v1/import-progress.
(function () {
  var chips = document.querySelectorAll('[data-dc-chip]');
  var tables = document.querySelectorAll('section.dc[data-dc-gov]');
  if (!chips.length && !tables.length) return;
  var GREEN = 100, YELLOW = 50;
  var st = function (p) { return p >= GREEN ? 'complete' : p >= YELLOW ? 'partial' : 'missing'; };
  var TEXT = {complete: 'Complete', partial: 'Partial', missing: 'Mostly missing'};
  var setSt = function (el, s) { el.classList.remove('dc-complete', 'dc-partial', 'dc-missing'); el.classList.add('dc-' + s); };
  fetch('/api/v1/import-progress', {headers: {Accept: 'application/json'}})
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (!d || !d.installed || !d.boards) return;
      var by = {};
      d.boards.forEach(function (b) {
        if (!b.gov) return;
        var g = by[b.gov] || (by[b.gov] = {found: 0, read: 0});
        g.found += b.totals.found || 0; g.read += b.totals.read || 0;
      });
      var pctOf = function (g) { return g && g.found ? Math.min(100, Math.round(1000 * g.read / g.found) / 10) : null; };
      chips.forEach(function (c) {
        var v = pctOf(by[c.getAttribute('data-dc-gov')]);
        if (v == null) return;
        var p = Math.round((Number(c.getAttribute('data-sum')) + v) / (Number(c.getAttribute('data-n')) + 1));
        c.querySelector('[data-dc-pct]').textContent = p + '%';
        setSt(c, st(p));
      });
      tables.forEach(function (t) {
        var g = by[t.getAttribute('data-dc-gov')], v = pctOf(g), row = t.querySelector('[data-dc-votes]');
        if (v == null || !row) return;
        var s = st(v);
        setSt(row.querySelector('.dc-fill'), s);
        row.querySelector('.dc-fill').style.width = Math.max(2, v) + '%';
        row.querySelector('[data-v-pct]').textContent = Math.round(v) + '%';
        row.querySelector('[data-v-n]').textContent = g.read.toLocaleString('en-US') + ' of ' + g.found.toLocaleString('en-US') + ' files';
        var sp = row.querySelector('[data-v-st]');
        setSt(sp, s);
        sp.querySelector('.dc-sx').textContent = TEXT[s]; sp.title = TEXT[s];
        row.hidden = false;
      });
    })
    .catch(function () {});
})();
