#!/usr/bin/env python3
"""
read_minutes.py - read captured minutes into motions and roll calls, in batches.

  --submit    find minutes files not read yet (newest meetings first), pull their text (OCR for scanned pages),
              and send them to the model as a batch (Anthropic Message Batches or OpenAI Batch API: half the normal
              price; results within a day, usually an hour). Long files are split at page boundaries into several requests.
  --collect   fetch finished batches, store each file's motions, match names to officeholders and run the checks
              (match.py). Flagged motions wait on /admin ("Votes from minutes").
  --rematch   re-run matching and checks on every stored motion (after data/civic/officeholders.json changes).
              Review decisions are kept.
  --file F    local check: print the text and the request for one file; add --direct (needs the model's API key) to
              read it right away and print the motions and matched votes. Add --board pc --date 2016-12-13.

Spending limits: each --submit stops at MINUTES_SUBMIT_MAX files (default 150) or MINUTES_BATCH_BUDGET_USD of
estimated cost (default 25), and never lets the total for all reads pass MINUTES_TOTAL_BUDGET_USD (default 150;
Jeremy approved about $100 for the 2016-2026 backfill on 2026-10-26).

Model: MINUTES_MODEL (default claude-sonnet-5-5). A gpt-* name sends the batches to OpenAI instead (data/llm.py).
Each batch keeps the model it was sent with, so switching models mid-backlog is safe and the caps count both.

Environment: DATABASE_URL, SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (stored copies), and the key for the model's
provider: ANTHROPIC_API_KEY (+ ANTHROPIC_WORKSPACE_ID if the key isn't scoped to a workspace) or OPENAI_API_KEY.
Needs poppler-utils and tesseract-ocr.
"""
import concurrent.futures as cf
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agendas"))
sys.path.insert(0, os.path.join(HERE, ".."))
import llm  # noqa: E402  (Claude or GPT, picked by the model name)
import match as M  # noqa: E402
import text as T  # noqa: E402
import watch_agendas as wa  # noqa: E402
import extract_agendas as xa  # noqa: E402  (get_bytes)

fm = wa.fm
MODEL = os.environ.get("MINUTES_MODEL") or "claude-sonnet-5-5"
SUBMIT_MAX = int(os.environ.get("MINUTES_SUBMIT_MAX") or 150)
BATCH_BUDGET = float(os.environ.get("MINUTES_BATCH_BUDGET_USD") or 25)
TOTAL_BUDGET = float(os.environ.get("MINUTES_TOTAL_BUDGET_USD") or 150)
OCR_WORKERS = int(os.environ.get("MINUTES_OCR_WORKERS") or 4)
BATCH_DISCOUNT = 0.5
CHUNK_CHARS = 90_000          # about 25k tokens of text per request
KEEP_TEXT = 400_000
MAX_OUT = 32_000
RETRY_HOURS, MAX_ATTEMPTS = 6, 3
FIRST_DATE = "2016-01-01"

KINDS = ["contract", "purchase", "change_order", "budget", "millage", "grant", "bond_debt", "rezoning_land_use",
         "ordinance", "resolution", "appointment", "personnel", "settlement", "fee_rate", "property", "policy",
         "consent_agenda", "procedural", "other"]

