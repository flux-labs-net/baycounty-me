-- Connections (/connections): one network of who every local government and agency paid, documented links between
-- payees, and business gifts to the officials who approve the spending. Built by site/page_datasets.py from
-- site/connections.py. Replaces the CRA-only network datasets (cra-network-payees, -links, -gifts), whose page moved
-- to /connections: they are taken out of the dataset list here, and their tables are left in place, no longer synced.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists connections_payees (
  id bigint generated always as identity primary key,
  "entity_id" text,
  "name" text,
  "kind" text,
  "subconsultant_only" boolean,
  "paid_by" jsonb,
  "record_types" jsonb,
  "records" bigint,
  "dollars_in_records" numeric,
  "gave_to_campaigns" boolean,
  "vendor_page" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists connections_payees_gov_idx on connections_payees (government_key);
create index if not exists connections_payees_gov_id_idx on connections_payees (gov_id);
create index if not exists connections_payees_entity_id_idx on connections_payees ("entity_id");

insert into datasets (id, table_name, title, description) values ('connections-payees', 'connections_payees', $t$Connections: payees$t$, $d$Every payee in the payment records of every local government and agency (contracts, change orders, emergency purchases, check registers, tourism agency payments and the CRA ledger) as one entity, with who paid it and whether it gave to a campaign. dollars_in_records adds every record, and an award and the payments on it can both be records, so it is not a deduplicated total. Unnamed grant recipients are grouped.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table connections_payees enable row level security;
drop policy if exists "public read" on connections_payees;
create policy "public read" on connections_payees for select using (true);

drop trigger if exists connections_payees_touch on connections_payees;
create trigger connections_payees_touch before update on connections_payees for each row execute function touch_updated_at();

create table if not exists connections_payments (
  id bigint generated always as identity primary key,
  "record_id" text,
  "payer_id" text,
  "payer" text,
  "payer_kind" text,
  "payer_gov_id" text,
  "entity_id" text,
  "payee" text,
  "record_type" text,
  "amount" numeric,
  "date" text,
  "what" text,
  "cra_status" text,
  "inside_project_total" boolean,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists connections_payments_gov_idx on connections_payments (government_key);
create index if not exists connections_payments_gov_id_idx on connections_payments (gov_id);
create index if not exists connections_payments_entity_id_idx on connections_payments ("entity_id");

insert into datasets (id, table_name, title, description) values ('connections-payments', 'connections_payments', $t$Connections: payment records$t$, $d$One row per payment record behind the Connections network: which government or agency paid which payee, the record type, amount, date and source. CRA ledger items that are only proposed or planned are not included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table connections_payments enable row level security;
drop policy if exists "public read" on connections_payments;
create policy "public read" on connections_payments for select using (true);

drop trigger if exists connections_payments_touch on connections_payments;
create trigger connections_payments_touch before update on connections_payments for each row execute function touch_updated_at();

create table if not exists connections_links (
  id bigint generated always as identity primary key,
  "entity_a" text,
  "name_a" text,
  "entity_b" text,
  "name_b" text,
  "connection" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists connections_links_gov_idx on connections_links (government_key);
create index if not exists connections_links_gov_id_idx on connections_links (gov_id);

insert into datasets (id, table_name, title, description) values ('connections-links', 'connections_links', $t$Connections: documented links$t$, $d$Documented links between payees that are not payments (shared project, address or subcontract), each with its source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table connections_links enable row level security;
drop policy if exists "public read" on connections_links;
create policy "public read" on connections_links for select using (true);

drop trigger if exists connections_links_touch on connections_links;
create trigger connections_links_touch before update on connections_links for each row execute function touch_updated_at();

create table if not exists connections_gifts (
  id bigint generated always as identity primary key,
  "donor" text,
  "donor_type" text,
  "official" text,
  "office" text,
  "official_gov_id" text,
  "candidate_2026" boolean,
  "sits_on" jsonb,
  "amount" numeric,
  "gifts" bigint,
  "dates" text,
  "payee_entity_id" text,
  "match_confidence" text,
  "report_url" text,
  "as_of" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists connections_gifts_gov_idx on connections_gifts (government_key);
create index if not exists connections_gifts_gov_id_idx on connections_gifts (gov_id);
create index if not exists connections_gifts_payee_entity_idx on connections_gifts ("payee_entity_id");

insert into datasets (id, table_name, title, description) values ('connections-gifts', 'connections_gifts', $t$Connections: business gifts to officials$t$, $d$Gifts from businesses, PACs and committees to current officeholders and 2026 candidates, one row per donor and official, with the payee id when the donor was also paid by a local government. Individual donors are never included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table connections_gifts enable row level security;
drop policy if exists "public read" on connections_gifts;
create policy "public read" on connections_gifts for select using (true);

drop trigger if exists connections_gifts_touch on connections_gifts;
create trigger connections_gifts_touch before update on connections_gifts for each row execute function touch_updated_at();

-- the CRA-only network datasets are superseded by the connections datasets above
delete from datasets where id in ('cra-network-payees', 'cra-network-links', 'cra-network-gifts');
