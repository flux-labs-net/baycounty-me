// One check of every emergency source for a place: store what's live in emergency_live, the shelter status in
// emergency_state, and send phone notifications for new evacuation orders, warnings, shelter openings and boil-water
// notices, and (hourly) for agenda items near a phone's saved place (api/_agenda_push.js). Called every 5 minutes by the database (pg_cron, see 0067_emergency.sql) through api/emergency-run.js, and
// by /api/v1/emergency when the last check is old. At most one check per place every ~2 minutes (claimed in emergency_state).
const E = require('./_emergency');
const db = require('./_db');
const P = require('./_push');
const D = require('./_dupes');

const MIN_GAP_S = 110;
const PUSH_MAX_AGE_H = 24;      // a notice first issued longer ago than this is recorded but not pushed (e.g. on first run)
const WEATHER_REPEAT_H = 12;    // the same weather event (e.g. Hurricane Warning) is pushed at most once in this window
const COLS = ['notice_id', 'place_id', 'kind', 'source', 'source_type', 'gov_id', 'title', 'summary', 'instruction', 'severity', 'event', 'area', 'zones',
  'issued', 'starts', 'ends', 'updated', 'status', 'full_closure', 'roadway', 'url', 'source_url'];

// Which reader a notice came from, so a notice only ends when its own source answered without it.
function sourceKey(n) {
  if (n.source_type === 'nws') return 'nws';
  if (n.source_type === 'alert-center') return 'alert:' + n.gov_id;
  if (n.source_type === 'news') return 'news:' + n.gov_id;
  if (n.source_type === 'fl511') return 'fl511:' + ({Incident: 'Incidents', Closure: 'Closures', Construction: 'Construction'}[n.event] || 'Closures');
  if (n.source_type === 'shelters') return 'shelters';
  if (n.source_type === 'status-page') return 'page:' + n.gov_id;
  return n.source_type;
}

async function claim(place) {
  const r = await db.q(`insert into emergency_state (place_id, started_at) values ($1, now())
    on conflict (place_id) do update set started_at = now()
      where emergency_state.started_at is null or emergency_state.started_at < now() - make_interval(secs => $2)
    returning place_id`, [place, MIN_GAP_S]);
  return r.length > 0;
}

async function store(place, notices, ok) {
  // The map shape (staff alerts) is written only when a notice has one, so a run before migration 0090 still stores.
  const cols = notices.some(n => n.geometry) ? [...COLS, 'geometry'] : COLS;
  const rows = notices.map(n => ({...Object.fromEntries(cols.map(c => [c, n[c] ?? null])), push_topic: E.pushTopic(n), active: n.status === 'active'}));
  if (rows.length) {
    await db.q(`insert into emergency_live (${cols.join(', ')}, push_topic, active)
      select ${cols.join(', ')}, push_topic, active from json_populate_recordset(null::emergency_live, $1::json)
      on conflict (notice_id) do update set ${[...cols.filter(c => c !== 'notice_id'), 'push_topic', 'active'].map(c => `${c} = excluded.${c}`).join(', ')}, last_seen = now()`,
    [JSON.stringify(rows)]);
  }
  // End notices that their source no longer lists (only for sources that answered this time).
  const live = await db.q('select notice_id, source_type, gov_id, event from emergency_live where place_id = $1 and active', [place]);
  const now = new Set(notices.filter(n => n.status === 'active').map(n => n.notice_id)), okSet = new Set(ok);
  const gone = live.filter(r => !now.has(r.notice_id) && okSet.has(sourceKey(r))).map(r => r.notice_id);
  if (gone.length) await db.q('update emergency_live set active = false where notice_id = any($1::text[])', [gone]);
  return gone.length;
}

