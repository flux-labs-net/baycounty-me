#!/usr/bin/env python3
"""export_name_decisions.py - write data/entities/name_decisions.json from the admin's calls on look-alike business names,
and data/dupes/decisions.json from the calls on posts that may be listed twice (kind 'repeat', migration 0079; read by
data/dupes.py).

/admin > Name matches stores each call in name_match_reviews (migration 0059, api/_name_matches.js): confirmed = the two names
are one company, rejected = keep them apart. build_entities.py reads this file (name_match.decisions()) and joins or
separates the names in vendors.json, name_joins.json and everything built from them.

Run by the daily meetings refresh before data/build.py. Reviewer emails are not written to the repository, only the date.
A database problem keeps the last export.
Usage: DATABASE_URL=... python3 data/entities/export_name_decisions.py
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
OUT = os.path.join(HERE, "name_decisions.json")
REPEATS_OUT = os.path.join(HERE, "..", "dupes", "decisions.json")


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set; keeping the last export")
        return 0
    sys.path.insert(0, os.path.join(ROOT, "db", "scripts"))
    from load import connect
    try:
        conn = connect(url)
        with conn.cursor() as cur:
            cur.execute("select to_regclass('public.name_match_reviews')")
            if not cur.fetchone()[0]:
                print("name_match_reviews doesn't exist yet (migration 0059); keeping the last export")
                return 0
            cur.execute("select 1 from information_schema.columns where table_name = 'name_match_reviews' and column_name = 'kind'")
            kind = "kind" if cur.fetchone() else "'name'"
            cur.execute("select a_key, b_key, a_name, b_name, status, reviewed_at, %s from name_match_reviews order by a_key, b_key" % kind)
            rows = cur.fetchall()
    except Exception as e:
        print("couldn't read name_match_reviews (%s); keeping the last export" % e, file=sys.stderr)
        return 1
    doc = {"about": "Admin calls on look-alike business names from /admin > Name matches. confirmed: one company; rejected: keep apart. "
                    "Read by build_entities.py. Written by export_name_decisions.py.",
           "confirmed": [], "rejected": []}
    rep = {"about": "Admin calls on repeated posts (the same notice, event or job listed twice) from /admin > Name matches. confirmed: one post; "
                    "rejected: keep apart. Read by data/dupes.py and api/_dupes.js. Written by data/entities/export_name_decisions.py.",
           "confirmed": [], "rejected": []}
    for a, b, an, bn, st, at, k in rows:
        (rep if k == "repeat" else doc)[st].append({"a_key": a, "b_key": b, "a_name": an, "b_name": bn, "reviewed_on": at.date().isoformat() if at else None})
    for path, d in ((OUT, doc), (REPEATS_OUT, rep)):
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, path)
    print("wrote %d confirmed and %d rejected name pairs, %d and %d repeated-post calls" % (len(doc["confirmed"]), len(doc["rejected"]), len(rep["confirmed"]), len(rep["rejected"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
