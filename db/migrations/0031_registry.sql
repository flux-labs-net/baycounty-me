-- Business registry links (data/sunbiz): which people run which registered businesses, and which of those businesses
-- gave to local campaigns.
--
-- Public: business_donor_sunbiz, a normal dataset table (business-level only; no officer, owner or agent names).
-- Private: schema `registry`, loaded by db/scripts/load_registry.py from the Sunbiz county filter output. It holds
-- officer and registered-agent names, so RLS is on with no public policy and anon/authenticated have no access;
-- only the service role / DATABASE_URL (the admin API) can read it. Street addresses are not stored, only city, ZIP
-- and a hash of the address used to group a person. Everything is keyed by county so other counties can be added.

-- ---------- public dataset ----------
create table if not exists business_donor_sunbiz (
  id bigint generated always as identity primary key,
  "contributor" text,
  "candidate" text,
  "office" text,
  "election" text,
  "contribution_amount" numeric,
  "contribution_items" bigint,
  "first_date" text,
  "last_date" text,
  "sunbiz_doc_number" text,
  "sunbiz_entity_name" text,
  "sunbiz_status" text,
  "sunbiz_filing_type" text,
  "sunbiz_principal_city" text,
  "match_method" text,
  "county" text,
  "source_url" text,
  "campaign_report_url" text,
  "vendor_id" text,
  "vendor_ids" jsonb,
  "person_id" text,
  "district" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists business_donor_sunbiz_gov_idx on business_donor_sunbiz (government_key);
create index if not exists business_donor_sunbiz_gov_id_idx on business_donor_sunbiz (gov_id);
create index if not exists business_donor_sunbiz_doc_idx on business_donor_sunbiz ("sunbiz_doc_number");

insert into datasets (id, table_name, title, description) values ('business-donor-sunbiz', 'business_donor_sunbiz', $t$Business donors in the state corporate registry$t$, $d$Each business that gave to a current officeholder or 2026 local candidate, matched to its Florida Division of Corporations (Sunbiz) record: document number, registered name, status and principal city, with the match method. Business-level only; no owner or officer names.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table business_donor_sunbiz enable row level security;
drop policy if exists "public read" on business_donor_sunbiz;
create policy "public read" on business_donor_sunbiz for select using (true);

drop trigger if exists business_donor_sunbiz_touch on business_donor_sunbiz;
create trigger business_donor_sunbiz_touch before update on business_donor_sunbiz for each row execute function touch_updated_at();

-- ---------- private registry ----------
create schema if not exists registry;
revoke all on schema registry from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema registry from anon, authenticated'; end if;
end $$;

-- One row per registered entity in a county's filter output (Sunbiz quarterly corporate file).
create table if not exists registry.entities (
  county text not null,                       -- data/sunbiz/counties.py key ('bay')
  doc_number text not null,
  name text not null,
  name_key text,                              -- name for matching (no punctuation or legal suffix)
  status text,                                -- A active, I inactive
  filing_type text,                           -- FLAL (FL LLC), DOMP (FL corp), DOMNP (nonprofit) ...
  nonprofit boolean not null default false,
  file_date date,
  last_report_year int,
  principal_city text,
  principal_zip text,
  principal_in_county boolean,
  loaded_at timestamptz not null default now(),
  primary key (county, doc_number)
);
create index if not exists registry_entities_key on registry.entities (name_key);

-- One row per person (officers/managers and registered agents grouped by name + address).
create table if not exists registry.people (
  county text not null,
  person_key text not null,                   -- stable hash of the grouping key
  display_name text not null,                 -- as Sunbiz lists it
  name_key text not null,                     -- LAST FIRST
  city text,
  zip5 text,
  resident boolean not null,                  -- any address for this person is in the county
  address_hash text,                          -- hash of the normalized address; the address itself is not stored
  entities_as_officer int not null default 0,
  active_entities_as_officer int not null default 0,
  entities_as_agent int not null default 0,
  corporate_officer boolean not null default false,   -- on 25+ active entities (subsidiary boards), left out of findings
  agent_service boolean not null default false,       -- registered agent for 20+ entities it doesn't run; never links businesses
  loaded_at timestamptz not null default now(),
  primary key (county, person_key)
);
create index if not exists registry_people_name on registry.people (name_key);

-- Person <-> entity roles.
create table if not exists registry.roles (
  id bigint generated always as identity primary key,
  county text not null,
  person_key text not null,
  doc_number text not null,
  role text not null,                         -- officer, registered_agent
  title text,                                 -- MGR, P, VP, RA ...
  foreign key (county, person_key) references registry.people (county, person_key) on delete cascade,
  foreign key (county, doc_number) references registry.entities (county, doc_number) on delete cascade
);
create index if not exists registry_roles_person on registry.roles (county, person_key);
create index if not exists registry_roles_doc on registry.roles (county, doc_number);

-- Each business campaign gift line and the entity it matched (null when no match).
create table if not exists registry.gift_matches (
  id bigint generated always as identity primary key,
  county text not null,
  gift_source text not null,                  -- officeholders | candidates_2026
  candidate text not null,
  office text,
  government_key text,
  contributor text not null,
  amount numeric,
  gift_date date,
  doc_number text,
  match_method text,
  report_url text
);
create index if not exists registry_gift_doc on registry.gift_matches (county, doc_number);
create index if not exists registry_gift_cand on registry.gift_matches (candidate);

-- Findings: per candidate, 2+ businesses that gave and share a person.
create table if not exists registry.shared_owner_groups (
  county text not null,
  group_id text not null,                     -- opaque, stable hash of the businesses
  candidate text not null,
  office text,
  government_key text,
  election text,
  n_businesses int not null,
  n_checks int not null,
  n_people int not null,
  combined_amount numeric not null,
  all_at_1000 boolean not null,
  same_day boolean not null,
  businesses jsonb not null,                  -- [{doc_number, entity_name, status, filed_as, amount, dates, people}]
  person_keys jsonb not null,
  report_url text,
  review_status text not null default 'unreviewed',   -- unreviewed, confirmed, rejected (admin review before anything is published)
  loaded_at timestamptz not null default now(),
  primary key (county, group_id, candidate)
);

-- Load log.
create table if not exists registry.loads (
  id bigint generated always as identity primary key,
  county text not null,
  loaded_at timestamptz not null default now(),
  git_sha text,
  entities int, people int, roles int, gifts int, groups int,
  summary jsonb
);

do $$ declare t text; begin
  foreach t in array array['entities', 'people', 'roles', 'gift_matches', 'shared_owner_groups', 'loads'] loop
    execute format('alter table registry.%I enable row level security', t);
  end loop;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema registry from anon, authenticated';
  end if;
end $$;
