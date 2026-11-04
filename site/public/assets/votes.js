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
// people: one option and one link (?p=<person id>) per person, covering every spelling of their name in the minutes
const PEOPLE = D.people || {}, KEY2P = {};
Object.entries(PEOPLE).forEach(([pid, p]) => p.k.forEach(([g, n]) => { KEY2P[g + '|' + n] = pid; }));
const keysOf = m => !m ? null : m.startsWith('p:') ? (PEOPLE[m.slice(2)]?.k || []) : D.govs.map(([g]) => [g, m]);
const voteOf = (v, keys) => { for (const [g, n] of keys) { const x = v.g === g && v.m[n]; if (x && x !== 'unknown') return [n, x]; } return null; };
const labelOf = m => m.startsWith('p:') ? (PEOPLE[m.slice(2)]?.n || m.slice(2)) : m;
const F = {q: $('vtQ'), g: $('vtG'), m: $('vtM'), c: $('vtC'), y: $('vtY'), o: $('vtO'), sort: $('vtSort')};

// options
D.govs.forEach(([k, n]) => F.g.insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`));
Object.entries(D.cat).forEach(([k, n]) => { if (D.votes.some(v => v.c === k)) F.c.insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`); });
const YRS = [...new Set(D.votes.map(v => (v.d || '').slice(0, 4)).filter(Boolean))].sort().reverse();
YRS.forEach(y => F.y.insertAdjacentHTML('beforeend', `<option>${y}</option>`));
// opens on the newest year with votes; a search or member link (?q=, ?m=) looks across every year
{ const Q = new URLSearchParams(location.search); F.y.value = (Q.get('q') || Q.get('m') || Q.get('p')) ? 'all' : String(TT.startYear(YRS.map(Number), TT.countBy(D.votes.map(v => +(v.d || '').slice(0, 4) || null))) || 'all'); }
function members() { // members who appear in recorded roll calls, grouped by government
  const g = F.g.value, by = {};
  D.votes.forEach(v => { if (g && v.g !== g) return; Object.entries(v.m).forEach(([n, x]) => { if (x === 'unknown') return; const pid = KEY2P[v.g + '|' + n];
    (by[v.g] ||= new Map()).set(pid ? 'p:' + pid : n, pid ? PEOPLE[pid].n : n); }); });
  const keep = F.m.value;
  F.m.innerHTML = '<option value="">Anyone</option>' + D.govs.filter(([k]) => by[k]).map(([k, n]) => `<optgroup label="${esc(n)}">${[...by[k]].sort((a, b) => a[1].split(' ').pop().localeCompare(b[1].split(' ').pop()) || a[1].localeCompare(b[1])).map(([val, lab]) => `<option value="${esc(val)}">${esc(lab)}</option>`).join('')}</optgroup>`).join('');
  F.m.value = [...F.m.options].some(o => o.value === keep) ? keep : '';
}

