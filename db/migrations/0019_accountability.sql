-- Accountability console (PR #30): projects tracked from opening to close, and their dated timelines.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0001_init.sql).
create table if not exists accountability_projects (
  id bigint generated always as identity primary key,
  "project_id" text,
  "project" text,
  "government" text,
  "agency" text,
  "kind" text,
  "stage" text,
  "first_figure" numeric,
  "first_figure_is" text,
  "latest_figure" numeric,
  "latest_figure_is" text,
  "growth_pct" numeric,
  "project_total" numeric,
  "flags" text,
  "records_missing" text,
  "agency_reply" text,
  "first_date" date,
  "last_date" date,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists accountability_projects_gov_idx on accountability_projects (government_key);
create index if not exists accountability_projects_gov_id_idx on accountability_projects (gov_id);
create index if not exists accountability_projects_project_id_idx on accountability_projects (project_id);

insert into datasets (id, table_name, title, description) values ('accountability-projects', 'accountability_projects', $t$Accountability: projects$t$, $d$One row per project on the Accountability console: stage, first and latest figures, cost growth, questions raised by the published rules, records still missing and the agency reply.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table accountability_projects enable row level security;
drop policy if exists "public read" on accountability_projects;
create policy "public read" on accountability_projects for select using (true);

drop trigger if exists accountability_projects_touch on accountability_projects;
create trigger accountability_projects_touch before update on accountability_projects for each row execute function touch_updated_at();

-- Accountability: project timelines. Every dated event (budgets, approvals, awards, change orders, votes, payments,
-- completion). "date" stays text because some sources give only a month or a fiscal year; sort_date orders them.
create table if not exists accountability_events (
  id bigint generated always as identity primary key,
  "project_id" text,
  "project" text,
  "government" text,
  "date" text,
  "sort_date" text,
  "event" text,
  "amount" numeric,
  "approximate" boolean,
  "description" text,
  "paid_to" text,
  "news_report" boolean,
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
create index if not exists accountability_events_gov_idx on accountability_events (government_key);
create index if not exists accountability_events_gov_id_idx on accountability_events (gov_id);
create index if not exists accountability_events_project_id_idx on accountability_events (project_id, sort_date);

insert into datasets (id, table_name, title, description) values ('accountability-events', 'accountability_events', $t$Accountability: project timelines$t$, $d$Every dated event in each project timeline: budgets, approvals, awards, change orders, votes, payments and completion, with sources.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table accountability_events enable row level security;
drop policy if exists "public read" on accountability_events;
create policy "public read" on accountability_events for select using (true);

drop trigger if exists accountability_events_touch on accountability_events;
create trigger accountability_events_touch before update on accountability_events for each row execute function touch_updated_at();
