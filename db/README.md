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

`.github/workflows/sync-db.yml` runs `db/scripts/load.py --migrate` after every push to `main` that touches data, when a refresh workflow starts it after pushing, or by hand from the Actions tab. It needs the `DATABASE_URL` repository secret (Supabase > Connect > Session pooler URI).

Run it locally:

```
pip install 'psycopg[binary]'
python3 site/build_site.py > /dev/null
DATABASE_URL=postgresql://... python3 db/scripts/load.py --migrate
```

## Adding data

**Rule:** every page's data lives here and is served by `/api/v1`. A new page means a new dataset, a migration for its
table and an entry in `api/_pages.js` (the API test fails otherwise). See `CLAUDE.md` at the repo root.

1. **A few records:** open the table in Supabase and add rows. Leave `origin` as `manual`, fill `source_url`, and set `record_hash` to anything unique (e.g. the source URL plus a row number).
2. **A spreadsheet:** Supabase table editor > Import data from CSV, into the matching table. Same `origin` and `record_hash` rules.
3. **A recurring source:** write a script that inserts with `origin = 'scraper:<name>'`, logs an `ingest_runs` row, and upserts on `(origin, record_hash)`.
4. **A new kind of data:** add a numbered migration (the next number, e.g. `db/migrations/0005_<name>.sql`) that creates the table with the same standard columns, enables RLS and adds the public read policy. Never edit `0001_init.sql`.

If a site dataset gains a column, the sync fails with a message naming it: add a migration with `alter table ... add column`.

**How migrations reach production:** the Sync database workflow runs `load.py --migrate` after every push to main that touches `data/`, `db/` or the downloads. It applies every `db/migrations/*.sql` file not yet in `schema_migrations`, in filename order, all in one transaction. Files must be named `NNNN_short_name.sql` with a number nobody else has used; the Checks workflow (`db/scripts/check_migrations.py`) applies the whole chain to an empty Postgres on every pull request and fails on a bad name, a reused number or a migration that errors.

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

## Ingestion alerts for admins

- **Workflows:** each ingestion workflow (`refresh-meetings`, `refresh-weekly`, `sync-db`) ends with
  `.github/scripts/notify_admins.py`, which emails the admins when the job or any step failed (including steps with
  `continue-on-error`) or a step reported an `alert` output (e.g. a missing `DATABASE_URL`). Repeat meeting-source errors
  only comment on the open issue and don't email again. Needs repository secrets `RESEND_FULL_KEY` and `ADMIN_EMAILS`.
- **Daily check:** `/api/alerts-run` first runs `api/_health.js` against `ingest_runs` and the `alerts` tables, and emails
  `ADMIN_EMAILS` (Vercel) only when a dataset's latest load failed or is stuck, there's been no successful sync in
  `INGEST_STALE_HOURS` (default 36), alert emails failed, or new records sat unprocessed for 2 days.
  `GET /api/alerts-run?health=1` with the `CRON_SECRET` runs just the check.
- **/admin:** the Ingestion tab shows the same report; the Emails tab previews every subscriber email (built by the same
  code that sends them, `api/_emails.js`) and can send a test to the signed-in admin.

## Secrets and settings

Where each secret lives. Values are never committed.

| Name | Where | Used by |
|---|---|---|
| `DATABASE_URL` | GitHub secret, Vercel env | sync-db, watch-agendas, refresh-meetings (agenda export), API |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | GitHub secret | watch-agendas (file storage) |
| `RESEND_FULL_KEY` | GitHub secret | admin emails from every workflow; watch-agendas reads the agenda inbox |
| `ADMIN_EMAILS` | GitHub secret | who gets workflow problem emails |
| `OWNER_ID_KEY` | GitHub secret | keys public business-owner ids (`owner:o_…`) so they can't be traced to an address; never change it (every owner profile link would change) |
| `VERCEL_DEPLOY_HOOK` | GitHub secret | refresh workflows deploy bot commits (Vercel skips Git deploys by non-members) |
| `ANTHROPIC_API_KEY` | GitHub secret | watch-agendas reads posted agendas into items |
| `POP_HOST`, `POP_USER`, `POP_PASS` | GitHub secret (optional) | a POP3 agenda mailbox |
| `SUPABASE_REGION`, `AGENDA_INBOX`, `AGENDA_MODEL`, `AGENDA_EXTRACT_MAX`, `AGENDA_EXTRACT_BUDGET_USD`, `ANTHROPIC_WORKSPACE_ID`, `POP_DELETE` | GitHub variables | workflow settings |
| `CRON_SECRET` | Vercel env | `/api/digest` and `/api/alerts-run` crons |
| `ALERTS_SECRET` | Vercel env | signs alert subscribe/manage links |
| `FINANCE_HASH_SECRET` | Vercel env | /finance sign-in hashing |
| `GITHUB_DISPATCH_TOKEN` | Vercel env | `api/agenda-inbound.js` starts watch-agendas |
| `RESEND_WEBHOOK_SECRET` | Vercel env | verifies the Resend inbound webhook |
| `DIGEST_REVIEWER`, `DIGEST_AUTOSEND`, `ALERTS_AUTOSEND` | Vercel env | weekly digest and alert sending |

`load.py` refuses a sync that would empty a dataset, or drop more than 60% of a dataset with 100+ rows, and logs it
as failed. If the drop is real, run the Sync database workflow by hand and put the dataset id in its `allow_shrink` box.
