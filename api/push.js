// Phone notification sign-up for the BayCounty.me apps.
//   GET  /api/push                      {ready: {ios, android}, topics, defaults}
//   POST /api/push {token, platform: 'ios'|'android', topics: [...], govs: [...], zone, lat, lng, radius_mi, app_version, place}
//        lat/lng is the saved place for 'agenda' (agenda items near me), rounded to about 100 m before it is stored.
//        saves or updates this phone's choices. An empty topics list turns notifications off.
//   POST /api/push {token, platform, action: 'unregister'}  (or DELETE with the same body) removes the phone.
// The token is the one Apple or Firebase gives the app; no address, name or other detail about the person is stored.
const {TOPICS, DEFAULT_TOPICS, SOURCES} = require('./_emergency');
const {ipOf} = require('./_gate');
const db = require('./_db');
const P = require('./_push');

const hits = new Map();
const GOVS = new Set((require('../places/fl-bay/place.json').governments || []).map(g => g.key));
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
  const platform = b.platform === 'android' ? 'android' : b.platform === 'ios' ? 'ios' : null;
  const token = String(b.token || '').trim();
  if (!platform || !TOKEN[platform].test(token)) return res.status(400).json({ok: false, error: 'A valid device token and platform are required.'});
  if (!db.hasDb()) return res.status(503).json({ok: false, error: 'Notifications aren’t set up yet.'});
  try {
    if (req.method === 'DELETE' || b.action === 'unregister') {
      await db.q('delete from push.devices where token = $1', [token]);
      return res.status(200).json({ok: true, removed: true});
    }
    const place = SOURCES[b.place] ? b.place : 'fl-bay';
    const topics = Array.isArray(b.topics) ? [...new Set(b.topics.filter(t => TOPICS[t]))] : DEFAULT_TOPICS;
    const govs = Array.isArray(b.govs) ? [...new Set(b.govs.filter(g => GOVS.has(g)))] : [];
    const zone = /^[A-E]$/.test(String(b.zone || '').toUpperCase()) ? String(b.zone).toUpperCase() : null;
    const ver = String(b.app_version || '').slice(0, 40) || null;
    const lat = Number(b.lat), lng = Number(b.lng);
    const pt = Number.isFinite(lat) && Number.isFinite(lng) && b.lat !== null && b.lng !== null && lat > 29 && lat < 31.5 && lng > -87.7 && lng < -84.5
      ? [Math.round(lat * 1000) / 1000, Math.round(lng * 1000) / 1000] : [null, null];
    const radius = [0.25, 0.5, 1, 2, 5].includes(Number(b.radius_mi)) ? Number(b.radius_mi) : 1;
    await db.q(`insert into push.devices (token, platform, place_id, topics, govs, zone, lat, lng, radius_mi, app_version) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
      on conflict (token) do update set platform = excluded.platform, place_id = excluded.place_id, topics = excluded.topics, govs = excluded.govs,
        zone = excluded.zone, lat = excluded.lat, lng = excluded.lng, radius_mi = excluded.radius_mi, app_version = excluded.app_version, last_seen = now(), failures = 0, disabled_at = null`,
    [token, platform, place, topics, govs, zone, pt[0], pt[1], radius, ver]);
    return res.status(200).json({ok: true, topics, govs, zone, saved_place: pt[0] != null, radius_mi: radius, sending: P.ready()[platform]});
  } catch (e) {
    console.error('push register', e.message);
    return res.status(500).json({ok: false, error: 'Couldn’t save your choices. Try again.'});
  }
};
