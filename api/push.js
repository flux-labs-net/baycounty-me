// Phone notifications for the BayCounty.me apps.
//   GET  /api/push                      {ready: {ios, android}, topics, defaults}
//   POST /api/push {token, platform, action: 'unregister'}  (or DELETE with the same body) removes the phone.
// Signing a phone up needs a BayCounty.me account: the apps turn alerts on in My home > Settings, which calls
// POST /api/account device (api/_account.js). The phone's alerts then follow the account's home and choices, and
// only phones tied to an account are sent anything (api/_emergency_run.js, api/_agenda_push.js).
const {TOPICS, DEFAULT_TOPICS} = require('./_emergency');
const {ipOf} = require('./_gate');
const db = require('./_db');
const P = require('./_push');

const hits = new Map();
const TOKEN = {ios: /^[0-9a-f]{64,200}$/i, android: /^[\w:.-]{100,400}$/};

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'GET') return res.status(200).json({ready: P.ready(), topics: TOPICS, defaults: DEFAULT_TOPICS});
  if (req.method !== 'POST' && req.method !== 'DELETE') return res.status(405).json({ok: false, error: 'Use POST.'});
  const ip = ipOf(req), now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (recent.length >= 60) return res.status(429).json({ok: false, error: 'Too many requests. Try again later.'});
  recent.push(now); hits.set(ip, recent);
  let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = {}; } } b = b || {};
  if (req.method !== 'DELETE' && b.action !== 'unregister') {
    return res.status(401).json({ok: false, signed_out: true, error: 'Sign in to BayCounty.me in the app to get alerts.'});
  }
  const platform = b.platform === 'android' ? 'android' : b.platform === 'ios' ? 'ios' : null;
  const token = String(b.token || '').trim();
  if (!platform || !TOKEN[platform].test(token)) return res.status(400).json({ok: false, error: 'A valid device token and platform are required.'});
  if (!db.hasDb()) return res.status(503).json({ok: false, error: 'Notifications aren’t set up yet.'});
  try {
    await db.q('delete from push.devices where token = $1', [token]);
    return res.status(200).json({ok: true, removed: true});
  } catch (e) {
    console.error('push unregister', e.message);
    return res.status(500).json({ok: false, error: 'Couldn’t remove this phone. Try again.'});
  }
};
