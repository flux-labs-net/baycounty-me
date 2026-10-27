#!/usr/bin/env python3
"""export_name_decisions.py - write data/entities/name_decisions.json from the admin's calls on look-alike business names.

/admin > Name matches stores each call in name_match_reviews (migration 0059, api/_names.js): confirmed = the two names
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
            cur.execute("select a_key, b_key, a_name, b_name, status, reviewed_at from name_match_reviews order by a_key, b_key")
            rows = cur.fetchall()
    except Exception as e:
        print("couldn't read name_match_reviews (%s); keeping the last export" % e, file=sys.stderr)
        return 1
    doc = {"about": "Admin calls on look-alike business names from /admin > Name matches. confirmed: one company; rejected: keep apart. "
                    "Read by build_entities.py. Written by export_name_decisions.py.",
           "confirmed": [], "rejected": []}
    for a, b, an, bn, st, at in rows:
        doc[st].append({"a_key": a, "b_key": b, "a_name": an, "b_name": bn, "reviewed_on": at.date().isoformat() if at else None})
    tmp = OUT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    os.replace(tmp, OUT)
    print("wrote %d confirmed and %d rejected name pairs" % (len(doc["confirmed"]), len(doc["rejected"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
