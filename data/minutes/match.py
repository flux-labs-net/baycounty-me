"""
match.py - turn motions read from minutes into member votes, and check them.

Pure functions, no network or database (tested in tests/test_match.py).

1. Roster: who held a voting seat on the board on the meeting date, from data/civic/officeholders.json (the
   officeholder-terms dataset). CRA boards are the city commission sitting as the CRA, so they use its roster.
2. Names: the minutes say "Commissioner Rader", "Mr. Dozier", "Mayor Brudnicki" or an OCR'd "Kadv". Each printed
   name is matched to a roster member by last name (fuzzy, for OCR errors), using the first name when two members
   share a last name.
3. Votes: named yes/no/abstain/absent votes are used as printed. When the minutes say only "carried unanimously"
   (or "carried" with no dissent named), every member present at roll call is recorded yes, and anyone named as
   voting no is recorded no. Members listed absent at roll call are absent.
4. Checks: a motion passes when the named votes add up to the printed tally, every voter held a seat that day, a
   quorum voted, and the outcome agrees with the count. Anything else is flagged for review in /admin.
"""
import datetime as dt
import difflib
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OFFICEHOLDERS = os.path.join(HERE, "..", "civic", "officeholders.json")

# fetch_meetings board id -> (officeholders gov_id, votes.json body id, display name)
BOARDS = {
    "county": ("county", "bay-bocc", "Bay County Commission"),
    "schools": ("schools", "bds-board", "Bay District School Board"),
    "pc": ("pc", "pc-commission", "Panama City Commission"),
    "pc-cra": ("pc", "pc-cra", "Panama City CRA Board"),
    "pcb": ("pcb", "pcb-council", "Panama City Beach Council"),
    "lh": ("lh", "lh-commission", "Lynn Haven Commission"),
    "lh-cra": ("lh", "lh-cra", "Lynn Haven CRA Board"),
    "cw": ("cw", "cw-commission", "Callaway Commission"),
    "cw-cra": ("cw", "cw-cra", "Callaway CRA Board"),
    "sp": ("sp", "sp-commission", "Springfield Commission"),
    "parker": ("parker", "parker-council", "Parker Council"),
    "mb": ("mb", "mb-council", "Mexico Beach Council"),
}
NON_VOTING = re.compile(r"superintendent|manager|administrator|clerk|attorney", re.I)
APPROX_DAYS = 75          # slack around a term date marked approximate
SAMPLE_RATE = 50          # 1 in 50 passing motions is also sent to review, to measure the error rate

TITLES = re.compile(r"(?i)\b(commissioners?|councilm[ae]n|councilwom[ae]n|council\s*members?|board\s*members?|members?|"
                    r"vice[\s-]*(chair(man|woman|person)?|mayor)|chair(man|woman|person)?|mayor(\s+pro[\s-]*tem(pore)?)?|"
                    r"pro[\s-]*tem|mr|mrs|ms|miss|dr|hon(orable)?|school\s*board|superintendent)\b\.?")


def _d(s):
    return dt.date.fromisoformat(s) if s else None


_CACHE = {}


def load_officeholders(path=OFFICEHOLDERS):
    if path not in _CACHE:
        with open(path) as f:
            _CACHE[path] = json.load(f)
    return _CACHE[path]


def roster(board, date, data=None):
    """-> list of {name, seat, approx} holding a voting seat on `board` on `date` (a date or ISO string)."""
    data = data or load_officeholders()
    gov = BOARDS.get(board, (board,))[0]
    date = _d(date) if isinstance(date, str) else date
    out = []
    for g in data.get("governments") or []:
        if g.get("gov_id") != gov:
            continue
        for s in g.get("seats") or []:
            if s.get("appointed") or NON_VOTING.search(s.get("seat") or ""):
                continue
            for t in s.get("terms") or []:
                if not t.get("name"):
                    continue
                start, end = _d(t.get("start")), _d(t.get("end"))
                slack_s = dt.timedelta(days=APPROX_DAYS if t.get("start_approx") else 0)
                slack_e = dt.timedelta(days=APPROX_DAYS if t.get("end_approx") else 0)
                if (start is None or start - slack_s <= date) and (end is None or date < end + slack_e):
                    out.append({"name": t["name"], "seat": s.get("seat"),
                                "approx": bool((start and date < start) or (end and date >= end))})
    return out


