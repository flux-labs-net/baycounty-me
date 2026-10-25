-- Budgets by year, line by line (/public-money/budget-compare and GET /api/v1/budget-compare): every budget line on
-- record for each government and fiscal year, built by site/page_datasets.py budget_years() from data/budgets/*.json
-- (each year's budget document), data/civic/budgets_detail.json, data/tax/budgets.json and data/tax/finances.json.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists budget_years (
  id bigint generated always as identity primary key,
  "government" text,
  "fiscal_year" bigint,
  "fy" text,
  "basis" text,
  "section" text,
  "line_key" text,
  "name" text,
  "service" text,
  "fund_type" text,
  "amount" numeric,
  "in_total" boolean,
  "status" text,
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
create index if not exists budget_years_gov_idx on budget_years (government_key);
create index if not exists budget_years_gov_id_idx on budget_years (gov_id, basis, fiscal_year);

insert into datasets (id, table_name, title, description) values ('budget-years', 'budget_years', $t$Budgets by year, line by line$t$, $d$Every budget line on record for each government and fiscal year, to compare one year with another: the adopted budget's total, General Fund, funds and General Fund departments, and audited revenue by source and spending by function.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table budget_years enable row level security;
drop policy if exists "public read" on budget_years;
create policy "public read" on budget_years for select using (true);

drop trigger if exists budget_years_touch on budget_years;
create trigger budget_years_touch before update on budget_years for each row execute function touch_updated_at();
