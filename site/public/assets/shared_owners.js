// /connections/shared-owners: confirmed shared-owner groups from /api/v1/datasets/shared-owner-groups (no person names).
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => '$' + Number(n || 0).toLocaleString('en-US', {maximumFractionDigits: 0});
  const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Llc|Inc|Pa|Lp|Llp|Pllc)\b/g, m => m.toUpperCase());
  let groups = [];
  const yearOf = g => (String(g.election || '').match(/\b(19|20)\d\d\b/) || [''])[0];

  async function load() {
    let rows = [];
    try {
      const r = await fetch('/api/v1/datasets/shared-owner-groups?limit=1000');
      if (!r.ok) throw new Error();
      rows = (await r.json()).data || [];
    } catch (e) { $('#soList').innerHTML = '<p class="muted">Couldn’t load the list. Try again in a moment.</p>'; return; }
    const by = new Map();
    for (const x of rows) {
      const k = x.group_id + '|' + x.candidate;
      if (!by.has(k)) by.set(k, {...x, businesses: []});
      by.get(k).businesses.push(x);
    }
    groups = [...by.values()].sort((a, b) => yearOf(b).localeCompare(yearOf(a)) || b.group_total - a.group_total || a.candidate.localeCompare(b.candidate));
    const years = [...new Set(groups.map(yearOf).filter(Boolean))].sort().reverse();
    $('#soY').innerHTML = '<option value="">All elections</option>' + years.map(y => `<option value="${y}">${y} elections</option>`).join('');
    const cands = [...new Set(groups.map(g => g.candidate))].sort();
    $('#soC').innerHTML = '<option value="">All candidates</option>' + cands.map(c => `<option>${esc(c)}</option>`).join('');
    render();
  }

  // when the checks were written, e.g. "Oct 2023" or "Aug 2023 to Jan 2024" (often a year before the election)
  const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function written(g) {
    const ds = g.businesses.flatMap(b => String(b.business_dates || '').match(/\d{4}-\d\d-\d\d/g) || []).sort();
    if (!ds.length) return '';
    const m = d => MON[+d.slice(5, 7) - 1] + ' ' + d.slice(0, 4);
    return m(ds[0]) === m(ds[ds.length - 1]) ? m(ds[0]) : m(ds[0]) + ' to ' + m(ds[ds.length - 1]);
  }

  function render() {
    const c = $('#soC').value, y = $('#soY').value;
    const gs = groups.filter(g => (!c || g.candidate === c) && (!y || yearOf(g) === y));
    // totals by election year for what's shown
    const per = new Map();
    for (const g of gs) { const k = yearOf(g) || 'Other'; const t = per.get(k) || {n: 0, d: 0}; t.n++; t.d += Number(g.group_total); per.set(k, t); }
    $('#soYears').innerHTML = per.size > 1 ? [...per].map(([k, t]) => `<button type="button" class="so-yr" data-y="${esc(k)}"><b>${esc(k)}</b><span>${usd(t.d)}</span><small>${t.n} group${t.n === 1 ? '' : 's'}</small></button>`).join('') : '';
    $('#soCount').textContent = gs.length ? `${gs.length} group${gs.length === 1 ? '' : 's'}, ${usd(gs.reduce((a, g) => a + Number(g.group_total), 0))} in all` : '';
    $('#soList').innerHTML = gs.map(g => `<article class="so-c">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap">
        <div><h3>${g.group_businesses} businesses gave to ${esc(g.candidate)}</h3><div class="so-meta">${esc(g.office || '')}${g.election ? ' · ' + esc(g.election) : ''}${written(g) ? ' · checks written ' + esc(written(g)) : ''}</div></div>
        <div class="so-total">${usd(g.group_total)}</div></div>
      <div class="so-tags"><span class="so-tag">${g.group_checks} check${g.group_checks === 1 ? '' : 's'}</span>
        <span class="so-tag">linked by ${g.shared_people} shared ${g.shared_people === 1 ? 'person' : 'people'}</span>
        ${g.all_checks_1000 ? '<span class="so-tag">every check $1,000</span>' : ''}${g.same_day ? '<span class="so-tag">all the same day</span>' : ''}</div>
      <table class="so-biz"><tbody>${g.businesses.sort((a, b) => b.business_amount - a.business_amount).map(b => `<tr>
        <td><a href="${esc(b.source_url)}" target="_blank" rel="noopener">${esc(title(b.business))}</a>${window.BCM_bizOff ? BCM_bizOff(b.business_status, b.business_last_filed) : ''}<small>${b.business_status === 'Active' ? 'Active' : ''}${b.business_dates ? (b.business_status === 'Active' ? ' · ' : '') + 'gave ' + esc(window.BCM_usDate ? BCM_usDate(b.business_dates) : b.business_dates) : ''}</small></td>
        <td class="num">${usd(b.business_amount)}</td></tr>`).join('')}</tbody></table>
      ${g.campaign_report_url ? `<p class="small" style="margin:10px 0 0"><a href="${esc(g.campaign_report_url)}" target="_blank" rel="noopener">Campaign finance report</a></p>` : ''}
    </article>`).join('') || '<p class="muted">No groups have been checked and listed yet.</p>';
  }

  $('#soC').addEventListener('change', render);
  $('#soY').addEventListener('change', render);
  $('#soYears').addEventListener('click', e => { const b = e.target.closest('.so-yr'); if (!b || b.dataset.y === 'Other') return; $('#soY').value = b.dataset.y; render(); });
  load();
})();
