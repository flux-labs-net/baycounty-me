#!/usr/bin/env python3
"""
watch_agendas.py - know when an agenda is posted, and capture the files.

Two triggers, one pipeline:

  --inbox   Poll a mailbox over POP3 (TLS). Each notice email (CivicPlus AgendaCenter "Notify Me", CivicClerk
            subscriptions, or anything forwarded there) is matched to a source by its sender and links, and that
            source is rescanned right away. Links in the email that point straight at a document, and PDF
            attachments, are captured too.
  --sweep   Rescan every source on its own (no email needed). Catches boards with no notification list and
            anything the inbox missed. Run it a few times a day.

For every agenda / packet / minutes URL found, the file is downloaded and hashed (SHA-256). New URL = "new".
Same URL with different content = "updated" (an amended agenda) and a new version. Same content = "unchanged".
Files are stored in Supabase Storage (bucket "agendas") when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set.
Everything is recorded in the agendas.* tables (db/migrations/0012_agenda_inbox.sql) and one ingest_runs row,
which the /admin "Agendas" tab reads. The download itself never needs a login: the files are public; the website
account only exists to receive the notice emails.

Environment:
  DATABASE_URL                     Postgres (Supabase). Required unless --dry-run.
  POP_HOST, POP_USER, POP_PASS     mailbox (port POP_PORT, default 995, TLS). Needed for --inbox.
  POP_DELETE=1                     delete messages from the server once recorded (default: leave them; UIDL dedupes)
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   store files in Storage (optional)
  RESEND_KEY, ADMIN_EMAILS         email the admins a summary when new or updated documents land (optional)
  AGENDA_MAX_DOWNLOADS             cap per run (default 150); packets can be large

Usage:
  python3 data/agendas/watch_agendas.py --inbox            # the frequent run
  python3 data/agendas/watch_agendas.py --sweep            # all sources
  python3 data/agendas/watch_agendas.py --sweep --only pc,cw --dry-run   # print what it would do, no DB
Standard library only, plus psycopg when writing to the database.
"""

import datetime as dt
import email
import email.policy
import email.utils
import hashlib
import json
import os
import poplib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "meetings"))
import fetch_meetings as fm  # noqa: E402  (reuses the per-board source adapters)

MAX_BYTES = 80 * 1024 * 1024
MAX_DOWNLOADS = int(os.environ.get("AGENDA_MAX_DOWNLOADS") or 150)
RECHECK_HOURS = float(os.environ.get("AGENDA_RECHECK_HOURS") or 6)  # sweeps skip files checked more recently
BUCKET = "agendas"
DOC_URL = re.compile(r"AgendaCenter/ViewFile|GetMeetingFileStream|CompiledDocument|/media/\d+|\.pdf(\?|$)|"
                     r"MetaViewer\.php|AgendaViewer\.php", re.I)

# ---------------------------------------------------------------------------------------------------------------
# Sources: key -> (hosts that identify it, scan function returning fetch_meetings meeting dicts)


def _ac(host, cat_map):
    def scan(today):
        r = fm.src_agendacenter(host, today, 60, cat_map)
        return [m for lst in r.values() for m in lst]
    return scan


def _flat(fn):
    def scan(today):
        r = fn(today)
        return [m for lst in r.values() for m in lst] if isinstance(r, dict) else (r or [])
    return scan


