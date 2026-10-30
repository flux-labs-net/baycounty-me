// BayCounty.me government workspace (/staff). Talks only to /api/gov.
// Record data is read-only: the only action on it is a flag. Staff edit only what they posted here.
(() => {
  const $ = s => document.querySelector(s);
  const $$ = s => [...document.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const when = s => { if (!s) return '—'; const d = new Date(s); return isNaN(d) ? esc(s) : d.toLocaleString('en-US', {month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit'}); };
  const day = s => { if (!s) return ''; const d = new Date(String(s).length <= 10 ? s + 'T12:00:00' : s); return isNaN(d) ? esc(s) : d.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'}); };
  const ROLE = {viewer: 1, auditor: 1, records: 1, publisher: 2, alert_sender: 3, owner: 4};
  const ACTIONS = {signed_in: 'signed in', notice_posted: 'posted a notice', notice_edited: 'changed a notice', notice_withdrawn: 'withdrew a notice',
    event_posted: 'posted an event', event_edited: 'changed an event', event_withdrawn: 'withdrew an event', job_posted: 'posted a job', job_edited: 'changed a job',
    job_withdrawn: 'withdrew a job', alert_sent: 'sent an alert', alert_drafted: 'saved a countywide alert for a second person to confirm', alert_confirmed: 'confirmed an alert',
    alert_ended: 'ended an alert', alert_cancelled: 'cancelled an alert', data_flagged: 'flagged record data', flag_answered: 'BayCounty.me answered a flag',
    member_set: 'changed access', member_removed: 'removed access', records_published: 'published records', records_withdrawn: 'withdrew records'};

  let me = null, ws = null, wsInfo = null, role = 'viewer';
  // submit = send records: the records role, or publisher and up.
  const can = r => r === 'submit' ? role === 'records' || (ROLE[role] || 0) >= 2 : (ROLE[role] || 0) >= (ROLE[r] || 9);

  async function api(action, {method = 'GET', body, params} = {}) {
    const qs = new URLSearchParams({action, ...(ws && !['login', 'verify'].includes(action) ? {workspace: ws} : {}), ...(params || {})});
    const r = await fetch('/api/gov?' + qs, {method, credentials: 'same-origin',
      headers: method === 'POST' ? {'Content-Type': 'application/json', 'X-BCM-Gov': '1'} : {},
      body: body ? JSON.stringify({...(ws ? {workspace: ws} : {}), ...body}) : undefined});
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && !['login', 'verify'].includes(action)) { showSignin(); throw new Error('Signed out'); }
    if (!r.ok) throw Object.assign(new Error(j.error || 'Something went wrong. Try again.'), {status: r.status});
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

  // ---------- menu ----------
  const loaders = {home: loadHome, alerts: loadAlerts, notices: () => loadPosts('notice'), events: () => loadPosts('event'), jobs: () => loadPosts('job'),
    submit: loadSubmit, records: loadRecords, flags: loadFlags, people: loadPeople, activity: loadActivity};
  const nav = $('#an-nav'), menuBtn = $('#an-open');
  function menu(open) { nav.classList.toggle('open', open); document.body.classList.toggle('an-lock', open); menuBtn.setAttribute('aria-expanded', String(open)); }
  menuBtn.addEventListener('click', () => menu(true));
  $('#an-close').addEventListener('click', () => menu(false));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && nav.classList.contains('open')) menu(false); });
  function tab(name, push = true) {
    if (!loaders[name]) name = 'home';
    const link = nav.querySelector(`[data-tab="${name}"]`);
    if (!link || link.hidden) name = 'home';
    nav.querySelectorAll('[data-tab]').forEach(a => a.dataset.tab === name ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
    $$('[data-panel]').forEach(p => { p.hidden = p.id !== 'p-' + name; });
    const title = nav.querySelector(`[data-tab="${name}"] span`).textContent;
    $('#fw-h').textContent = title; $('#an-cur').textContent = title;
    document.title = `${title} · ${wsInfo ? wsInfo.name : 'Government workspace'} · BayCounty.me`;
    if (push) { history.replaceState(null, '', '#' + name); window.scrollTo(0, 0); }
    menu(false);
    loaders[name]().catch(e => { if (e.message !== 'Signed out') console.error(e); });
  }
  nav.addEventListener('click', e => { const a = e.target.closest('a[data-tab]'); if (!a) return; e.preventDefault(); tab(a.dataset.tab); });
  window.addEventListener('hashchange', () => { if (!$('#app').hidden) tab(location.hash.slice(1), false); });
  document.addEventListener('click', e => { const g = e.target.closest('[data-go]'); if (g) tab(g.dataset.go); });

  async function start() {
    let j;
    try { j = await api('me'); } catch (e) { if (e.message !== 'Signed out') showSignin(); return; }
    me = j;
    if (!j.workspaces.length) { showSignin(); $('#signin-msg').textContent = 'You’re signed in, but no government has given you access yet.'; return; }
    const saved = (() => { try { return localStorage.getItem('gov-ws'); } catch (e) { return null; } })();
    wsInfo = j.workspaces.find(x => x.id === saved) || j.workspaces[0];
    ws = wsInfo.id; role = wsInfo.role;
    if (j.workspaces.length > 1) {
      const sel = $('#ws-pick'); sel.hidden = false;
      sel.innerHTML = j.workspaces.map(x => `<option value="${esc(x.id)}"${x.id === ws ? ' selected' : ''}>${esc(x.name)}</option>`).join('');
      sel.onchange = () => { try { localStorage.setItem('gov-ws', sel.value); } catch (e) {} location.reload(); };
    }
    $('#ws-name').textContent = wsInfo.name; $('#ws-name').hidden = j.workspaces.length > 1;
    $('#an-ws-cur').textContent = wsInfo.name;
    $('#who').textContent = j.email; $('#who').title = j.email;
    $('#who-role').textContent = (j.roles[role] || role) + (j.admin ? ' (BayCounty.me)' : '');
    nav.querySelectorAll('[data-min]').forEach(a => { a.hidden = !can(a.dataset.min) && !(a.dataset.tab === 'activity' && role === 'auditor'); });
    nav.querySelectorAll('.an-g').forEach(g => { g.hidden = !g.querySelector('a[data-tab]:not([hidden])'); });
    $$('[data-can]').forEach(el => { el.hidden = !can(el.dataset.can); });
    $$('[data-cant]').forEach(el => { el.hidden = can(el.dataset.cant); });
    $('#al-kind').innerHTML = Object.entries(j.alert_kinds).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
    $('#al-cw-l').hidden = !wsInfo.countywide;
    $('#rec-pick').innerHTML = Object.entries(j.records).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
    $('#signin').hidden = true; $('#app').hidden = false;
    tab(location.hash.slice(1) || 'home', false);
  }

  // ---------- home ----------
  const actLine = a => `${esc(a.email)} ${esc(ACTIONS[a.action] || a.action.replace(/_/g, ' '))}${a.detail && a.detail.title ? `: “${esc(a.detail.title)}”` : ''}${a.detail && a.detail.email ? ` (${esc(a.detail.email)}${a.detail.role ? ', ' + esc(me.roles[a.detail.role] || a.detail.role) : ''})` : ''}`;
  async function loadHome() {
    const h = await api('home'), c = h.counts;
    $('#home-lead').innerHTML = c.live_alerts ? `<b>${c.live_alerts} alert${c.live_alerts === 1 ? ' is' : 's are'} live</b> for ${esc(wsInfo.name)} right now.`
      : `Nothing urgent for ${esc(wsInfo.name)}. Send an alert, post a notice, or check your record data.`;
    const lc = $('#live-count'); lc.hidden = !c.live_alerts; lc.textContent = c.live_alerts;
    const t = (go, n, label, hot) => `<button class="tile${hot ? ' hot' : ''}" type="button" data-go="${go}"><b>${n ?? '—'}</b><span>${label}</span></button>`;
    $('#home-tiles').innerHTML = t('alerts', c.live_alerts, 'Live alerts', c.live_alerts) + (c.waiting_alerts ? t('alerts', c.waiting_alerts, 'Waiting for a second person', true) : '') +
      t('notices', c.notices, 'Notices posted') + t('events', c.events, 'Upcoming events') + t('jobs', c.jobs, 'Open jobs') + t('flags', c.open_flags, 'Flags waiting on us') +
      (can('owner') ? t('people', c.members, 'People with access') : '');
    $('#home-activity').innerHTML = h.activity.length ? h.activity.map(a => `<li><div class="grow"><h3>${actLine(a)}</h3><div class="meta">${when(a.at)}</div></div></li>`).join('')
      : '<li class="muted small">Nothing yet.</li>';
  }

  // ---------- map field (alerts and notices) ----------
  // The map editor loads only when someone presses "Add a map". The drawing lives in the form's hidden geometry field.
  async function mapOpen(fld) {
    const box = fld.querySelector('[data-map-box]'), input = fld.querySelector('input[name=geometry]');
    box.hidden = false; fld.querySelector('[data-map-open]').hidden = true;
    if (!fld._ed) fld._ed = await window.BCMap.editor(box, input);
    else fld._ed.refresh();
  }
  function mapSet(form, value) {
    const fld = form.querySelector('.mapfld'); if (!fld) return;
    const input = fld.querySelector('input[name=geometry]');
    input.value = value || '';
    if (fld._ed) fld._ed.set(value || '');
    const has = window.BCMap && window.BCMap.parse(value);
    if (has) mapOpen(fld);
    else { fld.querySelector('[data-map-box]').hidden = true; fld.querySelector('[data-map-open]').hidden = false; }
    mapSum(fld);
  }
  function mapSum(fld) {
    const g = window.BCMap && window.BCMap.parse(fld.querySelector('input[name=geometry]').value);
    fld.querySelector('[data-map-sum]').textContent = g ? 'On the map: ' + window.BCMap.describe(g) : '';
  }
  document.addEventListener('click', e => { const b = e.target.closest('[data-map-open]'); if (b) mapOpen(b.closest('.mapfld')); });
  document.addEventListener('change', e => { if (e.target.name === 'geometry') mapSum(e.target.closest('.mapfld')); });

  // ---------- alerts ----------
  const fAlert = $('#f-alert');
  async function showReach() {
    const box = $('#al-reach');
    if (!can('alert_sender')) return;
    try {
      const r = await api('reach', {params: {kind: fAlert.elements.kind.value, countywide: $('#al-cw').checked ? '1' : ''}});
      box.innerHTML = r.topic ? `<span>Reaches now: <b>${r.phones ?? '—'}</b> phones · <b>${r.emails ?? '—'}</b> email inboxes</span><span class="muted">${$('#al-cw').checked ? 'All of Bay County' : 'People in ' + esc(wsInfo.name)}</span>`
        : `<span class="muted">${esc(r.note)}</span>`;
      return r;
    } catch (e) { box.textContent = e.message; }
  }
  fAlert.elements.kind.addEventListener('change', showReach);
  $('#al-cw').addEventListener('change', showReach);
  fAlert.addEventListener('submit', async e => {
    e.preventDefault();
    fAlert.querySelector('.err').textContent = '';
    const r = await showReach();
    const cw = $('#al-cw').checked;
    $('#al-confirm-h').textContent = cw ? 'Save this countywide alert for a second person to confirm?' : `Send this alert to ${wsInfo.name} now?`;
    $('#al-confirm-p').innerHTML = `“${esc(fAlert.elements.title.value)}”` + (r && r.topic ? ` will reach about ${r.phones ?? 0} phones and ${r.emails ?? 0} inboxes, and show on the public alert timeline.` : ' will show on the public alert timeline.') +
      (window.BCMap.parse(fAlert.elements.geometry.value) ? ' The map you drew shows with it.' : '') +
      (cw ? ' Nothing goes out until another alert sender confirms it.' : ' It can’t be unsent, but you can end it at any time.');
    $('#al-confirm').hidden = false; $('#al-send').focus();
  });
  $('#al-back').addEventListener('click', () => { $('#al-confirm').hidden = true; });
  $('#al-send').addEventListener('click', async () => {
    const btn = $('#al-send'); btn.disabled = true;
    const f = Object.fromEntries(new FormData(fAlert));
    try {
      const r = await api('alert', {method: 'POST', body: {...f, countywide: $('#al-cw').checked}});
      fAlert.reset(); mapSet(fAlert, ''); $('#al-confirm').hidden = true;
      fAlert.querySelector('.err').textContent = r.message + (r.delivery && r.delivery.error ? ' ' + r.delivery.error : '');
      await loadAlerts();
    } catch (err) { fAlert.querySelector('.err').textContent = err.message; }
    btn.disabled = false;
  });
  async function loadAlerts() {
    showReach();
    const j = await api('alerts');
    $('#l-alerts').innerHTML = j.alerts.length ? j.alerts.map(a => {
      const st = a.live ? '<span class="status live">Live</span>' : a.status === 'pending' ? '<span class="status pending">Waiting for a second person</span>'
        : `<span class="status done">${a.status === 'cancelled' ? 'Cancelled' : 'Ended'}</span>`;
      const mine = (a.created_by || '').toLowerCase() === (me.email || '').toLowerCase();
      const btns = !can('alert_sender') ? '' : (a.status === 'pending' && (!mine || me.admin) ? `<button class="btn primary" type="button" data-confirm="${a.id}">Confirm and send</button>` : '') +
        (a.live || a.status === 'pending' ? `<button class="btn" type="button" data-end="${a.id}">${a.status === 'pending' ? 'Cancel' : 'End now'}</button>` : '');
      return `<li><div class="grow"><h3>${esc(a.title)} ${st}</h3><div class="meta"><span>${esc(me.alert_kinds[a.kind] || a.kind)}</span><span>${a.countywide ? 'All of Bay County' : esc(wsInfo.name)}</span>
        <span>By ${esc(a.created_by)}${a.confirmed_by ? `, confirmed by ${esc(a.confirmed_by)}` : ''}</span><span>${a.sent_at ? 'Sent ' + when(a.sent_at) : 'Saved ' + when(a.created_at)}</span>
        ${a.geometry ? '<span>Has a map</span>' : ''}${a.live && a.ends_at ? `<span>Ends ${when(a.ends_at)}</span>` : ''}${a.ended_at ? `<span>${a.status === 'cancelled' ? 'Cancelled' : 'Ended'} ${when(a.ended_at)} by ${esc(a.ended_by)}</span>` : ''}</div>
        <p class="body">${esc(a.message)}${a.instruction ? '\n\n' + esc(a.instruction) : ''}</p></div><div class="row">${btns}</div></li>`;
    }).join('') : '<li class="muted small">No alerts sent from this workspace yet.</li>';
  }
  $('#l-alerts').addEventListener('click', async e => {
    const c = e.target.closest('[data-confirm]'), x = e.target.closest('[data-end]');
    if (!c && !x) return;
    const b = c || x; b.disabled = true;
    try { await api(c ? 'alert-confirm' : 'alert-end', {method: 'POST', body: {id: Number(b.dataset.confirm || b.dataset.end)}}); await loadAlerts(); }
    catch (err) { b.disabled = false; b.insertAdjacentHTML('afterend', `<span class="small err">${esc(err.message)}</span>`); }
  });

  // ---------- notices, events, jobs ----------
  const posts = {notice: [], event: [], job: []};
  const LINE = {
    notice: r => ({h: r.title, meta: [r.kind_label, r.published && 'Published ' + day(r.published), r.event_date && 'Date: ' + day(r.event_date), r.geometry && 'Has a map'], body: r.text}),
    event: r => ({h: r.title, meta: [day(r.starts) + (String(r.starts || '').length > 10 ? ', ' + new Date(r.starts).toLocaleTimeString('en-US', {hour: 'numeric', minute: '2-digit'}) : ''), r.venue, r.category, r.cost]}),
    job: r => ({h: r.title, meta: [r.department, r.job_type, r.pay, r.posted && 'Posted ' + day(r.posted), r.closes && 'Closes ' + day(r.closes)]}),
  };
  const postItem = (kind, r) => {
    const l = LINE[kind](r);
    const btns = r.editable && can('publisher') ? `<div class="row"><button class="btn" type="button" data-edit="${kind}:${r.id}">Edit</button><button class="btn quiet" type="button" data-withdraw="${kind}:${r.id}">Withdraw</button></div>` : '';
    return `<li><div class="grow"><h3>${esc(l.h)}</h3><div class="meta">${l.meta.filter(Boolean).map(m => `<span>${esc(m)}</span>`).join('')}${r.editable ? '' : '<span>From records · read only</span>'}</div>
      ${l.body ? `<p class="body">${esc(String(l.body).slice(0, 400))}${String(l.body).length > 400 ? '…' : ''}</p>` : ''}</div>${btns}</li>`;
  };
  async function loadPosts(kind) {
    const j = await api('posts', {params: {kind}});
    posts[kind] = j.posts;
    $('#l-' + kind).innerHTML = j.posts.length ? j.posts.map(r => postItem(kind, r)).join('') : '<li class="muted small">Nothing posted from this workspace yet.</li>';
    $('#r-' + kind).innerHTML = j.from_records.length ? j.from_records.map(r => postItem(kind, r)).join('') : '<li class="muted small">None on file.</li>';
  }
  const localInput = s => String(s || '').slice(0, 16);
  function openForm(kind, row) {
    const f = $('#f-' + kind); f.reset(); f.hidden = false; f.querySelector('.err').textContent = '';
    if (row) for (const el of f.elements) if (el.name && row[el.name] != null) el.value = el.type === 'datetime-local' ? localInput(row[el.name]) : el.type === 'date' ? String(row[el.name]).slice(0, 10) : row[el.name];
    mapSet(f, row && row.geometry);
    f.querySelector('input:not([type=hidden]),textarea').focus();
  }
  document.addEventListener('click', async e => {
    const n = e.target.closest('[data-new]'), ed = e.target.closest('[data-edit]'), w = e.target.closest('[data-withdraw]'), c = e.target.closest('[data-cancel]');
    if (n) openForm(n.dataset.new);
    if (ed) { const [k, id] = ed.dataset.edit.split(':'); openForm(k, posts[k].find(r => String(r.id) === id)); }
    if (c) c.closest('form').hidden = true;
    if (w) {
      const [k, id] = w.dataset.withdraw.split(':');
      if (w.dataset.sure !== '1') { w.dataset.sure = '1'; w.textContent = 'Withdraw: are you sure?'; return; }
      w.disabled = true;
      try { await api('withdraw', {method: 'POST', body: {kind: k, id: Number(id)}}); await loadPosts(k); } catch (err) { w.disabled = false; w.textContent = err.message; }
    }
  });
  $$('form[data-kind]').forEach(f => f.addEventListener('submit', async e => {
    e.preventDefault();
    const kind = f.dataset.kind, btn = f.querySelector('button[type=submit]'); btn.disabled = true; f.querySelector('.err').textContent = '';
    const data = Object.fromEntries(new FormData(f));
    if (!data.id) delete data.id;
    try { await api('post', {method: 'POST', body: {...data, ...(kind === 'notice' ? {notice_kind: data.kind} : {}), kind}}); f.hidden = true; await loadPosts(kind); }
    catch (err) { f.querySelector('.err').textContent = err.message; }
    btn.disabled = false;
  }));

  // ---------- send records ----------
  // A file goes up as base64 (or through a storage link when it's over 3 MB), comes back as a preview saved as
  // "waiting", and is published only when someone presses Publish. Emailed files arrive as "waiting" too.
  const money = n => n == null ? '—' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  const ST = {waiting: ['pending', 'Waiting for a check'], published: ['fixed', 'Published'], held: ['held', 'Doesn’t add up'], not_public: ['done', 'Not public'], withdrawn: ['done', 'Withdrawn']};
  const openBooks = $('#app').dataset.openBooks === '1';
  let sub = null, subKind = 'checkbook', pv = null;
  const toB64 = f => new Promise((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(',')[1]); r.onerror = () => no(new Error('The file couldn’t be read.')); r.readAsDataURL(f); });
  function kindsUi() {
    $('#sub-kinds').innerHTML = Object.entries(me.record_kinds).map(([k, v]) => `<label><input type="radio" name="sub-kind" value="${k}"${k === subKind ? ' checked' : ''}><span><b>${esc(v.label)}</b>${esc(v.hint)}</span></label>`).join('');
    $('#sub-opts').hidden = subKind === 'contracts';
    $('#sub-asof-l').hidden = subKind !== 'budget';
  }
  $('#sub-kinds').addEventListener('change', e => { if (e.target.name === 'sub-kind') { subKind = e.target.value; kindsUi(); } });
  async function loadSubmit() {
    if (!$('#sub-kinds').innerHTML) kindsUi();
    sub = await api('submissions');
    $('#sub-due').innerHTML = sub.due.map(d => `<div class="${d.current ? 'in' : ''}"><b>${esc(d.label)}</b><span>${esc(d.text)}</span>
      <span class="status ${d.current ? 'fixed' : 'pending'}" style="align-self:flex-start">${d.current ? 'In' : d.have ? 'Due: latest is ' + day(d.have) : 'Not sent yet'}</span></div>`).join('');
    $('#sub-inbox').hidden = !sub.address; $('#sub-addr').textContent = sub.address || '';
    $('#sub-tpl').innerHTML = 'No export handy? Column templates: ' + Object.keys(sub.templates).map(k => `<a href="/api/gov?action=template&workspace=${encodeURIComponent(ws)}&kind=${k}">${esc(me.record_kinds[k].label)}</a>`).join(' · ') + '.';
    $('#sub-list').innerHTML = sub.files.length ? sub.files.map(f => {
      const st = ST[f.status] || ['done', f.status];
      const period = f.period_start && f.period_end && f.period_start !== f.period_end ? `${day(f.period_start)} to ${day(f.period_end)}` : f.period_end ? day(f.period_end) : '';
      const btns = !can('submit') ? '' : f.status === 'waiting' ? `<button class="btn primary" type="button" data-sub-pub="${f.id}">Publish</button><button class="btn quiet" type="button" data-sub-wd="${f.id}">Discard</button>`
        : f.status === 'published' ? `<button class="btn quiet" type="button" data-sub-wd="${f.id}">Withdraw</button>` : '';
      return `<li><div class="grow"><h3>${esc(f.name)} <span class="status ${st[0]}">${st[1]}</span></h3><div class="meta"><span>${esc(me.record_kinds[f.kind] ? me.record_kinds[f.kind].label : f.kind)}</span>
        ${period ? `<span>${esc(period)}</span>` : ''}${f.rows != null ? `<span>${Number(f.rows).toLocaleString('en-US')} rows</span>` : ''}<span>${f.via === 'email' ? 'Emailed in by' : 'Sent by'} ${esc(f.sent_by)}, ${when(f.sent_at)}</span>
        ${f.published_at ? `<span>Published ${when(f.published_at)}${f.published_by ? ' by ' + esc(f.published_by) : ''}</span>` : ''}</div>
        ${f.status === 'held' ? `<p class="body">The rows don’t add up to the file’s own printed total${f.difference ? ` (off by ${money(f.difference)})` : ''}, so nothing from it is used. Send a corrected file.</p>` : ''}
        ${f.problem && f.status === 'waiting' ? `<p class="body">${esc(f.problem)}</p>` : ''}</div><div class="row">${btns}</div></li>`;
    }).join('') : '<li class="muted small">Nothing sent yet. Your first file shows up here.</li>';
  }
  const drop = $('#sub-drop'), finput = $('#sub-file');
  drop.addEventListener('click', () => finput.click());
  drop.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); finput.click(); } });
  ['dragenter', 'dragover'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add('over'); }));
  ['dragleave', 'drop'].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove('over'); }));
  drop.addEventListener('drop', e => { if (e.dataTransfer.files[0]) sendFile(e.dataTransfer.files[0]); });
  finput.addEventListener('change', () => { if (finput.files[0]) sendFile(finput.files[0]); });
  async function sendFile(file) {
    $('#sub-msg').textContent = `Reading ${file.name}…`; $('#sub-pv').hidden = true;
    const body = {kind: subKind, filename: file.name};
    if (subKind === 'budget' && $('#sub-asof').value) body.as_of = $('#sub-asof').value;
    if (subKind !== 'contracts' && $('#sub-total').value.trim()) body.printed_total = $('#sub-total').value.trim();
    try {
      if (file.size <= 3 * 1024 * 1024) body.content = await toB64(file);
      else {
        const u = await api('submit-url', {method: 'POST', body: {filename: file.name}});
        const r = await fetch(u.url, {method: 'PUT', body: file, headers: {'x-upsert': 'true', 'Content-Type': file.type || 'application/octet-stream'}});
        if (!r.ok) throw new Error('The file didn’t upload (' + r.status + '). Try again.');
        body.path = u.path;
      }
      showPreview(await api('submit-preview', {method: 'POST', body}));
      $('#sub-msg').textContent = '';
    } catch (err) { $('#sub-msg').innerHTML = `<span class="err">${esc(err.message)}</span>`; }
    finput.value = '';
    loadSubmit().catch(() => {});
  }
  const COLS = {
    checkbook: [['paid_on', 'Date'], ['doc_no', 'Check'], ['payee', 'Paid to'], ['amount', 'Amount', 1], ['description', 'Description']],
    budget: [['department', 'Department'], ['account', 'Account'], ['description', 'Description'], ['amended_budget', 'Budget', 1], ['actual_ytd', 'Spent or received', 1]],
    contracts: [['date', 'Awarded'], ['vendor', 'Vendor'], ['purpose', 'What for'], ['amount', 'Amount', 1], ['method', 'How awarded']],
  };
  function showPreview(p) {
    pv = p;
    const cols = COLS[p.kind], period = p.period && (p.period.start || p.period.end) ? [p.period.start, p.period.end].filter(Boolean).map(day).join(' to ') : '';
    $('#sub-pv-h').textContent = p.ok ? `Check the preview: ${me.record_kinds[p.kind].label}` : 'This file can’t be published yet';
    $('#sub-pv-sum').innerHTML = [`<span><b>${Number(p.row_count || 0).toLocaleString('en-US')}</b> rows</span>`, p.parsed_total != null ? `<span>Total <b>${money(p.parsed_total)}</b></span>` : '',
      period ? `<span>${esc(period)}</span>` : '', p.tie && p.tie.status === 'ties' ? '<span class="status fixed">Adds up to the printed total</span>' : '',
      p.tie && p.tie.status === 'mismatch' ? `<span class="status held">Off from the printed total by ${money(p.tie.difference)}</span>` : '',
      p.used_saved_mapping ? '<span class="muted">Columns matched like last time</span>' : ''].filter(Boolean).join('');
    const notes = [];
    if (!p.ok) notes.push(`Missing: ${esc((p.missing || []).join('; '))}. Check you chose the right kind of record, or send the report straight from your system.`);
    if (p.kind === 'checkbook' && p.ok) notes.push('Payments to private people (refunds, reimbursements) are published without their name. Voided checks are left out.');
    if (p.kind === 'contracts') {
      if (p.already_on_site) notes.push(`${p.already_on_site} contract${p.already_on_site === 1 ? ' is' : 's are'} already on the site and won’t be added twice.`);
      if (p.withheld) notes.push(`${p.withheld} with a private person will be listed without the person’s name.`);
      if (p.skipped) notes.push(`${p.skipped} row${p.skipped === 1 ? ' was' : 's were'} left out (${esc(Object.entries(p.reasons || {}).map(([k, n]) => `${n} ${k}`).join(', '))}).`);
    }
    if (p.already_added) notes.push('This exact file was already added before.');
    if (p.ok && p.kind !== 'contracts' && !openBooks) notes.push('Published files show on the public checkbook and budget tracker pages once those pages open; they are on the site’s data downloads and API right away.');
    $('#sub-pv-note').innerHTML = notes.join(' ');
    $('#sub-pv-t thead').innerHTML = `<tr>${cols.map(c => `<th>${esc(c[1])}</th>`).join('')}</tr>`;
    $('#sub-pv-t tbody').innerHTML = (p.sample || []).map(r => `<tr>${cols.map(c => `<td${c[2] ? ' class="num"' : ''} title="${esc(r[c[0]] ?? '')}">${esc(c[2] ? money(r[c[0]]) : c[0] === 'paid_on' || c[0] === 'date' ? day(r[c[0]]) : r[c[0]] ?? '')}</td>`).join('')}</tr>`).join('')
      || `<tr><td class="empty" colspan="${cols.length}">No rows to show.</td></tr>`;
    $('#sub-go').hidden = !p.ok || (p.tie && p.tie.status === 'mismatch');
    $('#sub-err').textContent = '';
    $('#sub-pv').hidden = false; $('#sub-pv').scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  async function publishFile(id, btn) {
    btn.disabled = true;
    try {
      const r = await api('submit-publish', {method: 'POST', body: {id}});
      if (r.held) throw new Error(r.message);
      const msg = `Published ${Number(r.rows).toLocaleString('en-US')} rows${r.individuals_withheld ? `, ${r.individuals_withheld} without a private person’s name` : ''}.`;
      $('#sub-pv').hidden = true; pv = null;
      $('#sub-msg').innerHTML = esc(msg) + (r.kind === 'contracts' || openBooks ? ` <a href="${esc(r.page)}" target="_blank" rel="noopener">See it on the site</a>` : '');
      await loadSubmit();
    } catch (err) { btn.disabled = false; ($('#sub-pv').hidden ? $('#sub-msg') : $('#sub-err')).textContent = err.message; }
  }
  $('#sub-go').addEventListener('click', e => pv && publishFile(pv.id, e.currentTarget));
  $('#sub-cancel').addEventListener('click', async () => { if (pv) await api('submit-withdraw', {method: 'POST', body: {id: pv.id}}).catch(() => {}); pv = null; $('#sub-pv').hidden = true; loadSubmit(); });
  $('#sub-list').addEventListener('click', async e => {
    const p = e.target.closest('[data-sub-pub]'), w = e.target.closest('[data-sub-wd]');
    if (p) return publishFile(p.dataset.subPub, p);
    if (!w) return;
    if (w.dataset.sure !== '1') { w.dataset.sure = '1'; w.textContent = w.textContent === 'Discard' ? 'Discard: sure?' : 'Take it off the site?'; return; }
    w.disabled = true;
    try { await api('submit-withdraw', {method: 'POST', body: {id: w.dataset.subWd}}); await loadSubmit(); } catch (err) { w.disabled = false; w.textContent = err.message; }
  });

  // ---------- record data (read only) + flags ----------
  let recRows = [], recCols = [];
  const SKIP = new Set(['id', 'gov_id', 'source_url', 'date_start', 'date_end', 'date_precision']);
  const label = c => c.replace(/_/g, ' ').replace(/^./, x => x.toUpperCase());
  const cell = v => v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : typeof v === 'number' ? v.toLocaleString('en-US') : String(v);
  async function loadRecords() {
    const ds = $('#rec-pick').value;
    const j = await api('records', {params: {dataset: ds}});
    recRows = j.rows;
    recCols = recRows.length ? Object.keys(recRows[0]).filter(c => !SKIP.has(c)).slice(0, 7) : [];
    $('#rec-count').textContent = `${recRows.length} row${recRows.length === 1 ? '' : 's'} · read only`;
    $('#rec-t thead').innerHTML = recRows.length ? `<tr>${recCols.map(c => `<th>${esc(label(c))}</th>`).join('')}<th></th></tr>` : '';
    $('#rec-t tbody').innerHTML = recRows.length ? recRows.map((r, i) => `<tr>${recCols.map(c => `<td title="${esc(cell(r[c]))}">${esc(cell(r[c]))}</td>`).join('')}
      <td class="act">${r.source_url ? `<a class="btn quiet" href="${esc(r.source_url)}" target="_blank" rel="noopener">Source</a>` : ''}<button class="btn" type="button" data-flag-row="${i}">Flag</button></td></tr>`).join('')
      : `<tr><td class="empty">Nothing on file for ${esc(wsInfo.name)} in this dataset.</td></tr>`;
  }
  $('#rec-pick').addEventListener('change', loadRecords);
  const dlg = $('#flag-dlg'), ff = $('#flag-form');
  let flagRow = null;
  $('#rec-t').addEventListener('click', e => {
    const b = e.target.closest('[data-flag-row]'); if (!b) return;
    flagRow = recRows[Number(b.dataset.flagRow)];
    ff.reset(); ff.querySelector('.err').textContent = '';
    const cols = Object.keys(flagRow).filter(c => !SKIP.has(c));
    $('#flag-rec').innerHTML = recCols.slice(0, 4).map(c => `<dt>${esc(label(c))}</dt><dd>${esc(cell(flagRow[c]))}</dd>`).join('');
    $('#flag-field').innerHTML = cols.map(c => `<option value="${esc(c)}">${esc(label(c))}: ${esc(cell(flagRow[c]).slice(0, 60))}</option>`).join('') + '<option value="">Something else</option>';
    dlg.showModal();
  });
  $('#flag-cancel').addEventListener('click', () => dlg.close());
  ff.addEventListener('submit', async e => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(ff)), field = f.field;
    const labelOf = recCols.slice(0, 3).map(c => cell(flagRow[c])).filter(Boolean).join(' · ');
    try {
      await api('flag', {method: 'POST', body: {dataset: $('#rec-pick').value, record_key: String(flagRow.id ?? ''), record_label: labelOf, field,
        shown_value: field ? cell(flagRow[field]) : '', correct_value: f.correct_value, evidence_url: f.evidence_url, note: f.note}});
      dlg.close();
      $('#rec-count').textContent = 'Flag sent. We’ll check it against the source and answer under Flags you sent.';
    } catch (err) { ff.querySelector('.err').textContent = err.message; }
  });
  async function loadFlags() {
    const j = await api('flags');
    const st = {open: ['open', 'Waiting on us'], fixed: ['fixed', 'Fixed'], not_changed: ['done', 'Not changed']};
    $('#l-flags').innerHTML = j.flags.length ? j.flags.map(f => `<li><div class="grow"><h3>${esc(me.records[f.dataset] || f.dataset)}${f.record_label ? ': ' + esc(f.record_label) : ''} <span class="status ${st[f.status][0]}">${st[f.status][1]}</span></h3>
      <div class="meta"><span>${esc(f.email)}</span><span>${when(f.created_at)}</span></div>
      <p class="body">${f.field ? `${esc(label(f.field))}: “${esc(f.shown_value)}”` : ''}${f.correct_value ? ` should be “${esc(f.correct_value)}”` : ''}${f.note ? '\n' + esc(f.note) : ''}${f.reply ? `\n\nBayCounty.me: ${esc(f.reply)}` : ''}</p></div></li>`).join('')
      : '<li class="muted small">No flags sent yet. Use Record data to flag a value that looks wrong.</li>';
  }

  // ---------- people + activity ----------
  async function loadPeople() {
    const j = await api('members');
    $('#pp-t tbody').innerHTML = j.members.map(m => `<tr><td>${esc(m.email)}</td><td>${esc(me.roles[m.role] || m.role)}</td><td>${esc(m.added_by || '')}</td><td>${day(m.created_at)}</td>
      <td>${m.email.toLowerCase() === me.email ? '' : `<button class="btn quiet" type="button" data-rm="${esc(m.email)}">Remove</button>`}</td></tr>`).join('') || '<tr><td colspan="5" class="empty">Nobody yet.</td></tr>';
  }
  $('#pp-form').addEventListener('submit', async e => {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.target));
    try { await api('members', {method: 'POST', body: f}); e.target.reset(); $('#pp-msg').textContent = `${f.email} can now sign in.`; await loadPeople(); }
    catch (err) { $('#pp-msg').textContent = err.message; }
  });
  $('#pp-t').addEventListener('click', async e => {
    const b = e.target.closest('[data-rm]'); if (!b) return;
    if (b.dataset.sure !== '1') { b.dataset.sure = '1'; b.textContent = 'Remove: sure?'; return; }
    await api('members', {method: 'POST', body: {email: b.dataset.rm, role: 'remove'}}).catch(err => { $('#pp-msg').textContent = err.message; });
    loadPeople();
  });
  async function loadActivity() {
    const j = await api('activity');
    $('#act-t tbody').innerHTML = j.activity.map(a => `<tr><td>${when(a.at)}</td><td>${esc(a.email)}</td><td>${actLine({...a, email: ''}).trim()}</td></tr>`).join('') || '<tr><td colspan="3" class="empty">Nothing yet.</td></tr>';
  }

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
