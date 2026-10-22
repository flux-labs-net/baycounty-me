# BayCounty.me database

Postgres (Supabase) copy of every public dataset, built so new data can be added without editing JSON by hand.

## Layout

| Table | What it holds |
|---|---|
| `governments`, `government_aliases` | The 9 local governments plus `constitutional` and `special`; aliases map source spellings ("Bay County BOCC") to a key |
| one table per dataset (`votes`, `contracts`, `salary_positions`, ...) | Same columns as the API dataset, plus `government_key`, `origin`, `ingest_run_id`, `record_hash`, timestamps |
| `raw_files` | Lossless JSON copy of every `data/**/*.json` research file |
| `ingest_runs` | One row per load: origin, dataset, rows in/deleted, git sha, status |
| `sources` | Source documents (URL, publisher, type, date retrieved) for new ingestion work |
| `datasets` | Dataset id to table name, title, description |

Every table has row-level security with a public read policy. Writes need the service role or a direct database connection.

## The `origin` column

- `site_build`: loaded from the site's published datasets. **Replaced on every sync.**
- `manual`: the default. Rows typed in the Supabase table editor or imported from CSV.
- `scraper:<name>` or `import:<file>`: rows written by an ingestion script.

The loader only deletes and reloads `site_build` rows, so anything else you add stays put. `unique (origin, record_hash)` stops a scraper from inserting the same record twice; set `record_hash` to a stable hash of the source record.

## Sync

`.github/workflows/sync-db.yml` runs `db/scripts/load.py --migrate` after every push to `main` that touches data, after the daily refresh, or by hand from the Actions tab. It needs the `DATABASE_URL` repository secret (Supabase > Connect > Session pooler URI).

Run it locally:

```
pip install 'psycopg[binary]'
python3 site/build_site.py > /dev/null
DATABASE_URL=postgresql://... python3 db/scripts/load.py --migrate
```

## Adding data

1. **A few records:** open the table in Supabase and add rows. Leave `origin` as `manual`, fill `source_url`, and set `record_hash` to anything unique (e.g. the source URL plus a row number).
2. **A spreadsheet:** Supabase table editor > Import data from CSV, into the matching table. Same `origin` and `record_hash` rules.
3. **A recurring source:** write a script that inserts with `origin = 'scraper:<name>'`, logs an `ingest_runs` row, and upserts on `(origin, record_hash)`.
4. **A new kind of data:** add a numbered migration (the next number, e.g. `db/migrations/0005_<name>.sql`) that creates the table with the same standard columns, enables RLS and adds the public read policy. Never edit `0001_init.sql`.

If a site dataset gains a column, the sync fails with a message naming it: add a migration with `alter table ... add column`.

## Privacy

The same rules as the site apply: individual campaign donors and rank-and-file employees are never stored by name. Only elected officials and top leaders are named in salary data.

## Who reads it

The API (`/api/v1`) and the MCP server read dataset rows from the database through Supabase's public read-only API (`api/_data.js`), cached for five minutes. If the database can't be reached they fall back to the published `/downloads` files, and `meta.data_source` says which was used. Set `API_SOURCE=files` in Vercel to force the files. The static site pages are still built from the JSON in `data/`.

## Server-side connection and TLS

The Vercel functions that handle API keys, throttles, logs, admin and rule alerts connect with `DATABASE_URL` (`api/_db.js`).
The connection is always encrypted. To also **verify** the server's certificate, set `SUPABASE_CA_CERT` in Vercel to the
PEM text of Supabase's CA certificate (Supabase dashboard > Project Settings > Database > SSL configuration > Download certificate).
Paste the file as-is, or with literal `\n` for line breaks. Without it, the code falls back to encrypting without checking
the certificate (the previous behavior). After setting it, check `/admin` still loads; if it fails with a certificate error,
the pooler host doesn't match the certificate, so remove the variable and report it.

## Change tracking and rule alerts (migration 0008)

From 0008 on, the loader compares each dataset with the previous sync by `record_hash`: unchanged rows stay as they
are (so `created_at` is when a record first appeared, which `/api/v1/changes` reads), rows that disappeared are deleted,
and only new hashes are inserted. A record whose content changed gets a new hash, so it shows up as new.
`ingest_runs.rows_added` and `notes` record the counts; a dataset that fails to load gets a `failed` row and the sync
continues with the next dataset, then exits non-zero.

New rows in `contracts`, `change-orders`, `member-votes`, `meetings` and `candidates-2026` are also written to
`alerts.events` (skipped on a dataset's very first load). The daily `/api/alerts-run` cron matches them against
confirmed rules in `alerts.subscriptions`, records each match in `alerts.deliveries` (never sent twice), and writes one
email per subscriber to `alerts.outbox`: drafts for review unless `ALERTS_AUTOSEND=1`. Everything in the `alerts`
schema is private (not exposed by Supabase's data API).

## API log retention

Migration `0006` adds `apiadmin.prune_requests(days)`, which deletes `apiadmin.requests` rows older than 180 days.
It runs automatically now and then from `check_request` (about one request in a thousand), and after every database
sync (`db/scripts/load.py` calls it at the end). Raw IP addresses are cleared from log rows after 90 days, as before.
Run it by hand with `select apiadmin.prune_requests(180);`.
