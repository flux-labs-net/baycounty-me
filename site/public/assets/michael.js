(async () => {
const $ = id => document.getElementById(id);
let D; // page data loads after the page has rendered; the markup shows a loading note until then
try { const r = await fetch('/data/michael-page.json'); if (!r.ok) throw new Error(r.status); D = await r.json(); }
catch (e) { $('ledCount').textContent = 'The FEMA projects could not be loaded. Please refresh the page.'; return; }
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => n == null ? '—' : n >= 1e9 ? '$' + (n / 1e9).toFixed(2) + 'B' : n >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : usd(n);
const nice = s => String(s || '').replace(/, City [Oo]f$/, '').replace(/^School Board of Bay County Florida$/, 'Bay District Schools').replace(/^The Board of Trustees of Bay Medical Center$/, 'Bay Medical Center (trustees)');

function bars(el, rows, max) {
  el.innerHTML = rows.map(r => `<div class="hb"><span class="hb-n">${esc(r.n)}${r.s ? ` <em>${esc(r.s)}</em>` : ''}</span><span class="hb-track"><span class="hb-bar" style="width:${Math.max(.4, r.v / max * 100)}%"></span></span><span class="hb-v">${big(r.v)}${r.p != null ? ` <em>${(r.p * 100).toFixed(r.p < .1 ? 1 : 0)}%</em>` : ''}</span></div>`).join('');
}
const tot = D.apps.reduce((a, x) => a + x.f, 0);
const top = D.apps.slice().sort((a, b) => b.f - a.f), TOPN = 14;
const rest = top.slice(TOPN), restSum = rest.reduce((a, x) => a + x.f, 0);
bars($('appBars'), top.slice(0, TOPN).map(x => ({n: nice(x.n), s: `${x.p} projects`, v: x.f, p: x.f / tot})).concat(rest.length ? [{n: `${rest.length} other applicants`, s: 'mostly churches, nonprofits and schools', v: restSum, p: restSum / tot}] : []), top[0].f);
const cats = D.catsum.slice().sort((a, b) => b.f - a.f);
bars($('catBars'), cats.map(c => ({n: `${c.c}: ${c.n}`, s: `${c.p} projects`, v: c.f, p: c.f / tot})), cats[0].f);
bars($('debBars'), D.debris.slice().sort((a, b) => b.f - a.f).slice(0, 10).map(x => ({n: nice(x.g), v: x.f})), Math.max(...D.debris.map(x => x.f)));

/* ledger */
const A = [...new Set(D.rows.map(r => r.a))].sort((a, b) => nice(a).localeCompare(nice(b)));
$('ledA').innerHTML += A.map(a => `<option value="${esc(a)}">${esc(nice(a))}</option>`).join('');
$('ledC').innerHTML += Object.entries(D.cats).map(([k, v]) => `<option value="${k}">${k}: ${esc(v)}</option>`).join('');
let shown = 50, cur = [];
/* sort: newest first, then applicant A to Z; any heading re-sorts */
const LCOLS = [{key: 'a', type: 'text', get: r => nice(r.a)}, {key: 't', type: 'text'}, {key: 'c', type: 'text'}, {key: 'f', type: 'num'}, {key: 'd1', type: 'date'}, {key: 'st', type: 'text'}];
const lsort = TT.attach($('ledT'), {cols: LCOLS, sort: {key: 'd1', dir: 'desc'}, onSort: () => filt()});
const lorder = rows => { const s = lsort.sort, c = LCOLS.find(x => x.key === s.key); return TT.sortBy(rows, [{get: c.get || (r => r[s.key]), type: c.type, dir: s.dir}, {get: r => r.d1, type: 'date', dir: 'desc'}, {get: r => nice(r.a), type: 'text', dir: 'asc'}, {get: r => r.t, type: 'text', dir: 'asc'}]); };
function filt() {
  const q = $('ledQ').value.trim().toLowerCase(), a = $('ledA').value, c = $('ledC').value;
  cur = D.rows.filter(r => (!a || r.a === a) && (!c || r.c === c) && (!q || (r.t + ' ' + r.a + ' ' + r.pw).toLowerCase().includes(q)));
  cur = lorder(cur);
  const s = cur.reduce((x, r) => x + r.f, 0);
  $('ledCount').textContent = `${cur.length.toLocaleString()} projects · ${big(s)} federal`;
  $('ledT').tBodies[0].innerHTML = cur.slice(0, shown).map(r => `<tr><td>${esc(nice(r.a))}</td><td class="wrap">${esc(r.t || '—')} <span class="muted small">#${esc(r.pw)}</span></td><td>${esc(r.c)}</td><td class="num">${usd(r.f)}</td><td class="num">${esc(r.d1 || '—')}</td><td class="small">${esc(r.st.replace('Project ', ''))}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No projects match.</td></tr>';
  $('ledMore').hidden = cur.length <= shown;
}
['ledQ', 'ledA', 'ledC'].forEach(id => $(id).addEventListener('input', () => { shown = 50; filt(); }));
$('ledMore').addEventListener('click', () => { shown += 100; filt(); });
$('ledCsv').addEventListener('click', () => {
  const head = ['applicant', 'project_number', 'title', 'category', 'federal_obligated', 'eligible_cost', 'first_obligation', 'last_obligation', 'status'];
  TT.csv('bay-county-fema-michael-projects', head, cur.map(r => [r.a, r.pw, r.t, r.c, r.f, r.e, r.d1, r.d2, r.st]));
  if (window.BCM) BCM.announce('Downloaded ' + cur.length + ' projects');
});
{ const q0 = new URL(location.href).searchParams.get('q'); if (q0) { $('ledQ').value = q0; requestAnimationFrame(() => $('led-h').scrollIntoView()); } }
filt();

/* households */
const ia = D.ia.slice().sort((a, b) => (b.t || 0) - (a.t || 0));
const n = v => v == null ? '—' : Math.round(v).toLocaleString('en-US');
$('iaT').innerHTML = `<thead><tr><th scope="col">City (mailing)</th><th scope="col" class="num">Owners registered</th><th scope="col" class="num">Owners approved</th><th scope="col" class="num">Owner aid</th><th scope="col" class="num">Renters registered</th><th scope="col" class="num">Renters approved</th><th scope="col" class="num">Renter aid</th><th scope="col" class="num">Total</th></tr></thead><tbody>` +
  ia.map(c => `<tr><th scope="row">${esc(String(c.city).toLowerCase().replace(/\b\w/g, m => m.toUpperCase()))}</th><td class="num">${n(c.oreg)}</td><td class="num">${n(c.oapp)}</td><td class="num">${c.oamt != null ? big(c.oamt) : '—'}</td><td class="num">${n(c.rreg)}</td><td class="num">${n(c.rapp)}</td><td class="num">${c.ramt != null ? big(c.ramt) : '—'}</td><td class="num"><b>${big(c.t)}</b></td></tr>`).join('') + '</tbody>';

/* CDBG-DR */
$('cdT').innerHTML = `<thead><tr><th scope="col">Recipient</th><th scope="col">Program</th><th scope="col">For</th><th scope="col" class="num">Award</th><th scope="col">Announced</th></tr></thead><tbody>` +
  D.cdbg.filter(x => x.amt).sort((a, b) => b.amt - a.amt).map(x => `<tr><th scope="row">${esc(x.r)}</th><td class="small">${esc(x.prog)}</td><td class="wrap small">${esc(x.p)}</td><td class="num">${x.rounded ? '~' : ''}${usd(x.amt)}</td><td class="small"><a href="${esc(x.u)}" target="_blank" rel="noopener">${esc(x.d || 'Source')}</a></td></tr>`).join('') + '</tbody>';

$('pdf').addEventListener('click', () => { document.querySelectorAll('.mi details').forEach(d => d.open = true); setTimeout(() => window.print(), 60); });
})();
