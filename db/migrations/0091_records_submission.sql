-- Records submission, Phase 1 (Jeremy, 2026-10-30: "Go", for the county and every city at once). Each government's
-- staff send the files their own systems already make (a check register, a budget-vs-actual report, a list of
-- contracts) from the "Send records" tab of the government workspace (/staff), or by emailing them to their
-- government's intake address. We read the file, staff check a preview, and it is published with the usual privacy
-- rules. Plan: https://claude.ai/artifact/UNm1HqnaEx5gwbTp3V5Xg2
--
-- Check registers and budget reports go through the existing finance importer (finance.uploads, migration 0015)
-- and publish to checkbook_payments and budget_actuals (0047). Contract lists are kept in gov.submissions and publish
-- to the contracts table with origin 'gov' (the site sync never touches them). Nothing is edited after it is
-- published: a corrected file replaces the old one, and both stay on record.
-- Idempotent.

-- 1. A "records" role: can send records and see the workspace, but can't post notices or send alerts.
alter table gov.members drop constraint if exists members_role_check;
alter table gov.members add constraint members_role_check
  check (role in ('owner', 'alert_sender', 'publisher', 'records', 'viewer', 'auditor'));

alter table gov.workspaces alter column modules set default '{alerts,notices,events,jobs,data,records}';
update gov.workspaces set modules = array_append(modules, 'records') where not ('records' = any(modules));

-- 2. A finance workspace for every government workspace, same id, so the importer has somewhere to put the files.
insert into finance.workspaces (id, government_key, name, settings)
select w.id, w.id, w.name, coalesce((select settings from finance.workspaces where id = 'lh'), '{}')
from gov.workspaces w
on conflict (id) do nothing;

-- 3. An intake address for every government. Files emailed there by the government's own workspace members (or by
-- an address on the source's allowed list) land in its finance workspace as unreviewed imports, shown under
-- "Send records" for staff to check and publish.
insert into ingest.sources (entity_name, entity_type, erp_system, intake_method, inbound_address) values
  ('Bay County', 'county', 'other', 'email', 'baycounty@ingest.baycounty.me'),
  ('City of Panama City Beach', 'city', 'other', 'email', 'panamacitybeach@ingest.baycounty.me'),
  ('City of Callaway', 'city', 'other', 'email', 'callaway@ingest.baycounty.me'),
  ('City of Parker', 'city', 'other', 'email', 'parker@ingest.baycounty.me'),
  ('City of Mexico Beach', 'city', 'other', 'email', 'mexicobeach@ingest.baycounty.me')
on conflict (inbound_address) do nothing;

update ingest.sources s set finance_workspace_id = m.ws
from (values ('baycounty@ingest.baycounty.me', 'county'), ('panamacitybeach@ingest.baycounty.me', 'pcb'), ('callaway@ingest.baycounty.me', 'cw'),
             ('parker@ingest.baycounty.me', 'parker'), ('mexicobeach@ingest.baycounty.me', 'mb'), ('panamacity@ingest.baycounty.me', 'pc'),
             ('springfield@ingest.baycounty.me', 'sp'), ('lynnhaven@ingest.baycounty.me', 'lh')) m(addr, ws)
where s.inbound_address = m.addr and s.finance_workspace_id is null;

-- Mail from the government's own published email domain is accepted too (only where no allowed list was set in
-- /admin). Accepting a file never publishes it: it waits until someone signed in checks it and presses Publish.
-- Domains are the ones in the clerks' published addresses (data/civic/scripts/records_requests.py). Panama City Beach
-- and Springfield publish none, so only their workspace members can email files in until /admin adds one.
update ingest.sources s set allowed_senders = array[m.dom]
from (values ('baycounty@ingest.baycounty.me', '@baycountyfl.gov'), ('panamacity@ingest.baycounty.me', '@panamacity.gov'),
             ('lynnhaven@ingest.baycounty.me', '@cityoflynnhaven.com'), ('callaway@ingest.baycounty.me', '@cityofcallaway.com'),
             ('parker@ingest.baycounty.me', '@cityofparker.com'), ('mexicobeach@ingest.baycounty.me', '@mexicobeachfl.gov')) m(addr, dom)
where s.inbound_address = m.addr and coalesce(cardinality(s.allowed_senders), 0) = 0;

-- The ingest-email edge function asks this before accepting a file from a sender who isn't on the source's allowed
-- list: anyone in that government's workspace who may send records counts.
create or replace function public.ingest_sender_is_staff(p_source_id uuid, p_sender text)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from ingest.sources s join gov.members m on m.workspace_id = s.finance_workspace_id
    where s.id = p_source_id and lower(m.email) = lower(p_sender) and m.role in ('owner', 'alert_sender', 'publisher', 'records'));
$$;
revoke all on function public.ingest_sender_is_staff(uuid, text) from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function public.ingest_sender_is_staff(uuid, text) to service_role;
  end if;
end $$;

-- 4. Contract lists sent by staff. rows holds each contract as it will be published (vendor names of private
-- individuals already withheld), so the preview staff confirm is exactly what goes public.
create table if not exists gov.submissions (
  id bigint generated always as identity primary key,
  workspace_id text not null references gov.workspaces(id) on delete cascade,
  kind text not null check (kind in ('contracts')),
  original_name text not null,
  storage_path text,
  sha256 text not null,
  bytes bigint,
  submitted_by text not null,
  submitted_at timestamptz not null default now(),
  status text not null default 'preview' check (status in ('preview', 'published', 'withdrawn')),
  row_count integer not null default 0,
  skipped integer not null default 0,
  rows jsonb not null default '[]',
  period_start date,
  period_end date,
  published_at timestamptz,
  published_by text,
  withdrawn_at timestamptz,
  withdrawn_by text
);
create index if not exists gov_submissions_ws on gov.submissions (workspace_id, submitted_at desc);
alter table gov.submissions enable row level security;
