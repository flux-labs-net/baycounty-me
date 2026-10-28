-- This week in Bay County: this week's edition of the weekly email and the /this-week page (dataset weekly-roundup,
-- site/weekly.py). One row per item: events and public meetings this week, and votes, contracts and change orders
-- first seen on the site last week (data/weekly/first_seen.json).

create table if not exists weekly_roundup (
  id bigint generated always as identity primary key,
  "place_id" text,
  "week_of" text,
  "section" text,
  "rank" bigint,
  "featured" boolean,
  "record_id" text,
  "title" text,
  "summary" text,
  "date" text,
  "starts" text,
  "ends" text,
  "all_day" boolean,
  "government" text,
  "board" text,
  "town" text,
  "venue" text,
  "category" text,
  "recurring" boolean,
  "agenda_posted" boolean,
  "amount" numeric,
  "new_total" numeric,
  "method" text,
  "outcome" text,
  "tally" text,
  "split" boolean,
  "voted_no" text,
  "people" jsonb,
  "vendor" text,
  "vendor_entity_id" text,
  "vendor_url" text,
  "url" text,
  "page_url" text,
  "source" text,
  "source_url" text,
  "first_seen" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists weekly_roundup_gov_idx on weekly_roundup (government_key);
create index if not exists weekly_roundup_week_idx on weekly_roundup (place_id, week_of, section, rank);

insert into datasets (id, table_name, title, description) values ('weekly-roundup', 'weekly_roundup', $t$This week in Bay County$t$, $d$This week's edition of the weekly email: events and public meetings this week, and votes, contracts and change orders that first appeared on BayCounty.me last week.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table weekly_roundup enable row level security;
drop policy if exists "public read" on weekly_roundup;
create policy "public read" on weekly_roundup for select using (true);

drop trigger if exists weekly_roundup_touch on weekly_roundup;
create trigger weekly_roundup_touch before update on weekly_roundup for each row execute function touch_updated_at();
