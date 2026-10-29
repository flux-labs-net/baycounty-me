-- School grade details and school day times (/schools): third-grade reading and the school type on each school grade
-- row, statewide grade results by school type (school-grade-state) so a school can be compared with the state, and each
-- school's start and end times (school-bell-times). Built by site/page_datasets.py _school_rows() from
-- data/schools/<county>/grades.json (data/schools/fetch_fldoe.py) and bell_times.json (typed from the district's chart).
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

alter table school_grades add column if not exists "school_type" text;
alter table school_grades add column if not exists "grade3_ela_achievement" numeric;

create table if not exists school_grade_state (
  id bigint generated always as identity primary key,
  "state" text,
  "year" bigint,
  "school_year" text,
  "school_type" text,
  "schools_graded" numeric,
  "grade_a" numeric,
  "grade_b" numeric,
  "grade_c" numeric,
  "grade_d" numeric,
  "grade_f" numeric,
  "grade_i" numeric,
  "grade3_ela_achievement" numeric,
  "ela_achievement" numeric,
  "ela_gains" numeric,
  "ela_gains_low25" numeric,
  "math_achievement" numeric,
  "math_gains" numeric,
  "math_gains_low25" numeric,
  "science_achievement" numeric,
  "social_studies_achievement" numeric,
  "middle_acceleration" numeric,
  "graduation_rate" numeric,
  "college_career_acceleration" numeric,
  "percent_of_points" numeric,
  "percent_tested" numeric,
  "pct_economically_disadvantaged" numeric,
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
create index if not exists school_grade_state_gov_idx on school_grade_state (government_key);
create index if not exists school_grade_state_year_idx on school_grade_state (year, school_type);

insert into datasets (id, table_name, title, description) values ('school-grade-state', 'school_grade_state', $t$School grades statewide$t$, $d$Florida-wide school grade results by school type and year: how many schools got each grade and the average of each grade component across the state's schools.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_grade_state enable row level security;
drop policy if exists "public read" on school_grade_state;
create policy "public read" on school_grade_state for select using (true);

drop trigger if exists school_grade_state_touch on school_grade_state;
create trigger school_grade_state_touch before update on school_grade_state for each row execute function touch_updated_at();

create table if not exists school_bell_times (
  id bigint generated always as identity primary key,
  "place_id" text,
  "school_id" text,
  "school" text,
  "part" text,
  "kind" text,
  "start_time" text,
  "end_time" text,
  "note" text,
  "group_name" text,
  "school_year" text,
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
create index if not exists school_bell_times_gov_idx on school_bell_times (government_key);
create index if not exists school_bell_times_place_idx on school_bell_times (place_id, school_id);

insert into datasets (id, table_name, title, description) values ('school-bell-times', 'school_bell_times', $t$School start and end times$t$, $d$When each public school's day starts and ends this school year, from the district's published chart, plus early release dismissal times by school level.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_bell_times enable row level security;
drop policy if exists "public read" on school_bell_times;
create policy "public read" on school_bell_times for select using (true);

drop trigger if exists school_bell_times_touch on school_bell_times;
create trigger school_bell_times_touch before update on school_bell_times for each row execute function touch_updated_at();
