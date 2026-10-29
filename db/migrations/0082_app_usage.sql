-- Anonymous app usage counts for the iOS and Android apps (api/app-usage.js, shown in /admin > App usage).
--
-- Once a day, when the app opens, it sends one check-in: the platform, the app version, whether this is the phone's
-- first check-in ever, its first this month and this week, how many times the app was opened and which screens were
-- viewed since the last check-in. No device id, account, address, IP address or anything else that could pick out a
-- person is sent or stored: only these daily totals. A resident can turn the check-in off in the app.
--
-- Private: schema `appusage`, read and written only by server-side code through the service connection.
-- Keyed by place for other counties.

create schema if not exists appusage;
revoke all on schema appusage from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema appusage from anon, authenticated'; end if;
end $$;

-- One row per Central-time day, place, platform and app version.
--   users          phones that checked in that day (daily active users)
--   new_users      phones checking in for the first time (new installs)
--   month_users    phones checking in for the first time that calendar month (sum over a month = monthly active users)
--   week_users     the same for the week starting Monday (sum over a week = weekly active users)
--   opens          times the app was opened, as reported in the check-ins that day
create table if not exists appusage.app_days (
  day date not null,
  place_id text not null default 'fl-bay',
  platform text not null check (platform in ('ios', 'android')),
  app_version text not null default '',
  users int not null default 0,
  new_users int not null default 0,
  month_users int not null default 0,
  week_users int not null default 0,
  opens int not null default 0,
  primary key (day, place_id, platform, app_version)
);

-- Screens viewed, totalled by the day the check-in arrived. screen is a short name such as 'today', 'restaurants' or
-- 'dataset/votes' (never a person, address or search).
create table if not exists appusage.app_screens (
  day date not null,
  place_id text not null default 'fl-bay',
  platform text not null check (platform in ('ios', 'android')),
  screen text not null check (screen ~ '^[a-z0-9][a-z0-9:/_-]{0,59}$'),
  views int not null default 0,
  primary key (day, place_id, platform, screen)
);
create index if not exists app_screens_day on appusage.app_screens (day);
