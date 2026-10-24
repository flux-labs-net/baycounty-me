// /connections/business-ties: confirmed official-to-business matches and their links, from
// /api/v1/datasets/official-businesses and /api/v1/datasets/official-business-links (officials and candidates only).
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = n => '$' + Number(n || 0).toLocaleString('en-US', {maximumFractionDigits: 0});
  const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Llc|Inc|Pa|Lp|Llp|Pllc|Pc)\b/g, m => m.toUpperCase());
  const NOW = new Date().getFullYear();
  const LINK = {shared_business: 'Same business', own_business_gift: 'Business gave', partner_business_gift: 'Shared officer', public_payee: 'Paid by a government'};
  let people = [];

  async function get(id) {
    const r = await fetch(`/api/v1/datasets/${id}?limit=1000`);
    if (!r.ok) throw new Error();
    return (await r.json()).data || [];
  }

  function linkText(l, self) {
    const biz = esc(title(l.business));
    if (l.link_type === 'shared_business') {
      const other = l.person_id === self ? l.other_official : l.official;
      return `${esc(other)} is also listed on ${biz}`;
    }
    if (l.link_type === 'own_business_gift') return `${biz} gave ${usd(l.amount)} to ${l.self_gift ? 'their own campaign' : esc(l.candidate)}${l.first_date ? ' (' + esc(String(l.first_date).slice(0, 4)) + ')' : ''}`;
    if (l.link_type === 'partner_business_gift') return `${biz} gave ${usd(l.amount)} to this campaign and shares ${l.shared_people} officer${l.shared_people === 1 ? '' : 's'} with ${esc(title(l.related_business))}`;
    if (l.link_type === 'public_payee') return `${biz} was paid ${usd(l.amount)} by ${esc(l.payer || 'a local government')}${l.own_government ? ', the government this person serves' : ''}`;
    return esc(l.detail || '');
  }

  // Officials on the same business are one line per business; every other link is its own line.
  function linkItems(p) {
    const shared = new Map(), out = [];
    for (const l of p.links) {
      if (l.link_type === 'shared_business') {
        const other = l.person_id === p.id ? l.other_official : l.official;
        if (!shared.has(l.sunbiz_doc_number)) shared.set(l.sunbiz_doc_number, {business: l.business, names: new Set()});
        shared.get(l.sunbiz_doc_number).names.add(other);
      } else {
        out.push(`<li><span class="bt-tag${l.own_government ? ' hot' : ''}">${esc(LINK[l.link_type] || l.link_type)}</span>${linkText(l, p.id)}${l.report_url ? ` · <a href="${esc(l.report_url)}" target="_blank" rel="noopener">report</a>` : ''}</li>`);
      }
    }
    const sh = [...shared.values()].map(s => `<li><span class="bt-tag">${LINK.shared_business}</span>${esc(title(s.business))} also lists ${esc([...s.names].sort().join(', '))}</li>`);
    return sh.concat(out).join('');
  }

  async function load() {
    let biz, links;
    try { [biz, links] = await Promise.all([get('official-businesses'), get('official-business-links')]); }
    catch (e) { $('#btList').innerHTML = '<p class="muted">Couldn’t load the list. Try again in a moment.</p>'; return; }
    const by = new Map();
    const person = (id, name, role) => {
      if (!by.has(id)) by.set(id, {id, name, role: role || '', businesses: [], links: []});
      const p = by.get(id); if (!p.role && role) p.role = role; return p;
    };
    for (const b of biz) person(b.person_id, b.official, b.official_role).businesses.push(b);
    for (const l of links) {
      person(l.person_id, l.official).links.push(l);
      if (l.link_type === 'shared_business' && l.other_person_id) person(l.other_person_id, l.other_official).links.push(l);
    }
    people = [...by.values()].sort((a, b) => b.links.length - a.links.length || a.name.localeCompare(b.name));
    render();
  }

  function bar(b, lo) {
    const start = Number(String(b.filed_date || '').slice(0, 4)) || lo;
    const end = b.business_status === 'Active' ? NOW : (Number(b.closed_year) || start);
    const span = NOW - lo || 1;
    const left = Math.max(0, (start - lo) / span * 100), width = Math.max(2, (Math.min(end, NOW) - start) / span * 100);
    return `<div class="bt-track" title="${start}–${b.business_status === 'Active' ? 'now' : end}"><div class="bt-bar${b.business_status === 'Active' ? '' : ' off'}" style="left:${left}%;width:${Math.min(width, 100 - left)}%"></div></div>`;
  }

  function render() {
    const q = $('#btQ').value.trim().toLowerCase(), t = $('#btT').value;
    const ps = people.filter(p => (!t || p.links.length) && (!q || p.name.toLowerCase().includes(q) || p.businesses.some(b => String(b.business).toLowerCase().includes(q))));
    $('#btCount').textContent = ps.length ? `${ps.length} ${ps.length === 1 ? 'person' : 'people'}, ${ps.reduce((a, p) => a + p.businesses.length, 0)} businesses` : '';
    $('#btList').innerHTML = ps.map(p => {
      const years = p.businesses.map(b => Number(String(b.filed_date || '').slice(0, 4))).filter(Boolean);
      const lo = Math.min(NOW - 10, ...years);
      const bs = p.businesses.slice().sort((a, b) => (a.business_status === 'Active' ? 0 : 1) - (b.business_status === 'Active' ? 0 : 1) || String(a.filed_date).localeCompare(String(b.filed_date)));
      return `<article class="bt-c"><h3>${p.id ? `<a href="/people/${encodeURIComponent(p.id)}">${esc(p.name)}</a>` : esc(p.name)}</h3><div class="bt-meta">${esc(p.role)}</div>
        ${bs.map(b => `<div class="bt-row"><div><a href="/profile/business/${encodeURIComponent(String(b.sunbiz_doc_number || '').toLowerCase())}">${esc(title(b.business))}</a> <a class="src" href="${esc(b.source_url)}" target="_blank" rel="noopener">State record</a>${window.BCM_bizOff ? BCM_bizOff(b.business_status, b.closed_year) : ''}
          <small>${esc(b.titles || '')}${b.nonprofit ? ' · nonprofit' : ''}${b.business_status === 'Active' ? ' · Active' : ''}${b.filed_date ? ' · filed ' + esc(String(b.filed_date).slice(0, 4)) : ''}${b.principal_city ? ' · ' + esc(b.principal_city) : ''}</small></div>
          ${bar(b, lo)}</div>`).join('')}
        ${bs.length ? `<div class="bt-axis"><span>${lo}</span><span>${NOW}</span></div>` : ''}
        ${p.links.length ? `<ul class="bt-links">${linkItems(p)}</ul>` : ''}
      </article>`;
    }).join('') || '<p class="muted">No matches have been checked and listed yet.</p>';
  }

  $('#btQ').addEventListener('input', render);
  $('#btT').addEventListener('change', render);
  load();
})();
