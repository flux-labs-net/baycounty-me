-- The public "Ask" chatbot (/ask, api/chat.js): its switch, per-visitor limits, daily spending cap and usage log.
-- Lives in the private apiadmin schema like the API keys: only server-side code can read or write it.
-- Questions and answers are never stored. Each turn logs its token counts, cost and which tools it used.

create table if not exists apiadmin.chat_settings (
  id boolean primary key default true check (id),
  enabled boolean not null default true,
  per_hour integer not null default 20,          -- questions per visitor (salted IP hash) per hour
  per_day integer not null default 60,           -- and per day (Central time)
  daily_usd numeric(10, 2) not null default 5,   -- all visitors together; the chat pauses until midnight when reached
  model text,                                    -- null = the CHAT_MODEL setting in Vercel (default claude-haiku-5-5)
  updated_at timestamptz not null default now()
);
insert into apiadmin.chat_settings (id) values (true) on conflict do nothing;

create table if not exists apiadmin.chat_turns (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  ip_hash text not null,
  model text,
  status text not null,                          -- ok, refused, error, limited
  input_tokens integer not null default 0,
  output_tokens integer not null default 0,
  cache_read_tokens integer not null default 0,
  cache_write_tokens integer not null default 0,
  cost_usd numeric(12, 6) not null default 0,
  tools text[] not null default '{}',            -- tool names used, e.g. {find_entity,get_entity}
  rounds integer not null default 0,
  ms integer
);
create index if not exists chat_turns_at_idx on apiadmin.chat_turns (at desc);
create index if not exists chat_turns_ip_at_idx on apiadmin.chat_turns (ip_hash, at desc);

alter table apiadmin.chat_settings enable row level security;
alter table apiadmin.chat_turns enable row level security;

-- One call before each question: is the chat on, is this visitor under their limits, is today's spending under the cap?
create or replace function apiadmin.chat_check(p_ip_hash text)
returns jsonb language plpgsql set search_path = '' as $$
declare s apiadmin.chat_settings; hour_n integer; day_n integer; spent numeric; day0 timestamptz;
begin
  select * into s from apiadmin.chat_settings where id;
  if not found then s.enabled := true; s.per_hour := 20; s.per_day := 60; s.daily_usd := 5; end if;
  if not s.enabled then return jsonb_build_object('ok', false, 'reason', 'off'); end if;
  day0 := (date_trunc('day', now() at time zone 'America/Chicago')) at time zone 'America/Chicago';
  select coalesce(sum(cost_usd), 0) into spent from apiadmin.chat_turns where at >= day0;
  if spent >= s.daily_usd then return jsonb_build_object('ok', false, 'reason', 'budget', 'spent', spent); end if;
  select count(*) filter (where at >= now() - interval '1 hour'), count(*) into hour_n, day_n
    from apiadmin.chat_turns where ip_hash = p_ip_hash and at >= day0 and status <> 'limited';
  if hour_n >= s.per_hour then return jsonb_build_object('ok', false, 'reason', 'hour', 'retry_after', 3600); end if;
  if day_n >= s.per_day then return jsonb_build_object('ok', false, 'reason', 'day'); end if;
  if random() < 0.002 then delete from apiadmin.chat_turns where at < now() - interval '400 days'; end if;
  return jsonb_build_object('ok', true, 'model', s.model, 'remaining_hour', s.per_hour - hour_n - 1,
    'remaining_day', s.per_day - day_n - 1, 'budget_left', s.daily_usd - spent);
end $$;
revoke all on function apiadmin.chat_check(text) from public;
