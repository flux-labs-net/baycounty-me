-- BayCounty.me database, initial schema.
-- Every public dataset gets a typed table. Each row records where it came from (origin, ingest run, source_url)
-- so data loaded from the site build ('site_build') can be refreshed without touching rows added by hand or by scrapers.
-- Everything is public record: anyone may read; only the service role (server-side keys) may write.

create table if not exists governments (
  key text primary key,            -- county, schools, pc, pcb, lh, cw, sp, parker, mb, constitutional, special
  slug text unique,
  short_name text not null,
  name text not null,
  kind text,                       -- county, schools, city, constitutional, special
  population_2025 bigint,
  website text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists government_aliases (
  alias text primary key,          -- any spelling used in source data, lowercased: 'bay county bocc', 'city of lynn haven'
  government_key text not null references governments(key) on delete cascade
);

create table if not exists sources (
  id bigint generated always as identity primary key,
  url text unique not null,
  title text,
  publisher text,
  doc_type text,                   -- budget, minutes, audit, pay plan, contract, news, statute, dataset ...
  retrieved_at date,
  created_at timestamptz not null default now()
);

create table if not exists ingest_runs (
  id bigint generated always as identity primary key,
  origin text not null,            -- site_build, manual, scraper:<name>, import:<file>
  dataset text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  rows_in integer,
  rows_deleted integer,
  status text not null default 'running',  -- running, ok, failed
  git_sha text,
  notes text
);

create table if not exists datasets (
  id text primary key,             -- matches the API dataset id, e.g. salary-positions
  table_name text unique not null,
  title text not null,
  description text,
  updated_at timestamptz not null default now()
);

-- Lossless copy of every research file in data/ (the site build still reads these).
create table if not exists raw_files (
  path text primary key,           -- e.g. data/votes/votes.json
  sha256 text not null,
  bytes integer not null,
  content jsonb not null,
  loaded_at timestamptz not null default now(),
  ingest_run_id bigint references ingest_runs(id)
);

-- Government profiles: One row per government: population, budget, tax rate, debt, audit findings, votes, staff, utility bill and Hurricane Michael money.
create table if not exists government_profiles (
  id bigint generated always as identity primary key,
  "government" text,
  "kind" text,
  "population_2025" numeric,
  "budget_total" numeric,
  "general_fund" numeric,
  "budget_status" text,
  "millage" numeric,
  "property_tax_levy" numeric,
  "debt_total" numeric,
  "debt_year" text,
  "audit_year" text,
  "audit_findings" bigint,
  "repeat_findings" bigint,
  "votes_recorded" bigint,
  "split_votes" bigint,
  "employees_fte" numeric,
  "typical_utility_bill" numeric,
  "fema_michael_obligated" numeric,
  "page" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists government_profiles_gov_idx on government_profiles (government_key);
insert into datasets (id, table_name, title, description) values ('government-profiles', 'government_profiles', $t$Government profiles$t$, $d$One row per government: population, budget, tax rate, debt, audit findings, votes, staff, utility bill and Hurricane Michael money.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Recorded votes: Money votes by the County Commission, School Board, city commissions and CRA boards, with how each member voted.
create table if not exists votes (
  id bigint generated always as identity primary key,
  "date" date,
  "government" text,
  "board" text,
  "category" text,
  "headline" text,
  "summary" text,
  "amount" numeric,
  "outcome" text,
  "tally" text,
  "split" boolean,
  "voted_yes" text,
  "voted_no" text,
  "absent_or_abstained" text,
  "agenda_item" text,
  "source_title" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists votes_gov_idx on votes (government_key);
insert into datasets (id, table_name, title, description) values ('votes', 'votes', $t$Recorded votes$t$, $d$Money votes by the County Commission, School Board, city commissions and CRA boards, with how each member voted.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Votes by member: One row per member per vote (long format), for tallying individual records.
create table if not exists member_votes (
  id bigint generated always as identity primary key,
  "date" date,
  "board" text,
  "member" text,
  "vote" text,
  "headline" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists member_votes_gov_idx on member_votes (government_key);
insert into datasets (id, table_name, title, description) values ('member-votes', 'member_votes', $t$Votes by member$t$, $d$One row per member per vote (long format), for tallying individual records.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Contracts: Major contracts approved since October 2022: vendor, amount, purpose, how awarded.
create table if not exists contracts (
  id bigint generated always as identity primary key,
  "government" text,
  "vendor" text,
  "amount" numeric,
  "purpose" text,
  "date" date,
  "method" text,
  "source_title" text,
  "source_url" text,
  "notes" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists contracts_gov_idx on contracts (government_key);
insert into datasets (id, table_name, title, description) values ('contracts', 'contracts', $t$Contracts$t$, $d$Major contracts approved since October 2022: vendor, amount, purpose, how awarded.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Change orders: Contract change orders with original and new totals.
create table if not exists change_orders (
  id bigint generated always as identity primary key,
  "government" text,
  "vendor" text,
  "project" text,
  "original_amount" numeric,
  "change_amount" numeric,
  "new_total" numeric,
  "pct_of_original" numeric,
  "reason" text,
  "date" date,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists change_orders_gov_idx on change_orders (government_key);
insert into datasets (id, table_name, title, description) values ('change-orders', 'change_orders', $t$Change orders$t$, $d$Contract change orders with original and new totals.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Emergency purchases: Purchases made under emergency rules without normal bidding.
create table if not exists emergency_purchases (
  id bigint generated always as identity primary key,
  "government" text,
  "vendor" text,
  "amount" numeric,
  "purpose" text,
  "date" date,
  "basis" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists emergency_purchases_gov_idx on emergency_purchases (government_key);
insert into datasets (id, table_name, title, description) values ('emergency-purchases', 'emergency_purchases', $t$Emergency purchases$t$, $d$Purchases made under emergency rules without normal bidding.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- CRA spending: What Bay County's Community Redevelopment Agencies paid for, with locations.
create table if not exists cra_payments (
  id bigint generated always as identity primary key,
  "cra" text,
  "city" text,
  "payee" text,
  "amount" numeric,
  "date_or_fy" text,
  "status" text,
  "category" text,
  "purpose" text,
  "location_name" text,
  "district" text,
  "lat" numeric,
  "lng" numeric,
  "count" boolean,
  "source_title" text,
  "source_url" text,
  "notes" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists cra_payments_gov_idx on cra_payments (government_key);
insert into datasets (id, table_name, title, description) values ('cra-payments', 'cra_payments', $t$CRA spending$t$, $d$What Bay County's Community Redevelopment Agencies paid for, with locations.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Property tax rates: Millage, rolled-back rate and levy for every taxing authority, by tax year.
create table if not exists property_tax_rates (
  id bigint generated always as identity primary key,
  "authority_id" text,
  "authority" text,
  "kind" text,
  "school" boolean,
  "tax_year" numeric,
  "millage" numeric,
  "rolled_back_rate" numeric,
  "levy" numeric,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists property_tax_rates_gov_idx on property_tax_rates (government_key);
insert into datasets (id, table_name, title, description) values ('property-tax-rates', 'property_tax_rates', $t$Property tax rates$t$, $d$Millage, rolled-back rate and levy for every taxing authority, by tax year.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Debt by government: Total debt from the latest audited financial statements.
create table if not exists debt (
  id bigint generated always as identity primary key,
  "government" text,
  "fy" text,
  "total_debt" numeric,
  "total_debt_note" text,
  "population_2025_estimate" numeric,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists debt_gov_idx on debt (government_key);
insert into datasets (id, table_name, title, description) values ('debt', 'debt', $t$Debt by government$t$, $d$Total debt from the latest audited financial statements.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Audit findings: Findings from audits filed with the Florida Auditor General, in plain English.
create table if not exists audit_findings (
  id bigint generated always as identity primary key,
  "government" text,
  "fy" text,
  "opinion" text,
  "finding" text,
  "plain_english" text,
  "repeat" boolean,
  "management_response" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists audit_findings_gov_idx on audit_findings (government_key);
insert into datasets (id, table_name, title, description) values ('audit-findings', 'audit_findings', $t$Audit findings$t$, $d$Findings from audits filed with the Florida Auditor General, in plain English.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Hurricane Michael FEMA projects: Every FEMA Public Assistance project in Bay County for disaster DR-4399.
create table if not exists fema_michael_projects (
  id bigint generated always as identity primary key,
  "applicant" text,
  "project" bigint,
  "title" text,
  "category" text,
  "federal_share" numeric,
  "eligible_amount" numeric,
  "first_obligated" date,
  "last_obligated" date,
  "status" text,
  "size" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists fema_michael_projects_gov_idx on fema_michael_projects (government_key);
insert into datasets (id, table_name, title, description) values ('fema-michael-projects', 'fema_michael_projects', $t$Hurricane Michael FEMA projects$t$, $d$Every FEMA Public Assistance project in Bay County for disaster DR-4399.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Half-cent sales tax projects: Every infrastructure sales tax project on the county map, with status and cost.
create table if not exists sales_tax_projects (
  id bigint generated always as identity primary key,
  "name" text,
  "government" text,
  "category" text,
  "status" text,
  "pct_complete" numeric,
  "promised_cost" numeric,
  "programmed_cost" numeric,
  "actual_cost" text,
  "fiscal_years" text,
  "location" text,
  "lat" numeric,
  "lng" numeric,
  "description" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists sales_tax_projects_gov_idx on sales_tax_projects (government_key);
insert into datasets (id, table_name, title, description) values ('sales-tax-projects', 'sales_tax_projects', $t$Half-cent sales tax projects$t$, $d$Every infrastructure sales tax project on the county map, with status and cost.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Tourist tax collections: Bed tax collected by zone and fiscal year.
create table if not exists bed_tax_collections (
  id bigint generated always as identity primary key,
  "fy" bigint,
  "district" text,
  "amount" numeric,
  "partial" boolean,
  "period" text,
  "basis" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists bed_tax_collections_gov_idx on bed_tax_collections (government_key);
insert into datasets (id, table_name, title, description) values ('bed-tax-collections', 'bed_tax_collections', $t$Tourist tax collections$t$, $d$Bed tax collected by zone and fiscal year.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Fees on tax bills: Non-ad valorem assessments: fire, stormwater, CRA and other flat fees.
create table if not exists fees_assessments (
  id bigint generated always as identity primary key,
  "government" text,
  "area" text,
  "name" text,
  "category" text,
  "how_charged" text,
  "rate" text,
  "residential_single_family_amount" jsonb,
  "fiscal_year" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists fees_assessments_gov_idx on fees_assessments (government_key);
insert into datasets (id, table_name, title, description) values ('fees-assessments', 'fees_assessments', $t$Fees on tax bills$t$, $d$Non-ad valorem assessments: fire, stormwater, CRA and other flat fees.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Officials and pay: Salaries of top elected and appointed officials.
create table if not exists officials_pay (
  id bigint generated always as identity primary key,
  "government" text,
  "title" text,
  "name" text,
  "annual" bigint,
  "year" text,
  "basis" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists officials_pay_gov_idx on officials_pay (government_key);
insert into datasets (id, table_name, title, description) values ('officials-pay', 'officials_pay', $t$Officials and pay$t$, $d$Salaries of top elected and appointed officials.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Upcoming meetings: Scheduled and expected meetings for every board.
create table if not exists meetings (
  id bigint generated always as identity primary key,
  "board" text,
  "title" text,
  "start" text,
  "location" text,
  "agenda_url" text,
  "packet_url" text,
  "minutes_url" text,
  "source" text,
  "status" text,
  "past" boolean,
  "detail_url" text,
  "items" jsonb,
  "time_from_schedule" boolean,
  "calendar_source" text,
  "expected" boolean,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists meetings_gov_idx on meetings (government_key);
insert into datasets (id, table_name, title, description) values ('meetings', 'meetings', $t$Upcoming meetings$t$, $d$Scheduled and expected meetings for every board.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Campaign finance totals: Money raised by current officeholders (organizations named; individuals summed).
create table if not exists campaign_finance (
  id bigint generated always as identity primary key,
  "official" text,
  "office" text,
  "gov" text,
  "election" text,
  "total_raised" numeric,
  "total_spent" numeric,
  "n_contributions" bigint,
  "report_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists campaign_finance_gov_idx on campaign_finance (government_key);
insert into datasets (id, table_name, title, description) values ('campaign-finance', 'campaign_finance', $t$Campaign finance totals$t$, $d$Money raised by current officeholders (organizations named; individuals summed).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Who gets paid: Payments to vendors from check registers, totaled by vendor and year.
create table if not exists vendor_payments (
  id bigint generated always as identity primary key,
  "government" text,
  "vendor" text,
  "total" numeric,
  "payments" numeric,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists vendor_payments_gov_idx on vendor_payments (government_key);
insert into datasets (id, table_name, title, description) values ('vendor-payments', 'vendor_payments', $t$Who gets paid$t$, $d$Payments to vendors from check registers, totaled by vendor and year.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Bonds and notes: Outstanding bond and note issues of Bay County governments.
create table if not exists bonds (
  id bigint generated always as identity primary key,
  "gov" text,
  "issuer" text,
  "series" text,
  "type" text,
  "par_amount" numeric,
  "par_note" text,
  "dated_date" text,
  "final_maturity" text,
  "interest_rate" text,
  "purpose" text,
  "security" text,
  "outstanding" numeric,
  "outstanding_as_of" text,
  "placement" text,
  "rating" text,
  "official_statement_url" text,
  "status" text,
  "sources" jsonb,
  "rating_note" text,
  "emma_issuer_urls" jsonb,
  "notes" text,
  "outstanding_note" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists bonds_gov_idx on bonds (government_key);
insert into datasets (id, table_name, title, description) values ('bonds', 'bonds', $t$Bonds and notes$t$, $d$Outstanding bond and note issues of Bay County governments.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Budgets by fund and department: Adopted budgets broken down by fund and general-fund department.
create table if not exists budget_detail (
  id bigint generated always as identity primary key,
  "government" text,
  "fiscal_year" text,
  "level" text,
  "name" text,
  "amount" numeric,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists budget_detail_gov_idx on budget_detail (government_key);
insert into datasets (id, table_name, title, description) values ('budget-detail', 'budget_detail', $t$Budgets by fund and department$t$, $d$Adopted budgets broken down by fund and general-fund department.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Public salaries by job title: Pay ranges, budgeted positions and unnamed actual salaries by job title for the county, constitutional officers, school district, cities, airport and port.
create table if not exists salary_positions (
  id bigint generated always as identity primary key,
  "employer" text,
  "employer_id" text,
  "government" text,
  "fiscal_year" text,
  "title" text,
  "department" text,
  "category" text,
  "grade" text,
  "pay_min" numeric,
  "pay_mid" numeric,
  "pay_max" numeric,
  "pay_basis" text,
  "hourly_min" numeric,
  "hourly_max" numeric,
  "actual_salaries" jsonb,
  "budgeted_fte" numeric,
  "union" text,
  "source_url" text,
  "notes" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists salary_positions_gov_idx on salary_positions (government_key);
insert into datasets (id, table_name, title, description) values ('salary-positions', 'salary_positions', $t$Public salaries by job title$t$, $d$Pay ranges, budgeted positions and unnamed actual salaries by job title for the county, constitutional officers, school district, cities, airport and port.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Salaries of officials and leaders: Named salaries of elected officials and top appointed leaders only.
create table if not exists salary_leaders (
  id bigint generated always as identity primary key,
  "employer" text,
  "employer_id" text,
  "government" text,
  "name" text,
  "title" text,
  "department" text,
  "salary" numeric,
  "basis" text,
  "as_of" text,
  "source_url" text,
  "notes" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists salary_leaders_gov_idx on salary_leaders (government_key);
insert into datasets (id, table_name, title, description) values ('salary-leaders', 'salary_leaders', $t$Salaries of officials and leaders$t$, $d$Named salaries of elected officials and top appointed leaders only.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- 2026 local candidates: Every 2026 local race and candidate with status, platform in their own words and campaign money totals.
create table if not exists candidates_2026 (
  id bigint generated always as identity primary key,
  "race_id" text,
  "office" text,
  "government" text,
  "race_status" text,
  "candidate" text,
  "party" text,
  "incumbent" boolean,
  "status" text,
  "website" text,
  "platform" jsonb,
  "platform_sources" jsonb,
  "total_raised" numeric,
  "total_spent" numeric,
  "from_individuals_total" numeric,
  "from_individuals_count" numeric,
  "from_organizations" numeric,
  "own_money" numeric,
  "reports_through" date,
  "finance_report_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists candidates_2026_gov_idx on candidates_2026 (government_key);
insert into datasets (id, table_name, title, description) values ('candidates-2026', 'candidates_2026', $t$2026 local candidates$t$, $d$Every 2026 local race and candidate with status, platform in their own words and campaign money totals.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- 2026 contributions from organizations: Every contribution from a business, committee or party to a 2026 local candidate. Individual donors are not included.
create table if not exists campaign_contributions_2026 (
  id bigint generated always as identity primary key,
  "candidate" text,
  "office" text,
  "contributor" text,
  "contributor_type" text,
  "city" text,
  "amount" numeric,
  "date" date,
  "kind" text,
  "report_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists campaign_contributions_2026_gov_idx on campaign_contributions_2026 (government_key);
insert into datasets (id, table_name, title, description) values ('campaign-contributions-2026', 'campaign_contributions_2026', $t$2026 contributions from organizations$t$, $d$Every contribution from a business, committee or party to a 2026 local candidate. Individual donors are not included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Property tax exemptions (2026 roll): Every exemption type on the 2026 tax roll: parcels, value exempted and estimated tax removed.
create table if not exists property_tax_exemptions (
  id bigint generated always as identity primary key,
  "code" text,
  "exemption" text,
  "statute" text,
  "applies_to" text,
  "parcels" numeric,
  "homesteads" bigint,
  "value_exempted" numeric,
  "estimated_tax_removed" numeric,
  "roll" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists property_tax_exemptions_gov_idx on property_tax_exemptions (government_key);
insert into datasets (id, table_name, title, description) values ('property-tax-exemptions', 'property_tax_exemptions', $t$Property tax exemptions (2026 roll)$t$, $d$Every exemption type on the 2026 tax roll: parcels, value exempted and estimated tax removed.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

-- Public read, server-side write. (In Supabase, anon/authenticated are the public roles; service_role bypasses RLS.)
alter table governments enable row level security;
drop policy if exists "public read" on governments;
create policy "public read" on governments for select using (true);
alter table government_aliases enable row level security;
drop policy if exists "public read" on government_aliases;
create policy "public read" on government_aliases for select using (true);
alter table sources enable row level security;
drop policy if exists "public read" on sources;
create policy "public read" on sources for select using (true);
alter table ingest_runs enable row level security;
drop policy if exists "public read" on ingest_runs;
create policy "public read" on ingest_runs for select using (true);
alter table datasets enable row level security;
drop policy if exists "public read" on datasets;
create policy "public read" on datasets for select using (true);
alter table raw_files enable row level security;
drop policy if exists "public read" on raw_files;
create policy "public read" on raw_files for select using (true);
alter table government_profiles enable row level security;
drop policy if exists "public read" on government_profiles;
create policy "public read" on government_profiles for select using (true);
alter table votes enable row level security;
drop policy if exists "public read" on votes;
create policy "public read" on votes for select using (true);
alter table member_votes enable row level security;
drop policy if exists "public read" on member_votes;
create policy "public read" on member_votes for select using (true);
alter table contracts enable row level security;
drop policy if exists "public read" on contracts;
create policy "public read" on contracts for select using (true);
alter table change_orders enable row level security;
drop policy if exists "public read" on change_orders;
create policy "public read" on change_orders for select using (true);
alter table emergency_purchases enable row level security;
drop policy if exists "public read" on emergency_purchases;
create policy "public read" on emergency_purchases for select using (true);
alter table cra_payments enable row level security;
drop policy if exists "public read" on cra_payments;
create policy "public read" on cra_payments for select using (true);
alter table property_tax_rates enable row level security;
drop policy if exists "public read" on property_tax_rates;
create policy "public read" on property_tax_rates for select using (true);
alter table debt enable row level security;
drop policy if exists "public read" on debt;
create policy "public read" on debt for select using (true);
alter table audit_findings enable row level security;
drop policy if exists "public read" on audit_findings;
create policy "public read" on audit_findings for select using (true);
alter table fema_michael_projects enable row level security;
drop policy if exists "public read" on fema_michael_projects;
create policy "public read" on fema_michael_projects for select using (true);
alter table sales_tax_projects enable row level security;
drop policy if exists "public read" on sales_tax_projects;
create policy "public read" on sales_tax_projects for select using (true);
alter table bed_tax_collections enable row level security;
drop policy if exists "public read" on bed_tax_collections;
create policy "public read" on bed_tax_collections for select using (true);
alter table fees_assessments enable row level security;
drop policy if exists "public read" on fees_assessments;
create policy "public read" on fees_assessments for select using (true);
alter table officials_pay enable row level security;
drop policy if exists "public read" on officials_pay;
create policy "public read" on officials_pay for select using (true);
alter table meetings enable row level security;
drop policy if exists "public read" on meetings;
create policy "public read" on meetings for select using (true);
alter table campaign_finance enable row level security;
drop policy if exists "public read" on campaign_finance;
create policy "public read" on campaign_finance for select using (true);
alter table vendor_payments enable row level security;
drop policy if exists "public read" on vendor_payments;
create policy "public read" on vendor_payments for select using (true);
alter table bonds enable row level security;
drop policy if exists "public read" on bonds;
create policy "public read" on bonds for select using (true);
alter table budget_detail enable row level security;
drop policy if exists "public read" on budget_detail;
create policy "public read" on budget_detail for select using (true);
alter table salary_positions enable row level security;
drop policy if exists "public read" on salary_positions;
create policy "public read" on salary_positions for select using (true);
alter table salary_leaders enable row level security;
drop policy if exists "public read" on salary_leaders;
create policy "public read" on salary_leaders for select using (true);
alter table candidates_2026 enable row level security;
drop policy if exists "public read" on candidates_2026;
create policy "public read" on candidates_2026 for select using (true);
alter table campaign_contributions_2026 enable row level security;
drop policy if exists "public read" on campaign_contributions_2026;
create policy "public read" on campaign_contributions_2026 for select using (true);
alter table property_tax_exemptions enable row level security;
drop policy if exists "public read" on property_tax_exemptions;
create policy "public read" on property_tax_exemptions for select using (true);

-- Keep updated_at current on edits made in the table editor or by scripts.
create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists governments_touch on governments;
create trigger governments_touch before update on governments for each row execute function touch_updated_at();
drop trigger if exists government_profiles_touch on government_profiles;
create trigger government_profiles_touch before update on government_profiles for each row execute function touch_updated_at();
drop trigger if exists votes_touch on votes;
create trigger votes_touch before update on votes for each row execute function touch_updated_at();
drop trigger if exists member_votes_touch on member_votes;
create trigger member_votes_touch before update on member_votes for each row execute function touch_updated_at();
drop trigger if exists contracts_touch on contracts;
create trigger contracts_touch before update on contracts for each row execute function touch_updated_at();
drop trigger if exists change_orders_touch on change_orders;
create trigger change_orders_touch before update on change_orders for each row execute function touch_updated_at();
drop trigger if exists emergency_purchases_touch on emergency_purchases;
create trigger emergency_purchases_touch before update on emergency_purchases for each row execute function touch_updated_at();
drop trigger if exists cra_payments_touch on cra_payments;
create trigger cra_payments_touch before update on cra_payments for each row execute function touch_updated_at();
drop trigger if exists property_tax_rates_touch on property_tax_rates;
create trigger property_tax_rates_touch before update on property_tax_rates for each row execute function touch_updated_at();
drop trigger if exists debt_touch on debt;
create trigger debt_touch before update on debt for each row execute function touch_updated_at();
drop trigger if exists audit_findings_touch on audit_findings;
create trigger audit_findings_touch before update on audit_findings for each row execute function touch_updated_at();
drop trigger if exists fema_michael_projects_touch on fema_michael_projects;
create trigger fema_michael_projects_touch before update on fema_michael_projects for each row execute function touch_updated_at();
drop trigger if exists sales_tax_projects_touch on sales_tax_projects;
create trigger sales_tax_projects_touch before update on sales_tax_projects for each row execute function touch_updated_at();
drop trigger if exists bed_tax_collections_touch on bed_tax_collections;
create trigger bed_tax_collections_touch before update on bed_tax_collections for each row execute function touch_updated_at();
drop trigger if exists fees_assessments_touch on fees_assessments;
create trigger fees_assessments_touch before update on fees_assessments for each row execute function touch_updated_at();
drop trigger if exists officials_pay_touch on officials_pay;
create trigger officials_pay_touch before update on officials_pay for each row execute function touch_updated_at();
drop trigger if exists meetings_touch on meetings;
create trigger meetings_touch before update on meetings for each row execute function touch_updated_at();
drop trigger if exists campaign_finance_touch on campaign_finance;
create trigger campaign_finance_touch before update on campaign_finance for each row execute function touch_updated_at();
drop trigger if exists vendor_payments_touch on vendor_payments;
create trigger vendor_payments_touch before update on vendor_payments for each row execute function touch_updated_at();
drop trigger if exists bonds_touch on bonds;
create trigger bonds_touch before update on bonds for each row execute function touch_updated_at();
drop trigger if exists budget_detail_touch on budget_detail;
create trigger budget_detail_touch before update on budget_detail for each row execute function touch_updated_at();
drop trigger if exists salary_positions_touch on salary_positions;
create trigger salary_positions_touch before update on salary_positions for each row execute function touch_updated_at();
drop trigger if exists salary_leaders_touch on salary_leaders;
create trigger salary_leaders_touch before update on salary_leaders for each row execute function touch_updated_at();
drop trigger if exists candidates_2026_touch on candidates_2026;
create trigger candidates_2026_touch before update on candidates_2026 for each row execute function touch_updated_at();
drop trigger if exists campaign_contributions_2026_touch on campaign_contributions_2026;
create trigger campaign_contributions_2026_touch before update on campaign_contributions_2026 for each row execute function touch_updated_at();
drop trigger if exists property_tax_exemptions_touch on property_tax_exemptions;
create trigger property_tax_exemptions_touch before update on property_tax_exemptions for each row execute function touch_updated_at();
