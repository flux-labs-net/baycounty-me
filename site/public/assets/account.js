/* My home (/account): sign in with an emailed code, save a home address, see what's happening around it, and pick
   what to hear about. Accounts: /api/account (api/_account.js). The feed is the public /api/v1/nearby answer for the
   saved home (api/_nearby.js), fetched through /api/account?action=feed so the address never goes in a URL. */
(() => {
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3/query';
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const title = s => String(s || '').toLowerCase().replace(/\b([a-z])/g, m => m.toUpperCase()).replace(/\b(Ne|Nw|Se|Sw|Us|Cr|Sr)\b/g, m => m.toUpperCase());
const ico = (name, tone) => `<span class="ui-ti t-${tone}"><span class="ico i-${name}" aria-hidden="true"></span></span>`;
const LOOK = {alerts: ['storm', 'salmon'], meetings: ['calendar', 'blue'], events: ['sun', 'teal'], projects: ['crane', 'amber'], notices: ['megaphone', 'blue'], food: ['store', 'salmon'], business: ['briefcase', 'teal']};
let ME = null, FEED = null, PICK = null, EDITING = false;

async function api(action, body) {
  const r = await fetch(`/api/account?action=${action}`, body === undefined ? {credentials: 'same-origin'}
    : {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-BCM-Account': '1'}, body: JSON.stringify(body)});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(j.error || 'Something went wrong. Try again.'), {status: r.status});
  return j;
}
const msg = (el, text, kind) => { const m = $(el); m.textContent = text || ''; m.className = 'mh-msg' + (kind ? ' ' + kind : ''); };
function show(view) { $('mhWait').hidden = true; $('mhOut').hidden = view !== 'out'; $('mhIn').hidden = view !== 'in'; }

/* ---------- sign in ---------- */
let EMAIL = '';
$('startForm').addEventListener('submit', async e => {
  e.preventDefault();
  if (!$('stepCode').hidden) return verify();
  EMAIL = $('email').value.trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(EMAIL)) return msg('startMsg', 'Enter a valid email address.', 'err');
  $('startBtn').disabled = true; msg('startMsg', 'Sending…');
  try {
    const r = await api('start', {email: EMAIL});
    $('stepEmail').hidden = true; $('stepCode').hidden = false; $('codeLbl').textContent = `Code sent to ${EMAIL}`;
    msg('startMsg', r.message || 'Check your email for the code.', 'ok'); $('code').focus();
  } catch (e2) { msg('startMsg', e2.message, 'err'); }
  $('startBtn').disabled = false;
});
$('code').addEventListener('input', () => { $('code').value = $('code').value.replace(/\D/g, '').slice(0, 6); if ($('code').value.length === 6) verify(); });
$('verifyBtn').addEventListener('click', verify);
$('backBtn').addEventListener('click', () => { $('stepEmail').hidden = false; $('stepCode').hidden = true; msg('startMsg', ''); $('email').focus(); });
let verifying = false;
async function verify() {
  const code = $('code').value.replace(/\D/g, '');
  if (code.length !== 6) return msg('startMsg', 'Enter the 6 digits from the email.', 'err');
  if (verifying) return; verifying = true; $('verifyBtn').disabled = true; msg('startMsg', 'Checking…');
  try { ME = await api('verify', {email: EMAIL, code, client: 'web'}); msg('startMsg', ''); enter(); }
  catch (e) { msg('startMsg', e.message, 'err'); }
  verifying = false; $('verifyBtn').disabled = false;
}

/* ---------- signed in ---------- */
function enter() {
  show('in');
  document.documentElement.classList.add('signed-in');
  renderTop(); renderSettings();
  if (!ME.home) { openHome(false); $('feed').innerHTML = ''; }
  else { $('homeForm').hidden = true; loadFeed(); }
}
function renderTop() {
  const h = ME.home, hour = +new Date().toLocaleString('en-US', {hour: 'numeric', hour12: false, timeZone: 'America/Chicago'});
  const hi = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  $('hello').textContent = ME.user.first_name ? `${hi}, ${ME.user.first_name}` : 'My home';
  $('homeTitle').textContent = h ? h.address : 'Welcome to BayCounty.me';
  $('homeAddr').innerHTML = h ? [`<span>${esc([h.city, h.zip].filter(Boolean).join(' '))}</span>`,
    `<span class="mh-chip">${h.gov_id && h.gov_id !== 'county' ? 'City of ' + esc(h.city || '') : 'Unincorporated Bay County'}</span>`,
    h.zone ? `<span class="mh-chip zone">Evacuation zone ${esc(h.zone)}</span>` : `<span class="mh-chip">Not in an evacuation zone</span>`].join('') : '<span>Save your address to see what’s around it.</span>';
  $('who').textContent = ME.user.email;
  // Same sign-in as the realtor console: an agent's account links straight to it.
  $('rcLink').hidden = ME.realtor !== 'active';
}

/* ---------- the feed ---------- */
async function loadFeed() {
  $('feed').innerHTML = '<p class="mh-loading"><span class="mh-spin" aria-hidden="true"></span>Looking around your home…</p>';
  try { FEED = await api('feed'); renderFeed(); }
  catch (e) { if (e.status === 401) return signedOut(); $('feed').innerHTML = `<p class="mh-msg err">${esc(e.message)}</p>`; }
}
// Dates without an offset are Bay County clock times: read and shown as written (UTC on both sides), whatever the
// visitor's own time zone. Times with an offset are shown in Bay County time.
const naive = d => !/[zZ]|[+-]\d\d:?\d\d$/.test(String(d));
const at = d => new Date(String(d).length === 10 ? d + 'T12:00:00Z' : naive(d) ? d + 'Z' : d);
const tz = d => ({timeZone: naive(d) ? 'UTC' : 'America/Chicago'});
function whenTile(it) {
  if (it.miles != null && (!it.date || ['development', 'sales-tax', 'road'].includes(it.kind))) return `<span class="mh-when mi"><b>${it.miles < 0.1 ? '<0.1' : it.miles.toFixed(1)}</b><span>mi</span></span>`;
  if (!it.date) return '';
  const d = at(it.date); if (isNaN(d)) return '';
  return `<span class="mh-when"><span>${d.toLocaleDateString('en-US', {month: 'short', ...tz(it.date)})}</span><b>${d.toLocaleDateString('en-US', {day: 'numeric', ...tz(it.date)})}</b></span>`;
}
function timeOf(it) {
  if (!it.date || String(it.date).length <= 10 || it.all_day) return '';
  const d = at(it.date); if (isNaN(d)) return '';
  return d.toLocaleString('en-US', {weekday: 'short', hour: 'numeric', minute: '2-digit', ...tz(it.date)}).replace(':00', '');
}
const TAG = {evacuation: 'Evacuation', weather: 'Weather', 'boil-water': 'Boil water', road: 'Road', shelter: 'Shelter', utility: 'Utility', safety: 'Public safety', closed: 'Closed', warning: 'Warning', agenda: 'Agenda', development: 'Development', 'sales-tax': 'Sales tax', meeting: '', event: '', notice: '', inspection: '', business: ''};
function itemHtml(it) {
  const link = it.entity_id && window.BC && BC.href && BC.href(it.entity_id) ? BC.href(it.entity_id) : it.url;
  const ext = link && /^https?:/.test(link) && !link.startsWith('https://baycounty.me') ? ' target="_blank" rel="noopener"' : '';
  const href = link ? link.replace(/^https:\/\/baycounty\.me/, '') : null;
  const tagKey = it.level === 'closed' || it.level === 'warning' ? it.level : it.kind;
  const tag = TAG[tagKey] ? `<span class="tag ${esc(tagKey)}">${esc(TAG[tagKey])}</span>` : '';
  const sub = [timeOf(it), it.detail, it.miles != null && it.date && !['development', 'sales-tax', 'road'].includes(it.kind) ? `${it.miles.toFixed(1)} mi` : null].filter(Boolean).join(' · ');
  return `<li>${whenTile(it)}<div class="mh-it">${href ? `<a class="t" href="${esc(href)}"${ext}>${esc(it.title)}</a>` : `<b class="t">${esc(it.title)}</b>`}<small>${tag}${esc(sub)}</small></div></li>`;
}
function renderFeed() {
  const f = FEED, t = f.today_card || {};
  const alerts = (f.sections.find(s => s.id === 'alerts') || {items: []}).items;
  const trash = (t.trash || []).slice(0, 2);
  const tiles = [
    `<a class="mh-t${alerts.length ? ' warn' : ''}" href="/emergency">${ico('storm', alerts.length ? 'salmon' : 'teal')}<div><span class="k">Alerts</span><b>${alerts.length ? `${alerts.length} for your home` : 'All clear'}</b><small>${alerts.length ? esc(alerts[0].title) : 'No warnings or orders for your home'}</small></div></a>`,
    `<a class="mh-t" href="/utilities">${ico('home', 'blue')}<div><span class="k">Pickup</span><b>${trash.length ? esc(trash[0].days) : 'See your days'}</b><small>${trash.length ? esc(trash.map(x => x.service).join(' · ')) : 'Garbage and yard waste days'}</small></div></a>`,
    `<a class="mh-t" href="/emergency">${ico('shield', 'amber')}<div><span class="k">Evacuation zone</span><b>${f.zone ? 'Zone ' + esc(f.zone) : 'Not in a zone'}</b><small>${f.zone ? `Leave when an order names Zone ${esc(f.zone)}` : 'Shelter in place unless an order covers you'}</small></div></a>`,
    t.beach ? `<a class="mh-t" href="/beaches">${ico('waves', 'teal')}<div><span class="k">Beach flag today</span><b>${esc(t.beach.flag)}</b><small>${esc([t.beach.rip_current_risk && t.beach.rip_current_risk + ' rip current risk', t.beach.water_temperature].filter(Boolean).join(' · '))}</small></div></a>`
      : `<a class="mh-t" href="/governments/${esc((f.governments.find(g => g.gov_id === f.gov_id) || f.governments[0]).url.split('/').pop())}">${ico('city', 'blue')}<div><span class="k">Your government</span><b>${esc(f.local_government)}</b><small>Budget, votes and who’s in charge</small></div></a>`,
  ].join('');
  const secs = f.sections.filter(s => s.id !== 'alerts' || s.items.length);
  const sec = s => { const [i, tn] = LOOK[s.id] || ['grid', 'blue'];
    return `<section class="mh-sec${s.id === 'alerts' ? ' wide' : ''}"><h2>${ico(i, tn)}${esc(s.title)}${s.count != null && s.count > s.items.length ? `<span class="n">${s.count} filed</span>` : ''}</h2>${s.items.length
      ? `<ul class="mh-items">${s.items.map(itemHtml).join('')}</ul>` : `<p class="mh-empty">${esc(s.empty)}</p>`}</section>`; };
  $('feed').innerHTML = `<div class="mh-today">${tiles}</div><div class="mh-grid">${secs.map(sec).join('')}</div>
    <div class="mh-govs">${f.governments.map(g => `<a class="mh-btn ghost sm" href="${esc(g.url.replace('https://baycounty.me', ''))}">${esc(g.name)} →</a>`).join('')}<a class="mh-btn ghost sm" href="${esc(window.BCHomeLink(ME.home))}">Tax bill, schools and more for this address →</a></div>
    <p class="mh-fine">${esc(f.note)}</p>`;
}

/* ---------- home address ---------- */
function openHome(cancelable) {
  EDITING = true; $('homeForm').hidden = false; $('homeCancel').hidden = !cancelable;
  $('homeFormH').textContent = ME.home ? 'Change your home' : 'Where’s home?';
  msg('homeMsg', ''); $('q').value = ''; PICK = null; tabTo('feed'); $('q').focus();
}
$('homeCancel').addEventListener('click', () => { EDITING = false; $('homeForm').hidden = true; });
$('changeHome').addEventListener('click', () => openHome(!!ME.home));
$('removeHome').addEventListener('click', async () => {
  if (!ME.home || !confirm('Remove your saved home? My home will be empty until you add one again.')) return;
  try { ME = await api('home_delete', {}); FEED = null; renderTop(); renderSettings(); openHome(false); $('feed').innerHTML = ''; } catch (e) { msg('setMsg', e.message, 'err'); }
});
$('homeForm').addEventListener('submit', async e => {
  e.preventDefault();
  if (!PICK && items.length && !list.hidden) pick(items[0]);
  const body = PICK ? {lat: PICK.lat, lon: PICK.lon, address: PICK.address, parcel_id: PICK.parcel_id} : {address: inp.value.trim()};
  if (!PICK && !body.address) return msg('homeMsg', 'Type your street address first.', 'err');
  $('homeBtn').disabled = true; msg('homeMsg', 'Finding your home on the county map…');
  try { ME = await api('home', body); EDITING = false; $('homeForm').hidden = true; renderTop(); renderSettings(); loadFeed(); }
  catch (e2) { msg('homeMsg', e2.message, 'err'); }
  $('homeBtn').disabled = false;
});

/* address search (Bay County's address points; CORS is open). Same as the realtor console. */
const inp = $('q'), list = $('acList');
let timer, items = [], active = -1, seq = 0;
const SKIP = new Set(['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'BLVD', 'LN', 'LANE', 'CT', 'CIR', 'PL', 'WAY', 'FL', 'FLORIDA', 'PANAMA', 'CITY', 'BEACH', 'LYNN', 'HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO', 'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN']);
inp.addEventListener('input', () => { PICK = null; clearTimeout(timer); timer = setTimeout(suggest, 220); });
async function suggest() {
  const s = inp.value.toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b\d{5}\s*$/, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) { list.hidden = true; return; }
  const words = m[2].replace(/\bHWY\b/g, 'HIGHWAY').split(' ').filter(w => w.length > 1 && !SKIP.has(w)).slice(0, 3);
  if (!words.length) { list.hidden = true; return; }
  const where = [`ADDRESS LIKE '${m[1]} %'`, ...words.map(w => `ADDRESS LIKE '% ${w.replace(/'/g, "''")}%'`)].join(' AND ');
  const my = ++seq;
  try {
    const r = await fetch(GIS + '?' + new URLSearchParams({where, outFields: 'ADDRESS,UNIT,CMNTY,ZIP,RENUM', returnGeometry: 'true', outSR: 4326, resultRecordCount: 10, orderByFields: 'ADDRESS', f: 'json'}));
    const j = await r.json(); if (my !== seq) return;
    items = (j.features || []).filter(f => f.geometry).map(f => ({address: title(f.attributes.ADDRESS) + (f.attributes.UNIT && f.attributes.UNIT.trim() ? ' #' + f.attributes.UNIT.trim() : ''),
      city: title(f.attributes.CMNTY), zip: f.attributes.ZIP ? String(f.attributes.ZIP) : '', parcel_id: f.attributes.RENUM || '', lat: f.geometry.y, lon: f.geometry.x}));
    active = -1;
    list.innerHTML = items.length ? items.map((x, i) => `<li role="option" id="ac${i}" data-i="${i}">${esc(x.address)}<span>${esc(x.city)} ${esc(x.zip)}</span></li>`).join('')
      : '<li class="ac-empty">No matching address. Try the house number and street name, like "825 Ohio".</li>';
    list.hidden = false;
  } catch (e) { if (my === seq) { list.innerHTML = '<li class="ac-empty">Bay County’s map server didn’t answer. You can still save the address as typed.</li>'; list.hidden = false; } }
}
function pick(x) { PICK = x; inp.value = `${x.address}, ${x.city}`; list.hidden = true; }
inp.addEventListener('keydown', e => {
  if (list.hidden || !items.length) return;
  if (e.key === 'ArrowDown') { e.preventDefault(); active = Math.min(items.length - 1, active + 1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); active = Math.max(0, active - 1); }
  else if (e.key === 'Enter') { e.preventDefault(); pick(items[Math.max(0, active)]); return; }
  else if (e.key === 'Escape') { list.hidden = true; return; }
  list.querySelectorAll('li[role=option]').forEach((li, i) => li.setAttribute('aria-selected', i === active));
});
list.addEventListener('mousedown', e => { const li = e.target.closest('li[data-i]'); if (li) { e.preventDefault(); pick(items[+li.dataset.i]); } });
document.addEventListener('click', e => { if (!e.target.closest('.mh-ac')) list.hidden = true; });

/* ---------- settings ---------- */
const checks = (id, opts, on) => { $(id).innerHTML = Object.entries(opts).map(([k, v]) => `<label><input type="checkbox" value="${esc(k)}"${on.includes(k) ? ' checked' : ''}><span>${esc(v)}</span></label>`).join(''); };
const checked = id => [...$(id).querySelectorAll('input:checked')].map(i => i.value);
function renderSettings() {
  const p = ME.prefs || {}, c = ME.choices || {};
  $('setHome').textContent = ME.home ? `${ME.home.address}, ${[ME.home.city, ME.home.zip].filter(Boolean).join(' ')}` : 'No home saved yet.';
  $('removeHome').hidden = !ME.home;
  $('firstName').value = ME.user.first_name || '';
  $('radius').value = String(p.radius_mi || 1);
  $('weekly').checked = !!p.weekly_email;
  checks('topics', c.topics || {}, p.topics || []);
  renderAlerts(p, c);
  $('devices').textContent = ME.devices ? `${ME.devices} phone${ME.devices === 1 ? ' is' : 's are'} signed in.` : 'No phones signed in yet.';
  $('testRow').hidden = !ME.devices;
}
// Emergency alerts: areas (chips) and a type × channel table.
function renderAlerts(p, c) {
  const areas = p.alert_areas || [], A = c.areas || {};
  $('alertAreas').innerHTML = Object.entries(A).map(([k, v]) => `<label><input type="checkbox" value="${esc(k)}"${areas.includes(k) ? ' checked' : ''}>${esc(v)}</label>`).join('');
  $('areaNote').textContent = ME.home ? `Your home's city and evacuation zone always count${ME.home.zone ? ` (Zone ${ME.home.zone})` : ''}. Add any other areas you care about, like where family lives or where you work.`
    : 'Pick the parts of the county you want notices for. Save a home to get evacuation orders for your zone only.';
  const push = p.push_topics || [], mail = p.alert_email || [], txt = p.alert_sms || [];
  // Texts: the column shows once texting is set up (or the person already has a number); boxes work once the number is confirmed.
  const sms = ME.sms, texting = !!(c.sms_ready || sms), live = !!(sms && sms.status === 'active');
  document.querySelectorAll('.mh-tx').forEach(el => { el.hidden = !texting; });
  const box = (ch, t, on, label, off) => t.channels.includes(ch) ? `<input type="checkbox" data-ch="${ch}" value="${esc(t.key)}" aria-label="${esc(t.label)} ${label}"${on ? ' checked' : ''}${off ? ' disabled title="Add your mobile number below first"' : ''}>` : '';
  $('alertTypes').innerHTML = (c.alert_types || []).map(t => `<tr><td>${esc(t.label)}${t.urgency === 'urgent' ? '<span class="urg">Urgent</span>' : ''}<small>${esc(t.detail)}</small></td>
    <td>${box('push', t, push.includes(t.key), 'by phone')}</td><td>${box('email', t, mail.includes(t.key), 'by email')}</td>${texting ? `<td>${box('sms', t, txt.includes(t.key), 'by text', !live)}</td>` : ''}</tr>`).join('');
  $('quiet').checked = !!p.quiet_hours;
  renderSms(texting);
}
function renderSms(texting) {
  const sms = ME.sms;
  $('smsBox').hidden = !texting;
  $('smsOn').hidden = !(sms && sms.status === 'active');
  $('smsCode').hidden = !(sms && sms.status === 'pending');
  $('smsStart').hidden = !!(sms && sms.status !== 'stopped');
  if (sms && sms.status === 'active') $('smsPhone').textContent = sms.phone;
  if (sms && sms.status === 'stopped' && !$('smsMsg').textContent) msg('smsMsg', `Texts to ${sms.phone} are stopped. Text START to the alert number, or add the number again below.`);
}
const smsDo = async (btn, action, payload, after) => {
  btn.disabled = true; msg('smsMsg', 'One moment…');
  try { const r = await api(action, payload); ME = r; renderSettings(); msg('smsMsg', r.message || '', 'ok'); if (after) after(); }
  catch (e) { msg('smsMsg', e.message, 'err'); }
  btn.disabled = false;
};
$('smsSend').addEventListener('click', () => smsDo($('smsSend'), 'sms_start', {phone: $('smsNum').value, consent: $('smsOk').checked}, () => $('smsCodeIn').focus()));
$('smsConfirm').addEventListener('click', () => smsDo($('smsConfirm'), 'sms_verify', {code: $('smsCodeIn').value}));
$('smsBack').addEventListener('click', () => smsDo($('smsBack'), 'sms_off', {}));
$('smsOff').addEventListener('click', () => { if (confirm('Stop alert texts and remove your number?')) smsDo($('smsOff'), 'sms_off', {}); });
// "All of Bay County" and single areas are exclusive.
$('alertAreas').addEventListener('change', e => {
  const all = $('alertAreas').querySelector('input[value=all]');
  if (e.target === all && all.checked) $('alertAreas').querySelectorAll('input:not([value=all])').forEach(i => { i.checked = false; });
  else if (e.target !== all && e.target.checked && all) all.checked = false;
});
const chan = ch => [...$('alertTypes').querySelectorAll(`input[data-ch=${ch}]:checked`)].map(i => i.value);
$('testPush').addEventListener('click', async () => {
  $('testPush').disabled = true; msg('testMsg', 'Sending…');
  try {
    const r = await api('test_push', {});
    msg('testMsg', r.delivered ? `Sent to ${r.delivered} phone${r.delivered === 1 ? '' : 's'}. It should arrive in a few seconds.` : `Apple or Google didn’t accept it${r.reasons && r.reasons.length ? ' (' + r.reasons.join(', ') + ')' : ''}. Open the app, turn alerts off and on again in My home settings, then try again.`, r.delivered ? 'ok' : 'err');
  } catch (e) { msg('testMsg', e.message, 'err'); }
  $('testPush').disabled = false;
});
$('saveSet').addEventListener('click', async () => {
  $('saveSet').disabled = true; msg('setMsg', 'Saving…');
  try {
    if (($('firstName').value.trim() || null) !== (ME.user.first_name || null)) ME = await api('profile', {first_name: $('firstName').value});
    ME = await api('prefs', {weekly_email: $('weekly').checked, alert_email: chan('email'), topics: checked('topics'), push_topics: chan('push'), radius_mi: Number($('radius').value),
      alert_areas: checked('alertAreas'), quiet_hours: $('quiet').checked, ...(ME.sms && ME.sms.status === 'active' ? {alert_sms: chan('sms')} : {})});
    renderTop(); renderSettings(); msg('setMsg', 'Saved.', 'ok'); if (ME.home) FEED = null;
  } catch (e) { msg('setMsg', e.message, 'err'); }
  $('saveSet').disabled = false;
});
$('signOut').addEventListener('click', async () => { await api('logout', {}).catch(() => {}); signedOut(); });
$('delAcct').addEventListener('click', async () => {
  if (!confirm('Delete your BayCounty.me account? Your home, choices and sign-ins will be removed. This can’t be undone.')) return;
  try { await api('delete_account', {}); signedOut('Your account is deleted.'); } catch (e) { msg('setMsg', e.message, 'err'); }
});
function signedOut(note) {
  ME = null; FEED = null; document.documentElement.classList.remove('signed-in');
  $('stepEmail').hidden = false; $('stepCode').hidden = true; $('code').value = '';
  show('out'); msg('startMsg', note || '', note ? 'ok' : '');
}

/* ---------- tabs ---------- */
function tabTo(which) {
  $('tFeed').setAttribute('aria-selected', which === 'feed'); $('tSet').setAttribute('aria-selected', which === 'set');
  $('pFeed').hidden = which !== 'feed'; $('pSet').hidden = which !== 'set';
  if (which === 'feed' && ME && ME.home && !FEED && !EDITING) loadFeed();
}
$('tFeed').addEventListener('click', () => tabTo('feed'));
$('tSet').addEventListener('click', () => tabTo('set'));

/* ---------- start ---------- */
(async () => {
  const qs = new URLSearchParams(location.search);
  try { ME = await api('me'); enter(); if (qs.get('tab') === 'settings' || location.hash === '#alerts') { tabTo('set'); if (location.hash === '#alerts') $('alerts').scrollIntoView(); } }
  catch (e) {
    show('out');
    if (qs.get('signin') === 'expired') msg('startMsg', 'That sign-in link has expired or was already used. Send a new code.', 'err');
    else if (e.status && e.status !== 401) msg('startMsg', e.message, 'err');
  }
})();
})();
