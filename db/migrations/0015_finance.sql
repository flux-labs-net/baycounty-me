-- Finance workspace (budget anomaly dashboard, Phase 1). One workspace per government. Staff upload accounting
-- exports (budget vs. actual, check registers, bank statements, bank reconciliations); each file is stored unchanged
-- in the private "finance-uploads" bucket, parsed into the tables below, tied out to its printed total, and then
-- checked by the flag rules (api/_finance/rules.js).
--
-- Private: RLS is on everywhere and the schema is not exposed through Supabase's data API, so only the service role
-- or DATABASE_URL can read it (the Vercel functions). Membership policies keyed to auth.uid() are added when the auth
-- schema exists, so the mobile app can read its own workspace once the schema is exposed and users sign in.
create schema if not exists finance;

create table if not exists finance.workspaces (
  id text primary key,                           -- 'lh'
  government_key text not null,                  -- matches public.governments.key
  name text not null,
  fy_start_month integer not null default 10,    -- Florida cities: fiscal year starts Oct 1
  settings jsonb not null default '{}',          -- rule thresholds (see api/_finance/rules.js DEFAULTS)
  created_at timestamptz not null default now()
);

-- Who can see a workspace. user_id links to auth.users once app sign-in exists; until then email is the key.
create table if not exists finance.members (
  id bigint generated always as identity primary key,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  email text not null,
  user_id uuid,
  role text not null default 'viewer' check (role in ('owner', 'reviewer', 'uploader', 'viewer', 'auditor')),
  created_at timestamptz not null default now(),
  unique (workspace_id, email)
);
create index if not exists members_user on finance.members (user_id);

-- One row per uploaded file.
create table if not exists finance.uploads (
  id bigint generated always as identity primary key,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  shape text check (shape in ('budget', 'disbursements', 'bank_transactions', 'bank_recs')),
  source_system text,                            -- 'Tyler Incode', 'QuickBooks', ... when known
  original_name text not null,
  storage_path text,                             -- finance-uploads/<workspace>/<sha256>/<name>
  sha256 text not null,
  bytes bigint,
  uploaded_by text,
  uploaded_at timestamptz not null default now(),
  period_start date,
  period_end date,
  row_count integer,
  parsed_total numeric(16,2),
  printed_total numeric(16,2),
  tie_status text check (tie_status in ('ties', 'mismatch', 'no_total')),
  tie_difference numeric(16,2),
  status text not null default 'preview' check (status in ('preview', 'committed', 'held', 'failed', 'replaced')),
  mapping jsonb,                                 -- {canonical_field: "Source column"}
  warnings jsonb not null default '[]',
  error text
);
create index if not exists uploads_ws on finance.uploads (workspace_id, uploaded_at desc);
create unique index if not exists uploads_one_commit on finance.uploads (workspace_id, sha256) where status = 'committed';

-- Saved column mappings, so next month's export from the same system maps itself.
create table if not exists finance.mappings (
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  shape text not null,
  signature text not null,                       -- hash of the normalized header row
  mapping jsonb not null,
  headers jsonb not null,
  source_system text,
  updated_at timestamptz not null default now(),
  primary key (workspace_id, shape, signature)
);

create table if not exists finance.budget_lines (
  id bigint generated always as identity primary key,
  upload_id bigint not null references finance.uploads(id) on delete cascade,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  fiscal_year integer,                           -- FY2026 = Oct 1, 2025 - Sep 30, 2026
  as_of date,
  fund text, department text, account text, description text,
  original_budget numeric(16,2), amended_budget numeric(16,2), actual_ytd numeric(16,2), encumbered numeric(16,2),
  source_row integer
);
create index if not exists budget_ws on finance.budget_lines (workspace_id, fiscal_year, as_of);

create table if not exists finance.disbursements (
  id bigint generated always as identity primary key,
  upload_id bigint not null references finance.uploads(id) on delete cascade,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  paid_on date,
  doc_no text,                                   -- check or EFT number
  method text,                                   -- check, ach, wire, card, other
  payee text,
  payee_key text,                                -- normalized for matching
  amount numeric(16,2),
  invoice_no text,
  fund text, account text, description text,
  is_void boolean not null default false,
  source_row integer
);
create index if not exists disb_ws on finance.disbursements (workspace_id, paid_on);
create index if not exists disb_payee on finance.disbursements (workspace_id, payee_key);

-- Account numbers are never stored: account_label keeps only the last 4 digits, account_hash matches accounts across files.
create table if not exists finance.bank_transactions (
  id bigint generated always as identity primary key,
  upload_id bigint not null references finance.uploads(id) on delete cascade,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  account_label text, account_hash text,
  posted_on date,
  amount numeric(16,2),                          -- signed: withdrawals negative
  check_no text,
  description text,
  source_row integer
);
create index if not exists bank_ws on finance.bank_transactions (workspace_id, account_hash, posted_on);

create table if not exists finance.bank_recs (
  id bigint generated always as identity primary key,
  upload_id bigint not null references finance.uploads(id) on delete cascade,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  account_label text, account_hash text,
  period_end date,
  statement_balance numeric(16,2), book_balance numeric(16,2),
  outstanding_checks numeric(16,2), deposits_in_transit numeric(16,2), other_adjustments numeric(16,2),
  reconciled_on date,
  prepared_by text, approved_by text,
  source_row integer
);
create index if not exists recs_ws on finance.bank_recs (workspace_id, account_hash, period_end);

