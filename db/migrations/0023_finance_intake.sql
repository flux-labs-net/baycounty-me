-- Link email intake (ingest schema, 0022) to the finance workspaces (0015). Each intake source can name a finance
-- workspace; every file emailed to that source's address is also run through the /finance importer and lands there
-- as an unreviewed import (finance.uploads status 'preview', uploaded_by 'email: <sender>') for staff to check and add.
-- Files the importer reads as budget, bank statement or bank reconciliation reports are marked 'finance_only' in
-- ingest.raw, so they never go through the public-ledger normalizer. Idempotent.

alter table ingest.sources add column if not exists finance_workspace_id text references finance.workspaces(id);

alter table ingest.raw add column if not exists finance_upload_id bigint references finance.uploads(id) on delete set null;
alter table ingest.raw add column if not exists finance_status text;   -- importing | imported | failed | not_linked
alter table ingest.raw add column if not exists finance_shape text;    -- what the importer read it as
alter table ingest.raw add column if not exists finance_error text;
alter table ingest.raw add column if not exists finance_at timestamptz;
alter table ingest.raw drop constraint if exists raw_finance_status_check;
alter table ingest.raw add constraint raw_finance_status_check check (finance_status in ('importing', 'imported', 'failed', 'not_linked'));
alter table ingest.raw drop constraint if exists raw_status_check;
alter table ingest.raw add constraint raw_status_check check (status in ('received', 'normalized', 'failed', 'duplicate', 'finance_only'));
create index if not exists raw_finance_pending on ingest.raw (received_at) where finance_upload_id is null and storage_path is not null;

-- Workspaces for every intake government. Same rule thresholds as Lynn Haven's.
insert into finance.workspaces (id, government_key, name, settings) values
  ('pc', 'pc', 'Panama City', coalesce((select settings from finance.workspaces where id = 'lh'), '{}')),
  ('sp', 'sp', 'Springfield', coalesce((select settings from finance.workspaces where id = 'lh'), '{}'))
on conflict (id) do nothing;
insert into finance.members (workspace_id, email, role) values ('pc', 'jeremy@fluxlabs.net', 'owner'), ('sp', 'jeremy@fluxlabs.net', 'owner')
on conflict (workspace_id, email) do nothing;

-- Lynn Haven intake address (its accounting system isn't confirmed yet).
insert into ingest.sources (entity_name, entity_type, erp_system, intake_method, inbound_address) values
  ('City of Lynn Haven', 'city', 'other', 'email', 'lynnhaven@ingest.baycounty.me')
on conflict (inbound_address) do nothing;

update ingest.sources s set finance_workspace_id = m.ws
from (values ('panamacity@ingest.baycounty.me', 'pc'), ('springfield@ingest.baycounty.me', 'sp'), ('lynnhaven@ingest.baycounty.me', 'lh')) m(addr, ws)
where s.inbound_address = m.addr and s.finance_workspace_id is null;
