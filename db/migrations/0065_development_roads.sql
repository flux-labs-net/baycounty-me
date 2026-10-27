-- Building and development (/development) and road projects (/roads).
-- Built by site/page_datasets.py from data/development/<county>/ (data/development/fetch.py) and data/roads/<county>/
-- (data/roads/fetch_fdot.py). place_id keeps rows for other places apart (fl-bay = Bay County). Same standard columns,
-- public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists development_projects (
  id bigint generated always as identity primary key,
  "place_id" text,
  "project_id" text,
  "gov_id" text,
  "government" text,
  "name" text,
  "case_number" text,
  "description" text,
  "size" text,
  "location" text,
  "status" text,
  "applied_date" date,
  "approved_date" date,
  "permit_date" date,
  "occupancy_date" date,
  "plans_url" text,
  "lat" numeric,
  "lng" numeric,
  "source" text,
  "source_page" text,
  "fetched" date,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists development_projects_gov_idx on development_projects (government_key);
create index if not exists development_projects_place_idx on development_projects (place_id, gov_id, status, applied_date);

insert into datasets (id, table_name, title, description) values ('development-projects', 'development_projects', $t$Development projects$t$, $d$Development projects on each government's public planning map: name, use, size, address, status and dates.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table development_projects enable row level security;
drop policy if exists "public read" on development_projects;
create policy "public read" on development_projects for select using (true);

drop trigger if exists development_projects_touch on development_projects;
create trigger development_projects_touch before update on development_projects for each row execute function touch_updated_at();

create table if not exists housing_permits (
  id bigint generated always as identity primary key,
  "place_id" text,
  "area_id" text,
  "gov_id" text,
  "area" text,
  "year" bigint,
  "period" text,
  "months" bigint,
  "year_to_date" boolean,
  "months_reported" bigint,
  "estimated" boolean,
  "single_family_units" bigint,
  "single_family_value" numeric,
  "two_to_four_units" bigint,
  "two_to_four_buildings" bigint,
  "two_to_four_value" numeric,
  "five_plus_units" bigint,
  "five_plus_buildings" bigint,
  "five_plus_value" numeric,
  "total_units" numeric,
  "total_value" numeric,
  "summary" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists housing_permits_gov_idx on housing_permits (government_key);
create index if not exists housing_permits_place_idx on housing_permits (place_id, area_id, year);

insert into datasets (id, table_name, title, description) values ('housing-permits', 'housing_permits', $t$New homes permitted$t$, $d$New homes authorized by building permits per year for the county, each city and the unincorporated area (Census Building Permits Survey).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table housing_permits enable row level security;
drop policy if exists "public read" on housing_permits;
create policy "public read" on housing_permits for select using (true);

drop trigger if exists housing_permits_touch on housing_permits;
create trigger housing_permits_touch before update on housing_permits for each row execute function touch_updated_at();

create table if not exists road_contracts (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency" text,
  "contract_id" text,
  "project_id" text,
  "description" text,
  "description_fdot" text,
  "contract_type" text,
  "contract_type_code" text,
  "status" text,
  "active_on_fdot_map" boolean,
  "contractor" text,
  "amount" numeric,
  "let_date" date,
  "executed_date" date,
  "work_began_date" date,
  "estimated_completion_date" date,
  "final_acceptance_date" date,
  "ended_date" date,
  "bid_days" bigint,
  "financial_projects" bigint,
  "length_miles" numeric,
  "lat" numeric,
  "lng" numeric,
  "district" text,
  "website" text,
  "data_date" date,
  "source_url" text,
  "roads" text,
  "fetched" date,
  "vendor_id" text,
  "vendor_ids" jsonb,
  "gov_id" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists road_contracts_gov_idx on road_contracts (government_key);
create index if not exists road_contracts_place_idx on road_contracts (place_id, status, vendor_id, let_date);

insert into datasets (id, table_name, title, description) values ('road-contracts', 'road_contracts', $t$State road contracts$t$, $d$Florida Department of Transportation construction and maintenance contracts in the county since 2016: contractor, amount, dates and status.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table road_contracts enable row level security;
drop policy if exists "public read" on road_contracts;
create policy "public read" on road_contracts for select using (true);

drop trigger if exists road_contracts_touch on road_contracts;
create trigger road_contracts_touch before update on road_contracts for each row execute function touch_updated_at();

create table if not exists road_work_program (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency" text,
  "project_id" text,
  "phase_code" text,
  "phase" text,
  "description" text,
  "description_fdot" text,
  "work_type" text,
  "project_status" text,
  "length_miles" numeric,
  "district" text,
  "source_url" text,
  "fiscal_years" jsonb,
  "first_fiscal_year" bigint,
  "last_fiscal_year" bigint,
  "fetched" date,
  "gov_id" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists road_work_program_gov_idx on road_work_program (government_key);
create index if not exists road_work_program_place_idx on road_work_program (place_id, project_id, phase);

insert into datasets (id, table_name, title, description) values ('road-work-program', 'road_work_program', $t$State road work program$t$, $d$Projects in FDOT's current adopted five-year work program in the county, one row per project and phase, with fiscal years.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table road_work_program enable row level security;
drop policy if exists "public read" on road_work_program;
create policy "public read" on road_work_program for select using (true);

drop trigger if exists road_work_program_touch on road_work_program;
create trigger road_work_program_touch before update on road_work_program for each row execute function touch_updated_at();

