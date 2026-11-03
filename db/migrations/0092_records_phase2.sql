-- Records submission, Phase 2 (Jeremy, 2026-10-30: "build it out and get everything linked and connected").
--  1. Workspaces for the School Board and the five constitutional officers, so they can send records too.
--  2. More kinds of record in gov.submissions: payroll by job title, board appointments and fee or rate changes.
--  3. Two new public datasets those publish to (board-appointments, fee-changes); payroll goes to salary-positions.
--  4. Feed agreements: a government says yes to a source we already read for it automatically.
-- Same standard columns, public read policy and updated_at trigger as every dataset table (see 0021_page_datasets.sql).
-- Idempotent.

-- 1. School Board and constitutional officers. No alerts module: their alerts go through the county for now.
insert into gov.workspaces (id, name, countywide, modules) values
  ('schools', 'Bay District Schools', false, '{notices,events,jobs,data,records}'),
  ('sheriff', 'Bay County Sheriff''s Office', false, '{notices,events,jobs,data,records}'),
  ('clerk', 'Bay County Clerk of Court and Comptroller', false, '{notices,events,jobs,data,records}'),
  ('property_appraiser', 'Bay County Property Appraiser', false, '{notices,events,jobs,data,records}'),
  ('tax_collector', 'Bay County Tax Collector', false, '{notices,events,jobs,data,records}'),
  ('soe', 'Bay County Supervisor of Elections', false, '{notices,events,jobs,data,records}')
on conflict (id) do nothing;

insert into finance.workspaces (id, government_key, name, settings)
select w.id, w.id, w.name, coalesce((select settings from finance.workspaces where id = 'lh'), '{}')
from gov.workspaces w
on conflict (id) do nothing;

alter table ingest.sources drop constraint if exists sources_entity_type_check;
alter table ingest.sources add constraint sources_entity_type_check
  check (entity_type in ('city', 'county', 'cra', 'school_district', 'constitutional_officer'));

insert into ingest.sources (entity_name, entity_type, erp_system, intake_method, inbound_address) values
  ('Bay District Schools', 'school_district', 'other', 'email', 'schools@ingest.baycounty.me'),
  ('Bay County Sheriff''s Office', 'constitutional_officer', 'other', 'email', 'sheriff@ingest.baycounty.me'),
  ('Bay County Clerk of Court and Comptroller', 'constitutional_officer', 'other', 'email', 'clerk@ingest.baycounty.me'),
  ('Bay County Property Appraiser', 'constitutional_officer', 'other', 'email', 'propertyappraiser@ingest.baycounty.me'),
  ('Bay County Tax Collector', 'constitutional_officer', 'other', 'email', 'taxcollector@ingest.baycounty.me'),
  ('Bay County Supervisor of Elections', 'constitutional_officer', 'other', 'email', 'elections@ingest.baycounty.me')
on conflict (inbound_address) do nothing;

update ingest.sources s set finance_workspace_id = m.ws
from (values ('schools@ingest.baycounty.me', 'schools'), ('sheriff@ingest.baycounty.me', 'sheriff'), ('clerk@ingest.baycounty.me', 'clerk'),
             ('propertyappraiser@ingest.baycounty.me', 'property_appraiser'), ('taxcollector@ingest.baycounty.me', 'tax_collector'),
             ('elections@ingest.baycounty.me', 'soe')) m(addr, ws)
where s.inbound_address = m.addr and s.finance_workspace_id is null;

-- The district's own email domain, used only to tell a district employee who may send (migration 0093).

update ingest.sources set gov_domain = 'bay.k12.fl.us'
where inbound_address = 'schools@ingest.baycounty.me' and gov_domain is null;

-- 2. More kinds of record.
alter table gov.submissions drop constraint if exists submissions_kind_check;
alter table gov.submissions add constraint submissions_kind_check check (kind in ('contracts', 'payroll', 'appointments', 'fees'));

-- 3a. Board appointments: who sits on each advisory board or authority a government appoints (sent by the government).
create table if not exists board_appointments (
  id bigint generated always as identity primary key,
  "government" text,
  "board" text,
  "seat" text,
  "person" text,
  "appointed_by" text,
  "term_start" date,
  "term_end" date,
  "notes" text,
  "source_url" text,
  "source_title" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'gov',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists board_appointments_gov_idx on board_appointments (government_key);
create index if not exists board_appointments_gov_id_idx on board_appointments (gov_id, board);

insert into datasets (id, table_name, title, description) values ('board-appointments', 'board_appointments', $t$Board appointments$t$, $d$Who sits on each advisory board, committee and authority a Bay County government appoints, with the seat, who appointed them and the term, as sent by the government.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table board_appointments enable row level security;
drop policy if exists "public read" on board_appointments;
create policy "public read" on board_appointments for select using (true);
drop trigger if exists board_appointments_touch on board_appointments;
create trigger board_appointments_touch before update on board_appointments for each row execute function touch_updated_at();

-- 3b. Fee and rate changes a government adopts (sent by the government).
create table if not exists fee_changes (
  id bigint generated always as identity primary key,
  "government" text,
  "fee" text,
  "category" text,
  "old_amount" numeric,
  "new_amount" numeric,
  "unit" text,
  "effective_date" date,
  "adopted_by" text,
  "source_url" text,
  "source_title" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'gov',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists fee_changes_gov_idx on fee_changes (government_key);
create index if not exists fee_changes_gov_id_idx on fee_changes (gov_id, effective_date);

insert into datasets (id, table_name, title, description) values ('fee-changes', 'fee_changes', $t$Fee and rate changes$t$, $d$New and changed fees and utility rates adopted by each Bay County government: the old and new amount, the unit, when it takes effect and the ordinance or resolution, as sent by the government.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table fee_changes enable row level security;
drop policy if exists "public read" on fee_changes;
create policy "public read" on fee_changes for select using (true);
drop trigger if exists fee_changes_touch on fee_changes;
create trigger fee_changes_touch before update on fee_changes for each row execute function touch_updated_at();

-- 4. Feed agreements: the sources in data_sources we read automatically for a government, and which it said yes to.
create table if not exists gov.feed_agreements (
  workspace_id text not null references gov.workspaces(id) on delete cascade,
  source_url text not null,
  agreed_by text not null,
  agreed_at timestamptz not null default now(),
  primary key (workspace_id, source_url)
);
alter table gov.feed_agreements enable row level security;
