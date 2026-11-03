-- Records requests drafted automatically when a source goes stale (data/civic/scripts/stale_requests.py), and a locked
-- history of everything that happens to each request.
--
-- kind: 'budget' (the missing budget years, 0046) or 'stale' (a source whose newest official record is older than its
-- usual schedule). gap_ids: one id per gap ("beach-water:Bay11:2025-05-05"). A gap already in a sent or dismissed
-- request is never drafted again (api/_records_requests.js seedStale). group_key ties drafts from the same check and
-- custodian together, so a check keeps one open draft at a time.
-- status 'dismissed': an admin decided not to send it (with a reason), or the gap closed because newer records showed up.
alter table corr.records_requests add column if not exists kind text not null default 'budget';
alter table corr.records_requests add column if not exists group_key text;
alter table corr.records_requests add column if not exists gap_ids text[] not null default '{}';
alter table corr.records_requests add column if not exists check_title text;
alter table corr.records_requests add column if not exists page text;
alter table corr.records_requests add column if not exists dismissed_at timestamptz;
alter table corr.records_requests add column if not exists dismissed_by text;
alter table corr.records_requests add column if not exists dismissed_reason text;
alter table corr.records_requests drop constraint if exists records_requests_status_check;
alter table corr.records_requests add constraint records_requests_status_check
  check (status in ('draft', 'sent', 'received', 'closed', 'dismissed'));
create index if not exists corr_rr_gap_ids on corr.records_requests using gin (gap_ids);
create index if not exists corr_rr_group on corr.records_requests (group_key) where status = 'draft';

-- Every action on a request: drafted, refreshed, edited, test sent, sent, dismissed, closed by newer records.
-- Append-only and hash-chained (same pattern as gov.audit_log, 0093): changing or removing a row breaks the chain.
create table if not exists corr.records_request_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default clock_timestamp(),
  request_id bigint not null,
  actor text not null,                           -- the admin's email, or 'system' for the automatic check
  action text not null,
  detail jsonb not null default '{}',
  prev_hash text not null,
  hash text not null unique
);
create index if not exists corr_rr_log_request on corr.records_request_log (request_id, id);
alter table corr.records_request_log enable row level security;
revoke all on corr.records_request_log from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on corr.records_request_log from anon, authenticated';
  end if;
end $$;

create or replace function corr.rr_log_payload(a corr.records_request_log) returns text language sql immutable as $$
  select concat_ws('|', a.prev_hash, to_char(a.at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'), a.request_id::text, a.actor, a.action, a.detail::text)
$$;

create or replace function corr.rr_log_chain() returns trigger language plpgsql as $$
begin
  perform pg_advisory_xact_lock(hashtext('corr.records_request_log'));
  new.at := clock_timestamp();
  new.prev_hash := coalesce((select hash from corr.records_request_log order by id desc limit 1), repeat('0', 64));
  new.hash := encode(sha256(convert_to(corr.rr_log_payload(new), 'UTF8')), 'hex');
  return new;
end $$;
drop trigger if exists rr_log_chain on corr.records_request_log;
create trigger rr_log_chain before insert on corr.records_request_log for each row execute function corr.rr_log_chain();

create or replace function corr.rr_log_locked() returns trigger language plpgsql as $$
begin
  raise exception 'corr.records_request_log is locked: rows can''t be changed or deleted';
end $$;
drop trigger if exists rr_log_locked on corr.records_request_log;
create trigger rr_log_locked before update or delete on corr.records_request_log for each row execute function corr.rr_log_locked();
drop trigger if exists rr_log_no_truncate on corr.records_request_log;
create trigger rr_log_no_truncate before truncate on corr.records_request_log execute function corr.rr_log_locked();

-- Ids of rows whose hash no longer matches (empty when the history is intact).
create or replace function corr.rr_log_breaks() returns table (id bigint, problem text) language sql stable as $$
  with c as (select a as r, a.id, a.hash, a.prev_hash, lag(a.hash) over (order by a.id) as before from corr.records_request_log a)
  select c.id, case when c.prev_hash <> coalesce(c.before, repeat('0', 64)) then 'does not follow the row before it' else 'row was changed' end
  from c
  where c.prev_hash <> coalesce(c.before, repeat('0', 64))
     or c.hash <> encode(sha256(convert_to(corr.rr_log_payload(c.r), 'UTF8')), 'hex')
$$;
