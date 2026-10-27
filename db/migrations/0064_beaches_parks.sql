-- Beaches, beach water quality and parks (/beaches, /parks), built by site/page_datasets.py from data/outdoors/<county>/
-- (data/outdoors/fetch_outdoors.py: county and Panama City Beach GIS, Florida DEP coastal access survey, Florida Department of
-- Health Healthy Beaches samples, National Weather Service surf zone forecast). place_id keeps rows for other places apart
-- (fl-bay = Bay County). Same standard columns, public read policy and updated_at trigger as every other dataset table
-- (see 0021_page_datasets.sql).

create table if not exists beach_access (
  id bigint generated always as identity primary key,
  "place_id" text,
  "access_id" text,
  "name" text,
  "number" text,
  "address" text,
  "area" text,
  "latitude" numeric,
  "longitude" numeric,
  "vehicle_access" boolean,
  "wheelchair_access" boolean,
  "parking" boolean,
  "parking_spaces" bigint,
  "ada_parking" boolean,
  "restroom" boolean,
  "shower" boolean,
  "lifeguard" boolean,
  "boardwalk" boolean,
  "notes" text,
  "state_access_name" text,
  "state_site_id" text,
  "source_url" text,
  "run_by" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists beach_access_gov_idx on beach_access (government_key);
create index if not exists beach_access_place_idx on beach_access (place_id, access_id);

insert into datasets (id, table_name, title, description) values ('beach-access', 'beach_access', $t$Beach access points$t$, $d$Every public Gulf beach access in the county: address, area, map point, drive-on and wheelchair access, and amenities from the state coastal access survey.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table beach_access enable row level security;
drop policy if exists "public read" on beach_access;
create policy "public read" on beach_access for select using (true);

drop trigger if exists beach_access_touch on beach_access;
create trigger beach_access_touch before update on beach_access for each row execute function touch_updated_at();

create table if not exists beach_parking (
  id bigint generated always as identity primary key,
  "place_id" text,
  "lot_id" text,
  "spaces" bigint,
  "parking_type" text,
  "latitude" numeric,
  "longitude" numeric,
  "nearest_access" text,
  "nearest_access_id" text,
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
create index if not exists beach_parking_gov_idx on beach_parking (government_key);
create index if not exists beach_parking_place_idx on beach_parking (place_id, lot_id);

insert into datasets (id, table_name, title, description) values ('beach-parking', 'beach_parking', $t$Beach parking lots$t$, $d$County beach parking lots: spaces, type and the nearest beach access.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table beach_parking enable row level security;
drop policy if exists "public read" on beach_parking;
create policy "public read" on beach_parking for select using (true);

drop trigger if exists beach_parking_touch on beach_parking;
create trigger beach_parking_touch before update on beach_parking for each row execute function touch_updated_at();

create table if not exists beach_water_sites (
  id bigint generated always as identity primary key,
  "place_id" text,
  "site_id" text,
  "name" text,
  "active" boolean,
  "epa_beach_id" text,
  "latitude" numeric,
  "longitude" numeric,
  "latest_date" text,
  "latest_enterococcus" numeric,
  "latest_rating" text,
  "latest_advisory" boolean,
  "samples" bigint,
  "first_date" text,
  "good" bigint,
  "moderate" bigint,
  "poor" bigint,
  "advisories" bigint,
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
create index if not exists beach_water_sites_gov_idx on beach_water_sites (government_key);
create index if not exists beach_water_sites_place_idx on beach_water_sites (place_id, site_id);

insert into datasets (id, table_name, title, description) values ('beach-water-sites', 'beach_water_sites', $t$Beach water quality: sampling sites$t$, $d$Florida Healthy Beaches sampling sites with their latest rated sample and counts of Good, Moderate and Poor samples.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table beach_water_sites enable row level security;
drop policy if exists "public read" on beach_water_sites;
create policy "public read" on beach_water_sites for select using (true);

drop trigger if exists beach_water_sites_touch on beach_water_sites;
create trigger beach_water_sites_touch before update on beach_water_sites for each row execute function touch_updated_at();

create table if not exists beach_water_samples (
  id bigint generated always as identity primary key,
  "place_id" text,
  "site_id" text,
  "site" text,
  "sample_number" text,
  "date" text,
  "enterococcus" numeric,
  "reported" text,
  "advisory" boolean,
  "rating" text,
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
create index if not exists beach_water_samples_gov_idx on beach_water_samples (government_key);
create index if not exists beach_water_samples_place_idx on beach_water_samples (place_id, site_id, date);

insert into datasets (id, table_name, title, description) values ('beach-water-samples', 'beach_water_samples', $t$Beach water quality: samples$t$, $d$Every published Healthy Beaches sample: date, enterococcus count, rating and health advisory.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table beach_water_samples enable row level security;
drop policy if exists "public read" on beach_water_samples;
create policy "public read" on beach_water_samples for select using (true);

drop trigger if exists beach_water_samples_touch on beach_water_samples;
create trigger beach_water_samples_touch before update on beach_water_samples for each row execute function touch_updated_at();

create table if not exists beach_conditions (
  id bigint generated always as identity primary key,
  "place_id" text,
  "zone" text,
  "issued" text,
  "period" text,
  "flag_color" text,
  "meaning" text,
  "rip_current_risk" text,
  "surf_height" text,
  "uv_index" text,
  "water_temperature" text,
  "weather" text,
  "high_temperature" text,
  "winds" text,
  "sunrise" text,
  "sunset" text,
  "summary" text,
  "date" text,
  "ends" text,
  "sort_order" bigint,
  "source_url" text,
  "kind" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists beach_conditions_gov_idx on beach_conditions (government_key);
create index if not exists beach_conditions_place_idx on beach_conditions (place_id, kind, date);

insert into datasets (id, table_name, title, description) values ('beach-conditions', 'beach_conditions', $t$Beach conditions and flags$t$, $d$Surf zone forecast (rip current risk, surf, UV, water temperature), beach alerts, the flag color reported each day, and what each flag means.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table beach_conditions enable row level security;
drop policy if exists "public read" on beach_conditions;
create policy "public read" on beach_conditions for select using (true);

drop trigger if exists beach_conditions_touch on beach_conditions;
create trigger beach_conditions_touch before update on beach_conditions for each row execute function touch_updated_at();

create table if not exists parks (
  id bigint generated always as identity primary key,
  "place_id" text,
  "park_id" text,
  "name" text,
  "address" text,
  "run_by" text,
  "acres" numeric,
  "kind" text,
  "also" text,
  "restroom" boolean,
  "community_building" boolean,
  "pavilion" boolean,
  "picnic_tables" boolean,
  "beach_access" boolean,
  "boat_ramp" boolean,
  "boat_dock" boolean,
  "fishing_pier" boolean,
  "baseball" boolean,
  "basketball" boolean,
  "football" boolean,
  "soccer" boolean,
  "volleyball" boolean,
  "tennis" boolean,
  "trail" boolean,
  "playground" boolean,
  "other" text,
  "facilities" text,
  "photo_url" text,
  "latitude" numeric,
  "longitude" numeric,
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
create index if not exists parks_gov_idx on parks (government_key);
create index if not exists parks_place_idx on parks (place_id, park_id);

insert into datasets (id, table_name, title, description) values ('parks', 'parks', $t$Parks$t$, $d$Every public park in the county from the county's parks inventory: who runs it, acres, main use and its amenities.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table parks enable row level security;
drop policy if exists "public read" on parks;
create policy "public read" on parks for select using (true);

drop trigger if exists parks_touch on parks;
create trigger parks_touch before update on parks for each row execute function touch_updated_at();

create table if not exists boat_ramps (
  id bigint generated always as identity primary key,
  "place_id" text,
  "ramp_id" text,
  "name" text,
  "park" text,
  "address" text,
  "run_by" text,
  "water" text,
  "waterbody" text,
  "ramp_surface" text,
  "restroom" boolean,
  "boat_dock" boolean,
  "fishing_pier" boolean,
  "acres" numeric,
  "latitude" numeric,
  "longitude" numeric,
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
create index if not exists boat_ramps_gov_idx on boat_ramps (government_key);
create index if not exists boat_ramps_place_idx on boat_ramps (place_id, ramp_id);

insert into datasets (id, table_name, title, description) values ('boat-ramps', 'boat_ramps', $t$Boat ramps and launches$t$, $d$Public boat ramps and small-craft launches: water, waterbody, surface, restroom, dock and pier.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table boat_ramps enable row level security;
drop policy if exists "public read" on boat_ramps;
create policy "public read" on boat_ramps for select using (true);

drop trigger if exists boat_ramps_touch on boat_ramps;
create trigger boat_ramps_touch before update on boat_ramps for each row execute function touch_updated_at();

create table if not exists trails (
  id bigint generated always as identity primary key,
  "place_id" text,
  "trail_id" text,
  "name" text,
  "area" text,
  "miles" numeric,
  "surface" text,
  "uses" text,
  "skill_level" text,
  "latitude" numeric,
  "longitude" numeric,
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
create index if not exists trails_gov_idx on trails (government_key);
create index if not exists trails_place_idx on trails (place_id, trail_id);

insert into datasets (id, table_name, title, description) values ('trails', 'trails', $t$Trails$t$, $d$Named trails with miles, surface, allowed uses and skill level.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table trails enable row level security;
drop policy if exists "public read" on trails;
create policy "public read" on trails for select using (true);

drop trigger if exists trails_touch on trails;
create trigger trails_touch before update on trails for each row execute function touch_updated_at();

create table if not exists recreation_departments (
  id bigint generated always as identity primary key,
  "place_id" text,
  "name" text,
  "run_by" text,
  "parks_url" text,
  "programs_url" text,
  "programs_label" text,
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
create index if not exists recreation_departments_gov_idx on recreation_departments (government_key);
create index if not exists recreation_departments_place_idx on recreation_departments (place_id, gov_id);

insert into datasets (id, table_name, title, description) values ('recreation-departments', 'recreation_departments', $t$Parks and recreation departments$t$, $d$Each local government's parks and recreation pages, for program sign-ups and rentals.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table recreation_departments enable row level security;
drop policy if exists "public read" on recreation_departments;
create policy "public read" on recreation_departments for select using (true);

drop trigger if exists recreation_departments_touch on recreation_departments;
create trigger recreation_departments_touch before update on recreation_departments for each row execute function touch_updated_at();

