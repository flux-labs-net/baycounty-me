-- Officeholders by year (government pages' "Who runs it" section, year by year): who held each elected seat on every
-- local government since 2014, one row per person per seat with start and end dates, built by site/page_datasets.py
-- officeholder_terms() from data/civic/officeholders.json (data/civic/scripts/officeholders.py). confirmed = false is
-- a stretch nobody could confirm. place_id keeps rows for other places apart (fl-bay = Bay County).
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists officeholder_terms (
  id bigint generated always as identity primary key,
  "place_id" text,
  "government" text,
  "body" text,
  "seat" text,
  "seat_order" bigint,
  "appointed" boolean,
  "term_order" bigint,
  "person_name" text,
  "person_id" text,
  "start_date" text,
  "end_date" text,
  "start_approx" boolean,
  "end_approx" boolean,
  "how" text,
  "vacant" boolean,
  "confirmed" boolean,
  "note" text,
  "source_title" text,
  "source_url" text,
  gov_id text,
  date_start text,
  date_end text,
  date_precision text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists officeholder_terms_gov_idx on officeholder_terms (government_key);
create index if not exists officeholder_terms_gov_id_idx on officeholder_terms (place_id, gov_id, seat_order, term_order);
create index if not exists officeholder_terms_person_idx on officeholder_terms (person_id);

insert into datasets (id, table_name, title, description) values ('officeholder-terms', 'officeholder_terms', $t$Officeholders by year$t$, $d$Who held each elected seat, and each government's appointed manager, on every local government since 2014: one row per person per seat with start and end dates, so the officials in office in any year can be picked out. Stretches nobody could confirm are marked, and each term names its source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table officeholder_terms enable row level security;
drop policy if exists "public read" on officeholder_terms;
create policy "public read" on officeholder_terms for select using (true);

drop trigger if exists officeholder_terms_touch on officeholder_terms;
create trigger officeholder_terms_touch before update on officeholder_terms for each row execute function touch_updated_at();
