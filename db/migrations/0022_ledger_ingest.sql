-- Accounting-system ingestion: city and county ERP exports (Tyler New World, BS&A, Springbrook) arrive by email
-- (per-city addresses @ingest.baycounty.me, handled by the ingest-email edge function), and later SFTP or an
-- authenticated push. Files land in ingest.raw, the ingest-normalize edge function maps them into ingest.staging,
-- and an admin approves or rejects rows in /admin (Ingestion tab). Only approved rows reach public.ledger_transactions.
--
-- The ingest schema is private: RLS is on with no policies and anon/authenticated have no grants, so only the
-- service role and DATABASE_URL can touch it. The ledger is public read-only.
--
-- These objects were first created directly in Supabase (migrations create_ingestion_pipeline,
-- ingest_email_rpc_and_bucket, normalizer_support on 2026-10-23). Everything here is idempotent so the production
-- sync can apply this file over them without changing existing rows.
create schema if not exists ingest;
revoke all on schema ingest from anon, authenticated;

-- One row per government feeding data, and how it sends it.
create table if not exists ingest.sources (
  id uuid primary key default gen_random_uuid(),
  entity_name text not null,
  entity_type text not null check (entity_type in ('city','county','cra')),
  erp_system text not null check (erp_system in ('new_world','bsa','springbrook','other')),
  intake_method text not null check (intake_method in ('sftp','email','api','manual')),
  contact_email text,
  inbound_address text unique,               -- e.g. springfield@ingest.baycounty.me; the To address picks the source
  allowed_senders text[] not null default '{}', -- exact addresses, or '@domain' for a whole domain
  sftp_folder text unique,
  api_key_hash text,
  column_map jsonb,                          -- this source's export columns -> standard fields
  active boolean not null default true,
  created_at timestamptz not null default now()
);
alter table ingest.sources add column if not exists auto_normalize boolean not null default false;

-- Every file or payload exactly as received.
create table if not exists ingest.raw (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references ingest.sources(id),
  received_at timestamptz not null default now(),
  intake_method text,
  sender text,
  file_name text,
  file_hash text not null,
  storage_path text,                         -- Supabase Storage path in the private "ingest-raw" bucket
  payload jsonb,
  row_count int,
  status text not null default 'received' check (status in ('received','normalized','failed','duplicate')),
  error_message text,
  unique (source_id, file_hash)
);

-- Normalized rows waiting for review.
create table if not exists ingest.staging (
  id uuid primary key default gen_random_uuid(),
  raw_id uuid not null references ingest.raw(id) on delete cascade,
  source_id uuid not null references ingest.sources(id),
  txn_date date,
  fiscal_year int,                           -- Florida local fiscal year (Oct 1 - Sep 30), named for the ending year
  fund_code text,
  fund_name text,
  account_code text,
  account_name text,
  vendor_name text,
  amount numeric(14,2) not null,
  description text,
  cra_district text,
  check_number text,
  source_row jsonb not null,
  row_hash text not null,
  review_status text not null default 'pending' check (review_status in ('pending','approved','rejected')),
  reviewed_by uuid,
  reviewed_at timestamptz,
  review_note text,
  created_at timestamptz not null default now(),
  unique (source_id, row_hash)
);
alter table ingest.staging add column if not exists reviewed_by_email text;
create index if not exists staging_review_idx on ingest.staging (review_status, source_id);
create index if not exists staging_raw_idx on ingest.staging (raw_id);

-- The public ledger: approved rows only.
create table if not exists public.ledger_transactions (
  id uuid primary key default gen_random_uuid(),
  staging_id uuid not null unique references ingest.staging(id),
  source_id uuid not null references ingest.sources(id),
  entity_name text not null,
  txn_date date,
  fiscal_year int,
  fund_code text,
  account_code text,
  account_name text,
  vendor_name text,
  amount numeric(14,2) not null,
  description text,
  cra_district text,
  approved_by uuid,
  approved_at timestamptz not null default now(),
  published_at timestamptz not null default now()
);
alter table public.ledger_transactions enable row level security;
drop policy if exists "public read ledger" on public.ledger_transactions;
create policy "public read ledger" on public.ledger_transactions for select to anon, authenticated using (true);