// a person's yes / no / absent by year (same look as the profile's chart, people_pages.vote_years); a year picks that year
const YK = [['yes', 'yes', 'vy-yes'], ['no', 'no', 'vy-no'], ['absent', 'absent', 'vy-ab'], ['abstain', 'abstained', 'vy-ab']];
function yearChart(m, mk, rows) {
  const box = $('vtYears'), by = {}, t = {}; let lost = 0;
  rows.forEach(v => { const x = voteOf(v, mk)?.[1], y = +(v.d || '').slice(0, 4); if (!x || !y) return;
    (by[y] ||= {})[x] = (by[y][x] || 0) + 1; t[x] = (t[x] || 0) + 1; if ((x === 'no' && !failed(v)) || (x === 'yes' && failed(v))) lost++; });
  const ys = Object.keys(by).map(Number); if (!ys.length) { box.hidden = true; return; }
  const sum = c => Object.values(c).reduce((a, b) => a + b, 0), top = Math.max(...ys.map(y => sum(by[y]))), n = k => t[k] || 0, cast = n('yes') + n('no');
  const fmt = x => x.toLocaleString('en-US'), sel = F.y.value;
  let bars = '';
  for (let y = Math.min(...ys); y <= Math.max(...ys); y++) {
    const c = by[y] || {}, tot = sum(c);
    if (!tot) { bars += `<div class="vy-row vy-empty"><span class="vy-y">${y}</span><span class="vy-track"></span><span class="vy-c">No votes on file</span></div>`; continue; }
    const txt = YK.filter(([k]) => c[k]).map(([k, w]) => `${fmt(c[k])} ${w}`).join(' · ');
    bars += `<button type="button" class="vy-row${sel === String(y) ? ' on' : ''}" data-y="${y}" aria-pressed="${sel === String(y)}" aria-label="${y}: ${txt}"><span class="vy-y">${y}</span><span class="vy-track"><span class="vy-bar" style="width:${Math.max(2, Math.round(100 * tot / top))}%">${YK.filter(([k]) => c[k]).map(([k, , cls]) => `<i class="${cls}" style="flex:${c[k]}"></i>`).join('')}</span></span><span class="vy-c">${txt}</span></button>`;
  }
  // one decimal near the ends so 5 no votes in 1,254 never reads as 100% yes (same as people_pages._pct)
  const pct = (a, b) => { if (!b) return '0'; const x = 100 * a / b; return (x > 99.5 || x < 0.5) && a > 0 && a < b ? x.toFixed(1) : String(Math.round(x)); };
  const st = (l, v, s) => `<div><dt>${l}</dt><dd>${v}</dd><span>${s}</span></div>`;
  box.innerHTML = `<dl class="vy-stats">${st('Voted yes', pct(n('yes'), cast) + '%', `${fmt(n('yes'))} of ${fmt(cast)} yes or no votes`)}${st('Voted no', fmt(n('no')), `${cast ? (100 * n('no') / cast).toFixed(1) : 0}% of yes or no votes`)}${st('Missed', fmt(n('absent') + n('abstain')), 'absent or abstained')}${st('On the losing side', fmt(lost), 'voted no and it passed, or yes and it failed')}</dl>
    <figure class="vy" aria-label="${esc(labelOf(m))}'s votes by year"><figcaption class="vy-key"><span><i class="vy-yes"></i>Yes</span><span><i class="vy-no"></i>No</span><span><i class="vy-ab"></i>Absent or abstained</span><span class="muted">${esc(labelOf(m))}'s votes that match the other filters. Pick a year to list only its votes${sel !== 'all' ? ', or pick it again for every year' : ''}.</span></figcaption>${bars}</figure>`;
  box.hidden = false;
}
$('vtYears').addEventListener('click', ev => { const b = ev.target.closest('[data-y]'); if (!b) return;
  F.y.value = F.y.value === b.dataset.y ? 'all' : b.dataset.y; shown = 40; filt(); });

