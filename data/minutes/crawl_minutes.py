#!/usr/bin/env python3
"""
crawl_minutes.py - capture every governing-board minutes file from 2016 on into the agenda watcher's store.

Lists each archive year by year (archive.py) and hands every file to the watcher's capture step
(data/agendas/watch_agendas.py): downloaded, hashed, versioned, stored in the private "agendas" bucket and listed
on /admin (Agendas tab) as kind "minutes". Files already captured are skipped, so the crawl can be stopped and run
again; read_minutes.py reads whatever has been captured.

Usage:
  python3 data/minutes/crawl_minutes.py --list [--only pc,county] [--from 2016]     # count files, no database
  python3 data/minutes/crawl_minutes.py [--only ...] [--from 2016] [--to 2026] [--max 400]
Environment: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (same as the watcher).
"""
import collections
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "agendas"))
import archive  # noqa: E402
import watch_agendas as wa  # noqa: E402


def arg(argv, name, default=None, cast=str):
    return cast(argv[argv.index(name) + 1]) if name in argv else default


def known_urls(db):
    with db.conn.cursor() as c:
        c.execute("select url from agendas.documents where kind = 'minutes' and current_sha256 is not null")
        return {r[0] for r in c.fetchall()}


def main(argv):
    only = [k for k in (arg(argv, "--only", "") or "").split(",") if k] or None
    first, last = arg(argv, "--from", archive.FIRST_YEAR, int), arg(argv, "--to", None, int)
    cap = arg(argv, "--max", 100000, int)
    errors = []
    recs = archive.list_minutes(only, first, last, errors)
    c = collections.Counter((r["board"], r["date"].year) for r in recs)
    for b in sorted({k[0] for k in c}):
        print("%-8s %s" % (b, " ".join("%d:%d" % (y, c[(b, y)]) for y in sorted({k[1] for k in c}) if c[(b, y)])))
    print("%d minutes files listed" % len(recs))
    for k, e in errors:
        print("ERROR listing %s: %s" % (k, e), file=sys.stderr)
    if "--list" in argv:
        return 1 if errors else 0
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set (use --list to count without a database)", file=sys.stderr)
        return 2
    wa.MAX_DOWNLOADS = cap
    db = wa.DB(url, False)
    run = wa.Run(db, wa.Storage())
    run.start("minutes backfill" + (" (%s)" % ",".join(only) if only else ""))
    for k, e in errors:
        run.error("scan", e, k)
    have = known_urls(db)
    todo = [r for r in recs if wa.canonical(r["url"]) not in have]
    print("%d already captured, %d to fetch%s" % (len(recs) - len(todo), len(todo), " (first %d this run)" % cap if len(todo) > cap else ""))
    fatal = None
    try:
        for r in reversed(todo[-cap:] if cap < len(todo) else todo):   # newest first, like the watcher
            if r.get("fetch"):
                try:
                    data, ctype = r["fetch"]()
                except Exception as e:
                    run.counts["failed"] += 1
                    run.error("download", e, r["source"], r["url"])
                    continue
                run.capture(r["url"], r["source"], "minutes", r["board"], r["title"], r["date"], data=data, ctype=ctype)
            else:
                run.capture(r["url"], r["source"], "minutes", r["board"], r["title"], r["date"])
    except Exception as e:
        fatal = "%s: %s" % (type(e).__name__, e)
        run.error("run", fatal)
    run.finish(fatal)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
