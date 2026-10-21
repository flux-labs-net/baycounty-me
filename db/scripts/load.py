"""Load BayCounty.me data into Postgres (Supabase).

Usage:
  DATABASE_URL=postgresql://... python3 db/scripts/load.py          # after `python3 site/build_site.py`
  DATABASE_URL=... python3 db/scripts/load.py --migrate             # also apply db/migrations/*.sql not yet applied

What it does, inside one transaction per dataset:
  * refreshes rows that came from the site build (origin = 'site_build'): deletes them and inserts the current ones
  * never touches rows added by hand or by scrapers (any other origin)
  * stores a lossless copy of every data/**/*.json file in raw_files (only when the file changed)
  * records each step in ingest_runs
Fails loudly if a dataset gained a column the database doesn't have yet: add a migration for it.
"""
import glob, hashlib, json, os, re, subprocess, sys
import psycopg
import psycopg.conninfo
from psycopg.types.json import Jsonb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PUB = os.path.join(ROOT, 'site', 'public')
sys.path.insert(0, os.path.join(ROOT, 'site'))

EXTRA_GOVS = [('constitutional', None, 'County officers', 'Bay County constitutional officers', 'constitutional'),
              ('special', None, 'Special districts', 'Bay County special districts', 'special')]


def git_sha():
    try:
        return subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def migrate(cur):
    cur.execute('create table if not exists schema_migrations (name text primary key, applied_at timestamptz not null default now())')
    cur.execute('select name from schema_migrations'); done = {r[0] for r in cur.fetchall()}
    for fp in sorted(glob.glob(os.path.join(ROOT, 'db', 'migrations', '*.sql'))):
        name = os.path.basename(fp)
        if name in done:
            continue
        cur.execute(open(fp).read())
        cur.execute('insert into schema_migrations (name) values (%s)', (name,))
        print('applied', name)


def seed_governments(cur):
    from govs import GOVS
    pops = {}
    try:
        for r in json.load(open(os.path.join(PUB, 'downloads', 'government-profiles.json'))):
            pops[r.get('government')] = r.get('population_2025')
    except FileNotFoundError:
        pass
    aliases = {}
    for g in GOVS:
        cur.execute('''insert into governments (key, slug, short_name, name, kind, population_2025) values (%s,%s,%s,%s,%s,%s)
                       on conflict (key) do update set slug=excluded.slug, short_name=excluded.short_name, name=excluded.name, kind=excluded.kind,
                       population_2025=coalesce(excluded.population_2025, governments.population_2025)''',
                    (g['key'], g['slug'], g['short'], g['name'], g['kind'], pops.get(g['short'])))
        for a in {g['key'], g['short'], g['name'], g.get('fees'), g.get('tax'), g['slug'], 'City of ' + g['short'], g['short'] + ' BOCC'}:
            if a:
                aliases[a.lower()] = g['key']
    for key, slug, short, name, kind in EXTRA_GOVS:
        cur.execute('insert into governments (key, slug, short_name, name, kind) values (%s,%s,%s,%s,%s) on conflict (key) do nothing', (key, slug, short, name, kind))
        aliases[key] = key; aliases[short.lower()] = key
    aliases.update({'bay county bocc': 'county', 'bay county board of county commissioners': 'county', 'bay district school board': 'schools',
                    'school board': 'schools', 'bay county': 'county'})
    for a, k in aliases.items():
        cur.execute('insert into government_aliases (alias, government_key) values (%s,%s) on conflict (alias) do update set government_key = excluded.government_key', (a, k))
    return aliases


def gov_key(row, aliases):
    for col in ('government', 'employer_id', 'gov', 'city'):
        v = row.get(col)
        if isinstance(v, str) and v.strip():
            k = aliases.get(v.strip().lower())
            if k:
                return k
            # board names like "Lynn Haven City Commission"
            for a, kk in sorted(aliases.items(), key=lambda x: -len(x[0])):
                if len(a) > 4 and a in v.lower():
                    return kk
    b = row.get('board')
    if isinstance(b, str):
        for a, kk in sorted(aliases.items(), key=lambda x: -len(x[0])):
            if len(a) > 4 and a in b.lower():
                return kk
    return None


# Datasets that rule alerts watch (api/_rules.js). New rows in these become alerts.events.
ALERT_DATASETS = {'contracts', 'change-orders', 'member-votes', 'meetings', 'candidates-2026'}


