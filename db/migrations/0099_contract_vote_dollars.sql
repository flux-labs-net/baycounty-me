-- Contract dollars behind each official's votes (site/vote_dollars.py): every contract, purchase and consent agenda vote
-- with the dollar figure it approved and whether it is counted, each member's vote on the counted ones, and per-official
-- totals. Same standard columns, public read policy and updated_at trigger as 0021_page_datasets.sql.

create table if not exists contract_vote_dollars (
  id bigint generated always as identity primary key,
  "vote_id" text,
  "body" text,
  "board" text,
  "date" date,
  "agenda_item" text,
  "headline" text,
  "category" text,
  "kind" text,
  "amount" numeric,
  "amount_from" text,
  "up_to" boolean,
  "per_year" boolean,
  "counted" boolean,
  "not_counted_reason" text,
  "same_item_as" text,
  "outcome" text,
  "tally" text,
  "vote_method" text,
  "verified" text,
  "contract_record_ids" text,
  "contract_vendor_ids" text,
  "source_type" text,
  "source_title" text,
  "source_url" text,
  "source_page" bigint,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists contract_vote_dollars_gov_idx on contract_vote_dollars (government_key);
create index if not exists contract_vote_dollars_gov_id_idx on contract_vote_dollars (gov_id);
create index if not exists contract_vote_dollars_vote_id_idx on contract_vote_dollars ("vote_id");
create index if not exists contract_vote_dollars_date_idx on contract_vote_dollars ("date");
create index if not exists contract_vote_dollars_counted_idx on contract_vote_dollars ("counted");

insert into datasets (id, table_name, title, description) values ('contract-vote-dollars', 'contract_vote_dollars', $t$Contract votes and their dollar figures$t$, $d$Every recorded vote since 2016 on a contract, purchase, change order, task order or consent agenda, with the dollar figure it approved and whether that figure is counted in the officials' contract-dollar totals (not_counted_reason says why not).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table contract_vote_dollars enable row level security;
drop policy if exists "public read" on contract_vote_dollars;
create policy "public read" on contract_vote_dollars for select using (true);

drop trigger if exists contract_vote_dollars_touch on contract_vote_dollars;
create trigger contract_vote_dollars_touch before update on contract_vote_dollars for each row execute function touch_updated_at();

create table if not exists member_contract_dollars (
  id bigint generated always as identity primary key,
  "vote_id" text,
  "person_id" text,
  "member" text,
  "vote" text,
  "board" text,
  "date" date,
  "headline" text,
  "kind" text,
  "amount" numeric,
  "up_to" boolean,
  "per_year" boolean,
  "outcome" text,
  "tally" text,
  "vote_method" text,
  "source_url" text,
  "source_page" bigint,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists member_contract_dollars_gov_idx on member_contract_dollars (government_key);
create index if not exists member_contract_dollars_gov_id_idx on member_contract_dollars (gov_id);
create index if not exists member_contract_dollars_person_id_idx on member_contract_dollars ("person_id");
create index if not exists member_contract_dollars_vote_id_idx on member_contract_dollars ("vote_id");

insert into datasets (id, table_name, title, description) values ('member-contract-dollars', 'member_contract_dollars', $t$Contract dollars by member vote$t$, $d$One row per board member per counted contract vote: how the member voted on that dollar figure.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table member_contract_dollars enable row level security;
drop policy if exists "public read" on member_contract_dollars;
create policy "public read" on member_contract_dollars for select using (true);

drop trigger if exists member_contract_dollars_touch on member_contract_dollars;
create trigger member_contract_dollars_touch before update on member_contract_dollars for each row execute function touch_updated_at();

create table if not exists contract_dollar_totals (
  id bigint generated always as identity primary key,
  "person_id" text,
  "member" text,
  "yes_total" numeric,
  "yes_votes" bigint,
  "yes_failed_total" numeric,
  "yes_failed_votes" bigint,
  "no_total" numeric,
  "no_votes" bigint,
  "absent_or_abstained_votes" bigint,
  "first_date" date,
  "last_date" date,
  "contract_votes" bigint,
  "not_counted_consent" bigint,
  "not_counted_no_amount" bigint,
  "not_counted_unclear" bigint,
  "not_counted_not_spending" bigint,
  "not_counted_repeat" bigint,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists contract_dollar_totals_gov_idx on contract_dollar_totals (government_key);
create index if not exists contract_dollar_totals_gov_id_idx on contract_dollar_totals (gov_id);
create index if not exists contract_dollar_totals_person_id_idx on contract_dollar_totals ("person_id");

insert into datasets (id, table_name, title, description) values ('contract-dollar-totals', 'contract_dollar_totals', $t$Contract dollars each official voted on$t$, $d$One row per official per government: dollars in counted contract votes they voted yes on (passed and failed) and no on, with the vote counts behind each and how many contract votes are not in the totals.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table contract_dollar_totals enable row level security;
drop policy if exists "public read" on contract_dollar_totals;
create policy "public read" on contract_dollar_totals for select using (true);

drop trigger if exists contract_dollar_totals_touch on contract_dollar_totals;
create trigger contract_dollar_totals_touch before update on contract_dollar_totals for each row execute function touch_updated_at();
