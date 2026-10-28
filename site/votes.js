(async () => {
const $ = id => document.getElementById(id);
let D; // page data loads after the page has rendered; the markup shows a loading note until then
// votes-page.json has the names and lists; each government's votes are in their own file
const getJ = async u => { const r = await fetch(u); if (!r.ok) throw new Error(r.status); return r.json(); };
try { D = await getJ('/data/votes-page.json');
  D.votes = D.votes || (await Promise.all(Object.values(D.files || {}).map(f => getJ(f.url)))).flatMap(x => x.votes || []);
  D.votes.sort((a, b) => (b.d || '').localeCompare(a.d || '')); }
catch (e) { $('vtCount').textContent = 'The votes could not be loaded. Please refresh the page.'; return; }
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const V = {yes: 'Yes', no: 'No', absent: 'Absent', abstain: 'Abstained', unknown: '?'}, ORD = {no: 0, yes: 1, abstain: 2, absent: 3, unknown: 4};
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
const GN = Object.fromEntries(D.govs);
const margin = v => { const m = /(\d+)\s*-\s*(\d+)/.exec(v.t || ''); return m ? Math.abs(+m[1] - +m[2]) : 99; };
const failed = v => /fail|denied|reject/i.test(v.o || '');
const F = {q: $('vtQ'), g: $('vtG'), m: $('vtM'), c: $('vtC'), y: $('vtY'), o: $('vtO'), sort: $('vtSort')};

// options
D.govs.forEach(([k, n]) => F.g.insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`));
Object.entries(D.cat).forEach(([k, n]) => { if (D.votes.some(v => v.c === k)) F.c.insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`); });
const YRS = [...new Set(D.votes.map(v => (v.d || '').slice(0, 4)).filter(Boolean))].sort().reverse();
YRS.forEach(y => F.y.insertAdjacentHTML('beforeend', `<option>${y}</option>`));
// opens on the newest year with votes; a search or member link (?q=, ?m=) looks across every year
{ const Q = new URLSearchParams(location.search); F.y.value = (Q.get('q') || Q.get('m')) ? 'all' : String(TT.startYear(YRS.map(Number), TT.countBy(D.votes.map(v => +(v.d || '').slice(0, 4) || null))) || 'all'); }
function members() { // members who appear in recorded roll calls, grouped by government
  const g = F.g.value, by = {};
  D.votes.forEach(v => { if (g && v.g !== g) return; Object.entries(v.m).forEach(([n, x]) => { if (x === 'unknown') return; (by[v.g] ||= new Set()).add(n); }); });
  const keep = F.m.value;
  F.m.innerHTML = '<option value="">Anyone</option>' + D.govs.filter(([k]) => by[k]).map(([k, n]) => `<optgroup label="${esc(n)}">${[...by[k]].sort((a, b) => a.split(' ').pop().localeCompare(b.split(' ').pop())).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('')}</optgroup>`).join('');
  F.m.value = [...F.m.options].some(o => o.value === keep) ? keep : '';
}

