-- Savings finder (/public-money/savings): opportunities and the records behind them, built by site/savings_page.py from the
-- Accountability project histories and the CRA ledger. Same standard columns, public read policy and updated_at trigger as
-- every other dataset table (see 0021_page_datasets.sql).

create table if not exists savings_opportunities (
  id bigint generated always as identity primary key,
  "opportunity_id" text,
  "rank" bigint,
  "title" text,
  "government" text,
  "gov_ids" jsonb,
  "lever" text,
  "confidence" text,
  "in_play" numeric,
  "in_play_is" text,
  "rate_low" numeric,
  "rate_high" numeric,
  "savings_low" numeric,
  "savings_high" numeric,
  "estimate" text,
  "basis" text,
  "assumption" text,
  "next_step" text,
  "overlaps" jsonb,
  "records_needed" jsonb,
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
create index if not exists savings_opportunities_gov_idx on savings_opportunities (government_key);
create index if not exists savings_opportunities_gov_id_idx on savings_opportunities (gov_id);
create index if not exists savings_opportunities_opportunity_id_idx on savings_opportunities ("opportunity_id");

insert into datasets (id, table_name, title, description) values ('savings-opportunities', 'savings_opportunities', $t$Savings finder: opportunities$t$, $d$Places Bay County governments could spend less: the spending each touches, a low and high estimate with its stated assumption, the next step and the records still needed. Every figure is computed from the Accountability projects and the CRA ledger.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table savings_opportunities enable row level security;
drop policy if exists "public read" on savings_opportunities;
create policy "public read" on savings_opportunities for select using (true);

drop trigger if exists savings_opportunities_touch on savings_opportunities;
create trigger savings_opportunities_touch before update on savings_opportunities for each row execute function touch_updated_at();

create table if not exists savings_evidence (
  id bigint generated always as identity primary key,
  "opportunity_id" text,
  "group_id" text,
  "group_title" text,
  "kind" text,
  "label" text,
  "amount" numeric,
  "amount_is" text,
  "compare" numeric,
  "compare_is" text,
  "gap" numeric,
  "ratio" numeric,
  "units" numeric,
  "unit" text,
  "per_unit" numeric,
  "paid_to" text,
  "project_id" text,
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
create index if not exists savings_evidence_gov_idx on savings_evidence (government_key);
create index if not exists savings_evidence_gov_id_idx on savings_evidence (gov_id);
create index if not exists savings_evidence_opportunity_id_idx on savings_evidence ("opportunity_id");

insert into datasets (id, table_name, title, description) values ('savings-evidence', 'savings_evidence', $t$Savings finder: evidence$t$, $d$The records behind each savings opportunity, one row per project or CRA ledger record: the figure, what it is compared with, the gap or share, cost per unit where one applies, and the source.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table savings_evidence enable row level security;
drop policy if exists "public read" on savings_evidence;
create policy "public read" on savings_evidence for select using (true);

drop trigger if exists savings_evidence_touch on savings_evidence;
create trigger savings_evidence_touch before update on savings_evidence for each row execute function touch_updated_at();