def has_table(cur, name):
    cur.execute('select to_regclass(%s) is not null', (name,))
    return cur.fetchone()[0]


def table_columns(cur, table):
    cur.execute('select column_name, data_type from information_schema.columns where table_schema = current_schema() and table_name = %s', (table,))
    return dict(cur.fetchall())


def adapt(v, typ):
    if v is None or v == '':
        return None
    if typ == 'jsonb':
        return Jsonb(v)
    if typ in ('bigint', 'numeric'):
        try:
            return float(v) if typ == 'numeric' else int(float(v))
        except (TypeError, ValueError):
            return None
    if typ == 'boolean':
        return bool(v) if isinstance(v, bool) else str(v).lower() in ('true', '1', 'yes')
    if typ == 'date':
        return v if isinstance(v, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', v) else None
    return v if isinstance(v, str) else json.dumps(v)


def load_dataset(conn, d, aliases, sha):
    table = d['id'].replace('-', '_')
    rows = json.load(open(os.path.join(PUB, d['json'].lstrip('/'))))
    with conn.transaction():
        cur = conn.cursor()
        cols = table_columns(cur, table)
        if not cols:
            raise SystemExit(f'Table {table} is missing: add a migration for dataset "{d["id"]}".')
        missing = [c['name'] for c in d['columns'] if c['name'] not in cols]
        if missing:
            raise SystemExit(f'Dataset "{d["id"]}" has columns the table lacks: {missing}. Add a migration.')
        cur.execute("insert into ingest_runs (origin, dataset, git_sha) values ('site_build', %s, %s) returning id", (d['id'], sha))
        run = cur.fetchone()[0]
        # Compare with the previous sync by record_hash: rows whose hash is still present are kept as they are
        # (so created_at is when a record first appeared), rows that are gone are deleted, and only new hashes are
        # inserted. A record whose content changed gets a new hash, so it counts as removed + added.
        cur.execute(f"select record_hash from {table} where origin = 'site_build'")
        old = {x[0] for x in cur.fetchall()}
        names = [c['name'] for c in d['columns']]
        qcols = ', '.join('"' + n + '"' for n in names)
        sql = f'insert into {table} ({qcols}, government_key, origin, ingest_run_id, record_hash) values ({", ".join(["%s"] * (len(names) + 4))}) on conflict (origin, record_hash) do nothing'
        batch, seen, added = [], set(), []
        for r in rows:
            h = hashlib.sha1(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if h in seen:
                continue
            seen.add(h)
            if h in old:
                continue
            g = gov_key(r, aliases)
            batch.append([adapt(r.get(n), cols[n]) for n in names] + [g, 'site_build', run, h])
            added.append((h, g, r))
        cur.execute(f"delete from {table} where origin = 'site_build' and not (record_hash = any(%s))", (list(seen),))
        deleted = cur.rowcount
        cur.executemany(sql, batch)
        # Rule alerts: new rows in the datasets rules watch become alerts.events (migration 0008). Skipped on a
        # dataset's first load (everything would look new) and when the migration isn't applied.
        events = 0
        if old and d['id'] in ALERT_DATASETS and added and has_table(cur, 'alerts.events'):
            cur.executemany('insert into alerts.events (dataset, record_hash, government_key, record, ingest_run_id) values (%s,%s,%s,%s,%s)',
                            [(d['id'], h, g, Jsonb(r), run) for h, g, r in added])
            events = len(added)
        extra = ', rows_added = %s' if 'rows_added' in table_columns(cur, 'ingest_runs') else ''
        cur.execute(f"update ingest_runs set finished_at = now(), rows_in = %s, rows_deleted = %s{extra}, status = 'ok', notes = %s where id = %s",
                    (len(seen), deleted, *([len(batch)] if extra else []), f'{len(batch)} new, {len(seen) - len(batch)} unchanged' + (f', {events} alert events' if events else ''), run))
        cur.execute('update datasets set updated_at = now(), title = %s, description = %s where id = %s', (d['title'], d['description'], d['id']))
    return len(seen), deleted, len(batch), events


def load_raw(conn, sha):
    n = 0
    with conn.transaction():
        cur = conn.cursor()
        cur.execute("insert into ingest_runs (origin, dataset, git_sha) values ('site_build', 'raw_files', %s) returning id", (sha,))
        run = cur.fetchone()[0]
        cur.execute('select path, sha256 from raw_files'); have = dict(cur.fetchall())
        for fp in sorted(glob.glob(os.path.join(ROOT, 'data', '**', '*.json'), recursive=True)):
            rel = os.path.relpath(fp, ROOT); b = open(fp, 'rb').read(); h = hashlib.sha256(b).hexdigest()
            if have.get(rel) == h:
                continue
            try:
                content = json.loads(b)
            except ValueError:
                continue
            cur.execute('''insert into raw_files (path, sha256, bytes, content, ingest_run_id) values (%s,%s,%s,%s,%s)
                           on conflict (path) do update set sha256=excluded.sha256, bytes=excluded.bytes, content=excluded.content, loaded_at=now(), ingest_run_id=excluded.ingest_run_id''',
                        (rel, h, len(b), Jsonb(content), run))
            n += 1
        cur.execute("update ingest_runs set finished_at = now(), rows_in = %s, status = 'ok' where id = %s", (n, run))
    return n


def connect(url):
    """Connect, falling back to Supabase's IPv4 session pooler when given the direct (IPv6-only) address,
    since GitHub runners can't reach IPv6. Set SUPABASE_REGION (e.g. us-east-2) for the fallback."""
    try:
        return psycopg.connect(url, autocommit=True, connect_timeout=15)
    except psycopg.OperationalError as e:
        params = psycopg.conninfo.conninfo_to_dict(url)
        m = re.match(r'^db\.([a-z0-9]+)\.supabase\.co$', params.get('host') or '')
        region = os.environ.get('SUPABASE_REGION')
        if not (m and region):
            raise
        print('direct connection failed (%s); trying the session pooler' % str(e).splitlines()[0][:80])
        ref = m.group(1)
        for prefix in ('aws-1', 'aws-0'):
            p = dict(params, host=f'{prefix}-{region}.pooler.supabase.com', port='5432', user=f'{params.get("user") or "postgres"}.{ref}', connect_timeout='15')
            try:
                return psycopg.connect(psycopg.conninfo.make_conninfo(**p), autocommit=True)
            except psycopg.OperationalError as e2:
                print(f'  {prefix} pooler failed: {str(e2).splitlines()[0][:120]}')
        raise


def main():
    url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL_NON_POOLING') or os.environ.get('POSTGRES_URL')
    if not url:
        raise SystemExit('Set DATABASE_URL (Supabase: Project Settings > Database > Connection string, session pooler).')
    cat = json.load(open(os.path.join(PUB, 'downloads', 'index.json')))
    sha = git_sha()
    with connect(url) as conn:
        if '--migrate' in sys.argv:
            with conn.transaction():
                migrate(conn.cursor())
        with conn.transaction():
            aliases = seed_governments(conn.cursor())
        total = 0
        failed = []
        for d in cat['datasets']:
            try:
                n, dl, new, ev = load_dataset(conn, d, aliases, sha)
            except SystemExit:
                raise
            except psycopg.Error as e:
                # One bad dataset shouldn't stop the rest; the failure is recorded for /api/v1/status.
                msg = str(e).splitlines()[0][:300]
                print(f'{d["id"]:32s} FAILED: {msg}')
                failed.append(d['id'])
                with conn.transaction():
                    conn.cursor().execute("insert into ingest_runs (origin, dataset, git_sha, finished_at, status, notes) values ('site_build', %s, %s, now(), 'failed', %s)", (d['id'], sha, msg))
                continue
            total += n
            print(f'{d["id"]:32s} {n:6d} rows ({new} new, {dl} removed{", %d alert events" % ev if ev else ""})')
        print('raw files updated:', load_raw(conn, sha))
        print('total rows:', total)
        prune_logs(conn)
        if failed:
            raise SystemExit('datasets that failed to load: ' + ', '.join(failed))


def prune_logs(conn):
    """Delete API request-log rows older than 180 days (migration 0006). Skipped if that migration isn't applied."""
    try:
        with conn.transaction():
            cur = conn.cursor()
            cur.execute('select apiadmin.prune_requests(180)')
            print('api log rows pruned (older than 180 days):', cur.fetchone()[0])
    except psycopg.Error as e:
        print('api log prune skipped:', str(e).splitlines()[0][:120])


if __name__ == '__main__':
    main()
