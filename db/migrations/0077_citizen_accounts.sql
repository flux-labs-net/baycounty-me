-- Citizen accounts (/account and the apps' "My home"): a resident signs in with a code sent to their email, saves their
-- home address, and picks what BayCounty.me tells them about (a weekly email about their home, emails for emergencies
-- at their home, and phone notifications).
--
-- Private: schema `account`, read and written only by server-side code (api/_account.js through the service
-- connection). There are no passwords. The saved home is the person's own address, shown only back to them and used to
-- pick what is near them; it is never published, never in a dataset, never in a log, and deleting the account deletes
-- it. Everything shown on the "My home" page is public data from GET /api/v1/nearby. Keyed by place for other counties.

create schema if not exists account;
revoke all on schema account from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema account from anon, authenticated'; end if;
end $$;

-- One row per person. status: active, or paused (an admin turned them off).
create table if not exists account.users (
  id uuid primary key default gen_random_uuid(),
  place_id text not null default 'fl-bay',
  email text not null unique check (email = lower(email) and position('@' in email) > 1),
  first_name text check (first_name is null or length(first_name) <= 60),
  status text not null default 'active' check (status in ('active', 'paused')),
  created_at timestamptz not null default now(),
  last_login_at timestamptz,
  login_count int not null default 0
);

-- The saved home. lat/lon is the county address point. gov_id is the city it is in ('county' when unincorporated),
-- zone its hurricane evacuation zone, both worked out when it is saved.
create table if not exists account.homes (
  user_id uuid primary key references account.users(id) on delete cascade,
  place_id text not null default 'fl-bay',
  label text not null default 'Home' check (length(label) <= 40),
  address text not null check (length(address) <= 160),
  city text,
  zip text,
  parcel_id text,
  lat double precision not null,
  lon double precision not null,
  gov_id text,
  zone text,
  updated_at timestamptz not null default now()
);

-- What the person wants to hear about.
--   weekly_email   Monday email: what's coming up and new near home
--   alert_email    emergency topics also sent by email when they affect the home (evacuation for its zone, a
--                  boil-water notice for its city, weather warnings for the county)
--   push_topics    phone notification topics (copied to each signed-in phone in push.devices)
--   radius_mi      how far "near my home" reaches
create table if not exists account.prefs (
  user_id uuid primary key references account.users(id) on delete cascade,
  weekly_email boolean not null default true,
  alert_email text[] not null default array['evacuation', 'water'],
  push_topics text[] not null default array['weather', 'evacuation', 'shelters', 'water', 'agenda'],
  radius_mi numeric not null default 1 check (radius_mi in (0.25, 0.5, 1, 2, 5)),
  topics text[] not null default array['meetings', 'events', 'projects', 'notices', 'food', 'business'],
  updated_at timestamptz not null default now()
);

-- Sign-in codes. Only a hash of the code is kept; a code lasts 15 minutes, allows 5 tries and works once.
create table if not exists account.codes (
  id bigint generated always as identity primary key,
  email text not null,
  code_hash text not null,
  nonce text not null unique,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  attempts int not null default 0,
  used_at timestamptz
);
create index if not exists account_codes_email_idx on account.codes (email, created_at desc);

-- Signed-in browsers and phones. Only a hash of the session token is kept, so signing out (or deleting the account)
-- ends a session everywhere it is used.
create table if not exists account.sessions (
  token_hash text primary key,
  user_id uuid not null references account.users(id) on delete cascade,
  client text not null default 'web' check (client in ('web', 'ios', 'android')),
  created_at timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  expires_at timestamptz not null
);
create index if not exists account_sessions_user_idx on account.sessions (user_id);

-- Emails sent to an account (counts and keys only, never the message), so a notice or a week is sent once.
create table if not exists account.sends (
  id bigint generated always as identity primary key,
  user_id uuid not null references account.users(id) on delete cascade,
  kind text not null check (kind in ('weekly', 'alert')),
  dedupe_key text not null,
  items int not null default 0,
  resend_id text,
  sent_at timestamptz not null default now(),
  unique (user_id, kind, dedupe_key)
);

-- A phone signed in to an account follows that account's home and choices.
alter table push.devices add column if not exists user_id uuid references account.users(id) on delete set null;
create index if not exists push_devices_user_idx on push.devices (user_id) where user_id is not null;

alter table account.users enable row level security;
alter table account.homes enable row level security;
alter table account.prefs enable row level security;
alter table account.codes enable row level security;
alter table account.sessions enable row level security;
alter table account.sends enable row level security;
