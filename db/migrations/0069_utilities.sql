-- Utilities and trash pickup (/utilities): who provides water, sewer, power, gas, garbage, yard waste, recycling and internet
-- in each part of the county, the rates public utilities set, pickup routes and days, and holiday changes. Built by
-- site/page_datasets.py from data/utilities/<county>/utilities.json (copied by hand from city and county pages and route
-- maps) and data/fees/fees_pay_officials.json (rates). /api/v1/utilities?lat=&lon= reads these tables to answer for one
-- address. place_id keeps rows for other places apart (fl-bay = Bay County). Same standard columns, public read policy
-- and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists utility_providers (
  id bigint generated always as identity primary key,
  "place_id" text,
  "area" text,
  "area_name" text,
  "service" text,
  "service_label" text,
  "provider" text,
  "entity_id" text,
  "entity_name" text,
  "provider_kind" text,
  "coverage" text,
  "phone" text,
  "website" text,
  "outage_url" text,
  "notes" text,
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
create index if not exists utility_providers_gov_idx on utility_providers (government_key);
create index if not exists utility_providers_place_idx on utility_providers (place_id, area, service);

insert into datasets (id, table_name, title, description) values ('utility-providers', 'utility_providers', $t$Utilities: who provides each service$t$, $d$Who provides water, sewer, electricity, natural gas, garbage, yard waste, recycling and internet in each part of the county, with phone numbers, websites and outage pages.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table utility_providers enable row level security;
drop policy if exists "public read" on utility_providers;
create policy "public read" on utility_providers for select using (true);

drop trigger if exists utility_providers_touch on utility_providers;
create trigger utility_providers_touch before update on utility_providers for each row execute function touch_updated_at();

create table if not exists utility_rates (
  id bigint generated always as identity primary key,
  "place_id" text,
  "area" text,
  "area_name" text,
  "provider" text,
  "service" text,
  "service_label" text,
  "charge" text,
  "amount" numeric,
  "unit" text,
  "applies_to" text,
  "effective" text,
  "notes" text,
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
create index if not exists utility_rates_gov_idx on utility_rates (government_key);
create index if not exists utility_rates_place_idx on utility_rates (place_id, area, service);

insert into datasets (id, table_name, title, description) values ('utility-rates', 'utility_rates', $t$Utilities: rates$t$, $d$Monthly charges set by each public utility: water and sewer base and usage charges, garbage, stormwater, fees and a typical bill at 5,000 gallons.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table utility_rates enable row level security;
drop policy if exists "public read" on utility_rates;
create policy "public read" on utility_rates for select using (true);

drop trigger if exists utility_rates_touch on utility_rates;
create trigger utility_rates_touch before update on utility_rates for each row execute function touch_updated_at();

create table if not exists trash_pickup (
  id bigint generated always as identity primary key,
  "place_id" text,
  "area" text,
  "area_name" text,
  "service" text,
  "service_label" text,
  "provider" text,
  "zone" text,
  "pickup_days" text,
  "zone_area" text,
  "rule" text,
  "lookup_layer" text,
  "zone_field" text,
  "day_field" text,
  "notes" text,
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
create index if not exists trash_pickup_gov_idx on trash_pickup (government_key);
create index if not exists trash_pickup_place_idx on trash_pickup (place_id, area, service, zone);

insert into datasets (id, table_name, title, description) values ('trash-pickup', 'trash_pickup', $t$Trash pickup: routes and days$t$, $d$Garbage, yard waste and bulk pickup routes and their usual days in each city, with the public map layer that holds each route.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table trash_pickup enable row level security;
drop policy if exists "public read" on trash_pickup;
create policy "public read" on trash_pickup for select using (true);

drop trigger if exists trash_pickup_touch on trash_pickup;
create trigger trash_pickup_touch before update on trash_pickup for each row execute function touch_updated_at();

create table if not exists trash_holidays (
  id bigint generated always as identity primary key,
  "place_id" text,
  "area" text,
  "area_name" text,
  "provider" text,
  "holiday" text,
  "when_observed" text,
  "garbage" text,
  "yard_waste" text,
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
create index if not exists trash_holidays_gov_idx on trash_holidays (government_key);
create index if not exists trash_holidays_place_idx on trash_holidays (place_id, area);

insert into datasets (id, table_name, title, description) values ('trash-holidays', 'trash_holidays', $t$Trash pickup: holiday changes$t$, $d$How each city's garbage and yard waste pickup changes on holidays.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table trash_holidays enable row level security;
drop policy if exists "public read" on trash_holidays;
create policy "public read" on trash_holidays for select using (true);

drop trigger if exists trash_holidays_touch on trash_holidays;
create trigger trash_holidays_touch before update on trash_holidays for each row execute function touch_updated_at();