NAMES = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["meetings"],
    "properties": {"meetings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["board", "date", "type", "present", "absent", "motions"],
        "properties": {
            "board": {"type": ["string", "null"], "description": "Board as named in the minutes"},
            "date": {"type": ["string", "null"], "description": "Meeting date, YYYY-MM-DD"},
            "type": {"type": "string", "enum": ["regular", "special", "workshop", "budget_hearing", "other"]},
            "present": {**NAMES, "description": "Voting board members present at roll call, names as printed"},
            "absent": {**NAMES, "description": "Voting board members absent at roll call"},
            "motions": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "required": ["item_number", "item_title", "motion", "summary", "kind", "consent", "mover", "seconder",
                             "outcome", "tally_text", "yes", "no", "abstain", "absent", "unanimous", "amounts",
                             "ordinances", "resolutions", "parties", "page"],
                "properties": {
                    "item_number": {"type": ["string", "null"]},
                    "item_title": {"type": ["string", "null"], "description": "Agenda item title as printed"},
                    "motion": {"type": "string", "description": "The motion as printed, trimmed to its substance"},
                    "summary": {"type": "string", "description": "One plain sentence: what the board voted to do"},
                    "kind": {"type": "string", "enum": KINDS},
                    "consent": {"type": "boolean", "description": "A single vote approving the consent agenda"},
                    "mover": {"type": ["string", "null"]},
                    "seconder": {"type": ["string", "null"]},
                    "outcome": {"type": "string", "enum": ["passed", "failed", "tabled", "withdrawn", "unclear"]},
                    "tally_text": {"type": ["string", "null"], "description": "Count as printed, e.g. 5-0, 4 to 1"},
                    "yes": {**NAMES, "description": "Members recorded voting yes/aye/yea by name"},
                    "no": {**NAMES, "description": "Members recorded voting no/nay by name"},
                    "abstain": NAMES,
                    "absent": {**NAMES, "description": "Members named as absent or not voting on this motion"},
                    "unanimous": {"type": "boolean", "description": "Minutes say unanimous / all in favor / without objection"},
                    "amounts": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False, "required": ["amount", "text"],
                        "properties": {"amount": {"type": "number"}, "text": {"type": "string"}}}},
                    "ordinances": {**NAMES, "description": "Ordinance numbers acted on"},
                    "resolutions": {**NAMES, "description": "Resolution numbers acted on"},
                    "parties": {**NAMES, "description": "Companies, agencies or organizations the motion is about"},
                    "page": {"type": ["integer", "null"], "description": "Page number from the === Page N === marker"},
                }}},
        }}}},
}

SYSTEM = """You read official meeting minutes from local governments in Bay County, Florida, and record every vote \
the board took. The text may come from OCR of a scanned page, so expect small spelling errors in names; copy names \
as printed (the system matches them to officeholders later).

Rules:
- Record every motion that was voted on, in order, including consent agenda approvals, budget and millage votes, \
contracts, ordinances, resolutions, appointments, settlements and failed motions. Skip purely procedural motions \
(approve the agenda, approve prior minutes, adjourn, recess) unless the vote was not unanimous.
- A file can hold several meetings (for example a year of minutes, or draft minutes inside an agenda packet). Give \
each meeting separately with its own date, roll call and motions.
- present/absent: only voting board members (not staff, attorneys or clerks), from the roll call at the start.
- yes/no/abstain/absent per motion: only names the minutes give for that vote. If the minutes say "carried \
unanimously", "all in favor" or similar, set unanimous true and leave yes empty. If they name only the dissenters \
("motion carried, Commissioner X voting no"), put X in no and leave yes empty. Never infer a vote that isn't written.
- tally_text: the count exactly as printed, or null. outcome: what the minutes say happened.
- amounts: every dollar figure in the motion or the item it acts on ("$1.2 million" -> 1200000).
- summary: one short plain-English sentence on what was decided, using only the minutes' words. No opinions.
- Use only what is printed. Never guess a date, name, amount or outcome; use null or an empty list.
- Privacy: never copy a student's name or initials (write "a student"), and don't name private individuals in \
code-enforcement, lien or disciplinary matters (write "a property owner", "an employee"). Officials, staff, \
applicants and companies may be named.
- page: the number from the nearest "=== Page N ===" marker above the motion."""


def params(board_name, doc_date, chunk_text, first, total_chunks):
    where = "%s minutes" % board_name + (" dated %s" % doc_date if doc_date else "")
    part = "" if total_chunks == 1 else " (part of a longer file, starting at page %d; a meeting may begin or end outside this part)" % first
    return {"system": SYSTEM, "user": "Minutes file: %s%s.\n\n%s" % (where, part, chunk_text)}


def body(p, model=None):
    """The request body for one chunk, in the provider's own shape."""
    return llm.request_body(model or MODEL, p["system"], p["user"], SCHEMA, "minutes", MAX_OUT)


def price(tin, tout, discount=BATCH_DISCOUNT, model=None):
    model = model or MODEL
    c = llm.price(model, tin, tout, discount)
    return c if c is not None else llm.price("claude-sonnet-5-5", tin, tout, discount)


def estimate(chars):
    tin = chars / 3.3 + 1500
    return price(tin, min(MAX_OUT, 1500 + chars / 12))


# ---------------------------------------------------------------------------------------------------------------
# Turning the model's answer into motions

