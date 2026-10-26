#!/usr/bin/env python3
"""
export_votes.py - write data/votes/minutes_votes.json from the motions read out of minutes.

Published: motions that passed every check (match.py) and weren't rejected on review, plus flagged motions an
admin approved. One minutes file per meeting: when the same meeting was captured twice (e.g. Callaway's Archive
Center and its AgendaCenter), the file with more motions wins. Motions that repeat a hand-researched vote in
data/votes/votes.json (same board and date, and the same amount, ordinance/resolution number or wording) are left
out, since the researched entry has the fuller write-up.

Run by the daily meetings refresh before the site build (like data/agendas/export_items.py); site/opendata.py adds
these rows to the votes and member-votes datasets. A database problem keeps the last export.
Usage: DATABASE_URL=... python3 data/minutes/export_votes.py [--out PATH]
"""
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import match as M  # noqa: E402

ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(ROOT, "data", "votes", "minutes_votes.json")
RESEARCHED = os.path.join(ROOT, "data", "votes", "votes.json")

CATEGORY = {"contract": "contract", "purchase": "contract", "change_order": "contract", "budget": "budget", "millage": "millage",
            "grant": "grant", "bond_debt": "debt", "rezoning_land_use": "land use", "ordinance": "ordinance",
            "resolution": "resolution", "appointment": "appointment", "personnel": "personnel", "settlement": "settlement",
            "fee_rate": "fees", "property": "property", "policy": "policy", "consent_agenda": "consent agenda",
            "procedural": "procedural", "other": "other"}

QUERY = """
select m.id, m.board, m.meeting_date, m.meeting_type, m.item_number, m.item_title, m.motion, m.summary, m.kind, m.consent,
       m.mover, m.seconder, m.outcome, m.tally, m.tally_printed, m.amount, m.ordinances, m.resolutions, m.page, m.votes,
       m.vote_method, m.check_status, m.review_status, d.id, d.url, d.title,
       (select count(*) from agendas.motions x where x.document_id = d.id) n
  from agendas.motions m
  join agendas.minutes_reads r on r.id = m.read_id and r.status = 'ok'
  join agendas.documents d on d.id = m.document_id and d.current_sha256 = r.sha256
 where m.meeting_date >= date '2016-01-01'
   and m.review_status <> 'rejected'
   and (m.check_status = 'passed' or m.review_status = 'approved')
 order by m.meeting_date, m.board, d.id, m.position"""


def words(s):
    return {w for w in re.findall(r"[a-z]{4,}", (s or "").lower())} - {"approve", "approval", "motion", "commission", "board", "with", "that", "from"}


def researched_index(path=RESEARCHED):
    try:
        votes = json.load(open(path))["votes"]
    except (FileNotFoundError, KeyError, ValueError):
        return {}
    idx = {}
    for v in votes:
        idx.setdefault((v.get("body"), v.get("date")), []).append(v)
    return idx


def duplicates_researched(row, idx):
    """True when a hand-researched vote already covers this motion."""
    body = M.BOARDS.get(row["board"], (None, None))[1]
    cands = idx.get((body, row["date"])) or []
    text = " ".join(filter(None, [row.get("item_title"), row.get("motion")]))
    nums = {n.lower() for n in (row.get("ordinances") or []) + (row.get("resolutions") or [])}
    for v in cands:
        item = (v.get("item") or "") + " " + (v.get("summary") or "")
        if row.get("amount") and v.get("amount") and abs(float(row["amount"]) - float(v["amount"])) < 1:
            return True
        if nums and any(n in item.lower() for n in nums):
            return True
        a, b = words(text), words(item)
        if a and b and len(a & b) / max(1, min(len(a), len(b))) >= 0.5:
            return True
    return False


def source_title(board, date, page, title):
    name = M.BOARDS.get(board, (None, None, board))[2]
    return "%s minutes, %s%s" % (name, date, ", page %d" % page if page else "")


def rows(cur, idx):
    cur.execute(QUERY)
    recs = cur.fetchall()
    # one file per meeting: the file with the most motions for that board and date
    best = {}
    for r in recs:
        key = (r[1], r[2])
        if key not in best or r[26] > best[key][1] or (r[26] == best[key][1] and r[23] > best[key][0]):
            best[key] = (r[23], r[26])
    out = []
    for (mid, board, date, mtype, num, title, motion, summary, kind, consent, mover, seconder, outcome, tally, tprinted,
         amount, ords, ress, page, votes, method, cstatus, rstatus, doc_id, url, dtitle, _n) in recs:
        if best[(board, date)][0] != doc_id:
            continue
        row = {"board": board, "date": date.isoformat(), "item_title": title, "motion": motion, "amount": float(amount) if amount is not None else None,
               "ordinances": ords or [], "resolutions": ress or []}
        if duplicates_researched(row, idx):
            continue
        out.append({
            "body": M.BOARDS[board][1], "date": date.isoformat(), "category": CATEGORY.get(kind, "other"),
            "item": " ".join(filter(None, [num, title])) or motion[:200],
            "amount": row["amount"], "outcome": outcome, "tally": tally or tprinted,
            "by_member": votes or {}, "headline": summary, "summary": motion, "plain_summary": summary,
            "consent": bool(consent), "mover": mover, "seconder": seconder, "vote_method": method,
            "verified": "reviewed" if rstatus == "approved" else "auto-checked", "meeting_type": mtype,
            "source_title": source_title(board, date.isoformat(), page, dtitle), "source_url": url if str(url).startswith("http") else None,
            "source_page": page, "motion_id": mid, "vote_id": "%s:%s:m%d" % (M.BOARDS[board][1], date.isoformat(), mid)})
    return out


def main(argv):
    out_path = argv[argv.index("--out") + 1] if "--out" in argv else OUT
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set; keeping the last export")
        return 0
    sys.path.insert(0, os.path.join(ROOT, "db", "scripts"))
    from load import connect
    try:
        conn = connect(url)
        with conn.cursor() as cur:
            cur.execute("select to_regclass('agendas.motions')")
            if not cur.fetchone()[0]:
                print("agendas.motions doesn't exist yet (migration 0055); keeping the last export")
                return 0
            data = rows(cur, researched_index())
    except Exception as e:
        print("couldn't read motions (%s); keeping the last export" % e, file=sys.stderr)
        return 1
    doc = {"as_of": dt.date.today().isoformat(),
           "notes": ["Every motion read from official minutes by a Claude model (data/minutes/read_minutes.py), with names "
                     "matched to officeholder-terms. 'auto-checked' votes passed every automatic check (the named votes add up "
                     "to the printed tally, every voter held a seat that day, a quorum voted); 'reviewed' votes were flagged "
                     "and then approved by an admin. Scanned minutes were read with OCR, so check the source page before "
                     "relying on a single vote.",
                     "vote_method: roll_call = each member's vote is printed; unanimous = minutes say unanimous, so every "
                     "member present is recorded yes; no_dissent_recorded = minutes say the motion carried and name no one "
                     "voting no."],
           "votes": data}
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=0, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out_path)
    print("wrote %d votes to %s" % (len(data), os.path.relpath(out_path, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
