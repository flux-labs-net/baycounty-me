(async () => {
const $ = id => document.getElementById(id);
let D; // page data loads after the page has rendered; the markup shows a loading note until then
try { const r = await fetch('/data/contracts-page.json'); if (!r.ok) throw new Error(r.status); D = await r.json(); }
catch (e) { $('ctCount').textContent = 'The contracts could not be loaded. Please refresh the page.'; return; }
const R = D.rows, VP = D.vp;
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const usd = n => '$' + Math.round(n).toLocaleString('en-US');
const big = n => (n < 0 ? '\u2212' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(1) + 'M' : '$' + Math.round(Math.abs(n) / 1e3) + 'K');
let shown = 50, cur = [];
// year: opens on the newest year with contracts; ?year= in the link (a year or 'all') picks another
const YRS = [...new Set(R.map(r => +(r.d || '').slice(0, 4)).filter(Boolean))].sort((a, b) => b - a);
$('ctY').insertAdjacentHTML('beforeend', YRS.map(y => `<option value="${y}">${y}</option>`).join(''));
const QS = new URLSearchParams(location.search);
// a search or company link should find its record whatever the year
$('ctY').value = String(!QS.has('year') && (QS.get('q') || QS.get('v')) ? '' : TT.startYear(YRS));
/* sort: newest first, then vendor A to Z; any heading re-sorts */
const COLS = [{key: 'g', type: 'text'}, {key: 'v', type: 'text'}, {key: 'p', type: 'text'}, {key: 'a', type: 'num'}, {key: 'm', type: 'text'}, {key: 'd', type: 'date'}];
const sorter = TT.attach($('ctT'), {cols: COLS, sort: {key: 'd', dir: 'desc'}, onSort: () => filt()});
const order = rows => { const s = sorter.sort, c = COLS.find(x => x.key === s.key); return TT.sortBy(rows, [{get: r => r[s.key], type: c.type, dir: s.dir}, {get: r => r.d, type: 'date', dir: 'desc'}, {get: r => r.v, type: 'text', dir: 'asc'}]); };
function filt() {
  const q = $('ctQ').value.trim().toLowerCase(), g = $('ctG').value, m = $('ctM').value, y = $('ctY').value;
  cur = R.filter(r => (!g || r.g === g) && (!m || r.m === m) && (!y || (r.d || '').startsWith(y)) && (!q || (r.v + ' ' + r.p + ' ' + r.n).toLowerCase().includes(q)));
  cur = order(cur);
  $('ctCount').textContent = `${cur.length} contracts${y ? ' in ' + y : ''} · ${big(cur.reduce((a, r) => a + r.a, 0))}`;
  $('ctT').tBodies[0].innerHTML = cur.slice(0, shown).map(r => `<tr><td>${esc(r.g)}</td><td class="wrap"><button type="button" class="vbtn" data-v="${esc(r.id)}">${esc(r.v)}</button></td><td class="wrap small">${esc(r.p)}${r.n ? `<br><span class="muted">${esc(r.n)}</span>` : ''}</td><td class="num">${usd(r.a)}</td><td class="small">${esc(r.m)}</td><td class="small">${esc(r.d)} ${r.u ? `<a class="src" href="${esc(r.u)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="muted">No contracts match.</td></tr>';
  $('ctMore').hidden = cur.length <= shown;
}
['ctQ', 'ctG', 'ctM'].forEach(id => $(id).addEventListener('input', () => { shown = 50; filt(); }));
$('ctY').addEventListener('input', () => { shown = 50; if (window.BCM) BCM.urlState.set({year: $('ctY').value || 'all'}); filt(); });
$('ctMore').addEventListener('click', () => { shown += 100; filt(); });
$('ctCsv').addEventListener('click', () => {
  const rows = [['government', 'vendor', 'purpose', 'amount', 'method', 'method_as_stated', 'date', 'source_url', 'notes']].concat(cur.map(r => [r.g, r.v, r.p, r.a, r.m, r.mf, r.d, r.u, r.n]));
  TT.csv('baycounty-contracts', rows[0], rows.slice(1)); if (window.BCM) BCM.announce('Downloaded ' + cur.length + ' contracts');
});
filt();
// the city bar at the top picks the government (#ctG follows it); keep the year on one that city has contracts for
if (window.BCM && BCM.city) BCM.city.on(k => BCM.city.fitYear($('ctY'), R.filter(r => BCM.city.has(k, r.g)).map(r => +(r.d || '').slice(0, 4) || null)));

/* company cards: every record for one company, whatever spelling each record used */
const VBY = Object.fromEntries(VP.map(p => [p.id, p]));
const fdt = s => s ? new Date(s + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '';
const src = u => u ? ` <a class="src" href="${esc(u)}" target="_blank" rel="noopener">Source</a>` : '';
const named = VP.filter(p => p.t !== 'unnamed');
$('vpList').innerHTML = named.map(p => `<option value="${esc(p.n)}">`).join('');
const VSLUG = fetch('/data/vendor-slugs.json').then(r => r.json()).catch(() => ({}));  // vendor profile pages
function card(id, scroll) {
  const p = VBY[id], el = $('vpCard');
  if (!p) return;
  const sum = (a, k = 'a') => a.reduce((t, x) => t + (x[k] || 0), 0);
  const govs = [...new Set([...p.aw, ...p.paid].map(x => x.g))];
  const byGov = govs.map(g => { const aw = p.aw.filter(x => x.g === g), pd = p.paid.filter(x => x.g === g);
    return `<tr><th scope="row">${esc(g)}</th><td class="num">${aw.length || '—'}</td><td class="num">${aw.length ? big(sum(aw)) : '—'}</td><td class="num">${pd.length ? big(sum(pd)) + `<small class="muted vp-yr">${pd.map(x => `<span title="${esc(x.cover)}">FY${String(x.fy).slice(2)} ${big(x.a)} (#${x.rank})</span>`).join('<br>')}</small>` : '—'}</td></tr>`; }).join('');
  const kpi = (lbl, v, sub) => `<div class="kpi"><span class="eyebrow">${lbl}</span><span class="v">${v}</span><span class="s">${sub}</span></div>`;
  const offs = new Set(p.gifts.map(g => g.o));
  el.innerHTML = `<div class="vp-hd"><h3>${esc(p.n)}</h3>${p.t === 'public' ? '<span class="badge">Public agency</span>' : ''}</div>
    ${p.aka.length ? `<p class="small muted">Also written as: ${p.aka.map(esc).join(' · ')}</p>` : ''}
    <div class="kpis">${kpi('Contracts awarded', p.aw.length, p.aw.length ? big(p.tot) : 'none in this list')}
      ${kpi('Paid, where known', p.paid.length ? big(sum(p.paid)) : '—', p.paid.length ? 'in top-payee lists' : 'not a top payee in any register')}
      ${kpi('Change orders', p.co.length, p.co.length ? 'net ' + (sum(p.co) >= 0 ? '+' : '') + big(sum(p.co)) : 'none recorded')}
      ${kpi('Campaign gifts', p.gifts.length ? usd(sum(p.gifts)) : '—', p.gifts.length ? `to ${offs.size} current official${offs.size > 1 ? 's' : ''}` : 'none from the company')}</div>
    ${byGov ? `<h4>By government</h4><div class="tablewrap"><table class="tx-table vp-gov" data-tt="off"><thead><tr><th scope="col">Government</th><th scope="col" class="num">Awards</th><th scope="col" class="num">Awarded</th><th scope="col" class="num">Paid</th></tr></thead><tbody>${byGov}</tbody></table></div>
      <p class="note">Awards are contract amounts approved on agendas since October 2022. Payments come only from the lists of each register's biggest payees (Bay County's top 25, Lynn Haven's top 20; the number in parentheses is the company's rank), so a blank means the company wasn't in that list, not that it wasn't paid. Bay County's registers are missing some months, and Lynn Haven's lists show only checks of about $10,000 or more. Award and payment periods don't line up exactly. Other cities don't publish registers online.</p>` : ''}
    ${p.aw.length ? `<h4>Contracts</h4><ul class="plain mm-list vp-aw">${p.aw.map((a, i) => `<li${i >= 6 ? ' hidden' : ''}><b>${big(a.a)}</b> · ${esc(a.g)} · ${fdt(a.d)}<br>${esc(a.p)} <span class="muted small">(${esc(a.m)})</span>${src(a.u)}</li>`).join('')}</ul>${p.aw.length > 6 ? `<button type="button" class="pill sm" id="vpAll">Show all ${p.aw.length} contracts</button>` : ''}` : ''}
    ${p.co.length ? `<h4>Change orders</h4><ul class="plain mm-list">${p.co.map(a => `<li><b>${a.a == null ? 'amount not stated' : (a.a >= 0 ? '+' : '') + big(a.a)}</b>${typeof a.pct === 'number' ? ` (${a.pct.toFixed(0)}% of the original)` : ''} · ${esc(a.g)} · ${fdt(a.d)}<br>${esc(a.p)}${src(a.u)}</li>`).join('')}</ul>` : ''}
    ${p.em.length ? `<h4>Emergency purchases</h4><ul class="plain mm-list">${p.em.map(a => `<li><b>${a.a == null ? '' : big(a.a)}</b> · ${esc(a.g)} · ${fdt(a.d)}<br>${esc(a.p)}${src(a.u)}</li>`).join('')}</ul>` : ''}
    ${p.gifts.length ? `<h4>Campaign gifts from the company</h4><ul class="plain mm-list">${p.gifts.map(g => `<li><b>${esc(g.o)}</b>, ${esc(g.off)}: ${usd(g.a)}${g.dates && g.dates.length ? ' on ' + g.dates.map(fdt).join(', ') : ''}${g.same ? ' <span class="badge warn">their government pays this company</span>' : ''}</li>`).join('')}</ul>
      <p class="note">From current officials' latest campaign reports. Gifts from the company's owners or employees as individuals aren't linked to it.</p>` : ''}
    ${p.votes.length ? `<h4>Votes on this company's contracts by officials it gave to</h4><ul class="plain mm-list">${p.votes.map(v => `<li><b>${fdt(v.d)}</b> · ${esc(v.g)}: ${esc(v.h)}${v.a ? ' · ' + big(v.a) : ''}${v.consent ? ' <span class="muted">(consent agenda)</span>' : ''} · ${esc(v.outcome || '')} ${esc(v.tally || '')}${src(v.u)}<br><span class="small">${v.roll.map(m => m.gift ? `<b>${esc(m.n)}</b> ${esc(m.vote)} (got ${usd(m.gift)})` : `${esc(m.n)} ${esc(m.vote)}`).join(' · ')}</span></li>`).join('')}</ul>` : ''}
    ${p.gifts.length ? `<p><a class="pill" href="/connections/money-map?show=all&amp;q=${encodeURIComponent(p.mm || p.n)}#map">See it on the money map</a></p>` : ''}
    <p data-vprof="${esc(p.id)}" hidden><a class="pill" href="/public-money/vendors/${esc(p.id)}">Full vendor page</a></p>`;
  VSLUG.then(s => { const x = el.querySelector('[data-vprof]'); if (x && s.ids && s.ids[x.dataset.vprof]) x.hidden = false; });
  const all = $('vpAll'); if (all) all.addEventListener('click', () => { el.querySelectorAll('.vp-aw li[hidden]').forEach(li => li.hidden = false); all.remove(); });
  const u = new URL(location.href); u.searchParams.set('company', id); history.replaceState(null, '', u.pathname + u.search + '#company');
  if (scroll) $('company').scrollIntoView({behavior: 'smooth', block: 'start'});
}
document.addEventListener('click', ev => { const b = ev.target.closest('[data-v]'); if (b && VBY[b.dataset.v]) card(b.dataset.v, true); });
document.addEventListener('keydown', ev => { const b = ev.target.closest && ev.target.closest('.vlink'); if (b && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); card(b.dataset.v, true); } });
$('vpQ').addEventListener('change', () => { const q = $('vpQ').value.trim().toLowerCase(); const p = named.find(x => x.n.toLowerCase() === q) || named.find(x => x.n.toLowerCase().includes(q) || x.aka.some(a => a.toLowerCase().includes(q))); if (p) card(p.id, false); });
{ const c = new URLSearchParams(location.search).get('company'); if (c && VBY[c]) card(c, true); }
})();
