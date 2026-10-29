// Entity profiles: the mini network and the connection list on every profile page (/people/<id>, vendor and government
// pages, and /profile/<kind>/<id> for every other company, nonprofit, board member, business and committee).
// Data: GET /api/v1/entities/<id> (api/_entities.js). A static page also embeds its build-time connections in
// #pfData, so the map draws at once and then gains any hand-checked connections the API adds.
(() => {
  const root = document.getElementById('pf'); if (!root) return;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const money = n => n == null ? '' : (n < 0 ? '−' : '') + (Math.abs(n) >= 1e6 ? '$' + (Math.abs(n) / 1e6).toFixed(2) + 'M' : '$' + Math.round(Math.abs(n)).toLocaleString('en-US'));
  const KIND = {gov: 'Government', vendor: 'Company', person: 'Official or candidate', nonprofit: 'Nonprofit', member: 'Board member', owner: 'Business owner', business: 'Business', committee: 'Committee or PAC'};
  const COLOR = {gov: 'var(--navy)', vendor: 'var(--blue)', business: 'var(--blue)', person: 'var(--salmon)', nonprofit: 'var(--teal)', member: 'var(--amber)', owner: 'var(--amber)', committee: 'var(--muted)'};
  const LINE = {gift: 'pf-l-gift', paid: 'pf-l-paid', board: 'pf-l-board', runs: 'pf-l-runs', voted: 'pf-l-voted', serves: 'pf-l-board', served: 'pf-l-board', candidate: 'pf-l-board', ran: 'pf-l-board', grant: 'pf-l-paid', related: 'pf-l-runs', same: 'pf-l-runs', works: 'pf-l-runs', hired: 'pf-l-paid', charter: 'pf-l-runs', motion: 'pf-l-voted', agenda: 'pf-l-runs', project: 'pf-l-runs'};
  const ORDER = ['serves', 'candidate', 'served', 'ran', 'paid', 'hired', 'gift', 'voted', 'motion', 'agenda', 'project', 'board', 'works', 'charter', 'runs', 'grant', 'related', 'same'];
  let id = root.dataset.id;
  if (!id) {  // /profile/<kind>/<key> or /profile?id=<kind>:<key>
    const m = location.pathname.match(/^\/profile\/([a-z]+)\/(.+?)\/?$/);
    id = m ? m[1] + ':' + decodeURIComponent(m[2]) : new URLSearchParams(location.search).get('id');
  }
  const embedded = document.getElementById('pfData');
  let D = embedded ? JSON.parse(embedded.textContent) : null;

  // the shared page look (site/ui.py): initials or an icon in a tinted badge, the section kicker, icon stat cards
  const TONES = ['blue', 'teal', 'amber', 'salmon'];
  const toneOf = t => TONES[[...String(t || '')].reduce((a, c) => a + c.codePointAt(0), 0) % 4];  // same as ui.tone_of
  const ico = (n, t) => { const i = `<span class="ico i-${n}" aria-hidden="true"></span>`; return t ? `<span class="ui-ti t-${t}">${i}</span>` : i; };
  const ICON = {gov: 'county', vendor: 'store', business: 'store', nonprofit: 'heart', committee: 'megaphone'};
  // photos are served by the site itself, so a preview build shows its own copies
  const rel = u => String(u || '').replace(/^https:\/\/baycounty\.me(?=\/)/, '');
  // a person's photo in a circle on the network map, ringed in the color of their kind
  let faces = 0;
  const face = (x, y, r, url, ring, cls) => { const k = 'pfc' + (++faces);
    return `<clipPath id="${k}"><circle cx="${x}" cy="${y}" r="${r}"/></clipPath><circle cx="${x}" cy="${y}" r="${r}" fill="var(--sunken)"/><image href="${esc(rel(url))}" x="${(x - r).toFixed(1)}" y="${(y - r).toFixed(1)}" width="${(2 * r).toFixed(1)}" height="${(2 * r).toFixed(1)}" clip-path="url(#${k})" preserveAspectRatio="xMidYMid slice"/><circle class="pf-face${cls ? ' ' + cls : ''}" cx="${x}" cy="${y}" r="${r}" fill="none" stroke="${ring}"/>`; };
  function initials(name) {
    const w = String(name || '').replace(/\([^)]*\)?|"[^"]*"?/g, ' ').split(/\s+/).filter(x => /^\p{L}/u.test(x));
    return w.length ? (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : '')).toUpperCase() : '?';
  }
  function header(e) {
    const h = document.getElementById('pfHead'); if (!h) return;
    document.title = e.name + ' · BayCounty.me';
    const tone = toneOf(e.name), ic = ICON[e.kind];
    const ph = !ic && e.photo && e.photo.url;
    const badge = ph ? `<span class="ui-badge ui-badge-av ui-badge-ph t-${tone}"><img src="${esc(rel(ph))}" alt="Photo of ${esc(e.name)}" width="160" height="160" decoding="async"></span>`
      : ic ? `<span class="ui-badge t-${tone}">${ico(ic)}</span>` : `<span class="ui-badge ui-badge-av t-${tone}" aria-hidden="true">${esc(initials(e.name))}</span>`;
    const credit = ph && e.photo.credit ? `<p class="ui-photo-cr">Photo: ${e.photo.source_url ? `<a href="${esc(e.photo.source_url)}" target="_blank" rel="noopener">${esc(e.photo.credit)}</a>` : esc(e.photo.credit)}</p>` : '';
    const kp = (i, t, l, v, s) => v ? `<div class="kpi ui-k"><span class="kh">${ico(i, t)}<span class="eyebrow">${l}</span></span><span class="v">${v}</span><span class="s">${s}</span></div>` : '';
    const tags = e.source_url ? `<div class="ui-tags"><a class="ui-tag" href="${esc(e.source_url)}" target="_blank" rel="noopener">${ico('link')}Public record</a></div>` : '';
    h.closest('.page')?.classList.add('ui-pfp');
    h.innerHTML = `<header class="tx-top ui-hero ui-pf"><div class="ui-id">${badge}<div class="ui-hd"><div class="tx-brand"><span class="eyebrow ui-kick k-blue"><a href="/connections">Connections</a> · ${esc(e.kind_label || KIND[e.kind])}</span><h1>${esc(e.name)}</h1>
      ${e.subtitle ? `<p class="lede">${esc(e.subtitle)}</p>` : ''}${credit}${e.aliases && e.aliases.length ? `<p class="small muted">Also written as: ${esc(e.aliases.join(' · '))}</p>` : ''}${e.same_as && e.same_as.page_url ? `<p class="small">Checked by hand: this board member is <a href="${esc(e.same_as.page_url)}">${esc(e.same_as.name)}</a> <span class="pf-badge">Official</span></p>` : ''}</div>${tags}</div></div></header>
      <div class="kpis">${kp('network', 'blue', 'Connections', (e.connections || 0).toLocaleString('en-US'), 'in public records')}${kp('dollar', 'teal', 'Received', money(e.amount_received), 'payments, gifts and grants in the records')}${kp('wallet', 'amber', 'Gave or paid', money(e.amount_given), 'payments, gifts and grants in the records')}</div>`;
  }

  // ---------- mini network ----------
  function net(d) {
    const box = document.getElementById('pfNet'); if (!box) return;
    const cs = d.connections.filter(c => c.other && c.other.entity_id);
    if (!cs.length) { box.innerHTML = '<p class="muted small">No connections in the records yet.</p>'; return; }
    const narrow = box.clientWidth < 560, W = narrow ? 420 : 900, max = narrow ? 16 : 30;
    // one node per other entity, keeping its largest connection; a few of each kind of connection, then the largest
    const by = new Map();
    cs.forEach(c => { const k = c.other.entity_id, o = by.get(k); if (!o || (c.amount || 0) > (o.amount || 0)) by.set(k, c); });
    const all = [...by.values()];
    const pick = [], seen = new Set();
    ORDER.forEach(r => all.filter(c => c.relation === r).slice(0, 3).forEach(c => { pick.push(c); seen.add(c); }));
    all.sort((a, b) => (b.amount || 0) - (a.amount || 0)).forEach(c => { if (pick.length < max && !seen.has(c)) { pick.push(c); seen.add(c); } });
    const nodes = pick.slice(0, max).sort((a, b) => ORDER.indexOf(a.relation) - ORDER.indexOf(b.relation) || (b.amount || 0) - (a.amount || 0));
    const top = Math.max(1, ...nodes.map(c => c.amount || 0));
    // two arcs, right then left, so every label has its own line and room beside its circle
    const half = Math.ceil(nodes.length / 2), step = narrow ? 30 : 26;
    const H = Math.max(narrow ? 300 : 280, Math.max(half, 1) * step + 60), cx = W / 2, cy = H / 2;
    const rx = narrow ? 62 : 230, ry = (H - 60) / 2, span = Math.min(1.25, 0.35 + half * 0.08);
    const pts = nodes.map((c, i) => {
      const right = i < half, j = right ? i : i - half, n = right ? half : nodes.length - half;
      const f = n > 1 ? j / (n - 1) : 0.5, a = -span + 2 * span * f;
      const t = right ? a : Math.PI - a;
      const r = 4 + 8 * Math.sqrt((c.amount || 0) / top);
      return {c, right, x: cx + rx * Math.cos(t), y: cy + ry * Math.sin(a), r: c.other.photo ? Math.max(r, 11) : r};
    });
    let svg = '';
    pts.forEach(p => { svg += `<line class="pf-l ${LINE[p.c.relation] || ''}" x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}"/>`; });
    const lab = (s, n) => s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
    pts.forEach(p => {
      const dx = p.right ? p.r + 5 : -p.r - 5;
      const o = p.c.other, tip = `${o.name} (${KIND[o.kind] || o.kind}): ${p.c.label}${p.c.amount ? ' · ' + money(p.c.amount) : ''}`;
      const dot = o.photo ? face(+p.x.toFixed(1), +p.y.toFixed(1), +p.r.toFixed(1), o.photo, COLOR[o.kind] || 'var(--muted)')
        : `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${p.r.toFixed(1)}" fill="${COLOR[o.kind] || 'var(--muted)'}"/>`;
      const inner = `${dot}<text x="${(p.x + dx).toFixed(1)}" y="${(p.y + 4).toFixed(1)}" text-anchor="${p.right ? 'start' : 'end'}" data-w="${Math.floor(p.right ? W - p.x - dx - 4 : p.x + dx - 4)}">${esc(lab(o.name, narrow ? 15 : 30))}</text><title>${esc(tip)}</title>`;
      svg += o.page_url ? `<a href="${esc(o.page_url)}">${inner}</a>` : `<g>${inner}</g>`;
    });
    const me = d.entity;
    const mePh = me.photo && (me.photo.url || me.photo);
    svg += mePh ? face(cx, cy, 24, mePh, COLOR[me.kind] || 'var(--navy)', 'pf-me-ph') + `<text class="pf-me-t" x="${cx}" y="${cy + 42}" text-anchor="middle">${esc(lab(me.name, narrow ? 22 : 34))}</text>`
      : `<circle class="pf-me" cx="${cx}" cy="${cy}" r="16" fill="${COLOR[me.kind] || 'var(--navy)'}"/><text class="pf-me-t" x="${cx}" y="${cy + 34}" text-anchor="middle">${esc(lab(me.name, narrow ? 22 : 34))}</text>`;
    const kinds = [...new Set(nodes.map(c => c.other.kind === 'business' ? 'vendor' : c.other.kind).concat([me.kind === 'business' ? 'vendor' : me.kind]))];
    const rels = [...new Set(nodes.map(c => c.relation))];
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}"${narrow ? ' class="pf-sm"' : ''} role="img" aria-label="${esc(me.name)} and ${nodes.length} of its connections">${svg}</svg>
      <div class="pf-legend">${kinds.map(k => `<span><i style="background:${COLOR[k]}"></i>${k === 'vendor' ? 'Company or business' : KIND[k]}</span>`).join('')}${rels.map(r => `<span><i class="ln ${LINE[r] || ''}"></i>${esc(labelOf(r))}</span>`).join('')}</div>
      <p class="cn-note">${all.length > nodes.length ? `Showing ${nodes.length} of ${all.length} connections, the largest of each kind first. ` : ''}Tap a name to open its profile. Bigger circles carry more dollars in the records.</p>`;
    // a long name on the left arc can run past the edge of the map: shorten any label wider than the room beside its circle
    box.querySelectorAll('text[data-w]').forEach(t => {
      const w = +t.dataset.w; let s = t.textContent;
      try { while (s.length > 4 && t.getComputedTextLength() > w) { s = s.slice(0, -2).trimEnd() + '…'; t.textContent = s; } } catch (e) { /* not rendered */ }
    });
  }
  const labelOf = r => ({serves: 'Serves', served: 'Served', candidate: 'Candidates', ran: 'Ran for office', paid: 'Payments', gift: 'Campaign gifts', voted: 'Votes on contracts', board: 'Board seats', runs: 'Runs a business', grant: 'Grants', related: 'Shared project or tie', same: 'Same organization', works: 'Works at', hired: 'Contracts', charter: 'Charter schools', motion: 'Motions naming', agenda: 'On agendas', project: 'Development projects'}[r] || r);

  // ---------- connection list ----------
  // One row per name and kind of connection. The records can name the same pair more than once (a company in both the
  // contracts and the check registers, a donor giving under two office names), so those rows are folded together.
  // Contracts and checks can describe the same dollars, so a folded payment row shows the largest amount, with each
  // record type's amount in the detail; gifts and grants add up.
  function fold(cs) {
    const by = new Map();
    cs.forEach(c => {
      const k = c.relation + '|' + c.direction + '|' + (c.other.entity_id || c.other.name);
      const o = by.get(k);
      if (!o) { by.set(k, {...c, parts: [c]}); return; }
      o.parts.push(c);
    });
    return [...by.values()].map(o => {
      if (o.parts.length === 1) return o;
      const ps = o.parts, amts = ps.map(c => c.amount || 0), sum = o.relation !== 'paid';
      const dates = ps.flatMap(c => [c.first_date, c.last_date]).filter(Boolean).sort();
      const detail = [...new Set(ps.map(c => (c.detail || '') + (!sum && c.amount && ps.filter(x => x.amount).length > 1 ? ': ' + money(c.amount) : '')).filter(Boolean))].join(' · ');
      return {...o, amount: amts.some(Boolean) ? (sum ? amts.reduce((a, b) => a + b, 0) : Math.max(...amts)) : null,
        records: ps.reduce((t, c) => t + (c.records || 1), 0), first_date: dates[0] || null, last_date: dates[dates.length - 1] || null, detail: detail || null,
        source_url: (ps.find(c => c.source_url) || {}).source_url || null, checked_by_hand: ps.some(c => c.checked_by_hand) || undefined,
        merged_from: (ps.find(c => c.merged_from) || {}).merged_from};
    }).sort((a, b) => (b.amount || 0) - (a.amount || 0) || String(a.other.name).localeCompare(String(b.other.name)));
  }
  // A hand-checked official gets an "Official" badge. When the build also listed the same person (as a board member
  // or business officer on the same record), the API has already merged the two into this one row.
  const what = c => c.merged_from && c.relation === 'board' ? 'Board member' : (c.other.kind_label || KIND[c.other.kind] || '');
  const rowHtml = c => `<tr><th scope="row">${c.other.photo ? `<img class="pf-row-ph" src="${esc(rel(c.other.photo))}" alt="" width="32" height="32" loading="lazy" decoding="async">` : ''}${c.other.page_url ? `<a href="${esc(c.other.page_url)}">${esc(c.other.name)}</a>` : esc(c.other.name)}${c.other.kind === 'person' && c.checked_by_hand ? ' <span class="pf-badge">Official</span>' : ''}<small>${esc(what(c))}${c.checked_by_hand ? ' · checked by hand' : ''}</small></th>
        <td class="wrap small">${esc(c.detail || '')}</td><td class="num">${c.amount ? money(c.amount) : ''}${c.records > 1 ? `<small>${c.records} records</small>` : ''}</td>
        <td class="small">${esc([c.first_date, c.last_date].filter((x, i, a) => x && a.indexOf(x) === i).join(' to '))}</td><td>${c.source_url ? `<a class="src" href="${esc(c.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}</td></tr>`;
  // a business's state filing (new-businesses) and the restaurants it holds a license for (restaurants)
  const LEVEL = {ok: 'ok', warning: 'warn', fine: 'bad', closed: 'bad'};
  function facts(e) {
    let h = '';
    const f = e.filing;
    if (f) h += `<section class="pf-grp"><div class="sec-hd"><h3>State filing</h3><span class="muted">Florida Division of Corporations</span></div>
      <p>${esc(f.filing_type)} filed ${esc(f.filed_date)}${f.city ? ', ' + esc(f.city) : ''}. ${f.status === 'Active' ? 'Active' : 'Inactive'}${f.latest_annual_report ? `; latest annual report ${esc(f.latest_annual_report)}` : ''}.
      <a href="${esc(f.source_url)}" target="_blank" rel="noopener">State record</a> (officers and registered agent). <a href="/new-businesses">New businesses →</a></p></section>`;
    const of = e.officers || [];
    if (of.length) {  // one line per person, every title they hold on the filing
      const by = new Map();
      of.forEach(o => { const k = (o.entity_id || o.name).toLowerCase(); const x = by.get(k) || by.set(k, {...o, titles: []}).get(k); if (!x.titles.includes(o.title)) x.titles.push(o.title); });
      const ppl = [...by.values()].sort((a, b) => (a.titles.includes('Registered agent') && a.titles.length === 1) - (b.titles.includes('Registered agent') && b.titles.length === 1) || a.name.localeCompare(b.name));
      h += `<section class="pf-grp"><div class="sec-hd"><h3>Officers</h3><span class="muted">${ppl.length} · as filed with the state (Sunbiz)</span></div>
      <div class="tablewrap"><table class="tx-table vd-table" data-tt="off"><tbody>${ppl.map(o => `<tr><th scope="row">${o.page_url ? `<a href="${esc(o.page_url)}">${esc(o.name)}</a>` : esc(o.name)}${o.official ? ' <span class="pf-badge">Official</span>' : ''}<small>${esc(o.kind === 'organization' ? 'Company' : 'Person')}</small></th>
        <td class="wrap small">${esc(o.titles.join(' · '))}</td><td><a class="src" href="${esc(o.source_url)}" target="_blank" rel="noopener">Source</a></td></tr>`).join('')}</tbody></table></div></section>`;
    }
    const rs = e.restaurants || [];
    if (rs.length) h += `<section class="pf-grp"><div class="sec-hd"><h3>Restaurant licenses</h3><span class="muted">${rs.length} · state food safety inspections</span></div>
      <div class="tablewrap"><table class="tx-table vd-table" data-tt="off"><tbody>${rs.map(r => `<tr><td><a href="${esc(r.page_url)}">${esc(r.name)}</a><small>${esc([r.kind, r.city, r.licensed_now ? null : 'no longer licensed'].filter(Boolean).join(' · '))}</small></td>
        <td class="wrap small"><span class="pf-res ${LEVEL[r.last_result_level] || ''}">${esc(r.last_result || 'Not inspected yet')}</span>${r.closures ? ` · ${r.closures} emergency closure${r.closures > 1 ? 's' : ''}` : ''}</td><td class="small">${esc(r.last_inspection || '')}</td></tr>`).join('')}</tbody></table></div></section>`;
    return h;
  }
  function list(d) {
    const box = document.getElementById('pfList'); if (!box) return;
    const groups = new Map();
    fold(d.connections).forEach(c => { const k = c.relation + ':' + c.direction; (groups.get(k) || groups.set(k, []).get(k)).push(c); });
    const keys = [...groups.keys()].sort((a, b) => ORDER.indexOf(a.split(':')[0]) - ORDER.indexOf(b.split(':')[0]));
    const SHOW = 25;
    box.innerHTML = keys.map(k => {
      const rs = groups.get(k), lbl = rs[0].label, tot = rs.reduce((t, c) => t + (c.amount || 0), 0);
      const row = rowHtml;
      return `<section class="pf-grp"><div class="sec-hd"><h3>${esc(lbl.charAt(0).toUpperCase() + lbl.slice(1))}</h3><span class="muted">${rs.length.toLocaleString('en-US')}${tot ? ' · ' + money(tot) + ' in the records' : ''}</span></div>
        <div class="tablewrap"><table class="tx-table vd-table" data-tt="off" data-cols="|What|Amount|Dates|"><tbody>${rs.slice(0, SHOW).map(row).join('')}</tbody></table></div>
        ${rs.length > SHOW ? `<button type="button" class="pill pf-more" data-k="${esc(k)}">Show all ${rs.length.toLocaleString('en-US')}</button>` : ''}</section>`;
    }).join('') || (d.entity.filing || d.entity.restaurants || d.entity.officers ? '' : '<p class="muted">No connections in the records yet.</p>');
    box.insertAdjacentHTML('afterbegin', facts(d.entity));
    box.querySelectorAll('.pf-more').forEach(b => b.addEventListener('click', () => {
      const rs = groups.get(b.dataset.k), tb = b.previousElementSibling.querySelector('tbody');
      tb.innerHTML = rs.map(rowHtml).join('');
      b.remove();
    }));
    const live = d.connections.filter(c => c.checked_by_hand);
    const lb = document.getElementById('pfLive');
    if (lb) lb.hidden = !live.length;
  }

  function draw() { if (!D) return; if (!embedded) header(D.entity); net(D); list(D); }
  draw();
  let t; addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => D && net(D), 200); });
  if (!id) return;
  fetch('/api/v1/entities/' + encodeURIComponent(id)).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(j => {
    const e = j.data.entity;
    if (!embedded && e.page_url && decodeURIComponent(location.pathname.replace(/\/$/, '')) !== decodeURIComponent(e.page_url)) { location.replace(e.page_url); return; }
    D = j.data; draw();
  }).catch(s => {
    if (D) return;
    const h = document.getElementById('pfHead');
    if (h) h.innerHTML = `<header class="tx-top"><div class="tx-brand"><span class="eyebrow"><a href="/connections">Connections</a></span><h1>${s === 404 ? 'No profile with that name' : 'This profile could not load'}</h1>
      <p class="lede">${s === 404 ? 'The link may be out of date.' : 'Try again in a moment.'} <a href="/search">Search the site</a> or start from the <a href="/connections">Connections network</a>.</p></div></header>`;
    const n = document.getElementById('pfNet'); if (n) n.innerHTML = '';
  });
})();