SOURCES = {
    "pc": (["panamacity.gov"], _ac("www.panamacity.gov", [(r"community redevelopment|\bCRA\b", "pc-cra"),
                                                          (r"city commission|budget hearing|public workshop", "pc")])),
    "cw": (["cityofcallaway.com"], _ac("www.cityofcallaway.com", [(r"community redevelopment|\bCRA\b", "cw-cra"),
                                                                  (r"commission", "cw")])),
    "lh": (["cityoflynnhaven.gov", "cityoflynnhaven.com", "lynnhavenfl.portal.civicclerk.com", "lynnhavenfl.api.civicclerk.com"],
           _flat(lambda today: fm.src_civicclerk_lh(today, 60))),
    "county": (["baycountyfl.gov", "baycountyfl.primegov.com"], _flat(lambda today: fm.src_primegov_bocc("county", today))),
    "pcb": (["pcbfl.gov", "pcbgov.granicus.com"], _flat(lambda today: fm.src_granicus_pcb())),
    "sp": (["springfieldfl.net"], _flat(lambda today: fm.src_springfield())),
    "parker": (["cityofparker.com"], _flat(lambda today: fm.src_parker())),
    "mb": (["mexicobeachfl.gov"], _flat(lambda today: fm.src_mexico_beach(today))),
}
GOV_OF_BOARD = {b["id"]: b.get("gov") for b in fm.BOARDS}


def host_of(url):
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def source_for_host(host):
    host = (host or "").lower()
    for key, (hosts, _) in SOURCES.items():
        if any(host == h or host.endswith("." + h) for h in hosts):
            return key
    # CivicPlus sends Notify Me mail from its own domain; the sender name/links decide then.
    return None


# ---------------------------------------------------------------------------------------------------------------
# Email parsing (pure, unit-testable)

URL_RE = re.compile(r"""https?://[^\s<>"')\]]+""", re.I)


def parse_email(raw_bytes):
    """-> dict(message_id, received_at, from_addr, subject, body_text, links, attachments[{filename, content_type, data}])"""
    msg = email.message_from_bytes(raw_bytes, policy=email.policy.default)
    texts, htmls, atts = [], [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        fn = part.get_filename()
        disp = (part.get_content_disposition() or "").lower()
        if fn or disp == "attachment":
            try:
                data = part.get_payload(decode=True) or b""
            except Exception:
                data = b""
            atts.append({"filename": fn or "attachment", "content_type": ctype, "data": data})
        elif ctype == "text/plain":
            texts.append(_content(part))
        elif ctype == "text/html":
            htmls.append(_content(part))
    html_all = "\n".join(htmls)
    hrefs = [fm.html.unescape(h) for h in re.findall(r"""href\s*=\s*["']([^"']+)["']""", html_all, re.I)]
    body = "\n".join(texts) or fm.strip_tags(html_all, sep="\n")
    links = []
    for u in hrefs + URL_RE.findall(body) + URL_RE.findall(fm.strip_tags(html_all, sep=" ")):
        u = u.strip().rstrip(".,;")
        if u.lower().startswith("http") and u not in links:
            links.append(u)
    try:
        received = email.utils.parsedate_to_datetime(msg["Date"]).isoformat() if msg["Date"] else None
    except Exception:
        received = None
    return {"message_id": (msg["Message-ID"] or "").strip() or None, "received_at": received,
            "from_addr": str(msg["From"] or ""), "subject": str(msg["Subject"] or ""),
            "body_text": re.sub(r"\n{3,}", "\n\n", body).strip()[:20000], "links": links, "attachments": atts}


def _content(part):
    try:
        return part.get_content()
    except Exception:
        return (part.get_payload(decode=True) or b"").decode("utf-8", "replace")


def classify(parsed):
    """Which sources does this notice point at? -> (sorted source keys, direct document links)."""
    keys = set()
    for u in parsed["links"]:
        k = source_for_host(host_of(u))
        if k:
            keys.add(k)
    addr = email.utils.parseaddr(parsed["from_addr"])[1]
    k = source_for_host(addr.split("@")[-1]) if "@" in addr else None
    if k:
        keys.add(k)
    if not keys:  # e.g. a CivicPlus relay address: fall back to names in the sender/subject/body
        hay = " ".join([parsed["from_addr"], parsed["subject"], parsed["body_text"][:2000]]).lower()
        for k, words in {"pc": ["panama city, fl", "city of panama city", "panamacity"], "cw": ["callaway"],
                         "lh": ["lynn haven"], "county": ["bay county"], "pcb": ["panama city beach"],
                         "sp": ["springfield"], "parker": ["city of parker"], "mb": ["mexico beach"]}.items():
            if any(w in hay for w in words):
                keys.add(k)
        if "pcb" in keys:
            keys.discard("pc")
    docs = [u for u in parsed["links"] if DOC_URL.search(u) and source_for_host(host_of(u))]
    return sorted(keys), docs


# ---------------------------------------------------------------------------------------------------------------
# Network


def download(url, tries=3):
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": fm.UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("file is larger than %d MB" % (MAX_BYTES // 1048576))
                return data, (r.headers.get_content_type() or "application/octet-stream"), r.geturl()
        except ValueError:
            raise
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # reset, timeout, TLS
            last = e
        fm.time.sleep(2 * (attempt + 1))
    raise RuntimeError("%s: %s" % (type(last).__name__, last))


def canonical(url):
    """AgendaCenter serves the same agenda as HTML (?html=true) and PDF (no query); keep the PDF."""
    if url and "AgendaCenter/ViewFile" in url and "html=true" in url:
        return url.split("?", 1)[0]
    return url


def fingerprint(data, ctype):
    """SHA-256 of the content. HTML pages are hashed on their visible text, so a changing session token or
    timestamp in the markup doesn't look like an amended agenda."""
    if ctype == "text/html":
        t = fm.strip_tags(data.decode("utf-8", "replace"), sep=" ")
        t = re.sub(r"\s+", " ", t).strip()
        return hashlib.sha256(t.encode()).hexdigest()
    return hashlib.sha256(data).hexdigest()


def file_name(url, ctype):
    q = urllib.parse.urlsplit(url)
    base = os.path.basename(q.path) or "file"
    if "fileId=" in url:
        base = "file-" + re.search(r"fileId=(\d+)", url).group(1)
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base)[:80].strip("-") or "file"
    if "." not in base[-6:]:
        base += {"application/pdf": ".pdf", "text/html": ".html"}.get(ctype, "")
    return base


