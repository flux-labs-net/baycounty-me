-- Restaurant inspections (/restaurants) and new businesses (/new-businesses), built by site/page_datasets.py:
-- restaurants and restaurant-inspections from data/restaurants/<county>/ (data/restaurants/fetch_dbpr.py, the Florida
-- DBPR Division of Hotels and Restaurants public records, refreshed daily), and new-businesses from the Sunbiz quarterly
-- file (data/sunbiz/<county>/entities.csv.gz). place_id keeps rows for other places apart (fl-bay = Bay County). Same
-- standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists restaurants (
  id bigint generated always as identity primary key,
  "place_id" text,
  "license_number" text,
  "license_type" text,
  "kind" text,
  "business_name" text,
  "licensee" text,
  "licensee_entity_id" text,
  "address" text,
  "city" text,
  "zip" text,
  "seats" bigint,
  "licensed_now" boolean,
  "license_expires" text,
  "risk_level" text,
  "opened" text,
  "first_inspection" text,
  "last_inspection" text,
  "last_result" text,
  "last_result_level" text,
  "last_high_priority" bigint,
  "last_routine_date" text,
  "last_routine_violations" bigint,
  "last_routine_high_priority" bigint,
  "inspections" bigint,
  "inspections_last_year" bigint,
  "high_priority_last_year" bigint,
  "closures" bigint,
  "last_closure" text,
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
create index if not exists restaurants_gov_idx on restaurants (government_key);
create index if not exists restaurants_1_idx on restaurants (place_id, license_number);
create index if not exists restaurants_2_idx on restaurants (licensee_entity_id);
create index if not exists restaurants_3_idx on restaurants (city, licensed_now);

insert into datasets (id, table_name, title, description) values ('restaurants', 'restaurants', $t$Restaurants and food service$t$, $d$One row per restaurant, food truck, caterer or other food service license in the county, with its inspection record. Food trucks, caterers and event vendors show only city and ZIP.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table restaurants enable row level security;
drop policy if exists "public read" on restaurants;
create policy "public read" on restaurants for select using (true);

drop trigger if exists restaurants_touch on restaurants;
create trigger restaurants_touch before update on restaurants for each row execute function touch_updated_at();

create table if not exists restaurant_inspections (
  id bigint generated always as identity primary key,
  "place_id" text,
  "visit_id" text,
  "license_number" text,
  "business_name" text,
  "city" text,
  "date" text,
  "inspection_type" text,
  "visit_number" bigint,
  "disposition" text,
  "result" text,
  "result_level" text,
  "high_priority" bigint,
  "intermediate" bigint,
  "basic" bigint,
  "total_violations" bigint,
  "violation_codes" text,
  "violation_items" text,
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
create index if not exists restaurant_inspections_gov_idx on restaurant_inspections (government_key);
create index if not exists restaurant_inspections_1_idx on restaurant_inspections (place_id, license_number, date);
create index if not exists restaurant_inspections_2_idx on restaurant_inspections (date);
create index if not exists restaurant_inspections_3_idx on restaurant_inspections (result_level);

insert into datasets (id, table_name, title, description) values ('restaurant-inspections', 'restaurant_inspections', $t$Restaurant inspections$t$, $d$Every state food safety inspection of a food service license in the county since 2016, one row per visit, with the result in plain words and the violations cited.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table restaurant_inspections enable row level security;
drop policy if exists "public read" on restaurant_inspections;
create policy "public read" on restaurant_inspections for select using (true);

drop trigger if exists restaurant_inspections_touch on restaurant_inspections;
create trigger restaurant_inspections_touch before update on restaurant_inspections for each row execute function touch_updated_at();

create table if not exists new_businesses (
  id bigint generated always as identity primary key,
  "place_id" text,
  "doc_number" text,
  "name" text,
  "filing_type" text,
  "filed_date" text,
  "filed_month" text,
  "status" text,
  "city" text,
  "zip" text,
  "last_filing_date" text,
  "latest_annual_report" bigint,
  "entity_id" text,
  "restaurants" text,
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
create index if not exists new_businesses_gov_idx on new_businesses (government_key);
create index if not exists new_businesses_1_idx on new_businesses (place_id, filed_date);
create index if not exists new_businesses_2_idx on new_businesses (doc_number);
create index if not exists new_businesses_3_idx on new_businesses (entity_id);
create index if not exists new_businesses_4_idx on new_businesses (filed_month, filing_type, city);

insert into datasets (id, table_name, title, description) values ('new-businesses', 'new_businesses', $t$New businesses$t$, $d$Every company, nonprofit and partnership filed with Sunbiz since 2016 whose main address is in the county: name, type, filing date, status, city and ZIP, and a link to its state record.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table new_businesses enable row level security;
drop policy if exists "public read" on new_businesses;
create policy "public read" on new_businesses for select using (true);

drop trigger if exists new_businesses_touch on new_businesses;
create trigger new_businesses_touch before update on new_businesses for each row execute function touch_updated_at();
