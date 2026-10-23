-- Datasets for pages whose data lived only inside the page or the app's /data/app files (CRA network, money map,
-- donor contracts, companies, people, glossary, what's new, tax districts), so every page's data is in the database
-- and the API. Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0001_init.sql).

-- CRA network payee id on each CRA ledger row (joins cra_network_payees.entity_id)
alter table cra_payments add column if not exists payee_entity_id text;
create index if not exists cra_payments_payee_entity_idx on cra_payments (payee_entity_id);

create table if not exists cra_network_payees (
  id bigint generated always as identity primary key,
  "entity_id" text,
  "name" text,
  "kind" text,
  "subconsultant_only" boolean,
  "cras" jsonb,
  "records" bigint,
  "counted_total" numeric,
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
create index if not exists cra_network_payees_gov_idx on cra_network_payees (government_key);
create index if not exists cra_network_payees_gov_id_idx on cra_network_payees (gov_id);
create index if not exists cra_network_payees_entity_id_idx on cra_network_payees ("entity_id");

insert into datasets (id, table_name, title, description) values ('cra-network-payees', 'cra_network_payees', $t$CRA network: payees$t$, $d$Every payee in the CRA ledger as one entity (businesses, governments, property owners; unnamed grant recipients grouped), with the CRAs that paid it and the counted total.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_network_payees enable row level security;
drop policy if exists "public read" on cra_network_payees;
create policy "public read" on cra_network_payees for select using (true);

drop trigger if exists cra_network_payees_touch on cra_network_payees;
create trigger cra_network_payees_touch before update on cra_network_payees for each row execute function touch_updated_at();

create table if not exists cra_network_links (
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
create index if not exists cra_network_links_gov_idx on cra_network_links (government_key);
create index if not exists cra_network_links_gov_id_idx on cra_network_links (gov_id);
create index if not exists cra_network_links_entity_a_idx on cra_network_links ("entity_a");

insert into datasets (id, table_name, title, description) values ('cra-network-links', 'cra_network_links', $t$CRA network: documented connections$t$, $d$Documented links between CRA payees that are not payments (shared project, address or subcontract), each with its source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_network_links enable row level security;
drop policy if exists "public read" on cra_network_links;
create policy "public read" on cra_network_links for select using (true);

drop trigger if exists cra_network_links_touch on cra_network_links;
create trigger cra_network_links_touch before update on cra_network_links for each row execute function touch_updated_at();

create table if not exists cra_network_gifts (
  id bigint generated always as identity primary key,
  "donor" text,
  "donor_type" text,
  "official" text,
  "office" text,
  "cra_board" text,
  "amount" numeric,
  "gifts" bigint,
  "dates" text,
  "payee_entity_id" text,
  "match_confidence" text,
  "report_url" text,
  "as_of" date,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists cra_network_gifts_gov_idx on cra_network_gifts (government_key);
create index if not exists cra_network_gifts_gov_id_idx on cra_network_gifts (gov_id);
create index if not exists cra_network_gifts_payee_entity_id_idx on cra_network_gifts ("payee_entity_id");

insert into datasets (id, table_name, title, description) values ('cra-network-gifts', 'cra_network_gifts', $t$CRA network: campaign gifts$t$, $d$Business and committee campaign gifts to the officials who sit as each CRA's board, and gifts from donors who are CRA payees. Individual donors are not included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table cra_network_gifts enable row level security;
drop policy if exists "public read" on cra_network_gifts;
create policy "public read" on cra_network_gifts for select using (true);

drop trigger if exists cra_network_gifts_touch on cra_network_gifts;
create trigger cra_network_gifts_touch before update on cra_network_gifts for each row execute function touch_updated_at();

create table if not exists money_map_gifts (
  id bigint generated always as identity primary key,
  "donor" text,
  "donor_type" text,
  "official" text,
  "office" text,
  "gov" text,
  "amount" numeric,
  "dates" jsonb,
  "donor_holds_contracts_here" boolean,
  "official_total_raised" numeric,
  "official_from_individuals" numeric,
  "official_individual_gifts" bigint,
  "report_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists money_map_gifts_gov_idx on money_map_gifts (government_key);
create index if not exists money_map_gifts_gov_id_idx on money_map_gifts (gov_id);
create index if not exists money_map_gifts_official_idx on money_map_gifts ("official");

insert into datasets (id, table_name, title, description) values ('money-map-gifts', 'money_map_gifts', $t$Money map: gifts to officials$t$, $d$Gifts from businesses and committees to each current officeholder, and whether the donor holds contracts with that official's government. Individuals appear only as totals.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table money_map_gifts enable row level security;
drop policy if exists "public read" on money_map_gifts;
create policy "public read" on money_map_gifts for select using (true);

drop trigger if exists money_map_gifts_touch on money_map_gifts;
create trigger money_map_gifts_touch before update on money_map_gifts for each row execute function touch_updated_at();

create table if not exists money_map_contracts (
  id bigint generated always as identity primary key,
  "donor" text,
  "donor_type" text,
  "gov" text,
  "government" text,
  "awarded_total" numeric,
  "paid_total" numeric,
  "awards" bigint,
  "other_records" bigint,
  "records" jsonb,
  "source_urls" jsonb,
  "likely_match_only" boolean,
  "vendor" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists money_map_contracts_gov_idx on money_map_contracts (government_key);
create index if not exists money_map_contracts_gov_id_idx on money_map_contracts (gov_id);
create index if not exists money_map_contracts_donor_idx on money_map_contracts ("donor");

insert into datasets (id, table_name, title, description) values ('money-map-contracts', 'money_map_contracts', $t$Money map: donor contracts$t$, $d$Contracts, awards and payments held by campaign donors, per donor and government.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table money_map_contracts enable row level security;
drop policy if exists "public read" on money_map_contracts;
create policy "public read" on money_map_contracts for select using (true);

drop trigger if exists money_map_contracts_touch on money_map_contracts;
create trigger money_map_contracts_touch before update on money_map_contracts for each row execute function touch_updated_at();

create table if not exists money_map_votes (
  id bigint generated always as identity primary key,
  "donor" text,
  "official" text,
  "office" text,
  "gov" text,
  "gift_amount" numeric,
  "gift_dates" jsonb,
  "vote_date" date,
  "item" text,
  "amount" numeric,
  "vote" text,
  "outcome" text,
  "tally" text,
  "consent_agenda" boolean,
  "gift_before_or_after_vote" text,
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
create index if not exists money_map_votes_gov_idx on money_map_votes (government_key);
create index if not exists money_map_votes_gov_id_idx on money_map_votes (gov_id);
create index if not exists money_map_votes_official_idx on money_map_votes ("official");

insert into datasets (id, table_name, title, description) values ('money-map-votes', 'money_map_votes', $t$Money map: votes on donors' contracts$t$, $d$Recorded votes by an official on a contract with one of their own donors, and whether the gift came before or after.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table money_map_votes enable row level security;
drop policy if exists "public read" on money_map_votes;
create policy "public read" on money_map_votes for select using (true);

drop trigger if exists money_map_votes_touch on money_map_votes;
create trigger money_map_votes_touch before update on money_map_votes for each row execute function touch_updated_at();

create table if not exists donor_contracts (
  id bigint generated always as identity primary key,
  "contributor" text,
  "vendor" text,
  "vendor_id" text,
  "candidate" text,
  "person_id" text,
  "office" text,
  "office_gov_id" text,
  "election" text,
  "contribution_amount" numeric,
  "contribution_dates" jsonb,
  "contract_ids_or_descriptions" jsonb,
  "record_ids" jsonb,
  "contract_source_urls" jsonb,
  "contract_government" text,
  "contract_gov_id" text,
  "record_types" jsonb,
  "match_confidence" text,
  "note" text,
  "campaign_report_url" text,
  "same_government_as_office" boolean,
  "refunded_by_campaign" numeric,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists donor_contracts_gov_idx on donor_contracts (government_key);
create index if not exists donor_contracts_gov_id_idx on donor_contracts (gov_id);
create index if not exists donor_contracts_vendor_id_idx on donor_contracts ("vendor_id");

insert into datasets (id, table_name, title, description) values ('donor-contracts', 'donor_contracts', $t$Donors with government contracts$t$, $d$Each business donor matched to a local government contract, award or payment, with the match method and confidence.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table donor_contracts enable row level security;
drop policy if exists "public read" on donor_contracts;
create policy "public read" on donor_contracts for select using (true);

drop trigger if exists donor_contracts_touch on donor_contracts;
create trigger donor_contracts_touch before update on donor_contracts for each row execute function touch_updated_at();

create table if not exists vendors_directory (
  id bigint generated always as identity primary key,
  "vendor_id" text,
  "name" text,
  "aliases" jsonb,
  "gov_ids" jsonb,
  "records" jsonb,
  "vendor_type" text,
  "page" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists vendors_directory_gov_idx on vendors_directory (government_key);
create index if not exists vendors_directory_gov_id_idx on vendors_directory (gov_id);
create index if not exists vendors_directory_vendor_id_idx on vendors_directory ("vendor_id");

insert into datasets (id, table_name, title, description) values ('vendors-directory', 'vendors_directory', $t$Companies$t$, $d$Every company in BayCounty.me records, with its other spellings, the governments it works with and how many records name it.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table vendors_directory enable row level security;
drop policy if exists "public read" on vendors_directory;
create policy "public read" on vendors_directory for select using (true);

drop trigger if exists vendors_directory_touch on vendors_directory;
create trigger vendors_directory_touch before update on vendors_directory for each row execute function touch_updated_at();

create table if not exists people_directory (
  id bigint generated always as identity primary key,
  "person_id" text,
  "name" text,
  "district" text,
  "gov_ids" jsonb,
  "roles" jsonb,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists people_directory_gov_idx on people_directory (government_key);
create index if not exists people_directory_gov_id_idx on people_directory (gov_id);
create index if not exists people_directory_person_id_idx on people_directory ("person_id");

insert into datasets (id, table_name, title, description) values ('people-directory', 'people_directory', $t$People$t$, $d$Elected officials, department leaders and 2026 candidates named in BayCounty.me records, with their roles.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table people_directory enable row level security;
drop policy if exists "public read" on people_directory;
create policy "public read" on people_directory for select using (true);

drop trigger if exists people_directory_touch on people_directory;
create trigger people_directory_touch before update on people_directory for each row execute function touch_updated_at();

create table if not exists glossary_terms (
  id bigint generated always as identity primary key,
  "term_id" text,
  "group_id" text,
  "group_name" text,
  "term" text,
  "simple" text,
  "more" text,
  "example" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists glossary_terms_gov_idx on glossary_terms (government_key);
create index if not exists glossary_terms_gov_id_idx on glossary_terms (gov_id);
create index if not exists glossary_terms_term_id_idx on glossary_terms ("term_id");

insert into datasets (id, table_name, title, description) values ('glossary-terms', 'glossary_terms', $t$Glossary$t$, $d$Plain-English definitions of the government and tax terms used on the site.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table glossary_terms enable row level security;
drop policy if exists "public read" on glossary_terms;
create policy "public read" on glossary_terms for select using (true);

drop trigger if exists glossary_terms_touch on glossary_terms;
create trigger glossary_terms_touch before update on glossary_terms for each row execute function touch_updated_at();

create table if not exists site_updates (
  id bigint generated always as identity primary key,
  "date" date,
  "title" text,
  "text" text,
  "pages" jsonb,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists site_updates_gov_idx on site_updates (government_key);
create index if not exists site_updates_gov_id_idx on site_updates (gov_id);
create index if not exists site_updates_date_idx on site_updates ("date");

insert into datasets (id, table_name, title, description) values ('site-updates', 'site_updates', $t$What's new$t$, $d$Each change to the site's data and pages, newest first.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table site_updates enable row level security;
drop policy if exists "public read" on site_updates;
create policy "public read" on site_updates for select using (true);

drop trigger if exists site_updates_touch on site_updates;
create trigger site_updates_touch before update on site_updates for each row execute function touch_updated_at();

create table if not exists tax_districts (
  id bigint generated always as identity primary key,
  "district" text,
  "label" text,
  "authority_ids" jsonb,
  "total_millage" numeric,
  "tax_district_codes" jsonb,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists tax_districts_gov_idx on tax_districts (government_key);
create index if not exists tax_districts_gov_id_idx on tax_districts (gov_id);
create index if not exists tax_districts_district_idx on tax_districts ("district");

insert into datasets (id, table_name, title, description) values ('tax-districts', 'tax_districts', $t$Tax districts$t$, $d$Which taxing authorities levy property tax in each tax district, and the combined millage. Rates by year are in property-tax-rates (authority_id).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table tax_districts enable row level security;
drop policy if exists "public read" on tax_districts;
create policy "public read" on tax_districts for select using (true);

drop trigger if exists tax_districts_touch on tax_districts;
create trigger tax_districts_touch before update on tax_districts for each row execute function touch_updated_at();