class Storage:
    def __init__(self):
        self.url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        self.ready = False

    @property
    def on(self):
        return bool(self.url and self.key)

    def _req(self, method, path, data=None, ctype="application/json", extra=None):
        h = {"Authorization": "Bearer " + self.key, "apikey": self.key, "Content-Type": ctype}
        h.update(extra or {})
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=h)
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()

    def put(self, path, data, ctype):
        if not self.ready:
            try:
                self._req("POST", "/storage/v1/bucket", json.dumps({"id": BUCKET, "name": BUCKET, "public": False}).encode())
            except urllib.error.HTTPError as e:
                if e.code not in (400, 409):  # 400/409: already exists
                    raise
            self.ready = True
        self._req("POST", "/storage/v1/object/%s/%s" % (BUCKET, urllib.parse.quote(path)), data, ctype or "application/octet-stream",
                  {"x-upsert": "true"})
        return path


# ---------------------------------------------------------------------------------------------------------------
# Database (thin wrapper so --dry-run works without psycopg)


class DB:
    def __init__(self, url, dry):
        self.dry = dry or not url
        self.conn = None
        if not self.dry:
            sys.path.insert(0, os.path.join(HERE, "..", "..", "db", "scripts"))
            from load import connect  # same IPv4-pooler fallback the daily sync uses
            self.conn = connect(url)

    def one(self, sql, args=()):
        if self.dry:
            return None
        with self.conn.cursor() as c:
            c.execute(sql, args)
            return c.fetchone() if c.description else None

    def j(self, v):
        from psycopg.types.json import Jsonb
        return Jsonb(v)


# ---------------------------------------------------------------------------------------------------------------


