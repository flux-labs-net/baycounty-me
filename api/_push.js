// Phone notifications for the emergency hub: Apple (APNs, token auth over HTTP/2) and Android (Firebase Cloud Messaging
// HTTP v1). Nothing is sent until the keys are set in Vercel:
//   APNS_KEY       the .p8 key text from Apple Developer > Keys (Apple Push Notifications service), with \n for line breaks
//   APNS_KEY_ID    that key's 10-character id
//   APNS_TEAM_ID   the team id (Q8EM9CLKCK for Flux Labs)
//   APNS_TOPIC     the app's bundle id (default me.baycounty.app); APNS_ENV=development for Xcode debug builds
//   FCM_SERVICE_ACCOUNT  the Firebase project's service account JSON (Project settings > Service accounts > Generate key)
// Each send returns {delivered, failed, dead: [tokens the service says are gone]}; the caller disables dead tokens.
const crypto = require('crypto');
const http2 = require('http2');

const b64u = b => Buffer.from(b).toString('base64url');
const pem = s => String(s || '').replace(/\\n/g, '\n').trim();

const apnsReady = () => !!(process.env.APNS_KEY && process.env.APNS_KEY_ID && process.env.APNS_TEAM_ID);
const fcmReady = () => { try { const s = JSON.parse(process.env.FCM_SERVICE_ACCOUNT || ''); return !!(s.client_email && s.private_key && s.project_id); } catch (e) { return false; } };
const ready = () => ({ios: apnsReady(), android: fcmReady()});

// ---------- Apple ----------
let apnsJwt = null;
function apnsToken(now = Date.now()) {
  if (apnsJwt && now - apnsJwt.t < 45 * 60e3) return apnsJwt.v; // Apple wants a new token at most hourly, at least every 20 minutes apart
  const head = b64u(JSON.stringify({alg: 'ES256', kid: process.env.APNS_KEY_ID}));
  const body = b64u(JSON.stringify({iss: process.env.APNS_TEAM_ID, iat: Math.floor(now / 1000)}));
  const sig = crypto.sign('sha256', Buffer.from(`${head}.${body}`), {key: pem(process.env.APNS_KEY), dsaEncoding: 'ieee-p1363'});
  apnsJwt = {t: now, v: `${head}.${body}.${b64u(sig)}`};
  return apnsJwt.v;
}
function apnsPayload(msg) {
  return JSON.stringify({aps: {alert: {title: msg.title, body: msg.body}, sound: 'default', 'thread-id': msg.topic,
    'interruption-level': msg.critical ? 'time-sensitive' : 'active'}, notice_id: msg.notice_id, url: msg.url});
}
// One connection to one APNs host; returns [{status, data}] in token order.
async function apnsPost(host, tokens, msg) {
  const body = apnsPayload(msg), auth = 'bearer ' + apnsToken(); // before connecting: a bad key throws here
  const client = http2.connect(host);
  client.on('error', () => {});
  const one = token => new Promise(resolve => {
    const req = client.request({':method': 'POST', ':path': `/3/device/${token}`, authorization: auth, 'apns-topic': process.env.APNS_TOPIC || 'me.baycounty.app',
      'apns-push-type': 'alert', 'apns-priority': '10', 'apns-collapse-id': String(msg.notice_id).slice(0, 64), 'content-type': 'application/json'});
    let status = 0, data = '';
    req.setTimeout(10000, () => { req.close(); resolve({status: 0}); });
    req.on('response', h => { status = h[':status']; });
    req.on('data', c => { data += c; });
    req.on('end', () => resolve({status, data}));
    req.on('error', () => resolve({status: 0}));
    req.end(body);
  });
  const rs = [];
  try { for (const batch of chunks(tokens, 50)) rs.push(...await Promise.all(batch.map(one))); } finally { client.close(); }
  return rs;
}
const APNS_PROD = 'https://api.push.apple.com', APNS_SANDBOX = 'https://api.sandbox.push.apple.com';
const apnsReason = r => { try { return JSON.parse(r.data || '{}').reason || null; } catch (e) { return null; } };
// A phone running a build installed from Xcode has a sandbox token, which production calls BadDeviceToken; those are
// tried once on the sandbox before they count as gone. reasons: Apple's answer per failure, for the test button.
async function sendApns(tokens, msg) {
  const out = {delivered: 0, failed: 0, dead: [], reasons: []};
  if (!tokens.length) return out;
  const dev = process.env.APNS_ENV === 'development';
  const first = await apnsPost(dev ? APNS_SANDBOX : APNS_PROD, tokens, msg);
  const retry = dev ? [] : tokens.filter((t, i) => apnsReason(first[i]) === 'BadDeviceToken');
  const second = retry.length ? await apnsPost(APNS_SANDBOX, retry, msg) : [];
  const final = tokens.map((t, i) => { const j = retry.indexOf(t); return j >= 0 ? second[j] : first[i]; });
  final.forEach((r, i) => {
    if (r.status === 200) { out.delivered++; return; }
    out.failed++;
    const why = apnsReason(r) || (r.status ? 'HTTP ' + r.status : 'no answer');
    out.reasons.push(why);
    if (r.status === 410 || /BadDeviceToken|Unregistered|DeviceTokenNotForTopic/.test(why)) out.dead.push(tokens[i]);
  });
  return out;
}

