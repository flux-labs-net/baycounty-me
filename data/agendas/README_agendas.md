# Agenda watcher

Know within half an hour when a Bay County government posts an agenda, and keep a copy of every version.

`watch_agendas.py` has two triggers feeding one pipeline:

- **Inbox (every 30 min, weekdays 6 a.m.–6:30 p.m. Central).** Polls a mailbox over POP3/TLS. Each notice email is matched to a government by its sender and links, and that government's agenda system is rescanned right away. Document links in the email and PDF attachments are captured too.
- **Sweep (7 a.m. and 5 p.m. daily).** Rescans every source without waiting for email, which covers boards that send no notices.

Every agenda, packet and minutes file found is downloaded and hashed. A new URL is **new**; the same URL with different content is **updated** (an amended agenda) and gets a new version; otherwise **unchanged**. Files go to Supabase Storage (private bucket `agendas`). New or updated files email the admins and trigger the meetings refresh so the site updates. Everything shows on **/admin → Agendas**: documents and every version (open any version), inbox emails with their text, links and attachments, errors (resolve them there), and runs.

The website account is only for receiving notices. Downloads need no login: AgendaCenter, CivicClerk, PrimeGov and Granicus files are public.

## Which sources send notices

| Key | Government | Agenda system | Email notice option |
|---|---|---|---|
| `pc` | Panama City (+ CRA) | CivicPlus AgendaCenter | AgendaCenter **Notify Me** (needs a site account) |
| `cw` | Callaway (+ CRA) | CivicPlus AgendaCenter | AgendaCenter **Notify Me** (needs a site account) |
| `lh` | Lynn Haven (+ CRA) | CivicClerk | Check the portal's subscribe option |
| `county` | Bay County BOCC | PrimeGov | Check the portal; sweep covers it either way |
| `pcb` | Panama City Beach | Granicus | Sweep |
| `sp`, `parker`, `mb` | Springfield, Parker, Mexico Beach | Own web pages | Sweep |

Unknown senders are matched by government names in the subject and body; anything still unmatched shows on the admin tab as **Unmatched**.

## Setup

1. **Mailbox.** A dedicated address (for example `agendas@…`) with POP3 over TLS turned on. Microsoft 365 / Exchange Online does not allow POP3 with a password (basic auth is off), so use a mailbox host that does, or forward the notices into one that does.
2. **Sign up.** On panamacity.gov and cityofcallaway.com, create an account with that address and turn on Notify Me for the Agenda Center lists (City Commission and Community Redevelopment). Add other governments' subscriptions as they're found.
3. **GitHub secrets:** `POP_HOST`, `POP_USER`, `POP_PASS`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (plus the existing `DATABASE_URL`, `RESEND_FULL_KEY`, `ADMIN_EMAILS`). Optional repository variable `POP_DELETE=1` to delete mail once recorded (otherwise it stays on the server and is skipped by its POP3 UIDL).
4. **Vercel env:** `SUPABASE_SERVICE_ROLE_KEY` (signs 5-minute links to stored files on /admin). Optional `GITHUB_DISPATCH_TOKEN` (fine-grained token, Actions: write on this repo) enables the **Run now** button.
5. The next database sync applies `db/migrations/0012_agenda_inbox.sql`. Then run **Watch agendas** from the Actions tab with mode `sweep` once to load the current documents.

## Run it locally

```
python3 data/agendas/watch_agendas.py --sweep --only pc,cw --dry-run   # no database, prints what it finds
DATABASE_URL=... python3 data/agendas/watch_agendas.py --inbox --sweep
python3 -m unittest discover data/agendas/tests
```

Limits: `AGENDA_MAX_DOWNLOADS` (default 150 per run), files over 80 MB are skipped, and sweeps skip files checked in the last `AGENDA_RECHECK_HOURS` (default 6) unless an email just pointed at that government. HTML agendas are hashed on their visible text, so markup that changes on every load doesn't count as an amendment. AgendaCenter's `?html=true` agendas are captured as the PDF.

## Tables

`agendas.notices` (emails), `agendas.documents` (one per URL, current hash and status), `agendas.versions` (every distinct content, with its Storage path), `agendas.errors` (inbox, parse, scan, download, store and notify problems). Each run logs one `ingest_runs` row with origin `scraper:agendas`. Admin-only: row-level security is on with no public read policy.
