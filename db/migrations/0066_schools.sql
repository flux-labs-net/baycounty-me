-- Public schools (/schools): the school district's schools, state grades, spending per school, enrollment by year,
-- calendar and attendance zones, built by site/page_datasets.py _school_rows() from data/schools/<county>/
-- (data/schools/fetch_schools.py and fetch_fldoe.py). place_id keeps rows for other places apart (fl-bay = Bay County).
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists schools (
  id bigint generated always as identity primary key,
  "place_id" text,
  "school_id" text,
  "nces_id" text,
  "name" text,
  "status" text,
  "level" text,
  "school_type" text,
  "grades" text,
  "charter" boolean,
  "virtual" boolean,
  "operator_entity_id" text,
  "address" text,
  "city" text,
  "zip" text,
  "phone" text,
  "latitude" numeric,
  "longitude" numeric,
  "enrollment" bigint,
  "enrollment_year" text,
  "last_year_open" text,
  "teachers_fte" numeric,
  "students_per_teacher" numeric,
  "free_reduced_lunch_pct" numeric,
  "latest_grade" text,
  "latest_grade_year" bigint,
  "prior_grade" text,
  "grades_on_record" bigint,
  "latest_per_student" numeric,
  "latest_spending_year" bigint,
  "zoned_levels" text,
  "district" text,
  "page_url" text,
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
create index if not exists schools_gov_idx on schools (government_key);
create index if not exists schools_place_idx on schools (place_id, school_id, status, level);

insert into datasets (id, table_name, title, description) values ('schools', 'schools', $t$Public schools$t$, $d$One row per public school in the district, open now or closed since 2016: level, grades, district or charter, address, enrollment, teachers, latest state grade and per-student spending, and the attendance zones that feed it.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table schools enable row level security;
drop policy if exists "public read" on schools;
create policy "public read" on schools for select using (true);

drop trigger if exists schools_touch on schools;
create trigger schools_touch before update on schools for each row execute function touch_updated_at();

create table if not exists school_grades (
  id bigint generated always as identity primary key,
  "place_id" text,
  "school_id" text,
  "school" text,
  "school_year" text,
  "grade" text,
  "informational_baseline" boolean,
  "year" bigint,
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
  "total_points" numeric,
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
create index if not exists school_grades_gov_idx on school_grades (government_key);
create index if not exists school_grades_place_idx on school_grades (place_id, school_id, year);

insert into datasets (id, table_name, title, description) values ('school-grades', 'school_grades', $t$School grades$t$, $d$Every Florida school grade on record for each school since 2016, with the latest year's components.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_grades enable row level security;
drop policy if exists "public read" on school_grades;
create policy "public read" on school_grades for select using (true);

drop trigger if exists school_grades_touch on school_grades;
create trigger school_grades_touch before update on school_grades for each row execute function touch_updated_at();

create table if not exists school_spending (
  id bigint generated always as identity primary key,
  "place_id" text,
  "school_id" text,
  "school" text,
  "year" bigint,
  "school_year" text,
  "federal_per_student" numeric,
  "state_local_per_student" numeric,
  "total_per_student" numeric,
  "enrollment" bigint,
  "estimated_total" numeric,
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
create index if not exists school_spending_gov_idx on school_spending (government_key);
create index if not exists school_spending_place_idx on school_spending (place_id, school_id, year);

insert into datasets (id, table_name, title, description) values ('school-spending', 'school_spending', $t$Spending per school$t$, $d$Per-student spending at each school (federal, state and local) from the state's ESSA per-pupil expenditure reports.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_spending enable row level security;
drop policy if exists "public read" on school_spending;
create policy "public read" on school_spending for select using (true);

drop trigger if exists school_spending_touch on school_spending;
create trigger school_spending_touch before update on school_spending for each row execute function touch_updated_at();

create table if not exists school_enrollment (
  id bigint generated always as identity primary key,
  "place_id" text,
  "school_id" text,
  "school" text,
  "year" bigint,
  "school_year" text,
  "enrollment" bigint,
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
create index if not exists school_enrollment_gov_idx on school_enrollment (government_key);
create index if not exists school_enrollment_place_idx on school_enrollment (place_id, school_id, year);

insert into datasets (id, table_name, title, description) values ('school-enrollment', 'school_enrollment', $t$School enrollment by year$t$, $d$Students enrolled at each public school each school year since 2015-16, from the federal school directory.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_enrollment enable row level security;
drop policy if exists "public read" on school_enrollment;
create policy "public read" on school_enrollment for select using (true);

drop trigger if exists school_enrollment_touch on school_enrollment;
create trigger school_enrollment_touch before update on school_enrollment for each row execute function touch_updated_at();

create table if not exists school_calendar (
  id bigint generated always as identity primary key,
  "place_id" text,
  "event_id" text,
  "title" text,
  "kind" text,
  "starts" text,
  "ends" text,
  "all_day" boolean,
  "venue" text,
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
create index if not exists school_calendar_gov_idx on school_calendar (government_key);
create index if not exists school_calendar_place_idx on school_calendar (place_id, starts, kind);

insert into datasets (id, table_name, title, description) values ('school-calendar', 'school_calendar', $t$School district calendar$t$, $d$The school district's calendar: first and last day, holidays and breaks, no-school days, early release, grading periods, graduations and School Board meetings.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_calendar enable row level security;
drop policy if exists "public read" on school_calendar;
create policy "public read" on school_calendar for select using (true);

drop trigger if exists school_calendar_touch on school_calendar;
create trigger school_calendar_touch before update on school_calendar for each row execute function touch_updated_at();

create table if not exists school_zones (
  id bigint generated always as identity primary key,
  "place_id" text,
  "zone_id" text,
  "level" text,
  "zone_name" text,
  "school_id" text,
  "school" text,
  "mou_area" boolean,
  "pieces" bigint,
  "area_sq_mi" numeric,
  "last_edited" text,
  "geometry" text,
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
create index if not exists school_zones_gov_idx on school_zones (government_key);
create index if not exists school_zones_place_idx on school_zones (place_id, level, school_id);

insert into datasets (id, table_name, title, description) values ('school-zones', 'school_zones', $t$School attendance zones$t$, $d$The school district's attendance zones with the school each feeds and its shape as GeoJSON.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table school_zones enable row level security;
drop policy if exists "public read" on school_zones;
create policy "public read" on school_zones for select using (true);

drop trigger if exists school_zones_touch on school_zones;
create trigger school_zones_touch before update on school_zones for each row execute function touch_updated_at();