// ---------- Android (FCM) ----------
let fcmAuth = null;
async function fcmAccess(now = Date.now()) {
  if (fcmAuth && now < fcmAuth.exp - 120e3) return fcmAuth;
  const sa = JSON.parse(process.env.FCM_SERVICE_ACCOUNT);
  const iat = Math.floor(now / 1000);
  const head = b64u(JSON.stringify({alg: 'RS256', typ: 'JWT'}));
  const claims = b64u(JSON.stringify({iss: sa.client_email, scope: 'https://www.googleapis.com/auth/firebase.messaging', aud: 'https://oauth2.googleapis.com/token', iat, exp: iat + 3600}));
  const sig = crypto.sign('sha256', Buffer.from(`${head}.${claims}`), pem(sa.private_key));
  const r = await fetch('https://oauth2.googleapis.com/token', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${head}.${claims}.${b64u(sig)}`})});
  const j = await r.json();
  if (!r.ok) throw new Error('FCM sign-in failed: ' + (j.error_description || j.error || r.status));
  fcmAuth = {token: j.access_token, project: sa.project_id, exp: now + (j.expires_in || 3600) * 1000};
  return fcmAuth;
}
async function sendFcm(tokens, msg) {
  const out = {delivered: 0, failed: 0, dead: []};
  if (!tokens.length) return out;
  const a = await fcmAccess();
  const one = async token => {
    const r = await fetch(`https://fcm.googleapis.com/v1/projects/${a.project}/messages:send`, {method: 'POST',
      headers: {Authorization: `Bearer ${a.token}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({message: {token, notification: {title: msg.title, body: msg.body},
        data: {notice_id: String(msg.notice_id), url: msg.url, topic: msg.topic},
        android: {priority: 'high', collapse_key: String(msg.notice_id).slice(0, 64), notification: {channel_id: 'emergency', tag: String(msg.notice_id).slice(0, 64)}}}})}).catch(() => null);
    if (r && r.ok) return 'ok';
    const j = r ? await r.json().catch(() => ({})) : {};
    const code = JSON.stringify(j.error || {});
    return r && (r.status === 404 || /UNREGISTERED|INVALID_ARGUMENT.*registration/i.test(code)) ? 'dead' : 'fail';
  };
  for (const batch of chunks(tokens, 25)) {
    const rs = await Promise.all(batch.map(one));
    rs.forEach((s, i) => { if (s === 'ok') out.delivered++; else { out.failed++; if (s === 'dead') out.dead.push(batch[i]); } });
  }
  return out;
}

function chunks(a, n) { const out = []; for (let i = 0; i < a.length; i += n) out.push(a.slice(i, i + n)); return out; }

// devices: [{token, platform}]. Platforms without keys are skipped (counted as not sent).
async function send(devices, msg) {
  const r = ready(), res = {delivered: 0, failed: 0, skipped: 0, dead: [], reasons: []};
  const add = x => { res.delivered += x.delivered; res.failed += x.failed; res.dead.push(...x.dead); res.reasons.push(...(x.reasons || (x.e ? [String(x.e.message || x.e)] : []))); };
  const ios = devices.filter(d => d.platform === 'ios').map(d => d.token), android = devices.filter(d => d.platform === 'android').map(d => d.token);
  if (r.ios) add(await sendApns(ios, msg).catch(e => ({delivered: 0, failed: ios.length, dead: [], e}))); else res.skipped += ios.length;
  if (r.android) add(await sendFcm(android, msg).catch(e => ({delivered: 0, failed: android.length, dead: [], e}))); else res.skipped += android.length;
  return res;
}

// What a notification says. Short: lock screens cut at about 110 characters.
const LABEL = {weather: 'Weather', evacuation: 'Evacuation order', shelters: 'Shelter open', water: 'Boil-water notice', roads: 'Road closed'};
function message(n, topic, site = 'https://baycounty.me') {
  const lead = topic === 'weather' ? n.event || 'Weather alert' : LABEL[topic] || 'Alert';
  const where = n.kind === 'boil-water' || n.kind === 'road' ? (n.source || '').replace(/^City of /, '') : '';
  const zones = n.zones ? ` · Zone${n.zones.includes(',') ? 's' : ''} ${n.zones}` : '';
  const title = `${lead}${where ? ' · ' + where : ''}${zones}`.slice(0, 80);
  let body = n.title || '';
  if (topic === 'weather' && n.area) body = `${n.event} for ${n.area}`.replace(/;/g, ',');
  if (body.length > 160) body = body.slice(0, 157).replace(/\s+\S*$/, '') + '…';
  return {title, body, topic, notice_id: n.notice_id, url: `${site}/emergency#n-${encodeURIComponent(n.notice_id)}`, critical: topic === 'evacuation' || (topic === 'weather' && n.severity === 'extreme')};
}

module.exports = {ready, send, message, apnsToken, apnsPayload, apnsReason, chunks};
