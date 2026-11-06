-- Contract awards in the minutes and what came after (site/award_followup.py): every passed contract award since 2016,
-- one row per award and company, with whether any later record at the same government names the same company or bid
-- number (votes, agenda items, contract records, change orders, payments, project histories). no_follow_up rows are the
-- flag: six months or more since the award and nothing on record. Shown on the government pages' Contracts section and
-- drafted as records requests in /admin (data/civic/scripts/stale_requests.py). Same standard columns, public read
-- policy and updated_at trigger as 0021_page_datasets.sql.

create table if not exists award_follow_up (
  id bigint generated always as identity primary key,
  "vote_id" text,
  "board" text,
  "award_date" date,
  "year" bigint,
  "headline" text,
  "amount" numeric,
  "bid_numbers" text,
  "flag_after" date,
  "source_url" text,
  "entity_id" text,
  "company" text,
  "company_from" text,
  "status" text,
  "later_records" bigint,
  "later_kinds" text,
  "first_later_date" date,
  "first_later_what" text,
  "first_later_url" text,
  "last_later_date" date,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists award_follow_up_gov_idx on award_follow_up (government_key);
create index if not exists award_follow_up_gov_id_idx on award_follow_up (gov_id);
create index if not exists award_follow_up_date_idx on award_follow_up ("award_date");
create index if not exists award_follow_up_status_idx on award_follow_up ("status");
create index if not exists award_follow_up_entity_idx on award_follow_up ("entity_id");

insert into datasets (id, table_name, title, description) values ('award-follow-up', 'award_follow_up', $t$Contract awards and what came after$t$, $d$Every passed contract award read from the minutes since 2016, checked for any later record at the same government that names the same company or bid number (votes, agenda items, contract records, change orders, payments, project histories). no_follow_up: six months or more since the award and nothing on record, a question for the government rather than a finding.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table award_follow_up enable row level security;
drop policy if exists "public read" on award_follow_up;
create policy "public read" on award_follow_up for select using (true);

drop trigger if exists award_follow_up_touch on award_follow_up;
create trigger award_follow_up_touch before update on award_follow_up for each row execute function touch_updated_at();
