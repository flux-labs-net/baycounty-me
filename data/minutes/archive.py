"""
archive.py - list every governing-board minutes file from 2016 on, per source.

The agenda watcher (data/agendas/watch_agendas.py) only looks about 60-120 days back, so older minutes were never
captured. These listers walk each government's archive year by year and return one record per minutes file:

    {"date": date, "url": str, "source": key, "board": board id, "title": str,
     "fetch": None | callable returning (bytes, content type)}

`fetch` is set where the file can't be downloaded from `url` with a plain GET (the Clerk's OnBase search hands out
per-session document ids; BoardDocs serves minutes from a POST). `url` is then a stable public link used as the
document's key, so a rerun recognizes files it already has.

Board ids are fetch_meetings.BOARDS ids (county, schools, pc, pc-cra, pcb, lh, lh-cra, cw, cw-cra, sp, parker, mb).
Only governing boards and their CRAs: planning boards, advisory committees and magistrates are left out.
Where each archive starts, and what's missing, is in README_minutes.md.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "meetings"))
import fetch_meetings as fm  # noqa: E402

FIRST_YEAR = 2016  # data/entities/cutoff.py: nothing before 2016 anywhere on the site
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def _req(url, data=None, ctype=None, ua=None, timeout=90):
    h = {"User-Agent": ua or BROWSER_UA, "Accept": "*/*"}
    if ctype:
        h["Content-Type"] = ctype
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get_content_type()
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:
            last = e
        fm.time.sleep(2 * (attempt + 1))
    raise RuntimeError("%s: %s" % (type(last).__name__, last))


def _text(url, **kw):
    data, _ = _req(url, **kw)
    return data.decode("utf-8", "replace")


def years(first, last):
    return range(max(first, FIRST_YEAR), last + 1)


# ---------------------------------------------------------------------------------------------------------------
# CivicPlus AgendaCenter (Panama City, Callaway, Lynn Haven's old site): one search page per year.

AC = {
    "pc": ("www.panamacity.gov", [(r"community redevelopment|\bCRA\b", "pc-cra"),
                                  (r"city commission|budget hearing|public workshop", "pc")]),
    # Lynn Haven moved to CivicClerk in Aug 2026 (the watcher covers that); the old AgendaCenter keeps 2016-2026.
    "lh": ("www.cityoflynnhaven.gov", [(r"advisory", None), (r"community redevelopment agency board|\bCRA\b", "lh-cra"),
                                       (r"city commission|public workshop", "lh")]),
}


def parse_agendacenter(page, host, cat_map):
    """One AgendaCenter search page -> minutes records (no network)."""
    out = []
    parts = re.split(r'(<div[^>]*id="cat\d+"[^>]*>)', page)
    for i in range(1, len(parts) - 1, 2):
        sec = parts[i + 1]
        hm = re.search(r"<h2[^>]*>(.*?)</h2>", sec, re.S)
        cname = fm.clean(hm.group(1)) if hm else ""
        board = next((b for rx, b in cat_map if re.search(rx, cname, re.I)), None)
        if not board:
            continue
        for row in re.findall(r'<tr[^>]*class="catAgendaRow".*?</tr>', sec, re.S):
            mins = re.search(r'href="([^"]*ViewFile/Minutes/_(\d{2})(\d{2})(\d{4})-\d+[^"]*)"', row)
            if not mins:
                continue
            d = dt.date(int(mins.group(4)), int(mins.group(2)), int(mins.group(3)))
            am = re.search(r'<p>\s*<a[^>]*>(.*?)</a>', row, re.S)
            out.append({"date": d, "url": urllib.parse.urljoin("https://" + host, mins.group(1)), "board": board,
                        "title": fm.clean(am.group(1)) if am else cname, "fetch": None})
    return out


def agendacenter(key, first, last):
    host, cat_map = AC[key]
    out = []
    for y in years(first, last):
        url = ("https://%s/AgendaCenter/Search/?term=&CIDs=all&startDate=01/01/%d&endDate=12/31/%d&dateRange=&dateSelector="
               % (host, y, y))
        for r in parse_agendacenter(_text(url), host, cat_map):
            r["source"] = key
            out.append(r)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Callaway: the Archive Center keeps every Board of Commissioners minutes file back to 2010 (module 35) and the CRA's
# (module 38); its AgendaCenter only starts in 2021, so the Archive Center is used for every year. A meeting the
# watcher also captured from AgendaCenter is read twice but counted once (export_votes.py keeps one file per meeting).

CW_ARCHIVE = "https://www.cityofcallaway.com/Archive.aspx"
CW_MODULES = {35: "cw", 38: "cw-cra"}


def parse_archive_center(page, board, base=CW_ARCHIVE):
    out = []
    for href, label in re.findall(r'href="(Archive\.aspx\?ADID=\d+)"[^>]*>(.*?)</a>', page, re.S):
        title = fm.clean(label)
        d = fm.parse_date_text(title)
        if not d or re.search(r"planning|workshop only|cancel", title, re.I):
            continue
        out.append({"date": d, "url": urllib.parse.urljoin(base, href), "board": board,
                    "title": fm.DATE_RE.sub("", title).strip(" ,-/") or title, "fetch": None, "source": "cw"})
    return out


def callaway(first, last):
    out = []
    for amid, board in CW_MODULES.items():
        out += [r for r in parse_archive_center(_text("%s?AMID=%d" % (CW_ARCHIVE, amid)), board)
                if max(first, FIRST_YEAR) <= r["date"].year <= last]
    return out


# ---------------------------------------------------------------------------------------------------------------
# Bay County Commission: the Clerk of Court's OnBase Public Access ("BOCC - Minutes Search", query 105). The search
# API answers plain JSON; each hit's document id only works for a while, so the stable key is the search itself.

ONBASE = "https://bayforms.baycoclerk.com/PublicAccess/api"
ONBASE_PAGE = "https://bayforms.baycoclerk.com/PublicAccess/PublicRecordSearch/"
ONBASE_MINUTES = 105


def onbase_search(query_id, year):
    body = json.dumps({"QueryID": query_id, "Keywords": [{"ID": 157, "Value": str(year), "KeywordOperator": "="}],
                       "QueryLimit": 0}).encode()
    data, _ = _req(ONBASE + "/CustomQuery/KeywordSearch", body, "application/json")
    return json.loads(data.decode("utf-8")).get("Data") or []


def onbase_file(doc_id):
    def get():
        return _req("%s/Document/%s/?ViewerMode=PDF" % (ONBASE, urllib.parse.quote(doc_id, safe="")), timeout=180)
    return get


def parse_onbase(hits):
    out = []
    for h in hits:
        cols = [c.get("Value") for c in h.get("DisplayColumnValues") or []]
        d = fm.parse_date_text(cols[0]) if cols else None
        if not d:
            m = re.search(r"Date: (\d{1,2})/(\d{1,2})/(\d{4})", h.get("Name") or "")
            d = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2))) if m else None
        if not d:
            continue
        desc = (cols[2] if len(cols) > 2 else None) or "Minutes"
        key = "%s?minutes=%s&desc=%s" % (ONBASE_PAGE, d.isoformat(), urllib.parse.quote(desc.strip().lower()))
        out.append({"date": d, "url": key, "board": "county", "title": desc.strip().title(), "fetch": onbase_file(h["ID"])})
    return out


def county(first, last):
    out = []
    for y in years(first, last):
        for r in parse_onbase(onbase_search(ONBASE_MINUTES, y)):
            r["source"] = "county"
            out.append(r)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Bay District School Board: BoardDocs (go.boarddocs.com/fl/bcsdfl), Board of Education committee. Minutes are an
# HTML page per meeting (POST BD-GetMinutes). The site starts in 2022; older minutes need a records request.

BD = "https://go.boarddocs.com/fl/bcsdfl/Board.nsf"
BD_COMMITTEE = "A4EP6J588C05"


def boarddocs_file(unique):
    def get():
        body = urllib.parse.urlencode({"id": unique, "current_committee_id": BD_COMMITTEE}).encode()
        data, _ = _req(BD + "/BD-GetMinutes?open", body, "application/x-www-form-urlencoded")
        if len(fm.strip_tags(data.decode("utf-8", "replace"))) < 200:
            raise RuntimeError("no minutes posted for this meeting")
        return data, "text/html"
    return get


def parse_boarddocs(meetings, first, last):
    out, seen = [], set()
    for m in meetings:
        nd = str(m.get("numberdate") or "")
        if not re.match(r"^\d{8}$", nd):
            continue
        d = dt.date(int(nd[:4]), int(nd[4:6]), int(nd[6:]))
        if not (max(first, FIRST_YEAR) <= d.year <= last):
            continue
        name = m.get("name") or ""
        # Each meeting has an "Agenda" and a "Detailed Agenda" entry; the minutes hang off the first one seen.
        if d in seen and not re.search(r"special|workshop|hearing", name, re.I):
            continue
        seen.add(d)
        out.append({"date": d, "url": "%s/goto?open&id=%s" % (BD, m["unique"]), "board": "schools",
                    "title": re.sub(r"\s*(detailed\s+)?agenda$", "", name, flags=re.I) or "School Board Meeting",
                    "fetch": boarddocs_file(m["unique"]), "source": "schools"})
    return out


def schools(first, last):
    body = urllib.parse.urlencode({"current_committee_id": BD_COMMITTEE}).encode()
    data, _ = _req(BD + "/BD-GetMeetingsList?open", body, "application/x-www-form-urlencoded")
    return parse_boarddocs(json.loads(data.decode("utf-8")), first, last)


# ---------------------------------------------------------------------------------------------------------------
# Panama City Beach: Granicus archive (view 1). Council minutes back to 2019; scanned PDFs.

PCB_VIEW = "https://pcbgov.granicus.com/ViewPublisher.php?view_id=1"


def parse_granicus(page):
    out = []
    for row in re.findall(r'<tr class="listingRow".*?</tr>', page, re.S):
        nm = re.search(r'headers="Name"[^>]*>(.*?)</td>', row, re.S)
        name = fm.clean(nm.group(1)) if nm else ""
        if not re.search(r"city council|meeting minutes", name, re.I):
            continue
        dm = re.search(r'headers="Date[^"]*"[^>]*>(.*?)</td>', row, re.S)
        d = fm.parse_date_text(fm.clean(dm.group(1)).split(" - ")[0]) if dm else None
        mm = re.search(r'href="([^"]*MinutesViewer\.php[^"]*)"', row)
        if not (d and mm):
            continue
        url = urllib.parse.urljoin("https://pcbgov.granicus.com/", html.unescape(mm.group(1)))
        out.append({"date": d, "url": url, "board": "pcb", "title": name, "fetch": None, "source": "pcb"})
    return out


def pcb(first, last):
    return [r for r in parse_granicus(_text(PCB_VIEW)) if max(first, FIRST_YEAR) <= r["date"].year <= last]


# ---------------------------------------------------------------------------------------------------------------
# Springfield: the city's meetings view, /meetings/recent?page=N (newest first, back to about 2018).

def parse_springfield(page):
    out = []
    tb = re.search(r"<tbody>(.*?)</tbody>", page, re.S)
    for row in re.findall(r"<tr>(.*?)</tr>", tb.group(1) if tb else "", re.S):
        dm = re.search(r'views-field-field-smart-date">(.*?)</td>', row, re.S)
        tm = re.search(r'views-field-title">(.*?)</td>', row, re.S)
        lm = re.search(r'href="(/media/\d+)" title="PDF Minutes for', row)
        if not (dm and tm and lm):
            continue
        d = fm.parse_date_text(fm.clean(dm.group(1)))
        title = fm.clean(tm.group(1))
        if not d or re.search(r"planning|zoning|board of adjustment|code enforcement|magistrate", title, re.I):
            continue
        out.append({"date": d, "url": fm.SP_BASE + lm.group(1), "board": "sp", "title": title, "fetch": None, "source": "sp"})
    return out


def springfield(first, last):
    out = []
    for page_no in range(0, 40):
        rows = parse_springfield(_text(fm.SP_BASE + "/meetings/recent" + ("?page=%d" % page_no if page_no else "")))
        if not rows:
            break
        out += [r for r in rows if max(first, FIRST_YEAR) <= r["date"].year <= last]
        if min(r["date"].year for r in rows) < max(first, FIRST_YEAR):
            break
    return out


# ---------------------------------------------------------------------------------------------------------------
# Parker: WordPress "filr" minutes table. Meeting minutes from 2020; 2016 and 2017 are one PDF each for the whole
# year (read as several meetings).

def parse_parker(page, first, last):
    out = []
    tm = re.search(r'<table[^>]*id="filr-library-minutes[^"]*"[^>]*>(.*?)</table>', page, re.S)
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(1) if tm else "", re.S):
        t = re.search(r'<td class="title">(.*?)</td>', r, re.S)
        h = re.search(r'href="([^"]+)"', r)
        if not (t and h):
            continue
        title = fm.clean(t.group(1))
        if re.search(r"planning|magistrate|code enforcement|board of adjustment", title, re.I):
            continue
        d = fm.parse_date_text(title)
        ym = re.match(r"^(20\d\d)\s+(official\s+)?minutes$", title, re.I)
        if ym:  # a whole year in one file: dated Dec 31 so it sorts with its year
            d = dt.date(int(ym.group(1)), 12, 31)
        if not d or not (max(first, FIRST_YEAR) <= d.year <= last):
            continue
        out.append({"date": d, "url": html.unescape(h.group(1)), "board": "parker", "title": title, "fetch": None,
                    "source": "parker", "multi": bool(ym)})
    return out


def parker(first, last):
    return parse_parker(_text(fm.PARKER_AM), first, last)


# ---------------------------------------------------------------------------------------------------------------
# Mexico Beach: council meetings page. Its yearly accordion lists every year, but minutes are linked from 2022 on.

def parse_mexico_beach(page, first, last):
    out, seen = [], set()
    im = re.search(r':items="(\[.*?\])"', page, re.S)
    chunks = [page]
    if im:
        chunks += [a.get("content") or "" for a in json.loads(html.unescape(im.group(1)))]
    for ch in chunks:
        for card in re.split(r'<div class="space-y-1 p-6', ch)[1:]:
            tm = re.search(r"<span[^>]*>(.*?)</span>", card, re.S)
            if not tm:
                continue
            title = fm.clean(tm.group(1))
            if re.search(r"planning|zoning|\bP&Z\b|code enforcement", title, re.I):
                continue
            d = fm.parse_date_text(title)
            links = dict((fm.clean(lbl).lower(), href) for href, lbl in re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', card, re.S))
            url = links.get("minutes")
            if not (d and url) or url in seen or not (max(first, FIRST_YEAR) <= d.year <= last):
                continue
            seen.add(url)
            out.append({"date": d, "url": html.unescape(url), "board": "mb", "title": fm.DATE_RE.sub("", title).strip(" ,-") or title,
                        "fetch": None, "source": "mb"})
    return out


def mexico_beach(first, last):
    return parse_mexico_beach(_text(fm.MB_URL), first, last)


# ---------------------------------------------------------------------------------------------------------------

LISTERS = {
    "county": county, "schools": schools, "pcb": pcb, "sp": springfield, "parker": parker, "mb": mexico_beach,
    "pc": lambda a, b: agendacenter("pc", a, b), "cw": callaway,
    "lh": lambda a, b: agendacenter("lh", a, b),
}


def list_minutes(keys=None, first=FIRST_YEAR, last=None, errors=None):
    """-> records for the given source keys (all by default), oldest first. A failing source is skipped and its
    error appended to `errors` (a list), so one broken site doesn't stop the others."""
    last = last or fm.now_central().year
    out = []
    for k in keys or LISTERS:
        try:
            got = LISTERS[k](first, last)
        except Exception as e:
            if errors is not None:
                errors.append((k, "%s: %s" % (type(e).__name__, e)))
            continue
        out += got
    out.sort(key=lambda r: (r["date"], r["source"], r["url"]))
    return out


if __name__ == "__main__":  # quick look: python3 data/minutes/archive.py [keys] [first year]
    import collections
    keys = sys.argv[1].split(",") if len(sys.argv) > 1 else None
    first = int(sys.argv[2]) if len(sys.argv) > 2 else FIRST_YEAR
    errs = []
    recs = list_minutes(keys, first, errors=errs)
    c = collections.Counter((r["board"], r["date"].year) for r in recs)
    for b in sorted({k[0] for k in c}):
        print("%-8s %s" % (b, " ".join("%d:%d" % (y, c[(b, y)]) for y in sorted({k[1] for k in c}) if c[(b, y)])))
    print("%d minutes files" % len(recs))
    for k, e in errs:
        print("ERROR %s: %s" % (k, e))
