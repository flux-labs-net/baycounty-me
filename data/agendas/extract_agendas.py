#!/usr/bin/env python3
"""
extract_agendas.py - read captured agendas into items.

For each agenda captured by watch_agendas.py whose current version hasn't been read yet:
  1. get the file (Supabase Storage copy, else the public source URL)
  2. pull out its text (pdftotext for PDFs; visible text for HTML pages)
  3. send the text to a Claude model (AGENDA_MODEL, default claude-sonnet-5-5) with a JSON schema, and store the
     meeting details and every numbered item: title, one-line summary, kind, dollar amounts, parties, addresses.

Only agendas (and agenda-like files from notice emails) are read, never packets: packets run to hundreds of pages
and the agenda already lists every item. Scanned agendas with no text layer are marked no_text (no OCR yet).
Each run reads at most AGENDA_EXTRACT_MAX documents (default 25), newest meetings first, and stops early if the
run's estimated cost passes AGENDA_EXTRACT_BUDGET_USD (default 2.00).

A failed read is retried after RETRY_HOURS (6), up to MAX_ATTEMPTS (3). A setup problem (pdftotext missing, a bad
key, a key that needs ANTHROPIC_WORKSPACE_ID) stops the run without marking agendas failed.

Environment: DATABASE_URL, ANTHROPIC_API_KEY, ANTHROPIC_WORKSPACE_ID (only if the key isn't scoped to a workspace), SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (to read stored copies),
AGENDA_MODEL, AGENDA_EXTRACT_MAX, AGENDA_EXTRACT_BUDGET_USD.
Usage:
  python3 data/agendas/extract_agendas.py                 # the scheduled step
  python3 data/agendas/extract_agendas.py --file x.pdf    # read one local file and print the JSON (no database)
"""

import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import watch_agendas as wa  # noqa: E402  (DB, Storage, download, fetch_meetings helpers)
from export_items import keep_party  # noqa: E402

fm = wa.fm
MODEL = os.environ.get("AGENDA_MODEL") or "claude-sonnet-5-5"
MAX_DOCS = int(os.environ.get("AGENDA_EXTRACT_MAX") or 25)
BUDGET = float(os.environ.get("AGENDA_EXTRACT_BUDGET_USD") or 2.0)
MAX_CHARS = 120_000          # ~30k tokens; an agenda is far shorter, this only guards against a mislabeled packet
KEEP_TEXT = 200_000
RETRY_HOURS = 6              # a failed read is tried again after this long ...
MAX_ATTEMPTS = 3             # ... up to this many times


ALERT_DAYS_BACK = 3          # items for meetings older than this don't become alert events (a backfill isn't news)


def alert_record(item, board, meeting_date, url, title):
    """The alerts.events record for one agenda item (dataset 'agenda-items', matched by api/_rules.js)."""
    return {"board": board, "meeting_date": str(meeting_date) if meeting_date else None, "meeting_title": title,
            "item_number": item.get("number"), "section": item.get("section"), "title": item.get("title"),
            "summary": item.get("summary"), "kind": item.get("kind"),
            "amount": max((a["amount"] for a in item.get("amounts") or [] if isinstance(a.get("amount"), (int, float))), default=None),
            # same privacy filter as site search: organizations kept, private individuals' names dropped
            "parties": [p for p in item.get("parties") or [] if keep_party(p)], "addresses": item.get("addresses") or [],
            "agenda_url": url}


def alert_hash(rec):
    key = "|".join(str(rec.get(k) or "") for k in ("board", "meeting_date", "item_number")) + "|" + re.sub(r"\W+", " ", (rec.get("title") or "").lower()).strip()
    return hashlib.sha1(key.encode()).hexdigest()[:32]


def wants_alerts(meeting_date, today):
    return meeting_date is not None and meeting_date >= today - dt.timedelta(days=ALERT_DAYS_BACK)


class SetupError(RuntimeError):
    """A problem with the run's setup (missing tool, bad key or workspace), not with one agenda: stop the run and
    record nothing per agenda, so every agenda isn't marked failed and retried for no reason."""