-- Prior audit findings (rule 16). Seeded below from data/debt_audit/debt_audit.json.
create table if not exists finance.audit_findings (
  id bigint generated always as identity primary key,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  fiscal_year integer not null,
  finding_id text not null,
  title text not null,
  topic text not null,                           -- reconciliation, adjustments, segregation, budget, other
  repeat boolean not null default false,
  mgmt_response text,
  source_url text,
  unique (workspace_id, fiscal_year, finding_id)
);

-- One row per open or reviewed flag. fingerprint = rule + the facts that make it this flag (vendor, amount, dates),
-- so a re-run updates the same row, and an "explained" flag stays quiet until its amount changes.
create table if not exists finance.flags (
  id bigint generated always as identity primary key,
  workspace_id text not null references finance.workspaces(id) on delete cascade,
  rule text not null,
  fingerprint text not null,
  severity text not null check (severity in ('info', 'review', 'urgent')),
  title text not null,
  detail text,
  amount_at_risk numeric(16,2),
  score numeric(18,2),
  refs jsonb not null default '[]',              -- [{table, id}] rows behind the flag
  facts jsonb not null default '{}',
  status text not null default 'open' check (status in ('open', 'explained', 'follow_up', 'referred', 'cleared')),
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (workspace_id, fingerprint)
);
create index if not exists flags_ws on finance.flags (workspace_id, status, score desc);

create table if not exists finance.flag_notes (
  id bigint generated always as identity primary key,
  flag_id bigint not null references finance.flags(id) on delete cascade,
  author text not null,
  status text,
  note text,
  created_at timestamptz not null default now()
);

create table if not exists finance.activity (
  id bigint generated always as identity primary key,
  workspace_id text references finance.workspaces(id) on delete cascade,
  actor text,
  action text not null,
  detail jsonb,
  at timestamptz not null default now()
);

do $$
declare t text;
begin
  foreach t in array array['workspaces','members','uploads','mappings','budget_lines','disbursements','bank_transactions',
                           'bank_recs','audit_findings','flags','flag_notes','activity'] loop
    execute format('alter table finance.%I enable row level security', t);
  end loop;
end $$;

-- App-ready read policies: a signed-in member reads their own workspace's rows. Inert until the finance schema is
-- exposed in the Supabase API settings; the service role (Vercel functions) bypasses RLS either way.
do $$
declare t text;
begin
  if exists (select 1 from pg_namespace where nspname = 'auth') then
    execute $f$
      create or replace function finance.is_member(ws text) returns boolean
      language sql stable security definer set search_path = finance, pg_temp as
      'select exists (select 1 from finance.members m where m.workspace_id = ws and m.user_id = auth.uid())'
    $f$;
    revoke all on function finance.is_member(text) from public;
    foreach t in array array['uploads','budget_lines','disbursements','bank_transactions','bank_recs','audit_findings','flags'] loop
      execute format('drop policy if exists "members read" on finance.%I', t);
      execute format('create policy "members read" on finance.%I for select to authenticated using (finance.is_member(workspace_id))', t);
    end loop;
    drop policy if exists "members read" on finance.workspaces;
    create policy "members read" on finance.workspaces for select to authenticated using (finance.is_member(id));
    drop policy if exists "own membership" on finance.members;
    create policy "own membership" on finance.members for select to authenticated using (user_id = auth.uid());
  end if;
end $$;

-- Private storage bucket for the original files (kept unchanged for the audit trail and records retention).
do $$
begin
  if exists (select 1 from pg_namespace where nspname = 'storage') then
    insert into storage.buckets (id, name, public, file_size_limit)
    values ('finance-uploads', 'finance-uploads', false, 52428800)
    on conflict (id) do nothing;
  end if;
end $$;

-- Pilot workspace: City of Lynn Haven. Thresholds from the Procurement Policy approved 2025-12-09
-- (https://www.cityoflynnhaven.com/DocumentCenter/View/4551/Procurement-Policy-Approved-12-9-25pdf):
-- $35,000+ needs Commission approval and formal bids; $3,500-$35,000 City Manager approval.
insert into finance.workspaces (id, government_key, name, settings) values
  ('lh', 'lh', 'City of Lynn Haven', '{"bid_threshold": 35000, "manager_threshold": 3500, "threshold_source": "https://www.cityoflynnhaven.com/DocumentCenter/View/4551/Procurement-Policy-Approved-12-9-25pdf"}')
on conflict (id) do nothing;

insert into finance.members (workspace_id, email, role) values ('lh', 'jeremy@fluxlabs.net', 'owner')
on conflict (workspace_id, email) do nothing;

insert into finance.audit_findings (workspace_id, fiscal_year, finding_id, title, topic, repeat, mgmt_response, source_url) values
  ('lh', 2025, '2025-001', 'Reconciliation of Account Balances, Audit Adjustments', 'reconciliation', true,
   'Hired an Assistant Finance Director in spring 2025 and adopted finance policies; auditor noted significant improvement.',
   'https://flauditor.gov/pages/mun_efile%20rpts/2025%20lynn%20haven.pdf'),
  ('lh', 2024, '2024-001', 'Reconciliation of Account Balances and Audit Adjustments', 'reconciliation', true,
   'Substantial progress; downgraded to significant deficiency in FY2025.',
   'https://flauditor.gov/pages/mun_efile%20rpts/2024%20lynn%20haven.pdf'),
  ('lh', 2023, '2023-001', 'Reconciliation of Account Balances and Audit Adjustments', 'reconciliation', true,
   'Repeat of 2022-001; corrective action not taken.',
   'https://flauditor.gov/pages/mun_efile%20rpts/2023%20lynn%20haven.pdf')
on conflict (workspace_id, fiscal_year, finding_id) do nothing;
