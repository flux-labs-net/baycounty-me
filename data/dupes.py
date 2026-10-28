"""dupes.py - find posts that are the same thing listed twice (a notice re-posted with a small update, a legal notice
published again next week, one event listed by two calendars).

The same rules as api/_dupes.js, so the static pages, the data build and the live API merge the same posts.
api/__tests__/dupes.test.js checks the two agree on data/dupes_cases.json.

How two posts are compared (only when they share a group, such as the same government's alert center, and were posted
within the feed's window):
  title  shared title words, ignoring filler ("notice", "temporarily", "due to"): |A and B| / |A or B|
  body   shared 3-word runs of the text: |A and B| / the shorter text's runs (so "the old text plus a few words" scores 1)
  numbers every number in the shorter post appears in the longer one (an update adds to a post; it doesn't change it)
Verdicts: "same" (merged automatically), "maybe" (listed for review on /admin > Name matches), or None.
A reviewer's call (data/dupes/decisions.json) beats the score either way.
"""
import json
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))

FILLER = set((
    "a an the and or of for to in on at by as is are was be will been from with into until through thru due "
    "notice notices update updated updates alert alerts advisory reminder important please note attention "
    "temporarily temporary currently now new today city county residents customers"
).split())
BODY_SAME = 0.8      # body runs shared, for an automatic merge
TITLE_SAME = 0.85    # title words shared, for an automatic merge (when the bodies don't disagree)
BODY_MAYBE = 0.5     # worth a look
TITLE_MAYBE = 0.6
MIN_BODY_WORDS = 8   # shorter bodies are judged by the title alone
NUM = re.compile(r"\d+")


def words(s):
    return re.findall(r"[a-z0-9]+", str(s or "").lower().replace("’", "'").replace("'", ""))


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def title_words(s):
    return {_stem(w) for w in words(s) if w not in FILLER}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def shingles(ws, n=3):
    return {" ".join(ws[i:i + n]) for i in range(len(ws) - n + 1)}


def containment(a, b):
    """Shared 3-word runs over the shorter text's runs; None when either text is too short to judge."""
    wa, wb = words(a), words(b)
    if min(len(wa), len(wb)) < MIN_BODY_WORDS:
        return None
    sa, sb = shingles(wa), shingles(wb)
    return len(sa & sb) / min(len(sa), len(sb))


def numbers_fit(a, b):
    """Every number in the shorter post (title + body) is also in the longer one."""
    na, nb = [x.lstrip("0") or "0" for x in NUM.findall(a)], [x.lstrip("0") or "0" for x in NUM.findall(b)]
    short, long_ = (na, nb) if len(words(a)) <= len(words(b)) else (nb, na)
    return set(short) <= set(long_)


def compare(a, b, strict_numbers=False):
    """a, b: dicts with title, body (optional), place (optional), ref (optional). Returns {title, body, numbers, verdict}.
    strict_numbers: posts whose numbers disagree are different posts (legal notices: another parcel, ordinance or bid)."""
    t = jaccard(title_words(a.get("title")), title_words(b.get("title")))
    body = containment(a.get("body"), b.get("body"))
    nums = numbers_fit("%s %s" % (a.get("title") or "", a.get("body") or ""), "%s %s" % (b.get("title") or "", b.get("body") or ""))
    out = {"title": t, "body": body, "numbers": nums, "verdict": None}
    if a.get("place") and b.get("place") and str(a["place"]).lower() != str(b["place"]).lower():
        return out  # one title in two towns is two things
    if (a.get("ref") and b.get("ref") and a["ref"] != b["ref"]):
        return out  # two job requisitions, two openings
    if nums and ((body is not None and body >= BODY_SAME) or (t >= TITLE_SAME and (body is None or body >= BODY_MAYBE))):
        out["verdict"] = "same"
    elif strict_numbers and not nums:
        pass
    elif (body is not None and (body >= BODY_SAME or (body >= BODY_MAYBE and t >= TITLE_MAYBE))) or (body is None and t >= TITLE_MAYBE):
        out["verdict"] = "maybe"
    return out


def _ts(v):
    if not v:
        return None
    s = str(v).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s if "T" in s or " " in s else s + "T00:00:00")
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def _r2(x):
    return int(x * 100 + 0.5) / 100


def pair_key(a, b):
    return (a, b) if a < b else (b, a)


def decision_sets(d):
    """{confirmed: [{a_key, b_key}], rejected: [...]} -> {"same": {pair}, "apart": {pair}}."""
    d = d or {}
    return {"same": {pair_key(x["a_key"], x["b_key"]) for x in d.get("confirmed", [])},
            "apart": {pair_key(x["a_key"], x["b_key"]) for x in d.get("rejected", [])}}


