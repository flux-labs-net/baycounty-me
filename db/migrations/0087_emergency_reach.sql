-- How many people each emergency notice reached, per channel (push, email, later sms), for the alert timeline on
-- /emergency and /api/v1/emergency-timeline. Counts only: no tokens, emails or phone numbers. Written by the poller
-- (api/_emergency_run.js, api/_account.js) with the server-side connection; anyone can read it, like emergency_live.
create table if not exists emergency_reach (
  notice_id text not null,
  channel text not null check (channel in ('push', 'email', 'sms')),
  place_id text not null,
  people integer not null default 0,
  delivered integer not null default 0,
  sent_at timestamptz not null default now(),
  primary key (notice_id, channel)
);
create index if not exists emergency_reach_place_idx on emergency_reach (place_id, sent_at desc);
alter table emergency_reach enable row level security;
drop policy if exists "public read" on emergency_reach;
create policy "public read" on emergency_reach for select using (true);

-- Push sends so far, so the timeline has counts from the start.
insert into emergency_reach (notice_id, channel, place_id, people, delivered, sent_at)
  select notice_id, 'push', place_id, devices, delivered, sent_at from push.sent where not suppressed and devices > 0
  on conflict (notice_id, channel) do nothing;

-- Email alerts so far (account.sends rows of kind 'alert' are keyed by notice id).
insert into emergency_reach (notice_id, channel, place_id, people, delivered, sent_at)
  select s.dedupe_key, 'email', coalesce(max(l.place_id), 'fl-bay'), count(*)::int, count(*)::int, min(s.sent_at)
  from account.sends s left join emergency_live l on l.notice_id = s.dedupe_key
  where s.kind = 'alert' group by s.dedupe_key
  on conflict (notice_id, channel) do nothing;