// Signed-in phones that want this notice (only phones tied to an account get alerts): the topic is on, and the notice's government is one they follow (or they follow all).
// A staff alert for one city goes to phones following that city; a countywide one (or one from the county) to all.
function govFilter(n) {
  if (n.source_type === 'staff') return n.area === require('./_gov').COUNTYWIDE || n.gov_id === 'county' ? null : n.gov_id;
  return E.LOCAL_KINDS.includes(n.kind) ? n.gov_id : null;
}
async function devicesFor(place, topic, n) {
  return db.q(`select token, platform, quiet from push.devices where place_id = $1 and disabled_at is null and user_id is not null and topics && $2::text[]
      and ($3::text is null or cardinality(govs) = 0 or $3 = any(govs))`, [place, E.topicsFor(topic), govFilter(n)]);
}

// How many people a notice reached per channel, for the alert timeline (emergency_reach, counts only).
async function reach(noticeId, place, rows) {
  const keep = rows.filter(r => r[1] > 0);
  if (!keep.length) return;
  try {
    await db.q(`insert into emergency_reach (notice_id, channel, place_id, people, delivered)
        select $1, x.channel, $2, x.people, x.delivered from json_to_recordset($3::json) as x(channel text, people int, delivered int)
        on conflict (notice_id, channel) do update set people = excluded.people, delivered = excluded.delivered`,
    [noticeId, place, JSON.stringify(keep.map(([channel, people, delivered]) => ({channel, people, delivered})))]);
  } catch (e) { console.error('emergency reach', e.message); }
}

// repeats: notice_id -> the other notice_ids of the same post (api/_dupes.js); a repeat of a post already sent is not sent again.
async function pushNew(place, notices, nowMs = Date.now(), repeats = new Map()) {
  const sent = [];
  for (const n of notices) {
    const topic = E.pushTopic(n);
    if (!topic) continue;
    const dedupe = topic === 'weather' ? `weather:${n.event}` : n.notice_id;
    const issued = Date.parse(n.issued || n.updated || '') || nowMs;
    const stale = nowMs - issued > PUSH_MAX_AGE_H * 3600e3;
    let suppressed = stale;
    if (!suppressed && topic === 'weather') {
      const r = await db.q(`select 1 from push.sent where place_id = $1 and dedupe_key = $2 and sent_at > now() - make_interval(hours => $3) and not suppressed limit 1`, [place, dedupe, WEATHER_REPEAT_H]);
      suppressed = r.length > 0;
    }
    if (!suppressed && (repeats.get(n.notice_id) || []).length) {
      const r = await db.q(`select 1 from push.sent where notice_id = any($1::text[]) and not suppressed limit 1`, [repeats.get(n.notice_id)]);
      suppressed = r.length > 0;
    }
    // Claim the notice first, so two overlapping runs can never send it twice.
    const claimed = await db.q(`insert into push.sent (notice_id, place_id, topic, dedupe_key, title, suppressed) values ($1, $2, $3, $4, $5, $6)
      on conflict (notice_id) do nothing returning notice_id`, [n.notice_id, place, topic, dedupe, n.title, suppressed]);
    if (!claimed.length || suppressed) continue;
    const devices = await devicesFor(place, topic, n);
    // Quiet hours: phones that asked for them get standard alerts silently overnight; urgent ones still sound.
    const hush = E.quietNow(nowMs) && !E.isUrgent(n, topic);
    const loud = hush ? devices.filter(d => !d.quiet) : devices, soft = hush ? devices.filter(d => d.quiet) : [];
    const res = {delivered: 0, failed: 0, skipped: 0, dead: []};
    for (const [group, quiet] of [[loud, false], [soft, true]]) {
      if (!group.length) continue;
      const r = await P.send(group, {...P.message(n, topic), quiet});
      res.delivered += r.delivered; res.failed += r.failed; res.skipped += r.skipped; res.dead.push(...r.dead);
    }
    await db.q('update push.sent set devices = $2, delivered = $3, failed = $4 where notice_id = $1', [n.notice_id, devices.length, res.delivered, res.failed]);
    if (res.dead.length) await db.q('update push.devices set disabled_at = now() where token = any($1::text[])', [res.dead]);
    if (res.delivered) await db.q('update emergency_live set pushed_at = now() where notice_id = $1', [n.notice_id]);
    // Residents with an account who asked for this topic by email, when the notice reaches their saved home (api/_account.js).
    let mail = {sent: 0, people: 0};
    try { mail = await require('./_account').emailNotice(place, n, topic); } catch (e) { console.error('account alert email', e.message); }
    await reach(n.notice_id, place, [['push', devices.length, res.delivered], ['email', mail.people || 0, mail.sent || 0]]);
    sent.push({notice_id: n.notice_id, topic, devices: devices.length, delivered: res.delivered});
  }
  return sent;
}

