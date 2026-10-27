-- Official photos (person profiles, People cards and government pages): one row per current official or department
-- leader with a headshot their government publishes, built by site/page_datasets.py official_photos() from
-- data/civic/official_photos.json (data/civic/scripts/official_photos.py). photo_url is the copy BayCounty.me serves;
-- source_url is the government page it came from. Anyone not listed is shown with initials.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists official_photos (
  id bigint generated always as identity primary key,
  "place_id" text,
  "person_id" text,
  "entity_id" text,
  "name" text,
  "photo_url" text,
  "photo_path" text,
  "width" bigint,
  "height" bigint,
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
create index if not exists official_photos_person_idx on official_photos (person_id);
create index if not exists official_photos_entity_idx on official_photos (entity_id);

insert into datasets (id, table_name, title, description) values ('official-photos', 'official_photos', $t$Official photos$t$, $d$Official headshots of current elected officials and department leaders, one row per person, with who published each photo and the government page it came from. Only photos a government publishes on its own website.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table official_photos enable row level security;
drop policy if exists "public read" on official_photos;
create policy "public read" on official_photos for select using (true);

drop trigger if exists official_photos_touch on official_photos;
create trigger official_photos_touch before update on official_photos for each row execute function touch_updated_at();
