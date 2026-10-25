-- CRA tax increment (/public-money/cra-tax-increment): how much property tax Bay County and the cities pay to each
-- Community Redevelopment Agency, by year, with projections to each sunset, built by site/page_datasets.py _cra_increment()
-- from data/cra/tax_increment.json, each CRA's budget_by_year and data/tax/millage.json.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists cra_agencies (
  id bigint generated always as identity primary key,
  "cra_id" text,
  "cra" text,
  "city" text,
  "created" text,
  "base_year" text,
  "first_fy_on_record" bigint,
  "years_filled" bigint,
  "increment_fy2025" numeric,
  "county_share_fy2025" numeric,
  "county_fy2025" numeric,
  "city_fy2025" numeric,
  "paid_on_record" numeric,
  "county_paid_on_record" numeric,
  "sunset_fy" bigint,
  "sunset_assumed" boolean,
  "sunset_basis" text,
  "yearly_cap" numeric,
  "to_come_low" numeric,
  "to_come_mid" numeric,
  "to_come_high" numeric,
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
create index if not exists cra_agencies_gov_idx on cra_agencies (government_key);
create index if not exists cra_agencies_key_idx on cra_agencies ("cra_id");

insert into datasets (id, table_name, title, description) values ('cra-agencies', 'cra_agencies', $t$CRAs: tax increment by agency$t$, $d$One row per Community Redevelopment Agency that collects tax increment in Bay County: base year, FY2025 increment and the county and city shares, the total on record, sunset date and its basis, and the increment still to come under three growth scenarios.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_agencies enable row level security;
drop policy if exists "public read" on cra_agencies;
create policy "public read" on cra_agencies for select using (true);

drop trigger if exists cra_agencies_touch on cra_agencies;
create trigger cra_agencies_touch before update on cra_agencies for each row execute function touch_updated_at();

create table if not exists cra_tax_increment (
  id bigint generated always as identity primary key,
  "cra_id" text,
  "cra" text,
  "fiscal_year" bigint,
  "fy" text,
  "basis" text,
  "scenario" text,
  "increment" numeric,
  "county_share" numeric,
  "county_amount" numeric,
  "city_amount" numeric,
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
create index if not exists cra_tax_increment_gov_idx on cra_tax_increment (government_key);
create index if not exists cra_tax_increment_key_idx on cra_tax_increment ("cra_id", "scenario", "fiscal_year");

insert into datasets (id, table_name, title, description) values ('cra-tax-increment', 'cra_tax_increment', $t$CRAs: tax increment by year$t$, $d$Property tax paid to each CRA by fiscal year, split between Bay County and the city by millage: reported and gap-filled history, then adopted budgets and 3%, 6% or 9% growth projections to each CRA's sunset.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_tax_increment enable row level security;
drop policy if exists "public read" on cra_tax_increment;
create policy "public read" on cra_tax_increment for select using (true);

drop trigger if exists cra_tax_increment_touch on cra_tax_increment;
create trigger cra_tax_increment_touch before update on cra_tax_increment for each row execute function touch_updated_at();

create table if not exists cra_increment_checks (
  id bigint generated always as identity primary key,
  "figure" text,
  "fiscal_year" bigint,
  "official_figure" numeric,
  "estimate" numeric,
  "difference_pct" numeric,
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
create index if not exists cra_increment_checks_gov_idx on cra_increment_checks (government_key);

insert into datasets (id, table_name, title, description) values ('cra-increment-checks', 'cra_increment_checks', $t$CRAs: estimate checked against official figures$t$, $d$Official county figures for CRA payments next to this estimate for the same year, with the difference in percent.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_increment_checks enable row level security;
drop policy if exists "public read" on cra_increment_checks;
create policy "public read" on cra_increment_checks for select using (true);

drop trigger if exists cra_increment_checks_touch on cra_increment_checks;
create trigger cra_increment_checks_touch before update on cra_increment_checks for each row execute function touch_updated_at();