def merge_chunks(results):
    """Chunk answers -> one list of meetings; a meeting cut across two chunks (same date) is joined."""
    out = []
    for r in results:
        for m in (r or {}).get("meetings") or []:
            prev = next((x for x in out if x.get("date") and x.get("date") == m.get("date")), None)
            if prev:
                prev["motions"] = (prev.get("motions") or []) + (m.get("motions") or [])
                for k in ("present", "absent"):
                    prev[k] = list(dict.fromkeys((prev.get(k) or []) + (m.get(k) or [])))
            else:
                out.append(dict(m))
    return out


def norm_date(s):
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", str(s or "")) else None


def motion_rows(meetings, board, doc_date, multi=False, data=None):
    """-> list of dicts ready for agendas.motions (no ids). Meetings before 2016 are dropped."""
    rows, pos = [], 0
    for mt in meetings:
        mt = dict(mt)
        mt["date"] = norm_date(mt.get("date"))
        date = mt["date"] or (str(doc_date) if doc_date and not multi else None)
        if date and date < FIRST_DATE:
            continue
        for mo in mt.get("motions") or []:
            pos += 1
            ev = M.evaluate(mo, {**mt, "date": date}, board, doc_date=None if multi else doc_date, data=data)
            amts = [a for a in mo.get("amounts") or [] if isinstance(a.get("amount"), (int, float))]
            key = "%s|%s|%s|%s" % (board, date, (mo.get("item_number") or "").strip().lower(),
                                   re.sub(r"\W+", " ", (mo.get("motion") or "").lower())[:80].strip())
            rows.append({
                "board": board, "meeting_date": date, "meeting_type": mt.get("type"), "position": pos,
                "item_number": mo.get("item_number"), "item_title": (mo.get("item_title") or "")[:1000] or None,
                "motion": (mo.get("motion") or "")[:2000], "summary": mo.get("summary"), "kind": mo.get("kind"),
                "consent": bool(mo.get("consent")), "mover": mo.get("mover"), "seconder": mo.get("seconder"),
                "outcome": mo.get("outcome"), "tally_printed": mo.get("tally_text"),
                "printed": {k: mo.get(k) or [] for k in ("yes", "no", "abstain", "absent")} | {"unanimous": bool(mo.get("unanimous")),
                                                                                             "present": mt.get("present") or [],
                                                                                             "absent_roll": mt.get("absent") or []},
                "amounts": amts, "amount": max((a["amount"] for a in amts), default=None),
                "ordinances": mo.get("ordinances") or [], "resolutions": mo.get("resolutions") or [],
                "parties": mo.get("parties") or [], "page": mo.get("page"),
                "votes": ev["votes"], "vote_method": ev["method"], "tally": ev["tally"], "unmatched": ev["unmatched"],
                "checks": ev["checks"], "check_status": ev["check_status"], "sampled": bool(ev.get("sampled")),
                "motion_key": key})
    return rows


# ---------------------------------------------------------------------------------------------------------------
# Database steps

PENDING = """
select d.id, d.url, d.board, d.title, d.meeting_date, d.current_sha256, d.content_type,
       (select v.storage_path from agendas.versions v where v.document_id = d.id and v.sha256 = d.current_sha256 limit 1)
  from agendas.documents d
 where d.kind = 'minutes' and d.current_sha256 is not null and d.board = any(%s)
   and (d.meeting_date is null or d.meeting_date >= %s)
   and not exists (select 1 from agendas.minutes_reads r where r.document_id = d.id and r.sha256 = d.current_sha256
                   and (r.status in ('ok', 'submitted', 'no_text') or r.attempts >= %s
                        or r.submitted_at > now() - make_interval(hours => %s)))
 order by d.meeting_date desc nulls last, d.id desc
 limit %s"""


def fetchall(db, sql, args=()):
    with db.conn.cursor() as c:
        c.execute(sql, args)
        return c.fetchall()


def prepare(storage, doc):
    """Download + text for one document. -> (doc, pages, method, ocr, error)."""
    doc_id, url, board, title, mdate, sha, ctype, path = doc
    try:
        data = xa.get_bytes(storage, path, url)
        pages, method, ocr = T.to_pages(data, ctype or "")
        return doc, pages, method, ocr, None
    except T.ToolMissing:
        raise
    except Exception as e:
        return doc, None, None, 0, "%s: %s" % (type(e).__name__, e)


