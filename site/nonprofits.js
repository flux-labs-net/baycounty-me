// /connections/nonprofits: reads the nonprofits, nonprofit-payments, nonprofit-grants and nonprofit-officials datasets
// from /api/v1, and nonprofit-board-members per nonprofit or person when a row opens. Officials are tagged only when an
// admin confirmed the name match.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => n == null || n === '' ? '—' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  const num = n => Number(n || 0).toLocaleString('en-US');
  const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Llc|Inc|Pa|Usa|Us|Ymca|Ywca|Vfw|Pta|Pto|Cra|Cdc|Ii|Iii)\b/g, m => m.toUpperCase());
  const HOA = 'Homeowner or condo association';
  const PAGE = 60;
  let orgs = [], pays = new Map(), grants = new Map(), offs = new Map(), shown = PAGE;

  async function all(id) {
    let out = [], url = `/api/v1/datasets/${id}?limit=1000`;
    for (let i = 0; url && i < 20; i++) {
      const r = await fetch(url);
      if (!r.ok) throw new Error(id);
      const j = await r.json();
      out = out.concat(j.data || []);
      url = j.meta && j.meta.next ? j.meta.next.replace(/^https?:\/\/[^/]+/, '') : null;
    }
    return out;
  }
  const people = new Map();  // person_id -> rows (every board that name sits on)
  async function boardOf(q) {
    const r = await fetch(`/api/v1/datasets/nonprofit-board-members?${q}&limit=1000`);
    if (!r.ok) throw new Error('board');
    return (await r.json()).data || [];
  }
  const years = r => r.first_year && r.last_year && r.first_year !== r.last_year ? `${r.first_year}–${r.last_year}` : (r.last_year || '');
  const pname = s => String(s || '').replace(/\b([A-Z])([A-Z']+)\b/g, (m, a, b) => a + b.toLowerCase());
  const group = (rows, key) => rows.reduce((m, r) => (r[key] && (m.get(r[key]) || m.set(r[key], []).get(r[key])).push(r), m), new Map());

  async function load() {
    let o, p, g, f;
    try { [o, p, g, f] = await Promise.all([all('nonprofits'), all('nonprofit-payments'), all('nonprofit-grants'), all('nonprofit-officials').catch(() => [])]); }
    catch (e) { $('#npList').innerHTML = '<p class="muted">Couldn’t load the list. Try again in a moment.</p>'; $('#npOff').innerHTML = ''; return; }
    orgs = o; pays = group(p, 'nonprofit_id'); grants = group(g, 'grantor_id'); offs = group(f, 'nonprofit_id');
    const kinds = [...new Set(orgs.map(x => x.kind).filter(k => k && k !== HOA))].sort();
    $('#npK').innerHTML = '<option value="">All types</option>' + kinds.map(k => `<option>${esc(k)}</option>`).join('') + `<option>${HOA}</option>`;
    const cities = [...new Set(orgs.map(x => x.city).filter(Boolean))].sort();
    $('#npC').innerHTML = '<option value="">All cities</option>' + cities.map(c => `<option>${esc(c)}</option>`).join('');
    const irs = orgs.filter(x => x.irs_recognized);
    const paid = orgs.filter(x => x.gov_payment_records > 0);
    $('#npKpis').innerHTML = [[num(orgs.length), 'nonprofits'], [num(irs.length), 'recognized by the IRS'],
      [usd(orgs.reduce((a, x) => a + Number(x.total_revenue || 0), 0)), 'revenue on latest 990s'], [num(paid.length), 'paid in government records'],
      [num(new Set(f.map(x => x.official_id)).size), 'officials on boards (checked)']]
      .map(([v, l]) => `<div class="np-kpi"><b>${v}</b><span>${l}</span></div>`).join('');
    renderOfficials(f);
    renderInterlocks();
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

  async function showPerson(btn) {
    const id = btn.dataset.person;
    const host = btn.closest('li, tr, article');
    const tr = host.tagName === 'TR';
    const old = tr ? (host.nextElementSibling && host.nextElementSibling.classList.contains('np-ppr') ? host.nextElementSibling : null) : host.querySelector('.np-pp');
    if (old) { old.remove(); return; }
    let rs = people.get(id);
    if (!rs) { try { rs = await boardOf('person_id=' + encodeURIComponent(id)); people.set(id, rs); } catch (e) { return; } }
    const d = document.createElement('div'); d.className = 'np-pp small';
    d.innerHTML = `<b>${esc(pname(rs[0] && rs[0].person))}</b> on ${rs.length} nonprofit${rs.length === 1 ? '' : 's'}: ` + rs.map(r => `<a href="?id=${encodeURIComponent(r.nonprofit_id)}#npList">${esc(title(r.nonprofit))}</a> <span class="muted">(${esc(r.titles || r.role)}${years(r) ? ', ' + esc(years(r)) : ''}${r.current ? '' : ', past'})</span>`).join(' · ')
      + '<div class="muted">Grouped by name, so two people with the same name can show up together.</div>';
    if (!tr) { host.appendChild(d); return; }
    // a row of its own under the person, so a long list wraps instead of stretching the table
    const row = document.createElement('tr'); row.className = 'np-ppr';
    const td = document.createElement('td'); td.colSpan = host.children.length; td.appendChild(d);
    row.appendChild(td); host.after(row);
  }

  function filtered() {
    const q = $('#npQ').value.trim().toLowerCase(), k = $('#npK').value, c = $('#npC').value, s = $('#npS').value;
    const hoa = $('#npHoa').checked || k === HOA, gov = $('#npGov').checked;
    const digits = q.replace(/\D/g, '');
    let rs = orgs.filter(x => (!k || x.kind === k) && (!c || x.city === c) && (hoa || x.kind !== HOA) && (!gov || x.gov_payment_records > 0)
      && (!q || x.name.toLowerCase().includes(q) || String(x.city || '').toLowerCase().includes(q) || (digits.length >= 4 && String(x.ein || '').includes(digits))));
    const rev = x => Number(x.total_revenue ?? x.irs_revenue ?? 0);
    const cmp = {rev: (a, b) => rev(b) - rev(a), gov: (a, b) => (b.gov_dollars_in_records || 0) - (a.gov_dollars_in_records || 0) || rev(b) - rev(a),
      board: (a, b) => (b.shares_board_with || 0) - (a.shares_board_with || 0) || rev(b) - rev(a), name: (a, b) => a.name.localeCompare(b.name)}[s];
    return rs.sort(cmp);
  }

  function render(open) {
    const rs = filtered();
    $('#npCount').textContent = `${num(rs.length)} nonprofit${rs.length === 1 ? '' : 's'}`;
    $('#npList').innerHTML = rs.slice(0, shown).map(x => {
      const o = offs.get(x.nonprofit_id) || [];
      const tags = [x.kind, x.subsection, x.gov_payment_records ? 'paid by ' + x.paid_by : '', o.length ? `${o.length} official${o.length === 1 ? '' : 's'} on board` : '',
        x.shares_board_with ? `shares board members with ${x.shares_board_with} other${x.shares_board_with === 1 ? '' : 's'}` : ''].filter(Boolean);
      const rev = x.total_revenue ?? x.irs_revenue;
      return `<div class="np-row" data-id="${esc(x.nonprofit_id)}"><button type="button" aria-expanded="false">
        <div><h3>${esc(title(x.name))}</h3><div class="m">${esc(x.city || '')}${x.latest_return_form ? ' · ' + esc(x.latest_return_form) + ' ' + esc(x.latest_return_year || '') : ''}</div>
          <div class="np-tags">${tags.map((t, i) => `<span class="np-tag${(i >= 2 && /paid|official/.test(t)) ? ' hot' : ''}">${esc(t)}</span>`).join('')}</div></div>
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
    const p = pays.get(x.nonprofit_id) || [], g = grants.get(x.nonprofit_id) || [], o = offs.get(x.nonprofit_id) || [];
    const dl = [['Type', x.kind], ['IRS status', x.subsection ? x.subsection + (x.foundation_type ? ', ' + x.foundation_type : '') + (x.ruling_year ? ' (since ' + x.ruling_year + ')' : '') : 'Not in the IRS master file'],
      ['EIN', x.ein], ['State filing', x.sunbiz_doc_number ? `<a href="${esc(x.sunbiz_url)}" target="_blank" rel="noopener">${esc(x.sunbiz_doc_number)}</a> · ${esc(x.sunbiz_status || '')}` : ''],
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
      <p class="small"><a href="${esc(x.source_url)}" target="_blank" rel="noopener">${x.ein ? 'IRS filings on ProPublica' : 'State corporate record'}</a></p>`;
    row.appendChild(d);
    if (x.board_members_listed || x.latest_return_form) loadBoard(x, d);
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
  ['#npQ', '#npK', '#npC', '#npS', '#npHoa', '#npGov'].forEach(s => $(s).addEventListener(s === '#npQ' ? 'input' : 'change', () => { shown = PAGE; render(); }));
  $('#npMore').addEventListener('click', () => { shown += PAGE * 2; render(); });
  load();
})();
