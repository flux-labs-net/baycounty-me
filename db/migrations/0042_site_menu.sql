-- The site's main menu (site/site_menu.py), one row per link, English and Spanish, keyed by place so each place can
-- carry its own menu. Same standard columns, public read policy and updated_at trigger as every other dataset table
-- (see 0021_page_datasets.sql).

create table if not exists site_menu (
  id bigint generated always as identity primary key,
  "place_id" text,
  "lang" text,
  "section" text,
  "section_order" bigint,
  "question" text,
  "item_group" text,
  "item_order" bigint,
  "label" text,
  "href" text,
  "description" text,
  "start_here" boolean,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists site_menu_gov_idx on site_menu (government_key);
create index if not exists site_menu_gov_id_idx on site_menu (gov_id);
create index if not exists site_menu_place_lang_idx on site_menu ("place_id", "lang");

insert into datasets (id, table_name, title, description) values ('site-menu', 'site_menu', $t$Site menu$t$, $d$Every link in the site's main menu, one row per link, in English and Spanish: the section and the question it answers, the link's place in the section, and the section's start-here page. place_id is the place the menu belongs to (fl-bay = Bay County).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table site_menu enable row level security;
drop policy if exists "public read" on site_menu;
create policy "public read" on site_menu for select using (true);

drop trigger if exists site_menu_touch on site_menu;
create trigger site_menu_touch before update on site_menu for each row execute function touch_updated_at();
