-- Elections hub (/elections/results, /elections/voting), public notices (/notices) and government job openings (/jobs),
-- built by site/civic_data.py from data/elections/results.json (fetch_results.py), data/elections/voting.json
-- (fetch_voting.py), data/notices/<county>/notices.json (fetch_notices.js + build_notices.py) and data/jobs/<county>/jobs.json
-- (fetch_jobs.js). place_id keeps rows for other places apart (fl-bay = Bay County). Same standard columns, public read
-- policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists elections (
  id bigint generated always as identity primary key,
  "place_id" text,
  "election_id" bigint,
  "date" text,
  "name" text,
  "kind" text,
  "status" text,
  "registered_voters" bigint,
  "ballots_cast" bigint,
  "turnout_pct" numeric,
  "precincts_reporting" bigint,
  "precincts_total" bigint,
  "contests" bigint,
  "updated" text,
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
create index if not exists elections_gov_idx on elections (government_key);
create index if not exists elections_place_idx on elections (place_id, election_id, date);

insert into datasets (id, table_name, title, description) values ('elections', 'elections', $t$Elections since 2016$t$, $d$Every election the Supervisor of Elections has held since 2016: date, kind, registered voters, ballots cast, turnout and status.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table elections enable row level security;
drop policy if exists "public read" on elections;
create policy "public read" on elections for select using (true);

drop trigger if exists elections_touch on elections;
create trigger elections_touch before update on elections for each row execute function touch_updated_at();

create table if not exists election_results (
  id bigint generated always as identity primary key,
  "place_id" text,
  "election_id" bigint,
  "election_date" text,
  "election_name" text,
  "election_kind" text,
  "contest_id" bigint,
  "contest" text,
  "office" text,
  "level" text,
  "measure" boolean,
  "party_primary" text,
  "recount" boolean,
  "choice" text,
  "party" text,
  "person_entity_id" text,
  "election_day" bigint,
  "early_voting" bigint,
  "vote_by_mail" bigint,
  "votes" bigint,
  "pct" numeric,
  "rank" bigint,
  "over_votes" bigint,
  "under_votes" bigint,
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
create index if not exists election_results_gov_idx on election_results (government_key);
create index if not exists election_results_place_idx on election_results (place_id, election_id, contest_id, person_entity_id);

insert into datasets (id, table_name, title, description) values ('election-results', 'election_results', $t$Election results since 2016$t$, $d$Official results of every contest on a Bay County ballot since 2016, one row per choice, with votes by Election Day, early voting and mail.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table election_results enable row level security;
drop policy if exists "public read" on election_results;
create policy "public read" on election_results for select using (true);

drop trigger if exists election_results_touch on election_results;
create trigger election_results_touch before update on election_results for each row execute function touch_updated_at();

create table if not exists election_dates (
  id bigint generated always as identity primary key,
  "place_id" text,
  "date" text,
  "end_date" text,
  "starts_at" text,
  "election" text,
  "kind" text,
  "title" text,
  "source" text,
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
create index if not exists election_dates_gov_idx on election_dates (government_key);
create index if not exists election_dates_place_idx on election_dates (place_id, date, kind);

insert into datasets (id, table_name, title, description) values ('election-dates', 'election_dates', $t$Election dates$t$, $d$Registration deadlines, early voting, vote-by-mail deadlines, election days and the Supervisor of Elections' upcoming events.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table election_dates enable row level security;
drop policy if exists "public read" on election_dates;
create policy "public read" on election_dates for select using (true);

drop trigger if exists election_dates_touch on election_dates;
create trigger election_dates_touch before update on election_dates for each row execute function touch_updated_at();

create table if not exists voting_locations (
  id bigint generated always as identity primary key,
  "place_id" text,
  "kind" text,
  "election" text,
  "starts" text,
  "ends" text,
  "hours" text,
  "precinct" text,
  "name" text,
  "address" text,
  "city" text,
  "zip" text,
  "lat" numeric,
  "lon" numeric,
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
create index if not exists voting_locations_gov_idx on voting_locations (government_key);
create index if not exists voting_locations_place_idx on voting_locations (place_id, kind, precinct);

insert into datasets (id, table_name, title, description) values ('voting-locations', 'voting_locations', $t$Where to vote$t$, $d$Early voting sites and each precinct's Election Day polling place, with map coordinates.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table voting_locations enable row level security;
drop policy if exists "public read" on voting_locations;
create policy "public read" on voting_locations for select using (true);

drop trigger if exists voting_locations_touch on voting_locations;
create trigger voting_locations_touch before update on voting_locations for each row execute function touch_updated_at();

create table if not exists public_notices (
  id bigint generated always as identity primary key,
  "place_id" text,
  "notice_id" text,
  "published" text,
  "agency" text,
  "kind" text,
  "kind_label" text,
  "title" text,
  "event_date" text,
  "notice_type" text,
  "text" text,
  "pdf_url" text,
  "publication" text,
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
create index if not exists public_notices_gov_idx on public_notices (government_key);
create index if not exists public_notices_place_idx on public_notices (place_id, notice_id, published, kind);

insert into datasets (id, table_name, title, description) values ('public-notices', 'public_notices', $t$Public notices$t$, $d$Legal notices from local governments and agencies: bids, public hearings, meetings and other notices, with full text. Court and private notices left out.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table public_notices enable row level security;
drop policy if exists "public read" on public_notices;
create policy "public read" on public_notices for select using (true);

drop trigger if exists public_notices_touch on public_notices;
create trigger public_notices_touch before update on public_notices for each row execute function touch_updated_at();

create table if not exists job_openings (
  id bigint generated always as identity primary key,
  "place_id" text,
  "job_id" text,
  "board" text,
  "employer" text,
  "title" text,
  "department" text,
  "job_type" text,
  "pay" text,
  "posted" text,
  "closes" text,
  "ref" text,
  "url" text,
  "first_seen" text,
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
create index if not exists job_openings_gov_idx on job_openings (government_key);
create index if not exists job_openings_place_idx on job_openings (place_id, job_id, board);

insert into datasets (id, table_name, title, description) values ('job-openings', 'job_openings', $t$Government job openings$t$, $d$Open jobs on the county's, school district's, cities' and airport's job boards, read daily.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table job_openings enable row level security;
drop policy if exists "public read" on job_openings;
create policy "public read" on job_openings for select using (true);

drop trigger if exists job_openings_touch on job_openings;
create trigger job_openings_touch before update on job_openings for each row execute function touch_updated_at();

create table if not exists job_boards (
  id bigint generated always as identity primary key,
  "place_id" text,
  "board" text,
  "employer" text,
  "url" text,
  "read" boolean,
  "openings" bigint,
  "note" text,
  "checked" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists job_boards_gov_idx on job_boards (government_key);
create index if not exists job_boards_place_idx on job_boards (place_id, board);

insert into datasets (id, table_name, title, description) values ('job-boards', 'job_boards', $t$Government job boards$t$, $d$Each local government's job board, whether it is read automatically, and how many openings it has.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table job_boards enable row level security;
drop policy if exists "public read" on job_boards;
create policy "public read" on job_boards for select using (true);

drop trigger if exists job_boards_touch on job_boards;
create trigger job_boards_touch before update on job_boards for each row execute function touch_updated_at();
