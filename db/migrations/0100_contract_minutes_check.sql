-- Contract votes in the minutes checked against the contract list (site/contract_coverage.py): every passed contract
-- vote since October 2022 with whether it is in the contracts dataset, under the list's size threshold, without a clear
-- amount, after the last date the list was read, or missing. The government pages use it to say how complete each
-- year's contract count is. Same standard columns, public read policy and updated_at trigger as 0021_page_datasets.sql.

create table if not exists contract_minutes_check (
  id bigint generated always as identity primary key,
  "vote_id" text,
  "board" text,
  "date" date,
  "year" bigint,
  "headline" text,
  "kind" text,
  "amount" numeric,
  "up_to" boolean,
  "status" text,
  "checked_note" text,
  "in_contract_list" boolean,
  "contract_record_ids" text,
  "list_threshold" numeric,
  "list_reviewed_through" date,
  "source_title" text,
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
create index if not exists contract_minutes_check_gov_idx on contract_minutes_check (government_key);
create index if not exists contract_minutes_check_gov_id_idx on contract_minutes_check (gov_id);
create index if not exists contract_minutes_check_date_idx on contract_minutes_check ("date");
create index if not exists contract_minutes_check_status_idx on contract_minutes_check ("status");

insert into datasets (id, table_name, title, description) values ('contract-minutes-check', 'contract_minutes_check', $t$Contract votes checked against the contract list$t$, $d$Every passed contract vote read from the minutes since October 2022, checked against the contracts dataset: in the list, under the list's size threshold, no clear amount in the minutes, after the last date the list was read, or missing.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table contract_minutes_check enable row level security;
drop policy if exists "public read" on contract_minutes_check;
create policy "public read" on contract_minutes_check for select using (true);

drop trigger if exists contract_minutes_check_touch on contract_minutes_check;
create trigger contract_minutes_check_touch before update on contract_minutes_check for each row execute function touch_updated_at();
