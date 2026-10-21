-- 0008: meeting agenda items, change tracking for the API, and rule-based email alerts.

-- data/meetings/fetch_meetings.py now publishes every agenda item title (not just money items) as agenda_items.
alter table meetings add column if not exists "agenda_items" jsonb;

-- Change tracking. Every dataset table already has created_at / updated_at in 0001; this adds them to any that
-- lack them (e.g. tables added later by hand). From this migration on, db/scripts/load.py keeps rows whose
-- record_hash didn't change instead of reloading everything, so created_at is the first sync that saw a row.
do $$
declare t text;
begin
  for t in select table_name from datasets loop
    if to_regclass(t) is null then continue; end if;
    execute format('alter table %I add column if not exists created_at timestamptz not null default now()', t);
    execute format('alter table %I add column if not exists updated_at timestamptz not null default now()', t);
    execute format('create index if not exists %I on %I (created_at)', t || '_created_idx', t);
  end loop;
end $$;
alter table ingest_runs add column if not exists rows_added integer;

-- Rule-based alerts. Private schema (created in 0007), not exposed by Supabase's public data API.
create schema if not exists alerts;

-- One row per confirmed alert rule. Rows are only written after the address confirms (double opt-in), so
-- confirmed is true for every row the app writes; the column is kept for rows added by hand.
create table if not exists alerts.subscriptions (
  id bigint generated always as identity primary key,
  email text not null,                       -- lower-cased
  confirmed boolean not null default false,
  confirmed_at timestamptz,
  rule_type text not null check (rule_type in ('contract', 'vote', 'keyword', 'campaign')),
  params jsonb not null default '{}'::jsonb, -- contract {gov, min}; vote {member}; keyword {keyword, gov?}; campaign {candidate}
  created_at timestamptz not null default now(),
  unsubscribed_at timestamptz
);
create unique index if not exists subscriptions_rule_uq on alerts.subscriptions (email, rule_type, md5(params::text));
create index if not exists subscriptions_email_idx on alerts.subscriptions (email);

-- New rows found by each database sync (load.py compares record_hash with the previous sync), for the datasets
-- rules can match. processed_at is set once the daily alerts run has looked at the event.
create table if not exists alerts.events (
  id bigint generated always as identity primary key,
  dataset text not null,
  record_hash text not null,
  government_key text,
  record jsonb not null,
  ingest_run_id bigint references public.ingest_runs(id) on delete set null,
  detected_at timestamptz not null default now(),
  processed_at timestamptz
);
create index if not exists events_unprocessed_idx on alerts.events (id) where processed_at is null;

-- Emails built by the daily alerts run. status: draft (waiting for review), sent, failed.
create table if not exists alerts.outbox (
  id bigint generated always as identity primary key,
  email text not null,
  subject text not null,
  html text not null,
  text text not null,
  matches integer not null,
  status text not null default 'draft' check (status in ('draft', 'sent', 'failed')),
  error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);
create index if not exists outbox_draft_idx on alerts.outbox (id) where status = 'draft';

-- What each rule has already matched, so the same record is never sent twice for one rule.
create table if not exists alerts.deliveries (
  subscription_id bigint not null references alerts.subscriptions(id) on delete cascade,
  dedupe_key text not null,
  outbox_id bigint references alerts.outbox(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (subscription_id, dedupe_key)
);

alter table alerts.subscriptions enable row level security;
alter table alerts.events enable row level security;
alter table alerts.outbox enable row level security;
alter table alerts.deliveries enable row level security;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema alerts from anon, authenticated';
  end if;
end $$;
