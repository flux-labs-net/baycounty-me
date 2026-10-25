-- Every local campaign from 2016 through 2025 (the "Past elections" page, /elections/past, and people's profiles): one row per
-- candidate campaign from the Bay County Supervisor of Elections, winners and losers, with totals by contributor type
-- (individuals summed, never named), and every gift from an organization to those campaigns. Built by site/opendata.py
-- from data/campaign/campaign_history.json (data/campaign/history.py). connections_gifts gains past_campaign_year for gifts
-- to someone known only from a past campaign.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists campaign_history (
  id bigint generated always as identity primary key,
  "election_year" bigint,
  "election" text,
  "election_date" text,
  "primary_date" text,
  "government" text,
  "office" text,
  "candidate" text,
  "district" text,
  "person_id" text,
  "party" text,
  "outcome" text,
  "soe_status" text,
  "total_raised" numeric,
  "monetary" numeric,
  "in_kind" numeric,
  "loans" numeric,
  "total_spent" numeric,
  "n_contributions" bigint,
  "from_individuals_total" numeric,
  "from_individuals_count" bigint,
  "from_individuals_in_county" numeric,
  "from_businesses" numeric,
  "from_pacs_and_committees" numeric,
  "from_parties" numeric,
  "from_other" numeric,
  "own_money" numeric,
  "own_loans" numeric,
  "reports_through" text,
  "reconciliation" text,
  "soe_candidate_id" bigint,
  "report_url" text,
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
create index if not exists campaign_history_gov_idx on campaign_history (government_key);
create index if not exists campaign_history_year_idx on campaign_history (election_year, gov_id);
create index if not exists campaign_history_person_idx on campaign_history (person_id);

insert into datasets (id, table_name, title, description) values ('campaign-history', 'campaign_history', $t$Local campaigns since 2016$t$, $d$Every candidate who opened a campaign account with the Bay County Supervisor of Elections for a local race from 2016 through 2025, winners and losers: what each raised and spent, and how much came from individuals (summed, never named), businesses, committees, parties and the candidate.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table campaign_history enable row level security;
drop policy if exists "public read" on campaign_history;
create policy "public read" on campaign_history for select using (true);

drop trigger if exists campaign_history_touch on campaign_history;
create trigger campaign_history_touch before update on campaign_history for each row execute function touch_updated_at();

create table if not exists campaign_contributions_history (
  id bigint generated always as identity primary key,
  "election_year" bigint,
  "election" text,
  "office" text,
  "candidate" text,
  "outcome" text,
  "contributor" text,
  "contributor_type" text,
  "city" text,
  "amount" numeric,
  "date" text,
  "kind" text,
  "report_url" text,
  "vendor_id" text,
  "vendor_ids" jsonb,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists campaign_contributions_history_gov_idx on campaign_contributions_history (government_key);
create index if not exists campaign_contributions_history_year_idx on campaign_contributions_history (election_year, gov_id);
create index if not exists campaign_contributions_history_vendor_idx on campaign_contributions_history (vendor_id);

insert into datasets (id, table_name, title, description) values ('campaign-contributions-history', 'campaign_contributions_history', $t$Contributions from organizations, 2016-2025$t$, $d$Every contribution from a business, committee or party to a local candidate in the 2016 to 2025 elections, as filed. Individual donors are not included, and neither is bank interest on campaign accounts.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table campaign_contributions_history enable row level security;
drop policy if exists "public read" on campaign_contributions_history;
create policy "public read" on campaign_contributions_history for select using (true);

drop trigger if exists campaign_contributions_history_touch on campaign_contributions_history;
create trigger campaign_contributions_history_touch before update on campaign_contributions_history for each row execute function touch_updated_at();

alter table connections_gifts add column if not exists "past_campaign_year" bigint;
