// Anonymous daily check-in from the BayCounty.me apps.
//   POST /api/app-usage {platform: 'ios'|'android', version, new, month, week, opens, screens: {name: count}}
// The apps send this at most once a day, and not at all when the resident turns "Share anonymous usage counts" off.
// Only daily totals are kept (api/_app_usage.js): no device id, account, address or IP address is stored.
const {ipOf} = require('./_gate');
const db = require('./_db');
const U = require('./_app_usage');

// A light per-instance limit so one address can't flood the counts. The address is only held in memory for an hour.
const hits = new Map();

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'POST') return res.status(405).json({ok: false, error: 'Use POST.'});
  const ip = ipOf(req), now = Date.now();
  const recent = (hits.get(ip) || []).filter(t => now - t < 3600e3);
  if (recent.length >= 30) return res.status(429).json({ok: false, error: 'Too many check-ins. Try again later.'});
  recent.push(now); hits.set(ip, recent);
  if (hits.size > 5000) for (const [k, v] of hits) if (!v.some(t => now - t < 3600e3)) hits.delete(k);
  let b = req.body; if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = null; } }
  const p = U.parse(b);
  if (!p) return res.status(400).json({ok: false, error: 'platform must be ios or android.'});
  if (!db.hasDb()) return res.status(202).json({ok: true, stored: false});
  try {
    await U.record(p);
    return res.status(200).json({ok: true});
  } catch (e) {
    console.error('app-usage', e.message);
    return res.status(500).json({ok: false, error: 'Couldn’t save the check-in.'});
  }
};
