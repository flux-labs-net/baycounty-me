-- Alert text messages (BayCounty.me alerts, phase 3). Sent from a Telnyx toll-free number (api/_sms.js).
-- Private like the rest of schema `account`: phone numbers are only read and written by server-side code, shown back
-- only to their owner (masked), never published or logged, and deleting the account deletes the number.
--
-- account.sms: one phone per account. status pending (code sent, not confirmed), active, or stopped (the person
--   texted STOP, or turned texts off). Only a hash of the confirm code is kept; a code lasts 15 minutes and allows 5 tries.
-- account.prefs.alert_sms: alert types that also come by text (only types whose channels include 'sms').
-- account.sms_log: every text sent (kind, segments and estimated cost, never the number or the message), so the
--   monthly spend can be capped and shown on /admin. Rows outlive a deleted account (user_id set null) so the month's
--   spend stays right.
-- account.sms_settings: one row. monthly_cap in US dollars; paused stops all texts at once.

create table if not exists account.sms (
  user_id uuid primary key references account.users(id) on delete cascade,
  phone text not null check (phone ~ '^\+1[2-9][0-9]{9}$'),
  status text not null default 'pending' check (status in ('pending', 'active', 'stopped')),
  code_hash text,
  code_expires timestamptz,
  attempts int not null default 0,
  consent_at timestamptz not null default now(),
  confirmed_at timestamptz,
  stopped_at timestamptz,
  updated_at timestamptz not null default now()
);
-- One account per confirmed number; a number can be pending on more than one account until someone confirms it.
create unique index if not exists account_sms_active_phone on account.sms (phone) where status = 'active';
create index if not exists account_sms_phone_idx on account.sms (phone);

alter table account.prefs add column if not exists alert_sms text[] not null default array['evacuation', 'weather', 'safety'];

create table if not exists account.sms_log (
  id bigint generated always as identity primary key,
  user_id uuid references account.users(id) on delete set null,
  kind text not null check (kind in ('alert', 'code', 'help', 'start', 'test')),
  notice_id text,
  segments int not null default 1,
  cost numeric(10, 4) not null default 0,
  provider_id text,
  ok boolean not null default true,
  sent_at timestamptz not null default now()
);
create unique index if not exists account_sms_log_alert on account.sms_log (user_id, notice_id) where kind = 'alert';
create index if not exists account_sms_log_sent_idx on account.sms_log (sent_at);

create table if not exists account.sms_settings (
  id boolean primary key default true check (id),
  monthly_cap numeric(10, 2) not null default 150 check (monthly_cap >= 0),
  paused boolean not null default false,
  cap_hit_month text,
  updated_by text,
  updated_at timestamptz not null default now()
);
insert into account.sms_settings (id) values (true) on conflict (id) do nothing;

alter table account.sms enable row level security;
alter table account.sms_log enable row level security;
alter table account.sms_settings enable row level security;