alter table ingest.sources enable row level security;
alter table ingest.raw enable row level security;
alter table ingest.staging enable row level security;

-- Review: approve copies rows into the ledger; reject only marks them. Only pending rows change.
-- The admin is identified by the email they signed in to /admin with.
create or replace function ingest.review_staging(p_ids uuid[], p_decision text, p_email text, p_note text default null)
returns int language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  if p_decision not in ('approved', 'rejected') then raise exception 'decision must be approved or rejected'; end if;
  update ingest.staging set review_status = p_decision, reviewed_by_email = p_email, reviewed_at = now(), review_note = p_note
  where id = any(p_ids) and review_status = 'pending';
  get diagnostics n = row_count;
  if p_decision = 'approved' then
    insert into public.ledger_transactions (staging_id, source_id, entity_name, txn_date, fiscal_year, fund_code, account_code,
      account_name, vendor_name, amount, description, cra_district, approved_at)
    select s.id, s.source_id, src.entity_name, s.txn_date, s.fiscal_year, s.fund_code, s.account_code, s.account_name,
      s.vendor_name, s.amount, s.description, s.cra_district, now()
    from ingest.staging s join ingest.sources src on src.id = s.source_id
    where s.id = any(p_ids) and s.review_status = 'approved'
    on conflict (staging_id) do nothing;
  end if;
  return n;
end $$;
revoke all on function ingest.review_staging(uuid[], text, text, text) from public, anon, authenticated;

-- Older review functions from the first Supabase migration (reviewer as a uuid). Kept for compatibility.
create or replace function ingest.approve_staging(p_ids uuid[], p_reviewer uuid, p_note text default null)
returns int language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  update ingest.staging set review_status='approved', reviewed_by=p_reviewer, reviewed_at=now(), review_note=p_note
  where id = any(p_ids) and review_status='pending';
  insert into public.ledger_transactions (staging_id, source_id, entity_name, txn_date, fiscal_year, fund_code, account_code, account_name, vendor_name, amount, description, cra_district, approved_by, approved_at)
  select s.id, s.source_id, src.entity_name, s.txn_date, s.fiscal_year, s.fund_code, s.account_code, s.account_name, s.vendor_name, s.amount, s.description, s.cra_district, p_reviewer, now()
  from ingest.staging s join ingest.sources src on src.id = s.source_id
  where s.id = any(p_ids) and s.review_status='approved'
  on conflict (staging_id) do nothing;
  get diagnostics n = row_count;
  return n;
end $$;
create or replace function ingest.reject_staging(p_ids uuid[], p_reviewer uuid, p_note text)
returns int language plpgsql security definer set search_path = '' as $$
declare n int;
begin
  update ingest.staging set review_status='rejected', reviewed_by=p_reviewer, reviewed_at=now(), review_note=p_note
  where id = any(p_ids) and review_status='pending';
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function ingest.approve_staging(uuid[], uuid, text) from public, anon, authenticated;
revoke all on function ingest.reject_staging(uuid[], uuid, text) from public, anon, authenticated;

-- RPCs used by the edge functions (service role only).
drop function if exists public.ingest_lookup_source(text); -- return columns changed (added auto_normalize)
create function public.ingest_lookup_source(p_to text)
returns table (id uuid, entity_name text, allowed_senders text[], active boolean, auto_normalize boolean)
language sql security definer set search_path = '' as $$
  select s.id, s.entity_name, s.allowed_senders, s.active, s.auto_normalize from ingest.sources s where lower(s.inbound_address) = lower(p_to) limit 1;
$$;

create or replace function public.ingest_register_raw(p_source_id uuid, p_sender text, p_file_name text, p_file_hash text, p_storage_path text, p_payload jsonb, p_status text default 'received', p_error text default null)
returns uuid language plpgsql security definer set search_path = '' as $$
declare v_id uuid;
begin
  insert into ingest.raw (source_id, intake_method, sender, file_name, file_hash, storage_path, payload, status, error_message)
  values (p_source_id, 'email', p_sender, p_file_name, p_file_hash, p_storage_path, p_payload, p_status, p_error)
  on conflict (source_id, file_hash) do nothing
  returning id into v_id;
  return v_id;
