-- Open books (/public-money/checkbook and /public-money/budget-tracker): each government's own accounting, published.
-- Rows are copied here from the private finance workspace (migration 0015) when an admin publishes a file there
-- (POST /api/finance?action=publish, api/_finance/publish.js), so they carry origin 'finance' and the site sync
-- (db/scripts/load.py) never deletes them. Only files that tie to their printed total can be published, never the
-- sample workspace. Payments to private individuals are published without the person's name (payee_kind
-- 'individual'); bank statements and reconciliations are never published.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists checkbook_payments (
  id bigint generated always as identity primary key,
  "government" text,
  "fiscal_year" bigint,
  "paid_on" date,
  "payee" text,
  "payee_kind" text,
  "payee_entity_id" text,
  "amount" numeric,
  "method" text,
  "doc_no" text,
  "invoice_no" text,
  "fund" text,
  "account" text,
  "description" text,
  "source_file" text,
  "upload_id" bigint,
  "published_at" timestamptz,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'finance',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists checkbook_payments_gov_idx on checkbook_payments (government_key);
create index if not exists checkbook_payments_gov_id_idx on checkbook_payments (gov_id, fiscal_year, paid_on);
create index if not exists checkbook_payments_payee_idx on checkbook_payments (payee_entity_id);
create index if not exists checkbook_payments_upload_idx on checkbook_payments (upload_id);

insert into datasets (id, table_name, title, description) values ('checkbook-payments', 'checkbook_payments', $t$Checkbook: every payment$t$, $d$Every payment in each government's own check register (checks, ACH, wires and cards), as published from the files the government sends. Voided checks are left out. Payments to private individuals (refunds, reimbursements) are listed without the person's name.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table checkbook_payments enable row level security;
drop policy if exists "public read" on checkbook_payments;
create policy "public read" on checkbook_payments for select using (true);

drop trigger if exists checkbook_payments_touch on checkbook_payments;
create trigger checkbook_payments_touch before update on checkbook_payments for each row execute function touch_updated_at();

create table if not exists budget_actuals (
  id bigint generated always as identity primary key,
  "government" text,
  "fiscal_year" bigint,
  "as_of" date,
  "line_type" text,
  "fund" text,
  "department" text,
  "account" text,
  "description" text,
  "original_budget" numeric,
  "amended_budget" numeric,
  "actual_ytd" numeric,
  "encumbered" numeric,
  "source_file" text,
  "upload_id" bigint,
  "published_at" timestamptz,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'finance',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists budget_actuals_gov_idx on budget_actuals (government_key);
create index if not exists budget_actuals_gov_id_idx on budget_actuals (gov_id, fiscal_year, as_of);
create index if not exists budget_actuals_upload_idx on budget_actuals (upload_id);

insert into datasets (id, table_name, title, description) values ('budget-actuals', 'budget_actuals', $t$Budget vs. actual, month by month$t$, $d$Each government's budget-vs-actual report as of each month end, line by line: the original and amended budget, spending (or revenue collected) to date and open purchase orders, from the reports the government sends.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table budget_actuals enable row level security;
drop policy if exists "public read" on budget_actuals;
create policy "public read" on budget_actuals for select using (true);

drop trigger if exists budget_actuals_touch on budget_actuals;
create trigger budget_actuals_touch before update on budget_actuals for each row execute function touch_updated_at();

-- Which finance files are published, and by whom: 0048_finance_publish.sql (finance schema only, so the finance tests can apply it).
