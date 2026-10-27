// GET /api/emergency-run?place=fl-bay : check every emergency source now (see _emergency_run.js).
// Public on purpose: the database's cron job calls it every 5 minutes without a secret. It only reads public feeds,
// runs at most once per ~2 minutes per place, and never sends the same notification twice, so extra calls do nothing.
// With Authorization: Bearer <CRON_SECRET>, ?force=1 skips the 2-minute wait (for testing).
const {run} = require('./_emergency_run');

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  if (req.method !== 'GET' && req.method !== 'POST') return res.status(405).json({error: 'Use GET.'});
  const place = String(req.query.place || 'fl-bay').replace(/[^a-z-]/g, '').slice(0, 40);
  const authed = !!process.env.CRON_SECRET && req.headers.authorization === `Bearer ${process.env.CRON_SECRET}`;
  try {
    const r = await run(place, {force: authed && req.query.force === '1'});
    // The public answer leaves out per-notice push counts.
    return res.status(200).json(authed ? r : {place: r.place, throttled: !!r.throttled, checked_at: r.checked_at, active: r.active, errors: (r.errors || []).length});
  } catch (e) {
    console.error('emergency-run', e);
    return res.status(e.status || 500).json({error: e.expose ? e.message : 'The check failed. It will run again shortly.'});
  }
};
