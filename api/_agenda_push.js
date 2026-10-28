// Phone notifications for agenda items near a saved place. The agenda reader (data/agendas/extract_agendas.py) records
// each new item as an alerts.events row (dataset 'agenda-items') with the street addresses the item names. Here each
// new item's first address that matches a county address point is placed on the map (cached in push.agenda_points),
// and phones that turned on "Agenda items near me" and saved a point within their radius get one notification.
// Runs inside the emergency check (api/_emergency_run.js) at most once an hour.
const E = require('./_emergency');
const db = require('./_db');
const P = require('./_push');
const {miles} = require('./_geo');

const DAYS_BACK = 3;          // events detected longer ago than this are left alone (a backfill isn't news)
const GEOCODE_MAX = 25;       // addresses looked up per run
const GOV_NAME = Object.fromEntries((require('../places/fl-bay/place.json').governments || []).map(g => [g.key, g.short || g.name]));
const govName = board => GOV_NAME[String(board || '').split('-')[0]] || 'A local board';

// The notification text for one agenda item. No address in the text: the item may name a private home.
function message(pt) {
  const md = pt.meeting_date instanceof Date ? pt.meeting_date.toISOString().slice(0, 10) : pt.meeting_date;
  const day = md ? new Date(md + 'T12:00:00').toLocaleDateString('en-US', {month: 'short', day: 'numeric', timeZone: 'America/Chicago'}) : null;
  return {notice_id: 'agenda:' + pt.record_hash, topic: 'agenda', title: `Near you: ${govName(pt.board)} agenda${day ? ', ' + day : ''}`,
    body: E.clip(pt.title, 170) + ' (on the agenda near your saved place)', url: pt.url || 'https://baycounty.me/meetings'};
}

async function placeNew(place) {
  const ev = await db.q(`select e.record_hash, e.record from alerts.events e
      where e.dataset = 'agenda-items' and e.detected_at > now() - make_interval(days => $1)
        and jsonb_array_length(coalesce(e.record->'addresses', '[]'::jsonb)) > 0
        and not exists (select 1 from push.agenda_points p where p.record_hash = e.record_hash)
      order by e.id desc limit $2`, [DAYS_BACK, GEOCODE_MAX]);
  let placed = 0;
  for (const {record_hash, record: r} of ev) {
    let hit = null;
    for (const a of (r.addresses || []).slice(0, 3)) {
      if (!/^\s*\d+\s+\S/.test(a)) continue;           // parcel numbers and areas without a house number are skipped
      hit = await E.geocode(a, place).catch(() => null);
      if (hit) break;
    }
    await db.q(`insert into push.agenda_points (record_hash, place_id, board, meeting_date, title, url, lat, lng)
      values ($1, $2, $3, $4, $5, $6, $7, $8) on conflict (record_hash) do nothing`,
    [record_hash, place, r.board || null, /^\d{4}-\d\d-\d\d/.test(r.meeting_date || '') ? r.meeting_date.slice(0, 10) : null, E.clip(r.title, 300), r.agenda_url || null, hit ? hit.lat : null, hit ? hit.lng : null]);
    if (hit) placed++;
  }
  return {looked_at: ev.length, placed};
}

async function pushNear(place, today) {
  const pts = await db.q(`select p.* from push.agenda_points p where p.place_id = $1 and p.lat is not null and (p.meeting_date is null or p.meeting_date >= $2::date)
      and not exists (select 1 from push.sent s where s.notice_id = 'agenda:' || p.record_hash) limit 50`, [place, today]);
  if (!pts.length) return [];
  const devs = await db.q(`select token, platform, lat, lng, radius_mi from push.devices where place_id = $1 and disabled_at is null and 'agenda' = any(topics) and lat is not null`, [place]);
  const sent = [];
  for (const pt of pts) {
    const msg = message(pt);
    const claimed = await db.q(`insert into push.sent (notice_id, place_id, topic, dedupe_key, title) values ($1, $2, 'agenda', $1, $3) on conflict (notice_id) do nothing returning notice_id`, [msg.notice_id, place, pt.title]);
    if (!claimed.length) continue;
    const near = devs.filter(d => miles({lat: +d.lat, lng: +d.lng}, {lat: +pt.lat, lng: +pt.lng}) <= (+d.radius_mi || 1));
    const res = near.length ? await P.send(near, msg) : {delivered: 0, failed: 0, dead: []};
    await db.q('update push.sent set devices = $2, delivered = $3, failed = $4 where notice_id = $1', [msg.notice_id, near.length, res.delivered, res.failed]);
    if (res.dead.length) await db.q('update push.devices set disabled_at = now() where token = any($1::text[])', [res.dead]);
    sent.push({notice_id: msg.notice_id, devices: near.length, delivered: res.delivered});
  }
  return sent;
}

async function run(place = 'fl-bay', now = new Date()) {
  const today = now.toLocaleDateString('en-CA', {timeZone: 'America/Chicago'});
  const placed = await placeNew(place);
  const pushed = await pushNear(place, today);
  return {...placed, pushed};
}

module.exports = {run, message, placeNew, pushNear};
