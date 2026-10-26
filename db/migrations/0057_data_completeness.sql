-- How complete each government's data is (site/completeness.py): per government and portion of its records, the years
-- since 2016 we expect, how many are on file, the percent and a green / yellow / red status. Same standard columns,
-- public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists data_completeness (
  id bigint generated always as identity primary key,
  "gov_id" text,
  "government" text,
  "portion_id" text,
  "portion" text,
  "period" text,
  "have" numeric,
  "expected" numeric,
  "unit" text,
  "pct" numeric,
  "status" text,
  "missing" text,
  "detail" text,
  "page_url" text,
  "source_url" text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists data_completeness_gov_idx on data_completeness (government_key);
create index if not exists data_completeness_gov_id_idx on data_completeness (gov_id);

insert into datasets (id, table_name, title, description) values ('data-completeness', 'data_completeness', $t$How complete each government's data is$t$, $d$For each government and each portion of its records (adopted budgets, audited spending, tax rates, debt, audit findings, officials by year): the years since 2016 we expect, how many are on file, the percent loaded and a status (complete, partial or missing).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table data_completeness enable row level security;
drop policy if exists "public read" on data_completeness;
create policy "public read" on data_completeness for select using (true);

drop trigger if exists data_completeness_touch on data_completeness;
create trigger data_completeness_touch before update on data_completeness for each row execute function touch_updated_at();