class Run:
    def __init__(self, db, storage):
        self.db, self.storage = db, storage
        self.run_id = None
        self.counts = {"notices": 0, "new": 0, "updated": 0, "unchanged": 0, "failed": 0, "errors": 0}
        self.fresh = []      # [(status, doc dict)] for the summary email
        self.downloads = 0
        self.seen_urls = set()
        self.force = False   # True while rescanning a source an email just pointed at

    def error(self, stage, message, source_key=None, url=None, notice_id=None, document_id=None):
        self.counts["errors"] += 1
        print("  ! %s %s %s: %s" % (stage, source_key or "", url or "", message), file=sys.stderr)
        self.db.one("insert into agendas.errors (stage, source_key, url, message, notice_id, document_id, ingest_run_id) "
                    "values (%s,%s,%s,%s,%s,%s,%s)", (stage, source_key, url, str(message)[:1000], notice_id, document_id, self.run_id))

    # --- documents -------------------------------------------------------------------------------------------
    def capture(self, url, source_key, kind, board=None, title=None, meeting_date=None, notice_id=None, data=None, ctype=None):
        url = canonical(url)
        if not url or url in self.seen_urls:
            return
        self.seen_urls.add(url)
        row = self.db.one("select id, current_sha256, version_count, last_checked_at > now() - make_interval(secs => %s) "
                          "from agendas.documents where url = %s", (RECHECK_HOURS * 3600, url))
        if row and row[3] and row[1] and not self.force and data is None:
            return  # checked recently and nothing asked for a recheck
        if not row:
            row = self.db.one("""insert into agendas.documents (url, source_key, board, government_key, kind, title, meeting_date, notice_id)
                values (%s,%s,%s,%s,%s,%s,%s,%s) returning id, current_sha256, version_count""",
                              (url, source_key, board, GOV_OF_BOARD.get(board), kind, title, meeting_date, notice_id))
        elif title or meeting_date:
            self.db.one("update agendas.documents set title = coalesce(%s, title), meeting_date = coalesce(%s, meeting_date), "
                        "board = coalesce(board, %s) where id = %s", (title, meeting_date, board, row[0]))
        doc_id, old_sha = (row[0], row[1]) if row else (None, None)
        if data is None:
            if self.downloads >= MAX_DOWNLOADS:
                return
            self.downloads += 1
            try:
                data, ctype, _final = download(url)
            except Exception as e:
                self.counts["failed"] += 1
                self.db.one("update agendas.documents set status = 'failed', error = %s, last_checked_at = now() where id = %s",
                            (str(e)[:500], doc_id))
                self.error("download", e, source_key, url, notice_id, doc_id)
                return
        sha = fingerprint(data, ctype)
        info = {"url": url, "source": source_key, "board": board, "kind": kind, "title": title,
                "meeting_date": str(meeting_date) if meeting_date else None, "bytes": len(data)}
        if sha == old_sha:
            self.counts["unchanged"] += 1
            self.db.one("update agendas.documents set status = 'unchanged', error = null, last_checked_at = now() where id = %s", (doc_id,))
            return
        status = "updated" if old_sha else "new"
        path = None
        if self.storage.on:
            gov = GOV_OF_BOARD.get(board) or source_key
            path = "%s/%s/%s-%s" % (gov, meeting_date or dt.date.today(), sha[:12], file_name(url, ctype))
            try:
                self.storage.put(path, data, ctype)
            except Exception as e:
                path = None
                self.error("store", e, source_key, url, notice_id, doc_id)
        self.db.one("insert into agendas.versions (document_id, sha256, bytes, content_type, storage_path, ingest_run_id) "
                    "values (%s,%s,%s,%s,%s,%s) on conflict (document_id, sha256) do nothing",
                    (doc_id, sha, len(data), ctype, path, self.run_id))
        self.db.one("""update agendas.documents set status = %s, error = null, current_sha256 = %s, content_type = %s, bytes = %s,
                last_checked_at = now(), last_changed_at = now(), version_count = version_count + 1 where id = %s""",
                    (status, sha, ctype, len(data), doc_id))
        self.counts[status] += 1
        self.fresh.append((status, info))
        print("  %-8s %-7s %s %s" % (status, kind, board or source_key, title or url))

    def scan(self, key, notice_id=None):
        today = fm.now_central().date()
        try:
            meetings = SOURCES[key][1](today)
        except Exception as e:
            self.error("scan", e, key, None, notice_id)
            return 0
        for e in fm.ERRORS:  # adapters record their own failures instead of raising
            self.error("scan", "%s: %s" % (e.get("source"), e.get("error")), key, e.get("url"), notice_id)
        del fm.ERRORS[:]
        n = 0
        for m in meetings:
            for kind, field in (("agenda", "agenda_url"), ("packet", "packet_url"), ("minutes", "minutes_url")):
                u = m.get(field)
                if u and not m.get("expected"):
                    n += 1
                    self.capture(u, key, kind, m.get("board"), m.get("title"), m.get("date"), notice_id)
        print("scanned %s: %d meetings, %d document links" % (key, len(meetings), n))
        return n

    # --- inbox -----------------------------------------------------------------------------------------------
    def inbox(self):
        host, user, pw = os.environ.get("POP_HOST"), os.environ.get("POP_USER"), os.environ.get("POP_PASS")
        if not (host and user and pw):
            self.error("inbox", "POP_HOST, POP_USER and POP_PASS must be set for --inbox")
            return set()
        try:
            box = poplib.POP3_SSL(host, int(os.environ.get("POP_PORT") or 995), timeout=60)
            box.user(user)
            box.pass_(pw)
        except Exception as e:
            self.error("inbox", "could not sign in to %s: %s" % (host, e))
            return set()
        triggered = set()
        try:
            uidls = {}
            for line in box.uidl()[1]:
                num, uid = line.decode().split(None, 1)
                uidls[int(num)] = uid.strip()
            print("inbox: %d message(s) on the server" % len(uidls))
            for num, uid in sorted(uidls.items()):
                if self.db.one("select 1 from agendas.notices where uidl = %s", (uid,)):
                    self._maybe_delete(box, num)
                    continue
                try:
                    raw = b"\r\n".join(box.retr(num)[1])
                    keys = self.notice(uid, raw)
                    triggered |= keys
                    self._maybe_delete(box, num)
                except Exception as e:
                    self.error("parse", "message %s: %s" % (uid, e))
        finally:
            try:
                box.quit()  # commits deletions
            except Exception:
                pass
        return triggered

    def _maybe_delete(self, box, num):
        if os.environ.get("POP_DELETE") == "1" and not self.db.dry:
            box.dele(num)

    def notice(self, uid, raw):
        p = parse_email(raw)
        keys, docs = classify(p)
        if p["message_id"] and self.db.one("select 1 from agendas.notices where message_id = %s", (p["message_id"],)):
            return set()
        self.counts["notices"] += 1
        atts = [{"filename": a["filename"], "content_type": a["content_type"], "bytes": len(a["data"]),
                 "sha256": hashlib.sha256(a["data"]).hexdigest()} for a in p["attachments"]]
        status = "processed" if (keys or docs or atts) else "unmatched"
        row = self.db.one("""insert into agendas.notices (uidl, message_id, received_at, from_addr, subject, body_text, links, attachments,
                sources, status, ingest_run_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id""",
                          (uid, p["message_id"], p["received_at"], p["from_addr"][:300], p["subject"][:500], p["body_text"],
                           self.db.j(p["links"][:200]) if not self.db.dry else None,
                           self.db.j(atts) if not self.db.dry else None, self.db.j(keys) if not self.db.dry else None,
                           status, self.run_id))
        nid = row[0] if row else None
        print("notice: %r from %s -> %s (%d doc links, %d attachments)" % (p["subject"][:80], p["from_addr"][:60], keys or "unmatched",
                                                                        len(docs), len(atts)))
        for u in docs:
            self.capture(u, source_for_host(host_of(u)) or "email", "linked", notice_id=nid)
        for a in p["attachments"]:
            if a["data"] and (a["content_type"] == "application/pdf" or a["filename"].lower().endswith(".pdf")):
                sha = hashlib.sha256(a["data"]).hexdigest()
                self.capture("email-attachment:%s/%s" % (sha, a["filename"]), (keys[0] if keys else "email"), "attachment",
                             title=a["filename"], notice_id=nid, data=a["data"], ctype="application/pdf")
        return set(keys)

    # --- bookkeeping -----------------------------------------------------------------------------------------
    def start(self, mode):
        r = self.db.one("insert into ingest_runs (origin, dataset, notes) values ('scraper:agendas', 'agenda_documents', %s) returning id",
                        ("mode: " + mode,))
        self.run_id = r[0] if r else None

    def finish(self, fatal=None):
        c = self.counts
        notes = "%d notice(s); %d new, %d updated, %d unchanged, %d failed downloads; %d error(s)" % (
            c["notices"], c["new"], c["updated"], c["unchanged"], c["failed"], c["errors"])
        if fatal:
            notes = "FAILED: %s | %s" % (fatal, notes)
        has_cols = self.db.one("select 1 from information_schema.columns where table_name = 'ingest_runs' and column_name = 'rows_added'")
        extra = ", rows_added = %d" % (c["new"] + c["updated"]) if has_cols else ""
        self.db.one("update ingest_runs set finished_at = now(), rows_in = %%s, status = %%s, notes = %%s%s where id = %%s" % extra,
                    (c["new"] + c["updated"] + c["unchanged"], "failed" if fatal else "ok", notes, self.run_id))
        print(notes)
        return notes


