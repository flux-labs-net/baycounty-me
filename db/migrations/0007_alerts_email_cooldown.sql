-- Email alerts: a private schema for sign-up bookkeeping (not exposed by Supabase's public data API).
-- This migration adds the per-address cooldown for confirmation emails: at most one confirmation email
-- per address every 10 minutes, across every server instance. Addresses are stored as a salted hash only.
create schema if not exists alerts;
revoke all on schema alerts from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema alerts from anon, authenticated'; end if;
end $$;

create table if not exists alerts.confirm_sends (
  email_hash text primary key,           -- HMAC of the lower-cased address (api/_alerts.js emailHash)
  last_sent_at timestamptz not null default now()
);
alter table alerts.confirm_sends enable row level security;

-- Returns true (and records the send) if no confirmation went to this address in the last p_minutes.
create or replace function alerts.claim_confirm_send(p_email_hash text, p_minutes integer default 10)
returns boolean language plpgsql set search_path = '' as $$
declare n integer;
begin
  insert into alerts.confirm_sends as c (email_hash, last_sent_at) values (p_email_hash, now())
    on conflict (email_hash) do update set last_sent_at = now()
    where c.last_sent_at < now() - make_interval(mins => p_minutes);
  get diagnostics n = row_count;
  if random() < 0.01 then delete from alerts.confirm_sends where last_sent_at < now() - interval '2 days'; end if;
  return n > 0;
end $$;
revoke all on function alerts.claim_confirm_send(text, integer) from public;
