-- Where the data comes from (site/data_sources.py): every source the site takes records from, and every website the
-- records cite. Same standard columns, public read policy and updated_at trigger as every other dataset table
-- (see 0021_page_datasets.sql).

create table if not exists data_sources (
  id bigint generated always as identity primary key,
  "topic" text,
  "topic_id" text,
  "government" text,
  "government_id" text,
  "source_name" text,
  "source_url" text,
  "method" text,
  "refresh" text,
  "what_we_take" text,
  "how_we_process" text,
  "checks" text,
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
create index if not exists data_sources_gov_idx on data_sources (government_key);
create index if not exists data_sources_gov_id_idx on data_sources (gov_id);
create index if not exists data_sources_topic_idx on data_sources ("topic_id");

insert into datasets (id, table_name, title, description) values ('data-sources', 'data_sources', $t$Where the data comes from$t$, $d$Every source BayCounty.me takes records from, one row per source: the topic, the government it covers (or state and federal databases), the link, how we get it, how often, what we take from it, how we process it and the checks we run.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table data_sources enable row level security;
drop policy if exists "public read" on data_sources;
create policy "public read" on data_sources for select using (true);

drop trigger if exists data_sources_touch on data_sources;
create trigger data_sources_touch before update on data_sources for each row execute function touch_updated_at();

create table if not exists data_source_sites (
  id bigint generated always as identity primary key,
  "website" text,
  "topic" text,
  "topic_id" text,
  "documents_cited" bigint,
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
create index if not exists data_source_sites_gov_idx on data_source_sites (government_key);
create index if not exists data_source_sites_gov_id_idx on data_source_sites (gov_id);
create index if not exists data_source_sites_topic_idx on data_source_sites ("topic_id");

insert into datasets (id, table_name, title, description) values ('data-source-sites', 'data_source_sites', $t$Websites our records cite$t$, $d$Every website cited by the records behind BayCounty.me, per topic, with how many distinct documents and pages from it the data links to.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table data_source_sites enable row level security;
drop policy if exists "public read" on data_source_sites;
create policy "public read" on data_source_sites for select using (true);

drop trigger if exists data_source_sites_touch on data_source_sites;
create trigger data_source_sites_touch before update on data_source_sites for each row execute function touch_updated_at();