// City and county road closure posts name streets but have no map: place them on the street layer once
// (api/_road_map.js) and keep that map, or the empty "looked, found none" one, on every later check.
const ROAD_LOOKUPS_PER_RUN = 6;
async function placeRoads(place, notices) {
  const need = notices.filter(n => n.kind === 'road' && !n.geometry && n.source_type !== 'staff' && n.source_type !== 'fl511');
  if (!need.length) return 0;
  const had = new Map((await db.q('select notice_id, geometry from emergency_live where notice_id = any($1::text[]) and geometry is not null',
    [need.map(n => n.notice_id)]).catch(() => [])).map(r => [r.notice_id, r.geometry]));
  const R = require('./_road_map'), cfg = E.placeConfig(place);
  let looked = 0;
  for (const n of need) {
    if (had.has(n.notice_id)) { n.geometry = had.get(n.notice_id); continue; }
    if (looked++ >= ROAD_LOOKUPS_PER_RUN) continue;
    n.geometry = await R.streetMap(n, cfg, E.get).catch(() => null);
  }
  return looked;
}

async function run(place = 'fl-bay', {force = false} = {}) {
  E.placeConfig(place);
  if (!db.hasDb()) throw Object.assign(new Error('The database is not connected.'), {status: 503, expose: true});
  if (!force && !(await claim(place))) {
    const s = (await db.q('select checked_at, started_at from emergency_state where place_id = $1', [place]))[0] || {};
    return {place, throttled: true, checked_at: s.checked_at || null};
  }
  const t0 = Date.now();
  const r = await E.readAll(place);
  await placeRoads(place, r.notices);
  const ended = await store(place, r.notices, r.ok);
  // The same post listed twice is sent once, as its newest version (kept versions go first).
  const live = r.notices.filter(n => n.status === 'active');
  const reps = D.noticeGroups(live, await D.decisions());
  const repeats = new Map(reps.groups.flatMap(g => g.map(id => [id, g.filter(x => x !== id)])));
  live.sort((a, b) => (reps.same_as[a.notice_id] ? 1 : 0) - (reps.same_as[b.notice_id] ? 1 : 0));
  const pushed = await pushNew(place, live, Date.now(), repeats);
  let agenda = null;
  const due = await db.q(`update emergency_state set agenda_checked_at = now() where place_id = $1
      and (agenda_checked_at is null or agenda_checked_at < now() - interval '55 minutes') returning place_id`, [place]);
  if (due.length) {
    try { agenda = await require('./_agenda_push').run(place); } catch (e) { agenda = {error: e.message}; console.error('agenda push', e.message); }
  }
  const active = r.notices.filter(n => n.status === 'active').length;
  const ready = P.ready();
  await db.q(`update emergency_state set checked_at = now(), shelters = coalesce($2::jsonb, shelters), sources_ok = $3::jsonb, errors = $4::jsonb,
      notices_active = $5, pushed = coalesce(pushed, 0) + $6, push_ready = $7 where place_id = $1`,
  [place, r.shelters ? JSON.stringify(r.shelters) : null, JSON.stringify(r.ok), JSON.stringify(r.errors), active, pushed.length, ready.ios || ready.android]);
  return {place, checked_at: new Date().toISOString(), ms: Date.now() - t0, notices: r.notices.length, active, ended, pushed, agenda, errors: r.errors, sources_ok: r.ok};
}

module.exports = {run, placeRoads, sourceKey, store, pushNew, claim, reach, govFilter};