def everyone(board, data=None):
    """Every name that ever held a voting seat on the board's government (for off-term matches)."""
    data = data or load_officeholders()
    gov = BOARDS.get(board, (board,))[0]
    return sorted({t["name"] for g in data.get("governments") or [] if g.get("gov_id") == gov
                   for s in g.get("seats") or [] if not s.get("appointed") and not NON_VOTING.search(s.get("seat") or "")
                   for t in s.get("terms") or [] if t.get("name")})


def norm(name):
    s = TITLES.sub(" ", name or "")
    s = re.sub(r"[^A-Za-z' -]", " ", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().lower()


def _parts(full):
    p = norm(full).split()
    return (p[0] if p else ""), (p[-1] if p else "")


def _one_edit(a, b):
    """True when a and b differ by at most one substitution, insertion or deletion (a typical OCR slip)."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    return any(a == b[:i] + b[i + 1:] for i in range(len(b)))


def _sim(a, b):
    if len(a) >= 4 and len(b) >= 4 and _one_edit(a, b):
        return max(0.8, difflib.SequenceMatcher(None, a, b).ratio())
    return difflib.SequenceMatcher(None, a, b).ratio()


def resolve(printed, names):
    """Printed name -> one of `names`, or None. Last name first (fuzzy for OCR), then the first name or initial
    when two people share a last name."""
    n = norm(printed)
    if not n:
        return None
    toks = n.split()
    last = toks[-1]
    first = toks[0] if len(toks) > 1 else ""
    scored = []
    for full in names:
        f, l = _parts(full)
        s = 1.0 if l == last else _sim(l, last)
        # Some printed names are first names only ("Ginger"), or the last name is first token in OCR noise
        if s < 0.8 and len(toks) == 1 and (f == last or _sim(f, last) >= 0.9):
            s = 0.85
        if s >= 0.8:
            if first and f:
                if f == first or (len(first) == 1 and f.startswith(first)) or _sim(f, first) >= 0.75 or f.startswith(first[:3]):
                    s += 0.2
                else:
                    s -= 0.1   # a different first name: still a match if nobody else fits
            scored.append((s, full))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.1:
        return None  # two members fit equally well
    return scored[0][1]


TALLY = re.compile(r"(\d+)\s*(?:-|–|—|to|/)\s*(\d+)")


def parse_tally(text):
    """'5-0', 'passed 4 to 1', 'by a 3/2 vote' -> (yes, no) or None."""
    m = TALLY.search(text or "")
    if not m:
        return None
    y, n = int(m.group(1)), int(m.group(2))
    return (y, n) if y <= 15 and n <= 15 else None


def member_votes(motion, meeting, board, date, data=None):
    """-> (votes {canonical name: yes|no|abstain|absent}, method, problems [str], unmatched [printed names])."""
    seats = roster(board, date, data)
    names = [s["name"] for s in seats]
    allnames = everyone(board, data)
    problems, unmatched = [], []

    def canon(printed):
        c = resolve(printed, names)
        if c:
            return c
        c = resolve(printed, allnames)
        if c:
            problems.append("off_term")   # held a seat on this body, but not on this date per officeholder-terms
            return c
        unmatched.append(printed)
        return None

    present = {c for c in (canon(p) for p in meeting.get("present") or []) if c}
    absent = {c for c in (canon(p) for p in meeting.get("absent") or []) if c}
    votes = {}
    for key, val in (("yes", "yes"), ("no", "no"), ("abstain", "abstain"), ("absent", "absent")):
        for p in motion.get(key) or []:
            c = canon(p)
            if c:
                votes[c] = val
    named = any(motion.get(k) for k in ("yes", "no"))
    if named and not motion.get("unanimous"):
        method = "roll_call"
    elif motion.get("unanimous"):
        method = "unanimous"
    elif motion.get("outcome") == "passed" and not motion.get("no"):
        method = "no_dissent_recorded"
    else:
        method = "outcome_only"
    if method != "roll_call" and method != "outcome_only":
        voters = (present or (set(names) - absent)) - absent
        for c in voters:
            votes.setdefault(c, "yes")
    for c in absent:
        votes.setdefault(c, "absent")
    if method == "roll_call" and motion.get("no") and not motion.get("yes"):
        # "passed 3-2, Pelletier and Griggs dissenting": only the no votes are named. When the printed count says the
        # rest of the members there voted yes, record them as yes; otherwise leave them for the checks to flag.
        t = parse_tally(motion.get("tally_text"))
        rest = ((present or set(names)) - absent) - set(votes)
        if t and t[1] == sum(1 for v in votes.values() if v == "no") and len(rest) == t[0]:
            for c in rest:
                votes[c] = "yes"
    if method == "roll_call":
        for c in present - set(votes):
            votes[c] = "absent"   # present at roll call but not in either list: left the room or didn't vote
    return votes, method, sorted(set(problems)), unmatched


def checks(motion, votes, method, board, date, problems, unmatched, data=None, doc_date=None):
    """-> list of failed check codes (empty = passed)."""
    out = list(problems)
    if unmatched:
        out.append("unmatched_name")
    seats = roster(board, date, data)
    y = sum(1 for v in votes.values() if v == "yes")
    n = sum(1 for v in votes.values() if v == "no")
    t = parse_tally(motion.get("tally_text"))
    if t and (y, n) != t:
        out.append("tally_mismatch")
    if method == "outcome_only":
        out.append("no_vote_detail")
    if seats and (y + n) * 2 <= len(seats) and method != "outcome_only":
        out.append("no_quorum")
    if len(seats) and y + n > len(seats):
        out.append("too_many_votes")
    oc = motion.get("outcome")
    if oc == "passed" and y + n and y <= n:
        out.append("outcome_mismatch")
    if oc == "failed" and y > n:
        out.append("outcome_mismatch")
    if oc not in ("passed", "failed"):
        out.append("outcome_unclear")
    if not seats:
        out.append("no_roster")
    if doc_date and date and abs((_d(str(date)) - _d(str(doc_date))).days) > 4:
        out.append("date_mismatch")
    return sorted(set(out))


def tally_text(votes):
    y = sum(1 for v in votes.values() if v == "yes")
    n = sum(1 for v in votes.values() if v == "no")
    return "%d-%d" % (y, n)


def sampled(key):
    """Deterministic 1-in-SAMPLE_RATE pick, so a re-run samples the same motions."""
    return int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % SAMPLE_RATE == 0


def evaluate(motion, meeting, board, doc_date=None, data=None):
    """One motion -> dict with votes, method, tally, checks, check_status, sampled."""
    date = meeting.get("date") or (str(doc_date) if doc_date else None)
    if not date:
        return {"votes": {}, "method": "outcome_only", "tally": None, "checks": ["no_date"], "check_status": "flagged",
                "unmatched": [], "date": None}
    votes, method, problems, unmatched = member_votes(motion, meeting, board, date, data)
    fails = checks(motion, votes, method, board, date, problems, unmatched, data, doc_date if meeting.get("date") else None)
    key = "%s|%s|%s|%s" % (board, date, motion.get("item_number") or "", (motion.get("motion") or "")[:80])
    return {"votes": votes, "method": method, "tally": tally_text(votes) if votes else motion.get("tally_text"),
            "checks": fails, "check_status": "flagged" if fails else "passed", "unmatched": unmatched,
            "sampled": not fails and sampled(key), "date": date}