end $$;

create or replace function public.ingest_normalize_context(p_raw_id uuid)
returns jsonb language sql security definer set search_path = ingest, public as $$
  select jsonb_build_object(
    'raw_id', r.id, 'source_id', r.source_id, 'status', r.status,
    'storage_path', r.storage_path, 'erp_system', s.erp_system,
    'column_map', s.column_map, 'auto_normalize', s.auto_normalize)
  from ingest.raw r join ingest.sources s on s.id = r.source_id
  where r.id = p_raw_id;
$$;

create or replace function public.ingest_pending_raw(p_limit int default 20)
returns setof uuid language sql security definer set search_path = ingest, public as $$
  select id from ingest.raw where status = 'received' and storage_path is not null
  order by received_at limit p_limit;
$$;

create or replace function public.ingest_stage_rows(p_raw_id uuid, p_rows jsonb)
returns jsonb language plpgsql security definer set search_path = ingest, public as $$
declare v_src uuid; v_ins int; v_total int;
begin
  select source_id into v_src from ingest.raw where id = p_raw_id;
  if v_src is null then raise exception 'raw % not found', p_raw_id; end if;
  v_total := jsonb_array_length(p_rows);
  insert into ingest.staging (raw_id, source_id, txn_date, fiscal_year, fund_code, account_code,
    vendor_name, amount, description, check_number, source_row, row_hash)
  select p_raw_id, v_src, (x->>'txn_date')::date, (x->>'fiscal_year')::int, x->>'fund_code',
    x->>'account_code', x->>'vendor_name', (x->>'amount')::numeric, x->>'description',
    x->>'check_number', x->'source_row', x->>'row_hash'
  from jsonb_array_elements(p_rows) x
  on conflict (source_id, row_hash) do nothing;
  get diagnostics v_ins = row_count;
  update ingest.raw set status = 'normalized', row_count = v_total, error_message = null where id = p_raw_id;
  return jsonb_build_object('total', v_total, 'inserted', v_ins, 'duplicates', v_total - v_ins);
end $$;

create or replace function public.ingest_fail_raw(p_raw_id uuid, p_msg text)
returns void language sql security definer set search_path = ingest, public as $$
  update ingest.raw set status = 'failed', error_message = p_msg where id = p_raw_id;
$$;

revoke all on function public.ingest_lookup_source(text), public.ingest_register_raw(uuid, text, text, text, text, jsonb, text, text),
  public.ingest_normalize_context(uuid), public.ingest_pending_raw(int), public.ingest_stage_rows(uuid, jsonb),
  public.ingest_fail_raw(uuid, text) from public, anon, authenticated;
grant execute on function public.ingest_lookup_source(text), public.ingest_register_raw(uuid, text, text, text, text, jsonb, text, text),
  public.ingest_normalize_context(uuid), public.ingest_pending_raw(int), public.ingest_stage_rows(uuid, jsonb),
  public.ingest_fail_raw(uuid, text) to service_role;

-- Private bucket for the raw files (Supabase only; plain Postgres in CI has no storage schema).
do $$ begin
  if to_regclass('storage.buckets') is not null then
    insert into storage.buckets (id, name, public) values ('ingest-raw', 'ingest-raw', false) on conflict (id) do nothing;
  end if;
end $$;

-- First two sources. Allowed senders are set in /admin, not here.
insert into ingest.sources (entity_name, entity_type, erp_system, intake_method, inbound_address) values
  ('City of Panama City', 'city', 'new_world', 'email', 'panamacity@ingest.baycounty.me'),
  ('City of Springfield', 'city', 'springbrook', 'email', 'springfield@ingest.baycounty.me')
on conflict (inbound_address) do nothing;

-- Springfield's Springbrook check register layout. Only filled in when no map is set yet.
update ingest.sources set column_map = '{
  "txn_date": {"col": "Check Date", "format": "MM/DD/YYYY"},
  "fund_code": "Fund",
  "account_code": "Account",
  "vendor_name": "Vendor",
  "description": "Description",
  "amount": "Amount",
  "check_number": "Check Number"
}'::jsonb where erp_system = 'springbrook' and column_map is null;
