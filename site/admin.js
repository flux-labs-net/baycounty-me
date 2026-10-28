// BayCounty.me admin page. Talks only to /api/admin.
(() => {
  const $ = s => document.querySelector(s);
  // Show script errors on the page itself, so a broken tab says why instead of staying blank.
  const oops = msg => {
    let box = document.getElementById('cp-oops');
    if (!box) {
      box = document.createElement('div'); box.id = 'cp-oops'; box.className = 'banner bad';
      box.style.cssText = 'position:fixed;z-index:100;left:16px;right:16px;bottom:16px;max-width:720px;margin:0 auto;box-shadow:0 8px 30px rgba(0,0,0,.18)';
      document.body.append(box);
    }
    box.innerHTML = '<div><b>Something broke on this page.</b><div class="small muted"></div></div>';
    box.querySelector('.small').textContent = String(msg).slice(0, 400);
  };
  addEventListener('error', e => oops((e.message || 'Error') + (e.filename ? ' (' + e.filename.split('/').pop() + ':' + e.lineno + ')' : '')));
  addEventListener('unhandledrejection', e => { const m = e.reason && e.reason.message || String(e.reason); if (m !== 'Signed out') oops(m); });
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const fmt = n => n == null ? '—' : Number(n).toLocaleString('en-US');
  const lim = n => n == null ? 'No limit' : fmt(n);
  const when = t => {
    if (!t) return '<span class="muted">Never</span>';
    const d = new Date(t), s = (Date.now() - d) / 1000;
    const rel = s < 60 ? 'just now' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' hr ago' : Math.round(s / 86400) === 1 ? '1 day ago' : Math.round(s / 86400) + ' days ago';
    return `<span title="${esc(d.toLocaleString())}">${rel}</span>`;
  };
  const stamp = t => new Date(t).toLocaleString('en-US', {month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit'});

  async function api(action, {method = 'GET', body, params} = {}) {
    const qs = new URLSearchParams({action, ...(params || {})});
    const r = await fetch('/api/admin?' + qs, {method, credentials: 'same-origin',
      headers: method === 'POST' ? {'Content-Type': 'application/json', 'X-BCM-Admin': '1'} : {}, body: body ? JSON.stringify(body) : undefined});
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && action !== 'login') { showSignin(); throw new Error('Signed out'); }
    if (!r.ok) throw new Error(j.error || 'Request failed');
    return j;
  }

  // ---------- sign in ----------
  function showSignin() { $('#app').hidden = true; $('#signin').hidden = false; }
  $('#signin-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button'); btn.disabled = true;
    try { const j = await api('login', {method: 'POST', body: {email: e.target.email.value}}); $('#signin-msg').textContent = j.message + ' Check your inbox.'; }
    catch (err) { $('#signin-msg').textContent = err.message; }
    btn.disabled = false;
  });
  $('#signout').addEventListener('click', async () => { await api('logout', {method: 'POST'}).catch(() => {}); location.href = '/admin'; });

  // ---------- menu + panes ----------
  // Old #hashes from before the menu was regrouped still land somewhere sensible.
  const ALIAS = {logs: 'analytics'};
  const loaders = {todo: loadTodo, keys: loadKeys, analytics: () => { loadStats(); loadLogs(true); }, settings: loadSettings, ingestion: loadIngestion,
    accounting: () => loadLedger(), agendas: loadAgendas, sent: loadSent, emails: loadEmails, compose: () => loadCompose(), correspondence: loadCorr,
    records: loadRR, owners: loadOwners, limits: loadLimits, ties: loadTies, names: loadNames, realtors: loadRealtors, boards: loadBoards, minutes: loadMinutes, progress: loadProgress};
  const nav = $('#an-nav'), menuBtn = $('#an-open');
  function menu(open) {
    nav.classList.toggle('open', open); document.body.classList.toggle('an-lock', open);
    menuBtn.setAttribute('aria-expanded', String(open));
    if (!open) { $('#an-find').value = ''; findFilter(''); }
  }
  menuBtn.addEventListener('click', () => menu(true));
  $('#an-close').addEventListener('click', () => menu(false));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && nav.classList.contains('open')) menu(false); });
  function tab(name) {
    name = ALIAS[name] || name;
    if (!loaders[name]) name = 'todo';
    nav.querySelectorAll('[data-tab]').forEach(a => a.dataset.tab === name ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    document.querySelectorAll('.pane').forEach(p => { p.hidden = p.id !== 'tab-' + name; });
    const link = nav.querySelector(`[data-tab="${name}"]`), title = link ? link.querySelector('span').textContent : 'To do';
    $('#cp-h').textContent = title; $('#an-cur').textContent = title; document.title = title + ' · Admin · BayCounty.me';
    history.replaceState(null, '', '#' + name);
    menu(false); window.scrollTo(0, 0);
    loaders[name]();
    document.dispatchEvent(new Event('cp:tab'));
  }
  nav.addEventListener('click', e => { const a = e.target.closest('a[data-tab]'); if (!a) return; e.preventDefault(); tab(a.dataset.tab); });
  window.addEventListener('hashchange', () => tab(location.hash.slice(1)));
  function findFilter(q) {
    q = q.trim().toLowerCase();
    nav.querySelectorAll('.an-items a').forEach(a => a.classList.toggle('an-hide', !!q && !a.textContent.toLowerCase().includes(q)));
    nav.querySelectorAll('.an-g').forEach(g => { g.hidden = !!q && !g.querySelector('.an-items a:not(.an-hide)'); });
  }
  $('#an-find').addEventListener('input', e => findFilter(e.target.value));
  $('#an-find').addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const a = nav.querySelector('.an-items a:not(.an-hide)'); if (a) { e.preventDefault(); tab(a.dataset.tab); }
  });

  // ---------- to do (api/_summary.js) ----------
  // One card per queue with waiting work; the menu gets a dot on each of those items.
  const TODO = [
    ['owners', 'teal', 'Review', 'Business owner groups', 'Businesses that share a person and gave to the same candidate.', 'Open queue'],
    ['limits', 'teal', 'Review', 'Gifts over the limit', 'Cases to confirm, reject or resolve with a source.', 'Open queue'],
    ['boards', 'teal', 'Review', 'Nonprofit board matches', 'Officials, leaders and candidates matched to board seats.', 'Open queue'],
    ['ties', 'teal', 'Review', 'Business ties', 'Officials matched by name to Sunbiz officers.', 'Open queue'],
    ['minutes', 'teal', 'Review', 'Votes from minutes', 'Motions read from minutes that failed a check, plus spot checks.', 'Open queue'],
    ['accounting', 'teal', 'Review', 'Accounting files', 'Check-register rows waiting for approve or reject.', 'Open queue'],
    ['replies', 'blue', 'Outreach', 'Replies to handle', 'Conversations with a reply, plus emails that matched no conversation.', 'Read replies', 'correspondence'],
    ['records', 'blue', 'Outreach', 'Unsent records requests', 'Drafts waiting for you to press Send.', 'Open drafts'],
    ['syncs', 'amber', 'Problems', 'Datasets failing now', 'Datasets whose latest load failed.', 'See data health', 'ingestion'],
    ['agendas', 'amber', 'Problems', 'Agenda errors', 'Unresolved errors from the last 14 days.', 'See agendas'],
  ];
  async function loadTodo() {
    let r;
    try { r = await api('summary'); }
    catch (e) { $('#td-banner').innerHTML = `<div class="banner bad"><div><b>Couldn’t load the to do list.</b><div class="small muted">${esc(e.message)}</div></div></div>`; $('#td-list').innerHTML = ''; return; }
    $('#td-banner').innerHTML = '';
    const c = r.counts || {};
    const busy = TODO.filter(t => c[t[0]] > 0), quiet = TODO.filter(t => c[t[0]] === 0);
    $('#td-list').innerHTML = busy.map(([key, tone, kind, title, desc, go, to]) => `<a href="#${to || key}" data-go="${to || key}">
      <span class="k ${tone}">${kind}<b>${fmt(c[key])}</b></span><span class="t">${title}</span><span class="d">${desc}</span><span class="go">${go} →</span></a>`).join('')
      || '<div class="banner good"><div><b>Nothing waiting.</b> <span class="small muted">Every queue is clear.</span></div></div>';
    const unknown = TODO.filter(t => c[t[0]] == null).map(t => t[3]);
    $('#td-quiet').textContent = (quiet.length ? 'Clear right now: ' + quiet.map(t => t[3].toLowerCase()).join(', ') + '.' : '')
      + (unknown.length ? ' Couldn’t count: ' + unknown.join(', ').toLowerCase() + '.' : '');
    markMenu(c);
  }
  function markMenu(c) {
    nav.querySelectorAll('[data-count]').forEach(a => a.querySelector('.an-n').classList.toggle('on', c[a.dataset.count] > 0));
    const total = TODO.reduce((n, t) => n + (c[t[0]] > 0 ? c[t[0]] : 0), 0);
    $('#an-total').hidden = !total; $('#an-total').textContent = total > 999 ? '999+' : fmt(total);
  }
  $('#td-list').addEventListener('click', e => { const a = e.target.closest('[data-go]'); if (!a) return; e.preventDefault(); tab(a.dataset.go); });

  // ---------- keys ----------
  let KEYS = [];
  const statusOf = k => k.status === 'active' && k.expires_at && new Date(k.expires_at) < new Date() ? 'expired' : k.status;
  const STATUS = {active: 'Active', disabled: 'Paused', revoked: 'Revoked', expired: 'Expired'};
  function scopeOptions(sel) {
    const cur = sel.value;
    sel.innerHTML = '<option value="all">All traffic</option><option value="anon">Requests without a key</option>' +
      KEYS.map(k => `<option value="${esc(k.id)}">${esc(k.name)} (${esc(k.prefix)}…)</option>`).join('');
    if ([...sel.options].some(o => o.value === cur)) sel.value = cur;
  }
  async function loadKeys() {
    const j = await api('keys');
    KEYS = j.keys;
    scopeOptions($('#an-scope')); scopeOptions($('#lg-scope'));
    const tb = $('#keys-table tbody');
    const anon = `<tr><td><b>Requests without a key</b><div class="muted small">Keyless access</div></td><td class="muted">Anyone</td><td class="muted">—</td><td class="num muted" colspan="2">See Throttles &amp; settings</td><td></td><td class="num">${fmt(j.anonymous.req_24h)}</td><td class="num">${fmt(j.anonymous.req_30d)}</td><td></td></tr>`;
    tb.innerHTML = (KEYS.length ? KEYS.map(k => `<tr class="click" data-id="${esc(k.id)}" tabindex="0">
      <td><b>${esc(k.name)}</b>${k.organization ? `<div class="muted small">${esc(k.organization)}</div>` : ''}</td>
      <td>${esc(k.owner_name || '')}${k.owner_email ? `<div class="muted small">${esc(k.owner_email)}</div>` : ''}${!k.owner_name && !k.owner_email ? '<span class="muted">—</span>' : ''}</td>
      <td class="mono">${esc(k.prefix)}…</td><td class="num">${lim(k.per_minute)}</td><td class="num">${lim(k.per_day)}</td>
      <td><span class="pill ${statusOf(k)}">${STATUS[statusOf(k)]}</span></td>
      <td class="num">${fmt(k.req_24h)}</td><td class="num">${fmt(k.req_30d)}</td><td>${when(k.last_used_at)}</td></tr>`).join('')
      : '<tr><td colspan="9" class="empty">No keys yet. Create one to give someone higher limits or to track their use.</td></tr>') + anon;
    tb.querySelectorAll('tr.click').forEach(tr => {
      const open = () => openKey(KEYS.find(k => k.id === tr.dataset.id));
      tr.addEventListener('click', open); tr.addEventListener('keydown', e => { if (e.key === 'Enter') open(); });
    });
  }

  const dlg = $('#key-dialog'), form = $('#key-form');
  let editing = null;
  function openKey(k) {
    editing = k || null;
    form.reset(); $('#kd-err').textContent = ''; $('#kd-secret').hidden = true; $('#kd-fields').hidden = false; $('#kd-save').hidden = false;
    $('#kd-title').textContent = k ? k.name : 'New API key';
    $('#kd-save').textContent = k ? 'Save changes' : 'Create key';
    ['#kd-stats', '#kd-logs', '#kd-rotate', '#kd-status-wrap'].forEach(s => { $(s).hidden = !k; });
    if (k) {
      for (const f of ['name', 'owner_name', 'owner_email', 'organization', 'notes', 'per_minute', 'per_day', 'status']) form[f].value = k[f] ?? '';
      form.expires_at.value = k.expires_at ? k.expires_at.slice(0, 10) : '';
      $('#kd-rotate').hidden = k.status === 'revoked';
    } else {
      api('settings').then(j => { if (!editing) { form.per_minute.value = j.settings.default_per_minute ?? ''; form.per_day.value = j.settings.default_per_day ?? ''; } }).catch(() => {});
    }
    dlg.showModal();
  }
  function showSecret(key, title) {
    $('#kd-title').textContent = title;
    $('#kd-secret-val').textContent = key; $('#kd-secret').hidden = false; $('#kd-fields').hidden = true; $('#kd-save').hidden = true;
    ['#kd-stats', '#kd-logs', '#kd-rotate'].forEach(s => { $(s).hidden = true; });
  }
  $('#new-key').addEventListener('click', () => openKey(null));
  $('#kd-copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText($('#kd-secret-val').textContent); $('#kd-copy').textContent = 'Copied'; setTimeout(() => { $('#kd-copy').textContent = 'Copy'; }, 1500); } catch (e) {}
  });
  $('#kd-save').addEventListener('click', async () => {
    if (!form.name.value.trim()) { $('#kd-err').textContent = 'Give the key a name.'; return; }
    const body = {};
    for (const f of ['name', 'owner_name', 'owner_email', 'organization', 'notes', 'per_minute', 'per_day', 'expires_at']) body[f] = form[f].value;
    if (body.expires_at) body.expires_at += 'T23:59:59-05:00';
    if (editing) {
      body.status = form.status.value;
      if (body.status === 'revoked' && editing.status !== 'revoked' && !confirm('Revoke this key? Apps using it stop working, and it can’t be turned back on.')) return;
    }
    try {
      if (editing) { await api('update', {method: 'POST', body: {id: editing.id, ...body}}); dlg.close(); }
      else { const j = await api('create', {method: 'POST', body}); showSecret(j.key, 'Key created: ' + j.record.name); }
      loadKeys();
    } catch (e) { $('#kd-err').textContent = e.message; }
  });
  $('#kd-rotate').addEventListener('click', async () => {
    if (!editing || !confirm('Replace this key? The current key stops working right away; its limits, history and settings stay.')) return;
    try { const j = await api('rotate', {method: 'POST', body: {id: editing.id}}); showSecret(j.key, 'New key for ' + j.record.name); loadKeys(); }
    catch (e) { $('#kd-err').textContent = e.message; }
  });
  $('#kd-stats').addEventListener('click', () => { const id = editing.id; dlg.close(); tab('analytics'); $('#an-scope').value = id; loadStats(); });
  $('#kd-logs').addEventListener('click', () => { const id = editing.id; dlg.close(); tab('logs'); $('#lg-scope').value = id; loadLogs(true); $('#logs').scrollIntoView(); });

  // ---------- analytics ----------
  $('#an-scope').addEventListener('change', loadStats);
  $('#an-days').addEventListener('change', loadStats);
  async function loadStats() {
    if (!KEYS.length) await loadKeys().catch(() => {});
    const j = await api('stats', {params: {key: $('#an-scope').value || 'all', days: $('#an-days').value}});
    const t = j.totals;
    const tiles = [['Requests', fmt(t.requests)], ['Blocked by limits', fmt(t.throttled)], ['Errors', fmt(t.errors)],
      ['Average response', t.avg_ms == null ? '—' : fmt(t.avg_ms) + ' ms'], ['Slowest 5% take longer than', t.p95_ms == null ? '—' : fmt(t.p95_ms) + ' ms'],
      ['Connections', fmt(t.connections)], ['Rows returned', fmt(t.rows_returned)]];
    $('#an-tiles').innerHTML = tiles.map(([l, v]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    chart(j.daily);
    const list = (title, rows, map = x => x) => {
      const max = Math.max(1, ...rows.map(r => r.n));
      return `<div class="card list"><h3>${title}</h3>${rows.length ? rows.map(r => `<div class="li"><span class="lbl" title="${esc(map(r.label))}">${esc(map(r.label))}</span><span class="n">${fmt(r.n)}</span><span class="track"><i style="width:${(r.n / max * 100).toFixed(1)}%"></i></span></div>`).join('') : '<p class="muted small">No requests in this range.</p>'}</div>`;
    };
    const SC = {200: '200 OK', 400: '400 Bad request', 401: '401 Key missing or invalid', 403: '403 Key paused, revoked or expired', 404: '404 Not found', 429: '429 Over a limit', 500: '500 Server error', 502: '502 Upstream error'};
    $('#an-lists').innerHTML = list('Top endpoints', j.endpoints) + list('Top datasets', j.datasets.filter(d => d.label !== '(none)')) + list('Responses', j.statuses, l => SC[l] || l) + list('Top IP addresses', j.ips || []);
  }
  function chart(daily) {
    const el = $('#an-chart'), W = 1000, H = 220, P = {l: 44, r: 8, t: 10, b: 26};
    const max = Math.max(1, ...daily.map(d => d.requests));
    const nice = (() => { const p = Math.pow(10, Math.floor(Math.log10(max))); return Math.ceil(max / p) * p; })();
    const n = daily.length, bw = (W - P.l - P.r) / n, gap = Math.min(2, bw * 0.2);
    const y = v => P.t + (H - P.t - P.b) * (1 - v / nice);
    const ticks = [0, nice / 2, nice];
    const every = Math.ceil(n / 8);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Requests per day">`;
    s += ticks.map(v => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-width="1"/><text x="${P.l - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)">${fmt(v)}</text>`).join('');
    daily.forEach((d, i) => {
      const x = P.l + i * bw + gap / 2, w = Math.max(1, bw - gap), top = y(d.requests), h = H - P.b - top;
      const r = Math.min(4, w / 2, h);
      if (d.requests > 0) s += `<path d="M${x},${H - P.b} V${top + r} q0,-${r} ${r},-${r} H${x + w - r} q${r},0 ${r},${r} V${H - P.b} Z" fill="var(--bar)"/>`;
      s += `<rect class="hit" data-i="${i}" x="${P.l + i * bw}" y="${P.t}" width="${bw}" height="${H - P.t - P.b}" fill="transparent"/>`;
      if (i % every === 0 || (i === n - 1 && (n - 1) % every >= every / 2)) s += `<text x="${x + w / 2}" y="${H - 8}" text-anchor="middle" font-size="11" fill="var(--muted)">${new Date(d.day + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric'})}</text>`;
    });
    s += `</svg><div class="tip" role="status"></div>`;
    el.innerHTML = s;
    const tip = el.querySelector('.tip');
    el.querySelectorAll('.hit').forEach(r => {
      r.addEventListener('mouseenter', () => {
        const d = daily[r.dataset.i];
        tip.innerHTML = `<b>${new Date(d.day + 'T12:00:00').toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric'})}</b><br>${fmt(d.requests)} requests${d.errors ? ` · ${fmt(d.errors)} errors or blocked` : ''}`;
        tip.style.display = 'block';
        const bb = r.getBoundingClientRect(), cb = el.getBoundingClientRect();
        tip.style.left = Math.min(cb.width - tip.offsetWidth, Math.max(0, bb.left - cb.left + bb.width / 2 - tip.offsetWidth / 2)) + 'px';
        tip.style.top = '0px';
      });
      r.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
    });
  }

  // ---------- logs ----------
  let before = null;
  $('#lg-scope').addEventListener('change', () => loadLogs(true));
  $('#lg-errors').addEventListener('change', () => loadLogs(true));
  $('#lg-ip').addEventListener('keydown', e => { if (e.key === 'Enter') loadLogs(true); });
  $('#lg-ip').addEventListener('change', () => loadLogs(true));
  $('#lg-refresh').addEventListener('click', () => loadLogs(true));
  $('#lg-more').addEventListener('click', () => loadLogs(false));
  async function loadLogs(reset) {
    if (!KEYS.length) await loadKeys().catch(() => {});
    if (reset) before = null;
    const params = {key: $('#lg-scope').value || 'all', limit: '100'};
    if (before) params.before = before;
    if ($('#lg-errors').checked) params.status = 'errors';
    if ($('#lg-ip').value.trim()) params.ip = $('#lg-ip').value.trim();
    const j = await api('logs', {params});
    const tb = $('#logs-table tbody');
    const rows = j.logs.map(l => `<tr><td class="small" style="white-space:nowrap">${stamp(l.at)}</td>
      <td class="small">${l.key_name ? esc(l.key_name) + `<div class="muted mono">${esc(l.prefix)}…</div>` : '<span class="muted">No key</span>'}</td>
      <td class="small">${l.surface === 'mcp' ? 'AI (MCP)' : 'API'}</td>
      <td class="small"><span class="mono">${esc(l.endpoint || '')}</span>${l.query ? `<div class="muted mono" style="word-break:break-all">${esc(l.query)}</div>` : ''}</td>
      <td class="small mono">${l.ip ? `<button class="linkish" data-ip="${esc(l.ip)}" title="Show only this address">${esc(l.ip)}</button> <button class="linkish danger small" data-block="${esc(l.ip)}">Block</button>` : '<span class="muted">\u2014</span>'}</td>
      <td class="num st e${l.status === 429 ? 429 : String(l.status || '')[0]}">${esc(l.status ?? '')}</td><td class="num">${fmt(l.rows_returned)}</td><td class="num">${fmt(l.ms)}</td></tr>`).join('');
    if (reset) tb.innerHTML = rows || '<tr><td colspan="8" class="empty">No requests yet.</td></tr>'; else tb.insertAdjacentHTML('beforeend', rows);
    before = j.next_before; $('#lg-more').hidden = !before;
  }

  $('#logs-table').addEventListener('click', async e => {
    const ipBtn = e.target.closest('[data-ip]'), blk = e.target.closest('[data-block]');
    if (ipBtn) { $('#lg-ip').value = ipBtn.dataset.ip; loadLogs(true); }
    if (blk) {
      const reason = prompt(`Block ${blk.dataset.block}? Its requests will get a 403 until you remove the block in Throttles & settings.\n\nReason (optional):`);
      if (reason === null) return;
      try { await api('blocks', {method: 'POST', body: {network: blk.dataset.block, reason}}); blk.replaceWith(Object.assign(document.createElement('span'), {className: 'small muted', textContent: 'Blocked'})); }
      catch (err) { alert(err.message); }
    }
  });

  // ---------- blocks ----------
  async function loadBlocks() {
    const j = await api('blocks');
    $('#blocks-table tbody').innerHTML = j.blocks.map(b => `<tr><td class="mono">${esc(b.network.replace(/\/(32|128)$/, ''))}</td><td class="small">${esc(b.reason || '')}</td>
      <td class="small">${b.expires_at ? new Date(b.expires_at).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : 'Until removed'}</td>
      <td class="num">${fmt(b.blocked_30d)}</td><td class="small">${stamp(b.created_at)}<div class="muted">${esc(b.created_by || '')}</div></td>
      <td><button class="btn" data-unblock="${b.id}" type="button">Remove</button></td></tr>`).join('') || '<tr><td colspan="6" class="empty">No addresses are blocked.</td></tr>';
  }
  $('#blocks-table').addEventListener('click', async e => {
    const b = e.target.closest('[data-unblock]'); if (!b) return;
    try { await api('unblock', {method: 'POST', body: {id: Number(b.dataset.unblock)}}); loadBlocks(); } catch (err) { $('#block-msg').textContent = err.message; }
  });
  $('#block-form').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target; $('#block-msg').textContent = '';
    try {
      await api('blocks', {method: 'POST', body: {network: f.network.value, reason: f.reason.value, expires_at: f.expires_at.value ? f.expires_at.value + 'T23:59:59-05:00' : ''}});
      f.reset(); loadBlocks();
    } catch (err) { $('#block-msg').textContent = err.message; }
  });

  // ---------- settings ----------
  // Long bulk-review details (up to 500 ids) are cut short; the full list is in the tooltip.
  const auditDetail = d => { const t = JSON.stringify(d); return t.length > 400 ? `<span title="${esc(t)}">${esc(t.slice(0, 400))}…</span>` : esc(t); };
  async function loadSettings() {
    loadBlocks().catch(() => {});
    const [s, a] = await Promise.all([api('settings'), api('audit')]);
    const f = $('#settings-form');
    for (const k of ['anon_per_minute', 'anon_per_day', 'default_per_minute', 'default_per_day']) f[k].value = s.settings[k] ?? '';
    f.require_key.checked = !!s.settings.require_key;
    const name = id => (KEYS.find(k => k.id === id) || {}).name;
    const WHAT = {email_test: 'Sent a test email', create_key: 'Created a key', update_key: 'Changed a key', rotate_key: 'Replaced a key', update_settings: 'Changed settings', block_ip: 'Blocked an address', unblock_ip: 'Removed a block', login: 'Signed in', login_requested: 'Asked for a sign-in link',
      ledger_normalize: 'Normalized accounting files', ledger_approve: 'Approved ledger rows', ledger_reject: 'Rejected ledger rows', ledger_source: 'Changed an accounting source', ledger_finance: 'Sent a file to /finance',
      registry_review: 'Reviewed shared-owner groups', registry_limit_review: 'Reviewed over-limit cases', boards_review: 'Reviewed board matches', careers_review: 'Reviewed business ties', names_review: 'Reviewed name matches', minutes_review: 'Reviewed votes from minutes'};
    $('#audit-table tbody').innerHTML = a.audit.map(x => `<tr><td class="small" style="white-space:nowrap">${stamp(x.at)}</td><td class="small">${esc(x.admin)}</td><td class="small">${esc(WHAT[x.action] || x.action)}${x.key_id && name(x.key_id) ? ': ' + esc(name(x.key_id)) : ''}</td>
      <td class="small muted mono" style="word-break:break-all">${x.detail && x.action !== 'login' ? auditDetail(x.detail) : ''}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Nothing yet.</td></tr>';
  }
  $('#settings-form').addEventListener('submit', async e => {
    e.preventDefault();
    const f = e.target, body = {require_key: f.require_key.checked};
    for (const k of ['anon_per_minute', 'anon_per_day', 'default_per_minute', 'default_per_day']) body[k] = f[k].value;
    if (body.require_key && !confirm('Require a key for every request? Anyone using the API or MCP server without a key will be turned away.')) return;
    try { await api('settings', {method: 'POST', body}); $('#settings-msg').textContent = 'Saved. Takes effect on the next request.'; loadSettings(); }
    catch (err) { $('#settings-msg').textContent = err.message; }
  });

  // ---------- ingestion ----------
  // Schedules are cron times in UTC (workflows and vercel.json); shown in Central time for today's date.
  const SCHED = [
    ['Meetings + campaign finance refresh, then database sync', 'daily', 11, 17],
    ['FEMA ledger + sales tax map refresh, then database sync', 'Tuesdays', 11, 41],
    ['Daily ingestion check + rule alerts', 'daily', 13, 40],
    ['Weekly digest drafts', 'Mondays', 13, 0],
  ];
  const central = (h, m) => { const d = new Date(); d.setUTCHours(h, m, 0, 0); return d.toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago'}); };
  const RUN = {ok: 'OK', failed: 'Failed', running: 'Running'};
  async function loadIngestion() {
    $('#in-sched').innerHTML = SCHED.map(([what, days, h, m]) => `<span>${esc(what)}</span><span>${esc(days)}, ${central(h, m)}</span>`).join('');
    let r;
    try { r = await api('ingestion'); }
    catch (e) { $('#in-banner').innerHTML = `<div class="banner bad"><div><b>Couldn’t load ingestion status.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    $('#in-banner').innerHTML = r.problems.length
      ? `<div class="banner bad"><div><b>${r.problems.length} problem${r.problems.length === 1 ? '' : 's'}</b><ul class="small">${r.problems.map(p => `<li>${esc(p.text)}</li>`).join('')}</ul></div></div>`
      : `<div class="banner good"><div><b>All good.</b> <span class="small muted">Every dataset’s latest load succeeded. Checked ${when(r.checked_at)}.</span></div></div>`;
    const failed = r.datasets.filter(d => d.status === 'failed').length;
    $('#in-tiles').innerHTML = [[r.last_sync ? when(r.last_sync).replace(/<[^>]+>/g, '') : 'Never', 'Last successful sync'], [fmt(r.datasets.length), 'Datasets'], [fmt(failed), 'Failing now'],
      [fmt(r.alerts.drafts), 'Alert emails waiting for review'], [fmt(r.alerts.events_pending), 'New records not yet matched']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    $('#in-table tbody').innerHTML = r.datasets.map(d => `<tr><td class="mono" style="white-space:nowrap">${esc(d.dataset)}${d.origin && d.origin !== 'site_build' ? `<div class="muted small">${esc(d.origin)}</div>` : ''}</td>
      <td><span class="pill ${esc(d.status)}">${RUN[d.status] || esc(d.status)}</span></td><td>${when(d.finished_at || d.started_at)}</td><td>${when(d.last_ok)}</td>
      <td class="num">${fmt(d.rows_in)}</td><td class="num">${fmt(d.rows_added)}</td><td class="num">${fmt(d.rows_deleted)}</td>
      <td class="small ${d.status === 'failed' ? '' : 'muted'}">${esc(d.notes || '')}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">No loads in the last 60 days.</td></tr>';
    $('#in-fail tbody').innerHTML = r.failures.map(f => `<tr><td class="small" style="white-space:nowrap">${stamp(f.started_at)}</td><td class="mono">${esc(f.dataset)}</td><td class="small">${esc(f.notes || '')}</td>
      <td class="mono small">${f.git_sha ? `<a href="https://github.com/jeremymcs/baycounty-me/commit/${esc(f.git_sha)}" target="_blank" rel="noopener">${esc(String(f.git_sha).slice(0, 7))}</a>` : ''}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">No failures.</td></tr>';
  }
  $('#in-refresh').addEventListener('click', loadIngestion);

  // ---------- accounting-system files (ingest schema, api/_ledger.js) ----------
  const ERP = {new_world: 'Tyler New World', bsa: 'BS&A', springbrook: 'Springbrook', other: 'Other'};
  const FILE = {received: 'New', normalized: 'Normalized', failed: 'Failed', duplicate: 'Duplicate', finance_only: '/finance only'};
  const FSHAPE = {budget: 'Budget', disbursements: 'Check register', bank_transactions: 'Bank statement', bank_recs: 'Bank rec'};
  const FUP = {preview: 'waiting for review', committed: 'added', held: 'held (doesn’t tie)', replaced: 'withdrawn', failed: 'failed'};
  const finCell = f => {
    if (!f.finance_workspace_id) return '<span class="muted small">Not linked</span>';
    if (f.finance_status === 'imported') return `<span class="small">${esc(FSHAPE[f.finance_shape] || 'Unrecognized')}, ${esc(FUP[f.finance_upload_status] || f.finance_upload_status || 'sent')}</span>`;
    if (f.finance_status === 'importing') return '<span class="small muted">Sending…</span>';
    if (f.finance_status === 'failed') return `<span class="small" style="color:var(--bad)">${esc(f.finance_error || 'Failed')}</span>`;
    return f.has_file ? '<span class="small muted">Not sent yet</span>' : '<span class="muted small">—</span>';
  };
  const REV = {pending: 'Pending', approved: 'Approved', rejected: 'Rejected'};
  const usd = n => n == null ? '—' : Number(n).toLocaleString('en-US', {style: 'currency', currency: 'USD'});
  const LG = {raw: '', picked: new Set(), rows: [], sources: []};
  function lgMsg(html, good) { $('#ac-banner').innerHTML = html ? `<div class="banner ${good ? 'good' : 'bad'}"><div>${html}</div></div>` : ''; }
  async function loadLedger(keepMsg) {
    let r;
    try { r = await api('ledger', {params: {status: $('#ac-status').value, source: $('#ac-source').value, raw: LG.raw}}); }
    catch (e) { lgMsg(`<b>Couldn’t load accounting files.</b><div class="small muted">${esc(e.message)}</div>`); return; }
    if (!keepMsg) lgMsg('');
    LG.sources = r.sources; LG.rows = r.rows; LG.picked.clear();
    const t = r.totals;
    $('#ac-tiles').innerHTML = [[fmt(t.waiting), 'Files waiting to normalize'], [fmt(t.pending), 'Rows waiting for review'], [usd(t.pending_amount), 'Pending amount'],
      [fmt(t.approved), 'Rows approved'], [fmt(t.failed_14d), 'Failed files, 14 days']].map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    const sel = $('#ac-source'), cur = sel.value;
    sel.innerHTML = '<option value="">All governments</option>' + r.sources.map(s => `<option value="${esc(s.id)}">${esc(s.entity_name)}</option>`).join('');
    sel.value = cur;
    $('#ac-sources tbody').innerHTML = r.sources.map(s => `<tr data-src="${esc(s.id)}"><td>${esc(s.entity_name)}${s.active ? '' : ' <span class="pill revoked">Off</span>'}${s.has_map ? '' : '<div class="small" style="color:var(--warn)">No column map yet</div>'}</td>
      <td class="small">${esc(ERP[s.erp_system] || s.erp_system)}</td><td class="mono small">${esc(s.inbound_address || '')}</td>
      <td class="small">${s.finance_workspace ? esc(s.finance_workspace) : '<span class="muted">Not linked</span>'}</td>
      <td><div class="ac-snd"><input value="${esc((s.allowed_senders || []).join(', '))}" placeholder="name@city.gov, @city.gov" aria-label="Allowed senders for ${esc(s.entity_name)}"><button class="btn" type="button" data-save-snd>Save</button></div></td>
      <td class="num">${fmt(s.files)}</td><td class="small">${when(s.last_file)}</td><td class="num">${fmt(s.pending)}</td>
      <td><label class="sw"><input type="checkbox" data-auto ${s.auto_normalize ? 'checked' : ''}> ${s.auto_normalize ? 'On' : 'Off'}</label></td></tr>`).join('') || '<tr><td colspan="9" class="empty">No sources yet.</td></tr>';
    $('#ac-files tbody').innerHTML = r.files.map(f => `<tr${f.id === LG.raw ? ' class="sel-row"' : ''}><td class="small" style="white-space:nowrap">${when(f.received_at)}</td><td class="small">${esc(f.entity_name)}</td>
      <td class="small">${esc(f.file_name || '(no file)')}${f.error_message ? `<div class="small" style="color:var(--bad)">${esc(f.error_message)}</div>` : ''}</td><td class="small mono">${esc(f.sender || '')}</td>
      <td><span class="pill ${esc(f.status)}">${FILE[f.status] || esc(f.status)}</span></td><td class="num">${fmt(f.row_count)}</td>
      <td class="small">${f.status === 'normalized' ? `${fmt(f.pending)} pending · ${fmt(f.approved)} approved · ${fmt(f.rejected)} rejected` : ''}</td>
      <td>${finCell(f)}</td>
      <td style="white-space:nowrap">${f.finance_workspace_id && f.has_file && !f.finance_upload_id && f.finance_status !== 'importing' ? `<button class="btn" type="button" data-fin="${esc(f.id)}">Send to /finance</button>` : ''}
        ${f.status === 'received' ? `<button class="btn" type="button" data-norm="${esc(f.id)}">Normalize</button>` : f.status === 'failed' && f.has_file ? `<button class="btn" type="button" data-norm="${esc(f.id)}">Retry</button>` : ''}
        ${f.status === 'normalized' ? `<button class="btn" type="button" data-rows="${esc(f.id)}">${f.id === LG.raw ? 'All files' : 'Rows'}</button>` : ''}
        ${f.pending ? `<button class="btn primary" type="button" data-approve-file="${esc(f.id)}">Approve ${fmt(f.pending)}</button>` : ''}</td></tr>`).join('') || '<tr><td colspan="9" class="empty">No files in the last 120 days.</td></tr>';
    const file = LG.raw && r.files.find(f => f.id === LG.raw);
    $('#ac-qscope').textContent = file ? `· ${file.file_name} (${file.entity_name})` : '';
    $('#ac-queue tbody').innerHTML = r.rows.map(x => `<tr><td>${x.review_status === 'pending' ? `<input type="checkbox" data-pick="${esc(x.id)}" aria-label="Select row">` : ''}</td>
      <td class="small" style="white-space:nowrap">${esc(x.txn_date || '')}</td><td class="small">${esc(x.entity_name)}</td><td class="mono small">${esc(x.fund_code || '')}</td>
      <td class="mono small">${esc(x.account_code || '')}</td><td class="small">${esc(x.vendor_name || '')}</td><td class="small" style="min-width:200px">${esc(x.description || '')}</td>
      <td class="num">${usd(x.amount)}</td><td><span class="pill ${esc(x.review_status)}">${REV[x.review_status] || esc(x.review_status)}</span>${x.review_note ? `<div class="small muted">${esc(x.review_note)}</div>` : ''}${x.reviewed_by_email ? `<div class="small muted">${esc(x.reviewed_by_email)}</div>` : ''}</td></tr>`).join('')
      || `<tr><td colspan="9" class="empty">${$('#ac-status').value === 'pending' ? 'Nothing waiting for review.' : 'No rows.'}</td></tr>`;
    $('#ac-all').checked = false; lgPicked();
  }
  function lgPicked() {
    const n = LG.picked.size;
    $('#ac-bulk').hidden = n === 0;
    const sum = LG.rows.filter(x => LG.picked.has(x.id)).reduce((a, x) => a + Number(x.amount || 0), 0);
    $('#ac-picked').textContent = `${fmt(n)} selected · ${usd(sum)}`;
  }
  async function lgDo(action, body, done) {
    try { const r = await api(action, {method: 'POST', body}); lgMsg(done(r), true); }
    catch (e) { lgMsg(`<b>That didn’t work.</b> <span class="small">${esc(e.message)}</span>`); }
    await loadLedger(true);
  }
  const normSummary = r => {
    const ok = (r.results || []).filter(x => x.ok), bad = (r.results || []).filter(x => !x.ok);
    if (!r.processed) return '<b>No new files to normalize.</b>';
    return `<b>Normalized ${ok.length} of ${r.processed} file${r.processed === 1 ? '' : 's'}.</b> <span class="small">${ok.map(x => `${fmt(x.inserted)} new rows${x.duplicates ? `, ${fmt(x.duplicates)} already queued` : ''}${x.skipped && x.skipped.length ? `, ${x.skipped.length} skipped` : ''}`).join('; ')}${bad.length ? ` · Failed: ${bad.map(x => esc(x.error)).join('; ')}` : ''}</span>`;
  };
  $('#ac-refresh').addEventListener('click', () => loadLedger());
  $('#ac-norm-all').addEventListener('click', e => { e.target.disabled = true; lgDo('ledger_normalize', {all: true}, normSummary).finally(() => { e.target.disabled = false; }); });
  $('#ac-status').addEventListener('change', () => loadLedger());
  $('#ac-source').addEventListener('change', () => { LG.raw = ''; loadLedger(); });
  $('#ac-files').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.norm) { b.disabled = true; lgDo('ledger_normalize', {raw_id: b.dataset.norm}, normSummary); }
    else if (b.dataset.fin) { b.disabled = true; lgDo('ledger_finance', {raw_id: b.dataset.fin}, r => `<b>Sent to /finance${r.shape ? ' as ' + esc(FSHAPE[r.shape] || r.shape) : ''}.</b> <span class="small">It’s waiting under “Emailed in” on the workspace’s Add a file tab.</span>`); }
    else if (b.dataset.rows) { LG.raw = LG.raw === b.dataset.rows ? '' : b.dataset.rows; $('#ac-status').value = LG.raw ? 'all' : 'pending'; loadLedger(); }
    else if (b.dataset.approveFile) { b.disabled = true; lgDo('ledger_approve', {raw_id: b.dataset.approveFile}, r => `<b>Approved ${fmt(r.changed)} row${r.changed === 1 ? '' : 's'}.</b> <span class="small">They’re now in the public ledger.</span>`); }
  });
  $('#ac-sources').addEventListener('change', e => {
    const box = e.target.closest('[data-auto]'); if (!box) return;
    const id = box.closest('tr').dataset.src;
    lgDo('ledger_source', {id, auto_normalize: box.checked}, r => `<b>Auto-normalize is ${r.auto_normalize ? 'on' : 'off'} for ${esc(r.entity_name)}.</b> <span class="small">${r.auto_normalize ? 'New files from this source are mapped into the review queue as soon as they arrive. Rows still need approval.' : 'New files wait for you to click Normalize.'}</span>`);
  });
  $('#ac-sources').addEventListener('click', e => {
    const b = e.target.closest('[data-save-snd]'); if (!b) return;
    const tr = b.closest('tr');
    lgDo('ledger_source', {id: tr.dataset.src, allowed_senders: tr.querySelector('.ac-snd input').value},
      r => `<b>Saved ${fmt(r.allowed_senders.length)} allowed sender${r.allowed_senders.length === 1 ? '' : 's'} for ${esc(r.entity_name)}.</b>`);
  });
  $('#ac-queue').addEventListener('change', e => {
    if (e.target.id === 'ac-all') {
      document.querySelectorAll('#ac-queue [data-pick]').forEach(c => { c.checked = e.target.checked; c.checked ? LG.picked.add(c.dataset.pick) : LG.picked.delete(c.dataset.pick); });
    } else if (e.target.dataset.pick) { e.target.checked ? LG.picked.add(e.target.dataset.pick) : LG.picked.delete(e.target.dataset.pick); }
    lgPicked();
  });
  $('#ac-approve').addEventListener('click', () => lgDo('ledger_approve', {ids: [...LG.picked], note: $('#ac-note').value},
    r => `<b>Approved ${fmt(r.changed)} row${r.changed === 1 ? '' : 's'}.</b> <span class="small">They’re now in the public ledger.</span>`));
  $('#ac-reject').addEventListener('click', () => {
    if (!$('#ac-note').value.trim()) { lgMsg('<b>Add a note saying why before rejecting.</b>'); $('#ac-note').focus(); return; }
    lgDo('ledger_reject', {ids: [...LG.picked], note: $('#ac-note').value}, r => `<b>Rejected ${fmt(r.changed)} row${r.changed === 1 ? '' : 's'}.</b>`).then(() => { $('#ac-note').value = ''; });
  });

  // ---------- agendas ----------
  const AG_STATUS = {new: 'New', updated: 'Updated', unchanged: 'Unchanged', failed: 'Failed', pending: 'Pending', processed: 'Processed', unmatched: 'Unmatched', ok: 'OK', running: 'Running'};
  const kb = n => n == null ? '' : n < 1048576 ? Math.max(1, Math.round(n / 1024)) + ' KB' : (n / 1048576).toFixed(1) + ' MB';
  const day = d => d ? new Date(String(d).slice(0, 10) + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '';
  const shortUrl = u => { try { const x = new URL(u); return x.hostname.replace(/^www\./, '') + x.pathname.slice(0, 48) + (x.pathname.length > 48 ? '…' : ''); } catch (e) { return String(u).slice(0, 60); } };
  let agBoardsLoaded = false;
  async function loadAgendas() {
    const params = {days: $('#ag-days').value, board: $('#ag-board').value, status: $('#ag-status').value};
    let r;
    try { r = await api('agendas', {params}); }
    catch (e) { $('#ag-banner').innerHTML = `<div class="banner bad"><div><b>Couldn’t load the agenda watcher.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    $('#ag-banner').innerHTML = r.problems.length
      ? `<div class="banner bad"><div><b>${r.problems.length} thing${r.problems.length === 1 ? '' : 's'} to look at</b><ul class="small">${r.problems.map(p => `<li>${esc(p.text)}</li>`).join('')}</ul></div></div>`
      : `<div class="banner good"><div><b>All good.</b> <span class="small muted">Last run ${when(r.last_run && (r.last_run.finished_at || r.last_run.started_at))}, last inbox check ${when(r.last_inbox && (r.last_inbox.finished_at || r.last_inbox.started_at))}.</span></div></div>`;
    if (!r.installed) { $('#ag-tiles').innerHTML = ''; ['#ag-docs', '#ag-notices', '#ag-errors', '#ag-runs'].forEach(t => $(t + ' tbody').innerHTML = ''); return; }
    const c = r.counts;
    $('#ag-tiles').innerHTML = [[r.last_inbox ? when(r.last_inbox.finished_at || r.last_inbox.started_at).replace(/<[^>]+>/g, '') : 'Never', 'Last inbox check'],
      [fmt(c.notices_7d), 'Notice emails, 7 days'], [fmt(c.new_7d), 'New documents, 7 days'], [fmt(c.updated_7d), 'Amended documents, 7 days'],
      [fmt(c.documents), 'Documents tracked'], [fmt(c.open_errors), 'Open errors'],
      ...(c.extract ? [[fmt(c.extract.items_7d), `Items read from ${fmt(c.extract.read_7d)} agenda${c.extract.read_7d === 1 ? '' : 's'}, 7 days`],
        [fmt(c.extract.waiting), 'Agendas waiting to be read'], ['$' + Number(c.extract.cost_7d || 0).toFixed(2), 'Reading cost, 7 days (estimate)']] : [])].map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    if (!agBoardsLoaded && r.boards.length) {
      $('#ag-board').innerHTML = '<option value="">All boards</option>' + r.boards.map(b => `<option value="${esc(b.board)}">${esc(b.board)} (${fmt(b.n)})</option>`).join('');
      $('#ag-board').value = params.board; agBoardsLoaded = true;
    }
    $('#ag-docs tbody').innerHTML = r.documents.map(d => {
      const files = d.versions.map((v, i) => `<button class="btn" type="button" data-ver="${v.id}" style="min-height:28px;padding:0 8px;font-size:.78rem" title="${esc(stamp(v.fetched_at))} · ${esc(v.sha256.slice(0, 12))}">${i === 0 ? 'Latest' : 'v' + (d.versions.length - i)}${v.stored ? '' : ' ↗'}</button>`).join(' ');
      return `<tr><td class="small" style="white-space:nowrap">${when(d.last_changed_at || d.first_seen_at)}</td><td class="mono small">${esc(d.board || d.source_key)}</td>
        <td><b>${esc(d.title || d.kind)}</b><div class="muted small">${esc(d.kind)}${d.bytes ? ' · ' + kb(d.bytes) : ''} · <a href="${esc(/^https?:/.test(d.url) ? d.url : '#')}" target="_blank" rel="noopener">${esc(shortUrl(d.url))}</a></div>${d.error ? `<div class="small" style="color:var(--bad)">${esc(d.error)}</div>` : ''}</td>
        <td class="small" style="white-space:nowrap">${day(d.meeting_date)}</td><td><span class="pill ${esc(d.status)}">${AG_STATUS[d.status] || esc(d.status)}</span>${d.extraction ? (d.extraction.status === 'ok'
          ? `<div><button class="btn" type="button" data-ext="${d.extraction.id}" style="min-height:26px;padding:0 8px;font-size:.76rem;margin-top:4px">${fmt(d.extraction.items)} item${d.extraction.items === 1 ? '' : 's'}</button></div>`
          : `<div class="small muted" title="${esc(d.extraction.error || '')}">${d.extraction.status === 'no_text' ? 'No text (scanned)' : 'Not read: ' + esc(d.extraction.status)}</div>`) : ''}</td>
        <td class="num">${fmt(d.version_count)}</td><td style="white-space:nowrap">${files || '<span class="muted small">None</span>'}</td></tr>`;
    }).join('') || '<tr><td colspan="7" class="empty">No documents in this window.</td></tr>';
    $('#ag-notices tbody').innerHTML = r.notices.map(n => `<tr><td class="small" style="white-space:nowrap">${n.received_at ? stamp(n.received_at) : when(n.pulled_at)}</td>
      <td class="small" title="${esc(n.from_addr)}">${esc(n.from_addr)}</td>
      <td style="min-width:220px"><b>${esc(n.subject || '(no subject)')}</b><details class="ag"><summary class="small">Email text</summary><pre>${esc(n.body_text || '')}</pre></details></td>
      <td class="mono small">${esc((n.sources || []).join(', ') || '—')}</td>
      <td class="small">${(n.links || []).length ? `<details class="ag"><summary>${(n.links || []).length}</summary><div class="ag-links">${n.links.map(u => `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(shortUrl(u))}</a>`).join('')}</div></details>` : '0'}</td>
      <td class="small">${(n.attachments || []).map(a => `${esc(a.filename)} <span class="muted">${kb(a.bytes)}</span>`).join('<br>') || '—'}</td>
      <td><span class="pill ${esc(n.status)}">${AG_STATUS[n.status] || esc(n.status)}</span>${n.error ? `<div class="small" style="color:var(--bad)">${esc(n.error)}</div>` : ''}</td></tr>`).join('') || '<tr><td colspan="7" class="empty">No emails yet. Sign up for Notify Me with the agenda mailbox address.</td></tr>';
    $('#ag-errors tbody').innerHTML = r.errors.map(e => `<tr${e.resolved_at ? ' class="muted"' : ''}><td class="small" style="white-space:nowrap">${stamp(e.at)}</td><td class="mono small">${esc(e.stage)}</td><td class="mono small">${esc(e.source_key || '')}</td>
      <td class="small" style="min-width:240px">${esc(e.message)}${e.url ? `<div><a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(shortUrl(e.url))}</a></div>` : ''}</td>
      <td>${e.resolved_at ? '<span class="small">Resolved</span>' : `<button class="btn" type="button" data-resolve="${e.id}" style="min-height:28px;padding:0 8px;font-size:.78rem">Resolve</button>`}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">No errors.</td></tr>';
    $('#ag-runs tbody').innerHTML = r.runs.slice(0, 20).map(x => `<tr><td class="small" style="white-space:nowrap">${stamp(x.started_at)}</td><td><span class="pill ${esc(x.status)}">${AG_STATUS[x.status] || esc(x.status)}</span></td>
      <td class="num">${fmt(x.rows_in)}</td><td class="small">${esc(x.notes || '')}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">No runs yet.</td></tr>';
  }
  $('#ag-refresh').addEventListener('click', loadAgendas);
  ['#ag-days', '#ag-board', '#ag-status'].forEach(s => $(s).addEventListener('change', loadAgendas));
  $('#ag-docs').addEventListener('click', async e => {
    const b = e.target.closest('[data-ver]'); if (!b) return;
    const w = window.open('', '_blank');
    try { const j = await api('agenda_file', {params: {id: b.dataset.ver}}); if (j.url) w.location = j.url; else { w.close(); alert('This file wasn’t stored and has no public link.'); } }
    catch (err) { w.close(); alert(err.message); }
  });

  const money = n => n == null ? '' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  $('#ag-docs').addEventListener('click', async e => {
    const b = e.target.closest('[data-ext]'); if (!b) return;
    const tr = b.closest('tr'), next = tr.nextElementSibling;
    if (next && next.classList.contains('ag-items')) { next.remove(); return; }
    const row = document.createElement('tr'); row.className = 'ag-items';
    row.innerHTML = '<td colspan="7" class="small muted">Loading…</td>'; tr.after(row);
    try {
      const r = await api('agenda_items', {params: {id: b.dataset.ext}}), x = r.extraction;
      const head = [x.meeting_body, x.meeting_date && day(x.meeting_date), x.meeting_time, x.meeting_location].filter(Boolean).map(esc).join(' · ');
      row.innerHTML = `<td colspan="7" style="background:var(--bg)"><div class="small muted" style="margin-bottom:8px">${head}${x.model ? ` · read by ${esc(x.model)}` : ''}${x.cost_usd != null ? ` · about $${Number(x.cost_usd).toFixed(3)}` : ''}${x.text_truncated ? ' · text was cut short' : ''}</div>
        <table class="at" data-tt="off"><thead><tr><th>#</th><th>Item</th><th>Kind</th><th class="num">Amount</th><th>Parties / places</th></tr></thead><tbody>${r.items.map(i => `<tr>
          <td class="mono small" style="white-space:nowrap">${esc(i.item_number || '')}</td>
          <td><b>${esc(i.title)}</b>${i.summary ? `<div class="small muted">${esc(i.summary)}</div>` : ''}${i.section ? `<div class="small muted">${esc(i.section)}</div>` : ''}</td>
          <td class="small">${esc((i.kind || '').replace(/_/g, ' '))}</td>
          <td class="num small" style="white-space:nowrap" title="${esc((i.amounts || []).map(a => a.text).join(', '))}">${money(i.total_amount)}</td>
          <td class="small">${esc([...(i.parties || []), ...(i.addresses || [])].join('; '))}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">No substantive items.</td></tr>'}</tbody></table></td>`;
    } catch (err) { row.innerHTML = `<td colspan="7" class="small" style="color:var(--bad)">${esc(err.message)}</td>`; }
  });
  $('#ag-errors').addEventListener('click', async e => {
    const b = e.target.closest('[data-resolve]'); if (!b) return;
    try { await api('agenda_resolve', {method: 'POST', body: {id: b.dataset.resolve}}); loadAgendas(); } catch (err) { alert(err.message); }
  });
  $('#ag-resolve-all').addEventListener('click', async () => {
    if (!confirm('Mark every open agenda error resolved?')) return;
    try { await api('agenda_resolve', {method: 'POST', body: {all: true}}); loadAgendas(); } catch (err) { alert(err.message); }
  });
  $('#ag-run').addEventListener('click', async e => {
    const b = e.target; b.disabled = true;
    try { await api('agenda_run', {method: 'POST', body: {mode: 'both'}}); b.textContent = 'Started'; setTimeout(() => { b.textContent = 'Run now'; b.disabled = false; loadAgendas(); }, 60000); }
    catch (err) { alert(err.message); b.disabled = false; }
  });

  // ---------- sent mail ----------
  let SE = null, seTimer = null;
  const seLabel = st => (SE && SE.labels[st]) || st;
  async function loadSent() {
    const params = {days: $('#se-days').value, domain: $('#se-domain').value, status: $('#se-status').value, q: $('#se-q').value};
    try { SE = await api('sent', {params}); }
    catch (e) { $('#se-banner').innerHTML = `<div class="banner bad"><div><b>Couldn’t load sent mail.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const c = SE.counts, pct = n => c.total ? Math.round(100 * n / c.total) + '%' : '—';
    $('#se-banner').innerHTML = c.problems
      ? `<div class="banner bad"><div><b>${fmt(c.problems)} email${c.problems === 1 ? '' : 's'} with a delivery problem</b> <span class="small muted">(bounced, marked as spam, failed, suppressed or delayed). Choose “Problems only” to see them.</span></div></div>`
      : `<div class="banner good"><div><b>No delivery problems</b> <span class="small muted">in this window. Checked ${when(SE.checked_at)}.</span></div></div>`;
    $('#se-tiles').innerHTML = [[fmt(c.total), 'Sent'], [fmt(c.reached), `Delivered (${pct(c.reached)})`], [fmt(c.by.bounced || 0), 'Bounced'],
      [fmt(c.by.complained || 0), 'Marked as spam'], [fmt(c.by.delivery_delayed || 0), 'Delayed'], [fmt((c.by.sent || 0) + (c.by.queued || 0) + (c.by.scheduled || 0)), 'Not yet delivered']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    const stSel = $('#se-status'), cur = stSel.value;
    stSel.innerHTML = '<option value="">Any status</option><option value="problems">Problems only</option>' +
      Object.entries(c.by).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<option value="${esc(k)}">${esc(seLabel(k))} (${fmt(n)})</option>`).join('');
    stSel.value = cur;
    const dSel = $('#se-domain'), dCur = dSel.value;
    dSel.innerHTML = SE.domains.map(d => `<option value="${esc(d)}">${esc(d)}</option>`).join('') + '<option value="">All domains</option>';
    dSel.value = dCur;
    const addr = f => { const m = String(f || '').match(/<([^>]+)>/); return m ? m[1] : String(f || ''); };
    $('#se-table tbody').innerHTML = SE.rows.map(r => `<tr class="click" data-se="${esc(r.id)}"><td class="small">${when(r.created_at)}</td>
      <td><b>${esc(r.subject || '(no subject)')}</b></td>
      <td class="small" title="${esc(r.to.join(', '))}">${esc(r.to[0] || '')}${r.to.length > 1 ? ` <span class="muted">+${r.to.length - 1}</span>` : ''}</td>
      <td class="small muted md-hide" title="${esc(r.from)}">${esc(addr(r.from))}</td>
      <td><span class="pill ${esc(r.status)}">${esc(seLabel(r.status))}</span></td>
      <td class="act ph-hide"><button class="btn sm" type="button" data-se="${esc(r.id)}">View</button></td></tr>`).join('')
      || '<tr><td colspan="6" class="empty">No emails match.</td></tr>';
    $('#se-foot').textContent = `Showing ${fmt(SE.rows.length)} of ${fmt(c.total)} in this window. ` +
      (SE.capped ? `Only the ${fmt(SE.fetched)} most recent sends are loaded (back to ${new Date(SE.oldest_fetched).toLocaleDateString()}); use the Resend dashboard for older mail.` : '');
  }
  async function showSent(id) {
    const box = $('#se-detail'); box.hidden = false; box.innerHTML = '<p class="muted small" style="margin:0">Loading…</p>';
    try {
      const d = await api('sent_detail', {params: {id}});
      const row = (k, v) => v && (!Array.isArray(v) || v.length) ? `<dt>${k}</dt><dd>${esc(Array.isArray(v) ? v.join(', ') : v)}</dd>` : '';
      box.innerHTML = `<div class="row" style="margin-bottom:10px"><h3 class="grow" style="font:600 .95rem var(--f-display);margin:0">${esc(d.subject || '(no subject)')}</h3>
        <span class="pill ${esc(d.status)}">${esc(seLabel(d.status))}</span><button class="btn" type="button" id="se-close" style="min-height:30px">Close</button></div>
        <dl>${row('Sent', new Date(d.created_at).toLocaleString())}${row('From', d.from)}${row('To', d.to)}${row('Cc', d.cc)}${row('Bcc', d.bcc)}${row('Reply-to', d.reply_to)}
        ${row('Tags', (d.tags || []).map(t => t.name + '=' + t.value))}${row('Resend id', d.id)}</dl>
        ${d.html ? '<iframe sandbox="" title="Email preview"></iframe>' : `<pre class="small" style="white-space:pre-wrap">${esc(d.text || '(no body)')}</pre>`}`;
      if (d.html) box.querySelector('iframe').srcdoc = d.html;
      $('#se-close').addEventListener('click', () => { box.hidden = true; });
      box.scrollIntoView({behavior: 'smooth', block: 'nearest'});
    } catch (e) { box.innerHTML = `<p class="small" style="color:var(--bad);margin:0">${esc(e.message)}</p>`; }
  }
  $('#se-table').addEventListener('click', e => { const b = e.target.closest('[data-se]'); if (b) showSent(b.dataset.se); });
  $('#se-refresh').addEventListener('click', loadSent);
  ['#se-days', '#se-domain', '#se-status'].forEach(s => $(s).addEventListener('change', loadSent));
  $('#se-q').addEventListener('input', () => { clearTimeout(seTimer); seTimer = setTimeout(loadSent, 300); });

  // ---------- email previews ----------
  let EM = null, emCur = null, emView = 'html', emReq = 0;
  async function loadEmails() {
    if (!EM) {
      EM = await api('email_previews');
      $('#em-gov').innerHTML = EM.govs.map(g => `<option value="${esc(g.key)}"${g.key === 'lh' ? ' selected' : ''}>${esc(g.name)}</option>`).join('');
      $('#em-list').innerHTML = EM.templates.map(x => `<button type="button" data-id="${esc(x.id)}" aria-pressed="false">${esc(x.name)}<span>${esc(x.when)}</span></button>`).join('');
      $('#em-list').querySelectorAll('button').forEach(b => b.addEventListener('click', () => showEmail(b.dataset.id)));
    }
    showEmail(emCur || EM.templates[0].id);
  }
  async function showEmail(id) {
    emCur = id;
    const tpl = EM.templates.find(x => x.id === id);
    $('#em-list').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
    $('#em-gov-wrap').hidden = ['manage_link', 'admin_signin'].includes(id);
    $('#em-src-wrap').hidden = !tpl.sources;
    $('#em-when').textContent = tpl.when; $('#em-test-msg').textContent = '';
    $('#em-subj').textContent = 'Loading…'; $('#em-note').hidden = true;
    const mine = ++emReq;
    let m;
    try { m = await api('email_preview', {params: {template: id, gov: $('#em-gov').value, source: $('#em-src').value}}); }
    catch (e) { m = {subject: '', html: '', text: '', note: e.message}; }
    if (mine !== emReq) return; // a newer preview was requested meanwhile
    $('#em-subj').textContent = m.subject ? 'Subject: ' + m.subject : 'No email';
    $('#em-note').hidden = !m.note; $('#em-note').textContent = m.note || '';
    $('#em-iframe').srcdoc = m.html ? m.html.replace(/<head>/i, '<head><base target="_blank">') : '<p style="font:14px Arial;color:#5A6372;padding:24px">Nothing to show.</p>';
    $('#em-text').textContent = m.text || '';
    $('#em-test').disabled = !m.html && !m.text;
  }
  $('#em-gov').addEventListener('change', () => emCur && showEmail(emCur));
  $('#em-src').addEventListener('change', () => emCur && showEmail(emCur));
  document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
    emView = b.dataset.view;
    document.querySelectorAll('[data-view]').forEach(x => x.setAttribute('aria-selected', String(x === b)));
    $('#em-frame').hidden = emView !== 'html'; $('#em-text').hidden = emView !== 'text';
  }));
  document.querySelectorAll('[data-width]').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('[data-width]').forEach(x => x.setAttribute('aria-selected', String(x === b)));
    $('#em-frame').classList.toggle('mobile', b.dataset.width === 'mobile');
  }));
  $('#em-test').addEventListener('click', async () => {
    const btn = $('#em-test'); btn.disabled = true; $('#em-test-msg').textContent = 'Sending…';
    try { const r = await api('email_test', {method: 'POST', body: {template: emCur, gov: $('#em-gov').value, source: $('#em-src').value}}); $('#em-test-msg').textContent = `Sent to ${r.to}. Subject starts with [Test].`; }
    catch (e) { $('#em-test-msg').textContent = e.message; }
    btn.disabled = false;
  });

  // ---------- write to officials ----------
  let CT = null; const coPicked = new Set();
  const STAFF_RE = /manager|attorney|clerk|director|superintendent|administrator|chief|finance|treasurer/i;
  const isStaff = c => !c.elected || STAFF_RE.test(c.seat);
  const dLabel = st => ({sent: 'Sent', delivered: 'Delivered', opened: 'Opened', clicked: 'Clicked', bounced: 'Bounced', complained: 'Marked as spam', failed: 'Failed', delivery_delayed: 'Delayed', suppressed: 'Suppressed', queued: 'Queued'}[st] || st);
  const cleanName = n => String(n || '').replace(/\s*\(.*?\)\s*/g, ' ').trim();
  async function loadCompose(force) {
    if (!CT || force) {
      // Postgres bigint ids arrive as strings; the page compares them as numbers.
      try { CT = await api('corr_contacts'); CT.contacts.forEach(c => { c.id = Number(c.id); }); }
      catch (e) { $('#co-list').innerHTML = `<p class="empty">${esc(e.message)}</p>`; return; }
      const govs = [...new Set(CT.contacts.map(c => c.government))];
      const cur = $('#co-gov').value;
      $('#co-gov').innerHTML = '<option value="">All governments</option>' + govs.map(g => `<option>${esc(g)}</option>`).join('');
      $('#co-gov').value = cur;
    }
    renderCompose();
  }
  function shownContacts() {
    const g = $('#co-gov').value, k = $('#co-kind').value;
    return CT.contacts.filter(c => (!g || c.government === g) && (!k || (k === 'staff') === isStaff(c)));
  }
  function renderCompose() {
    const rows = shownContacts(), byGov = new Map();
    rows.forEach(c => (byGov.get(c.government) || byGov.set(c.government, []).get(c.government)).push(c));
    $('#co-list').innerHTML = [...byGov].map(([g, cs]) => {
      const sendable = cs.filter(c => c.email && c.active);
      const allOn = sendable.length && sendable.every(c => coPicked.has(c.id));
      const shared = (CT.shared || []).find(s => s.government === g);
      return `<div class="co-gov"><span class="grow">${esc(g)}</span>${sendable.length ? `<button class="linkish" type="button" data-allgov="${esc(g)}">${allOn ? 'Clear' : 'Select all'}</button>` : ''}</div>` +
        (shared && (shared.shared_email || shared.contact_form) ? `<div class="co-p"><span></span><span class="sub" style="grid-column:2">Shared: ${shared.shared_email ? esc(shared.shared_email) : ''}${shared.contact_form ? ` <a href="${esc(shared.contact_form)}" target="_blank" rel="noopener">contact form</a>` : ''}</span><span></span></div>` : '') +
        cs.map(c => {
          const ok = c.email && c.active;
          return `<label class="co-p${ok ? '' : ' off'}"><input type="checkbox" data-pick="${c.id}"${coPicked.has(c.id) ? ' checked' : ''}${ok ? '' : ' disabled'}>
            <span class="nm">${esc(cleanName(c.name) || '(vacant)')} <span class="muted" style="font-weight:400">· ${esc(c.seat)}</span></span>
            <button class="linkish" type="button" data-edit="${c.id}">Edit</button>
            <span class="sub">${c.email ? esc(c.email) : 'No address on file'}${c.active ? '' : ' · turned off'}${c.source_url ? ` · <a href="${esc(c.source_url)}" target="_blank" rel="noopener">source</a>` : ''}</span></label>`;
        }).join('');
    }).join('') || '<p class="empty">No officials match.</p>';
    const sendableShown = rows.filter(c => c.email && c.active);
    $('#co-all').checked = sendableShown.length > 0 && sendableShown.every(c => coPicked.has(c.id));
    const noAddr = CT.contacts.filter(c => !c.email).length;
    $('#co-foot').textContent = `${fmt(CT.contacts.length - noAddr)} of ${fmt(CT.contacts.length)} seats have an address. Use Edit to add or correct one.`;
    updatePicked();
  }
  function updatePicked() {
    const ppl = CT.contacts.filter(c => coPicked.has(c.id));
    $('#co-count').textContent = `${ppl.length} selected`;
    $('#co-to').innerHTML = ppl.length ? ppl.map(c => `<span class="co-chip">${esc(cleanName(c.name))} · ${esc(c.seat)}<button class="linkish" type="button" data-unpick="${c.id}" aria-label="Remove">×</button></span>`).join('') : 'Pick officials on the left.';
    $('#co-send').disabled = !ppl.length;
    $('#co-send').textContent = ppl.length ? `Send to ${ppl.length} official${ppl.length === 1 ? '' : 's'}` : 'Send';
  }
  $('#co-list').addEventListener('change', e => {
    const id = Number(e.target.dataset.pick); if (!id) return;
    e.target.checked ? coPicked.add(id) : coPicked.delete(id); renderCompose();
  });
  $('#co-list').addEventListener('click', e => {
    const g = e.target.closest('[data-allgov]');
    if (g) {
      e.preventDefault();
      const cs = shownContacts().filter(c => c.government === g.dataset.allgov && c.email && c.active);
      const allOn = cs.every(c => coPicked.has(c.id));
      cs.forEach(c => allOn ? coPicked.delete(c.id) : coPicked.add(c.id)); renderCompose(); return;
    }
    const ed = e.target.closest('[data-edit]');
    if (ed) { e.preventDefault(); editContact(Number(ed.dataset.edit)); }
  });
  $('#co-to').addEventListener('click', e => { const b = e.target.closest('[data-unpick]'); if (b) { coPicked.delete(Number(b.dataset.unpick)); renderCompose(); } });
  $('#co-all').addEventListener('change', e => { shownContacts().filter(c => c.email && c.active).forEach(c => e.target.checked ? coPicked.add(c.id) : coPicked.delete(c.id)); renderCompose(); });
  ['#co-gov', '#co-kind'].forEach(s => $(s).addEventListener('change', renderCompose));

  let ctEditing = null;
  function editContact(id) {
    const c = CT.contacts.find(x => x.id === id); if (!c) return;
    ctEditing = c; const f = $('#ct-form');
    $('#ct-title').textContent = `${c.seat}, ${c.government}`;
    f.name.value = c.name || ''; f.email.value = c.email || ''; f.source_url.value = c.source_url || ''; f.notes.value = c.notes || ''; f.active.checked = !!c.active;
    $('#ct-err').textContent = ''; $('#ct-dialog').showModal();
  }
  $('#ct-save').addEventListener('click', async () => {
    const f = $('#ct-form');
    try {
      const r = await api('corr_contact', {method: 'POST', body: {id: ctEditing.id, name: f.name.value, email: f.email.value, source_url: f.source_url.value, notes: f.notes.value, active: f.active.checked}});
      Object.assign(ctEditing, r.contact, {id: Number(r.contact.id)});
      if (!(r.contact.email && r.contact.active)) coPicked.delete(ctEditing.id);
      $('#ct-dialog').close(); renderCompose();
    } catch (e) { $('#ct-err').textContent = e.message; }
  });

  $('#co-test').addEventListener('click', async () => {
    const btn = $('#co-test'); btn.disabled = true; $('#co-msg').textContent = 'Sending a test…';
    try { const r = await api('corr_send', {method: 'POST', body: {test: true, subject: $('#co-subj').value, body: $('#co-body').value, ids: [...coPicked]}}); $('#co-msg').textContent = `Test sent to ${r.to}. Its subject starts with [Test]; nothing was saved.`; }
    catch (e) { $('#co-msg').textContent = e.message; }
    btn.disabled = false;
  });
  $('#co-send').addEventListener('click', () => {
    if (!$('#co-subj').value.trim() || $('#co-body').value.trim().length < 10) { $('#co-msg').textContent = 'Add a subject and a message first.'; return; }
    const ppl = CT.contacts.filter(c => coPicked.has(c.id));
    $('#co-confirm-text').innerHTML = `<b>${esc($('#co-subj').value)}</b> goes to ${ppl.length} official${ppl.length === 1 ? '' : 's'}, each as a separate email. This can’t be unsent.`;
    $('#co-confirm-list').innerHTML = '<ul style="margin:0;padding-left:18px">' + ppl.map(c => `<li>${esc(cleanName(c.name))}, ${esc(c.seat)} (${esc(c.government)}) <span class="muted">${esc(c.email)}</span></li>`).join('') + '</ul>';
    $('#co-confirm').showModal();
  });
  $('#co-confirm-go').addEventListener('click', async () => {
    const btn = $('#co-confirm-go'); btn.disabled = true; btn.textContent = 'Sending…';
    try {
      const r = await api('corr_send', {method: 'POST', body: {subject: $('#co-subj').value, body: $('#co-body').value, ids: [...coPicked]}});
      $('#co-confirm').close();
      $('#co-msg').innerHTML = `Sent ${r.sent} email${r.sent === 1 ? '' : 's'}.` + (r.failed.length ? ` <span style="color:var(--bad)">${r.failed.length} failed: ${esc(r.failed.map(f => f.name + ' (' + f.error + ')').join('; '))}</span>` : '') +
        (r.skipped ? ` ${r.skipped} skipped (no address or turned off).` : '') + ' <button class="linkish" type="button" id="co-goto">View in Correspondence</button>';
      $('#co-goto').addEventListener('click', () => tab('correspondence'));
      coPicked.clear(); $('#co-subj').value = ''; $('#co-body').value = ''; renderCompose();
    } catch (e) { $('#co-confirm').close(); $('#co-msg').textContent = e.message; }
    btn.disabled = false; btn.textContent = 'Send now';
  });

  // ---------- records requests ----------
  let RR = null, rrOpen = null;
  const rrLabel = {draft: 'Draft', sent: 'Sent', received: 'Records received', closed: 'Closed'};
  async function loadRR() {
    try { RR = await api('rr_list'); RR.requests.forEach(r => { r.id = Number(r.id); }); }
    catch (e) { $('#rr-list').innerHTML = `<p class="empty">${esc(e.message)}</p>`; return; }
    renderRR();
  }
  function renderRR() {
    const rs = RR.requests, n = s => rs.filter(r => r.status === s).length;
    $('#rr-tiles').innerHTML = [['Drafts', n('draft')], ['Sent', n('sent')], ['Records received', n('received')], ['Need an address', rs.filter(r => r.status === 'draft' && !r.recipient_email).length]]
      .map(([l, v]) => `<div class="tile"><b>${fmt(v)}</b><span>${l}</span></div>`).join('');
    $('#rr-list').innerHTML = rs.map(r => `<button type="button" class="co-p${r.id === rrOpen ? ' on' : ''}" data-rr="${r.id}" style="width:100%;text-align:left;background:${r.id === rrOpen ? 'var(--sunken)' : 'none'};border-left:0;border-right:0;border-top:0;cursor:pointer;font:inherit;color:inherit">
        <span></span><span class="nm">${esc(r.government)}</span><span class="pill ${esc(r.status)}">${esc(rrLabel[r.status] || r.status)}</span>
        <span class="sub">${esc(r.gaps.length)} year${r.gaps.length === 1 ? '' : 's'} · ${r.recipient_email ? esc(r.recipient_email) : '<span style="color:var(--warn)">No address yet</span>'}</span></button>`).join('') || '<p class="empty">No requests.</p>';
    if (rrOpen) showRR(rrOpen);
  }
  $('#rr-list').addEventListener('click', e => { const b = e.target.closest('[data-rr]'); if (b) { rrOpen = Number(b.dataset.rr); renderRR(); } });
  function showRR(id) {
    const r = RR.requests.find(x => x.id === id); if (!r) return;
    const draft = r.status === 'draft', box = $('#rr-detail');
    box.innerHTML = `<div class="row" style="gap:8px;flex-wrap:wrap"><h2 class="h2 grow" style="margin:0">${esc(r.government)}</h2>
        <select class="sel" id="rr-status" aria-label="Status" style="width:auto">${Object.entries(rrLabel).map(([k, v]) => `<option value="${k}"${k === r.status ? ' selected' : ''}>${v}</option>`).join('')}</select></div>
      ${r.notes ? `<div class="banner"><div class="small">${esc(r.notes)}</div></div>` : ''}
      <div><div class="small muted" style="margin-bottom:4px">Missing years</div><div class="rr-gaps">${r.gaps.map(g => `<span title="${esc(g.need)}">FY${esc(g.fiscal_year)}</span>`).join('')}</div></div>
      <div class="row" style="gap:10px;flex-wrap:wrap">
        <label class="f grow" style="min-width:200px">To (name)<input id="rr-name" maxlength="200" value="${esc(r.recipient_name || '')}"${draft ? '' : ' disabled'}></label>
        <label class="f grow" style="min-width:200px">Email<input id="rr-email" type="email" value="${esc(r.recipient_email || '')}" placeholder="Add the records contact’s address"${draft ? '' : ' disabled'}></label>
      </div>
      ${r.contact_url ? `<p class="small muted" style="margin:-4px 0 0">Contact source: <a href="${esc(r.contact_url)}" target="_blank" rel="noopener">${esc(r.contact_url)}</a></p>` : ''}
      <label class="f">Subject<input id="rr-subj" maxlength="200" value="${esc(r.subject)}"${draft ? '' : ' disabled'}></label>
      <label class="f">Message<textarea id="rr-body" style="min-height:320px"${draft ? '' : ' disabled'}>${esc(r.body)}</textarea></label>
      <p class="small muted" style="margin:-4px 0 0">The email opens with “Dear ${esc(r.recipient_name && r.recipient_name.includes(',') ? r.recipient_name.split(',')[0] : 'Records Custodian')},” and ends with a reference number so the reply can be matched.</p>
      <label class="f">Notes (admin only)<textarea id="rr-notes" maxlength="2000">${esc(r.notes || '')}</textarea></label>
      <div class="row">${draft ? '<button class="btn" type="button" id="rr-save">Save draft</button><button class="btn" type="button" id="rr-test">Send a test to me</button><span class="grow"></span><button class="btn primary" type="button" id="rr-send">Send</button>'
        : `<button class="btn" type="button" id="rr-save">Save notes</button><span class="grow"></span>${r.thread_id ? '<button class="btn" type="button" id="rr-thread">Open in Correspondence</button>' : ''}`}</div>
      <p class="small" id="rr-msg" role="status" style="margin:0">${r.sent_at ? `Sent ${esc(stamp(r.sent_at))}${r.sent_by ? ' by ' + esc(r.sent_by) : ''}.` : ''}</p>`;
    const fields = () => draft ? {recipient_name: $('#rr-name').value, recipient_email: $('#rr-email').value, subject: $('#rr-subj').value, body: $('#rr-body').value, notes: $('#rr-notes').value} : {notes: $('#rr-notes').value};
    const save = async () => { const x = await api('rr_save', {method: 'POST', body: {id, ...fields()}}); Object.assign(r, x.request, {id}); return r; };
    $('#rr-save').addEventListener('click', async () => { try { await save(); renderRR(); $('#rr-msg').textContent = 'Saved.'; } catch (e) { $('#rr-msg').textContent = e.message; } });
    $('#rr-status').addEventListener('change', async e => {
      try { const x = await api('rr_save', {method: 'POST', body: {id, status: e.target.value}}); Object.assign(r, x.request, {id}); renderRR(); }
      catch (err) { e.target.value = r.status; $('#rr-msg').textContent = err.message; }
    });
    const th = $('#rr-thread'); if (th) th.addEventListener('click', () => { tab('correspondence'); showThread(Number(r.thread_id)); });
    if (!draft) return;
    $('#rr-test').addEventListener('click', async () => {
      $('#rr-msg').textContent = 'Saving and sending a test…';
      try { await save(); const x = await api('rr_send', {method: 'POST', body: {id, test: true}}); $('#rr-msg').textContent = `Test sent to ${x.to}. Its subject starts with [Test]; the request is still a draft.`; }
      catch (e) { $('#rr-msg').textContent = e.message; }
    });
    $('#rr-send').addEventListener('click', async () => {
      try { await save(); } catch (e) { $('#rr-msg').textContent = e.message; return; }
      if (!r.recipient_email) { $('#rr-msg').textContent = 'Add the recipient’s email address first.'; return; }
      $('#rr-confirm-text').innerHTML = `<b>${esc(r.subject)}</b> goes to ${esc(r.recipient_name || '')} at <b>${esc(r.recipient_email)}</b>. This can’t be unsent.`;
      $('#rr-confirm').showModal();
    });
  }
  $('#rr-confirm-go').addEventListener('click', async () => {
    const btn = $('#rr-confirm-go'); btn.disabled = true; btn.textContent = 'Sending…';
    try { await api('rr_send', {method: 'POST', body: {id: rrOpen}}); $('#rr-confirm').close(); await loadRR(); $('#rr-msg').textContent = 'Sent. The reply will show up under Correspondence.'; }
    catch (e) { $('#rr-confirm').close(); $('#rr-msg').textContent = e.message; }
    btn.disabled = false; btn.textContent = 'Send now';
  });

  // ---------- correspondence ----------
  let CR = null, crOpen = null, crTimer = null, crYearSet = false;
  const crLabel = {awaiting: 'Awaiting reply', replied: 'Replied', closed: 'Closed'};
  async function loadCorr() {
    const params = {q: $('#cr-q').value, government: $('#cr-gov').value, status: $('#cr-status').value, published: $('#cr-pub').value, year: $('#cr-year').value};
    try { CR = await api('corr_threads', {params}); }
    catch (e) { $('#cr-table tbody').innerHTML = `<tr><td colspan="7" class="empty">${esc(e.message)}</td></tr>`; return; }
    if (!crYearSet) {
      // Opens on the latest year with mail; older years are one choice away.
      $('#cr-year').innerHTML = CR.years.map(y => `<option value="${y}">${y}</option>`).join('') + '<option value="">All years</option>';
      $('#cr-year').value = CR.years.length ? String(CR.years[0]) : '';
      crYearSet = true;
      if (CR.years.length > 1) return loadCorr();
    }
    const gSel = $('#cr-gov'), gCur = gSel.value;
    gSel.innerHTML = '<option value="">All governments</option>' + CR.governments.map(g => `<option>${esc(g)}</option>`).join(''); gSel.value = gCur;
    const t = CR.totals;
    $('#cr-tiles').innerHTML = [[fmt(t.threads), 'Conversations'], [fmt(t.awaiting), 'Awaiting reply'], [fmt(t.replied), 'Replied'], [fmt(t.published), 'Published']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    const opts = CR.threads.map(x => `<option value="${x.id}">${esc(cleanName(x.official_name))} · ${esc(x.subject)}</option>`).join('');
    $('#cr-unmatched').innerHTML = CR.unmatched.length ? `<div class="banner bad"><div style="flex:1"><b>${CR.unmatched.length} email${CR.unmatched.length === 1 ? '' : 's'} to hello@ didn’t match a conversation.</b>
      <div class="small muted">Match each one to the conversation it belongs to, or dismiss it if it isn’t correspondence.</div>
      ${CR.unmatched.map(m => `<div class="row small" style="margin-top:8px;align-items:flex-start"><div class="grow" style="min-width:220px"><b>${esc(m.from_addr)}</b> · ${esc(m.subject || '(no subject)')} · ${when(m.at)}<div class="muted">${esc((m.snippet || '').slice(0, 160))}</div></div>
        <select class="sel" data-um="${m.id}" aria-label="Conversation"><option value="">Match to…</option>${opts}</select><button class="btn" type="button" data-dismiss="${m.id}">Dismiss</button></div>`).join('')}</div></div>` : '';
    $('#cr-table tbody').innerHTML = CR.threads.map(x => `<tr class="click" data-th="${x.id}"><td class="small" style="white-space:nowrap">${when(x.last_at)}</td>
      <td><b>${esc(cleanName(x.official_name))}</b><div class="small muted">${esc(x.official_seat)} · ${esc(x.government)}</div></td><td>${esc(x.subject)}</td>
      <td class="num">${x.sent}</td><td class="num">${x.received}</td><td><span class="pill ${esc(x.status)}">${esc(crLabel[x.status] || x.status)}</span>${x.delivery && x.delivery !== 'delivered' && x.delivery !== 'sent' ? ` <span class="pill ${esc(x.delivery)}">${esc(dLabel(x.delivery))}</span>` : ''}</td>
      <td>${x.published ? '<span class="pill public">Public</span>' : '<span class="muted small">Private</span>'}</td></tr>`).join('')
      || '<tr><td colspan="7" class="empty">No conversations yet. Start one under “Write to officials.”</td></tr>';
    if (crOpen) showThread(crOpen, true);
  }
  async function showThread(id, quiet) {
    crOpen = id;
    const box = $('#cr-detail'); box.hidden = false;
    if (!quiet) box.innerHTML = '<p class="muted small" style="margin:0">Loading…</p>';
    let d;
    try { d = await api('corr_thread', {params: {id}}); } catch (e) { box.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
    const t = d.thread;
    box.innerHTML = `<div class="row" style="margin-bottom:12px;align-items:flex-start"><div class="grow"><h3 style="font:600 1rem var(--f-display);margin:0 0 2px">${esc(t.subject)}</h3>
        <div class="small muted">${esc(cleanName(t.official_name))}, ${esc(t.official_seat)} · ${esc(t.government)} · ${esc(t.email || '')}</div></div>
        <label class="toggle small"><input type="checkbox" id="th-pub"${t.published ? ' checked' : ''}> Public</label>
        <select class="sel" id="th-status" aria-label="Status">${Object.entries(crLabel).map(([k, v]) => `<option value="${k}"${k === t.status ? ' selected' : ''}>${v}</option>`).join('')}</select>
        <button class="btn" type="button" id="th-close">Close</button></div>
      ${t.batch_id ? `<p class="small muted" style="margin:0 0 10px">Part of a send to several officials. <button class="linkish" type="button" id="th-pub-batch">Publish every conversation from that send</button></p>` : ''}
      ${d.messages.map(m => `<div class="th-msg ${m.direction}"><header><b>${m.direction === 'out' ? 'BayCounty.me' : esc(m.from_addr)}</b><span>${m.direction === 'out' ? 'to ' + esc(m.to_addr) : 'replied'}</span><span>${esc(stamp(m.at))}</span>
        ${m.direction === 'out' ? `<span class="pill ${esc(m.status)}">${esc(dLabel(m.status))}</span>` : (m.matched_by ? `<span class="small">matched by ${esc(m.matched_by)}</span>` : '')}
        ${(m.attachments || []).length ? `<span>📎 ${esc(m.attachments.map(a => a.filename).join(', '))}</span>` : ''}</header>
        <div class="body">${esc(m.shown.text || '(no text)')}</div>
        ${m.shown.quoted ? `<details class="ag" style="margin-top:6px"><summary class="small">Show quoted text</summary><pre>${esc(m.body_text)}</pre></details>` : ''}</div>`).join('')}
      <label class="f" style="margin-top:6px">Reply to ${esc(cleanName(t.official_name))}<textarea id="th-reply" placeholder="Sent as a reply in the same email thread"></textarea></label>
      <div class="row" style="margin-top:8px"><button class="btn primary" type="button" id="th-send">Send reply</button><span class="small" id="th-msg" role="status"></span></div>`;
    $('#th-close').addEventListener('click', () => { box.hidden = true; crOpen = null; });
    $('#th-pub').addEventListener('change', async e => {
      try { await api('corr_publish', {method: 'POST', body: {id, published: e.target.checked}}); loadCorr(); } catch (err) { e.target.checked = !e.target.checked; alert(err.message); }
    });
    const pb = $('#th-pub-batch');
    if (pb) pb.addEventListener('click', async () => { if (!confirm('Publish every conversation from this send?')) return; await api('corr_publish', {method: 'POST', body: {batch: t.batch_id, published: true}}); loadCorr(); });
    $('#th-status').addEventListener('change', async e => { await api('corr_status', {method: 'POST', body: {id, status: e.target.value}}); loadCorr(); });
    $('#th-send').addEventListener('click', async () => {
      const b = $('#th-send'); b.disabled = true; $('#th-msg').textContent = 'Sending…';
      try { await api('corr_reply', {method: 'POST', body: {thread_id: id, body: $('#th-reply').value}}); $('#th-msg').textContent = 'Sent.'; showThread(id, true); loadCorr(); }
      catch (e) { $('#th-msg').textContent = e.message; }
      b.disabled = false;
    });
    if (!quiet) box.scrollIntoView({behavior: 'smooth', block: 'nearest'});
  }
  $('#cr-table').addEventListener('click', e => { const r = e.target.closest('[data-th]'); if (r) showThread(Number(r.dataset.th)); });
  $('#cr-unmatched').addEventListener('change', async e => {
    const s = e.target.closest('[data-um]'); if (!s || !s.value) return;
    try { await api('corr_assign', {method: 'POST', body: {message_id: s.dataset.um, thread_id: s.value}}); loadCorr(); } catch (err) { alert(err.message); }
  });
  $('#cr-unmatched').addEventListener('click', async e => {
    const b = e.target.closest('[data-dismiss]'); if (!b || !confirm('Dismiss this email? It stays in the Resend inbox.')) return;
    await api('corr_dismiss', {method: 'POST', body: {message_id: b.dataset.dismiss}}); loadCorr();
  });
  ['#cr-year', '#cr-gov', '#cr-status', '#cr-pub'].forEach(s => $(s).addEventListener('change', loadCorr));
  $('#cr-q').addEventListener('input', () => { clearTimeout(crTimer); crTimer = setTimeout(loadCorr, 300); });

  // ---------- bulk review (shared by every review queue) ----------
  // Adds a bar above a review table: tick rows (shift-click for a range), select all shown, unreviewed or high-confidence,
  // then confirm, reject or reset them in one go. The loader puts b.cell(row) in the first column and calls b.set(rows)
  // after rendering. Requests go out in batches of 500; the server records who reviewed what in the audit log.
  const BULK_MAX = 500;
  function bulkReview(o) {
    const table = $(o.table), picked = new Set();
    let rows = [], last = null, msg = '';
    const bar = document.createElement('div');
    bar.className = 'bk'; bar.setAttribute('role', 'region'); bar.setAttribute('aria-label', 'Review several at once');
    table.closest('.tw').before(bar);
    const plural = n => n === 1 ? o.noun[0] : o.noun[1];
    const sure = r => !!(o.confident && r.review_status === 'unreviewed' && o.confident(r));
    const shown = () => rows.filter(r => !o.canPick || o.canPick(r));
    function render() {
      const n = picked.size, all = shown(), un = all.filter(r => r.review_status === 'unreviewed').length, hi = all.filter(sure).length;
      bar.innerHTML = `<div class="row bk-top">
          <b class="bk-n">${n ? fmt(n) + ' selected' : 'Select'}</b>
          <button type="button" class="linkish" data-bk-sel="all">All shown (${fmt(all.length)})</button>
          <button type="button" class="linkish" data-bk-sel="unreviewed">Unreviewed (${fmt(un)})</button>
          ${o.confident ? `<button type="button" class="linkish" data-bk-sel="sure" title="${esc(o.confidentHelp || '')}">${esc(o.confidentLabel)} (${fmt(hi)})</button>` : ''}
          ${n ? '<button type="button" class="linkish" data-bk-sel="none">Clear</button>' : ''}
          <span class="grow"></span>
          ${o.statuses.map(([st, label, cls]) => `<button type="button" class="btn ${cls || ''}" data-bk-do="${st}"${n ? '' : ' disabled'}>${esc(label)}${n ? ' ' + fmt(n) : ''}</button>`).join('')}
        </div>
        ${o.confident && hi ? `<div class="row bk-sure"><span class="small muted grow">${esc(o.confidentHelp || '')}</span><button type="button" class="btn primary" data-bk-sure>Confirm all ${fmt(hi)} ${esc(o.confidentLabel.toLowerCase())}</button></div>` : ''}
        ${o.note ? `<p class="small muted bk-note">${o.note}</p>` : ''}
        ${msg ? `<div class="bk-msg">${msg}</div>` : ''}`;
      const boxes = table.querySelectorAll('[data-bk]');
      boxes.forEach(c => { c.checked = picked.has(c.dataset.bk); });
      const head = table.querySelector('[data-bk-all]');
      if (head) { head.checked = boxes.length > 0 && n >= boxes.length && [...boxes].every(c => c.checked); head.indeterminate = n > 0 && !head.checked; }
    }
    function pick(list, on = true) { list.forEach(r => on ? picked.add(o.key(r)) : picked.delete(o.key(r))); msg = ''; render(); }
    async function run(status, list) {
      if (!list.length) return;
      const [, label] = o.statuses.find(x => x[0] === status) || [status, status];
      const warn = (o.warn && o.warn(status)) || '';
      if (!confirm(`${label} ${fmt(list.length)} ${plural(list.length)}?${warn ? '\n\n' + warn : ''}`)) return;
      bar.querySelectorAll('button').forEach(b => { b.disabled = true; });
      msg = '<span class="small muted">Saving…</span>'; render();
      let done = 0, published = null;
      try {
        for (let i = 0; i < list.length; i += BULK_MAX) {
          const r = await api(o.action, {method: 'POST', body: {status, ...o.body(list.slice(i, i + BULK_MAX))}});
          done += r.updated || 0; if (r.published != null) published = r.published;
        }
        picked.clear();
        msg = `<div class="banner good"><div><b>${esc(label)}: ${fmt(done)} ${plural(done)}.</b>${published != null && o.published ? ` <span class="small">${esc(o.published(published))}</span>` : ''} <span class="small muted">Logged under Throttles &amp; settings → Admin activity.</span></div></div>`;
      } catch (e) {
        msg = `<div class="banner bad"><div><b>Stopped after ${fmt(done)}.</b> <span class="small">${esc(e.message)}</span></div></div>`;
      }
      await o.reload();
    }
    bar.addEventListener('click', e => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.bkSel === 'all') pick(shown());
      else if (b.dataset.bkSel === 'unreviewed') { picked.clear(); pick(shown().filter(r => r.review_status === 'unreviewed')); }
      else if (b.dataset.bkSel === 'sure') { picked.clear(); pick(shown().filter(sure)); }
      else if (b.dataset.bkSel === 'none') { picked.clear(); msg = ''; render(); }
      else if (b.dataset.bkDo) { const by = new Map(rows.map(r => [o.key(r), r])); run(b.dataset.bkDo, [...picked].map(k => by.get(k)).filter(Boolean)); }
      else if (b.dataset.bkSure !== undefined) run('confirmed', shown().filter(sure));
    });
    table.addEventListener('click', e => {
      const c = e.target.closest('[data-bk]'); if (!c) return;
      const boxes = [...table.querySelectorAll('[data-bk]')];
      if (e.shiftKey && last && last !== c) {
        const [a, z] = [boxes.indexOf(last), boxes.indexOf(c)].sort((x, y) => x - y);
        boxes.slice(a, z + 1).forEach(x => { x.checked = c.checked; c.checked ? picked.add(x.dataset.bk) : picked.delete(x.dataset.bk); });
      } else c.checked ? picked.add(c.dataset.bk) : picked.delete(c.dataset.bk);
      last = c; msg = ''; render();
    });
    table.addEventListener('change', e => {
      if (!e.target.matches('[data-bk-all]')) return;
      const keys = [...table.querySelectorAll('[data-bk]')].map(c => c.dataset.bk);
      keys.forEach(k => e.target.checked ? picked.add(k) : picked.delete(k));
      msg = ''; render();
    });
    return {
      cell: r => (!o.canPick || o.canPick(r)) ? `<td class="pk"><input type="checkbox" data-bk="${esc(o.key(r))}" aria-label="Select"${picked.has(o.key(r)) ? ' checked' : ''}></td>` : '<td class="pk"></td>',
      set(list) { rows = list || []; const keys = new Set(rows.map(o.key)); [...picked].forEach(k => { if (!keys.has(k)) picked.delete(k); }); last = null; render(); },
      mark(key, status) { const r = rows.find(x => o.key(x) === key); if (r) { r.review_status = status; render(); } },
    };
  }
  const REVIEW_BTNS = [['confirmed', 'Confirm', 'primary'], ['rejected', 'Reject', 'danger'], ['unreviewed', 'Back to unreviewed']];

  // ---------- business owners (private registry, api/_registry.js) ----------
  const owUsd = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', {maximumFractionDigits: 0});
  const owNm = s => esc(String(s || '').replace(/\s+/g, ' ').trim());
  const SUNBIZ_SEARCH = 'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults';
  // Sunbiz record pages need an internal id the state files don't carry, so link the entity-name search (business listed
  // first). Same rule as data/entities/ids.py sunbiz_url().
  const owSunbiz = (name, doc) => {
    const nm = String(name || '').trim().replace(/\s+/g, ' ');
    if (!nm) return doc ? `${SUNBIZ_SEARCH}?inquiryType=DocumentNumber&searchTerm=${encodeURIComponent(String(doc).trim().toUpperCase())}` : null;
    const enc = s => encodeURIComponent(s).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
    return /[\/\\&*%:<>?]/.test(nm) ? `${SUNBIZ_SEARCH}?inquiryType=EntityName&searchTerm=${enc(nm)}` : `${SUNBIZ_SEARCH}/EntityName/${enc(nm)}/Page1`;
  };
  const OW_REV = {unreviewed: 'Unreviewed', confirmed: 'Confirmed', rejected: 'Rejected'};
  const owKey = g => g.group_id + '|' + g.candidate;
  const owBulk = bulkReview({table: '#ow-groups', noun: ['group', 'groups'], action: 'registry_review', statuses: REVIEW_BTNS, key: owKey,
    body: list => ({items: list.map(g => ({group_id: g.group_id, candidate: g.candidate}))}),
    warn: st => st === 'confirmed' ? 'Confirmed groups are published on /connections/shared-owners (business names only). Check each on Sunbiz first.' : 'Anything not confirmed is taken off the public page.',
    published: n => `${fmt(n)} business rows are now public.`, reload: () => loadOwners()});
  async function loadOwners() {
    let r;
    try { r = await api('registry', {params: {status: $('#ow-status').value}}); }
    catch (e) { $('#ow-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load the registry.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const s = (r.load && r.load.summary) || {};
    const rv = Object.fromEntries((r.review || []).map(x => [x.review_status, x.n]));
    $('#ow-tiles').innerHTML = r.load ? [[fmt(s.entities), 'Registered entities'], [fmt(s.residents_on_2plus_active), 'Residents running 2+ active businesses'],
      [`${fmt(s.matched_entities)}`, 'Businesses matched to campaign gifts'], [fmt(r.load.groups), 'Shared-owner groups'], [owUsd(s.shared_owner_dollars), 'Given by those groups'],
      [fmt(rv.unreviewed || 0), 'Not yet reviewed'], [when(r.load.loaded_at).replace(/<[^>]+>/g, ''), 'Last loaded']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('') : '<div class="banner"><div>Not loaded yet. The Sync database workflow loads it after the next push to main.</div></div>';
    $('#ow-groups tbody').innerHTML = r.groups.map(g => `<tr>${owBulk.cell(g)}
      <td><b>${esc(g.candidate)}</b><div class="muted small">${esc(g.office || '')}</div>${g.report_url ? `<a class="small" href="${esc(g.report_url)}" target="_blank" rel="noopener">Campaign report</a>` : ''}</td>
      <td class="small">${g.businesses.map(b => `<div><a href="#" data-doc="${esc(b.doc_number)}">${owNm(b.entity_name)}</a> ${b.status === 'I' ? '<span class="pill">Inactive</span> ' : ''}<span class="muted">${owUsd(b.amount)}${b.dates.length ? ', ' + esc(b.dates.join(', ')) : ''}</span></div>`).join('')}</td>
      <td class="small">${g.people.map(p => `<div><a href="#" data-person="${esc(p.person_key)}">${owNm(p.name)}</a> <span class="muted">${esc(p.city || '')}${p.resident ? '' : ', outside the county'}</span></div>`).join('')}</td>
      <td class="num">${fmt(g.n_checks)}${g.all_at_1000 ? '<div class="muted small">all $1,000</div>' : ''}${g.same_day ? '<div class="muted small">same day</div>' : ''}</td>
      <td class="num"><b>${owUsd(g.combined_amount)}</b></td>
      <td><select class="sel" data-review="${esc(g.group_id)}" data-cand="${esc(g.candidate)}" aria-label="Review">${Object.entries(OW_REV).map(([k, l]) => `<option value="${k}"${k === g.review_status ? ' selected' : ''}>${l}</option>`).join('')}</select>${g.reviewed_by ? `<div class="muted small">${esc(g.reviewed_by)}</div>` : ''}</td></tr>`).join('')
      || '<tr><td colspan="7" class="empty">No groups.</td></tr>';
    owBulk.set(r.groups);
  }
  async function owDetail(kind, id) {
    const box = $('#ow-detail'); box.innerHTML = '<p class="muted small">Loading…</p>';
    try {
      if (kind === 'person') {
        const r = await api('registry_person', {params: {key: id}}); const p = r.person;
        box.innerHTML = `<h3 class="h2">${owNm(p.display_name)}</h3><p class="muted small">${esc(p.city || '')} ${esc(p.zip5 || '')}${p.resident ? '' : ' (outside the county)'} · ${fmt(p.active_entities_as_officer)} active of ${fmt(p.entities_as_officer)} entities as officer · ${fmt(p.entities_as_agent)} as registered agent${p.corporate_officer ? ' · <b>corporate officer</b> (left out of groups)' : ''}${p.agent_service ? ' · <b>agent service</b>' : ''}</p>
          <div class="tw"><table class="at" data-tt="off"><thead><tr><th>Business</th><th>Status</th><th>Role</th><th>City</th><th class="num">Matched gifts</th><th>To</th></tr></thead><tbody>${r.businesses.map(b => `<tr><td><a href="#" data-doc="${esc(b.doc_number)}">${owNm(b.name)}</a></td><td>${b.status === 'A' ? 'Active' : 'Inactive'}</td><td class="small">${esc(b.titles || '')}</td><td class="small">${esc(b.principal_city || '')}</td><td class="num">${b.gifts_total ? owUsd(b.gifts_total) : '<span class="muted">—</span>'}</td><td class="small">${esc((b.candidates || []).join(', '))}</td></tr>`).join('')}</tbody></table></div>`;
      } else {
        const r = await api('registry_entity', {params: {doc: id}}); const e = r.entity;
        box.innerHTML = `<h3 class="h2">${owNm(e.name)}</h3><p class="muted small">${esc(e.doc_number)} · ${e.status === 'A' ? 'Active' : 'Inactive'} · ${esc(e.filing_type || '')} · ${esc(e.principal_city || '')} · <a href="${owSunbiz(e.name, e.doc_number)}" target="_blank" rel="noopener">Sunbiz record</a></p>
          <div class="tw"><table class="at" data-tt="off"><thead><tr><th>Person</th><th>Role</th><th>City</th><th class="num">Active businesses</th></tr></thead><tbody>${r.people.map(p => `<tr><td><a href="#" data-person="${esc(p.person_key)}">${owNm(p.display_name)}</a>${p.agent_service ? ' <span class="pill">agent service</span>' : ''}${p.corporate_officer ? ' <span class="pill">corporate officer</span>' : ''}</td><td class="small">${esc(p.titles || '')}</td><td class="small">${esc(p.city || '')}</td><td class="num">${fmt(p.active_entities_as_officer)}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">No people listed.</td></tr>'}</tbody></table></div>
          <div class="tw" style="margin-top:10px"><table class="at" data-tt="off"><thead><tr><th>Date</th><th>Candidate</th><th>Filed as</th><th class="num">Amount</th><th>Match</th></tr></thead><tbody>${r.gifts.map(g => `<tr><td class="small">${esc(String(g.gift_date || '').slice(0, 10))}</td><td>${esc(g.candidate)}</td><td class="small">${esc(g.contributor)}</td><td class="num">${owUsd(g.amount)}</td><td class="small muted">${esc(g.match_method || '')}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">No matched campaign gifts.</td></tr>'}</tbody></table></div>`;
      }
      box.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (err) { box.innerHTML = `<div class="banner bad"><div>${esc(err.message)}</div></div>`; }
  }
  $('#tab-owners').addEventListener('click', e => {
    const a = e.target.closest('[data-doc],[data-person]'); if (!a) return;
    e.preventDefault(); a.dataset.doc ? owDetail('entity', a.dataset.doc) : owDetail('person', a.dataset.person);
  });
  $('#ow-groups').addEventListener('change', async e => {
    const s = e.target.closest('[data-review]'); if (!s) return;
    s.disabled = true;
    try { await api('registry_review', {method: 'POST', body: {group_id: s.dataset.review, candidate: s.dataset.cand, status: s.value}}); owBulk.mark(s.dataset.review + '|' + s.dataset.cand, s.value); }
    catch (err) { alert(err.message); }
    s.disabled = false;
  });
  $('#ow-status').addEventListener('change', loadOwners);
  // gifts over the per-election limit (registry.limit_cases)
  const OL_REV = {unreviewed: 'Unreviewed', confirmed: 'Confirmed (open)', resolved: 'Resolved', rejected: 'Rejected'};
  const OL_RES = {reporting_error: 'Reporting error', amended_report: 'Amended report', refunded: 'Refunded', designated_general: 'Designated for the general', elections_commission: 'Elections Commission ruling', other: 'Other'};
  const olBulk = bulkReview({table: '#ol-cases', noun: ['case', 'cases'], action: 'registry_limit_review', key: c => c.case_id,
    statuses: [['confirmed', 'Confirm (open)', 'primary'], ['rejected', 'Reject', 'danger'], ['unreviewed', 'Back to unreviewed']],
    body: list => ({case_ids: list.map(c => c.case_id)}),
    warn: st => st === 'confirmed' ? 'Confirmed cases are published on /connections/shared-owners as open cases ("Over the limit as reported").' : 'Anything not confirmed or resolved is taken off the public page.',
    note: 'Resolve cases one at a time below, since each needs its own explanation and source.',
    published: n => `${fmt(n)} cases are now public.`, reload: () => loadLimits()});
  async function loadLimits() {
    let r;
    try { r = await api('registry_limits', {params: {status: $('#ol-status').value}}); }
    catch (e) { $('#ol-cases tbody').innerHTML = `<tr><td colspan="6" class="empty">Couldn’t load: ${esc(e.message)}</td></tr>`; return; }
    $('#ol-cases tbody').innerHTML = r.cases.map(c => {
      const res = c.resolution || c.auto_resolution || '';
      return `<tr data-case="${esc(c.case_id)}">${olBulk.cell(c)}
      <td><b>${esc(c.candidate)}</b><div class="muted small">${esc(c.office || '')}</div><div class="muted small">${esc(c.election || '')}${c.election_phase ? ' · ' + esc(c.election_phase) : ''}</div>${c.report_url ? `<a class="small" href="${esc(c.report_url)}" target="_blank" rel="noopener">Campaign report</a>` : ''}</td>
      <td>${owNm(c.contributor)}<div class="muted small">${esc(c.contributor_type || '')}${(c.spellings || []).length > 1 ? ' · filed as ' + esc(c.spellings.join(' / ')) : ''}</div>${c.possible_double_entry ? '<span class="pill">same amount, same day</span>' : ''}${c.in_current_data ? '' : ' <span class="pill">no longer in the reports</span>'}</td>
      <td class="small">${(c.items || []).map(i => `<div>${esc(i.date || '')} <b>${owUsd(i.amount)}</b> <span class="muted">${esc(i.kind || '')}</span></div>`).join('')}</td>
      <td class="num"><b>${owUsd(c.net_amount)}</b>${c.refunds ? `<div class="muted small">${owUsd(c.refunds)} refunded</div>` : ''}<div class="small">${c.over_by ? owUsd(c.over_by) + ' over' : 'at the limit'}</div></td>
      <td style="min-width:240px"><select class="sel" data-ol="status" aria-label="Review">${Object.entries(OL_REV).map(([k, l]) => `<option value="${k}"${k === c.review_status ? ' selected' : ''}>${l}</option>`).join('')}</select>
        <div data-ol-res style="margin-top:6px;gap:4px;display:${c.review_status === 'resolved' ? 'grid' : 'none'}">
          <select class="sel" data-ol="resolution" aria-label="How it was resolved"><option value="">How was it resolved?</option>${Object.entries(OL_RES).map(([k, l]) => `<option value="${k}"${k === res ? ' selected' : ''}>${l}</option>`).join('')}</select>
          <input class="sel" data-ol="note" placeholder="What happened (shown publicly)" value="${esc(c.resolution_note || '')}">
          <input class="sel" data-ol="url" placeholder="Source link (amended report, ruling…)" value="${esc(c.resolution_url || '')}">
        </div>
        <div class="row" style="gap:6px;margin-top:6px"><button class="btn" data-ol-save style="min-height:30px;padding:0 10px">Save</button><span class="small muted" data-ol-msg>${c.reviewed_by ? 'by ' + esc(c.reviewed_by) : ''}</span></div></td></tr>`;
    }).join('') || '<tr><td colspan="6" class="empty">No cases.</td></tr>';
    olBulk.set(r.cases);
  }
  $('#ol-cases').addEventListener('change', e => {
    const s = e.target.closest('[data-ol="status"]'); if (!s) return;
    s.closest('tr').querySelector('[data-ol-res]').style.display = s.value === 'resolved' ? 'grid' : 'none';
  });
  $('#ol-cases').addEventListener('click', async e => {
    const b = e.target.closest('[data-ol-save]'); if (!b) return;
    const tr = b.closest('tr'), v = k => tr.querySelector(`[data-ol="${k}"]`).value, msg = tr.querySelector('[data-ol-msg]');
    b.disabled = true; msg.textContent = 'Saving…';
    try {
      const r = await api('registry_limit_review', {method: 'POST', body: {case_id: tr.dataset.case, status: v('status'), resolution: v('resolution'), resolution_note: v('note'), resolution_url: v('url')}});
      msg.textContent = r.published ? 'Saved, published' : 'Saved, not public';
      olBulk.mark(tr.dataset.case, v('status'));
    } catch (err) { msg.textContent = err.message; }
    b.disabled = false;
  });
  $('#ol-status').addEventListener('change', loadLimits);
  $('#tab-limits').addEventListener('click', e => {
    const a = e.target.closest('[data-doc],[data-person]'); if (!a) return;
    e.preventDefault(); tab('owners'); a.dataset.doc ? owDetail('entity', a.dataset.doc) : owDetail('person', a.dataset.person);
  });
  let owTimer;
  $('#ow-q').addEventListener('input', () => {
    clearTimeout(owTimer);
    owTimer = setTimeout(async () => {
      const q = $('#ow-q').value.trim(); const box = $('#ow-results');
      if (q.length < 3) { box.innerHTML = ''; return; }
      try {
        const r = await api('registry_search', {params: {q}});
        box.innerHTML = `<div class="tw"><table class="at" data-tt="off"><tbody>${r.people.map(p => `<tr><td>Person</td><td><a href="#" data-person="${esc(p.person_key)}">${owNm(p.display_name)}</a></td><td class="small muted">${esc(p.city || '')}</td><td class="num small">${fmt(p.active_entities_as_officer)} active businesses</td></tr>`).join('')}${r.entities.map(b => `<tr><td>Business</td><td><a href="#" data-doc="${esc(b.doc_number)}">${owNm(b.name)}</a></td><td class="small muted">${esc(b.principal_city || '')}</td><td class="small">${b.status === 'A' ? 'Active' : 'Inactive'}</td></tr>`).join('') || ''}</tbody></table></div>`
          + (r.people.length || r.entities.length ? '' : '<p class="muted small">No matches.</p>');
      } catch (err) { box.innerHTML = `<p class="small">${esc(err.message)}</p>`; }
    }, 300);
  });

  // ---------- nonprofit boards (private registry, api/_boards.js) ----------
  const BD_SRC = {irs_990: 'IRS 990', irs_990ez: 'IRS 990-EZ', irs_990pf: 'IRS 990-PF', irs_990n: 'IRS 990-N', sunbiz: 'Sunbiz', fdacs: 'FDACS'};
  const bdSrc = s => String(s || '').split(', ').map(x => BD_SRC[x] || x).join(', ');
  const bdYears = b => b.first_year && b.last_year && b.first_year !== b.last_year ? `${b.first_year}–${b.last_year}` : (b.last_year || b.first_year || '');
  const bdBoards = list => (list || []).map(n => `<div>${owNm(n)}</div>`).join('');
  const bdBulk = bulkReview({table: '#bd-officials', noun: ['match', 'matches'], action: 'boards_review', statuses: REVIEW_BTNS,
    key: m => m.board_key + '|' + m.official_id, body: list => ({items: list.map(m => ({board_key: m.board_key, official_id: m.official_id}))}),
    confident: m => Number(m.same_name_people) <= 1, confidentLabel: 'Unique names',
    confidentHelp: 'Unique names: no other person with this name in the state corporate file (Sunbiz), so the board member is most likely the official.',
    warn: st => st === 'confirmed' ? 'Confirmed matches are tagged as officials on /connections/nonprofits.' : 'Anything not confirmed loses its official tag on the public page.',
    published: n => `${fmt(n)} official tags are now public.`, reload: () => loadBoards()});
  async function loadBoards() {
    let r;
    try { r = await api('boards', {params: {status: $('#bd-status').value}}); }
    catch (e) { $('#bd-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load nonprofit boards.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const s = (r.load && r.load.summary) || {};
    const rv = Object.fromEntries((r.review || []).map(x => [x.review_status, x.n]));
    $('#bd-tiles').innerHTML = r.load ? [[fmt(s.nonprofits), 'Nonprofits'], [fmt(s.with_board_list), 'With a board list'], [fmt(s.board_people), 'Board members'],
      [fmt(s.on_2plus_current_boards), 'On 2+ current boards (not HOAs)'], [fmt(s.official_name_matches), 'Match an official by name'], [fmt(rv.unreviewed || 0), 'Not yet reviewed'],
      [fmt(rv.confirmed || 0), 'Confirmed (public)'], [fmt(s.linked_to_donor_businesses), 'Run a business that gave'], [when(r.load.loaded_at).replace(/<[^>]+>/g, ''), 'Last loaded']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('') : '<div class="banner"><div>Not loaded yet. The Sync database workflow loads it after the next push to main.</div></div>';
    $('#bd-officials tbody').innerHTML = r.officials.map(m => `<tr>${bdBulk.cell(m)}
      <td><b>${esc(m.official_name)}</b><div class="muted small">${esc((m.official_roles || []).slice(0, 2).join('; '))}</div></td>
      <td><a href="#" data-board="${esc(m.board_key)}">${owNm(m.display_name)}</a></td>
      <td class="small">${m.boards.map(b => `<div><a href="#" data-np="${esc(b.nonprofit_id)}">${owNm(b.nonprofit)}</a> <span class="muted">${esc(b.titles || '')} · ${esc(bdYears(b))} · ${esc(bdSrc(b.sources))}${b.current ? '' : ' · past'}</span></div>`).join('')}</td>
      <td class="num">${fmt(m.same_name_people)}</td>
      <td><select class="sel" data-bdreview="${esc(m.board_key)}" data-official="${esc(m.official_id)}" aria-label="Review">${Object.entries(OW_REV).map(([k, l]) => `<option value="${k}"${k === m.review_status ? ' selected' : ''}>${l}</option>`).join('')}</select>${m.reviewed_by ? `<div class="muted small">${esc(m.reviewed_by)}</div>` : ''}</td></tr>`).join('')
      || '<tr><td colspan="6" class="empty">No matches.</td></tr>';
    bdBulk.set(r.officials);
    const [il, dn] = await Promise.all([api('boards_interlocks').catch(() => []), api('boards_donors').catch(() => [])]);
    $('#bd-interlocks tbody').innerHTML = il.slice(0, 100).map(p => `<tr><td><a href="#" data-board="${esc(p.board_key)}">${owNm(p.display_name)}</a></td><td class="num">${fmt(p.n_current_civic)}${p.n_current > p.n_current_civic ? `<div class="muted small">+${fmt(p.n_current - p.n_current_civic)} HOA</div>` : ''}</td>
      <td class="small">${bdBoards(p.boards)}</td><td class="small">${p.official_name ? 'Name matches ' + esc(p.official_name) + '<br>' : ''}${p.n_donor_businesses ? fmt(p.n_donor_businesses) + ' donor business(es)' : ''}</td></tr>`).join('')
      || '<tr><td colspan="4" class="empty">None.</td></tr>';
    $('#bd-donors tbody').innerHTML = dn.map(p => `<tr><td><a href="#" data-board="${esc(p.board_key)}">${owNm(p.display_name)}</a>${p.official_name ? `<div class="muted small">Name matches ${esc(p.official_name)}</div>` : ''}</td>
      <td class="small">${bdBoards(p.boards)}</td>
      <td class="small">${(p.businesses || []).map(b => `<div><a href="#" data-doc="${esc(b.doc_number)}">${owNm(b.name)}</a> <span class="pill">${b.via === 'same_person' ? 'same person' : 'same name'}</span> <span class="muted">${owUsd(b.gifts_total)} to ${esc((b.candidates || []).join(', '))}</span></div>`).join('')}</td>
      <td class="num"><b>${owUsd(p.donor_gifts_total)}</b></td></tr>`).join('') || '<tr><td colspan="4" class="empty">None.</td></tr>';
  }
  async function bdDetail(kind, id) {
    const box = $('#bd-detail'); box.innerHTML = '<p class="muted small">Loading…</p>';
    const pay = n => n ? owUsd(n) : '<span class="muted">—</span>';
    try {
      if (kind === 'person') {
        const r = await api('boards_person', {params: {key: id}}); const p = r.person;
        box.innerHTML = `<h3 class="h2">${owNm(p.display_name)}</h3><p class="muted small">${fmt(p.n_current)} current boards, ${fmt(p.n_nonprofits)} in all${p.official_name ? ` · name matches <b>${esc(p.official_name)}</b>` : ''} · ${fmt(p.same_name_people)} Sunbiz people share this name</p>
          <div class="tw"><table class="at" data-tt="off"><thead><tr><th>Nonprofit</th><th>Title</th><th>Year</th><th>Source</th><th class="num">Hours</th><th class="num">Pay</th></tr></thead><tbody>${r.seats.map(s => `<tr><td><a href="#" data-np="${esc(s.nonprofit_id)}">${owNm(s.nonprofit_name)}</a>${s.board ? '' : ' <span class="pill">staff or former</span>'}</td><td class="small">${esc(s.title || '')}</td><td>${esc(s.tax_year || '')}</td><td class="small">${s.source_url ? `<a href="${esc(s.source_url)}" target="_blank" rel="noopener">${esc(bdSrc(s.source))}</a>` : esc(bdSrc(s.source))}</td><td class="num">${s.hours == null ? '' : fmt(s.hours)}</td><td class="num">${pay(s.compensation)}</td></tr>`).join('')}</tbody></table></div>
          ${(p.businesses || []).length ? `<div class="tw" style="margin-top:10px"><table class="at" data-tt="off"><thead><tr><th>Business (Sunbiz name match)</th><th>Status</th><th>Link</th><th class="num">Campaign gifts</th><th>To</th></tr></thead><tbody>${p.businesses.map(b => `<tr><td><a href="#" data-doc="${esc(b.doc_number)}">${owNm(b.name)}</a></td><td>${b.status === 'A' ? 'Active' : 'Inactive'}</td><td class="small">${b.via === 'same_person' ? 'Same person' : 'Same name'}</td><td class="num">${pay(b.gifts_total)}</td><td class="small">${esc((b.candidates || []).join(', '))}</td></tr>`).join('')}</tbody></table></div>` : ''}`;
      } else {
        const r = await api('boards_nonprofit', {params: {id}});
        box.innerHTML = `<h3 class="h2">${owNm(r.name)}</h3><p class="muted small">${r.ein ? 'EIN ' + esc(r.ein) + ' · <a href="https://projects.propublica.org/nonprofits/organizations/' + esc(r.ein) + '" target="_blank" rel="noopener">990s on ProPublica</a>' : 'State corporate filing only'}</p>
          <div class="tw"><table class="at" data-tt="off"><thead><tr><th>Person</th><th>Title</th><th>Year</th><th>Source</th><th class="num">Pay</th><th>Also</th></tr></thead><tbody>${r.seats.map(s => `<tr${s.current ? '' : ' class="muted"'}><td><a href="#" data-board="${esc(s.board_key)}">${owNm(s.display_name)}</a>${s.board ? '' : ' <span class="pill">staff or former</span>'}</td><td class="small">${esc(s.title || '')}</td><td>${esc(s.tax_year || '')}</td><td class="small">${s.source_url ? `<a href="${esc(s.source_url)}" target="_blank" rel="noopener">${esc(bdSrc(s.source))}</a>` : esc(bdSrc(s.source))}</td><td class="num">${pay(s.compensation)}</td><td class="small">${s.n_current > 1 ? fmt(s.n_current) + ' boards' : ''}${s.official_name ? ' · matches ' + esc(s.official_name) : ''}${s.n_donor_businesses ? ' · donor business' : ''}</td></tr>`).join('')}</tbody></table></div>`;
      }
      box.scrollIntoView({behavior: 'smooth', block: 'start'});
    } catch (err) { box.innerHTML = `<div class="banner bad"><div>${esc(err.message)}</div></div>`; }
  }
  $('#tab-boards').addEventListener('click', e => {
    const a = e.target.closest('[data-board],[data-np],[data-doc]'); if (!a) return;
    e.preventDefault();
    if (a.dataset.doc) { tab('owners'); owDetail('entity', a.dataset.doc); return; }
    a.dataset.board ? bdDetail('person', a.dataset.board) : bdDetail('nonprofit', a.dataset.np);
  });
  $('#bd-officials').addEventListener('change', async e => {
    const s = e.target.closest('[data-bdreview]'); if (!s) return;
    s.disabled = true;
    try { await api('boards_review', {method: 'POST', body: {board_key: s.dataset.bdreview, official_id: s.dataset.official, status: s.value}}); bdBulk.mark(s.dataset.bdreview + '|' + s.dataset.official, s.value); }
    catch (err) { alert(err.message); }
    s.disabled = false;
  });
  $('#bd-status').addEventListener('change', loadBoards);
  let bdTimer;
  $('#bd-q').addEventListener('input', () => {
    clearTimeout(bdTimer);
    bdTimer = setTimeout(async () => {
      const q = $('#bd-q').value.trim(); const box = $('#bd-results');
      if (q.length < 3) { box.innerHTML = ''; return; }
      try {
        const r = await api('boards_search', {params: {q}});
        box.innerHTML = `<div class="tw"><table class="at" data-tt="off"><tbody>${r.people.map(p => `<tr><td>Person</td><td><a href="#" data-board="${esc(p.board_key)}">${owNm(p.display_name)}</a></td><td class="small muted">${p.official_name ? 'matches ' + esc(p.official_name) : ''}</td><td class="num small">${fmt(p.n_current)} current boards</td></tr>`).join('')}${r.nonprofits.map(n => `<tr><td>Nonprofit</td><td><a href="#" data-np="${esc(n.nonprofit_id)}">${owNm(n.nonprofit_name)}</a></td><td class="small muted">${esc(n.ein || '')}</td><td class="num small">${n.people ? fmt(n.people) + ' people listed' : ''}</td></tr>`).join('')}</tbody></table></div>`
          + (r.people.length || r.nonprofits.length ? '' : '<p class="muted small">No matches.</p>');
      } catch (err) { box.innerHTML = `<p class="small">${esc(err.message)}</p>`; }
    }, 300);
  });
  // ---------- business ties: officials matched to Sunbiz (private careers schema, api/_careers.js) ----------
  const BT_LINK = {shared_business: 'Same business as another official', own_business_gift: 'Business gave to a campaign',
    partner_business_gift: 'Donor shares an officer with their business', public_payee: 'Business paid by a government'};
  const btBulk = bulkReview({table: '#bt-table', noun: ['match', 'matches'], action: 'careers_review', statuses: REVIEW_BTNS,
    key: m => m.person_id + '|' + m.person_key, body: list => ({pairs: list.map(m => ({person_id: m.person_id, person_key: m.person_key}))}),
    confident: m => m.confidence === 'high', confidentLabel: 'High confidence',
    confidentHelp: 'High confidence: the name match scored high (county address, city matches the office, same first name, no corporate-board flags).',
    warn: st => st === 'confirmed' ? 'Confirming publishes each official’s businesses and links on /connections/business-ties.' : 'Anything not confirmed is taken off the public page.',
    published: n => `${fmt(n)} public rows rewritten.`, reload: () => loadTies()});
  async function loadTies() {
    let r;
    try { r = await api('careers', {params: {status: $('#bt-status').value, confidence: $('#bt-confidence').value, q: $('#bt-q').value.trim()}}); }
    catch (e) { $('#bt-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load business ties.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const s = (r.load && r.load.summary) || {};
    const n = st => (r.review || []).filter(x => x.review_status === st).reduce((a, x) => a + x.n, 0);
    $('#bt-tiles').innerHTML = r.load ? [[fmt(s.officials_with_a_match), 'Officials with a name match'], [fmt(r.load.matches), 'Matches'],
      [fmt(n('unreviewed')), 'Not yet reviewed'], [fmt(n('confirmed')), 'Confirmed'], [fmt(r.published.businesses), 'Businesses published'],
      [fmt(r.published.links), 'Links published'], [when(r.load.loaded_at).replace(/<[^>]+>/g, ''), 'Last loaded']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('') : '<div class="banner"><div>Not loaded yet. The Sync database workflow loads it after the next push to main.</div></div>';
    $('#bt-table tbody').innerHTML = r.matches.map(m => `<tr>${btBulk.cell(m)}
      <td><b>${esc(m.official_name)}</b><div class="muted small">${esc(m.label || '')}</div></td>
      <td class="small"><a href="#" data-person="${esc(m.person_key)}">${owNm(m.sunbiz_name)}</a> <span class="muted">${esc(m.sunbiz_city || '')}</span>
        <div><span class="pill">${esc(m.confidence)} (${m.score})</span>${m.corporate_officer ? ' <span class="pill">corporate officer</span>' : ''}${m.agent_service ? ' <span class="pill">agent service</span>' : ''}</div>
        <div class="muted">${(m.reasons || []).map(esc).join('; ')}</div></td>
      <td class="small">${m.businesses.map(b => `<div><a href="${owSunbiz(b.name, b.doc_number)}" target="_blank" rel="noopener">${owNm(b.name)}</a> <span class="muted">${esc(b.titles || '')}${b.file_date ? ', filed ' + esc(String(b.file_date).slice(0, 4)) : ''}</span>${b.status === 'I' ? ' <span class="pill">Inactive</span>' : ''}${b.nonprofit ? ' <span class="pill">nonprofit</span>' : ''}</div>`).join('')}</td>
      <td class="small">${m.links.map(l => `<div>${l.own_government ? '<b>' : ''}${esc(BT_LINK[l.link_type] || l.link_type)}${l.own_government ? ' (own government)</b>' : ''}: <span class="muted">${esc(l.detail || '')}${l.amount != null ? ', ' + owUsd(l.amount) : ''}</span></div>`).join('') || '<span class="muted">None</span>'}</td>
      <td><select class="sel" data-bt-id="${esc(m.person_id)}" data-bt-key="${esc(m.person_key)}" aria-label="Review">${Object.entries(OW_REV).map(([k, v]) => `<option value="${k}"${k === m.review_status ? ' selected' : ''}>${v}</option>`).join('')}</select>
        ${m.reviewed_by ? `<div class="muted small">${esc(m.reviewed_by)}</div>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">No matches with these filters.</td></tr>';
    btBulk.set(r.matches);
  }
  $('#bt-table').addEventListener('change', async e => {
    const s = e.target.closest('[data-bt-id]'); if (!s) return;
    s.disabled = true;
    try { await api('careers_review', {method: 'POST', body: {person_id: s.dataset.btId, person_key: s.dataset.btKey, status: s.value}}); btBulk.mark(s.dataset.btId + '|' + s.dataset.btKey, s.value); }
    catch (err) { alert(err.message); }
    s.disabled = false;
  });
  $('#bt-table').addEventListener('click', e => {
    const a = e.target.closest('[data-person]'); if (!a) return;
    e.preventDefault(); tab('owners'); owDetail('person', a.dataset.person);
  });
  ['#bt-status', '#bt-confidence'].forEach(s => $(s).addEventListener('change', loadTies));
  let btTimer;
  $('#bt-q').addEventListener('input', () => { clearTimeout(btTimer); btTimer = setTimeout(loadTies, 300); });

  // ---------- name matches: look-alike business names (api/_names.js) ----------
  const NM_REV = {unreviewed: 'Unreviewed', confirmed: 'One company', rejected: 'Keep apart'};
  const nmSide = s => `<b>${owNm((s.names || [])[0] || s.key)}</b>${(s.names || []).length > 1 ? `<div class="muted small">also ${(s.names || []).slice(1).map(owNm).join('; ')}</div>` : ''}
    <div class="muted small">${[s.vendor_id ? `<a href="/profile/vendor/${esc(s.vendor_id)}" target="_blank" rel="noopener">vendor</a>` : '',
      s.records ? Object.entries(s.records).map(([k, n]) => `${fmt(n)} ${esc(k.replace('_', ' '))}`).join(', ') : '',
      s.gifts ? `${fmt(s.gifts)} gift${s.gifts === 1 ? '' : 's'}, ${owUsd(s.given)}` : ''].filter(Boolean).join(' · ')}</div>`;
  const nmBulk = bulkReview({table: '#nm-table', noun: ['pair', 'pairs'], action: 'names_review',
    statuses: [['confirmed', 'One company', 'primary'], ['rejected', 'Keep apart', 'danger'], ['unreviewed', 'Back to unreviewed']],
    key: r => r.a_key + '|' + r.b_key,
    body: list => ({items: list.map(r => ({a_key: r.a_key, b_key: r.b_key, a_name: (r.a.names || [])[0], b_name: (r.b.names || [])[0]}))}),
    confident: r => r.reason === 'spelling' && (r.a.gifts || r.b.gifts) && !(r.a.vendor_id && r.b.vendor_id), confidentLabel: 'Spelling slips',
    confidentHelp: 'Spelling slips: one or two letters apart, at least one name from a campaign filing, and not two separate vendors. Still read each one.',
    warn: st => st === 'confirmed' ? 'The names are joined everywhere after the next daily refresh.' : '', reload: () => loadNames()});
  async function loadNames() {
    let r;
    try { r = await api('names', {params: {status: $('#nm-status').value, reason: $('#nm-reason').value, q: $('#nm-q').value.trim()}}); }
    catch (e) { $('#nm-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load name matches.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const c = r.counts;
    $('#nm-tiles').innerHTML = [[fmt(c.pairs), 'Look-alike pairs in the last build'], [fmt(c.unreviewed), 'Not yet reviewed'], [fmt(c.confirmed), 'One company'], [fmt(c.rejected), 'Kept apart']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    $('#nm-table tbody').innerHTML = r.rows.map(m => `<tr>${nmBulk.cell(m)}<td class="small">${nmSide(m.a)}</td><td class="small">${nmSide(m.b)}</td>
      <td class="small">${esc(m.reason_label || '')}</td>
      <td><select class="sel" data-nm-a="${esc(m.a_key)}" data-nm-b="${esc(m.b_key)}" aria-label="Review">${Object.entries(NM_REV).map(([k, v]) => `<option value="${k}"${k === m.review_status ? ' selected' : ''}>${v}</option>`).join('')}</select>
        ${m.reviewed_by ? `<div class="muted small">${esc(m.reviewed_by)}</div>` : ''}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">No pairs with these filters.</td></tr>';
    if (r.total > r.rows.length) $('#nm-table tbody').insertAdjacentHTML('beforeend', `<tr><td colspan="5" class="empty">Showing ${fmt(r.rows.length)} of ${fmt(r.total)}. Narrow the list with the filters.</td></tr>`);
    nmBulk.set(r.rows);
  }
  $('#nm-table').addEventListener('change', async e => {
    const s = e.target.closest('[data-nm-a]'); if (!s) return;
    s.disabled = true;
    const row = s.closest('tr');
    try { await api('names_review', {method: 'POST', body: {a_key: s.dataset.nmA, b_key: s.dataset.nmB, status: s.value,
      a_name: row.cells[1].querySelector('b').textContent, b_name: row.cells[2].querySelector('b').textContent}}); nmBulk.mark(s.dataset.nmA + '|' + s.dataset.nmB, s.value); }
    catch (err) { alert(err.message); }
    s.disabled = false;
  });
  ['#nm-status', '#nm-reason'].forEach(s => $(s).addEventListener('change', loadNames));
  let nmTimer;
  $('#nm-q').addEventListener('input', () => { clearTimeout(nmTimer); nmTimer = setTimeout(loadNames, 300); });

  // ---------- realtor agents (realtor.agents, api/_realtor.js) ----------
  const RA_ST = {active: 'Active', pending: 'Pending', paused: 'Paused'};
  const raDay = v => v ? new Date(v).toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}) : '—';
  async function loadRealtors() {
    let r;
    try { r = await api('realtors'); }
    catch (e) { $('#ra-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load agents.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    const c = r.counts;
    $('#ra-tiles').innerHTML = [[r.signup === 'invite' ? 'Invite only' : 'Open', 'Sign-up'], [fmt(c.active), 'Active'], [fmt(c.pending), 'Waiting for you'], [fmt(c.paused), 'Paused']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    $('#ra-table tbody').innerHTML = r.rows.map(a => `<tr><td><b>${esc(a.agent_name || a.email)}</b>${a.agent_name ? `<div class="muted small">${esc(a.email)}</div>` : ''}</td>
      <td class="small">${esc(a.brokerage || '—')}</td><td class="small">${raDay(a.created_at)}</td><td class="small">${raDay(a.last_login_at)}</td><td class="small">${fmt(a.reports_run || 0)}</td>
      <td><select class="sel" data-ra="${esc(a.email)}" aria-label="Access">${Object.entries(RA_ST).map(([k, v]) => `<option value="${k}"${k === a.status ? ' selected' : ''}>${v}</option>`).join('')}</select></td></tr>`).join('')
      || '<tr><td colspan="6" class="empty">No agents yet.</td></tr>';
  }
  $('#ra-table').addEventListener('change', async e => {
    const s = e.target.closest('[data-ra]'); if (!s) return;
    s.disabled = true;
    try { await api('realtor_set', {method: 'POST', body: {email: s.dataset.ra, status: s.value}}); } catch (err) { alert(err.message); }
    s.disabled = false; loadRealtors();
  });
  $('#ra-add').addEventListener('click', async () => {
    const v = $('#ra-email').value.trim(); if (!v) return;
    try { await api('realtor_set', {method: 'POST', body: {email: v, status: 'active'}}); $('#ra-email').value = ''; loadRealtors(); } catch (err) { alert(err.message); }
  });

  // ---------- votes from minutes (agendas.motions, api/_minutes.js) ----------
  const MV_BOARD = {county: 'County Commission', schools: 'School Board', pc: 'Panama City', 'pc-cra': 'Panama City CRA', pcb: 'Panama City Beach',
    lh: 'Lynn Haven', 'lh-cra': 'Lynn Haven CRA', cw: 'Callaway', 'cw-cra': 'Callaway CRA', sp: 'Springfield', parker: 'Parker', mb: 'Mexico Beach'};
  const MV_REV = {unreviewed: 'Unreviewed', approved: 'Approved', rejected: 'Rejected'};
  const MV_VOTE = {yes: 'Y', no: 'N', abstain: 'Abst.', absent: 'Abs.'};
  const mvBulk = bulkReview({table: '#mv-table', noun: ['motion', 'motions'], action: 'minutes_review',
    statuses: [['approved', 'Approve', 'primary'], ['rejected', 'Reject', 'danger'], ['unreviewed', 'Back to unreviewed']],
    key: m => String(m.id), body: list => ({items: list.map(m => ({id: m.id}))}),
    warn: st => st === 'approved' ? 'Approved motions go on the site with the next daily refresh.' : st === 'rejected' ? 'Rejected motions stay off the site.' : '',
    reload: () => loadMinutes()});
  // ---------- import progress (api/_minutes.js progress -> site/progress.js, shared with /data-sources) ----------
  async function loadProgress() {
    const el = $('#ip-admin');
    let r;
    try { r = await api('import_progress'); }
    catch (e) { el.innerHTML = `<div class="banner bad"><div><b>Couldn’t load progress.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    if (window.BCProgress) BCProgress.render(el, r, {admin: true});
    else el.textContent = 'The progress script didn’t load.';
  }
  let mvFilled = false;
  async function loadMinutes() {
    let r;
    try { r = await api('minutes', {params: {queue: $('#mv-queue').value, board: $('#mv-board').value, year: $('#mv-year').value, status: $('#mv-status').value, q: $('#mv-q').value.trim()}}); }
    catch (e) { $('#mv-tiles').innerHTML = `<div class="banner bad"><div><b>Couldn’t load votes from minutes.</b><div class="small muted">${esc(e.message)}</div></div></div>`; return; }
    if (!r.installed) { $('#mv-tiles').innerHTML = '<div class="banner"><div>Not set up yet. The next database sync applies migration 0055; then run the Read minutes workflow.</div></div>'; return; }
    const t = r.totals;
    $('#mv-tiles').innerHTML = [[fmt(t.files), 'Minutes files captured'], [fmt(t.read), 'Files read'], [fmt(t.waiting), 'Waiting on a batch'],
      [fmt(t.unread), 'Couldn’t read'], [fmt(t.motions), 'Motions'], [fmt(t.passed), 'Passed checks'], [fmt(t.flagged), 'Flagged, unreviewed'],
      [fmt(t.sample), 'Spot checks waiting'], ['$' + Number(t.cost || 0).toFixed(2), 'Spent so far'], ['$' + Number(t.in_flight || 0).toFixed(2), 'In flight (estimate)']]
      .map(([v, l]) => `<div class="tile"><b>${v}</b><span>${l}</span></div>`).join('');
    if (!mvFilled) {
      $('#mv-board').innerHTML += Object.entries(MV_BOARD).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
      const y = new Date().getFullYear();
      for (let i = y; i >= 2016; i--) $('#mv-year').innerHTML += `<option>${i}</option>`;
      mvFilled = true;
    }
    $('#mv-checks').innerHTML = (r.checks || []).length ? 'Waiting by check: ' + r.checks.map(c => `${esc(r.check_labels[c.code] || c.code)} (${fmt(c.n)})`).join(' · ') : '';
    const votes = m => Object.entries(m.votes || {}).map(([n, v]) => `<div><span class="pill">${MV_VOTE[v] || esc(v)}</span> ${esc(n)}</div>`).join('');
    $('#mv-table tbody').innerHTML = r.motions.map(m => `<tr>${mvBulk.cell(m)}
      <td class="small"><b>${esc(MV_BOARD[m.board] || m.board)}</b><div>${esc(m.meeting_date ? String(m.meeting_date).slice(0, 10) : 'No date')}${m.meeting_type && m.meeting_type !== 'regular' ? ' · ' + esc(m.meeting_type.replace('_', ' ')) : ''}</div>
        ${m.version_id ? `<button type="button" class="linkish" data-mv-ver="${m.version_id}">Open minutes${m.page ? ', page ' + m.page : ''}</button>` : ''}</td>
      <td class="small"><b>${esc(m.summary || '')}</b>${m.item_title ? `<div class="muted">${esc([m.item_number, m.item_title].filter(Boolean).join(' '))}</div>` : ''}
        <div>${esc((m.motion || '').slice(0, 400))}</div>
        <div class="muted">${[m.mover && 'Moved: ' + esc(m.mover), m.seconder && 'Second: ' + esc(m.seconder), m.consent ? 'Consent agenda' : '', m.amount != null ? owUsd(m.amount) : ''].filter(Boolean).join(' · ')}</div></td>
      <td class="small"><div><b>${esc(m.outcome || '')}</b> ${esc(m.tally || '')}${m.tally_printed && m.tally_printed !== m.tally ? ` <span class="muted">(printed ${esc(m.tally_printed)})</span>` : ''}</div>
        <div class="muted">${esc((m.vote_method || '').replace(/_/g, ' '))}</div>${votes(m)}</td>
      <td class="small">${(m.checks || []).map(c => `<div>${esc(r.check_labels[c] || c)}</div>`).join('') || (m.sampled ? '<span class="pill">spot check</span>' : '<span class="muted">Passed</span>')}
        ${(m.unmatched || []).length ? `<div class="muted">Unmatched: ${m.unmatched.map(esc).join(', ')}</div>` : ''}</td>
      <td><select class="sel" data-mv-id="${m.id}" aria-label="Review">${Object.entries(MV_REV).map(([k, v]) => `<option value="${k}"${k === m.review_status ? ' selected' : ''}>${v}</option>`).join('')}</select>
        ${m.reviewed_by ? `<div class="muted small">${esc(m.reviewed_by)}</div>` : ''}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">No motions with these filters.</td></tr>';
    mvBulk.set(r.motions);
    const byBoard = {};
    (r.coverage || []).forEach(c => { (byBoard[c.board] = byBoard[c.board] || []).push(c); });
    $('#mv-coverage tbody').innerHTML = Object.entries(byBoard).map(([b, rows]) => `<tr><td>${esc(MV_BOARD[b] || b)}</td>
      <td class="num">${fmt(rows.reduce((n, x) => n + x.files, 0))}</td><td class="num">${fmt(rows.reduce((n, x) => n + x.read, 0))}</td>
      <td class="num">${fmt(rows.reduce((n, x) => n + x.motions, 0))}</td>
      <td class="small">${rows.map(x => `${x.yr}: ${x.read}/${x.files}`).join(' · ')}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">No minutes captured yet.</td></tr>';
    $('#mv-batches tbody').innerHTML = (r.batches || []).map(b => `<tr><td class="small">${esc(b.batch_id)}</td><td>${esc(b.status)}</td><td class="num">${fmt(b.requests)}</td>
      <td class="num">${b.est != null ? '$' + b.est.toFixed(2) : '—'}</td><td class="num">${b.cost != null ? '$' + b.cost.toFixed(2) : '—'}</td>
      <td class="small">${when(b.submitted_at)}</td><td class="small">${b.collected_at ? when(b.collected_at) : ''}</td></tr>`).join('') || '<tr><td colspan="7" class="empty">No batches yet.</td></tr>';
  }
  $('#mv-table').addEventListener('change', async e => {
    const s = e.target.closest('[data-mv-id]'); if (!s) return;
    s.disabled = true;
    try { await api('minutes_review', {method: 'POST', body: {id: Number(s.dataset.mvId), status: s.value}}); mvBulk.mark(s.dataset.mvId, s.value); }
    catch (err) { alert(err.message); }
    s.disabled = false;
  });
  $('#mv-table').addEventListener('click', async e => {
    const b = e.target.closest('[data-mv-ver]'); if (!b) return;
    const w = window.open('', '_blank');
    try { const j = await api('agenda_file', {params: {id: b.dataset.mvVer}}); if (j.url) w.location = j.url; else { w.close(); alert('This file wasn’t stored and has no public link.'); } }
    catch (err) { w.close(); alert(err.message); }
  });
  ['#mv-queue', '#mv-board', '#mv-year', '#mv-status'].forEach(s => $(s).addEventListener('change', loadMinutes));
  let mvTimer;
  $('#mv-q').addEventListener('input', () => { clearTimeout(mvTimer); mvTimer = setTimeout(loadMinutes, 300); });

  // ---------- start ----------
  (async () => {
    if (new URLSearchParams(location.search).get('signin') === 'expired') $('#signin-msg').textContent = 'That sign-in link expired or was already used. Send a new one.';
    let me;
    try { me = await api('me'); } catch (e) { showSignin(); return; }
    $('#who').textContent = me.email; $('#signin').hidden = true; $('#app').hidden = false;
    // Keys fill the key pickers on Usage; a failure there must not stop the page from opening.
    try { await loadKeys(); } catch (e) { oops('Couldn’t load API keys: ' + e.message); }
    tab(location.hash.slice(1));
    if (location.hash !== '#todo') api('summary').then(r => markMenu(r.counts || {})).catch(() => {});
  })();
})();

/* Copied from site/site_helpers.js (the admin page does not load site.js). */
/* Phone tables: no sideways scrolling. Each body cell gets data-label (its column heading) and the table gets
   class "stk"; site.css turns rows into cards under 640px. Opt out with <table data-stack="off">. */
(() => {
  const colsOf = tr => { const out = []; for (const c of tr.cells) { const n = Math.max(1, c.colSpan || 1); out.push(c); for (let i = 1; i < n; i++) out.push(null); } return out; };
  const label = t => {
    if (t.dataset.stack === 'off' || t.closest('[data-stack="off"]')) return;
    const h = t.tHead && t.tHead.rows.length ? t.tHead.rows[t.tHead.rows.length - 1] : null;
    const names = h ? colsOf(h).map(c => c ? c.textContent.replace(/\s+/g, ' ').trim() : '') : (t.dataset.cols || '').split('|');
    let n = names.length; for (const b of t.tBodies) for (const r of b.rows) n = Math.max(n, colsOf(r).length);
    if (n < 3) { t.classList.add('stk2'); return; }   // two columns fit a phone once they may wrap
    t.classList.add('stk');
    for (const part of [...t.tBodies, t.tFoot].filter(Boolean)) for (const tr of part.rows) {
      const cs = colsOf(tr);
      if (tr.cells.length === 1 && (tr.cells[0].colSpan || 1) > 1) { tr.classList.add('stk-span'); continue; }
      cs.forEach((c, i) => { if (c && !c.hasAttribute('data-label') && names[i]) c.setAttribute('data-label', names[i]); });
    }
  };
  let q = false;
  const run = () => { q = false; document.querySelectorAll('table').forEach(label); };
  const go = () => { run(); new MutationObserver(ms => { if (q) return; if (ms.some(m => m.addedNodes.length)) { q = true; requestAnimationFrame(run); } }).observe(document.body, {childList: true, subtree: true}); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();

/* Desktop tables: every row on one line and no sideways scrolling. Short columns keep their full width; long text
   columns share the room left and end in "…" (hover shows the full text). A name with a second line (a <div>
   under it) runs on the same line after a "·". Phones get the cards above instead. Opt out with data-fit="off". */
(() => {
  const ACT = 'button,input,select,textarea', FREE = 'details,pre,iframe';
  const colsOf = tr => { const out = []; for (const c of tr.cells) { const n = Math.max(1, c.colSpan || 1); out.push(c); for (let i = 1; i < n; i++) out.push(null); } return out; };
  const fit = t => {
    if (t.dataset.fit === 'off' || !t.classList.contains('at')) return;
    t.classList.add('fit'); t.classList.remove('fixed');
    const span = tr => tr.cells.length === 1 && (tr.cells[0].colSpan || 1) > 1;
    const rows = [...t.rows].filter(tr => { if (span(tr)) { tr.cells[0].classList.add('fl-wrap'); return false; } return true; });
    const cols = [];   // per column: {cells, len, act, free}
    for (const tr of rows) colsOf(tr).forEach((c, i) => {
      if (!c) return;
      const col = cols[i] || (cols[i] = {cells: [], len: 0, act: false, free: false});
      col.cells.push(c);
      c.classList.remove('fl'); c.style.width = ''; c.style.maxWidth = '';
      if (c.tagName !== 'TD') return;
      if (c.querySelector(ACT)) col.act = true;
      if (c.querySelector(FREE)) col.free = true;
      let prev = false;
      for (const n of c.childNodes) {
        if (n.nodeType === 1 && n.tagName === 'DIV' && !n.querySelector(ACT)) { n.classList.add('fl-in'); n.classList.toggle('fl-sep', prev); }
        if (n.nodeType === 1 || (n.nodeType === 3 && n.textContent.trim())) prev = true;
      }
      col.len = Math.max(col.len, c.textContent.replace(/\s+/g, ' ').trim().length);
    });
    // Widths come from one row with a cell per column (the header row when there is one).
    const head = rows.find(tr => colsOf(tr).every(Boolean) && colsOf(tr).length === cols.length);
    const box = t.parentElement;
    if (!head || !box || !t.offsetParent || cols.some(c => !c)) return;
    const avail = box.clientWidth - 2, cells = colsOf(head);
    if (t.offsetWidth <= avail + 1) return;   // fits on one line already
    // A column's natural width is its widest body cell; headings may end in "…" before data does.
    const pad = c => { const s = getComputedStyle(c); return parseFloat(s.paddingLeft) + parseFloat(s.paddingRight); };
    const rg = document.createRange(), inner = c => { rg.selectNodeContents(c); return rg.getBoundingClientRect().width + pad(c) + 2; };
    const shown = c => c.getClientRects().length > 0;   // a column hidden at this width takes no room
    const nat = cols.map((col, i) => shown(cells[i]) ? Math.max(48, ...col.cells.filter(c => c.tagName === 'TD').map(inner)) : 0);
    // Too wide: the widest text columns shrink to one shared cap (short ones keep their width); buttons and
    // drop-downs never shrink. The cap is the largest width at which everything fits.
    const can = cols.map((c, i) => i).filter(i => !cols[i].act && !cols[i].free);
    if (!can.length) return;
    const room = avail - nat.reduce((a, w, i) => a + (can.includes(i) ? 0 : w), 0);
    const used = cap => can.reduce((a, i) => a + Math.min(nat[i], cap), 0);
    let lo = 0, hi = Math.max(...can.map(i => nat[i]));
    for (let k = 0; k < 24; k++) { const m = (lo + hi) / 2; if (used(m) <= room) lo = m; else hi = m; }
    const cap = Math.max(lo, 40), flex = new Set(can.filter(i => nat[i] > cap));
    const w = nat.map((n, i) => flex.has(i) ? Math.floor(cap) : Math.ceil(n));
    // site.css sets border-box, so a cell's width includes its padding.
    cells.forEach((c, i) => { c.style.width = Math.max(0, w[i] - (getComputedStyle(c).boxSizing === 'border-box' ? 0 : pad(c))) + 'px'; });
    t.classList.add('fixed');
    flex.forEach(i => cols[i].cells.forEach(c => { c.classList.add('fl'); c.style.minWidth = ''; }));
  };
  let q = false;
  const run = () => { q = false; if (innerWidth > 640) document.querySelectorAll('.cp-main table').forEach(fit); };
  const soon = () => { if (!q) { q = true; requestAnimationFrame(run); } };
  const go = () => {
    run();
    new MutationObserver(ms => { if (ms.some(m => m.addedNodes.length)) soon(); }).observe(document.body, {childList: true, subtree: true});
    document.addEventListener('cp:tab', soon); addEventListener('resize', soon);
    document.addEventListener('mouseover', e => {
      const c = e.target.closest && e.target.closest('td.fl');
      if (c && !c.title && c.scrollWidth > c.clientWidth) c.title = c.textContent.replace(/\s+/g, ' ').trim();
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', go); else go();
})();