def submit(db, storage, run_id):
    spent = float(fetchall(db, "select coalesce(sum(coalesce(cost_usd, 0)), 0) from agendas.minutes_reads")[0][0])
    pending = float(fetchall(db, "select coalesce(sum(est_cost_usd), 0) from agendas.minutes_batches where status = 'in_progress'")[0][0])
    room = min(BATCH_BUDGET, TOTAL_BUDGET - spent - pending)
    if room <= 0.5:
        print("budget: $%.2f spent + $%.2f in flight of the $%.2f total; nothing submitted" % (spent, pending, TOTAL_BUDGET))
        return 0
    docs = fetchall(db, PENDING, (list(M.BOARDS), FIRST_DATE, MAX_ATTEMPTS, RETRY_HOURS, SUBMIT_MAX))
    print("submit: %d minutes file(s) waiting; room for about $%.2f" % (len(docs), room))
    requests, est, reads = [], 0.0, 0
    with cf.ThreadPoolExecutor(OCR_WORKERS) as ex:
        for doc, pages, method, ocr, err in ex.map(lambda d: prepare(storage, d), docs):
            doc_id, url, board, title, mdate, sha, ctype, path = doc
            if est >= room:
                break
            text = T.joined(pages) if pages else None
            status = "failed" if err else ("no_text" if not text or T.letters(text) < 300 else "submitted")
            parts = T.chunks(pages, CHUNK_CHARS) if status == "submitted" else []
            cost = sum(estimate(sum(len(p) for p in ps)) for _, ps in parts)
            if status == "submitted" and est + cost > room and requests:
                break
            row = db.one("""insert into agendas.minutes_reads (document_id, sha256, status, error, model, chunks, pages, text_method,
                    ocr_pages, text_chars, text, ingest_run_id) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (document_id, sha256) do update set status = excluded.status, error = excluded.error, model = excluded.model,
                    chunks = excluded.chunks, chunks_done = 0, results = '[]', pages = excluded.pages, text_method = excluded.text_method,
                    ocr_pages = excluded.ocr_pages, text_chars = excluded.text_chars, text = excluded.text, batch_id = null,
                    attempts = agendas.minutes_reads.attempts + 1, submitted_at = now(), ingest_run_id = excluded.ingest_run_id
                returning id""",
                         (doc_id, sha, status, err, MODEL if parts else None, max(len(parts), 1), len(pages) if pages else None,
                          method, ocr, len(text) if text else None, text[:KEEP_TEXT] if text else None, run_id))
            if err:
                db.one("insert into agendas.errors (stage, source_key, url, message, document_id, ingest_run_id) "
                       "values ('minutes', %s, %s, %s, %s, %s)", (board, url, err[:1000], doc_id, run_id))
            print("  %-9s %-7s %s %s: %d pages (%s%s), %d request(s)" % (
                status, board, mdate or "", (title or url)[:50], len(pages or []), method or "-",
                ", %d OCR" % ocr if ocr else "", len(parts)))
            if status != "submitted":
                continue
            reads += 1
            est += cost
            name = M.BOARDS.get(board, (None, None, board))[2]
            for i, (first, ps) in enumerate(parts):
                p = params(name, mdate, T.joined(ps, first), first, len(parts))
                requests.append(llm.batch_request(MODEL, "r%d-c%d" % (row[0], i), p["system"], p["user"], SCHEMA,
                                                  "minutes", MAX_OUT))
    if not requests:
        print("nothing to send")
        return 0
    bid = llm.batch_submit(MODEL, requests)
    db.one("insert into agendas.minutes_batches (batch_id, model, requests, est_cost_usd) values (%s,%s,%s,%s)",
           (bid, MODEL, len(requests), round(est, 4)))
    ids = sorted({int(r["custom_id"].split("-")[0][1:]) for r in requests})
    db.one("update agendas.minutes_reads set batch_id = %s where id = any(%s)", (bid, ids))
    print("sent batch %s to %s: %d request(s) for %d file(s), about $%.2f" % (bid, MODEL, len(requests), reads, est))
    return reads


