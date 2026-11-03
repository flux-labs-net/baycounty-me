-- Special event road closures and visitor guides (IRONMAN Florida first): site/special_events.py, from
-- data/events/<county>/special/<event>.json and the map lines from data/events/place_closures.py.

create table if not exists event_road_closures (
  id bigint generated always as identity primary key,
  "place_id" text,
  "event_id" text,
  "event_name" text,
  "event_page" text,
  "closure_id" text,
  "sort_order" bigint,
  "road" text,
  "limits" text,
  "kind" text,
  "starts_at" text,
  "ends_at" text,
  "town" text,
  "geometry" text,
  "placed" text,
  "as_of" date,
  "source" text,
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
create index if not exists event_road_closures_gov_idx on event_road_closures (government_key);
create index if not exists event_road_closures_place_idx on event_road_closures (place_id);
create index if not exists event_road_closures_event_idx on event_road_closures (event_id);

insert into datasets (id, table_name, title, description) values ('event-road-closures', 'event_road_closures', $t$Special event road closures$t$, $d$Road closures and traffic delays for special events such as IRONMAN Florida, one row per closure, from the police department's traffic advisory: the road and the cross streets it is closed between, closed or delay, and when it starts and ends (ISO times with the Central offset). geometry is the closed stretch as a GeoJSON line in WGS84, placed on the county street centerlines from the street names (placed = street-names).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table event_road_closures enable row level security;
drop policy if exists "public read" on event_road_closures;
create policy "public read" on event_road_closures for select using (true);

drop trigger if exists event_road_closures_touch on event_road_closures;
create trigger event_road_closures_touch before update on event_road_closures for each row execute function touch_updated_at();

create table if not exists event_guide (
  id bigint generated always as identity primary key,
  "place_id" text,
  "event_id" text,
  "event_name" text,
  "section" text,
  "sort_order" bigint,
  "title" text,
  "text" text,
  "when_text" text,
  "at" text,
  "distance_miles" numeric,
  "lat" numeric,
  "lon" numeric,
  "link" text,
  "as_of" date,
  "source" text,
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
create index if not exists event_guide_gov_idx on event_guide (government_key);
create index if not exists event_guide_place_idx on event_guide (place_id);
create index if not exists event_guide_event_idx on event_guide (event_id);

insert into datasets (id, table_name, title, description) values ('event-guide', 'event_guide', $t$Special event visitor guide$t$, $d$The visitor guide for each special event on the site, one row per item: the race week schedule (at = start time), the course (distance_miles), where to watch (with a map point where there is one), getting around and things to do nearby, each with its source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table event_guide enable row level security;
drop policy if exists "public read" on event_guide;
create policy "public read" on event_guide for select using (true);

drop trigger if exists event_guide_touch on event_guide;
create trigger event_guide_touch before update on event_guide for each row execute function touch_updated_at();
