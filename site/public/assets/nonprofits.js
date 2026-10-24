// /connections/nonprofits: reads the nonprofits, nonprofit-payments, nonprofit-grants, nonprofit-officials and
// charity-registrations (FDACS) datasets from /api/v1, and nonprofit-board-members / nonprofit-board-businesses per nonprofit or person when a row opens. Officials are tagged only when an
// admin confirmed the name match.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => n == null || n === '' ? '—' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  const num = n => Number(n || 0).toLocaleString('en-US');
  const title = s => String(s || '').toLowerCase().replace(/(^|[^a-z'’])([a-z])/g, (m, a, b) => a + b.toUpperCase()).replace(/\b(Llc|Inc|Pa|Usa|Us|Ymca|Ywca|Vfw|Pta|Pto|Cra|Cdc|Ii|Iii)\b/g, m => m.toUpperCase());
  const HOA = 'Homeowner or condo association';
  const PAGE = 60;
  let orgs = [], pays = new Map(), grants = new Map(), offs = new Map(), regs = new Map(), shown = PAGE;
  const active = s => /^(active|registered)\b/i.test(s || '');  // FDACS: small charities are Active, larger ones Registered
  const pct = (a, b) => a != null && b ? ` (${Math.round(100 * a / b)}%)` : '';

  async function fromApi(id) {
    let out = [], url = `/api/v1/datasets/${id}?limit=1000`;
    for (let i = 0; url && i < 20; i++) {
      const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 20000);
      let r;
      try { r = await fetch(url, {signal: ctl.signal}); } finally { clearTimeout(t); }
      if (!r.ok) throw new Error(id);
      const j = await r.json();
      out = out.concat(j.data || []);
      url = j.meta && j.meta.next ? j.meta.next.replace(/^https?:\/\/[^/]+/, '') : null;
    }
    return out;
  }
  // The API first; if it fails, is slow or comes back empty (e.g. mid-sync), the published download of the same dataset.
  async function all(id) {
    try { const rows = await fromApi(id); if (rows.length) return rows; } catch (e) { /* fall through */ }
    const r = await fetch(`/downloads/${id}.json`);
    if (!r.ok) throw new Error(id);
    const d = await r.json();
    return Array.isArray(d) ? d : (d.rows || d.data || []);
  }
  const people = new Map();  // person_id -> rows (every board that name sits on)
  async function rowsOf(ds, q) {
    const r = await fetch(`/api/v1/datasets/${ds}?${q}&limit=1000`);
    if (!r.ok) throw new Error(ds);
    return (await r.json()).data || [];
  }
  const boardOf = q => rowsOf('nonprofit-board-members', q);
  const bizLine = b => `<a href="${esc(b.source_url)}" target="_blank" rel="noopener">${esc(title(b.business))}</a>${b.business_status === 'Active' ? '' : ' <span class="muted">(inactive)</span>'}`
    + (Number(b.campaign_gifts_total) > 0 ? ` <span class="muted">gave ${usd(b.campaign_gifts_total)} to campaigns${b.candidates ? ' (' + esc(b.candidates) + ')' : ''}</span>` : '')
    + (b.match === 'Name' ? ' <span class="muted">· name match</span>' : '');
  const years = r => r.first_year && r.last_year && r.first_year !== r.last_year ? `${r.first_year}–${r.last_year}` : (r.last_year || '');
  const pname = s => String(s || '').replace(/\b([A-Z])([A-Z']+)\b/g, (m, a, b) => a + b.toLowerCase());
  const group = (rows, key) => rows.reduce((m, r) => (r[key] && (m.get(r[key]) || m.set(r[key], []).get(r[key])).push(r), m), new Map());

  async function load() {
    let o, p, g, f, c;
    try { [o, p, g, f, c] = await Promise.all([all('nonprofits'), all('nonprofit-payments'), all('nonprofit-grants'), all('nonprofit-officials').catch(() => []),
      all('charity-registrations').catch(() => [])]); }
    catch (e) { $('#npList').innerHTML = '<p class="muted">Couldn’t load the list. Try again in a moment.</p>'; $('#npOff').innerHTML = ''; return; }
    orgs = o; pays = group(p, 'nonprofit_id'); grants = group(g, 'grantor_id'); offs = group(f, 'nonprofit_id');
    regs = new Map(c.map(r => [r.nonprofit_id, r]));
    const kinds = [...new Set(orgs.map(x => x.kind).filter(k => k && k !== HOA))].sort();
    $('#npK').innerHTML = '<option value="">All types</option>' + kinds.map(k => `<option>${esc(k)}</option>`).join('') + `<option>${HOA}</option>`;
    const cities = [...new Set(orgs.map(x => x.city).filter(Boolean))].sort();
    $('#npC').innerHTML = '<option value="">All cities</option>' + cities.map(c => `<option>${esc(c)}</option>`).join('');
    const irs = orgs.filter(x => x.irs_recognized);
    const paid = orgs.filter(x => x.gov_payment_records > 0);
    $('#npKpis').innerHTML = [[num(orgs.length), 'nonprofits'], [num(irs.length), 'recognized by the IRS'],
      [usd(orgs.reduce((a, x) => a + Number(x.total_revenue || 0), 0)), 'revenue on latest 990s'],
      ...(c.length ? [[num(orgs.filter(x => active(x.fdacs_status)).length), 'registered Florida charities']] : []), [num(paid.length), 'paid in government records'],
      [num(new Set(f.map(x => x.official_id)).size), 'officials on boards (checked)']]
      .map(([v, l]) => `<div class="np-kpi"><b>${v}</b><span>${l}</span></div>`).join('');
    renderOfficials(f);
    renderInterlocks();
    renderDonors();
    const want = new URLSearchParams(location.search).get('id');
    if (want) { const x = orgs.find(r => r.nonprofit_id === want); if (x) { $('#npQ').value = x.ein || x.name; if (x.kind === HOA) $('#npHoa').checked = true; } }
    render(want);
  }

  function renderOfficials(f) {
    const by = group(f, 'official_id');
    $('#npOff').innerHTML = [...by.values()].sort((a, b) => a[0].official.localeCompare(b[0].official)).map(rs => `<article>
      <h3>${esc(rs[0].official)}</h3><div class="m">${esc(String(rs[0].official_roles || '').replace(/[[\]"]/g, '').split(',').slice(0, 1).join(''))}</div>
      <ul class="plain">${rs.map(r => `<li><a href="?id=${encodeURIComponent(r.nonprofit_id)}#npList">${esc(title(r.nonprofit))}</a> <span class="muted small">${esc(r.titles || '')}${r.last_year ? ' · ' + esc(r.first_year && r.first_year !== r.last_year ? r.first_year + '–' + r.last_year : r.last_year) : ''}${r.current ? '' : ' · past'} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources || 'source')}</a></span></li>`).join('')}</ul></article>`).join('')
      || '<p class="muted">No board seats have been checked and listed yet.</p>';
  }

  async function renderInterlocks() {
    let rows = [];
    try { rows = await boardOf('current=true&role=Board&other_current_boards_min=1'); } catch (e) { $('#npMulti').innerHTML = ''; return; }
    const hoa = new Set(orgs.filter(x => x.kind === HOA).map(x => x.nonprofit_id));
    const by = group(rows.filter(r => !hoa.has(r.nonprofit_id)), 'person_id');
    const list = [...by.values()].filter(rs => rs.length >= 2).sort((a, b) => b.length - a.length || a[0].person.localeCompare(b[0].person)).slice(0, 40);
    $('#npMulti').innerHTML = list.map(rs => `<article><h3><button type="button" class="np-p" data-person="${esc(rs[0].person_id)}">${esc(pname(rs[0].person))}</button></h3><div class="m">${rs.length} current boards</div>
      <ul class="plain">${rs.map(r => `<li><a href="?id=${encodeURIComponent(r.nonprofit_id)}#npList">${esc(title(r.nonprofit))}</a> <span class="muted small">${esc(r.titles || '')}</span></li>`).join('')}</ul></article>`).join('')
      || '<p class="muted">No one sits on more than one current board.</p>';
  }

  async function renderDonors() {
    let rows = [];
    try { rows = await rowsOf('nonprofit-board-businesses', 'campaign_gifts_total_min=1'); } catch (e) { $('#npDon').innerHTML = ''; return; }
    const by = group(rows, 'person_id');
    const tot = rs => rs.reduce((a, b) => a + Number(b.campaign_gifts_total || 0), 0);
    const list = [...by.values()].sort((a, b) => tot(b) - tot(a) || a[0].person.localeCompare(b[0].person)).slice(0, 60);
    $('#npDon').innerHTML = list.map(rs => `<article><h3><button type="button" class="np-p" data-person="${esc(rs[0].person_id)}">${esc(pname(rs[0].person))}</button></h3><div class="m">${usd(tot(rs))} from ${rs.length} business${rs.length === 1 ? '' : 'es'}</div>
      <ul class="plain">${rs.map(b => `<li>${bizLine(b)}</li>`).join('')}</ul></article>`).join('')
      || '<p class="muted">No board member’s business gave to a local campaign.</p>';
  }

  async function showPerson(btn) {
    const id = btn.dataset.person;
    const host = btn.closest('li, tr, article');
    const tr = host.tagName === 'TR';
    const old = tr ? (host.nextElementSibling && host.nextElementSibling.classList.contains('np-ppr') ? host.nextElementSibling : null) : host.querySelector('.np-pp');
    if (old) { old.remove(); return; }
    let rs = people.get(id);
    if (!rs) {
      try {
        const [b, z] = await Promise.all([boardOf('person_id=' + encodeURIComponent(id)), rowsOf('nonprofit-board-businesses', 'person_id=' + encodeURIComponent(id)).catch(() => [])]);
        rs = Object.assign(b, {biz: z}); people.set(id, rs);
      } catch (e) { return; }
    }
    const d = document.createElement('div'); d.className = 'np-pp small';
    d.innerHTML = `<b>${esc(pname(rs[0] && rs[0].person))}</b> on ${rs.length} nonprofit${rs.length === 1 ? '' : 's'}: ` + rs.map(r => `<a href="?id=${encodeURIComponent(r.nonprofit_id)}#npList">${esc(title(r.nonprofit))}</a> <span class="muted">(${esc(r.titles || r.role)}${years(r) ? ', ' + esc(years(r)) : ''}${r.current ? '' : ', past'})</span>`).join(' · ')
      + (rs.biz && rs.biz.length ? `<div>Businesses (state filings): ${rs.biz.filter(b => b.business_status === 'Active' || Number(b.campaign_gifts_total) > 0).concat(rs.biz.filter(b => b.business_status !== 'Active' && !(Number(b.campaign_gifts_total) > 0))).slice(0, 12).map(bizLine).join(' · ')}${rs.biz.length > 12 ? ` <span class="muted">and ${rs.biz.length - 12} more</span>` : ''}</div>` : '')
      + '<div class="muted">Grouped by name, so two people with the same name can show up together.</div>';
    if (!tr) { host.appendChild(d); return; }
    // a row of its own under the person, so a long list wraps instead of stretching the table
    const row = document.createElement('tr'); row.className = 'np-ppr';
    const td = document.createElement('td'); td.colSpan = host.children.length; td.appendChild(d);
    row.appendChild(td); host.after(row);
  }

  function filtered() {
    const q = $('#npQ').value.trim().toLowerCase(), k = $('#npK').value, c = $('#npC').value, s = $('#npS').value;
    const hoa = $('#npHoa').checked || k === HOA, gov = $('#npGov').checked, fd = $('#npFd').checked;
    const digits = q.replace(/\D/g, '');
    let rs = orgs.filter(x => (!k || x.kind === k) && (!c || x.city === c) && (hoa || x.kind !== HOA) && (!gov || x.gov_payment_records > 0) && (!fd || x.fdacs_registration)
      && (!q || x.name.toLowerCase().includes(q) || String(x.city || '').toLowerCase().includes(q) || (digits.length >= 4 && String(x.ein || '').includes(digits))));
    const rev = x => Number(x.total_revenue ?? x.irs_revenue ?? x.fdacs_revenue ?? 0);
    const cmp = {rev: (a, b) => rev(b) - rev(a), gov: (a, b) => (b.gov_dollars_in_records || 0) - (a.gov_dollars_in_records || 0) || rev(b) - rev(a),
      board: (a, b) => (b.shares_board_with || 0) - (a.shares_board_with || 0) || rev(b) - rev(a), name: (a, b) => a.name.localeCompare(b.name)}[s];
    return rs.sort(cmp);
  }

  function render(open) {
    const rs = filtered();
    $('#npCount').textContent = `${num(rs.length)} nonprofit${rs.length === 1 ? '' : 's'}`;
    $('#npList').innerHTML = rs.slice(0, shown).map(x => {
      const o = offs.get(x.nonprofit_id) || [];
      const fdTag = x.fdacs_registration ? (active(x.fdacs_status) ? 'registered FL charity' : 'FL charity registration ' + String(x.fdacs_status || 'lapsed').toLowerCase()) : '';
      const tags = [x.kind, x.subsection, fdTag, x.gov_payment_records ? 'paid by ' + x.paid_by : '', o.length ? `${o.length} official${o.length === 1 ? '' : 's'} on board` : '',
        x.shares_board_with ? `shares board members with ${x.shares_board_with} other${x.shares_board_with === 1 ? '' : 's'}` : ''].filter(Boolean);
      const rev = x.total_revenue ?? x.irs_revenue ?? x.fdacs_revenue;
      return `<div class="np-row" data-id="${esc(x.nonprofit_id)}"><button type="button" aria-expanded="false">
        <div><h3>${esc(title(x.name))}</h3><div class="m">${esc(x.city || '')}${x.latest_return_form ? ' · ' + esc(x.latest_return_form) + ' ' + esc(x.latest_return_year || '') : ''}</div>
          <div class="np-tags">${tags.map((t, i) => `<span class="np-tag${(/^paid|official/.test(t)) ? ' hot' : ''}">${esc(t)}</span>`).join('')}</div></div>
        <div class="v">${rev ? usd(rev) : '<span class="muted">—</span>'}<div class="m">${rev ? 'revenue' : ''}</div></div></button></div>`;
    }).join('') || '<p class="muted">No nonprofits match.</p>';
    $('#npMore').hidden = rs.length <= shown;
    if (open) { const el = document.querySelector(`.np-row[data-id="${CSS.escape(open)}"]`); if (el) { toggle(el); el.scrollIntoView({block: 'start'}); } }
  }

  function toggle(row) {
    const btn = row.querySelector('button'), open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!open));
    const old = row.querySelector('.np-d'); if (old) { old.remove(); return; }
    const x = orgs.find(r => r.nonprofit_id === row.dataset.id); if (!x) return;
    const p = pays.get(x.nonprofit_id) || [], g = grants.get(x.nonprofit_id) || [], o = offs.get(x.nonprofit_id) || [], c = regs.get(x.nonprofit_id);
    const cx = c ? (c.total_expenses ?? null) : null;
    const dl = [['Type', x.kind], ['IRS status', x.subsection ? x.subsection + (x.foundation_type ? ', ' + x.foundation_type : '') + (x.ruling_year ? ' (since ' + x.ruling_year + ')' : '') : 'Not in the IRS master file'],
      ['EIN', x.ein], ['State filing', x.sunbiz_doc_number ? `<a href="${esc(x.sunbiz_url)}" target="_blank" rel="noopener">${esc(x.sunbiz_doc_number)}</a> · ${esc(x.sunbiz_status || '')}` : ''],
      ['Florida charity registration', x.fdacs_registration ? `<a href="${esc(x.fdacs_url)}" target="_blank" rel="noopener">${esc(x.fdacs_registration)}</a> · ${esc(x.fdacs_status || '')}${x.fdacs_expires ? (active(x.fdacs_status) ? ' until ' : ', expired ') + esc(x.fdacs_expires) : ''}` : ''],
      ['Reported to Florida', c && (c.total_revenue != null || cx != null) ? `${c.fiscal_year_end ? 'Year ending ' + esc(c.fiscal_year_end) + ': ' : ''}${c.total_revenue != null ? usd(c.total_revenue) + ' revenue' : ''}${cx != null ? (c.total_revenue != null ? ', ' : '') + usd(cx) + ' spent' : ''}`
        + (c.program_expenses != null || c.fundraising_expenses != null ? `<div class="muted small">Programs ${usd(c.program_expenses)}${pct(c.program_expenses, cx)} · fundraising ${usd(c.fundraising_expenses)}${pct(c.fundraising_expenses, cx)} · management ${usd(c.management_expenses)}${pct(c.management_expenses, cx)}</div>` : '') : ''],
      ['Fundraising firms', c && c.fundraising_consultants ? esc(c.fundraising_consultants) : ''],
      ['Latest return', x.latest_return_form ? `${esc(x.latest_return_form)} for ${esc(x.latest_return_year || '')}` : (x.irs_filing_requirement ? esc(x.irs_filing_requirement) : '')],
      ['Revenue', x.total_revenue != null ? usd(x.total_revenue) : ''], ['Expenses', x.total_expenses != null ? usd(x.total_expenses) : ''], ['Assets', x.total_assets != null ? usd(x.total_assets) : (x.irs_assets ? usd(x.irs_assets) : '')],
      ['Employees', x.employees ? num(x.employees) : ''], ['Board members listed', x.board_members_listed ? num(x.board_members_listed) : ''],
      ['Mission', x.mission ? esc(x.mission) : ''], ['Website', x.website ? `<a href="${esc(/^https?:/i.test(x.website) ? x.website : 'https://' + x.website)}" target="_blank" rel="noopener nofollow">${esc(x.website)}</a>` : '']]
      .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${k === 'EIN' || k === 'Type' ? esc(v) : v}</dd>`).join('');
    const d = document.createElement('div'); d.className = 'np-d';
    d.innerHTML = `<dl>${dl}</dl>
      ${o.length ? `<b>Officials on the board</b><table data-tt="off"><tbody>${o.map(r => `<tr><td>${esc(r.official)}<div class="muted small">${esc(r.titles || '')}</div></td><td class="num small"><a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources || 'source')} ${esc(r.last_year || '')}</a></td></tr>`).join('')}</tbody></table>` : ''}
      ${p.length ? `<b>Government payment records</b><table data-tt="off"><tbody>${p.sort((a, b) => (b.amount || 0) - (a.amount || 0)).map(r => `<tr><td>${esc(r.payer)}<div class="muted small">${esc(r.what || r.record_type)}${r.date ? ' · ' + esc(r.date) : ''}</div></td><td class="num">${r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${usd(r.amount)}</a>` : usd(r.amount)}</td></tr>`).join('')}</tbody></table>` : ''}
      ${g.length ? `<b>Grants it reported giving</b><table data-tt="off"><tbody>${g.sort((a, b) => (b.cash || 0) - (a.cash || 0)).slice(0, 25).map(r => `<tr><td>${r.recipient_id ? `<a href="?id=${encodeURIComponent(r.recipient_id)}#npList">${esc(title(r.recipient))}</a>` : esc(title(r.recipient))}<div class="muted small">${esc(r.purpose || '')} · ${esc(r.tax_year || '')}</div></td><td class="num"><a href="${esc(r.source_url)}" target="_blank" rel="noopener">${usd(r.cash)}</a></td></tr>`).join('')}</tbody></table>${g.length > 25 ? `<p class="muted small">${g.length - 25} more in the dataset.</p>` : ''}` : ''}
      <p class="small"><a href="${esc(x.source_url)}" target="_blank" rel="noopener">${x.irs_recognized ? 'IRS filings on ProPublica' : x.sunbiz_doc_number ? 'State corporate record' : 'FDACS Check-A-Charity'}</a></p>`;
    row.appendChild(d);
    if (x.board_members_listed || x.latest_return_form || x.fdacs_registration) loadBoard(x, d);
  }

  async function loadBoard(x, d) {
    const box = document.createElement('div');
    box.innerHTML = '<p class="muted small">Loading board…</p>';
    d.insertBefore(box, d.querySelector('dl').nextSibling);
    let rs;
    try { rs = await boardOf('nonprofit_id=' + encodeURIComponent(x.nonprofit_id)); } catch (e) { box.innerHTML = ''; return; }
    const offIds = new Set((offs.get(x.nonprofit_id) || []).map(o => o.person_id));
    const cur = rs.filter(r => r.current), past = rs.filter(r => !r.current);
    const tr = r => `<tr><td><button type="button" class="np-p" data-person="${esc(r.person_id)}">${esc(pname(r.person))}</button>${offIds.has(r.person_id) ? ' <span class="np-tag hot">official</span>' : ''}${r.other_current_boards ? ` <span class="np-tag">+${r.other_current_boards} board${r.other_current_boards === 1 ? '' : 's'}</span>` : ''}<div class="muted small">${esc(r.titles || r.role)}${r.role.includes('Staff') ? ' · staff' : ''} · ${esc(years(r))}</div></td>
      <td class="num small">${r.compensation ? usd(r.compensation) + '<div class="muted">pay ' + esc(r.compensation_year || '') + '</div>' : ''}<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources)}</a></td></tr>`;
    box.innerHTML = rs.length ? `<b>Board and officers</b><table data-tt="off"><tbody>${cur.map(tr).join('')}</tbody></table>`
      + (past.length ? `<details><summary class="small">${past.length} earlier board member${past.length === 1 ? '' : 's'}</summary><table data-tt="off"><tbody>${past.map(tr).join('')}</tbody></table></details>` : '') : '';
  }

  document.addEventListener('click', e => { const p = e.target.closest('.np-p'); if (p) { e.preventDefault(); showPerson(p); } });
  $('#npList').addEventListener('click', e => { const b = e.target.closest('.np-row>button'); if (b) toggle(b.parentElement); });
  ['#npQ', '#npK', '#npC', '#npS', '#npHoa', '#npGov', '#npFd'].forEach(s => $(s).addEventListener(s === '#npQ' ? 'input' : 'change', () => { shown = PAGE; render(); }));
  $('#npMore').addEventListener('click', () => { shown += PAGE * 2; render(); });
  load();
})();
