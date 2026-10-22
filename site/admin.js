// BayCounty.me admin page. Talks only to /api/admin.
(() => {
  const $ = s => document.querySelector(s);
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

  // ---------- tabs ----------
  const loaders = {keys: loadKeys, analytics: loadStats, logs: () => loadLogs(true), settings: loadSettings, ingestion: loadIngestion, agendas: loadAgendas, sent: loadSent, emails: loadEmails};
  function tab(name) {
    document.querySelectorAll('[role=tab][data-tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    document.querySelectorAll('[role=tabpanel]').forEach(p => { p.hidden = p.id !== 'tab-' + name; });
    history.replaceState(null, '', '#' + name);
    loaders[name]();
  }
  document.querySelectorAll('[role=tab][data-tab]').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));

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
  $('#kd-logs').addEventListener('click', () => { const id = editing.id; dlg.close(); tab('logs'); $('#lg-scope').value = id; loadLogs(true); });

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
  async function loadSettings() {
    loadBlocks().catch(() => {});
    const [s, a] = await Promise.all([api('settings'), api('audit')]);
    const f = $('#settings-form');
    for (const k of ['anon_per_minute', 'anon_per_day', 'default_per_minute', 'default_per_day']) f[k].value = s.settings[k] ?? '';
    f.require_key.checked = !!s.settings.require_key;
    const name = id => (KEYS.find(k => k.id === id) || {}).name;
    const WHAT = {email_test: 'Sent a test email', create_key: 'Created a key', update_key: 'Changed a key', rotate_key: 'Replaced a key', update_settings: 'Changed settings', block_ip: 'Blocked an address', unblock_ip: 'Removed a block', login: 'Signed in', login_requested: 'Asked for a sign-in link'};
    $('#audit-table tbody').innerHTML = a.audit.map(x => `<tr><td class="small" style="white-space:nowrap">${stamp(x.at)}</td><td class="small">${esc(x.admin)}</td><td class="small">${esc(WHAT[x.action] || x.action)}${x.key_id && name(x.key_id) ? ': ' + esc(name(x.key_id)) : ''}</td>
      <td class="small muted mono" style="word-break:break-all">${x.detail && x.action !== 'login' ? esc(JSON.stringify(x.detail)) : ''}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">Nothing yet.</td></tr>';
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
      <td class="small ${d.status === 'failed' ? '' : 'muted'}" style="min-width:220px;max-width:360px">${esc(d.notes || '')}</td></tr>`).join('') || '<tr><td colspan="8" class="empty">No loads in the last 60 days.</td></tr>';
    $('#in-fail tbody').innerHTML = r.failures.map(f => `<tr><td class="small" style="white-space:nowrap">${stamp(f.started_at)}</td><td class="mono">${esc(f.dataset)}</td><td class="small">${esc(f.notes || '')}</td>
      <td class="mono small">${f.git_sha ? `<a href="https://github.com/jeremymcs/baycounty-me/commit/${esc(f.git_sha)}" target="_blank" rel="noopener">${esc(String(f.git_sha).slice(0, 7))}</a>` : ''}</td></tr>`).join('') || '<tr><td colspan="4" class="empty">No failures.</td></tr>';
  }
  $('#in-refresh').addEventListener('click', loadIngestion);

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
      <td class="small" style="max-width:200px;word-break:break-word">${esc(n.from_addr)}</td>
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
    $('#se-table tbody').innerHTML = SE.rows.map(r => `<tr><td class="small" style="white-space:nowrap" title="${esc(new Date(r.created_at).toLocaleString())}">${when(r.created_at)}</td>
      <td class="small" style="max-width:220px;word-break:break-word">${esc(r.to.join(', '))}</td><td><b>${esc(r.subject || '(no subject)')}</b></td>
      <td class="small muted" style="max-width:200px;word-break:break-word">${esc(r.from)}</td>
      <td><span class="pill ${esc(r.status)}">${esc(seLabel(r.status))}</span></td>
      <td><button class="btn" type="button" data-se="${esc(r.id)}" style="min-height:28px;padding:0 8px;font-size:.78rem">View</button></td></tr>`).join('')
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

  // ---------- start ----------
  (async () => {
    if (new URLSearchParams(location.search).get('signin') === 'expired') $('#signin-msg').textContent = 'That sign-in link expired or was already used. Send a new one.';
    try {
      const me = await api('me');
      $('#who').textContent = me.email; $('#signin').hidden = true; $('#app').hidden = false;
      await loadKeys();
      const start = location.hash.slice(1);
      tab(loaders[start] ? start : 'keys');
    } catch (e) { showSignin(); }
  })();
})();
