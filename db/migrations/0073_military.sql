-- Military and the bases (/military): Tyndall Air Force Base and Naval Support Activity Panama City, news from the units on
-- them (DVIDS feeds, data/military/fetch_news.py) and federal contracts to companies based in the county (USAspending.gov,
-- data/military/fetch_contracts.py), built by site/page_datasets.py. place_id keeps rows for other places apart (fl-bay =
-- Bay County). Same standard columns, public read policy and updated_at trigger as every other dataset table (see
-- 0021_page_datasets.sql).

create table if not exists military_installations (
  id bigint generated always as identity primary key,
  "place_id" text,
  "installation_id" text,
  "name" text,
  "short_name" text,
  "branch" text,
  "host_unit" text,
  "commander" text,
  "commander_title" text,
  "commander_since" text,
  "commander_source_url" text,
  "location" text,
  "opened" bigint,
  "acres" bigint,
  "personnel" bigint,
  "mission" text,
  "storm" text,
  "tenants" text,
  "website" text,
  "dvids_url" text,
  "news_units" text,
  "stories" bigint,
  "latest_story" text,
  "as_of" text,
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
create index if not exists military_installations_gov_idx on military_installations (government_key);
create index if not exists military_installations_place_idx on military_installations (place_id, installation_id);

insert into datasets (id, table_name, title, description) values ('military-installations', 'military_installations', $t$Military installations$t$, $d$One row per military base in the county: branch, host unit, commander (with the change-of-command story that names them), mission, main tenant commands, size and history, its website and DVIDS page, and how many news stories are on file. Hand-checked from the units' own stories and public base histories; commanders change every two to three years.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table military_installations enable row level security;
drop policy if exists "public read" on military_installations;
create policy "public read" on military_installations for select using (true);

drop trigger if exists military_installations_touch on military_installations;
create trigger military_installations_touch before update on military_installations for each row execute function touch_updated_at();

create table if not exists military_news (
  id bigint generated always as identity primary key,
  "place_id" text,
  "news_id" text,
  "installation_id" text,
  "installation" text,
  "unit" text,
  "unit_id" text,
  "title" text,
  "summary" text,
  "published" text,
  "author" text,
  "url" text,
  "image_url" text,
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
create index if not exists military_news_gov_idx on military_news (government_key);
create index if not exists military_news_place_idx on military_news (place_id, installation_id, published);

insert into datasets (id, table_name, title, description) values ('military-news', 'military_news', $t$Military news from the bases$t$, $d$News stories published by the public affairs offices of the units at Tyndall Air Force Base and Naval Support Activity Panama City (325th Fighter Wing, 601st Air and Space Operations Center, NSA Panama City, Naval Surface Warfare Center Panama City Division, Navy Experimental Diving Unit), read daily from each unit's DVIDS feed: title, summary, date (Central time), author and the story's own link. Story text and photos stay on DVIDS. 2016 and later.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table military_news enable row level security;
drop policy if exists "public read" on military_news;
create policy "public read" on military_news for select using (true);

drop trigger if exists military_news_touch on military_news;
create trigger military_news_touch before update on military_news for each row execute function touch_updated_at();

create table if not exists federal_contracts (
  id bigint generated always as identity primary key,
  "place_id" text,
  "award_key" text,
  "award_id" text,
  "recipient" text,
  "recipient_uei" text,
  "recipient_city" text,
  "recipient_entity_id" text,
  "recipient_url" text,
  "recipient_match" text,
  "agency" text,
  "sub_agency" text,
  "agency_entity_id" text,
  "defense" boolean,
  "award_type" text,
  "description" text,
  "naics" text,
  "naics_description" text,
  "psc" text,
  "psc_description" text,
  "start_date" text,
  "end_date" text,
  "first_action_date" text,
  "last_action_date" text,
  "actions" bigint,
  "obligated" numeric,
  "award_amount" numeric,
  "performance_city" text,
  "performance_county" text,
  "performance_state" text,
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
create index if not exists federal_contracts_gov_idx on federal_contracts (government_key);
create index if not exists federal_contracts_place_idx on federal_contracts (place_id, recipient_entity_id, agency_entity_id);

insert into datasets (id, table_name, title, description) values ('federal-contracts', 'federal_contracts', $t$Federal contracts to local companies$t$, $d$Every federal contract with money obligated since 2016 to a company whose business address is in the county, from USAspending.gov: recipient (as registered in SAM.gov, with its city, never its street address), the agency and branch that signed it, what it buys (description, industry and product codes), start and end dates, and obligated, the money obligated from 2016 on (modifications and cuts included, so it can be negative). award_amount is USAspending's lifetime total, which can include earlier years. defense is true for Department of Defense contracts. recipient_entity_id links to the company's profile; recipient_match says how it was joined to other records (blank: by its own name only).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table federal_contracts enable row level security;
drop policy if exists "public read" on federal_contracts;
create policy "public read" on federal_contracts for select using (true);

drop trigger if exists federal_contracts_touch on federal_contracts;
create trigger federal_contracts_touch before update on federal_contracts for each row execute function touch_updated_at();

create table if not exists federal_contract_years (
  id bigint generated always as identity primary key,
  "place_id" text,
  "year" bigint,
  "recipient" text,
  "recipient_entity_id" text,
  "recipient_url" text,
  "agency" text,
  "sub_agency" text,
  "agency_entity_id" text,
  "defense" boolean,
  "obligated" numeric,
  "actions" bigint,
  "awards" bigint,
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
create index if not exists federal_contract_years_gov_idx on federal_contract_years (government_key);
create index if not exists federal_contract_years_place_idx on federal_contract_years (place_id, year, recipient_entity_id);

insert into datasets (id, table_name, title, description) values ('federal-contract-years', 'federal_contract_years', $t$Federal contracts to local companies by year$t$, $d$Money obligated each calendar year since 2016 on federal contracts to companies based in the county, per company and signing agency, from USAspending.gov contract transactions: obligated dollars, number of contract actions and number of contracts.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table federal_contract_years enable row level security;
drop policy if exists "public read" on federal_contract_years;
create policy "public read" on federal_contract_years for select using (true);

drop trigger if exists federal_contract_years_touch on federal_contract_years;
create trigger federal_contract_years_touch before update on federal_contract_years for each row execute function touch_updated_at();
