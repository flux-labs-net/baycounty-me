// Anonymous app usage counts (db/migrations/0082_app_usage.sql). The apps send one check-in a day (api/app-usage.js);
// /admin > App usage reads report(). Nothing that could pick out a person is taken in or stored: no device id, account,
// address or IP address, only daily totals by platform, app version and screen.
const db = require('./_db');

const SCREEN = /^[a-z0-9][a-z0-9:/_-]{0,59}$/;
const VERSION = /^[0-9A-Za-z .()_-]{1,24}$/;

// The check-in body, checked and trimmed. Returns null when it isn't one.
//   {platform: 'ios'|'android', version: '1.4 (12)', new: bool, month: bool, week: bool, opens: n, screens: {name: n}}
function parse(b) {
  if (!b || typeof b !== 'object') return null;
  const platform = b.platform === 'ios' || b.platform === 'android' ? b.platform : null;
  if (!platform) return null;
  const version = VERSION.test(String(b.version || '')) ? String(b.version).trim() : '';
  const count = (v, max) => Math.max(0, Math.min(max, Math.floor(Number(v) || 0)));
  const screens = {};
  if (b.screens && typeof b.screens === 'object' && !Array.isArray(b.screens)) {
    for (const [k, v] of Object.entries(b.screens).slice(0, 120)) {
      const name = String(k).toLowerCase();
      const n = count(v, 2000);
      if (SCREEN.test(name) && n > 0) screens[name] = (screens[name] || 0) + n;
    }
  }
  return {platform, version, isNew: b.new === true, month: b.month === true, week: b.week === true, opens: count(b.opens, 500), screens};
}

const DAY = `(now() at time zone 'America/Chicago')::date`;

async function record(p, place = 'fl-bay') {
  await db.q(`insert into appusage.app_days (day, place_id, platform, app_version, users, new_users, month_users, week_users, opens)
              values (${DAY}, $1, $2, $3, 1, $4, $5, $6, $7)
              on conflict (day, place_id, platform, app_version) do update set users = app_days.users + 1,
                new_users = app_days.new_users + excluded.new_users, month_users = app_days.month_users + excluded.month_users,
                week_users = app_days.week_users + excluded.week_users, opens = app_days.opens + excluded.opens`,
    [place, p.platform, p.version, p.isNew ? 1 : 0, p.month ? 1 : 0, p.week ? 1 : 0, p.opens]);
  const names = Object.keys(p.screens);
  if (names.length) {
    await db.q(`insert into appusage.app_screens (day, place_id, platform, screen, views)
                select ${DAY}, $1, $2, s, v from unnest($3::text[], $4::int[]) as t(s, v)
                on conflict (day, place_id, platform, screen) do update set views = app_screens.views + excluded.views`,
      [place, p.platform, names, names.map(n => p.screens[n])]);
  }
}

// For /admin: daily users by platform, monthly users, new installs, versions, top screens, plus the phones signed up
// for alerts and My home accounts (existing tables), over the last `days` days.
async function report(days = 30) {
  const d = Math.min(Math.max(parseInt(days, 10) || 30, 7), 365);
  const W = `day > ${DAY} - $1::int`;
  const [daily, totals, months, versions, screens, extra] = await Promise.all([
    db.q(`with g as (select generate_series(${DAY} - ($1::int - 1), ${DAY}, interval '1 day')::date as day)
          select to_char(g.day, 'YYYY-MM-DD') as day,
            coalesce(sum(a.users) filter (where a.platform = 'ios'), 0)::int ios,
            coalesce(sum(a.users) filter (where a.platform = 'android'), 0)::int android,
            coalesce(sum(a.new_users), 0)::int new_users, coalesce(sum(a.opens), 0)::int opens
          from g left join appusage.app_days a on a.day = g.day group by g.day order by g.day`, [d]),
    db.q(`select platform, sum(users)::int checkins, sum(new_users)::int new_users, sum(opens)::int opens,
            coalesce(sum(users) filter (where day = ${DAY}), 0)::int today
          from appusage.app_days where ${W} group by platform`, [d]),
    db.q(`select to_char(date_trunc('month', day), 'YYYY-MM') as month, platform, sum(month_users)::int users, sum(new_users)::int new_users
          from appusage.app_days where day >= date_trunc('month', ${DAY}) - interval '5 months' group by 1, 2 order by 1`),
    db.q(`select platform, app_version, sum(users)::int users from appusage.app_days where day > ${DAY} - 7
          group by 1, 2 order by 3 desc limit 12`),
    db.q(`select screen, sum(views)::int views, sum(views) filter (where platform = 'ios')::int ios, sum(views) filter (where platform = 'android')::int android
          from appusage.app_screens where ${W} group by 1 order by 2 desc limit 25`, [d]),
    db.q(`select (select count(*)::int from push.devices where platform = 'ios') push_ios,
            (select count(*)::int from push.devices where platform = 'android') push_android,
            (select count(*)::int from account.users) accounts,
            (select count(*)::int from account.users where created_at > now() - make_interval(days => $1::int)) new_accounts`, [d])
      .catch(() => [{}]),
  ]);
  const [wk] = await db.q(`select coalesce(sum(week_users) filter (where platform = 'ios'), 0)::int ios,
      coalesce(sum(week_users) filter (where platform = 'android'), 0)::int android
      from appusage.app_days where day >= date_trunc('week', ${DAY})`);
  return {days: d, daily, totals, months, versions, screens, week: wk, ...extra[0]};
}

module.exports = {parse, record, report, SCREEN};