let shown = 40, last = [];
function filt(push = true) {
  const q = F.q.value.trim().toLowerCase(), g = F.g.value, m = F.m.value, c = F.c.value, y = F.y.value === 'all' ? '' : F.y.value, o = F.o.value;
  let cur = D.votes.filter(v => (!g || v.g === g) && (!c || v.c === c) && (!y || (v.d || '').startsWith(y))
    && (!m || (v.m[m] && v.m[m] !== 'unknown'))
    && (!o || (o === 'split' ? v.x : o === 'unan' ? !v.x && !failed(v) : failed(v)))
    && (!q || (v.h + ' ' + v.i + ' ' + (v.s || '') + ' ' + Object.keys(v.m).join(' ') + ' ' + (D.bodies[v.b]?.n || '')).toLowerCase().includes(q)));
  const sort = F.sort.value;
  // every order breaks ties newest first, then by item A to Z
  const az = (a, b) => (a.h || '').localeCompare(b.h || '', 'en', {numeric: true, sensitivity: 'base'}), nw = (a, b) => (b.d || '').localeCompare(a.d || '') || az(a, b);
  cur = cur.slice().sort(sort === 'old' ? (a, b) => (a.d || '').localeCompare(b.d || '') || az(a, b) : sort === 'amt' ? (a, b) => (b.a || 0) - (a.a || 0) || nw(a, b)
    : sort === 'close' ? (a, b) => margin(a) - margin(b) || nw(a, b) : sort === 'az' ? (a, b) => az(a, b) || nw(a, b) : nw);
  last = cur;
  const ns = cur.filter(v => v.x).length;
  $('vtCount').textContent = `${cur.length} vote${cur.length === 1 ? '' : 's'}${ns ? ` · ${ns} split` : ''}`;
  if (m) { const mine = cur.map(v => v.m[m]); const c2 = k => mine.filter(x => x === k).length;
    $('vtMember').innerHTML = `<b>${esc(m)}</b>: yes ${c2('yes')} · no ${c2('no')}${c2('absent') ? ' · absent ' + c2('absent') : ''}${c2('abstain') ? ' · abstained ' + c2('abstain') : ''}`; }
  else $('vtMember').innerHTML = '';
  $('vtClear').hidden = !(q || g || m || c || y || o || sort !== 'new');
  $('vtList').innerHTML = cur.slice(0, shown).map(v => {
    const meta = [v.dn, D.cat[v.c] || v.c, v.a ? '$' + Math.round(v.a).toLocaleString('en-US') : ''].filter(Boolean).join(' · ');
    const ch = Object.entries(v.m).sort((a, b) => (ORD[a[1]] ?? 9) - (ORD[b[1]] ?? 9)).map(([n, x]) => `<span class="vchip v-${esc(x)}${n === m ? ' me' : ''}">${esc(n)} <b>${V[x] || esc(x)}</b></span>`).join('');
    return `<li class="fd vt"><div class="vt-top"><span class="vt-board">${esc(D.bodies[v.b]?.n || v.b)}</span><span class="badge ${v.x || failed(v) ? 'warn' : 'ok'}">${esc(v.t || '')} ${esc(cap(v.o || ''))}</span></div>
      <span class="vt-meta muted">${esc(meta)}</span>
      <div class="vt-h">${esc(v.h)}</div>${v.s ? `<p class="vt-s">${esc(v.s)}</p>` : ''}
      ${ch ? `<p class="votes-row">${ch}</p>` : ''}
      ${v.u ? `<a class="src" href="${esc(v.u)}" target="_blank" rel="noopener" title="${esc(v.ut || '')}">${esc(v.ul)}</a>` : ''}</li>`;
  }).join('') || '<li class="muted">No votes match these filters.</li>';
  $('vtMore').hidden = cur.length <= shown;
  $('vtMore').textContent = `Show more (${(cur.length - shown).toLocaleString()} left)`;
  if (push) { // keep filters in the link so a view can be shared
    const u = new URL(location.href);
    [['q', q], ['g', g], ['m', m], ['c', c], ['y', F.y.value], ['o', o], ['sort', sort === 'new' ? '' : sort]].forEach(([k, val]) => val ? u.searchParams.set(k, val) : u.searchParams.delete(k));
    history.replaceState(null, '', u);
  }
}
// restore from link
const P0 = new URLSearchParams(location.search);
['q', 'g', 'c', 'y', 'o', 'sort'].forEach(k => { const val = P0.get(k); if (val != null && F[k]) F[k].value = val; });
members(); if (P0.get('m')) F.m.value = P0.get('m');
F.g.addEventListener('change', () => { members(); shown = 40; filt(); });
['q', 'm', 'c', 'y', 'o', 'sort'].forEach(k => F[k].addEventListener('input', () => { shown = 40; filt(); }));
$('vtClear').addEventListener('click', () => { F.q.value = ''; ['g', 'c', 'o'].forEach(k => F[k].value = ''); F.y.value = 'all'; F.sort.value = 'new'; members(); F.m.value = ''; shown = 40; filt(); });
$('vtMore').addEventListener('click', () => { shown += 60; filt(false); });
filt(false);
// the city bar at the top: keep the year on one this government has votes for
BCM.city.on(k => BCM.city.fitYear(F.y, D.votes.filter(v => !k || v.g === k).map(v => +(v.d || '').slice(0, 4) || null)));
if ([...P0.keys()].some(k => ['q', 'g', 'm', 'c', 'y', 'o', 'sort'].includes(k))) $('all').scrollIntoView();
$('vtCsv').addEventListener('click', () => {
  const gov = Object.fromEntries(D.govs);
  TT.csv(`baycounty-votes${F.g.value ? '-' + TT.slug(gov[F.g.value] || F.g.value) : ''}`,
    ['date', 'government', 'board', 'item', 'summary', 'category', 'amount', 'outcome', 'tally', 'split', 'member_votes', 'source'],
    last.map(v => [v.d, gov[v.g] || v.g, D.bodies[v.b]?.n || v.b, v.h, v.s, D.cat[v.c] || v.c, v.a ?? '', cap(v.o || ''), v.t, v.x ? 'yes' : 'no',
      Object.entries(v.m).map(([n, x]) => `${n}: ${x}`).join('; '), v.u]));
});
})();
