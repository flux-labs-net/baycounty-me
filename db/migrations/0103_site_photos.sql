-- Site photos: photos of places in the county on the site's own pages (the homepage hero, section cards, this-week story
-- and Your money band), one row per spot a photo fills, with the photographer, license and Commons page. Built by
-- site/site_photos.py from data/photos/<county>/site_photos.json. Same standard columns, public read policy and
-- updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists site_photos (
  id bigint generated always as identity primary key,
  "place_id" text,
  "photo_id" text,
  "page" text,
  "slot" text,
  "title" text,
  "place_name" text,
  "photo_url" text,
  "photo_path" text,
  "small_path" text,
  "credit" text,
  "license" text,
  "license_url" text,
  "source_url" text,
  "taken" text,
  "fetched_on" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists site_photos_page_idx on site_photos (page, slot);
create index if not exists site_photos_gov_id_idx on site_photos (gov_id);

insert into datasets (id, table_name, title, description) values ('site-photos', 'site_photos', $t$Site photos$t$, $d$Photos of places in the county on BayCounty.me's own pages (the homepage first), one row per spot a photo fills, with what it shows, the photographer, the license and the photo's Wikimedia Commons page. Free licenses only.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table site_photos enable row level security;
drop policy if exists "public read" on site_photos;
create policy "public read" on site_photos for select using (true);

drop trigger if exists site_photos_touch on site_photos;
create trigger site_photos_touch before update on site_photos for each row execute function touch_updated_at();
