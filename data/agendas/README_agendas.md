# Agenda watcher

Know within half an hour when a Bay County government posts an agenda, and keep a copy of every version.

`watch_agendas.py` has two triggers feeding one pipeline:

- **Inbox.** Notices go to `ingest@baycounty.me`, a Resend inbox. When one arrives, Resend calls `/api/agenda-inbound` (signed webhook), which starts the **Watch agendas** workflow within a minute or two. The workflow reads the email through the Resend API (the original message, attachments included), matches it to a government by its sender and links, and rescans that government's agenda system. Document links in the email and PDF attachments are captured too. The same inbox check also runs every 30 minutes on weekdays (6 a.m.–6:30 p.m. Central) as a backstop. A POP3 mailbox still works instead of, or as well as, Resend.
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

1. **Inbox.** `ingest@baycounty.me` exists in Resend (receiving is on for baycounty.me). Use a different address by setting the repository variable `AGENDA_INBOX`.
2. **Sign up.** On panamacity.gov and cityofcallaway.com, create an account with `ingest@baycounty.me` and turn on Notify Me for the Agenda Center lists (City Commission and Community Redevelopment). Add other governments' subscriptions as they're found.
3. **GitHub secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (plus the existing `DATABASE_URL`, `RESEND_FULL_KEY`, `ADMIN_EMAILS`). `RESEND_FULL_KEY` must be a full-access key, since it reads received mail.
4. **Resend webhook:** endpoint `https://baycounty.me/api/agenda-inbound`, event `email.received`. Copy its signing secret.
5. **Vercel env:** `RESEND_WEBHOOK_SECRET` (that signing secret), `SUPABASE_SERVICE_ROLE_KEY` (signs 5-minute links to stored files on /admin) and `GITHUB_DISPATCH_TOKEN` (fine-grained token, Actions: write on this repo; powers both the webhook's instant run and the **Run now** button). Without the token, notices are still picked up by the 30-minute check.
6. The next database sync applies `db/migrations/0012_agenda_inbox.sql`. Then run **Watch agendas** from the Actions tab with mode `sweep` once to load the current documents.

**POP3 instead (optional).** Set `POP_HOST`, `POP_USER`, `POP_PASS` secrets (port 995, TLS) and optionally the variable `POP_DELETE=1`. Microsoft 365 / Exchange Online doesn't allow POP3 with a password.

## Run it locally

```
python3 data/agendas/watch_agendas.py --sweep --only pc,cw --dry-run   # no database, prints what it finds
RESEND_KEY=re_... python3 data/agendas/watch_agendas.py --inbox --dry-run   # read the Resend inbox, no database
DATABASE_URL=... python3 data/agendas/watch_agendas.py --inbox --sweep
python3 -m unittest discover data/agendas/tests
```

Limits: `AGENDA_MAX_DOWNLOADS` (default 150 per run), files over 80 MB are skipped, and sweeps skip files checked in the last `AGENDA_RECHECK_HOURS` (default 6) unless an email just pointed at that government. HTML agendas are hashed on their visible text, so markup that changes on every load doesn't count as an amendment. AgendaCenter's `?html=true` agendas are captured as the PDF.

## Tables

`agendas.notices` (emails; `uidl` is `resend:<email id>` for Resend mail, the POP3 UIDL otherwise), `agendas.documents` (one per URL, current hash and status), `agendas.versions` (every distinct content, with its Storage path), `agendas.errors` (inbox, parse, scan, download, store and notify problems). Each run logs one `ingest_runs` row with origin `scraper:agendas`. Admin-only: row-level security is on with no public read policy.
