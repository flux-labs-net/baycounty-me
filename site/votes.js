(() => {
const D = __VT__;
const $ = id => document.getElementById(id);
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
[...new Set(D.votes.map(v => (v.d || '').slice(0, 4)).filter(Boolean))].sort().reverse().forEach(y => F.y.insertAdjacentHTML('beforeend', `<option>${y}</option>`));
function members() { // members who appear in recorded roll calls, grouped by government
  const g = F.g.value, by = {};
  D.votes.forEach(v => { if (g && v.g !== g) return; Object.entries(v.m).forEach(([n, x]) => { if (x === 'unknown') return; (by[v.g] ||= new Set()).add(n); }); });
  const keep = F.m.value;
  F.m.innerHTML = '<option value="">Anyone</option>' + D.govs.filter(([k]) => by[k]).map(([k, n]) => `<optgroup label="${esc(n)}">${[...by[k]].sort((a, b) => a.split(' ').pop().localeCompare(b.split(' ').pop())).map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('')}</optgroup>`).join('');
  F.m.value = [...F.m.options].some(o => o.value === keep) ? keep : '';
}

let shown = 40, view = [];
function filt(push = true) {
  const q = F.q.value.trim().toLowerCase(), g = F.g.value, m = F.m.value, c = F.c.value, y = F.y.value, o = F.o.value;
  let cur = D.votes.filter(v => (!g || v.g === g) && (!c || v.c === c) && (!y || (v.d || '').startsWith(y))
    && (!m || (v.m[m] && v.m[m] !== 'unknown'))
    && (!o || (o === 'split' ? v.x : o === 'unan' ? !v.x && !failed(v) : failed(v)))
    && (!q || (v.h + ' ' + v.i + ' ' + (v.s || '') + ' ' + Object.keys(v.m).join(' ') + ' ' + (D.bodies[v.b]?.n || '')).toLowerCase().includes(q)));
  const sort = F.sort.value;
  cur = cur.slice().sort(sort === 'old' ? (a, b) => (a.d || '').localeCompare(b.d || '') : sort === 'amt' ? (a, b) => (b.a || 0) - (a.a || 0) || (b.d || '').localeCompare(a.d || '')
    : sort === 'close' ? (a, b) => margin(a) - margin(b) || (b.d || '').localeCompare(a.d || '') : (a, b) => (b.d || '').localeCompare(a.d || ''));
  view = cur;
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
    [['q', q], ['g', g], ['m', m], ['c', c], ['y', y], ['o', o], ['sort', sort === 'new' ? '' : sort]].forEach(([k, val]) => val ? u.searchParams.set(k, val) : u.searchParams.delete(k));
    history.replaceState(null, '', u);
  }
}
// restore from link
const P0 = new URLSearchParams(location.search);
['q', 'g', 'c', 'y', 'o', 'sort'].forEach(k => { const val = P0.get(k); if (val != null && F[k]) F[k].value = val; });
members(); if (P0.get('m')) F.m.value = P0.get('m');
F.g.addEventListener('change', () => { members(); shown = 40; filt(); });
['q', 'm', 'c', 'y', 'o', 'sort'].forEach(k => F[k].addEventListener('input', () => { shown = 40; filt(); }));
$('vtClear').addEventListener('click', () => { F.q.value = ''; ['g', 'c', 'y', 'o'].forEach(k => F[k].value = ''); F.sort.value = 'new'; members(); F.m.value = ''; shown = 40; filt(); });
$('vtMore').addEventListener('click', () => { shown += 60; filt(false); });
$('vtCsv').addEventListener('click', () => { // one row per member per vote, for the votes in the current view
  const rows = [['date', 'government', 'board', 'item', 'type', 'amount', 'tally', 'outcome', 'split', 'member', 'member_vote', 'source_url']];
  const mf = F.m.value;
  view.forEach(v => { const base = [v.d, GN[v.g] || v.g, D.bodies[v.b]?.n || v.b, v.h, D.cat[v.c] || v.c, v.a || '', v.t || '', v.o || '', v.x ? 'yes' : 'no'];
    const ms = Object.entries(v.m).filter(([n]) => !mf || n === mf);
    if (!ms.length) rows.push(base.concat(['', '', v.u || '']));
    ms.forEach(([n, x]) => rows.push(base.concat([n, V[x] || x, v.u || '']))); });
  if (window.BCM) { BCM.download('bay-county-votes' + (mf ? '-' + mf.toLowerCase().replace(/[^a-z0-9]+/g, '-') : '') + '.csv', BCM.toCSV(rows)); BCM.announce('Downloaded ' + view.length + ' votes'); }
});
filt(false);
if ([...P0.keys()].some(k => ['q', 'g', 'm', 'c', 'y', 'o', 'sort'].includes(k))) $('all').scrollIntoView();
})();
