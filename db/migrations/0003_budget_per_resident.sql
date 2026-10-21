-- Budget cost per resident, by service: FY2026 General Fund budget per resident for each service, with the city median.
-- Built by site/money_pages.py (per_resident_rows), the same grouping the budget explorer uses.
create table if not exists budget_per_resident (
  id bigint generated always as identity primary key,
  "government" text,
  "kind" text,
  "fiscal_year" text,
  "service_id" text,
  "service" text,
  "general_fund_amount" numeric,
  "residents" bigint,
  "per_resident" numeric,
  "city_median_per_resident" numeric,
  "vs_city_median_pct" numeric,
  "in_city_median" boolean,
  "departments_included" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists budget_per_resident_gov_idx on budget_per_resident (government_key);
create index if not exists budget_per_resident_service_idx on budget_per_resident (service_id);
alter table budget_per_resident enable row level security;
drop policy if exists "public read" on budget_per_resident;
create policy "public read" on budget_per_resident for select using (true);
insert into datasets (id, table_name, title, description) values ('budget-per-resident', 'budget_per_resident', $t$Budget cost per resident, by service$t$, $d$FY2026 General Fund budget per resident for police, fire, streets, parks, libraries, planning and administration, with the city median. Departments are grouped by name; the departments_included column shows what was added together. Schools are not included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();