# Published prices per million tokens (input, output). Haiku is listed "from" this price, so its estimate is a floor.
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50), "claude-opus-5-5": (4.0, 20.0)}
KINDS = ["contract", "purchase", "change_order", "budget", "grant", "bond_debt", "rezoning_land_use", "ordinance",
         "resolution", "appointment", "personnel", "presentation", "public_hearing", "consent", "minutes_approval",
         "other"]

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["meeting", "items"],
    "properties": {
        "meeting": {
            "type": "object", "additionalProperties": False,
            "required": ["body", "date", "time", "location"],
            "properties": {
                "body": {"type": ["string", "null"], "description": "Board as named on the agenda"},
                "date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                "time": {"type": ["string", "null"], "description": "As printed, e.g. 5:30 p.m."},
                "location": {"type": ["string", "null"]},
            },
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["number", "section", "title", "summary", "kind", "amounts", "parties", "addresses"],
                "properties": {
                    "number": {"type": ["string", "null"], "description": "Item number exactly as printed"},
                    "section": {"type": ["string", "null"], "description": "Heading the item sits under"},
                    "title": {"type": "string"},
                    "summary": {"type": ["string", "null"], "description": "One plain sentence, only from the agenda's words"},
                    "kind": {"type": "string", "enum": KINDS},
                    "amounts": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False, "required": ["amount", "text"],
                        "properties": {"amount": {"type": "number"}, "text": {"type": "string"}}}},
                    "parties": {"type": "array", "items": {"type": "string"},
                                "description": "Companies, applicants, agencies or nonprofits named (not staff, not board members)"},
                    "addresses": {"type": "array", "items": {"type": "string"},
                                  "description": "Street addresses, parcel IDs or named roads/sites the item is about"},
                },
            },
        },
    },
}

PROMPT = """You are reading a public meeting agenda from a local government in Bay County, Florida. Extract the meeting \
details and every substantive agenda item, in order.

Rules:
- Use only what the agenda says. Never guess amounts, vendors or addresses that aren't printed. Use null when a field isn't stated.
- Skip procedural items: call to order, invocation, pledge, roll call, approval of the agenda, public comment periods, \
staff/commissioner reports with no stated subject, adjournment. Keep "approval of minutes" only as kind minutes_approval.
- Consent agenda items are separate items (kind = what the item is, e.g. contract; section = the consent heading).
- amounts: every dollar figure stated for the item, as a number plus the text as printed ("$1.2 million" -> 1200000).
- summary: one short sentence in plain English drawn from the item's own wording; null if the title says it all.
- Keep item titles close to the agenda's wording; trim boilerplate like "Consideration of" only when it adds nothing.

Agenda text:
"""


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        try:
            r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", f.name, "-"], capture_output=True, timeout=120)
        except FileNotFoundError:
            raise SetupError("pdftotext isn't installed (poppler-utils)")
        if r.returncode != 0:
            raise RuntimeError("pdftotext: " + r.stderr.decode("utf-8", "replace")[:200])
        return r.stdout.decode("utf-8", "replace")


