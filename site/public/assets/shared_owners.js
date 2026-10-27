// /connections/shared-owners: confirmed shared-owner groups from /api/v1/datasets/shared-owner-groups (no person names).
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => '$' + Number(n || 0).toLocaleString('en-US', {maximumFractionDigits: 0});
  const title = s => window.BCNames ? BCNames.bizCase(String(s || '')) : String(s || '');  // api/_names.js, in site.js
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
    $('#soYears').innerHTML = per.size > 1 ? [...per].map(([k, t]) => `<button type="button" class="so-yr" data-y="${esc(k)}"><b>${esc(k)}</b><span>${usd(t.d)}</span><small>${t.n} owner group${t.n === 1 ? '' : 's'}</small></button>`).join('') : '';
    // one card per candidate and election; each owner group is a section inside it
    const cards = new Map();
    for (const g of gs) {
      const k = g.candidate + '|' + (g.election || '');
      if (!cards.has(k)) cards.set(k, {candidate: g.candidate, office: g.office, election: g.election, report: g.campaign_report_url, groups: []});
      cards.get(k).groups.push(g);
    }
    const list = [...cards.values()].map(c => ({...c, total: c.groups.reduce((a, g) => a + Number(g.group_total), 0), nb: c.groups.reduce((a, g) => a + Number(g.group_businesses), 0)}))
      .sort((a, b) => yearOf(b).localeCompare(yearOf(a)) || b.total - a.total || a.candidate.localeCompare(b.candidate));
    $('#soCount').textContent = gs.length ? `${list.length} candidate${list.length === 1 ? '' : 's'}, ${gs.length} owner group${gs.length === 1 ? '' : 's'}, ${usd(gs.reduce((a, g) => a + Number(g.group_total), 0))} in all` : '';
    const section = (g, i, many) => `<section class="so-grp">
      ${many ? `<div class="so-gh"><b>Owner group ${i + 1}</b><span>${usd(g.group_total)}</span></div>` : ''}
      <div class="so-tags"><span class="so-tag">${g.group_businesses} businesses</span><span class="so-tag">${g.group_checks} check${g.group_checks === 1 ? '' : 's'}</span>
        <span class="so-tag">linked by ${g.shared_people} shared ${g.shared_people === 1 ? 'person' : 'people'}</span>
        ${written(g) ? `<span class="so-tag">written ${esc(written(g))}</span>` : ''}
        ${g.all_checks_1000 ? '<span class="so-tag">every check $1,000</span>' : ''}${g.same_day ? '<span class="so-tag">all the same day</span>' : ''}</div>
      <table class="so-biz" data-tt="off"><tbody>${g.businesses.sort((a, b) => b.business_amount - a.business_amount).map(b => `<tr>
        <td>${b.sunbiz_doc_number && window.BC ? BC.a('business:' + String(b.sunbiz_doc_number).toLowerCase(), title(b.business)) : esc(title(b.business))}${b.source_url ? ` <a class="src" href="${esc(b.source_url)}" target="_blank" rel="noopener">Sunbiz</a>` : ''}${window.BCM_bizOff ? BCM_bizOff(b.business_status, b.business_last_filed) : ''}<small>${b.business_status === 'Active' ? 'Active' : ''}${b.business_dates ? (b.business_status === 'Active' ? ' · ' : '') + 'gave ' + esc(window.BCM_usDate ? BCM_usDate(b.business_dates) : b.business_dates) : ''}</small></td>
        <td class="num">${usd(b.business_amount)}</td></tr>`).join('')}</tbody></table></section>`;
    $('#soList').innerHTML = list.map(c => {
      const many = c.groups.length > 1;
      c.groups.sort((a, b) => b.group_total - a.group_total);
      return `<article class="so-c">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap">
        <div><h3>${esc(c.candidate)}</h3><div class="so-meta">${esc(c.office || '')}${c.election ? ' · ' + esc(c.election) : ''}</div></div>
        <div class="so-total">${usd(c.total)}</div></div>
      <p class="so-sum">${many ? `${c.nb} businesses in <b>${c.groups.length} separate owner groups</b>. Each group shares an officer, manager or agent; the groups don't share anyone.` : `${c.nb} businesses that share an officer, manager or agent.`}</p>
      ${c.groups.map((g, i) => section(g, i, many)).join('')}
      ${c.report ? `<p class="small" style="margin:10px 0 0"><a href="${esc(c.report)}" target="_blank" rel="noopener">Campaign finance report</a></p>` : ''}
    </article>`;
    }).join('') || '<p class="muted">No groups have been checked and listed yet.</p>';
  }

  // gifts over the per-election limit, confirmed or resolved by an admin (/api/v1/datasets/over-limit-gifts)
  const RES = {reporting_error: 'Reporting error', amended_report: 'Corrected in an amended report', refunded: 'Refunded', designated_general: 'Designated for the general election',
    elections_commission: 'Florida Elections Commission ruling', other: 'Explained'};
  async function loadLimits() {
    let rows = [];
    try {
      const r = await fetch('/api/v1/datasets/over-limit-gifts?limit=1000');
      if (!r.ok) throw new Error();
      rows = (await r.json()).data || [];
    } catch (e) { $('#olList').innerHTML = '<p class="muted">Couldn’t load this list. Try again in a moment.</p>'; return; }
    rows.sort((a, b) => (a.status === 'Open' ? 0 : 1) - (b.status === 'Open' ? 0 : 1) || String(b.last_date).localeCompare(String(a.last_date)));
    const ud = t => window.BCM_usDate ? BCM_usDate(t) : t;
    $('#olList').innerHTML = rows.map(c => `<article class="ol-c">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap">
        <div><h3>${esc(title(c.contributor))} to ${esc(c.candidate)}<span class="ol-st ${c.status === 'Resolved' ? 'res' : 'open'}">${c.status === 'Resolved' ? 'Resolved' : 'Open'}</span></h3>
          <div class="so-meta">${esc(c.office || '')}${c.election ? ' · ' + esc(c.election) : ''}${c.election_phase ? ' · ' + esc(c.election_phase) + ' election' : ''}</div></div>
        <div style="text-align:right"><div class="so-total">${usd(c.net_amount)}</div><div class="small muted">${Number(c.over_by) > 0 ? usd(c.over_by) + ' over the limit as reported' : 'within the limit after refunds'}</div></div></div>
      <div class="small">${esc(ud(String(c.gift_list || ''))).split('; ').join('<br>')}</div>
      ${Number(c.refunds) > 0 ? `<div class="small muted">${usd(c.refunds)} refunded</div>` : ''}
      ${c.status === 'Resolved' ? `<div class="ol-res"><b>${esc(RES[c.resolution] || 'Explained')}.</b> ${esc(c.resolution_note || '')}${c.resolution_url ? ` <a href="${esc(c.resolution_url)}" target="_blank" rel="noopener">Source</a>` : ''}</div>` : ''}
      ${c.source_url ? `<p class="small" style="margin:10px 0 0"><a href="${esc(c.source_url)}" target="_blank" rel="noopener">Campaign finance report</a></p>` : ''}
    </article>`).join('') || '<p class="muted">No cases have been checked and listed yet.</p>';
  }

  $('#soC').addEventListener('change', render);
  $('#soY').addEventListener('change', render);
  $('#soYears').addEventListener('click', e => { const b = e.target.closest('.so-yr'); if (!b || b.dataset.y === 'Other') return; $('#soY').value = b.dataset.y; render(); });
  load();
  loadLimits();
})();
