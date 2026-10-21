-- API keys, throttles and request logs for /api/v1 and /api/mcp.
-- Lives in its own schema, which Supabase's public data API does not expose; only server-side code
-- connecting with the database password (the Vercel functions) can read or write it.
create schema if not exists apiadmin;
revoke all on schema apiadmin from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema apiadmin from anon, authenticated'; end if;
end $$;

create table if not exists apiadmin.settings (
  id boolean primary key default true check (id),
  anon_per_minute integer default 60,      -- requests without a key, per connection; null = no limit
  anon_per_day integer default 5000,
  require_key boolean not null default false,
  default_per_minute integer default 120,  -- starting limits for new keys
  default_per_day integer default 20000,
  updated_at timestamptz not null default now()
);
insert into apiadmin.settings (id) values (true) on conflict do nothing;

create table if not exists apiadmin.keys (
  id uuid primary key default gen_random_uuid(),
  name text not null,                      -- what it's for, e.g. "News Herald data desk"
  owner_name text,
  owner_email text,
  organization text,
  notes text,
  prefix text not null,                    -- first characters of the key, shown so you can tell keys apart
  key_hash text not null unique,           -- sha256 of the full key; the key itself is never stored
  per_minute integer,                      -- null = no limit
  per_day integer,
  status text not null default 'active' check (status in ('active', 'disabled', 'revoked')),
  expires_at timestamptz,
  created_by text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  rotated_at timestamptz,
  last_used_at timestamptz
);

create table if not exists apiadmin.requests (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  key_id uuid references apiadmin.keys(id) on delete set null,
  ip_hash text,                            -- salted hash, never the raw address
  surface text not null,                   -- api or mcp
  endpoint text,                           -- e.g. datasets/contracts, governments, search, tools/call:query_dataset
  dataset text,
  query text,
  status integer,
  rows_returned integer,
  ms integer,
  user_agent text
);
create index if not exists requests_key_at_idx on apiadmin.requests (key_id, at desc);
create index if not exists requests_at_idx on apiadmin.requests (at desc);

create table if not exists apiadmin.counters (
  subject text not null,                   -- key:<uuid> or ip:<hash>
  kind char(1) not null,                   -- m = minute, d = day (Central time)
  window_start timestamptz not null,
  count integer not null default 0,
  primary key (subject, kind, window_start)
);

create table if not exists apiadmin.audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  admin text not null,
  action text not null,
  key_id uuid,
  detail jsonb
);

alter table apiadmin.settings enable row level security;
alter table apiadmin.keys enable row level security;
alter table apiadmin.requests enable row level security;
alter table apiadmin.counters enable row level security;
alter table apiadmin.audit enable row level security;

-- One call per API request: validates the key, counts the request, and says whether to allow it.
create or replace function apiadmin.check_request(p_key_hash text, p_ip_hash text)
returns jsonb language plpgsql set search_path = '' as $$
declare
  s apiadmin.settings; k apiadmin.keys; subj text; lim_m integer; lim_d integer; used_m integer; used_d integer;
  day_start timestamptz := (date_trunc('day', now() at time zone 'America/Chicago')) at time zone 'America/Chicago';
begin
  select * into s from apiadmin.settings where id;
  if p_key_hash is not null then
    select * into k from apiadmin.keys where key_hash = p_key_hash;
    if not found then return jsonb_build_object('ok', false, 'status', 401, 'reason', 'invalid_key'); end if;
    if k.status <> 'active' then return jsonb_build_object('ok', false, 'status', 403, 'reason', 'key_' || k.status, 'key_id', k.id); end if;
    if k.expires_at is not null and k.expires_at < now() then return jsonb_build_object('ok', false, 'status', 403, 'reason', 'key_expired', 'key_id', k.id); end if;
    subj := 'key:' || k.id; lim_m := k.per_minute; lim_d := k.per_day;
    if k.last_used_at is null or k.last_used_at < now() - interval '1 minute' then
      update apiadmin.keys set last_used_at = now() where id = k.id;
    end if;
  else
    if s.require_key then return jsonb_build_object('ok', false, 'status', 401, 'reason', 'key_required'); end if;
    subj := 'ip:' || coalesce(p_ip_hash, 'unknown'); lim_m := s.anon_per_minute; lim_d := s.anon_per_day;
  end if;
  insert into apiadmin.counters as c (subject, kind, window_start, count) values (subj, 'm', date_trunc('minute', now()), 1)
    on conflict (subject, kind, window_start) do update set count = c.count + 1 returning c.count into used_m;
  insert into apiadmin.counters as c (subject, kind, window_start, count) values (subj, 'd', day_start, 1)
    on conflict (subject, kind, window_start) do update set count = c.count + 1 returning c.count into used_d;
  if random() < 0.01 then delete from apiadmin.counters where window_start < now() - interval '3 days'; end if;
  if lim_m is not null and used_m > lim_m then
    return jsonb_build_object('ok', false, 'status', 429, 'reason', 'rate_limited', 'key_id', k.id, 'limit', lim_m, 'remaining', 0, 'retry_after', 60 - extract(second from now())::int);
  end if;
  if lim_d is not null and used_d > lim_d then
    return jsonb_build_object('ok', false, 'status', 429, 'reason', 'daily_quota', 'key_id', k.id, 'limit_day', lim_d, 'remaining_day', 0,
      'retry_after', extract(epoch from (day_start + interval '1 day' - now()))::int);
  end if;
  return jsonb_build_object('ok', true, 'key_id', k.id, 'key_name', k.name, 'limit', lim_m, 'remaining', case when lim_m is null then null else lim_m - used_m end,
    'limit_day', lim_d, 'remaining_day', case when lim_d is null then null else lim_d - used_d end);
end $$;
revoke all on function apiadmin.check_request(text, text) from public;
