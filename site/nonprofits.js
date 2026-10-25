// /connections/nonprofits. Cards with the strongest connections, a Nonprofits / People switch, a short ranked list and a
// details panel. Reads from /api/v1: nonprofits (list fields only), nonprofit-payments, nonprofit-officials, board
// members with a seat on several boards, and board members' businesses that gave to campaigns; a nonprofit's full row,
// board, grants and Florida registration load when it is opened. Officials are tagged only when an admin confirmed the
// name match. If the API fails or comes back empty, the main lists fall back to the published downloads.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => n == null || n === '' ? '—' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  const big = n => { n = Number(n || 0); return n >= 1e6 ? '$' + (n / 1e6).toFixed(1).replace(/\.0$/, '') + 'M' : n >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : '$' + Math.round(n); };
  const num = n => Number(n || 0).toLocaleString('en-US');
  const title = s => String(s || '').toLowerCase().replace(/(^|[^a-z'’])([a-z])/g, (m, a, b) => a + b.toUpperCase()).replace(/\b(Llc|Inc|Pa|Usa|Us|Ymca|Ywca|Vfw|Pta|Pto|Cra|Cdc|Ii|Iii)\b/g, m => m.toUpperCase());
  const pname = s => String(s || '').replace(/\b([A-Z])([A-Z']+)\b/g, (m, a, b) => a + b.toLowerCase());
  const plural = (n, w, ws) => `${num(n)} ${n === 1 ? w : (ws || w + 's')}`;
  const years = r => r.first_year && r.last_year && r.first_year !== r.last_year ? `${r.first_year}–${r.last_year}` : (r.last_year || '');
  const active = s => /^(active|registered)\b/i.test(s || '');  // FDACS: small charities are Active, larger ones Registered
  const pct = (a, b) => a != null && b ? ` (${Math.round(100 * a / b)}%)` : '';
  const group = (rows, key) => rows.reduce((m, r) => (r[key] && (m.get(r[key]) || m.set(r[key], []).get(r[key])).push(r), m), new Map());
  const HOA = 'Homeowner or condo association';
  const PAGE = 25;
  const ti = (i, t) => `<span class="ui-ti t-${t}"><span class="ico i-${i}" aria-hidden="true"></span></span>`;
  const ICON = {gov: ti('receipt', 'salmon'), donor: ti('megaphone', 'amber'), multi: ti('network', 'teal'), off: ti('user', 'blue')};
  const LIST_FIELDS = 'nonprofit_id,name,ein,city,kind,total_revenue,irs_revenue,fdacs_revenue,gov_payment_records,gov_dollars_in_records,paid_by,shares_board_with,fdacs_registration,fdacs_status,board_members_listed';

  // ---------- data ----------
  async function pages(ds, q = '') {
    let out = [], url = `/api/v1/datasets/${ds}?limit=1000${q ? '&' + q : ''}`;
    for (let i = 0; url && i < 20; i++) {
      const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 20000);
      let r;
      try { r = await fetch(url, {signal: ctl.signal}); } finally { clearTimeout(t); }
      if (!r.ok) throw new Error(ds);
      const j = await r.json();
      out = out.concat(j.data || []);
      url = j.meta && j.meta.next ? j.meta.next.replace(/^https?:\/\/[^/]+/, '') : null;
    }
    return out;
  }
  async function download(ds) {
    const r = await fetch(`/downloads/${ds}.json`);
    if (!r.ok) throw new Error(ds);
    const d = await r.json();
    return Array.isArray(d) ? d : (d.rows || d.data || []);
  }
  // The API first; if it fails, is slow or comes back empty (e.g. mid-sync), the published download.
  async function rows(ds, q, keep) {
    try { const rs = await pages(ds, q); if (rs.length) return rs; } catch (e) { /* fall through */ }
    const rs = await download(ds);
    return keep ? rs.filter(keep) : rs;
  }

  const S = {orgs: [], byId: new Map(), pays: new Map(), offs: new Map(), multi: [], donorBiz: new Map(), donorSeats: [],
    orgDonors: new Map(), people: [], view: 'org', tab: 'connected', ptab: 'top', shown: PAGE, sel: null};

  async function load() {
    let o, p, f;
    try {
      [o, p, f] = await Promise.all([rows('nonprofits', 'fields=' + LIST_FIELDS), rows('nonprofit-payments'), rows('nonprofit-officials').catch(() => [])]);
    } catch (e) { $('#npList').innerHTML = '<p class="np-empty">Couldn’t load the list. Try again in a moment.</p>'; return; }
    S.orgs = o; S.byId = new Map(o.map(x => [x.nonprofit_id, x])); S.pays = group(p, 'nonprofit_id'); S.offs = group(f, 'nonprofit_id'); S.offRows = f;
    const isHoa = id => (S.byId.get(id) || {}).kind === HOA;
    // people: current seats on several boards, and board members whose businesses gave to campaigns
    const [multi, biz] = await Promise.all([
      rows('nonprofit-board-members', 'current=true&other_current_boards_min=1&fields=person_id,person,nonprofit_id,nonprofit,titles,role', r => r.current && r.other_current_boards >= 1).catch(() => []),
      rows('nonprofit-board-businesses', 'campaign_gifts_total_min=1', r => Number(r.campaign_gifts_total) >= 1).catch(() => [])]);
    S.donorBiz = group(biz, 'person_id');
    const ids = [...S.donorBiz.keys()];
    S.donorSeats = ids.length ? await rows('nonprofit-board-members', 'current=true&person_id=' + ids.map(encodeURIComponent).join(',') + '&fields=person_id,person,nonprofit_id,nonprofit,titles,role',
      r => r.current && S.donorBiz.has(r.person_id)).catch(() => []) : [];
    S.multi = multi.filter(r => !isHoa(r.nonprofit_id));
    const gifts = id => (S.donorBiz.get(id) || []).reduce((a, b) => a + Number(b.campaign_gifts_total || 0), 0);
    S.orgDonors = new Map();
    for (const r of S.donorSeats) if (!isHoa(r.nonprofit_id)) {
      const m = S.orgDonors.get(r.nonprofit_id) || new Map(); m.set(r.person_id, gifts(r.person_id)); S.orgDonors.set(r.nonprofit_id, m);
    }
    // one row per person: their current boards (HOAs aside), campaign gifts from their businesses, boards paid with public money
    const seats = group(S.multi.concat(S.donorSeats.filter(r => !isHoa(r.nonprofit_id))), 'person_id');
    S.people = [...seats.entries()].map(([id, rs]) => {
      const boards = [...new Map(rs.map(r => [r.nonprofit_id, r])).values()];
      const g = gifts(id), gov = boards.filter(r => S.pays.has(r.nonprofit_id)).length;
      return {id, name: pname(rs[0].person), boards, gifts: g, nbiz: (S.donorBiz.get(id) || []).length, gov, score: boards.length * 2 + (g > 0 ? 3 : 0) + gov * 2};
    }).filter(p => p.boards.length >= 2 || p.gifts > 0);
    S.offPeople = new Set(f.map(r => r.person_id).filter(Boolean));
    setup();
  }

  // ---------- derived ----------
  const rev = x => Number(x.total_revenue ?? x.irs_revenue ?? x.fdacs_revenue ?? 0) || 0;
  const gov = x => Number(x.gov_dollars_in_records || 0);
  const donorsOf = x => S.orgDonors.get(x.nonprofit_id);
  const dGifts = x => { const m = donorsOf(x); return m ? [...m.values()].reduce((a, b) => a + b, 0) : 0; };
  const connected = x => x.kind !== HOA && (gov(x) > 0 || donorsOf(x) || S.offs.has(x.nonprofit_id));
  const payers = x => [...new Set((S.pays.get(x.nonprofit_id) || []).map(p => p.payer))];

  function setup() {
    const vis = S.orgs.filter(x => x.kind !== HOA);
    const hoas = S.orgs.length - vis.length;
    $('#npLede').textContent = `${num(vis.length)} local nonprofits, plus ${num(hoas)} homeowner and condo associations. Start with the ones tied to public money and campaigns, or search for any one.`;
    const paid = vis.filter(x => gov(x) > 0), don = vis.filter(x => donorsOf(x));
    const multiN = new Set(S.multi.map(r => r.person_id)).size;
    const cards = [
      {id: 'gov', n: num(paid.length), t: 'Paid with public money', s: big(paid.reduce((a, x) => a + gov(x), 0)) + ' in government payment records'},
      {id: 'donor', n: num(don.length), t: 'Board ties to campaign money', s: 'Board members run businesses that gave ' + big(S.people.reduce((a, p) => a + p.gifts, 0)) + ' to local campaigns'},
      {id: 'multi', n: num(multiN), t: 'People on several boards', s: 'Names on two or more current boards'}];
    if (S.offRows.length) cards.push({id: 'off', n: num(new Set(S.offRows.map(r => r.official_id)).size), t: 'Officials on boards', s: 'Checked by hand against officials and candidates'});
    $('#npCards').innerHTML = cards.map(c => `<button type="button" class="np-card" data-card="${c.id}" aria-pressed="false">${ICON[c.id] || ''}<b>${c.n}</b><strong>${esc(c.t)}</strong><span>${esc(c.s)}</span></button>`).join('');
    const kinds = [...new Set(S.orgs.map(x => x.kind).filter(k => k && k !== HOA))].sort();
    $('#npK').innerHTML = '<option value="">All types</option>' + kinds.map(k => `<option>${esc(k)}</option>`).join('') + `<option>${HOA}</option>`;
    $('#npC').innerHTML = '<option value="">All cities</option>' + [...new Set(S.orgs.map(x => x.city).filter(Boolean))].sort().map(c => `<option>${esc(c)}</option>`).join('');
    const q = new URLSearchParams(location.search);
    if (q.get('person')) { S.view = 'ppl'; render(); openPerson(q.get('person')); return; }
    render();
    if (q.get('id') && S.byId.has(q.get('id'))) openOrg(q.get('id'), true);
  }

  // ---------- list ----------
  function orgList() {
    const q = $('#npQ').value.trim().toLowerCase(), digits = q.replace(/\D/g, ''), k = $('#npK').value, c = $('#npC').value;
    const hoa = $('#npHoa').checked || k === HOA, fd = $('#npFd').checked;
    let rs = S.orgs.filter(x => (!k || x.kind === k) && (!c || x.city === c) && (hoa || x.kind !== HOA) && (!fd || active(x.fdacs_status))
      && (!q || x.name.toLowerCase().includes(q) || String(x.city || '').toLowerCase().includes(q) || (digits.length >= 4 && String(x.ein || '').includes(digits))));
    const tabs = {connected: rs.filter(connected), gov: rs.filter(x => gov(x) > 0), donor: rs.filter(x => donorsOf(x)), off: rs.filter(x => S.offs.has(x.nonprofit_id)),
      largest: rs.filter(x => rev(x) > 0), all: rs};
    const score = x => gov(x) + dGifts(x) * 5 + (S.offs.has(x.nonprofit_id) ? 1e6 : 0);
    const sorted = {connected: (a, b) => score(b) - score(a) || rev(b) - rev(a), gov: (a, b) => gov(b) - gov(a), donor: (a, b) => dGifts(b) - dGifts(a),
      off: (a, b) => rev(b) - rev(a), largest: (a, b) => rev(b) - rev(a), all: (a, b) => (connected(b) - connected(a)) || rev(b) - rev(a) || a.name.localeCompare(b.name)};
    return {tabs, list: tabs[S.tab].sort(sorted[S.tab])};
  }

  function chips(x) {
    const out = [];
    const py = payers(x);
    if (gov(x) > 0) out.push(`<span class="np-chip hot">${big(gov(x))} from ${esc(py.slice(0, 2).join(', '))}${py.length > 2 ? ' +' + (py.length - 2) : ''}</span>`);
    const o = S.offs.get(x.nonprofit_id);
    if (o) out.push(`<span class="np-chip hot">${plural(new Set(o.map(r => r.official_id)).size, 'official')} on board</span>`);
    const d = donorsOf(x);
    if (d) out.push(`<span class="np-chip">${d.size === 1 ? '1 board member’s businesses' : d.size + ' board members’ businesses'} gave ${big(dGifts(x))}</span>`);
    if (x.shares_board_with) out.push(`<span class="np-chip">Shares board with ${num(x.shares_board_with)}</span>`);
    return out.slice(0, 3).join('');
  }

  function peopleList() {
    const q = $('#npQ').value.trim().toLowerCase();
    let rs = S.people.filter(p => !q || p.name.toLowerCase().includes(q) || p.boards.some(b => String(b.nonprofit).toLowerCase().includes(q)));
    const tabs = {top: rs, gifts: rs.filter(p => p.gifts > 0), multi: rs.filter(p => p.boards.length >= 2)};
    const sorted = {top: (a, b) => b.score - a.score || b.gifts - a.gifts, gifts: (a, b) => b.gifts - a.gifts, multi: (a, b) => b.boards.length - a.boards.length || b.gifts - a.gifts};
    return {tabs, list: tabs[S.ptab].sort(sorted[S.ptab])};
  }

  function render() {
    const org = S.view === 'org';
    $('#npVOrg').setAttribute('aria-pressed', String(org)); $('#npVPpl').setAttribute('aria-pressed', String(!org));
    $('#npFilters').hidden = !org;
    $('#npQ').placeholder = org ? 'Search a nonprofit, city or EIN' : 'Search a person or nonprofit';
    document.querySelectorAll('.np-card').forEach(c => c.setAttribute('aria-pressed', String(org ? c.dataset.card === S.tab : (c.dataset.card === 'multi' && S.ptab === 'multi'))));
    let html;
    if (org) {
      const {tabs, list} = orgList();
      const T = [['connected', 'Connected'], ['largest', 'Largest'], ['all', 'All']];
      if (['gov', 'donor', 'off'].includes(S.tab)) T.unshift([S.tab, {gov: 'Public money', donor: 'Campaign ties', off: 'Officials'}[S.tab]]);
      $('#npTabs').innerHTML = T.map(([k, l]) => `<button type="button" role="tab" data-tab="${k}" aria-selected="${S.tab === k}">${l} (${num(tabs[k].length)})</button>`).join('');
      html = list.slice(0, S.shown).map(x => `<div class="np-row${S.sel === x.nonprofit_id ? ' sel' : ''}" role="button" tabindex="0" data-org="${esc(x.nonprofit_id)}">
        <div><h3>${esc(title(x.name))}</h3><div class="m">${esc([x.city, x.kind].filter(Boolean).join(' · '))}</div><div class="np-chips">${chips(x)}</div></div>
        <div class="v">${rev(x) ? big(rev(x)) : '<span class="muted">—</span>'}<div class="m">${rev(x) ? 'revenue' : ''}</div></div></div>`).join('');
      $('#npMore').hidden = list.length <= S.shown;
      if (!list.length) html = '<p class="np-empty">No nonprofits match.' + (S.tab !== 'all' ? ' Try the All tab.' : '') + '</p>';
    } else {
      const {tabs, list} = peopleList();
      $('#npTabs').innerHTML = [['top', 'Most connected'], ['gifts', 'Campaign ties'], ['multi', 'Several boards']]
        .map(([k, l]) => `<button type="button" role="tab" data-ptab="${k}" aria-selected="${S.ptab === k}">${l} (${num(tabs[k].length)})</button>`).join('');
      html = list.slice(0, S.shown).map(p => `<div class="np-row${S.sel === p.id ? ' sel' : ''}" role="button" tabindex="0" data-person="${esc(p.id)}">
        <div><h3>${esc(p.name)}${S.offPeople.has(p.id) ? ' <span class="np-chip hot">official</span>' : ''}</h3><div class="m">${p.boards.slice(0, 3).map(b => esc(title(b.nonprofit))).join(' · ')}${p.boards.length > 3 ? ' · +' + (p.boards.length - 3) : ''}</div>
        <div class="np-chips">${p.gifts ? `<span class="np-chip hot">Businesses gave ${big(p.gifts)} to campaigns</span>` : ''}${p.gov ? `<span class="np-chip">On ${plural(p.gov, 'board')} paid with public money</span>` : ''}</div></div>
        <div class="v">${p.boards.length}<div class="m">board${p.boards.length === 1 ? '' : 's'}</div></div></div>`).join('');
      $('#npMore').hidden = list.length <= S.shown;
      if (!list.length) html = '<p class="np-empty">No one matches.</p>';
    }
    $('#npList').innerHTML = html;
  }

  // ---------- panel ----------
  const panel = $('#npPanel');
  function showPanel(html) {
    panel.innerHTML = '<button type="button" class="pill np-x" id="npX">Close</button>' + html;
    panel.classList.add('open'); panel.scrollTop = 0;
    if (matchMedia('(max-width:860px)').matches) document.body.classList.add('np-lock');
    document.querySelectorAll('.np-row').forEach(r => r.classList.toggle('sel', r.dataset.org === S.sel || r.dataset.person === S.sel));
  }
  function closePanel() { panel.classList.remove('open'); document.body.classList.remove('np-lock'); }
  const tabsHtml = (names, on) => `<div class="np-tabs" role="tablist">${names.map(([k, l]) => `<button type="button" role="tab" data-ptab-panel="${k}" aria-selected="${k === on}">${l}</button>`).join('')}</div>`;
  const pane = (k, on, html) => `<div data-pane="${k}"${k === on ? '' : ' hidden'}>${html}</div>`;
  function setUrl(k, v) { try { const u = new URL(location.href); u.searchParams.delete('id'); u.searchParams.delete('person'); if (v) u.searchParams.set(k, v); history.replaceState(null, '', u); } catch (e) { /* ignore */ } }

  async function openOrg(id, scroll) {
    let x = S.byId.get(id); if (!x) return;
    S.sel = id; setUrl('id', id);
    const head = () => `<h2>${esc(title(x.name))}</h2><div class="m">${esc([x.city, x.kind].filter(Boolean).join(' · '))} · <a href="/profile/nonprofit/${encodeURIComponent(id)}">Full profile and network</a></div>`;
    showPanel(head() + '<p class="muted small">Loading…</p>');
    if (scroll) { const el = document.querySelector(`.np-row[data-org="${CSS.escape(id)}"]`); if (el) el.scrollIntoView({block: 'center'}); }
    const q = 'nonprofit_id=' + encodeURIComponent(id);
    const [full, board, grants, reg] = await Promise.all([pages('nonprofits', q).then(r => r[0]).catch(() => null), pages('nonprofit-board-members', q).catch(() => []),
      pages('nonprofit-grants', 'grantor_id=' + encodeURIComponent(id)).catch(() => []), x.fdacs_registration ? pages('charity-registrations', q).then(r => r[0]).catch(() => null) : null]);
    if (S.sel !== id) return;
    if (full) x = Object.assign({}, x, full);
    const p = S.pays.get(id) || [], o = S.offs.get(id) || [], d = donorsOf(x);
    const cur = board.filter(r => r.current), past = board.filter(r => !r.current);
    const offIds = new Set(o.map(r => r.person_id));
    // Connections
    const ties = [];
    for (const py of payers(x)) { const ps = p.filter(r => r.payer === py); ties.push(`<div class="np-tie"><b>Paid ${big(ps.reduce((a, r) => a + Number(r.amount || 0), 0))} by ${esc(py)}</b><div class="m">${esc(ps[0].what || ps[0].record_type)}${ps[0].date ? ' · ' + esc(ps[0].date) : ''}</div></div>`); }
    for (const r of o) ties.push(`<div class="np-tie"><b>${r.person_id ? `<a href="/people/${encodeURIComponent(r.person_id)}">${esc(r.official)}</a>` : esc(r.official)}</b> is on the board<div class="m">${esc(r.titles || '')}${years(r) ? ' · ' + esc(years(r)) : ''} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources || 'source')}</a></div></div>`);
    if (d) for (const [pid, g] of [...d.entries()].sort((a, b) => b[1] - a[1])) {
      const seat = S.donorSeats.find(r => r.person_id === pid && r.nonprofit_id === id) || {};
      const bz = (S.donorBiz.get(pid) || []).slice(0, 3).map(b => esc(title(b.business))).join(', ');
      ties.push(`<div class="np-tie"><button type="button" class="np-p" data-person="${esc(pid)}">${esc(pname(seat.person))}</button> runs businesses that gave ${big(g)} to campaigns<div class="m">${bz}</div></div>`);
    }
    const shared = cur.filter(r => r.other_current_boards > 0);
    if (shared.length) ties.push(`<div class="np-tie"><b>Shares board members with ${plural(x.shares_board_with || shared.length, 'other nonprofit')}</b><div class="m">${shared.slice(0, 6).map(r => `<button type="button" class="np-p" data-person="${esc(r.person_id)}">${esc(pname(r.person))}</button> (+${r.other_current_boards})`).join(' · ')}</div></div>`);
    // Board
    const tr = r => `<tr><td><button type="button" class="np-p" data-person="${esc(r.person_id)}">${esc(pname(r.person))}</button>${offIds.has(r.person_id) ? ' <span class="np-chip hot">official</span>' : ''}${r.other_current_boards ? ` <span class="np-chip">+${r.other_current_boards}</span>` : ''}<div class="m">${esc(r.titles || r.role)} · ${esc(years(r))}</div></td>
      <td class="num">${r.compensation ? usd(r.compensation) + '<div class="m">pay ' + esc(r.compensation_year || '') + '</div>' : ''}<a class="small" href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources)}</a></td></tr>`;
    const boardHtml = board.length ? `<table data-tt="off"><tbody>${cur.map(tr).join('')}</tbody></table>${past.length ? `<details><summary class="small">${plural(past.length, 'earlier board member')}</summary><table data-tt="off"><tbody>${past.map(tr).join('')}</tbody></table></details>` : ''}<p class="m">Grouped by name across boards, so two people with the same name can show up together.</p>`
      : '<p class="muted small">No board listed in its filings.</p>';
    // Money
    const cx = reg ? (reg.total_expenses ?? null) : null;
    const money = `<dl>${[['Revenue', x.total_revenue != null ? usd(x.total_revenue) : (x.irs_revenue ? usd(x.irs_revenue) : '')], ['Expenses', x.total_expenses != null ? usd(x.total_expenses) : ''],
      ['Assets', x.total_assets != null ? usd(x.total_assets) : (x.irs_assets ? usd(x.irs_assets) : '')], ['Employees', x.employees ? num(x.employees) : ''],
      ['Reported to Florida', reg && (reg.total_revenue != null || cx != null) ? `${reg.fiscal_year_end ? 'Year ending ' + esc(reg.fiscal_year_end) + ': ' : ''}${reg.total_revenue != null ? usd(reg.total_revenue) + ' revenue' : ''}${cx != null ? (reg.total_revenue != null ? ', ' : '') + usd(cx) + ' spent' : ''}`
        + (reg.program_expenses != null || reg.fundraising_expenses != null ? `<div class="m">Programs ${usd(reg.program_expenses)}${pct(reg.program_expenses, cx)} · fundraising ${usd(reg.fundraising_expenses)}${pct(reg.fundraising_expenses, cx)} · management ${usd(reg.management_expenses)}${pct(reg.management_expenses, cx)}</div>` : '') : ''],
      ['Fundraising firms', reg && reg.fundraising_consultants ? esc(reg.fundraising_consultants) : '']].filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`
      + (p.length ? `<b>Government payment records</b><table data-tt="off"><tbody>${p.slice().sort((a, b) => (b.amount || 0) - (a.amount || 0)).map(r => `<tr><td>${esc(r.payer)}<div class="m">${esc(r.what || r.record_type)}${r.date ? ' · ' + esc(r.date) : ''}</div></td><td class="num">${r.source_url ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener">${usd(r.amount)}</a>` : usd(r.amount)}</td></tr>`).join('')}</tbody></table>` : '')
      + (grants.length ? `<b>Grants it reported giving</b><table data-tt="off"><tbody>${grants.sort((a, b) => (b.cash || 0) - (a.cash || 0)).slice(0, 15).map(r => `<tr><td>${r.recipient_id && S.byId.has(r.recipient_id) ? `<button type="button" class="np-p" data-org="${esc(r.recipient_id)}">${esc(title(r.recipient))}</button>` : esc(title(r.recipient))}<div class="m">${esc(r.purpose || '')} · ${esc(r.tax_year || '')}</div></td><td class="num"><a href="${esc(r.source_url)}" target="_blank" rel="noopener">${usd(r.cash)}</a></td></tr>`).join('')}</tbody></table>${grants.length > 15 ? `<p class="m">${grants.length - 15} more in the dataset.</p>` : ''}` : '');
    // Filings
    const filings = `<dl>${[['IRS status', x.subsection ? esc(x.subsection + (x.foundation_type ? ', ' + x.foundation_type : '') + (x.ruling_year ? ' (since ' + x.ruling_year + ')' : '')) : 'Not in the IRS master file'],
      ['EIN', x.ein ? esc(x.ein) : ''], ['Latest return', x.latest_return_form ? `${esc(x.latest_return_form)} for ${esc(x.latest_return_year || '')}` : (x.irs_filing_requirement ? esc(x.irs_filing_requirement) : '')],
      ['State filing', x.sunbiz_doc_number ? `<a href="${esc(x.sunbiz_url)}" target="_blank" rel="noopener">${esc(x.sunbiz_doc_number)}</a> ${x.sunbiz_status && x.sunbiz_status !== 'Active' && window.BCM_bizOff ? BCM_bizOff(x.sunbiz_status) : (x.sunbiz_status ? ' · ' + esc(x.sunbiz_status) : '')}` : ''],
      ['Florida charity', x.fdacs_registration ? `<a href="${esc(x.fdacs_url)}" target="_blank" rel="noopener">${esc(x.fdacs_registration)}</a> · ${esc(x.fdacs_status || '')}${x.fdacs_expires ? (active(x.fdacs_status) ? ' until ' : ', expired ') + esc(x.fdacs_expires) : ''}` : ''],
      ['Mission', x.mission ? esc(x.mission) : ''], ['Website', x.website ? `<a href="${esc(/^https?:/i.test(x.website) ? x.website : 'https://' + x.website)}" target="_blank" rel="noopener nofollow">${esc(x.website)}</a>` : '']]
      .filter(([, v]) => v).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      <p class="small"><a href="${esc(x.source_url)}" target="_blank" rel="noopener">${x.irs_recognized ? 'IRS filings on ProPublica' : x.sunbiz_doc_number ? 'State corporate record' : 'FDACS Check-A-Charity'}</a></p>`;
    const on = ties.length ? 'ties' : 'board';
    showPanel(head() + `<div class="np-kv"><div><b>${rev(x) ? big(rev(x)) : '—'}</b><span>revenue</span></div><div><b>${gov(x) ? big(gov(x)) : '—'}</b><span>public money</span></div><div><b>${num(cur.length)}</b><span>on board now</span></div></div>`
      + tabsHtml([['ties', `Connections (${ties.length})`], ['board', `Board (${cur.length})`], ['money', 'Money'], ['filings', 'Filings']], on)
      + pane('ties', on, ties.join('') || '<p class="muted small">No ties to public money, campaigns or other boards in the records.</p>') + pane('board', on, boardHtml) + pane('money', on, money) + pane('filings', on, filings));
  }

  async function openPerson(id) {
    S.sel = id; setUrl('person', id);
    showPanel('<p class="muted small">Loading…</p>');
    const q = 'person_id=' + encodeURIComponent(id);
    const [seats, biz] = await Promise.all([pages('nonprofit-board-members', q).catch(() => []), pages('nonprofit-board-businesses', q).catch(() => [])]);
    if (S.sel !== id) return;
    if (!seats.length) { showPanel('<p class="muted small">No board seats found for this person.</p>'); return; }
    const cur = seats.filter(r => r.current), past = seats.filter(r => !r.current);
    const gifts = biz.reduce((a, b) => a + Number(b.campaign_gifts_total || 0), 0);
    const seat = r => `<div class="np-tie">${S.byId.has(r.nonprofit_id) ? `<button type="button" class="np-p" data-org="${esc(r.nonprofit_id)}">${esc(title(r.nonprofit))}</button>` : esc(title(r.nonprofit))}${S.pays.has(r.nonprofit_id) ? ' <span class="np-chip hot">public money</span>' : ''}
      <div class="m">${esc(r.titles || r.role)}${years(r) ? ' · ' + esc(years(r)) : ''}${r.compensation ? ' · paid ' + usd(r.compensation) + ' (' + esc(r.compensation_year || '') + ')' : ''} · <a href="${esc(r.source_url)}" target="_blank" rel="noopener">${esc(r.sources)}</a></div></div>`;
    const bz = biz.slice().sort((a, b) => Number(b.campaign_gifts_total || 0) - Number(a.campaign_gifts_total || 0) || (a.business_status === 'Active' ? -1 : 1));
    const bline = b => `<div class="np-tie"><a href="/profile/business/${encodeURIComponent(String(b.doc_number || '').toLowerCase())}">${esc(title(b.business))}</a> · <a class="src" href="${esc(b.source_url)}" target="_blank" rel="noopener">State record</a>${window.BCM_bizOff ? BCM_bizOff(b.business_status, b.closed_year) : (b.business_status === 'Active' ? '' : ' (inactive)')}
      <div class="m">${Number(b.campaign_gifts_total) > 0 ? `Gave ${usd(b.campaign_gifts_total)} to campaigns${b.candidates ? ': ' + esc(b.candidates) : ''} · ` : ''}${b.match === 'Name' ? 'matched by name' : 'matched by name and address'}</div></div>`;
    const on = 'boards';
    showPanel(`<h2>${esc(pname(seats[0].person))}</h2><div class="m">${plural(cur.length, 'current board')}${biz.length ? ' · ' + plural(biz.length, 'business', 'businesses') : ''} · <a href="/profile/member/${encodeURIComponent(id)}">Full profile and network</a></div>`
      + `<div class="np-kv"><div><b>${num(cur.length)}</b><span>boards now</span></div><div><b>${num(biz.length)}</b><span>businesses</span></div><div><b>${gifts ? big(gifts) : '—'}</b><span>business gifts to campaigns</span></div></div>`
      + tabsHtml([['boards', `Boards (${seats.length})`], ['biz', `Businesses (${biz.length})`]], on)
      + pane('boards', on, cur.map(seat).join('') + (past.length ? `<details><summary class="small">${plural(past.length, 'earlier seat')}</summary>${past.map(seat).join('')}</details>` : ''))
      + pane('biz', on, bz.length ? bz.slice(0, 40).map(bline).join('') + (bz.length > 40 ? `<p class="m">${bz.length - 40} more in the dataset.</p>` : '') : '<p class="muted small">No businesses found in Florida corporate filings under this name.</p>')
      + '<p class="m">Grouped by name, so two people with the same name can show up together. Check the filing before drawing conclusions.</p>');
  }

  // ---------- events ----------
  const rerender = () => { S.shown = PAGE; render(); };
  $('#npVOrg').addEventListener('click', () => { S.view = 'org'; rerender(); });
  $('#npVPpl').addEventListener('click', () => { S.view = 'ppl'; rerender(); });
  $('#npCards').addEventListener('click', e => {
    const c = e.target.closest('.np-card'); if (!c) return;
    const k = c.dataset.card;
    if (k === 'multi') { S.ptab = S.view === 'ppl' && S.ptab === 'multi' ? 'top' : 'multi'; S.view = 'ppl'; }
    else { S.view = 'org'; S.tab = S.tab === k ? 'connected' : k; }
    rerender();
    $('#npTabs').scrollIntoView({block: 'nearest', behavior: 'smooth'});
  });
  $('#npTabs').addEventListener('click', e => { const b = e.target.closest('button'); if (!b) return; if (b.dataset.tab) S.tab = b.dataset.tab; if (b.dataset.ptab) S.ptab = b.dataset.ptab; rerender(); });
  $('#npQ').addEventListener('input', () => { if (S.view === 'org' && $('#npQ').value.trim() && S.tab !== 'all') S.tab = 'all'; rerender(); });
  ['#npK', '#npC', '#npHoa', '#npFd'].forEach(s => $(s).addEventListener('change', () => { if (S.tab !== 'all') S.tab = 'all'; rerender(); }));
  $('#npMore').addEventListener('click', () => { S.shown += PAGE * 2; render(); });
  const pick = el => { if (el.dataset.org) openOrg(el.dataset.org); else if (el.dataset.person) openPerson(el.dataset.person); };
  $('#npList').addEventListener('click', e => { const r = e.target.closest('.np-row'); if (r) pick(r); });
  $('#npList').addEventListener('keydown', e => { const r = e.target.closest('.np-row'); if (r && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(r); } });
  panel.addEventListener('click', e => {
    if (e.target.closest('#npX')) { closePanel(); return; }
    const t = e.target.closest('[data-ptab-panel]');
    if (t) { panel.querySelectorAll('[data-ptab-panel]').forEach(b => b.setAttribute('aria-selected', String(b === t))); panel.querySelectorAll('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== t.dataset.ptabPanel; }); return; }
    const l = e.target.closest('.np-p'); if (l) { e.preventDefault(); pick(l); }
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && panel.classList.contains('open')) closePanel(); });
  load();
})();
