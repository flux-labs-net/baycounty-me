"""Generate db/migrations/0001_init.sql from the open-data catalog (site/public/downloads/index.json).

Run once to create the initial schema (already done; the output is committed). Later schema changes
go in new numbered migration files written by hand, never by editing 0001.
"""
import json, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CAT = os.path.join(ROOT, 'site', 'public', 'downloads', 'index.json')
OUT = os.path.join(ROOT, 'db', 'migrations', '0001_init.sql')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
MONEYISH = re.compile(r'amount|pay|salary|total|share|cost|rate|millage|levy|value|tax|pct|lat|lng|fte|hourly|budget|fund|debt|raised|spent|money|organizations|individuals|eligible|federal|payments|obligated|par|outstanding')


def col_type(name, typ, vals):
    if typ == 'number':
        ints = all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals)
        return 'bigint' if ints and not MONEYISH.search(name) else 'numeric'
    if typ == 'boolean':
        return 'boolean'
    if typ in ('array', 'object') or any(not isinstance(v, (str, bool)) for v in vals):
        return 'jsonb'
    return 'date' if vals and all(isinstance(v, str) and DATE.match(v) for v in vals) else 'text'


def q(n):
    return '"' + n.replace('"', '""') + '"'


def main():
    cat = json.load(open(CAT))
    sql = ['''-- BayCounty.me database, initial schema.
-- Every public dataset gets a typed table. Each row records where it came from (origin, ingest run, source_url)
-- so data loaded from the site build ('site_build') can be refreshed without touching rows added by hand or by scrapers.
-- Everything is public record: anyone may read; only the service role (server-side keys) may write.

create table if not exists governments (
  key text primary key,            -- county, schools, pc, pcb, lh, cw, sp, parker, mb, constitutional, special
  slug text unique,
  short_name text not null,
  name text not null,
  kind text,                       -- county, schools, city, constitutional, special
  population_2025 bigint,
  website text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists government_aliases (
  alias text primary key,          -- any spelling used in source data, lowercased: 'bay county bocc', 'city of lynn haven'
  government_key text not null references governments(key) on delete cascade
);

create table if not exists sources (
  id bigint generated always as identity primary key,
  url text unique not null,
  title text,
  publisher text,
  doc_type text,                   -- budget, minutes, audit, pay plan, contract, news, statute, dataset ...
  retrieved_at date,
  created_at timestamptz not null default now()
);

create table if not exists ingest_runs (
  id bigint generated always as identity primary key,
  origin text not null,            -- site_build, manual, scraper:<name>, import:<file>
  dataset text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  rows_in integer,
  rows_deleted integer,
  status text not null default 'running',  -- running, ok, failed
  git_sha text,
  notes text
);

create table if not exists datasets (
  id text primary key,             -- matches the API dataset id, e.g. salary-positions
  table_name text unique not null,
  title text not null,
  description text,
  updated_at timestamptz not null default now()
);

-- Lossless copy of every research file in data/ (the site build still reads these).
create table if not exists raw_files (
  path text primary key,           -- e.g. data/votes/votes.json
  sha256 text not null,
  bytes integer not null,
  content jsonb not null,
  loaded_at timestamptz not null default now(),
  ingest_run_id bigint references ingest_runs(id)
);
''']
    tables = []
    for d in cat['datasets']:
        rows = json.load(open(os.path.join(ROOT, 'site', 'public', d['json'].lstrip('/'))))
        tbl = d['id'].replace('-', '_')
        cols = []
        for c in d['columns']:
            vals = [r.get(c['name']) for r in rows if r.get(c['name']) not in (None, '')]
            cols.append((c['name'], col_type(c['name'], c['type'], vals)))
        tables.append(tbl)
        body = ',\n'.join(f'  {q(n)} {t}' for n, t in cols if n not in ('id',))
        sql.append(f'''-- {d["title"]}: {d["description"]}
create table if not exists {tbl} (
  id bigint generated always as identity primary key,
{body},
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists {tbl}_gov_idx on {tbl} (government_key);
insert into datasets (id, table_name, title, description) values ({json.dumps(d["id"]).replace('"', "'")}, '{tbl}', $t${d["title"]}$t$, $d${d["description"]}$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();
''')
    sql.append('-- Public read, server-side write. (In Supabase, anon/authenticated are the public roles; service_role bypasses RLS.)')
    for t in ['governments', 'government_aliases', 'sources', 'ingest_runs', 'datasets', 'raw_files'] + tables:
        sql.append(f'''alter table {t} enable row level security;
drop policy if exists "public read" on {t};
create policy "public read" on {t} for select using (true);''')
    sql.append('''
-- Keep updated_at current on edits made in the table editor or by scripts.
create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;''')
    for t in ['governments'] + tables:
        sql.append(f'drop trigger if exists {t}_touch on {t};\ncreate trigger {t}_touch before update on {t} for each row execute function touch_updated_at();')
    open(OUT, 'w').write('\n'.join(sql) + '\n')
    print(OUT, len(tables), 'dataset tables')


if __name__ == '__main__':
    main()
