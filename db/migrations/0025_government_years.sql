-- Governments by year (/governments/<slug> top cards): one row per government per fiscal year, built by
-- site/page_datasets.py government_years() from the budget, millage, audited-actuals, debt and staffing research files.
-- A blank value means no record for that year. Same standard columns, public read policy and updated_at trigger as
-- every other dataset table (see 0021_page_datasets.sql).

create table if not exists government_years (
  id bigint generated always as identity primary key,
  "government" text,
  "fiscal_year" bigint,
  "fy" text,
  "period" text,
  "budget_total" numeric,
  "general_fund" numeric,
  "budget_status" text,
  "budget_note" text,
  "budget_excludes_transfers" boolean,
  "budget_source_url" text,
  "tax_year" bigint,
  "millage" numeric,
  "rolled_back_rate" numeric,
  "property_tax_levy" numeric,
  "millage_source_url" text,
  "actual_revenue" numeric,
  "actual_spending" numeric,
  "actuals_source_url" text,
  "population" bigint,
  "population_year" bigint,
  "population_source" text,
  "debt_total" numeric,
  "debt_source_url" text,
  "employees_fte" numeric,
  "employees_note" text,
  "employees_source_url" text,
  "budget_per_resident" numeric,
  "source_url" text,
  gov_id text,
  date_start text,
  date_end text,
  date_precision text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists government_years_gov_idx on government_years (government_key);
create index if not exists government_years_gov_id_idx on government_years (gov_id, fiscal_year);

insert into datasets (id, table_name, title, description) values ('government-years', 'government_years', $t$Governments by year$t$, $d$One row per government per fiscal year: adopted budget and its status, general fund, property tax rate and levy, audited actual revenue and spending, residents, audited debt and staff count. A blank means no record for that year. fiscal_year is the year the fiscal year ends (FY2026 = Oct 2025 to Sep 2026; schools Jul to Jun).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table government_years enable row level security;
drop policy if exists "public read" on government_years;
create policy "public read" on government_years for select using (true);

drop trigger if exists government_years_touch on government_years;
create trigger government_years_touch before update on government_years for each row execute function touch_updated_at();
