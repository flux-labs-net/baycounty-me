-- Police, fire and the Sheriff (/public-safety): who polices and who fights fires in each local government with its
-- budget line (data/safety/<county>/agencies.json), and the crimes and police staffing each agency reported to the FBI
-- (data/safety/fetch_cde.py), built by site/safety_data.py. Counts only; no person is named. Same standard columns,
-- public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists safety_agencies (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency_id" text,
  "agency" text,
  "service" text,
  "government" text,
  "agency_gov_id" text,
  "arrangement" text,
  "budget_amount" numeric,
  "budget_lines" text,
  "budget_fiscal_year" text,
  "budget_source_url" text,
  "fbi_ori" text,
  "officers" bigint,
  "civilians" bigint,
  "staffing_year" bigint,
  "website" text,
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
create index if not exists safety_agencies_gov_idx on safety_agencies (government_key);
create index if not exists safety_agencies_place_idx on safety_agencies (place_id, "agency_id", "service");

insert into datasets (id, table_name, title, description) values ('safety-agencies', 'safety_agencies', $t$Police and fire departments$t$, $d$Who polices and who fights fires in each local government: the agency, how it is arranged (own department, the Sheriff, or a city paying the Sheriff by contract), the FY2026 budget for it (budget_lines names the lines added from the government's adopted budget, the same figures as the budget pages), the latest sworn officers and civilian staff the agency reported to the FBI, and its FBI reporting number (fbi_ori). Hand-checked.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table safety_agencies enable row level security;
drop policy if exists "public read" on safety_agencies;
create policy "public read" on safety_agencies for select using (true);

drop trigger if exists safety_agencies_touch on safety_agencies;
create trigger safety_agencies_touch before update on safety_agencies for each row execute function touch_updated_at();

create table if not exists crime_counts (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency_id" text,
  "agency" text,
  "fbi_ori" text,
  "year" bigint,
  "offense_code" text,
  "offense" text,
  "offense_group" text,
  "total_row" boolean,
  "count" bigint,
  "cleared" bigint,
  "months_reported" bigint,
  "population" bigint,
  "per_1000" numeric,
  "reporting" text,
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
create index if not exists crime_counts_gov_idx on crime_counts (government_key);
create index if not exists crime_counts_place_idx on crime_counts (place_id, "agency_id", "year");

insert into datasets (id, table_name, title, description) values ('crime-counts', 'crime_counts', $t$Crimes reported by police agency$t$, $d$Offenses each police agency in the county reported to the FBI's Uniform Crime Reporting program each year since 2016, from the FBI Crime Data Explorer: violent and property crime totals (total_row true) and murder, rape, robbery, aggravated assault, burglary, larceny-theft, motor vehicle theft and arson, with offenses cleared (solved or closed) and the population the agency covers. A missing year means the agency sent nothing that year (no Florida agency reported for 2021; Panama City Beach has not reported since 2020). Florida agencies sent one yearly summary until 2024 and monthly incident reports (NIBRS) from 2025, so 2025 on is not directly comparable with earlier years. months_reported below 12 means the year is partial; per_1000 is left blank then. Counts only; no person is named.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table crime_counts enable row level security;
drop policy if exists "public read" on crime_counts;
create policy "public read" on crime_counts for select using (true);

drop trigger if exists crime_counts_touch on crime_counts;
create trigger crime_counts_touch before update on crime_counts for each row execute function touch_updated_at();

create table if not exists police_staffing (
  id bigint generated always as identity primary key,
  "place_id" text,
  "agency_id" text,
  "agency" text,
  "fbi_ori" text,
  "year" bigint,
  "officers" bigint,
  "civilians" bigint,
  "employees" bigint,
  "female_officers" bigint,
  "employees_per_1000" numeric,
  "population" bigint,
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
create index if not exists police_staffing_gov_idx on police_staffing (government_key);
create index if not exists police_staffing_place_idx on police_staffing (place_id, "agency_id", "year");

insert into datasets (id, table_name, title, description) values ('police-staffing', 'police_staffing', $t$Police staffing$t$, $d$Sworn officers and civilian employees at each police agency in the county on October 31 each year since 2016, as the agency reported them to the FBI (Crime Data Explorer police employee data), with employees per 1,000 residents covered. The Sheriff's reported civilian staff went from 71 in 2022 to 271 in 2023; the FBI data does not say why.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table police_staffing enable row level security;
drop policy if exists "public read" on police_staffing;
create policy "public read" on police_staffing for select using (true);

drop trigger if exists police_staffing_touch on police_staffing;
create trigger police_staffing_touch before update on police_staffing for each row execute function touch_updated_at();
