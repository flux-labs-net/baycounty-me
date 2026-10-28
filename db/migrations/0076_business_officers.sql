-- Business officers (dataset business-officers, built by site/page_datasets.py business_officers): the officers,
-- managers, members and registered agent of each registered business that has a profile on the site, from the Sunbiz
-- quarterly file (data/sunbiz/<county>/officers.csv.gz). Names and titles only, never addresses. Shown on the business's
-- profile card. Same standard columns, public read policy and updated_at trigger as every other dataset table (see
-- 0021_page_datasets.sql).

create table if not exists business_officers (
  id bigint generated always as identity primary key,
  "place_id" text,
  "entity_id" text,
  "sunbiz_doc_number" text,
  "business" text,
  "business_status" text,
  "officer" text,
  "title" text,
  "officer_kind" text,
  "officer_entity_id" text,
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
create index if not exists business_officers_gov_idx on business_officers (government_key);
create index if not exists business_officers_1_idx on business_officers (entity_id);
create index if not exists business_officers_2_idx on business_officers (sunbiz_doc_number);
create index if not exists business_officers_3_idx on business_officers (officer_entity_id);

insert into datasets (id, table_name, title, description) values ('business-officers', 'business_officers', $t$Business officers$t$, $d$Officers, managers, members and the registered agent of each registered business that has a profile on the site, from Sunbiz. Names and titles only, never addresses.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table business_officers enable row level security;
drop policy if exists "public read" on business_officers;
create policy "public read" on business_officers for select using (true);

drop trigger if exists business_officers_touch on business_officers;
create trigger business_officers_touch before update on business_officers for each row execute function touch_updated_at();
