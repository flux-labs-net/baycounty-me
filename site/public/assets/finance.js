// BayCounty.me finance workspace (/finance). Talks only to /api/finance.
// Viewers (commissioners) get every screen read-only: no upload tab, no review controls, no note box.
(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const usd = (n, cents) => n == null || isNaN(n) ? '—' : (n < 0 ? '−' : '') + '$' + Math.abs(Number(n)).toLocaleString('en-US', cents ? {minimumFractionDigits: 2, maximumFractionDigits: 2} : {maximumFractionDigits: 0});
  const short = n => { const a = Math.abs(n); return a >= 1e6 ? '$' + (n / 1e6).toFixed(1) + 'M' : a >= 1e3 ? '$' + Math.round(n / 1e3) + 'K' : usd(n); };
  const pct = x => x == null ? '—' : Math.round(x * 100) + '%';
  const day = s => { if (!s) return '—'; const d = new Date(String(s).slice(0, 10) + 'T12:00:00Z'); return d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC'}); };
  const month = ym => new Date(ym + '-15T12:00:00Z').toLocaleDateString('en-US', {month: 'short', timeZone: 'UTC'});
  const ROLE = {viewer: 1, auditor: 1, uploader: 2, reviewer: 3, owner: 4};
  const RULES = {file_tie: 'File doesn’t tie', rec_overdue: 'Bank rec overdue', rec_difference: 'Unreconciled difference', stale_check: 'Stale check',
    over_budget: 'Over budget', burn_rate: 'Ahead of the year', duplicate_payment: 'Possible duplicate', split_purchase: 'Possible split purchase',
    round_or_weekend: 'Round-dollar or weekend', payee_spike: 'Vendor spike', audit_repeat: 'Repeat audit finding'};
  const SHAPES = {budget: 'Budget vs. actual', disbursements: 'Check register', bank_transactions: 'Bank statement', bank_recs: 'Bank reconciliations'};
  const STATUS = {open: 'Open', follow_up: 'Follow-up', referred: 'Referred to auditor', explained: 'Explained', cleared: 'Cleared'};

  let me = null, ws = null, role = 'viewer', overview = null;
  const PAGE_TITLE = document.title;
  const NEED = {read: 1, upload: 2, review: 3, manage: 4, viewer: 1, uploader: 2, reviewer: 3, owner: 4};
  const can = need => (ROLE[role] || 0) >= NEED[need];

  async function api(action, {method = 'GET', body, params} = {}) {
    const qs = new URLSearchParams({action, ...(ws && action !== 'login' && action !== 'verify' ? {workspace: ws} : {}), ...(params || {})});
    const r = await fetch('/api/finance?' + qs, {method, credentials: 'same-origin',
      headers: method === 'POST' ? {'Content-Type': 'application/json', 'X-BCM-Finance': '1'} : {},
      body: body ? JSON.stringify({...(ws ? {workspace: ws} : {}), ...body}) : undefined});
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && !['login', 'verify'].includes(action)) { showSignin(); throw new Error('Signed out'); }
    if (!r.ok) throw Object.assign(new Error(j.error || 'Something went wrong. Try again.'), {status: r.status, body: j});
    return j;
  }

  // ---------- sign in ----------
  let pendingEmail = '';
  function showSignin() { $('#app').hidden = true; $('#signin').hidden = false; $('#email-form').hidden = false; $('#code-form').hidden = true; }
  $('#email-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button'); btn.disabled = true; $('#signin-msg').textContent = '';
    try {
      pendingEmail = e.target.email.value.trim();
      await api('login', {method: 'POST', body: {email: pendingEmail}});
      $('#email-form').hidden = true; $('#code-form').hidden = false;
      $('#code-sent').innerHTML = `If <b>${esc(pendingEmail)}</b> has access, a code is on its way. It expires in 10 minutes.`;
      $('#code-form').code.focus();
    } catch (err) { $('#signin-msg').textContent = err.message; }
    btn.disabled = false;
  });
  $('#code-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]'); btn.disabled = true; $('#signin-msg').textContent = '';
    try { await api('verify', {method: 'POST', body: {email: pendingEmail, code: e.target.code.value}}); e.target.reset(); await start(); }
    catch (err) { $('#signin-msg').textContent = err.message; }
    btn.disabled = false;
  });
  $('#code-back').addEventListener('click', () => { $('#code-form').hidden = true; $('#email-form').hidden = false; $('#signin-msg').textContent = ''; });
  $('#signout').addEventListener('click', async () => { await api('logout', {method: 'POST'}).catch(() => {}); location.reload(); });

  // ---------- tabs ----------
  const loaders = {overview: loadOverview, flags: () => loadFlags(true), upload: () => loadEmailed(), files: loadFiles, people: loadPeople, packet: loadPacket};
  function tab(name, push = true) {
    if (!loaders[name]) name = 'overview';
    const b = $(`[role=tab][data-tab="${name}"]`);
    if (!b || b.hidden) name = 'overview';
    $$('[role=tab]').forEach(x => x.setAttribute('aria-selected', String(x.dataset.tab === name)));
    $$('[data-panel]').forEach(p => { p.hidden = p.id !== 'p-' + name; });
    if (push) history.replaceState(null, '', '#' + name);
    if (name !== 'packet') document.title = PAGE_TITLE;
    loaders[name]();
  }
  $$('[role=tab]').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));
  document.addEventListener('click', e => { const g = e.target.closest('[data-go]'); if (g) tab(g.dataset.go); });

  async function start() {
    let j;
    try { j = await api('workspaces'); } catch (e) { if (e.message !== 'Signed out') showSignin(); return; }
    me = j;
    if (!j.workspaces.length) { showSignin(); $('#signin-msg').textContent = 'You’re signed in, but no workspace has given you access yet.'; return; }
    const saved = (() => { try { return localStorage.getItem('fin-ws'); } catch (e) { return null; } })();
    const w = j.workspaces.find(x => x.id === saved) || j.workspaces[0];
    ws = w.id; role = w.role;
    if (j.workspaces.length > 1) {
      const sel = $('#ws-pick'); sel.hidden = false;
      sel.innerHTML = j.workspaces.map(x => `<option value="${esc(x.id)}"${x.id === ws ? ' selected' : ''}>${esc(x.name)}</option>`).join('');
      sel.onchange = () => { try { localStorage.setItem('fin-ws', sel.value); } catch (e) {} location.reload(); };
    } else $('#ws-name').textContent = w.name;
    $('#who').textContent = `${j.email} · ${role === 'auditor' ? 'auditor' : role}`;
    $$('[role=tab][data-min]').forEach(b => { b.hidden = !can(b.dataset.min); });
    $('#signin').hidden = true; $('#app').hidden = false;
    const want = location.hash.slice(1);
    tab(want || 'overview', false);
  }

  // ---------- overview ----------
  // A department is "ahead" when spending plus open POs runs more than 10 points past the share of the year gone, or
  // past its budget. Debt service is paid once a year, so it is never ahead.
  const usedShare = d => (d.actual + d.encumbered) / d.budget;
  const isOver = d => d.budget > 0 && !/debt\s*service/i.test(d.department) && usedShare(d) > 1.0001;
  const isAhead = (d, el) => d.budget > 0 && !/debt\s*service/i.test(d.department) && (usedShare(d) > 1.0001 || usedShare(d) - (el || 0) > 0.10);
  function paceChart(b, {compact = false} = {}) {
    if (!b || !b.departments.length) return '';
    const el = b.elapsed ?? 0;
    const rows = b.departments.filter(d => d.budget > 0);
    const mx = Math.max(1, ...rows.map(d => (d.actual + d.encumbered) / d.budget)) * 1.04;
    const html = rows.map(d => {
      const u = d.actual / d.budget, e = d.encumbered / d.budget, used = u + e;
      const ahead = isAhead(d, el);
      return `<div class="dept${ahead ? ' ahead' : ''}"><span class="nm" title="${esc(d.department)}">${esc(d.department)}</span>
        <span class="track" role="img" aria-label="${esc(d.department)}: ${pct(used)} of ${usd(d.budget)} used"><span class="used" style="width:${(Math.min(u, mx) / mx * 100).toFixed(2)}%"></span><span class="enc" style="left:${(u / mx * 100).toFixed(2)}%;width:${(Math.max(0, Math.min(e, mx - u)) / mx * 100).toFixed(2)}%"></span><i class="mark" style="left:${(el / mx * 100).toFixed(2)}%"></i></span>
        <span class="amt"><b>${pct(used)}</b> of ${compact ? short(d.budget) : usd(d.budget)}</span></div>`;
    }).join('');
    return `<div class="pace" style="--el:${(el / mx).toFixed(5)}">${html}<span class="pace-rule${el / mx > 0.8 ? ' flip' : ''}"><span>${pct(el)} of the year</span></span></div>
      <div class="legend"><span><i></i>Spent</span><span><i class="e"></i>On open purchase orders</span>${rows.some(d => isAhead(d, el)) ? '<span><i class="o"></i>More than 10 points ahead of the year, or over budget</span>' : ''}<span><i class="r"></i>Share of the fiscal year gone</span></div>`;
  }
  function flagItem(f) {
    return `<li><button type="button" data-flag="${f.id}"><span class="sev ${f.severity}">${f.severity === 'urgent' ? 'Urgent' : f.severity === 'review' ? 'Review' : 'Info'}</span>
      <span class="t">${esc(f.title)}${f.status !== 'open' ? `<span class="st">${esc(STATUS[f.status] || f.status)}</span>` : ''}</span>
      <span class="d">${f.amount_at_risk ? usd(f.amount_at_risk) : ''}</span>
      <span class="m">${esc(RULES[f.rule] || f.rule)} · first seen ${day(f.first_seen_at)}</span></button></li>`;
  }

  async function loadOverview() {
    $('#ov-lead').textContent = 'Loading…';
    try { overview = await api('overview'); } catch (e) { if (e.message !== 'Signed out') $('#ov-lead').textContent = e.message; return; }
    const o = overview, b = o.budget, f = o.flags;
    $('#flag-count').textContent = f.open ? ' ' + f.open : '';
    const parts = [];
    if (b) {
      const used = (b.total_actual + b.total_encumbered) / (b.total_budget || 1);
      const ahead = b.departments.filter(d => d.budget > 0 && !/debt\s*service/i.test(d.department) && ((d.actual + d.encumbered) / d.budget - (b.elapsed || 0) > 0.10 || d.actual + d.encumbered > d.budget));
      parts.push(`As of <b>${day(b.as_of)}</b>, departments have spent or committed <b>${usd(b.total_actual + b.total_encumbered)}</b> of <b>${usd(b.total_budget)}</b> (${pct(used)}) with ${pct(b.elapsed)} of FY${b.fiscal_year} gone.`);
      if (ahead.length) parts.push(`<b>${ahead.length} ${ahead.length === 1 ? 'department is' : 'departments are'}</b> running ahead of the year.`);
    }
    parts.push(f.open ? `<b>${f.open} ${f.open === 1 ? 'item needs' : 'items need'} attention</b>${f.urgent ? `, ${f.urgent} urgent` : ''}.` : 'Nothing needs attention right now.');
    if (!b && !o.payments) parts.unshift('No files have been added yet.');
    $('#ov-lead').innerHTML = parts.join(' ');

    $('#ov-budget').innerHTML = b ? `<h2 class="h2" style="margin-top:0">Departments: spending against the year</h2>
      <p class="sub">Spending plus open purchase orders as a share of each department's budget. The line marks how much of the fiscal year has passed. Revenue lines are left out.</p>
      <div class="panel">${paceChart(b)}</div>` : (can('upload') ? `<div class="panel empty">Add a budget-vs-actual report to see each department's pace. <button class="btn" data-go="upload" type="button" style="margin-left:8px">Add a file</button></div>` : '');

    const p = o.payments;
    $('#ov-pay-sub').textContent = p ? `Total ${usd(p.total)} in the 12 months through ${day(p.through)}.` : 'No check register added yet.';
    $('#ov-pay').innerHTML = p ? barChart(p.by_month) : '<p class="empty">—</p>';
    const top = p ? p.top_vendors : [], max = top.length ? top[0].total : 1;
    $('#ov-vendors').innerHTML = top.length ? top.map(v => `<li><span class="nm" title="${esc(v.payee)}">${esc(v.payee)}</span><span class="num">${usd(v.total)}</span><span class="bar"><i style="width:${(v.total / max * 100).toFixed(1)}%"></i></span></li>`).join('') : '<li class="muted">—</li>';

    const acc = o.bank_accounts || [];
    $('#ov-bank').innerHTML = acc.length ? `<div class="tw"><table class="t"><thead><tr><th>Account</th><th>Latest rec on file</th><th>Reconciled on</th></tr></thead><tbody>${acc.map(a => `<tr><td>${esc(a.account || 'Account')}</td><td>${a.last_rec ? day(a.last_rec) : '<span class="sev urgent">None on file</span>'}</td><td>${a.last_reconciled_on ? day(a.last_reconciled_on) : '—'}</td></tr>`).join('')}</tbody></table></div>`
      : '<div class="panel empty">No bank statements or reconciliations added yet.</div>';
    $('#ov-flags').innerHTML = f.top.length ? f.top.map(flagItem).join('') : '<li class="empty">No open flags.</li>';
  }

  function barChart(rows) {
    if (!rows.length) return '';
    const W = 560, H = 190, L = 44, B = 24, T = 10, max = Math.max(...rows.map(r => r.total)) * 1.08 || 1;
    const bw = (W - L - 8) / rows.length;
    const ticks = [0, .5, 1].map(t => t * max);
    const grid = ticks.map(v => { const y = T + (H - T - B) * (1 - v / max); return `<line x1="${L}" x2="${W}" y1="${y}" y2="${y}" stroke="var(--line)"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${short(v)}</text>`; }).join('');
    const bars = rows.map((r, i) => { const h = (H - T - B) * r.total / max, x = L + i * bw + 3, y = H - B - h;
      return `<rect x="${x}" y="${y}" width="${Math.max(2, bw - 6)}" height="${h}" rx="2" fill="var(--bar)"><title>${month(r.month)} ${r.month.slice(0, 4)}: ${usd(r.total)}</title></rect>${i % (rows.length > 8 ? 2 : 1) === 0 ? `<text x="${x + (bw - 6) / 2}" y="${H - 6}" text-anchor="middle">${month(r.month)}</text>` : ''}`; }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Payments by month">${grid}${bars}</svg>`;
  }

  // ---------- flags ----------
  let flagOffset = 0;
  $('#f-rule').innerHTML += Object.entries(RULES).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
  ['#f-status', '#f-sev', '#f-rule'].forEach(s => $(s).addEventListener('change', () => loadFlags(true)));
  $('#f-more').addEventListener('click', () => loadFlags(false));
  async function loadFlags(reset) {
    if (reset) { flagOffset = 0; $('#f-list').innerHTML = ''; }
    const params = {status: $('#f-status').value, limit: 50, offset: flagOffset};
    if ($('#f-sev').value) params.severity = $('#f-sev').value;
    if ($('#f-rule').value) params.rule = $('#f-rule').value;
    try {
      const j = await api('flags', {params});
      $('#f-list').insertAdjacentHTML('beforeend', j.flags.map(flagItem).join(''));
      flagOffset += j.flags.length;
      $('#f-sum').textContent = j.total ? `${j.total} ${j.total === 1 ? 'flag' : 'flags'}, highest stakes first.` : 'No flags match.';
      $('#f-more').hidden = flagOffset >= j.total;
    } catch (e) { $('#f-sum').textContent = e.message; }
  }

  // ---------- flag detail ----------
  const COLS = {
    disbursements: [['paid_on', 'Date', 'd'], ['doc_no', 'Check'], ['payee', 'Payee'], ['invoice_no', 'Invoice'], ['amount', 'Amount', '$'], ['is_void', 'Void', 'b']],
    budget_lines: [['as_of', 'As of', 'd'], ['department', 'Department'], ['account', 'Account'], ['description', 'Line'], ['amended_budget', 'Budget', '$'], ['actual_ytd', 'Spent', '$'], ['encumbered', 'On order', '$']],
    bank_transactions: [['posted_on', 'Date', 'd'], ['account_label', 'Account'], ['check_no', 'Check'], ['description', 'Description'], ['amount', 'Amount', '$']],
    bank_recs: [['account_label', 'Account'], ['period_end', 'Month end', 'd'], ['statement_balance', 'Bank', '$'], ['outstanding_checks', 'Outstanding', '$'], ['deposits_in_transit', 'In transit', '$'], ['book_balance', 'Books', '$'], ['reconciled_on', 'Reconciled', 'd'], ['approved_by', 'Approved by']],
    uploads: [['original_name', 'File'], ['uploaded_at', 'Added', 'd'], ['parsed_total', 'Rows add to', '$'], ['printed_total', 'File total', '$'], ['status', 'Status']],
    audit_findings: [['fiscal_year', 'Year'], ['finding_id', 'Finding'], ['title', 'Title'], ['source_url', 'Report', 'u']],
  };
  const TNAME = {disbursements: 'Payments', budget_lines: 'Budget lines', bank_transactions: 'Bank transactions', bank_recs: 'Reconciliations', uploads: 'File', audit_findings: 'Audit reports'};
  function cell(v, kind) {
    if (v == null || v === '') return '<td class="muted">—</td>';
    if (kind === '$') return `<td class="num">${usd(Number(v), true)}</td>`;
    if (kind === 'd') return `<td style="white-space:nowrap">${day(v)}</td>`;
    if (kind === 'b') return `<td>${v ? 'Void' : ''}</td>`;
    if (kind === 'u') return `<td><a href="${esc(v)}" target="_blank" rel="noopener">Open</a></td>`;
    return `<td>${esc(v)}</td>`;
  }
  document.addEventListener('click', e => { const b = e.target.closest('[data-flag]'); if (b) openFlag(b.dataset.flag); });
  $('#dr-close').addEventListener('click', () => $('#drawer').close());
  $('#drawer').addEventListener('click', e => { if (e.target === $('#drawer')) $('#drawer').close(); });

  async function openFlag(id) {
    const d = $('#drawer');
    $('#dr-title').textContent = 'Loading…'; $('#dr-sev').innerHTML = ''; $('#dr-body').innerHTML = '';
    if (!d.open) d.showModal();
    let f;
    try { f = await api('flag', {params: {id}}); } catch (e) { $('#dr-title').textContent = e.message; return; }
    $('#dr-sev').innerHTML = `<span class="sev ${f.severity}">${f.severity === 'urgent' ? 'Urgent' : f.severity === 'review' ? 'Review' : 'Info'} · ${esc(RULES[f.rule] || f.rule)}</span>`;
    $('#dr-title').textContent = f.title;
    const tables = Object.entries(f.rows || {}).filter(([, r]) => r.length).map(([t, rows]) => {
      const cols = COLS[t] || Object.keys(rows[0]).map(k => [k, k]);
      return `<h3 class="h2" style="font-size:.92rem">${TNAME[t] || t}</h3><div class="tw"><table class="t"><thead><tr>${cols.map(([, l, k]) => `<th${k === '$' ? ' class="num"' : ''}>${l}</th>`).join('')}</tr></thead>
        <tbody>${rows.map(r => `<tr>${cols.map(([c, , k]) => cell(r[c], k)).join('')}</tr>`).join('')}</tbody></table></div>`;
    }).join('');
    const notes = f.notes.length ? `<h3 class="h2" style="font-size:.92rem">Review history</h3><ul class="notes">${f.notes.map(n => `<li><span class="by">${esc(n.author)} · ${day(n.created_at)} · ${esc(STATUS[n.status] || n.status || '')}</span><br>${esc(n.note || '')}</li>`).join('')}</ul>` : '';
    const review = can('review') ? `<form class="rv-box" id="rv"><b>Review</b>
        <div class="seg" role="group" aria-label="Status">${['open', 'follow_up', 'explained', 'referred'].map(s => `<button type="button" data-st="${s}" aria-pressed="${f.status === s}">${STATUS[s]}</button>`).join('')}</div>
        <label class="f">Note<textarea name="note" placeholder="What you found, or why this is fine. Required for Explained."></textarea></label>
        <div class="row"><button class="btn primary" type="submit">Save review</button><span class="small" id="rv-msg" role="status"></span></div></form>`
      : `<p class="readonly">Status: <b>${esc(STATUS[f.status] || f.status)}</b>. Finance staff review and mark flags; this view is read-only.</p>`;
    $('#dr-body').innerHTML = `<p>${esc(f.detail || '')}</p><p class="small muted">${f.amount_at_risk ? `At stake: <b>${usd(f.amount_at_risk, true)}</b> · ` : ''}First seen ${day(f.first_seen_at)} · last checked ${day(f.last_seen_at)}</p>${tables}${notes}${review}`;
    const form = $('#rv');
    if (!form) return;
    let st = f.status === 'cleared' ? 'open' : f.status;
    form.querySelectorAll('[data-st]').forEach(b => b.addEventListener('click', () => { st = b.dataset.st; form.querySelectorAll('[data-st]').forEach(x => x.setAttribute('aria-pressed', String(x === b))); }));
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('[type=submit]'); btn.disabled = true;
      try {
        await api('flag-status', {method: 'POST', body: {id: Number(id), status: st, note: form.note.value}});
        $('#rv-msg').innerHTML = '<span class="ok">Saved.</span>';
        setTimeout(() => { d.close(); const cur = $('[role=tab][aria-selected=true]').dataset.tab; loaders[cur](); }, 500);
      } catch (err) { $('#rv-msg').innerHTML = `<span class="err">${esc(err.message)}</span>`; }
      btn.disabled = false;
    });
  }

  // ---------- upload ----------
  let up = null; // {file, content (base64) | path, preview}
  const drop = $('#drop'), input = $('#file');
  drop.addEventListener('click', () => input.click());
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); } });
  ['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) choose(e.dataTransfer.files[0]); });
  input.addEventListener('change', () => { if (input.files[0]) choose(input.files[0]); });
  $('#pv-reset').addEventListener('click', resetUpload);
  function resetUpload() { up = null; input.value = ''; $('#pv').hidden = true; drop.hidden = false; $('#up-msg').textContent = ''; loadEmailed(); }

  const toB64 = file => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = rej; r.readAsDataURL(file); });
  async function choose(file) {
    if (file.size > 50 * 1024 * 1024) { $('#up-msg').innerHTML = '<span class="err">That file is over 50 MB.</span>'; return; }
    $('#up-msg').textContent = `Reading ${file.name}…`;
    up = {file};
    try {
      if (file.size <= 3 * 1024 * 1024) up.content = await toB64(file);
      else {
        const u = await api('upload-url', {method: 'POST', body: {filename: file.name}});
        const r = await fetch(u.url, {method: 'PUT', body: file, headers: {'x-upsert': 'true', 'Content-Type': file.type || 'application/octet-stream'}});
        if (!r.ok) throw new Error('The file didn’t upload (' + r.status + '). Try again.');
        up.path = u.path;
      }
      await preview({});
    } catch (e) { $('#up-msg').innerHTML = `<span class="err">${esc(e.message)}</span>`; }
  }
  function extras() {
    const o = {};
    if (!$('#pv-asof-l').hidden && $('#pv-asof').value) o.as_of = $('#pv-asof').value;
    if (!$('#pv-acct-l').hidden && $('#pv-acct').value.trim()) o.account = $('#pv-acct').value.trim();
    if ($('#pv-total').value.trim()) o.printed_total = $('#pv-total').value.trim();
    if ($('#pv-system').value.trim()) o.source_system = $('#pv-system').value.trim();
    return o;
  }
  async function preview(over) {
    const body = {filename: up.file.name, ...(up.preview ? {upload_id: up.preview.upload_id} : {}), ...(up.content ? {content: up.content} : {path: up.path}), ...extras(), ...over};
    const j = await api('ingest', {method: 'POST', body});
    up.preview = j; up.mapping = j.mapping;
    drop.hidden = true; $('#pv').hidden = false; $('#up-msg').textContent = '';
    renderPreview(j);
  }
  const FIELD = {fund: 'Fund', department: 'Department', account: 'Account', description: 'Description', type: 'Revenue or expense', original_budget: 'Original budget',
    amended_budget: 'Amended budget', actual_ytd: 'Actual year to date', encumbered: 'Encumbered', paid_on: 'Payment date', doc_no: 'Check or payment no.',
    payee: 'Payee', amount: 'Amount', invoice_no: 'Invoice no.', status: 'Void or status', method: 'Payment type', posted_on: 'Posting date', debit: 'Debit',
    credit: 'Credit', check_no: 'Check no.', balance: 'Running balance', period_end: 'Month end', statement_balance: 'Bank balance', book_balance: 'Book balance',
    outstanding_checks: 'Outstanding checks', deposits_in_transit: 'Deposits in transit', other_adjustments: 'Other adjustments', reconciled_on: 'Date reconciled',
    prepared_by: 'Prepared by', approved_by: 'Approved by', is_void: 'Void', account_label: 'Account', as_of: 'As of'};
  function renderPreview(j) {
    $('#pv-title').textContent = up.file.name;
    $('#pv-shape').value = j.shape || 'disbursements';
    $('#pv-asof-l').hidden = j.shape !== 'budget';
    if (j.shape === 'budget' && j.period && j.period.end && !$('#pv-asof').value) $('#pv-asof').value = j.period.end;
    $('#pv-acct-l').hidden = !(j.shape === 'bank_transactions' || j.shape === 'bank_recs') || (j.missing || []).every(m => !/account/.test(m)) && !$('#pv-acct').value;
    const t = j.tie;
    $('#pv-tie').innerHTML = !j.ok ? `<div class="tie mismatch"><div><b>Not ready yet.</b> Missing: ${esc((j.missing || []).join('; '))}. Pick the right columns below or fill in the box above, then check again.</div></div>`
      : t && t.status === 'ties' ? `<div class="tie ties"><div><b>${j.row_count.toLocaleString()} rows add up to ${usd(j.parsed_total, true)}</b>, matching the file's total. ${j.period.start ? `Covers ${day(j.period.start)} to ${day(j.period.end)}.` : ''}</div></div>`
      : t && t.status === 'mismatch' ? `<div class="tie mismatch"><div><b>The rows add up to ${usd(j.parsed_total, true)}, but the file's total is ${usd(j.printed_total, true)}</b> (off by ${usd(t.difference, true)}). Check for missing pages or rows. If you add it anyway, it will be held and none of its rows will be used.</div></div>`
      : `<div class="tie no_total"><div><b>${j.row_count.toLocaleString()} rows, adding up to ${usd(j.parsed_total, true)}.</b> No report total was found to check against. Enter it above from the last page to tie out the file.</div></div>`;
    if (j.already_added) $('#pv-tie').innerHTML += `<div class="tie mismatch"><div>This exact file was already added on ${day(j.already_added.on)}.</div></div>`;
    $('#pv-mapsum').textContent = (j.used_saved_mapping ? 'using the saved layout for this report. ' : '') + Object.entries(j.mapping || {}).map(([f, c]) => `${FIELD[f] || f} ← ${c}`).join(', ');
    const opts = ['<option value="">(not in this file)</option>', ...(j.headers || []).filter(Boolean).map(h => `<option>${esc(h)}</option>`)].join('');
    $('#pv-map').innerHTML = (j.fields_available || []).map(f => `<label class="f">${FIELD[f] || f}<select data-field="${f}">${opts}</select></label>`).join('');
    $$('#pv-map select').forEach(s => { s.value = (j.mapping || {})[s.dataset.field] || ''; });
    const rows = j.sample || [], cols = rows.length ? Object.keys(rows[0]).filter(k => !['source_row', 'payee_key', 'account_hash', 'fiscal_year'].includes(k) && rows.some(r => r[k] !== null && r[k] !== '' && r[k] !== false)) : [];
    $('#pv-sample').innerHTML = rows.length ? `<table class="t"><thead><tr>${cols.map(c => `<th>${esc(FIELD[c] || c.replace(/_/g, ' '))}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${cols.map(c => typeof r[c] === 'number' ? `<td class="num">${usd(r[c], true)}</td>` : `<td>${/^\d{4}-\d{2}-\d{2}$/.test(r[c] || '') ? day(r[c]) : esc(r[c] === true ? 'Yes' : r[c] === false ? '' : r[c])}</td>`).join('')}</tr>`).join('')}</tbody></table>` : '<p class="empty">No rows read yet.</p>';
    $('#pv-err').textContent = '';
    $('#pv-commit').disabled = !j.ok || !!j.already_added;
    $('#pv-note').textContent = (j.warnings || []).join(' ');
  }
  $('#pv-recheck').addEventListener('click', async () => {
    const mapping = {}; $$('#pv-map select').forEach(s => { mapping[s.dataset.field] = s.value || null; });
    try { await preview({shape: $('#pv-shape').value, mapping}); } catch (e) { $('#pv-err').textContent = e.message; }
  });
  $('#pv-shape').addEventListener('change', async () => { try { await preview({shape: $('#pv-shape').value}); } catch (e) { $('#pv-err').textContent = e.message; } });
  $('#pv-commit').addEventListener('click', async () => {
    const btn = $('#pv-commit'); btn.disabled = true; $('#pv-err').textContent = '';
    const mapping = {}; $$('#pv-map select').forEach(s => { mapping[s.dataset.field] = s.value || null; });
    try {
      const j = await api('ingest', {method: 'POST', body: {filename: up.file.name, upload_id: up.preview.upload_id, ...(up.content ? {content: up.content} : {path: up.path}),
        shape: $('#pv-shape').value, mapping, commit: true, ...extras()}});
      resetUpload();
      $('#up-msg').innerHTML = j.held ? `<span class="err">${esc(j.message)}</span>` : `<span class="ok">Added ${j.row_count.toLocaleString()} rows. The checks ran again: ${j.rules.flags} flags in total.</span> <button class="linkish btn quiet" data-go="flags" type="button">See flags</button>`;
    } catch (e) { $('#pv-err').textContent = e.message; btn.disabled = false; }
  });

  // ---------- emailed in (unreviewed imports from ingest.baycounty.me) ----------
  let emailed = [];
  async function loadEmailed() {
    if (!can('upload')) return;
    try {
      const {uploads} = await api('uploads');
      emailed = uploads.filter(u => u.status === 'preview' && /^email: /.test(u.uploaded_by || '') && u.storage_path);
    } catch (e) { emailed = []; }
    $('#em').hidden = !emailed.length;
    $('#em-t tbody').innerHTML = emailed.map(u => `<tr><td>${esc(u.original_name)}${u.error ? `<div class="small err">${esc(u.error)}</div>` : ''}</td>
      <td>${esc(SHAPES[u.shape] || 'Not recognized')}</td><td class="num">${u.row_count != null ? u.row_count.toLocaleString() : '—'}</td><td class="num">${usd(u.parsed_total, true)}</td>
      <td style="white-space:nowrap">${day(u.uploaded_at)}<br><span class="muted small">${esc(String(u.uploaded_by).replace(/^email: /, ''))}</span></td>
      <td><button class="btn" type="button" data-em="${u.id}">Review</button></td></tr>`).join('');
  }
  $('#em-t').addEventListener('click', async e => {
    const btn = e.target.closest('[data-em]'); if (!btn) return;
    const u = emailed.find(x => String(x.id) === btn.dataset.em); if (!u) return;
    up = {file: {name: u.original_name}, path: u.storage_path, preview: {upload_id: u.id}};
    btn.disabled = true;
    try { await preview({}); $('#em').hidden = true; } catch (err) { $('#up-msg').innerHTML = `<span class="err">${esc(err.message)}</span>`; }
    btn.disabled = false;
  });

  // ---------- files ----------
  async function loadFiles() {
    const tb = $('#files-t tbody'); tb.innerHTML = '<tr><td colspan="8" class="muted">Loading…</td></tr>';
    try {
      const {uploads} = await api('uploads');
      const shown = uploads.filter(u => u.status !== 'preview');
      tb.innerHTML = shown.length ? shown.map(u => `<tr><td>${esc(u.original_name)}</td><td>${esc(SHAPES[u.shape] || '—')}</td>
        <td style="white-space:nowrap">${u.period_start ? day(u.period_start) + (u.period_end && u.period_end !== u.period_start ? ' – ' + day(u.period_end) : '') : (u.period_end ? day(u.period_end) : '—')}</td>
        <td class="num">${u.row_count != null ? u.row_count.toLocaleString() : '—'}</td><td class="num">${usd(u.parsed_total, true)}</td>
        <td>${u.status === 'committed' ? (u.tie_status === 'ties' ? '<span class="ok">Added, ties</span>' : 'Added, no total') : u.status === 'held' ? `<span class="err">Held: off by ${usd(u.tie_difference, true)}</span>` : u.status === 'replaced' ? '<span class="muted">Withdrawn</span>' : esc(u.status)}</td>
        <td style="white-space:nowrap">${day(u.uploaded_at)}<br><span class="muted small">${esc(u.uploaded_by || '')}</span></td>
        <td style="white-space:nowrap"><button class="btn quiet" type="button" data-dl="${u.id}">Original</button>${can('upload') && ['committed', 'held'].includes(u.status) ? `<button class="btn quiet" type="button" data-rm="${u.id}">Withdraw</button>` : ''}</td></tr>`).join('')
        : `<tr><td colspan="8" class="empty">No files yet.${can('upload') ? ' <button class="btn" data-go="upload" type="button">Add a file</button>' : ''}</td></tr>`;
    } catch (e) { tb.innerHTML = `<tr><td colspan="8" class="err">${esc(e.message)}</td></tr>`; }
  }
  document.addEventListener('click', async e => {
    const dl = e.target.closest('[data-dl]'), rm = e.target.closest('[data-rm]');
    if (dl) { try { const j = await api('file', {params: {upload_id: dl.dataset.dl}}); location.href = j.url; } catch (err) { alert(err.message); } }
    if (rm && confirm('Withdraw this file? Its rows stop counting and the checks run again. The original stays on record.')) {
      try { await api('replace', {method: 'POST', body: {upload_id: Number(rm.dataset.rm)}}); loadFiles(); } catch (err) { alert(err.message); }
    }
  });

  // ---------- people ----------
  async function loadPeople() {
    const tb = $('#pp-t tbody');
    try {
      const {members} = await api('members');
      tb.innerHTML = members.map(m => `<tr><td>${esc(m.email)}</td><td>${esc(m.role)}</td><td>${day(m.created_at)}</td>
        <td>${m.email !== me.email ? `<button class="btn quiet" type="button" data-unmember="${esc(m.email)}">Remove</button>` : '<span class="muted small">You</span>'}</td></tr>`).join('');
    } catch (e) { tb.innerHTML = `<tr><td colspan="4" class="err">${esc(e.message)}</td></tr>`; }
  }
  $('#pp-form').addEventListener('submit', async e => {
    e.preventDefault();
    try { await api('members', {method: 'POST', body: {email: e.target.email.value, role: e.target.role.value}}); $('#pp-msg').innerHTML = `<span class="ok">${esc(e.target.email.value)} can now sign in at baycounty.me/finance.</span>`; e.target.reset(); loadPeople(); }
    catch (err) { $('#pp-msg').innerHTML = `<span class="err">${esc(err.message)}</span>`; }
  });
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-unmember]');
    if (!b || !confirm(`Remove ${b.dataset.unmember}'s access?`)) return;
    try { await api('members', {method: 'POST', body: {email: b.dataset.unmember, role: 'remove'}}); loadPeople(); } catch (err) { alert(err.message); }
  });

  // ---------- board packet ----------
  // Laid out like the branded sample report ("Monthly finance summary"): masthead with a navy rule, a one-paragraph
  // summary, the pace chart, the items needing attention, bank reconciliation status and the open audit finding.
  // Every name it prints (site, operator, government) comes from the place config the page was built with.
  const BRAND = (() => { try { return JSON.parse($('#brand').textContent); } catch (e) { return {}; } })();
  const SITE = BRAND.site || location.hostname, OPERATOR = BRAND.operator || '';
  const monthYear = s => new Date(String(s).slice(0, 7) + '-15T12:00:00Z').toLocaleDateString('en-US', {month: 'short', year: 'numeric', timeZone: 'UTC'});
  const monthLong = s => new Date(String(s).slice(0, 7) + '-15T12:00:00Z').toLocaleDateString('en-US', {month: 'long', timeZone: 'UTC'});
  const nextMonth = s => { const d = new Date(String(s).slice(0, 7) + '-15T12:00:00Z'); d.setUTCMonth(d.getUTCMonth() + 1); return d.toISOString().slice(0, 10); };
  const listAnd = a => a.length < 2 ? a.join('') : a.length === 2 ? a.join(' and ') : a.slice(0, -1).join(', ') + ', and ' + a[a.length - 1];
  const fyRange = m => { const n = k => new Date(Date.UTC(2000, k - 1, 1)).toLocaleDateString('en-US', {month: 'short', timeZone: 'UTC'});
    const end = new Date(Date.UTC(2001, m - 1, 0)); return `${n(m)} 1–${n(end.getUTCMonth() + 1)} ${end.getUTCDate()}`; };
  // Latest month whose reconciliation is due (30 days after month end) as of the report date.
  function dueMonth(asOf) {
    const t = Date.parse(String(asOf).slice(0, 10) + 'T12:00:00Z') - 30 * 864e5, d = new Date(t);
    const end = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0));
    return (end.getTime() <= t ? end : new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 0))).toISOString().slice(0, 10);
  }
  function recStatus(a, due) {
    if (!a.last_rec) return {cls: 'urgent', text: 'None on file'};
    if (a.last_rec.slice(0, 7) < due.slice(0, 7)) return {cls: 'urgent', text: `${monthLong(nextMonth(a.last_rec))} not on file`};
    const ob = (a.out_of_balance || []).slice(-1)[0];
    if (ob) return {cls: 'urgent', text: `${monthLong(ob)} out of balance`};
    if (a.late) return {cls: 'review', text: `${a.late} late this year`};
    return {cls: 'ok', text: 'Current'};
  }
  function packetLead(o, b, items) {
    const f = o.flags, parts = [];
    if (b) {
      const done = b.total_actual + b.total_encumbered, el = b.elapsed || 0;
      const rows = b.departments.filter(d => d.budget > 0);
      const over = rows.filter(isOver).map(d => d.department), ahead = rows.filter(d => isAhead(d, el) && !isOver(d));
      parts.push(`Through ${monthLong(b.as_of)}, departments have spent or committed <b>${usd(done)}</b> of their <b>${usd(b.total_budget)}</b> budgets (${pct(done / (b.total_budget || 1))}) with ${pct(el)} of the fiscal year gone.`);
      const bits = [];
      if (ahead.length) bits.push(`<b>${ahead.length} ${ahead.length === 1 ? 'department is' : 'departments are'}</b> running well ahead of the year`);
      if (over.length) bits.push(over.length > 3 ? `<b>${over.length} departments</b> are over budget` : `${esc(listAnd(over))} ${over.length === 1 ? 'is' : 'are'} over budget`);
      if (f.open) bits.push(`<b>${f.open} ${f.open === 1 ? 'item needs' : 'items need'} attention</b>${f.urgent ? `, ${f.urgent} urgent` : ''}`);
      if (bits.length) parts.push(listAnd(bits).replace(/^./, c => c.toUpperCase()) + '.');
      else parts.push('Nothing needs attention right now.');
    } else {
      parts.push(o.payments ? 'No budget-vs-actual report has been added yet.' : 'No files have been added yet.');
      parts.push(f.open ? `<b>${f.open} ${f.open === 1 ? 'item needs' : 'items need'} attention</b>${f.urgent ? `, ${f.urgent} urgent` : ''}.` : 'Nothing needs attention right now.');
    }
    return parts.join(' ');
  }
  function setPrintFooter(title) {
    // Running footer on every printed page (Chrome and Edge print these; other browsers skip it and keep the
    // closing note at the end of the packet).
    const q = t => '"' + String(t).replace(/["\\]/g, '\\$&').replace(/\n/g, ' ') + '"';
    let st = $('#pk-page'); if (!st) { st = document.createElement('style'); st.id = 'pk-page'; document.head.appendChild(st); }
    st.textContent = `@media print{@page{
      @bottom-left{content:${q(`${SITE}${OPERATOR ? ' · powered by ' + OPERATOR : ''}`)};font:400 7pt Poppins,sans-serif;color:#5A6372}
      @bottom-right{content:${q(title + ' · page ')} counter(page) " of " counter(pages);font:400 7pt Poppins,sans-serif;color:#5A6372}}}`;
  }
  async function loadPacket() {
    const el = $('#packet'); el.innerHTML = '<p class="muted">Preparing…</p>';
    try {
      const o = overview || (overview = await api('overview'));
      const fl = await api('flags', {params: {status: 'all', limit: 15}});
      // Most serious first, then dollars at stake.
      const SEV = {urgent: 0, review: 1, info: 2};
      const items = fl.flags.filter(f => f.status !== 'cleared').slice(0, 12)
        .sort((x, y) => (SEV[x.severity] ?? 3) - (SEV[y.severity] ?? 3) || (Math.abs(y.amount_at_risk || 0) - Math.abs(x.amount_at_risk || 0)));
      const b = o.budget, w = o.workspace;
      const gov = (BRAND.governments || {})[w.government_key] || w.name.replace(/\s*\(sample data\)\s*$/i, '');
      const title = 'Monthly finance summary';
      const asOf = (b && b.as_of) || o.as_of, due = dueMonth(asOf);
      const fyStart = w.fy_start_month || 10;
      const accts = o.bank_accounts || [], finds = o.audit_findings || [];
      setPrintFooter(title);
      document.title = `${gov} · ${title} · ${SITE}`;
      el.innerHTML = `<header class="pk-head">
          <div><p class="pk-kicker">${esc(gov)} · Finance review</p><h1>${title}</h1></div>
          <div class="pk-meta">${b ? `FY${b.fiscal_year} through ${day(b.as_of)}<br>` : ''}Prepared ${day(new Date().toISOString())}<br>${esc(SITE)}${OPERATOR ? ` · powered by ${esc(OPERATOR)}` : ''}</div>
        </header>
        ${w.sample ? `<p class="pk-note"><b>Sample.</b> This shows what the report looks like once the city’s monthly exports are loaded. The figures in this workspace are illustrative sample data, not the city’s records.</p>` : ''}
        <p class="pk-lead">${packetLead(o, b, items)}</p>
        ${b ? `<section class="pk-sec"><h2 class="h2">Departments: spending against the year</h2>
          <p class="sub">Year-to-date spending plus open purchase orders, as a share of each department’s budget. The line marks how much of the fiscal year (${fyRange(fyStart)}) has passed. Debt service is paid once a year, so 100% is expected.</p>
          <div class="panel">${paceChart(b)}</div></section>` : ''}
        <section class="pk-sec"><h2 class="h2">Needs attention</h2>
          <p class="sub">Ranked by dollars at stake and seriousness. Staff mark each item explained, follow-up or referred to the auditor. Each is a pattern worth a second look, not a finding of wrongdoing.</p>
          <table class="t na"><thead><tr><th>Severity</th><th>What the review found</th><th class="num">At stake</th><th>Status</th></tr></thead><tbody>
          ${items.map(f => `<tr><td><span class="sev ${f.severity}">${f.severity === 'urgent' ? 'Urgent' : f.severity === 'review' ? 'Review' : 'Info'}</span></td><td>${esc(f.title)}</td><td class="num">${f.amount_at_risk ? usd(f.amount_at_risk) : '—'}</td><td><span class="pill">${esc(STATUS[f.status] || f.status)}</span></td></tr>`).join('') || '<tr><td colspan="4" class="muted">No open items.</td></tr>'}
          </tbody></table></section>
        ${accts.length || finds.length ? `<div class="pk-cols">
          ${accts.length ? `<section class="pk-sec pk-keep"><h2 class="h2">Bank reconciliations</h2>
            <p class="sub">Each account’s latest reconciliation on file. Due within 30 days of month end.</p>
            <table class="t"><thead><tr><th>Account</th><th>Latest rec</th><th>Status</th></tr></thead><tbody>
            ${accts.map(a => { const s = recStatus(a, due); return `<tr><td>${esc(a.account || 'Account')}</td><td>${a.last_rec ? monthYear(a.last_rec) : '—'}</td><td><span class="sev ${s.cls}">${esc(s.text)}</span></td></tr>`; }).join('')}
            </tbody></table></section>` : '<div></div>'}
          ${finds.length ? `<section class="pk-sec pk-keep"><h2 class="h2">Open audit finding${finds.length > 1 ? 's' : ''}</h2>
            <p class="sub">From the city’s annual audits.</p>
            ${finds.map(x => `<div class="pk-find"><b>${esc(x.finding_id)}: ${esc(x.title)}.</b> Reported in ${listAnd((x.years || [x.fiscal_year]).map(y => 'FY' + y))}.${x.mgmt_response ? ' ' + esc(x.mgmt_response.replace(/\.*$/, '.')) : ''}</div>`).join('')}
            ${finds.some(x => x.topic === 'reconciliation') ? '<p class="pk-small">This report marks a reconciliation finding as improving once three straight months of reconciliations are on file, on time and in balance.</p>' : ''}
            </section>` : ''}
        </div>` : ''}
        <p class="foot">Prepared with ${esc(SITE)}${OPERATOR ? `, powered by ${esc(OPERATOR)}` : ''}. Figures come from the city’s own exports, each tied to its printed total before use.</p>`;
    } catch (e) { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  }
  $('#print').addEventListener('click', () => window.print());

  // ---------- theme: same three-way setting as the rest of BayCounty.me (localStorage "theme") ----------
  const NAMES = {system: 'System', light: 'Light', dark: 'Dark'}, NEXT = {system: 'light', light: 'dark', dark: 'system'};
  const root = document.documentElement, mode = () => root.getAttribute('data-theme') || 'system';
  const showTheme = m => $$('.theme-btn').forEach(b => { b.dataset.mode = m; b.querySelector('.theme-lbl').textContent = NAMES[m];
    b.setAttribute('aria-label', 'Theme: ' + (m === 'system' ? 'match system' : NAMES[m].toLowerCase()) + '. Click to change.'); });
  $$('.theme-btn').forEach(b => b.addEventListener('click', () => {
    const m = NEXT[mode()];
    if (m === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', m);
    try { if (m === 'system') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    showTheme(m);
  }));
  showTheme(mode());

  start();
})();
