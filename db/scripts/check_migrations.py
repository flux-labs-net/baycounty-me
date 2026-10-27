"""Check that every db/migrations/*.sql file applies cleanly, in order, to an empty Postgres.

Usage (CI runs this on every pull request):
  DATABASE_URL=postgresql://postgres:postgres@localhost:5432/migrationtest python3 db/scripts/check_migrations.py

What it checks:
  * every file is named NNNN_<name>.sql and no number is used twice (gaps are fine)
  * the whole chain applies with the same runner the production sync uses (load.py --migrate)
  * a second run applies nothing, so schema_migrations records every file
  * every published dataset (site/public/downloads/index.json) has a table with all of its columns, the same check
    the sync makes, so a missing column fails the pull request instead of the sync after merge

Supabase's built-in roles (anon, authenticated, service_role) and auth.uid() don't exist in plain Postgres,
so a small stand-in is created first. Never point this at the production database.
"""
import glob, json, os, re, sys
import psycopg

sys.path.insert(0, os.path.dirname(__file__))
from load import PUB, ROOT, migrate, table_columns

STUB = '''
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end $$;
create schema if not exists auth;
create or replace function auth.uid() returns uuid language sql stable
  as $f$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $f$;
'''


def check_names():
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'db', 'migrations', '*')))
    problems, seen = [], {}
    for f in files:
        m = re.fullmatch(r'(\d{4})_[a-z0-9_]+\.sql', f)
        if not m:
            problems.append(f'{f}: name must look like 0020_short_name.sql (and end in .sql, or it is never applied)')
            continue
        if m.group(1) in seen:
            problems.append(f'{f}: number {m.group(1)} is already used by {seen[m.group(1)]}')
        seen[m.group(1)] = f
    return [f for f in files if f.endswith('.sql')], problems


def check_dataset_columns(cur):
    cat = json.load(open(os.path.join(PUB, 'downloads', 'index.json')))
    problems = []
    for d in cat['datasets']:
        table = d['id'].replace('-', '_')
        cols = table_columns(cur, table)
        if not cols:
            problems.append(f'dataset "{d["id"]}": table {table} is missing')
            continue
        missing = [c['name'] for c in d['columns'] if c['name'] not in cols]
        if missing:
            problems.append(f'dataset "{d["id"]}": table {table} lacks {missing}')
    return problems


def main():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit('Set DATABASE_URL to an empty throwaway Postgres database.')
    if 'supabase' in url:
        raise SystemExit('Refusing to run against a Supabase database; use a throwaway Postgres.')
    files, problems = check_names()
    if problems:
        print('Migration file problems:\n  ' + '\n  '.join(problems))
        raise SystemExit(1)
    with psycopg.connect(url, autocommit=True) as conn:
        cur = conn.cursor()
        cur.execute("select count(*) from information_schema.tables where table_name = 'schema_migrations'")
        if cur.fetchone()[0]:
            raise SystemExit('The test database already has schema_migrations; start from an empty database.')
        cur.execute(STUB)
        with conn.transaction():
            migrate(conn.cursor())
        cur.execute('select name from schema_migrations')
        applied = {r[0] for r in cur.fetchall()}
        missing = [f for f in files if f not in applied]
        if missing:
            print('Not recorded as applied: ' + ', '.join(missing))
            raise SystemExit(1)
        with conn.transaction():
            migrate(conn.cursor())  # must apply nothing
        gaps = check_dataset_columns(cur)
        if gaps:
            print('Datasets the sync would refuse (add a migration):\n  ' + '\n  '.join(gaps))
            raise SystemExit(1)
    print(f'OK: all {len(files)} migrations applied in order.')


if __name__ == '__main__':
    main()
