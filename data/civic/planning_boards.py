#!/usr/bin/env python3
"""planning_boards.py - build data/civic/planning_boards.json: Bay County's planning and zoning boards and who sits on them.

Each city and the county has an appointed board that holds the first public hearing on rezonings, land-use changes,
site plans and subdivisions (and, for a board of adjustment, variances) and sends a recommendation to the commission
or council, which makes the final decision. Meetings and agendas come from data/meetings/fetch_meetings.py (board ids
match). This file says what each board is and who is on it.

Members come from the government's own public pages and records, newest first:
  - Mexico Beach and Parker list their members on the city website; this script reads those pages on every run.
  - Panama City, Panama City Beach, Lynn Haven and Callaway don't list members online. Their rosters are taken by hand
    from the roll call in the board's latest posted minutes (ROLL_CALLS below, each with the minutes link and date).
    Refresh them when new minutes are posted.
  - Bay County and Springfield publish no member list, agendas or minutes online, so they have no members here.
Only full names the source prints are listed. A member the minutes name by last name only is counted in the board's
note, not listed. Names only: no addresses, phone numbers or emails (Mexico Beach's page lists emails; they are skipped).

Usage: python3 data/civic/planning_boards.py [--out PATH]   (standard library only)
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "planning_boards.json")
UA = "Mozilla/5.0 (compatible; BayCountyMe-PlanningBoards/1.0; +https://baycounty.me)"

BOARDS = [
    {"board_id": "county-planning", "gov_id": "county", "name": "Bay County Planning Commission", "kind": "planning",
     "also": "Local planning agency for unincorporated Bay County",
     "recommends_to": "Board of County Commissioners", "appointed_by": "Board of County Commissioners",
     "page_url": "https://www.baycountyfl.gov/276/Planning-Zoning",
     "records_online": "Meeting dates only (County calendar). Agendas, minutes and members are not posted online; rezonings reach the County Commission's agendas after the hearing."},
    {"board_id": "pc-planning", "gov_id": "pc", "name": "Panama City Planning Board", "kind": "planning",
     "also": "Local planning agency", "recommends_to": "City Commission", "appointed_by": "City Commission",
     "page_url": "https://www.panamacity.gov/241/Planning-Board",
     "records_online": "Agendas and minutes in the city's Agenda Center."},
    {"board_id": "pcb-planning", "gov_id": "pcb", "name": "Panama City Beach Planning Board", "kind": "planning",
     "recommends_to": "City Council", "appointed_by": "City Council", "seats": 7,
     "page_url": "https://pcbgov.granicus.com/ViewPublisher.php?view_id=1",
     "records_online": "Agendas, packets, minutes and video in the city's Granicus archive."},
    {"board_id": "lh-planning", "gov_id": "lh", "name": "Lynn Haven Planning Commission", "kind": "planning",
     "recommends_to": "City Commission", "appointed_by": "City Commission", "seats": 7, "term_years": 4,
     "page_url": "https://www.cityoflynnhaven.gov/300/Planning-Commission",
     "records_online": "Agendas on CivicClerk; older agendas and minutes in the city's Agenda Center."},
    {"board_id": "lh-boa", "gov_id": "lh", "name": "Lynn Haven Board of Adjustment", "kind": "adjustment",
     "recommends_to": "City Commission", "appointed_by": "City Commission", "seats": 5, "term_years": 3,
     "page_url": "https://www.cityoflynnhaven.gov/296/Board-of-Adjustment",
     "records_online": "Agendas and minutes in the city's Agenda Center; meets only when there is a variance request."},
    {"board_id": "cw-planning", "gov_id": "cw", "name": "Callaway Planning Board", "kind": "planning",
     "recommends_to": "City Commission", "appointed_by": "City Commission", "seats": 7, "term_years": 3,
     "page_url": "https://www.cityofcallaway.com/160/Planning-Board",
     "records_online": "Agendas and minutes in the city's Agenda Center."},
    {"board_id": "sp-planning", "gov_id": "sp", "name": "Springfield Planning Board", "kind": "planning",
     "recommends_to": "City Commission", "appointed_by": "City Commission", "seats": 5,
     "page_url": "https://www.springfieldfl.net/ordinance/planning-board-increase-3-5-members",
     "records_online": "Set up by city ordinance (later raised from 3 to 5 members). The city posts no Planning Board meetings, agendas or members online."},
    {"board_id": "parker-planning", "gov_id": "parker", "name": "Parker Planning Commission", "kind": "planning",
     "recommends_to": "City Council", "appointed_by": "City Council",
     "page_url": "https://cityofparker.com/government/planning-commission/",
     "records_online": "Agendas and some minutes on the city's Agendas & Minutes page; members on the Planning Commission page."},
    {"board_id": "mb-planning", "gov_id": "mb", "name": "Mexico Beach Planning & Zoning Board", "kind": "planning",
     "recommends_to": "City Council", "appointed_by": "City Council", "seats": 5, "alternates": 2,
     "page_url": "https://mexicobeachfl.gov/government/planning-zoning/",
     "records_online": "Members, posts and terms on the city's Planning & Zoning page; agendas, minutes and video on the Council Meetings page."},
]

# Rosters read by hand from the roll call in each board's latest posted minutes (checked 2026-11-06).
ROLL_CALLS = {
    "pc-planning": {
        "as_of": "2026-09-14", "source_title": "Panama City Planning Board minutes, September 2026 meeting (roll call)",
        "source_url": "https://www.panamacity.gov/AgendaCenter/ViewFile/Minutes/_09142026-907",
        "members": [("Brian Neubauer", "Chair"), ("Aaron Rich", "Member"), ("James Barker", "Member"),
                    ("Lynn Cherry", "Member"), ("Nicholas Trudell", "Member")]},
    "cw-planning": {
        "as_of": "2026-10-20", "source_title": "Callaway Planning Board minutes, October 20, 2026 (roll call)",
        "source_url": "https://www.cityofcallaway.com/AgendaCenter/ViewFile/Minutes/_10202026-426",
        "members": [("James Dougall", "Chair"), ("Spring Overway", "Vice Chair"), ("Paul Bohac", "Member"),
                    ("James Cormier", "Member"), ("Teddy Conte", "Member"), ("Don Hennings", "Member"),
                    ("Teresa Langston", "Member")]},
    "lh-planning": {
        "as_of": "2026-06-02", "source_title": "Lynn Haven Planning Commission minutes, June 2, 2026 (roll call)",
        "source_url": "https://www.cityoflynnhaven.gov/AgendaCenter/ViewFile/Minutes/_06022026-1337",
        "members": [("Erik Nolte", "Chair"), ("Chad Evans", "Vice Chair"), ("Joseph Ashbrook", "Member"),
                    ("Christopher Clubbs", "Member"), ("Morgan Doolittle", "Member")],
        "note": ("Robert Waddell and Aaron White, also on the June 2026 roll call, have resigned. The City Commission's "
                 "October 13, 2026 consent agenda proposed Carly Weaver and Jacob Durrance for their seats; they are not "
                 "listed until minutes confirm the appointments."),
        "note_url": "https://lynnhavenfl.api.civicclerk.com/v1/Meetings/GetMeetingFileStream(fileId=1136,plainText=false)"},
    "lh-boa": {
        "as_of": "2025-02-20", "source_title": "Lynn Haven Board of Adjustment minutes, February 20, 2025 (roll call)",
        "source_url": "https://www.cityoflynnhaven.gov/AgendaCenter/ViewFile/Minutes/_02202025-864",
        "members": [("Jerry Whitworth", "Chair"), ("Morgan Doolittle", "Member"), ("Douglas C. Pennington", "Member"),
                    ("Christopher Clubbs", "Member")],
        "note": "A fifth member, Ms. Boyanov, is named by last name only in the minutes. The board last posted minutes in February 2025."},
    "pcb-planning": {
        "as_of": "2026-11-12", "source_title": "Panama City Beach Planning Board agenda packet, November 12, 2026 (minutes and officer item)",
        "source_url": "https://d3n9y02raazwpg.cloudfront.net/pcbgov/d1a7f16c-3289-11f1-bb28-005056a89546-aebf6d52-58a9-4341-a472-98e656509a29-1793824316.pdf",
        "members": [("Josh Wakstein", "Chair"), ("Jason Morehouse", "Vice Chair")],
        "note": ("The minutes name the other five members by last name only (Mr. Bishop, Mr. Coleman, Mr. Painter, "
                 "Mr. Thomas and Mr. Wittstruck), so they are not listed by name.")},
}

PARKER_URL = "https://cityofparker.com/government/planning-commission/"
MB_URL = "https://mexicobeachfl.gov/government/planning-zoning/"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def lines(page):
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page))
    return [l.strip() for l in text.split("\n") if l.strip()]


def name_case(s):
    """'ANN PALRANG' -> 'Ann Palrang'; names already in mixed case are kept."""
    s = re.sub(r"\s+", " ", s).strip(" ,")
    if s.upper() != s:
        return s
    return " ".join(w[:1] + w[1:].lower() if not re.match(r"^(II|III|IV)$", w) else w for w in s.split())


def parker(today):
    """Members listed on the Parker Planning Commission page: NAME, then 'Planning Commissioner'."""
    L = lines(fetch(PARKER_URL))
    out = []
    for i, l in enumerate(L[:-1]):
        nxt = L[i + 1]
        if re.match(r"^planning (commissioner|commission chair|chair)", nxt, re.I) and re.match(r"^[A-Za-z .'-]{4,40}$", l):
            role = "Chair" if re.search(r"chair", nxt, re.I) and not re.search(r"vice", nxt, re.I) else "Vice Chair" if re.search(r"vice", nxt, re.I) else "Member"
            out.append({"name": name_case(l), "role": role, "seat": None, "term_end": None})
    return {"as_of": today, "source_title": "Parker Planning Commission page (city website)", "source_url": PARKER_URL, "members": out}


def mexico_beach(today):
    """'Board Members' on the Mexico Beach Planning & Zoning page: 'Name[ - Board Chairman],', 'Post N' or
    'Alternate Post N', 'Term ends <date>'."""
    L = lines(fetch(MB_URL))
    if "Board Members" not in L:
        raise ValueError("no 'Board Members' heading on " + MB_URL)
    L = L[L.index("Board Members") + 1:]
    out = []
    for i, l in enumerate(L[:-1]):
        post = re.match(r"^(Alternate )?Post (\d+)$", L[i + 1])
        if not post:
            continue
        nm, _, title = l.rstrip(",").partition(" - ")
        term = None
        if i + 2 < len(L):
            tm = re.match(r"^Term ends (.+)$", L[i + 2])
            if tm:
                try:
                    term = dt.datetime.strptime(tm.group(1).strip(), "%B %d, %Y").date().isoformat()
                except ValueError:
                    term = None
        role = ("Alternate" if post.group(1) else "Chair" if re.search(r"chair", title, re.I) and not re.search(r"vice", title, re.I)
                else "Vice Chair" if re.search(r"vice", title, re.I) else "Member")
        out.append({"name": name_case(nm), "role": role, "seat": L[i + 1], "term_end": term})
    return {"as_of": today, "source_title": "Mexico Beach Planning & Zoning page (city website)", "source_url": MB_URL, "members": out}


def main(argv):
    out_path = argv[argv.index("--out") + 1] if "--out" in argv else OUT
    today = dt.date.today().isoformat()
    old = {}
    if os.path.exists(out_path):
        old = {m["board_id"]: m for m in json.load(open(out_path)).get("rosters", [])}
    rosters, errors = [], []
    for bid, fn in (("parker-planning", parker), ("mb-planning", mexico_beach)):
        try:
            r = fn(today)
            if not r["members"]:
                raise ValueError("no members found")
            rosters.append(dict(board_id=bid, from_page=True, **r))
        except Exception as e:  # keep the last good roster when a page can't be read
            errors.append({"board_id": bid, "error": repr(e)[:300]})
            if bid in old:
                rosters.append(old[bid])
    for bid, r in ROLL_CALLS.items():
        rosters.append({"board_id": bid, "from_page": False, "as_of": r["as_of"], "source_title": r["source_title"],
                        "source_url": r["source_url"], "note": r.get("note"), "note_url": r.get("note_url"),
                        "members": [{"name": n, "role": role, "seat": None, "term_end": None} for n, role in r["members"]]})
    order = {b["board_id"]: i for i, b in enumerate(BOARDS)}
    rosters.sort(key=lambda r: order[r["board_id"]])
    doc = {"generated": today, "boards": BOARDS, "rosters": rosters, "errors": errors}
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out_path)
    print("wrote %s: %d boards, %d members, %d errors" % (out_path, len(BOARDS), sum(len(r["members"]) for r in rosters), len(errors)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
