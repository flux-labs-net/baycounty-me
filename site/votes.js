(() => {
const D = __VT__;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const V = {yes: 'Yes', no: 'No', absent: 'Absent', abstain: 'Abstained', unknown: '?'};
Object.entries(D.bodies).forEach(([k, b]) => { if (D.votes.some(v => v.b === k)) $('vtB').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(b.n)}</option>`); });
Object.entries(D.cat).forEach(([k, n]) => $('vtC').insertAdjacentHTML('beforeend', `<option value="${k}">${esc(n)}</option>`));
let shown = 40;
function filt() {
  const q = $('vtQ').value.trim().toLowerCase(), b = $('vtB').value, c = $('vtC').value, s = $('vtS').checked;
  const cur = D.votes.filter(v => (!b || v.b === b) && (!c || v.c === c) && (!s || v.x) && (!q || (v.i + ' ' + (v.s || '') + ' ' + Object.keys(v.m).join(' ')).toLowerCase().includes(q)));
  $('vtCount').textContent = `${cur.length} votes`;
  $('vtList').innerHTML = cur.slice(0, shown).map(v => {
    const split = v.x;
    return `<li class="fd"><div class="fd-hd"><b>${esc(D.bodies[v.b]?.n || v.b)}</b> <span class="muted">${esc(v.d)} · ${esc(D.cat[v.c] || v.c)}${v.a ? ' · $' + Math.round(v.a).toLocaleString('en-US') : ''}</span> <span class="badge ${split ? 'warn' : 'ok'}">${esc(v.t || '')} ${esc(v.o || '')}</span></div>
      <div class="fd-t">${esc(v.s || v.i)}</div>${v.s ? `<p class="small muted">${esc(v.i)}</p>` : ''}
      ${Object.keys(v.m).length ? `<p class="votes-row">${Object.entries(v.m).map(([n, x]) => `<span class="vchip v-${esc(x)}">${esc(n)}: ${V[x] || esc(x)}</span>`).join('')}</p>` : ''}
      ${v.u ? `<a class="src" href="${esc(v.u)}" target="_blank" rel="noopener">${esc(v.ut || 'Minutes')}</a>` : ''}</li>`;
  }).join('') || '<li class="muted">No votes match.</li>';
  $('vtMore').hidden = cur.length <= shown;
}
['vtQ', 'vtB', 'vtC', 'vtS'].forEach(id => $(id).addEventListener('input', () => { shown = 40; filt(); }));
$('vtMore').addEventListener('click', () => { shown += 60; filt(); });
filt();
})();