def notify(run):
    key, to = os.environ.get("RESEND_KEY"), os.environ.get("ADMIN_EMAILS") or "hello@fluxlabs.net"
    if not (key and run.fresh):
        return
    rows = sorted(run.fresh, key=lambda x: (x[1]["board"] or "", x[1]["meeting_date"] or ""))
    lines = ["%s: %s %s%s (%s)" % ("NEW" if s == "new" else "UPDATED", d["board"] or d["source"], d["kind"],
                                   " for " + d["meeting_date"] if d["meeting_date"] else "", d["title"] or "") + "\n  " + d["url"]
             for s, d in rows]
    n_new = sum(1 for s, _ in rows if s == "new")
    subject = "BayCounty.me agendas: %d new, %d updated" % (n_new, len(rows) - n_new)
    text = "\n".join(lines) + "\n\nReview them on https://baycounty.me/admin (Agendas tab).\n"
    html = "<p>" + "</p><p>".join(fm.html.escape(l).replace("\n  ", "<br>") for l in lines) + \
        '</p><p><a href="https://baycounty.me/admin">Open the Agendas tab</a></p>'
    body = json.dumps({"from": os.environ.get("ALERTS_FROM") or "BayCounty.me <hello@baycounty.me>",
                       "to": [a for a in re.split(r"[\s,;]+", to) if a], "subject": subject, "text": text, "html": html}).encode()
    req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception as e:
        run.error("notify", e)


