-- Government workspace (/staff): a private space per city and the county where their own staff sign in, post
-- notices, events and jobs, send emergency alerts, and flag data on the site that looks wrong.
--
-- Rule (Jeremy, 2026-10-30): staff never edit numbers that came from public records. Record data is read-only in
-- the workspace; a staff member can only flag it (gov.flags), and BayCounty.me checks the flag against the source.
-- Staff only add their own posts: rows they create go into the public tables with origin = 'gov' (the site sync
-- never touches them) and only rows with origin = 'gov' from their own government can be changed or withdrawn.
--
-- Private: RLS on, no policies, schema not exposed; only the Vercel functions (service role / DATABASE_URL) read it.
create schema if not exists gov;
revoke all on schema gov from public;

-- One workspace per government. id is the site's gov id (county, pc, pcb, lh, cw, sp, parker, mb).
create table if not exists gov.workspaces (
  id text primary key,
  place_id text not null default 'fl-bay',
  name text not null,
  modules text[] not null default '{alerts,notices,events,jobs,data}',
  countywide boolean not null default false,       -- may send alerts to the whole county (the county's emergency office)
  created_at timestamptz not null default now()
);

insert into gov.workspaces (id, name, countywide) values
  ('county', 'Bay County', true),
  ('pc', 'City of Panama City', false),
  ('pcb', 'City of Panama City Beach', false),
  ('lh', 'City of Lynn Haven', false),
  ('cw', 'City of Callaway', false),
  ('sp', 'City of Springfield', false),
  ('parker', 'City of Parker', false),
  ('mb', 'City of Mexico Beach', false)
on conflict (id) do nothing;

-- Who can sign in, and what they can do. Roles stack: owner > alert_sender > publisher > viewer (= auditor).
create table if not exists gov.members (
  id bigint generated always as identity primary key,
  workspace_id text not null references gov.workspaces(id) on delete cascade,
  email text not null,
  role text not null default 'viewer' check (role in ('owner', 'alert_sender', 'publisher', 'viewer', 'auditor')),
  added_by text,
  created_at timestamptz not null default now(),
  unique (workspace_id, email)
);
create index if not exists gov_members_email on gov.members (lower(email));

-- 6-digit emailed sign-in codes and the sessions they start (same pattern as finance.login_codes / finance.sessions).
create table if not exists gov.login_codes (
  id bigint generated always as identity primary key,
  email text not null,
  code_hash text not null,
  attempts integer not null default 0,
  ip_hash text,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  used_at timestamptz
);
create index if not exists gov_login_codes_email on gov.login_codes (lower(email), created_at desc);

create table if not exists gov.sessions (
  id bigint generated always as identity primary key,
  email text not null,
  token_hash text not null unique,
  user_agent text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz
);

-- Everything anyone does in a workspace: who, when, what.
create table if not exists gov.activity (
  id bigint generated always as identity primary key,
  workspace_id text references gov.workspaces(id) on delete cascade,
  email text not null,
  action text not null,
  detail jsonb not null default '{}',
  at timestamptz not null default now()
);
create index if not exists gov_activity_ws on gov.activity (workspace_id, at desc);

-- Emergency alerts written by staff (or by BayCounty.me itself: workspace_id null). A sent alert is read by
-- staffAlerts() in api/_emergency.js on every emergency check, so it goes out through the same push, email and
-- (later) text path as every other emergency notice, and shows on /emergency. Countywide alerts wait for a second
-- person to confirm. Cancelling or ending one takes it off the live list.
create table if not exists gov.alerts (
  id bigint generated always as identity primary key,
  workspace_id text references gov.workspaces(id) on delete set null,
  place_id text not null default 'fl-bay',
  kind text not null check (kind in ('evacuation', 'shelter', 'boil-water', 'road', 'safety', 'general')),
  title text not null,
  message text not null,
  instruction text,
  severity text not null default 'severe' check (severity in ('extreme', 'severe', 'moderate', 'minor', 'info')),
  countywide boolean not null default false,
  status text not null default 'pending' check (status in ('pending', 'sent', 'ended', 'cancelled')),
  created_by text not null,
  created_at timestamptz not null default now(),
  confirmed_by text,
  sent_at timestamptz,
  ends_at timestamptz,
  ended_by text,
  ended_at timestamptz
);
create index if not exists gov_alerts_live on gov.alerts (place_id, status, sent_at desc);
create index if not exists gov_alerts_ws on gov.alerts (workspace_id, created_at desc);

-- "This looks wrong" flags on record data. Staff can't change it; BayCounty.me checks the source and answers.
create table if not exists gov.flags (
  id bigint generated always as identity primary key,
  workspace_id text not null references gov.workspaces(id) on delete cascade,
  email text not null,
  dataset text not null,
  record_key text,
  record_label text,
  field text,
  shown_value text,
  correct_value text,
  evidence_url text,
  note text,
  status text not null default 'open' check (status in ('open', 'fixed', 'not_changed')),
  reply text,
  reviewed_by text,
  reviewed_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists gov_flags_status on gov.flags (status, created_at desc);

alter table gov.workspaces enable row level security;
alter table gov.members enable row level security;
alter table gov.login_codes enable row level security;
alter table gov.sessions enable row level security;
alter table gov.activity enable row level security;
alter table gov.alerts enable row level security;
alter table gov.flags enable row level security;
