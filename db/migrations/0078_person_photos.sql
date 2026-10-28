-- Person photos (profiles, connection lists, People cards, government pages, search, network maps, apps): one row per
-- profile with a photo, built by site/page_datasets.py person_photos() (site/person_photos.py) from government
-- headshots (data/civic/official_photos.json) and chamber board and staff headshots (data/chambers/<county>/photos.json).
-- entity_id is the profile (person: or member:); a government photo wins over a chamber photo for the same person.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists person_photos (
  id bigint generated always as identity primary key,
  "place_id" text,
  "entity_id" text,
  "person_id" text,
  "name" text,
  "photo_url" text,
  "photo_path" text,
  "published_by" text,
  "credit" text,
  "source_url" text,
  "image_source_url" text,
  "fetched_on" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists person_photos_entity_idx on person_photos (entity_id);
create index if not exists person_photos_person_idx on person_photos (person_id);

insert into datasets (id, table_name, title, description) values ('person-photos', 'person_photos', $t$Person photos$t$, $d$Every photo of a person on BayCounty.me, one row per profile: officials' headshots their government publishes and chamber of commerce board and staff headshots the chamber publishes, with who published each photo and the page it came from.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table person_photos enable row level security;
drop policy if exists "public read" on person_photos;
create policy "public read" on person_photos for select using (true);

drop trigger if exists person_photos_touch on person_photos;
create trigger person_photos_touch before update on person_photos for each row execute function touch_updated_at();