def main(argv):
    dry = "--dry-run" in argv
    do_inbox, do_sweep = "--inbox" in argv, "--sweep" in argv
    if not (do_inbox or do_sweep):
        print(__doc__)
        return 2
    only = None
    if "--only" in argv:
        only = [k.strip() for k in argv[argv.index("--only") + 1].split(",") if k.strip()]
    url = os.environ.get("DATABASE_URL")
    if not url and not dry:
        print("DATABASE_URL is not set (use --dry-run to try it without a database)", file=sys.stderr)
        return 2
    db = DB(url, dry)
    run = Run(db, Storage())
    if dry:
        run.storage.url = run.storage.key = ""
    run.start("inbox" if do_inbox and not do_sweep else "sweep" if do_sweep and not do_inbox else "inbox+sweep")
    fatal = None
    try:
        keys, emailed = set(), set()
        if do_inbox:
            emailed = run.inbox()
            keys |= emailed
        if do_sweep:
            keys |= set(SOURCES)
        if only:
            keys &= set(only)
        for k in sorted(keys):
            run.force = k in emailed
            run.scan(k)
    except Exception as e:
        fatal = "%s: %s" % (type(e).__name__, e)
        run.error("run", fatal)
    run.finish(fatal)
    if not dry:
        notify(run)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write("new_docs=%d\nupdated_docs=%d\nerrors=%d\n" % (run.counts["new"], run.counts["updated"], run.counts["errors"]))
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