def to_text(data, ctype, url=""):
    if ctype == "application/pdf" or data[:5] == b"%PDF-":
        t = pdf_text(data)
    elif ctype in ("text/html", "text/plain") or data.lstrip()[:1] == b"<":
        t = fm.strip_tags(data.decode("utf-8", "replace"), sep="\n")
    else:
        raise ValueError("can't read %s" % ctype)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def claude(text):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SetupError("ANTHROPIC_API_KEY is not set")
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json", "User-Agent": fm.UA}
    if os.environ.get("ANTHROPIC_WORKSPACE_ID"):  # needed when the key isn't scoped to a workspace
        headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
    body = json.dumps({"model": MODEL, "max_tokens": 16000,
                       "messages": [{"role": "user", "content": PROMPT + text}],
                       "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}).encode()
    last = None
    for attempt in range(3):
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                j = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode("utf-8", "replace")
            if e.code in (401, 403) or (e.code == 400 and re.search(r"api key|workspace|credit|billing", msg, re.I)):
                raise SetupError("Claude API %s: %s" % (e.code, msg))
            last = RuntimeError("Claude API %s: %s" % (e.code, msg))
            if e.code not in (429, 500, 502, 503, 529):
                raise last
        except Exception as e:
            last = e
        fm.time.sleep(5 * (attempt + 1))
    else:
        raise last
    if j.get("stop_reason") in ("refusal", "max_tokens"):
        raise RuntimeError("model stopped: %s" % j.get("stop_reason"))
    out = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
    u = j.get("usage") or {}
    return json.loads(out), u.get("input_tokens") or 0, u.get("output_tokens") or 0


def cost(model, tin, tout):
    p = PRICES.get(model)
    return round((tin * p[0] + tout * p[1]) / 1e6, 4) if p else None


def norm_date(s):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(s or ""))
    return s if m else None


def get_bytes(storage, path, url):
    if path and storage.on:
        try:
            return storage._req("GET", "/storage/v1/object/%s/%s" % (wa.BUCKET, urllib.parse.quote(path)))
        except Exception:
            pass  # fall back to the source
    if not url.startswith("http"):
        raise RuntimeError("no stored copy and no source URL")
    data, _ctype, _sha, size = wa.download(url)
    if data is None:
        raise RuntimeError("file is %d MB, too large to read as an agenda" % (size // 1048576))
    return data


PENDING = """
select d.id, d.url, d.board, d.title, d.meeting_date, d.current_sha256, d.content_type,
       (select v.storage_path from agendas.versions v where v.document_id = d.id and v.sha256 = d.current_sha256 limit 1)
  from agendas.documents d
 where d.kind in ('agenda', 'linked', 'attachment')
   and d.current_sha256 is not null
   and (d.bytes is null or d.bytes <= %s)
   and not exists (select 1 from agendas.extractions e where e.document_id = d.id and e.sha256 = d.current_sha256
                   and (e.status <> 'failed' or e.attempts >= %s or e.extracted_at > now() - make_interval(hours => %s)))
 order by d.meeting_date desc nulls last, d.id desc
 limit %s"""


def run():
    db = wa.DB(os.environ.get("DATABASE_URL"), False)
    storage = wa.Storage()
    r = db.one("insert into ingest_runs (origin, dataset, notes) values ('scraper:agendas', 'agenda_items', %s) returning id",
               ("model: " + MODEL,))
    run_id = r[0]
    with db.conn.cursor() as c:
        c.execute(PENDING, (wa.STORE_MAX, MAX_ATTEMPTS, RETRY_HOURS, MAX_DOCS))
        docs = c.fetchall()
    print("extract: %d agenda(s) to read with %s" % (len(docs), MODEL))
    spent, n_ok, n_items, n_fail, n_events = 0.0, 0, 0, 0, 0
    for doc_id, url, board, title, mdate, sha, ctype, path in docs:
        if spent >= BUDGET:
            print("budget of $%.2f reached; the rest waits for the next run" % BUDGET)
            break
        status, err, text, parsed, tin, tout = "ok", None, None, None, 0, 0
        try:
            data = get_bytes(storage, path, url)
            text = to_text(data, ctype or "", url)
            if len(re.sub(r"\s", "", text)) < 200:
                status = "no_text"
            else:
                parsed, tin, tout = claude(text[:MAX_CHARS])
        except SetupError as e:
            msg = str(e)[:500]
            print("setup problem, stopping: " + msg)
            db.one("insert into agendas.errors (stage, url, message, ingest_run_id) values ('extract', null, %s, %s)", (msg, run_id))
            db.one("update ingest_runs set finished_at = now(), status = 'failed', notes = %s where id = %s", ("FAILED: " + msg, run_id))
            return 1
        except Exception as e:
            status, err = "failed", str(e)[:500]
            n_fail += 1
            db.one("insert into agendas.errors (stage, source_key, url, message, document_id, ingest_run_id) "
                   "values ('extract', %s, %s, %s, %s, %s)", (board, url, err, doc_id, run_id))
        c_usd = cost(MODEL, tin, tout) if tin else None
        spent += c_usd or 0
        m = (parsed or {}).get("meeting") or {}
        items = (parsed or {}).get("items") or []
        row = db.one("""insert into agendas.extractions (document_id, sha256, status, error, model, meeting_body, meeting_date,
                meeting_time, meeting_location, item_count, text_chars, text_truncated, input_tokens, output_tokens, cost_usd, text,
                ingest_run_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (document_id, sha256) do update set status = excluded.status, error = excluded.error,
                model = excluded.model, meeting_body = excluded.meeting_body, meeting_date = excluded.meeting_date,
                meeting_time = excluded.meeting_time, meeting_location = excluded.meeting_location, item_count = excluded.item_count,
                text_chars = excluded.text_chars, text_truncated = excluded.text_truncated, input_tokens = excluded.input_tokens,
                output_tokens = excluded.output_tokens, cost_usd = excluded.cost_usd, text = excluded.text,
                ingest_run_id = excluded.ingest_run_id, attempts = agendas.extractions.attempts + 1, extracted_at = now() returning id""",
                     (doc_id, sha, status, err, MODEL if tin else None, m.get("body"), norm_date(m.get("date")), m.get("time"),
                      m.get("location"), len(items), len(text) if text else None, bool(text and len(text) > MAX_CHARS),
                      tin or None, tout or None, c_usd, text[:KEEP_TEXT] if text else None, run_id))
        ext_id = row[0]
        db.one("delete from agendas.items where extraction_id = %s", (ext_id,))
        for pos, it in enumerate(items, 1):
            amts = [a for a in it.get("amounts") or [] if isinstance(a.get("amount"), (int, float))]
            db.one("""insert into agendas.items (extraction_id, document_id, position, item_number, section, title, summary, kind,
                    amounts, total_amount, parties, addresses) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                   (ext_id, doc_id, pos, it.get("number"), it.get("section"), (it.get("title") or "")[:1000], it.get("summary"),
                    it.get("kind"), db.j(amts), max((a["amount"] for a in amts), default=None),
                    db.j(it.get("parties") or []), db.j(it.get("addresses") or [])))
        if status == "ok":
            n_ok += 1
            n_items += len(items)
            # New items for upcoming (or just-held) meetings feed rule alerts: keyword and contract rules.
            md = mdate or (dt.date.fromisoformat(norm_date(m.get("date"))) if norm_date(m.get("date")) else None)
            if items and wants_alerts(md, fm.now_central().date()):
                gov = wa.GOV_OF_BOARD.get(board)
                for it in items:
                    rec = alert_record(it, board, md, url, title)
                    db.one("insert into alerts.events (dataset, record_hash, government_key, record, ingest_run_id) "
                           "select 'agenda-items', %s, %s, %s, %s where not exists (select 1 from alerts.events "
                           "where dataset = 'agenda-items' and record_hash = %s)",
                           (alert_hash(rec), gov, db.j(rec), run_id, alert_hash(rec)))
                    n_events += 1
        print("  %-8s %-7s %s %s: %d items%s" % (status, board or "", mdate or "", (title or url)[:60], len(items),
                                                 " ($%.3f)" % c_usd if c_usd else ""))
    notes = "%s: %d read, %d items (%d for alerts), %d failed, about $%.2f" % (MODEL, n_ok, n_items, n_events, n_fail, spent)
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write("items_read=%d\n" % n_items)
    db.one("update ingest_runs set finished_at = now(), rows_in = %s, status = 'ok', notes = %s where id = %s",
           (n_items, notes, run_id))
    print(notes)
    return 0


def main(argv):
    if "--file" in argv:  # local check: read one file, print the result
        fp = argv[argv.index("--file") + 1]
        data = open(fp, "rb").read()
        text = to_text(data, "application/pdf" if fp.lower().endswith(".pdf") else "text/html")
        print("%d chars of text" % len(text), file=sys.stderr)
        if "--text-only" in argv:
            print(text[:4000])
            return 0
        parsed, tin, tout = claude(text[:MAX_CHARS])
        print(json.dumps(parsed, indent=2))
        print("tokens in/out %d/%d, about $%s" % (tin, tout, cost(MODEL, tin, tout)), file=sys.stderr)
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; skipping agenda extraction")
        return 0
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
