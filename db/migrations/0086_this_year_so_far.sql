-- This year's numbers before the year is over.
-- crime_monthly: each month each police agency reported to the FBI since January 2025 (monthly incident reports), so
--   /public-safety can compare this year so far with the same months last year (site/safety_data.py).
-- data_freshness: the newest period on file for each headline figure and when the next one is due, shown on
--   /data-sources#current (site/freshness.py).
-- bed_tax_collections gains prior_year_same_period: the same months a year earlier, for the current partial fiscal year.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists crime_monthly (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency_id" text,
  "agency" text,
  "fbi_ori" text,
  "year" bigint,
  "month" bigint,
  "period" text,
  "offense_code" text,
  "offense" text,
  "offense_group" text,
  "total_row" boolean,
  "count" bigint,
  "cleared" bigint,
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
create index if not exists crime_monthly_gov_idx on crime_monthly (government_key);
create index if not exists crime_monthly_place_idx on crime_monthly (place_id, "agency_id", "year", "month");

insert into datasets (id, table_name, title, description) values ('crime-monthly', 'crime_monthly', $t$Crimes reported by police agency, by month$t$, $d$Offenses each police agency in the county reported to the FBI each month since January 2025, when Florida agencies moved to monthly incident reports (NIBRS), from the FBI Crime Data Explorer: violent and property crime totals (total_row true) and the eight main offenses, with offenses cleared. This is where this year's numbers come from before the year is over: the page compares this year so far with the same months last year, leaving out the current month and the two before it, which agencies are still adding to. A month that is missing has not been sent yet. Counts only; no person is named.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table crime_monthly enable row level security;
drop policy if exists "public read" on crime_monthly;
create policy "public read" on crime_monthly for select using (true);

drop trigger if exists crime_monthly_touch on crime_monthly;
create trigger crime_monthly_touch before update on crime_monthly for each row execute function touch_updated_at();

create table if not exists data_freshness (
  id bigint generated always as identity primary key,
  "topic" text,
  "figure" text,
  "page" text,
  "latest_period" text,
  "latest_year" bigint,
  "status" text,
  "next_due" text,
  "how_we_get_it" text,
  "source" text,
  "source_url" text,
  "notes" text,
  "checked_on" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists data_freshness_gov_idx on data_freshness (government_key);

insert into datasets (id, table_name, title, description) values ('data-freshness', 'data_freshness', $t$How current each figure is$t$, $d$One row per headline figure on the site: the newest period we have (latest_period, read from the data itself so it moves as refreshes bring in more), whether that is this year, this year so far, the newest the source has published, or newer data that needs a by-hand download (status), when the next period is usually published (next_due, the source's usual schedule as checked on checked_on, not a promise), how we get it, and the source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table data_freshness enable row level security;
drop policy if exists "public read" on data_freshness;
create policy "public read" on data_freshness for select using (true);

drop trigger if exists data_freshness_touch on data_freshness;
create trigger data_freshness_touch before update on data_freshness for each row execute function touch_updated_at();

alter table bed_tax_collections add column if not exists "prior_year_same_period" numeric;
update datasets set description = $d$Bed tax collected by zone and fiscal year. A partial year (the current one) also gives prior_year_same_period: what was collected over the same months a year earlier, from the same Clerk report.$d$, updated_at = now()
  where id = 'bed-tax-collections';
