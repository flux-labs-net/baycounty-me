-- Community events: upcoming events from public calendars around the county (dataset community-events,
-- site/page_datasets.py community_events, input data/events/<county>/events.json from data/events/fetch_events.py).

create table if not exists community_events (
  id bigint generated always as identity primary key,
  "place_id" text,
  "event_id" text,
  "source_id" text,
  "source" text,
  "gov" text,
  "town" text,
  "title" text,
  "starts" text,
  "ends" text,
  "all_day" boolean,
  "venue" text,
  "category" text,
  "recurring" boolean,
  "cost" text,
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
create index if not exists community_events_gov_idx on community_events (government_key);
create index if not exists community_events_place_idx on community_events (place_id, starts);

insert into datasets (id, table_name, title, description) values ('community-events', 'community_events', $t$Community events$t$, $d$Upcoming events from public calendars around the county: county and city calendars, the library system, visitor bureaus and the PCB Chamber.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table community_events enable row level security;
drop policy if exists "public read" on community_events;
create policy "public read" on community_events for select using (true);

drop trigger if exists community_events_touch on community_events;
create trigger community_events_touch before update on community_events for each row execute function touch_updated_at();

-- chamber-leaders: the headshot each chamber publishes of its board and staff (data/chambers/scripts/chamber_photos.py)
alter table chamber_leaders add column if not exists "photo" text;
