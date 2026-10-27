-- Realtor console (/realtor): agent accounts, their saved branding and the reports they've run.
--
-- Private: schema `realtor`, read and written only by server-side code (api/_realtor.js through the service
-- connection). Agents sign in with an emailed one-time link, like the admin; there are no passwords. Nothing here is a
-- public dataset: the report itself is public data from GET /api/v1/address-report, and this schema only holds who may
-- print it with their brokerage's look. Report history keeps the address an agent ran (their own work, shown back to
-- them), never anything about the property's owner. Keyed by place so other counties can share the tables later.

create schema if not exists realtor;
revoke all on schema realtor from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema realtor from anon, authenticated'; end if;
end $$;

-- One row per agent. status: active (can sign in and print), paused (an admin turned them off), pending (asked to join
-- while sign-up is invite-only; an admin turns them on).
create table if not exists realtor.agents (
  id uuid primary key default gen_random_uuid(),
  place_id text not null default 'fl-bay',
  email text not null unique check (email = lower(email) and position('@' in email) > 1),
  status text not null default 'active' check (status in ('active', 'paused', 'pending')),
  created_at timestamptz not null default now(),
  last_login_at timestamptz,
  login_count int not null default 0,
  reports_run int not null default 0
);

-- One branding profile per agent: what goes on the report's cover and footer. Images are small data: URLs
-- (PNG or JPEG, which the PDF maker can draw; never SVG) checked for size by the API; colors are #rrggbb.
create table if not exists realtor.brands (
  agent_id uuid primary key references realtor.agents(id) on delete cascade,
  agent_name text,
  title text,
  brokerage text,
  license_no text,
  phone text,
  email text,
  website text,
  office_address text,
  tagline text,
  disclaimer text,
  color_primary text check (color_primary is null or color_primary ~ '^#[0-9a-fA-F]{6}$'),
  color_accent text check (color_accent is null or color_accent ~ '^#[0-9a-fA-F]{6}$'),
  logo text check (logo is null or (logo like 'data:image/%' and length(logo) <= 400000)),
  photo text check (photo is null or (photo like 'data:image/%' and length(photo) <= 300000)),
  updated_at timestamptz not null default now()
);

-- Reports an agent has run, newest first in their console. prepared_for is the client name the agent typed, if any.
create table if not exists realtor.reports (
  id bigint generated always as identity primary key,
  agent_id uuid not null references realtor.agents(id) on delete cascade,
  place_id text not null default 'fl-bay',
  address text not null,
  city text,
  zip text,
  parcel_id text,
  lat double precision,
  lon double precision,
  prepared_for text,
  created_at timestamptz not null default now()
);
create index if not exists realtor_reports_agent_idx on realtor.reports (agent_id, created_at desc);

-- One-time sign-in links: the nonce is recorded when a link is used, so it can't be used twice.
create table if not exists realtor.logins (
  nonce text primary key,
  email text not null,
  used_at timestamptz not null default now()
);

alter table realtor.agents enable row level security;
alter table realtor.brands enable row level security;
alter table realtor.reports enable row level security;
alter table realtor.logins enable row level security;
