-- Campaign gifts from business owners: personal gifts to local campaigns from people who run a registered Florida
-- business, matched by name and street address to a Sunbiz officer, manager or registered agent
-- (data/campaign/owner_gifts.py). One row per person and campaign. The person is named with the businesses they run;
-- no addresses or occupations. Every other individual donor stays unnamed (summed totals only).
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists owner_gifts (
  id bigint generated always as identity primary key,
  "donor_id" text,
  "donor" text,
  "businesses" text,
  "business_doc_numbers" text,
  "active_businesses" bigint,
  "candidate" text,
  "candidate_id" text,
  "office" text,
  "election" text,
  "gifts" bigint,
  "amount" numeric,
  "first_date" text,
  "last_date" text,
  "match" text,
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
create index if not exists owner_gifts_gov_idx on owner_gifts (government_key);
create index if not exists owner_gifts_gov_id_idx on owner_gifts (gov_id);
create index if not exists owner_gifts_donor_idx on owner_gifts ("donor_id");
create index if not exists owner_gifts_candidate_idx on owner_gifts ("candidate_id");

insert into datasets (id, table_name, title, description) values ('owner-gifts', 'owner_gifts', $t$Campaign gifts from business owners$t$, $d$Personal gifts to local campaigns from people who run a registered Florida business, one row per person and campaign, matched by name and street address to a Sunbiz officer, manager or registered agent. Other individual donors are never named. No addresses or occupations.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table owner_gifts enable row level security;
drop policy if exists "public read" on owner_gifts;
create policy "public read" on owner_gifts for select using (true);

drop trigger if exists owner_gifts_touch on owner_gifts;
create trigger owner_gifts_touch before update on owner_gifts for each row execute function touch_updated_at();
