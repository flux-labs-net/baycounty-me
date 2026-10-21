// BayCounty.me admin page. Talks only to /api/admin.
(() => {
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const fmt = n => n == null ? '—' : Number(n).toLocaleString('en-US');
  const lim = n => n == null ? 'No limit' : fmt(n);
  const when = t => {
    if (!t) return '<span class="muted">Never</span>';
    const d = new Date(t), s = (Date.now() - d) / 1000;
    const rel = s < 60 ? 'just now' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' hr ago' : Math.round(s / 86400) + ' days ago';
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
  const loaders = {keys: loadKeys, analytics: loadStats, logs: () => loadLogs(true), settings: loadSettings};
  function tab(name) {
    document.querySelectorAll('[role=tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    document.querySelectorAll('[role=tabpanel]').forEach(p => { p.hidden = p.id !== 'tab-' + name; });
    history.replaceState(null, '', '#' + name);
    loaders[name]();
  }
  document.querySelectorAll('[role=tab]').forEach(b => b.addEventListener('click', () => tab(b.dataset.tab)));

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
    const WHAT = {create_key: 'Created a key', update_key: 'Changed a key', rotate_key: 'Replaced a key', update_settings: 'Changed settings', block_ip: 'Blocked an address', unblock_ip: 'Removed a block', login: 'Signed in', login_requested: 'Asked for a sign-in link'};
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