let shown = 40, last = [];
function filt(push = true) {
  const q = F.q.value.trim().toLowerCase(), g = F.g.value, m = F.m.value, mk = keysOf(m), c = F.c.value, y = F.y.value === 'all' ? '' : F.y.value, o = F.o.value;
  const keep = v => (!g || v.g === g) && (!c || v.c === c)
    && (!m || voteOf(v, mk))
    && (!o || (o === 'split' ? v.x : o === 'unan' ? !v.x && !failed(v) : failed(v)))
    && (!q || (v.h + ' ' + v.i + ' ' + (v.s || '') + ' ' + Object.keys(v.m).join(' ') + ' ' + (D.bodies[v.b]?.n || '')).toLowerCase().includes(q));
  const base = D.votes.filter(keep); // every filter but the year
  let cur = y ? base.filter(v => (v.d || '').startsWith(y)) : base;
  if (m) yearChart(m, mk, base);
  else $('vtYears').hidden = true;
  const sort = F.sort.value;
  // every order breaks ties newest first, then by item A to Z
  const az = (a, b) => (a.h || '').localeCompare(b.h || '', 'en', {numeric: true, sensitivity: 'base'}), nw = (a, b) => (b.d || '').localeCompare(a.d || '') || az(a, b);
  cur = cur.slice().sort(sort === 'old' ? (a, b) => (a.d || '').localeCompare(b.d || '') || az(a, b) : sort === 'amt' ? (a, b) => (b.a || 0) - (a.a || 0) || nw(a, b)
    : sort === 'close' ? (a, b) => margin(a) - margin(b) || nw(a, b) : sort === 'az' ? (a, b) => az(a, b) || nw(a, b) : nw);
  last = cur;
  const ns = cur.filter(v => v.x).length;
  $('vtCount').textContent = `${cur.length} vote${cur.length === 1 ? '' : 's'}${ns ? ` · ${ns} split` : ''}`;
  if (m) { const mine = cur.map(v => voteOf(v, mk)?.[1]); const c2 = k => mine.filter(x => x === k).length;
    const pid = m.startsWith('p:') ? m.slice(2) : '', prof = pid ? (window.BC?.href ? BC.href('person:' + pid) : '/people/' + pid) : '';
    $('vtMember').innerHTML = `<b>${prof ? `<a href="${esc(prof)}">${esc(labelOf(m))}</a>` : esc(labelOf(m))}</b>: yes ${c2('yes')} · no ${c2('no')}${c2('absent') ? ' · absent ' + c2('absent') : ''}${c2('abstain') ? ' · abstained ' + c2('abstain') : ''}`; }
  else $('vtMember').innerHTML = '';
  $('vtClear').hidden = !(q || g || m || c || y || o || sort !== 'new');
  $('vtList').innerHTML = cur.slice(0, shown).map(v => {
    const me = m ? voteOf(v, mk)?.[0] : null;
    const meta = [v.dn, D.cat[v.c] || v.c, v.a ? '$' + Math.round(v.a).toLocaleString('en-US') : ''].filter(Boolean).join(' · ');
    const ch = Object.entries(v.m).sort((a, b) => (ORD[a[1]] ?? 9) - (ORD[b[1]] ?? 9)).map(([n, x]) => `<span class="vchip v-${esc(x)}${n === me ? ' me' : ''}">${esc(n)} <b>${V[x] || esc(x)}</b></span>`).join('');
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
    [['q', q], ['g', g], ['m', m.startsWith('p:') ? '' : m], ['p', m.startsWith('p:') ? m.slice(2) : ''], ['c', c], ['y', F.y.value], ['o', o], ['sort', sort === 'new' ? '' : sort]].forEach(([k, val]) => val ? u.searchParams.set(k, val) : u.searchParams.delete(k));
    history.replaceState(null, '', u);
  }
}
// restore from link
const P0 = new URLSearchParams(location.search);
['q', 'g', 'c', 'y', 'o', 'sort'].forEach(k => { const val = P0.get(k); if (val != null && F[k]) F[k].value = val; });
members();
{ // ?p=<person id>, or an older ?m=<name> link: pick the person's one option when the name is theirs
  const want = P0.get('p') ? 'p:' + P0.get('p') : P0.get('m');
  if (want) { const has = val => [...F.m.options].some(o => o.value === val);
    const pid = !want.startsWith('p:') && Object.keys(PEOPLE).find(k => PEOPLE[k].k.some(([, n]) => n === want));
    F.m.value = has(want) ? want : pid && has('p:' + pid) ? 'p:' + pid : ''; } }
F.g.addEventListener('change', () => { members(); shown = 40; filt(); });
['q', 'm', 'c', 'y', 'o', 'sort'].forEach(k => F[k].addEventListener('input', () => { shown = 40; filt(); }));
$('vtClear').addEventListener('click', () => { F.q.value = ''; ['g', 'c', 'o'].forEach(k => F[k].value = ''); F.y.value = 'all'; F.sort.value = 'new'; members(); F.m.value = ''; shown = 40; filt(); });
$('vtMore').addEventListener('click', () => { shown += 60; filt(false); });
filt(false);
// the city bar at the top: keep the year on one this government has votes for
BCM.city.on(k => BCM.city.fitYear(F.y, D.votes.filter(v => !k || v.g === k).map(v => +(v.d || '').slice(0, 4) || null)));
if ([...P0.keys()].some(k => ['q', 'g', 'm', 'p', 'c', 'y', 'o', 'sort'].includes(k))) $('all').scrollIntoView();
$('vtCsv').addEventListener('click', () => {
  const gov = Object.fromEntries(D.govs);
  TT.csv(`baycounty-votes${F.g.value ? '-' + TT.slug(gov[F.g.value] || F.g.value) : ''}${F.m.value ? '-' + TT.slug(labelOf(F.m.value)) : ''}`,
    ['date', 'government', 'board', 'item', 'summary', 'category', 'amount', 'outcome', 'tally', 'split', 'member_votes', 'source'],
    last.map(v => [v.d, gov[v.g] || v.g, D.bodies[v.b]?.n || v.b, v.h, v.s, D.cat[v.c] || v.c, v.a ?? '', cap(v.o || ''), v.t, v.x ? 'yes' : 'no',
      Object.entries(v.m).map(([n, x]) => `${n}: ${x}`).join('; '), v.u]));
});
})();