def store_read(db, read_id, data=None):
    """All chunks of a read are back: write its motions (keeping review decisions for motions seen before)."""
    r = fetchall(db, """select r.document_id, r.results, d.board, d.meeting_date, d.url, d.title
                          from agendas.minutes_reads r join agendas.documents d on d.id = r.document_id where r.id = %s""", (read_id,))
    if not r:
        return 0
    doc_id, results, board, mdate, url, title = r[0]
    model = fetchall(db, "select model from agendas.minutes_reads where id = %s", (read_id,))[0][0]
    results = sorted(results or [], key=lambda x: x.get("chunk", 0))
    multi = bool(re.search(r"^20\d\d\s+(official\s+)?minutes$", title or "", re.I))
    meetings = merge_chunks([x.get("answer") for x in results])
    rows = motion_rows(meetings, board, mdate, multi=multi, data=data)
    old = {k: (s, n, by, at) for k, s, n, by, at in fetchall(
        db, "select motion_key, review_status, review_note, reviewed_by, reviewed_at from agendas.motions "
            "where document_id = %s and review_status <> 'unreviewed'", (doc_id,))}
    db.one("delete from agendas.motions where document_id = %s", (doc_id,))
    for m in rows:
        rev = old.get(m["motion_key"], ("unreviewed", None, None, None))
        db.one("""insert into agendas.motions (read_id, document_id, board, meeting_date, meeting_type, position, item_number, item_title,
                motion, summary, kind, consent, mover, seconder, outcome, tally_printed, printed, amounts, amount, ordinances,
                resolutions, parties, page, votes, vote_method, tally, unmatched, checks, check_status, sampled, review_status,
                review_note, reviewed_by, reviewed_at, motion_key)
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
               (read_id, doc_id, m["board"], m["meeting_date"], m["meeting_type"], m["position"], m["item_number"], m["item_title"],
                m["motion"], m["summary"], m["kind"], m["consent"], m["mover"], m["seconder"], m["outcome"], m["tally_printed"],
                db.j(m["printed"]), db.j(m["amounts"]), m["amount"], db.j(m["ordinances"]), db.j(m["resolutions"]),
                db.j(m["parties"]), m["page"], db.j(m["votes"]), m["vote_method"], m["tally"], db.j(m["unmatched"]),
                db.j(m["checks"]), m["check_status"], m["sampled"], rev[0], rev[1], rev[2], rev[3], m["motion_key"]))
    tin = sum(x.get("in", 0) for x in results)
    tout = sum(x.get("out", 0) for x in results)
    db.one("""update agendas.minutes_reads set status = 'ok', error = null, meetings = %s, motion_count = %s, input_tokens = %s,
              output_tokens = %s, cost_usd = %s, read_at = now() where id = %s""",
           (len(meetings), len(rows), tin, tout, price(tin, tout, model=model), read_id))
    flagged = sum(1 for m in rows if m["check_status"] == "flagged")
    print("  ok      %-7s %s %s: %d meeting(s), %d motion(s), %d flagged" % (board, mdate or "", (title or url)[:50], len(meetings), len(rows), flagged))
    return len(rows)


def collect(db):
    batches = fetchall(db, "select batch_id, model from agendas.minutes_batches where status in ('in_progress', 'ended') order by id")
    n_motions = 0
    for bid, bmodel in batches:
        model = llm.batch_model(bmodel, bid)
        state, note = llm.batch_state(model, bid)
        if state == "running":
            print("batch %s: still running (%s)" % (bid, note))
            continue
        if state == "failed":  # the whole batch was refused (e.g. over the provider's queue limit): retry its files later
            db.one("update agendas.minutes_batches set status = 'failed', error = %s, ended_at = now() where batch_id = %s", (note, bid))
            db.one("update agendas.minutes_reads set status = 'failed', error = %s where batch_id = %s and status = 'submitted'", (note, bid))
            print("batch %s: %s" % (bid, note))
            continue
        db.one("update agendas.minutes_batches set status = 'ended', ended_at = coalesce(ended_at, now()) where batch_id = %s", (bid,))
        touched, cost = set(), 0.0
        for res in llm.batch_results(model, bid):
            m = re.match(r"r(\d+)-c(\d+)$", res.custom_id or "")
            if not m:
                continue
            read_id, chunk = int(m.group(1)), int(m.group(2))
            cost += price(res.tin, res.tout, model=model)
            if res.error:
                err = res.error if not res.error.startswith("model stopped") else "%s (chunk %d)" % (res.error, chunk)
                db.one("update agendas.minutes_reads set status = 'failed', error = %s where id = %s", (err[:500], read_id))
                continue
            db.one("""update agendas.minutes_reads set results = results || %s::jsonb, chunks_done = chunks_done + 1
                      where id = %s and status = 'submitted'""",
                   (json.dumps([{"chunk": chunk, "answer": res.answer, "in": res.tin, "out": res.tout}]), read_id))
            touched.add(read_id)
        for read_id in sorted(touched):
            done = fetchall(db, "select chunks, chunks_done, status from agendas.minutes_reads where id = %s", (read_id,))[0]
            if done[2] == "submitted" and done[1] >= done[0]:
                n_motions += store_read(db, read_id)
        # files in a batch that ended without an answer (expired or cancelled) go back in the queue
        db.one("""update agendas.minutes_reads set status = 'failed', error = 'no answer in batch'
                  where batch_id = %s and status = 'submitted' and chunks_done < chunks""", (bid,))
        db.one("update agendas.minutes_batches set status = 'collected', collected_at = now(), cost_usd = %s where batch_id = %s",
               (round(cost, 4), bid))
        print("batch %s collected: about $%.2f" % (bid, cost))
    return n_motions


def rematch(db):
    reads = fetchall(db, "select id from agendas.minutes_reads where status = 'ok' order by id")
    n = 0
    for (rid,) in reads:
        n += store_read(db, rid)
    print("re-matched %d motions in %d files" % (n, len(reads)))


# ---------------------------------------------------------------------------------------------------------------

def local(argv):
    fp = argv[argv.index("--file") + 1]
    board = argv[argv.index("--board") + 1] if "--board" in argv else "pc"
    date = argv[argv.index("--date") + 1] if "--date" in argv else None
    data = open(fp, "rb").read()
    pages, method, ocr = T.to_pages(data, "application/pdf" if fp.lower().endswith(".pdf") else "text/html")
    parts = T.chunks(pages, CHUNK_CHARS)
    print("%d pages (%s, %d OCR), %d request(s), about $%.3f" % (len(pages), method, ocr, len(parts),
                                                              sum(estimate(sum(len(p) for p in ps)) for _, ps in parts)), file=sys.stderr)
    name = M.BOARDS.get(board, (None, None, board))[2]
    if "--direct" not in argv:
        for first, ps in parts:
            p = body(params(name, date, T.joined(ps, first), first, len(parts)))
            print(json.dumps({k: v for k, v in p.items() if k not in ("output_config", "response_format")}, indent=1)[:6000])
        return 0
    results = []
    for i, (first, ps) in enumerate(parts):
        p = params(name, date, T.joined(ps, first), first, len(parts))
        answer, tin, tout = llm.structured(MODEL, p["system"], p["user"], SCHEMA, "minutes", MAX_OUT)
        print("chunk %d (%s): %s in / %s out, about $%.3f at full price" % (i, MODEL, tin, tout, price(tin, tout, 1)), file=sys.stderr)
        results.append(answer)
    rows = motion_rows(merge_chunks(results), board, date)
    for r in rows:
        print("%s p%s %-8s %-6s %-20s %s | %s" % (r["meeting_date"], r["page"], r["check_status"], r["tally"], r["vote_method"],
                                               (r["summary"] or r["motion"])[:90], ",".join(r["checks"])))
    if "--json" in argv:
        print(json.dumps(rows, indent=1, default=str))
    return 0


def main(argv):
    if "--file" in argv:
        return local(argv)
    if not any(a in argv for a in ("--submit", "--collect", "--rematch")):
        print(__doc__)
        return 2
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2
    if "--rematch" not in argv:
        if not llm.known(MODEL):  # without a price the spending caps can't work
            print("no price for model %s; add it to PRICES in data/llm.py" % MODEL, file=sys.stderr)
            return 2
        if not llm.has_key(MODEL):
            print("%s is not set (model %s); skipping minutes reading" % (llm.key_name(MODEL), MODEL))
            return 0
    db = wa.DB(os.environ["DATABASE_URL"], False)
    storage = wa.Storage()
    r = db.one("insert into ingest_runs (origin, dataset, notes) values ('scraper:minutes', 'minutes_votes', %s) returning id",
               ("model: " + MODEL,))
    run_id = r[0]
    notes, status = [], "ok"
    try:
        if "--rematch" in argv:
            rematch(db)
        if "--collect" in argv:
            notes.append("%d motions collected" % collect(db))
        if "--submit" in argv:
            notes.append("%d files sent" % submit(db, storage, run_id))
    except (xa.SetupError, T.ToolMissing) as e:
        status = "failed"
        notes.append("setup problem: %s" % e)
        db.one("insert into agendas.errors (stage, message, ingest_run_id) values ('minutes', %s, %s)", (str(e)[:1000], run_id))
    db.one("update ingest_runs set finished_at = now(), status = %s, notes = %s where id = %s", (status, "; ".join(notes), run_id))
    print("; ".join(notes))
    return 1 if status == "failed" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
