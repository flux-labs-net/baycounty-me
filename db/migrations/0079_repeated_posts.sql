-- Repeated posts: the same notice, event or job listed twice (a city re-posting an alert with an update, a legal notice
-- run on several days, one event on two calendars). data/dupes.py and api/_dupes.js find them by source, time, title and
-- text; every row stays on file, and pages, apps and the API show the kept row only.
--
-- 1. same_as on emergency_notices, public_notices, community_events and job_openings: on a repeated row, the id of the row
--    kept for it (notice_id, event_id or job_id). first_posted on a kept row: when the earliest version was posted.
-- 2. name_match_reviews.kind: 'name' for look-alike business names (as before), 'repeat' for possible repeated posts that
--    need a person's call on /admin > Name matches (confirmed = one post, rejected = keep apart). The live alerts feed
--    reads the calls directly; data/entities/export_name_decisions.py exports them to data/dupes/decisions.json for the build.

alter table emergency_notices add column if not exists "same_as" text;
alter table emergency_notices add column if not exists "first_posted" text;
alter table public_notices add column if not exists "same_as" text;
alter table public_notices add column if not exists "first_posted" text;
alter table community_events add column if not exists "same_as" text;
alter table community_events add column if not exists "first_posted" text;
alter table job_openings add column if not exists "same_as" text;
alter table job_openings add column if not exists "first_posted" text;

alter table name_match_reviews add column if not exists kind text not null default 'name';
alter table name_match_reviews drop constraint if exists name_match_reviews_kind_check;
alter table name_match_reviews add constraint name_match_reviews_kind_check check (kind in ('name', 'repeat'));
