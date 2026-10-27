-- Chambers of commerce (/chambers): the Bay County Chamber and the Panama City Beach Chamber, built by site/page_datasets.py
-- _chamber_rows() from data/chambers/<county>/chambers.json (copied by hand from each chamber's site) and events.json
-- (data/chambers/fetch_events.py), joined to the nonprofits datasets for IRS filings and public money. place_id keeps rows
-- for other places apart (fl-bay = Bay County). Same standard columns, public read policy and updated_at trigger as every
-- other dataset table (see 0021_page_datasets.sql).

create table if not exists chambers (
  id bigint generated always as identity primary key,
  "place_id" text,
  "chamber_id" text,
  "name" text,
  "short_name" text,
  "legal_name" text,
  "entity_id" text,
  "page_url" text,
  "ein" text,
  "sunbiz_doc_number" text,
  "tax_status" text,
  "founded" bigint,
  "serves" text,
  "tagline" text,
  "about" text,
  "mission" text,
  "board_meets" text,
  "board_seats" bigint,
  "staff_listed" bigint,
  "latest_return_year" bigint,
  "latest_return_form" text,
  "revenue" numeric,
  "expenses" numeric,
  "assets" numeric,
  "employees" bigint,
  "public_money_total" numeric,
  "public_money_from" text,
  "foundation_name" text,
  "foundation_entity_id" text,
  "foundation_revenue" numeric,
  "website" text,
  "events_url" text,
  "directory_url" text,
  "join_url" text,
  "board_url" text,
  "staff_url" text,
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
create index if not exists chambers_gov_idx on chambers (government_key);
create index if not exists chambers_place_idx on chambers (place_id, chamber_id, entity_id);

insert into datasets (id, table_name, title, description) values ('chambers', 'chambers', $t$Chambers of commerce$t$, $d$One row per chamber of commerce: what it is and who it serves, board meetings, its latest IRS Form 990, public money paid to it, its foundation, and links to its member directory, events and join page.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table chambers enable row level security;
drop policy if exists "public read" on chambers;
create policy "public read" on chambers for select using (true);

drop trigger if exists chambers_touch on chambers;
create trigger chambers_touch before update on chambers for each row execute function touch_updated_at();

create table if not exists chamber_leaders (
  id bigint generated always as identity primary key,
  "place_id" text,
  "chamber_id" text,
  "chamber" text,
  "chamber_entity_id" text,
  "role_group" text,
  "sort_order" bigint,
  "person_name" text,
  "title" text,
  "organization" text,
  "term_ends" text,
  "year" bigint,
  "current" boolean,
  "person_entity_id" text,
  "person_url" text,
  "person_match" text,
  "organization_entity_id" text,
  "organization_url" text,
  "organization_match" text,
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
create index if not exists chamber_leaders_gov_idx on chamber_leaders (government_key);
create index if not exists chamber_leaders_place_idx on chamber_leaders (place_id, chamber_id, person_entity_id, organization_entity_id);

insert into datasets (id, table_name, title, description) values ('chamber-leaders', 'chamber_leaders', $t$Chambers of commerce: boards and staff$t$, $d$Each chamber's board, staff and past chairs since 2016 as listed on the chamber's own website: name, title and the organization each board member represents, with links to profiles. No phone numbers, emails or addresses.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table chamber_leaders enable row level security;
drop policy if exists "public read" on chamber_leaders;
create policy "public read" on chamber_leaders for select using (true);

drop trigger if exists chamber_leaders_touch on chamber_leaders;
create trigger chamber_leaders_touch before update on chamber_leaders for each row execute function touch_updated_at();

create table if not exists chamber_events (
  id bigint generated always as identity primary key,
  "place_id" text,
  "chamber_id" text,
  "chamber" text,
  "kind" text,
  "sort_order" bigint,
  "title" text,
  "schedule" text,
  "about" text,
  "starts" text,
  "ends" text,
  "all_day" boolean,
  "venue" text,
  "city" text,
  "category" text,
  "chamber_event" boolean,
  "cost" text,
  "event_id" text,
  "url" text,
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
create index if not exists chamber_events_gov_idx on chamber_events (government_key);
create index if not exists chamber_events_place_idx on chamber_events (place_id, chamber_id, starts);

insert into datasets (id, table_name, title, description) values ('chamber-events', 'chamber_events', $t$Chambers of commerce: events and programs$t$, $d$Upcoming events from each chamber's public calendar and each chamber's signature programs.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table chamber_events enable row level security;
drop policy if exists "public read" on chamber_events;
create policy "public read" on chamber_events for select using (true);

drop trigger if exists chamber_events_touch on chamber_events;
create trigger chamber_events_touch before update on chamber_events for each row execute function touch_updated_at();
