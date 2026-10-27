-- Volunteer and nonprofit needs board (/volunteer), built by site/volunteer_data.py: open volunteer needs read daily from
-- public volunteer boards (data/volunteer/fetch_needs.py) and local nonprofits that use volunteers (their latest Form 990
-- volunteer count, data/volunteer/fetch_990_volunteers.py). place_id keeps rows for other places apart (fl-bay = Bay
-- County). Same standard columns, public read policy and updated_at trigger as every other dataset table (see
-- 0021_page_datasets.sql).

create table if not exists volunteer_needs (
  id bigint generated always as identity primary key,
  "place_id" text,
  "need_id" text,
  "title" text,
  "organization" text,
  "nonprofit_id" text,
  "organization_entity_id" text,
  "organization_url" text,
  "cause" text,
  "board_interest" text,
  "schedule" text,
  "when_text" text,
  "starts" text,
  "ends" text,
  "posted" text,
  "closes" text,
  "first_seen" text,
  "description" text,
  "details" text,
  "city" text,
  "zip" text,
  "remote" boolean,
  "board" text,
  "url" text,
  "as_of" text,
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
create index if not exists volunteer_needs_gov_idx on volunteer_needs (government_key);
create index if not exists volunteer_needs_place_idx on volunteer_needs (place_id, need_id);
create index if not exists volunteer_needs_cause_idx on volunteer_needs (cause);

insert into datasets (id, table_name, title, description) values ('volunteer-needs', 'volunteer_needs', $t$Volunteer needs$t$, $d$Open volunteer needs in the county, read every day from public volunteer boards (United Way of Northwest Florida's volunteer center and Idealist): what volunteers do, the organization, a plain cause, when (ongoing, one day or shifts), the city and ZIP, and the board's sign-up link. nonprofit_id and organization_entity_id link to the local nonprofit's profile where the name matches. No street addresses or contact details.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table volunteer_needs enable row level security;
drop policy if exists "public read" on volunteer_needs;
create policy "public read" on volunteer_needs for select using (true);

drop trigger if exists volunteer_needs_touch on volunteer_needs;
create trigger volunteer_needs_touch before update on volunteer_needs for each row execute function touch_updated_at();

create table if not exists volunteer_orgs (
  id bigint generated always as identity primary key,
  "place_id" text,
  "nonprofit_id" text,
  "entity_id" text,
  "page_url" text,
  "name" text,
  "cause" text,
  "kind" text,
  "city" text,
  "mission" text,
  "website" text,
  "volunteers_reported" bigint,
  "volunteers_year" bigint,
  "employees" bigint,
  "revenue" numeric,
  "open_needs" bigint,
  "needs_boards" text,
  "latest_return_form" text,
  "latest_return_year" bigint,
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
create index if not exists volunteer_orgs_gov_idx on volunteer_orgs (government_key);
create index if not exists volunteer_orgs_place_idx on volunteer_orgs (place_id, nonprofit_id);
create index if not exists volunteer_orgs_cause_idx on volunteer_orgs (cause);

insert into datasets (id, table_name, title, description) values ('volunteer-orgs', 'volunteer_orgs', $t$Nonprofits that use volunteers$t$, $d$Local nonprofits that reported volunteers on their latest IRS Form 990 (Part I line 6, the organization's own estimate, which can cover more than this county) or that have a volunteer need open now: what each does, a plain cause, website, volunteers and employees reported, revenue, and open needs. Homeowner associations, chambers and private foundations are left out unless they post a need.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table volunteer_orgs enable row level security;
drop policy if exists "public read" on volunteer_orgs;
create policy "public read" on volunteer_orgs for select using (true);

drop trigger if exists volunteer_orgs_touch on volunteer_orgs;
create trigger volunteer_orgs_touch before update on volunteer_orgs for each row execute function touch_updated_at();
