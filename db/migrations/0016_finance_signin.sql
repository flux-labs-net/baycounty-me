-- Sign-in for the finance dashboard (/finance) and the mobile app: a 6-digit code is emailed to a workspace member,
-- and a correct code opens a session. Codes and session tokens are stored only as hashes. Private like the rest of
-- the finance schema (RLS on, no policies): only the Vercel functions read these tables.
create table if not exists finance.login_codes (
  id bigint generated always as identity primary key,
  email text not null,
  code_hash text not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  attempts integer not null default 0,
  used_at timestamptz,
  ip_hash text
);
create index if not exists login_codes_email on finance.login_codes (lower(email), created_at desc);

create table if not exists finance.sessions (
  id bigint generated always as identity primary key,
  email text not null,
  token_hash text not null unique,
  client text not null default 'web' check (client in ('web', 'app')),
  user_agent text,
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null,
  revoked_at timestamptz
);
create index if not exists sessions_email on finance.sessions (lower(email));

alter table finance.login_codes enable row level security;
alter table finance.sessions enable row level security;

-- Housekeeping: codes older than a day and sessions expired over 30 days ago are deleted by the sign-in endpoint.
