-- Emergency and alerts hub (/emergency) and hurricane prep (/hurricane-prep). Seven datasets (four for the hub, three below) built by site/page_datasets.py from data/emergency/<county>/
-- (zones.json and resources.json by hand; shelters.json, zones_geo.json and notices.json from data/emergency/fetch_emergency.js),
-- plus the live tables the poller (api/emergency-run.js) writes every few minutes:
--   emergency_live   every notice currently or recently live (weather alerts, boil-water notices, road closures...), public read
--   emergency_state  per place: the latest shelter status and which sources answered, public read
--   push.devices / push.sent   phones signed up for notifications (private: no public access) and what was sent
-- place_id keeps places apart (fl-bay = Bay County). Same standard columns, public read policy and updated_at trigger as
-- every other dataset table (see 0021_page_datasets.sql).

create table if not exists evacuation_zones (
  id bigint generated always as identity primary key,
  "place_id" text,
  "zone" text,
  "sort_order" bigint,
  "color" text,
  "where_it_is" text,
  "when_ordered" text,
  "plain" text,
  "zone_edited" text,
  "geometry" text,
  "map_url" text,
  "layer_url" text,
  "as_of" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists evacuation_zones_gov_idx on evacuation_zones (government_key);
create index if not exists evacuation_zones_place_idx on evacuation_zones (place_id);

insert into datasets (id, table_name, title, description) values ('evacuation-zones', 'evacuation_zones', $t$Hurricane evacuation zones$t$, $d$Hurricane evacuation zones A to D: where each is, when it is ordered, and its shape (GeoJSON).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table evacuation_zones enable row level security;
drop policy if exists "public read" on evacuation_zones;
create policy "public read" on evacuation_zones for select using (true);

drop trigger if exists evacuation_zones_touch on evacuation_zones;
create trigger evacuation_zones_touch before update on evacuation_zones for each row execute function touch_updated_at();

create table if not exists emergency_shelters (
  id bigint generated always as identity primary key,
  "place_id" text,
  "shelter_id" text,
  "name" text,
  "address" text,
  "shelter_type" text,
  "group_name" text,
  "group_about" text,
  "note" text,
  "status" text,
  "status_as_of" text,
  "lat" numeric,
  "lng" numeric,
  "evacuation_zone" text,
  "operator" text,
  "source_url" text,
  "checked" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists emergency_shelters_gov_idx on emergency_shelters (government_key);
create index if not exists emergency_shelters_place_idx on emergency_shelters (place_id);

insert into datasets (id, table_name, title, description) values ('emergency-shelters', 'emergency_shelters', $t$Emergency shelters$t$, $d$Every disaster shelter the county lists, with type, address, posted open/closed status, map point and evacuation zone.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table emergency_shelters enable row level security;
drop policy if exists "public read" on emergency_shelters;
create policy "public read" on emergency_shelters for select using (true);

drop trigger if exists emergency_shelters_touch on emergency_shelters;
create trigger emergency_shelters_touch before update on emergency_shelters for each row execute function touch_updated_at();

create table if not exists emergency_resources (
  id bigint generated always as identity primary key,
  "place_id" text,
  "sort_order" bigint,
  "resource_id" text,
  "group" text,
  "name" text,
  "org" text,
  "phone" text,
  "url" text,
  "about" text,
  "as_of" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists emergency_resources_gov_idx on emergency_resources (government_key);
create index if not exists emergency_resources_place_idx on emergency_resources (place_id);

insert into datasets (id, table_name, title, description) values ('emergency-resources', 'emergency_resources', $t$Emergency phone numbers and sign-ups$t$, $d$Emergency phone numbers, sign-ups, plans, weather offices, road and power outage links.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table emergency_resources enable row level security;
drop policy if exists "public read" on emergency_resources;
create policy "public read" on emergency_resources for select using (true);

drop trigger if exists emergency_resources_touch on emergency_resources;
create trigger emergency_resources_touch before update on emergency_resources for each row execute function touch_updated_at();

create table if not exists emergency_notices (
  id bigint generated always as identity primary key,
  "notice_id" text,
  "place_id" text,
  "kind" text,
  "source" text,
  "source_type" text,
  "title" text,
  "summary" text,
  "instruction" text,
  "severity" text,
  "event" text,
  "area" text,
  "zones" text,
  "issued" text,
  "starts" text,
  "ends" text,
  "updated" text,
  "status" text,
  "full_closure" boolean,
  "roadway" text,
  "first_seen" text,
  "last_seen" text,
  "url" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists emergency_notices_gov_idx on emergency_notices (government_key);
create index if not exists emergency_notices_place_idx on emergency_notices (place_id);

insert into datasets (id, table_name, title, description) values ('emergency-notices', 'emergency_notices', $t$Emergency notices archive$t$, $d$Archive of every emergency notice seen: weather alerts, boil-water notices, road closures, outages, evacuation orders, shelter openings and storm updates.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table emergency_notices enable row level security;
drop policy if exists "public read" on emergency_notices;
create policy "public read" on emergency_notices for select using (true);

drop trigger if exists emergency_notices_touch on emergency_notices;
create trigger emergency_notices_touch before update on emergency_notices for each row execute function touch_updated_at();

-- Hurricane prep page (/hurricane-prep): prep steps (data/emergency/<county>/prep.json, by hand) and FEMA declarations and
-- rebuild money by ZIP code (rebuild.json, from data/emergency/fetch_fema.py).

create table if not exists hurricane_prep (
  id bigint generated always as identity primary key,
  "place_id" text,
  "sort_order" bigint,
  "topic" text,
  "step" text,
  "text" text,
  "source" text,
  "as_of" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists hurricane_prep_gov_idx on hurricane_prep (government_key);
create index if not exists hurricane_prep_place_idx on hurricane_prep (place_id);

insert into datasets (id, table_name, title, description) values ('hurricane-prep', 'hurricane_prep', $t$Hurricane prep steps$t$, $d$Plain-English steps for hurricane season, sandbags, generator safety, an approaching storm and the days after, each with the agency it comes from (Bay County, Ready.gov, CDC, National Weather Service, FEMA, the Army Corps of Engineers).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table hurricane_prep enable row level security;
drop policy if exists "public read" on hurricane_prep;
create policy "public read" on hurricane_prep for select using (true);

drop trigger if exists hurricane_prep_touch on hurricane_prep;
create trigger hurricane_prep_touch before update on hurricane_prep for each row execute function touch_updated_at();

create table if not exists disaster_declarations (
  id bigint generated always as identity primary key,
  "place_id" text,
  "disaster_number" bigint,
  "title" text,
  "kind" text,
  "incident_type" text,
  "declared" text,
  "began" text,
  "ended" text,
  "individual_aid" boolean,
  "public_aid" boolean,
  "mitigation" boolean,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists disaster_declarations_gov_idx on disaster_declarations (government_key);
create index if not exists disaster_declarations_place_idx on disaster_declarations (place_id);

insert into datasets (id, table_name, title, description) values ('disaster-declarations', 'disaster_declarations', $t$Disaster declarations$t$, $d$Every federal major disaster, emergency and fire management declaration that included the county since 2016, from OpenFEMA: the storm or event, the dates, and which FEMA programs were opened (individual aid to households, public aid to governments, hazard mitigation).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table disaster_declarations enable row level security;
drop policy if exists "public read" on disaster_declarations;
create policy "public read" on disaster_declarations for select using (true);

drop trigger if exists disaster_declarations_touch on disaster_declarations;
create trigger disaster_declarations_touch before update on disaster_declarations for each row execute function touch_updated_at();

create table if not exists rebuild_money (
  id bigint generated always as identity primary key,
  "place_id" text,
  "zip" text,
  "area_name" text,
  "program" text,
  "disaster_number" bigint,
  "event" text,
  "year" bigint,
  "count" bigint,
  "count_label" text,
  "approved" bigint,
  "amount_paid" numeric,
  "repair_amount" numeric,
  "rental_amount" numeric,
  "inspected_damage" numeric,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists rebuild_money_gov_idx on rebuild_money (government_key);
create index if not exists rebuild_money_place_idx on rebuild_money (place_id);

insert into datasets (id, table_name, title, description) values ('rebuild-money', 'rebuild_money', $t$Rebuild money by ZIP code$t$, $d$Money that reached each ZIP code after storms since 2016, from OpenFEMA: FEMA housing aid to owners and renters (Individuals and Households Program: households that applied, approved, dollars, of which repair and rental help, and FEMA-inspected damage for owners) and flood insurance claims paid (NFIP, building, contents and compliance payments added). One row per ZIP, program and storm. Totals only; FEMA does not publish who received aid and neither does BayCounty.me.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table rebuild_money enable row level security;
drop policy if exists "public read" on rebuild_money;
create policy "public read" on rebuild_money for select using (true);

drop trigger if exists rebuild_money_touch on rebuild_money;
create trigger rebuild_money_touch before update on rebuild_money for each row execute function touch_updated_at();


-- Live notices, written only by the poller (server-side connection). Rows stay after they end (active = false) so the
-- daily archive can pick up notices that came and went between runs.
create table if not exists emergency_live (
  notice_id text primary key,
  place_id text not null,
  kind text not null,
  source text,
  source_type text,
  gov_id text,
  title text not null,
  summary text,
  instruction text,
  severity text,
  event text,
  area text,
  zones text,
  issued text,
  starts text,
  ends text,
  updated text,
  status text,
  full_closure boolean,
  roadway text,
  url text,
  source_url text,
  push_topic text,
  pushed_at timestamptz,
  active boolean not null default true,
  first_seen timestamptz not null default now(),
  last_seen timestamptz not null default now()
);
create index if not exists emergency_live_place_idx on emergency_live (place_id, active, last_seen desc);
alter table emergency_live enable row level security;
drop policy if exists "public read" on emergency_live;
create policy "public read" on emergency_live for select using (true);

create table if not exists emergency_state (
  place_id text primary key,
  checked_at timestamptz,
  started_at timestamptz,
  shelters jsonb,
  sources_ok jsonb,
  errors jsonb,
  notices_active integer,
  pushed integer,
  push_ready boolean,
  agenda_checked_at timestamptz
);
alter table emergency_state enable row level security;
drop policy if exists "public read" on emergency_state;
create policy "public read" on emergency_state for select using (true);

-- Phones signed up for notifications. Only the server reads these; no public access.
create schema if not exists push;
revoke all on schema push from public;
create table if not exists push.devices (
  id bigint generated always as identity primary key,
  token text not null unique,
  platform text not null check (platform in ('ios', 'android')),
  place_id text not null default 'fl-bay',
  topics text[] not null default array['weather', 'evacuation', 'shelters', 'water'],
  govs text[] not null default '{}',
  zone text,
  lat numeric,          -- saved place for agenda items near me, rounded to about 100 m (no address is stored)
  lng numeric,
  radius_mi numeric not null default 1,
  app_version text,
  created_at timestamptz not null default now(),
  last_seen timestamptz not null default now(),
  failures integer not null default 0,
  disabled_at timestamptz
);
create index if not exists push_devices_place_idx on push.devices (place_id) where disabled_at is null;
create table if not exists push.sent (
  notice_id text primary key,
  place_id text not null,
  topic text not null,
  dedupe_key text,
  title text,
  suppressed boolean not null default false,
  sent_at timestamptz not null default now(),
  devices integer not null default 0,
  delivered integer not null default 0,
  failed integer not null default 0
);
create index if not exists push_sent_dedupe_idx on push.sent (place_id, dedupe_key, sent_at desc);
-- Agenda items placed on the map from the first address they name (api/_agenda_push.js); lat is null when none matched.
create table if not exists push.agenda_points (
  record_hash text primary key,
  place_id text not null,
  board text,
  meeting_date date,
  title text,
  url text,
  lat numeric,
  lng numeric,
  placed_at timestamptz not null default now()
);
alter table push.agenda_points enable row level security;
alter table push.devices enable row level security;
alter table push.sent enable row level security;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema push from anon, authenticated';
    execute 'revoke all on all tables in schema push from anon, authenticated';
  end if;
end $$;

-- Every 5 minutes the database asks the site to check the sources (pg_cron + pg_net, on Supabase). The endpoint is
-- public and throttled (one check per 2 minutes per place), so no secret is needed. Skipped where the extensions
-- aren't available (plain Postgres in CI).
do $$ begin
  if exists (select 1 from pg_available_extensions where name = 'pg_cron') and exists (select 1 from pg_available_extensions where name = 'pg_net') then
    begin
      create extension if not exists pg_cron with schema pg_catalog;
      create extension if not exists pg_net with schema extensions;
      perform cron.schedule('emergency-poll-fl-bay', '*/5 * * * *',
        $c$select net.http_get(url := 'https://baycounty.me/api/emergency-run?place=fl-bay', timeout_milliseconds := 30000)$c$);
    exception when others then raise notice 'emergency poll schedule skipped: %', sqlerrm;
    end;
  end if;
end $$;
