(() => {
const D = __VT__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const V = {yes: 'Yes', no: 'No', absent: 'Absent', abstain: 'Abstained', unknown: '?'}, ORD = {no: 0, yes: 1, abstain: 2, absent: 3, unknown: 4};
const cap = s => s ? s[0].toUpperCase() + s.slice(1) : '';
Object.entries(D.bodies).forEach(([k, b]) => { if (D.votes.some(v => v.b === k)) $('vtB').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(b.n)}</option>`); });
Object.entries(D.cat).forEach(([k, n]) => $('vtC').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`));
let shown = 40;
function filt() {
  const q = $('vtQ').value.trim().toLowerCase(), b = $('vtB').value, c = $('vtC').value, s = $('vtS').checked;
  const cur = D.votes.filter(v => (!b || v.b === b) && (!c || v.c === c) && (!s || v.x) && (!q || (v.h + ' ' + v.i + ' ' + (v.s || '') + ' ' + Object.keys(v.m).join(' ')).toLowerCase().includes(q)));
  $('vtCount').textContent = `${cur.length} votes`;
  $('vtList').innerHTML = cur.slice(0, shown).map(v => {
    const split = v.x;
    const meta = [v.dn, D.cat[v.c] || v.c, v.a ? '$' + Math.round(v.a).toLocaleString('en-US') : ''].filter(Boolean).join(' \u00b7 ');
    const ch = Object.entries(v.m).sort((a, b) => (ORD[a[1]] ?? 9) - (ORD[b[1]] ?? 9)).map(([n, x]) => `<span class="vchip v-${esc(x)}">${esc(n)} <b>${V[x] || esc(x)}</b></span>`).join('');
    return `<li class="fd vt"><div class="vt-top"><span class="vt-board">${esc(D.bodies[v.b]?.n || v.b)}</span><span class="badge ${split ? 'warn' : 'ok'}">${esc(v.t || '')} ${esc(cap(v.o || ''))}</span></div>
      <span class="vt-meta muted">${esc(meta)}</span>
      <div class="vt-h">${esc(v.h)}</div>${v.s ? `<p class="vt-s">${esc(v.s)}</p>` : ''}
      ${ch ? `<p class="votes-row">${ch}</p>` : ''}
      ${v.u ? `<a class="src" href="${esc(v.u)}" target="_blank" rel="noopener" title="${esc(v.ut || '')}">${esc(v.ul)}</a>` : ''}</li>`;
  }).join('') || '<li class="muted">No votes match.</li>';
  $('vtMore').hidden = cur.length <= shown;
}
['vtQ', 'vtB', 'vtC', 'vtS'].forEach(id => $(id).addEventListener('input', () => { shown = 40; filt(); }));
$('vtMore').addEventListener('click', () => { shown += 60; filt(); });
const q0 = new URLSearchParams(location.search).get('q'); if (q0) $('vtQ').value = q0;
filt();
if (q0) $('all').scrollIntoView();
})();