def load_decisions(path=None):
    """Reviewer calls on repeated posts from /admin > Name matches (data/entities/export_name_decisions.py)."""
    path = path or os.path.join(HERE, "dupes", "decisions.json")
    try:
        with open(path) as f:
            return decision_sets(json.load(f))
    except (OSError, ValueError):
        return decision_sets({})


# Possible repeats from the last find() for each named feed, for /admin > Name matches (site/repeats.py writes them out).
REVIEW = {}


def _side(it):
    return {"key": it["id"], "names": [it.get("title") or it["id"]], "source": it.get("source"), "posted": it.get("when"),
            "url": it.get("url"), "text": (it.get("body") or "")[:280] or None}


def find(items, window_hours=72, decisions=None, strict_numbers=False, feed=None):
    """items: dicts with id, group, when, title, body?, place?, ref?, rank? (lower is kept first), and for review: source?, url?.
    feed: a name ("notices", "events"...) to keep the possible repeats in REVIEW for the admin review list.
    Returns {"groups": [[id, ...] newest first, ...] (2+ posts each), "maybe": [{a, b, title, body}],
             "same_as": {id: kept id} for every post folded into another}."""
    if not decisions or "same" not in decisions:
        decisions = decision_sets(decisions)
    by = {}
    for it in items:
        by.setdefault(str(it.get("group") or ""), []).append(it)
    parent = {it["id"]: it["id"] for it in items}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    maybe = []
    win = window_hours * 3600
    for _, rows in sorted(by.items()):
        rows = sorted(rows, key=lambda r: (_ts(r.get("when")) or 0, r["id"]))
        for i, a in enumerate(rows):
            ta = _ts(a.get("when"))
            for b in rows[i + 1:]:
                tb = _ts(b.get("when"))
                if ta is not None and tb is not None and tb - ta > win:
                    break
                k = pair_key(a["id"], b["id"])
                if k in decisions["apart"]:
                    continue
                c = compare(a, b, strict_numbers)
                if k in decisions["same"] or c["verdict"] == "same":
                    parent[root(a["id"])] = root(b["id"])
                elif c["verdict"] == "maybe":
                    maybe.append({"a": k[0], "b": k[1], "title": _r2(c["title"]), "body": None if c["body"] is None else _r2(c["body"])})
    clusters = {}
    for it in items:
        clusters.setdefault(root(it["id"]), []).append(it)
    groups, same_as = [], {}
    for members in clusters.values():
        if len(members) < 2:
            continue
        # the kept post: the lowest rank (a feed's own preference, e.g. a city's calendar over an aggregator), then the newest
        members.sort(key=lambda r: (-(r.get("rank") or 0), _ts(r.get("when")) or 0, r["id"]), reverse=True)
        groups.append([m["id"] for m in members])
        for m in members[1:]:
            same_as[m["id"]] = members[0]["id"]
    in_group = {i for g in groups for i in g}
    maybe = [m for m in maybe if not (m["a"] in in_group and m["b"] in in_group and same_as.get(m["a"], m["a"]) == same_as.get(m["b"], m["b"]))]
    groups.sort()
    if feed:
        by_id = {it["id"]: it for it in items}
        REVIEW[feed] = [{"a": _side(by_id[m["a"]]), "b": _side(by_id[m["b"]]), "title": m["title"], "body": m["body"]} for m in maybe]
    return {"groups": groups, "maybe": maybe, "same_as": same_as}


# Emergency notices: one government's alert center or news feed, posted within 3 days. Weather alerts, FL511 and shelter
# notices keep their own ids for one event, so they aren't compared (api/_dupes.js NOTICE_SKIP).
NOTICE_SKIP = {"nws", "fl511", "shelters"}


def notice_item(n):
    return {"id": n["notice_id"], "group": "%s" % (n.get("gov_id") or n.get("source")), "when": n.get("issued") or n.get("updated") or n.get("first_seen"),
            "title": n.get("title"), "body": n.get("summary")}


def notice_groups(notices, decisions=None, feed=None):
    items = [dict(notice_item(n), source=n.get("source"), url=n.get("url")) for n in notices if n.get("source_type") not in NOTICE_SKIP]
    return find(items, window_hours=72, decisions=decisions, feed=feed)


def mark(rows, result, id_key, when_key):
    """Adds same_as (the kept row's id, on rows folded into another) and first_posted (the earliest version's time, on kept
    rows posted more than once) to dataset rows, in place."""
    by = {r[id_key]: r for r in rows}
    first = {}
    for g in result["groups"]:
        whens = sorted(str(by[i].get(when_key)) for i in g if by.get(i) and by[i].get(when_key))
        first[g[0]] = whens[0] if whens else None
    for r in rows:
        r["same_as"] = result["same_as"].get(r[id_key])
        r["first_posted"] = first.get(r[id_key])
    return rows
