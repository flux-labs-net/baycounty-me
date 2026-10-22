#!/usr/bin/env python3
"""
fetch_meetings.py - build data/meetings/meetings.json for BayCounty.me.

Collects upcoming public meetings (today .. today+60 days) for Bay County, FL
governing boards from their official public sources, plus the most recent
past meeting per board. Standard library only.

Source tiers, per board:
  1. agenda feed     - an official agenda system (PrimeGov, CivicClerk,
                       CivicPlus AgendaCenter, Granicus RSS, city web pages)
  2. calendar feed   - the government's own website calendar (CivicPlus iCal)
  3. expected        - dates generated from the published regular schedule,
                       only where neither of the above covers a date.
                       Marked "expected": true, never carry an agenda link.

A failure in any one source is recorded in "errors" and never stops the run.

Usage:  python3 data/meetings/fetch_meetings.py [--days 60] [--out PATH]
"""

import datetime as dt
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

UA = ("Mozilla/5.0 (compatible; BayCountyMe-MeetingsBot/1.0; "
      "+https://baycounty.me) Python-urllib")
TIMEOUT = 45
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "meetings.json")

ERRORS = []      # [{"board","source","url","error"}]
SOURCE_LOG = {}  # board id -> {source name: "ok (n)" | "error: ..."}


# --------------------------------------------------------------------------
# time helpers (Bay County is entirely in US Central time)
# --------------------------------------------------------------------------

def _nth_weekday(year, month, weekday, n):
    """n-th (1-based) weekday (Mon=0) of month; n=-1 means last. None if absent."""
    if n == -1:
        d = dt.date(year, month + 1, 1) if month < 12 else dt.date(year + 1, 1, 1)
        d -= dt.timedelta(days=1)
        while d.weekday() != weekday:
            d -= dt.timedelta(days=1)
        return d
    d = dt.date(year, month, 1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    d += dt.timedelta(weeks=n - 1)
    return d if d.month == month else None


def central_offset(d):
    """'-05:00' during CDT, '-06:00' during CST (US rules since 2007)."""
    start = _nth_weekday(d.year, 3, 6, 2)   # 2nd Sunday March
    end = _nth_weekday(d.year, 11, 6, 1)    # 1st Sunday November
    return "-05:00" if start <= d < end else "-06:00"


def iso_local(d, hh=None, mm=0):
    """ISO string with Central offset, or plain date when time is unknown."""
    if hh is None:
        return d.isoformat()
    return "%sT%02d:%02d:00%s" % (d.isoformat(), hh, mm, central_offset(d))


def now_central():
    utc = dt.datetime.now(dt.timezone.utc)
    off = -5 if central_offset(utc.date()) == "-05:00" else -6
    return utc.astimezone(dt.timezone(dt.timedelta(hours=off)))


MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MONTHS["sept"] = 9

DATE_RE = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|"
    r"Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})", re.I)
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?", re.I)


def parse_date_text(s):
    m = DATE_RE.search(s or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), MONTHS[m.group(1).lower()[:3]], int(m.group(2)))
    except (KeyError, ValueError):
        return None


def parse_time_text(s):
    m = TIME_RE.search(s or "")
    if not m:
        return None
    h = int(m.group(1)) % 12
    if m.group(3).lower() == "p":
        h += 12
    return h, int(m.group(2) or 0)


# --------------------------------------------------------------------------
# HTTP + text helpers
# --------------------------------------------------------------------------

def fetch(url, tries=3, accept="*/*"):
    """GET a URL -> str. Retries on network errors / 5xx. Raises on failure."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Accept": accept,
                "Accept-Encoding": "gzip, deflate",
                "Accept-Language": "en-US,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
                if enc == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    raw = zlib.decompress(raw)
                cs = r.headers.get_content_charset() or "utf-8"
                return raw.decode(cs, errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code < 500 and e.code != 429:
                break
        except Exception as e:  # network reset, timeout, TLS...
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("%s: %s" % (type(last).__name__, last))


def fetch_json(url):
    return json.loads(fetch(url, accept="application/json"))


def strip_tags(s, sep=" "):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s or "")
    s = re.sub(r"(?s)<[^>]+>", sep, s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"[ \t\r\f\v]+", " ", s).strip()


def clean(s):
    return re.sub(r"\s+", " ", strip_tags(s)).strip()


def note_error(board, source, url, err):
    ERRORS.append({"board": board, "source": source, "url": url, "error": str(err)[:300]})
    SOURCE_LOG.setdefault(board, {})[source] = "error: %s" % str(err)[:120]


def note_ok(board, source, n):
    SOURCE_LOG.setdefault(board, {})[source] = "ok (%d records)" % n


# --------------------------------------------------------------------------
# money-item extraction
# --------------------------------------------------------------------------

MONEY_KW = re.compile(
    r"\$\s?\d|\bcontracts?\b|\bbids?\b|\bbudget\b|\bmillage\b|\bpurchas\w*|"
    r"\baward\w*|\bchange order\b|\bgrant\b|\bRFP\b|\bRFQ\b|\bITB\b|\bappropriat\w*",
    re.I)
AMOUNT_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?(?:\s?(?:million|thousand))?", re.I)


AGENDA_SKIP = re.compile(
    r"^(call to order|invocation|pledge|roll call|adjourn\w*|approval of (the )?agenda|"
    r"additions?, deletions?|public comment\w*|mayor'?s report|commissioners'? reports?|"
    r"city manager'?s report|city attorney'?s report|reports?)\b", re.I)


def agenda_items(titles, limit=150):
    """Every agenda item title (cleaned, de-duplicated), skipping procedural items.
    Used for keyword alerts (a street name, a vendor) and search; money_items() stays the money subset."""
    out, seen = [], set()
    for t in titles:
        t = re.sub(r"\s+", " ", t or "").strip(" -")
        if len(t) < 6 or AGENDA_SKIP.match(t) or t.startswith("*") or (t.isupper() and len(t) < 45):
            continue   # procedural items and section headings ("CONSENT AGENDA")
        key = t[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t[:400])
        if len(out) >= limit:
            break
    return out


def money_items(titles, limit=60):
    out, seen = [], set()
    for t in titles:
        t = re.sub(r"\s+", " ", t or "").strip()
        if len(t) < 8 or not MONEY_KW.search(t):
            continue
        key = t[:120].lower()
        if key in seen:
            continue
        seen.add(key)
        amts = AMOUNT_RE.findall(t)
        out.append({"title": t[:400], "amount": amts[0].replace(" ", "") if amts else None})
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------
# iCal (CivicPlus website calendars)
# --------------------------------------------------------------------------

def parse_ics(text):
    text = re.sub(r"\r?\n[ \t]", "", text)
    events = []
    for block in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        ev = {}
        for line in block.strip().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            ev[k.split(";")[0].upper()] = v.strip()
        m = re.match(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?", ev.get("DTSTART", ""))
        if not m:
            continue
        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        hh = int(m.group(4)) if m.group(4) else None
        mm = int(m.group(5)) if m.group(5) else 0
        unesc = lambda s: (s or "").replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
        loc = clean(unesc(ev.get("LOCATION", "")))
        loc = re.sub(r"^\s*-\s*", "", loc).strip(" -")
        url = None
        um = re.search(r"https?://\S+calendar\.aspx\?EID=\d+", unesc(ev.get("DESCRIPTION", "")), re.I)
        if um:
            url = um.group(0)
        events.append({"date": d, "hh": hh, "mm": mm, "title": unesc(ev.get("SUMMARY", "")).strip(),
                       "location": loc or None, "url": url})
    return events


def civicplus_ical(board, host, cat_id, title_filter):
    url = "https://%s/common/modules/iCalendar/iCalendar.aspx?catID=%s&feed=calendar" % (host, cat_id)
    out = []
    try:
        for ev in parse_ics(fetch(url)):
            if not re.search(title_filter, ev["title"], re.I):
                continue
            out.append(meeting(board, ev["title"], ev["date"], ev["hh"], ev["mm"],
                               location=ev["location"], source="calendar:" + url,
                               status="calendar", detail_url=ev["url"]))
        note_ok(board, "calendar (iCal cat %s)" % cat_id, len(out))
    except Exception as e:
        note_error(board, "calendar (iCal cat %s)" % cat_id, url, e)
    return out


# --------------------------------------------------------------------------
# meeting record
# --------------------------------------------------------------------------

def meeting(board, title, date, hh=None, mm=0, location=None, agenda_url=None,
            packet_url=None, minutes_url=None, source=None, status="agenda",
            detail_url=None, items=None, cancelled=None, time_from_schedule=False):
    if status == "agenda":
        status = "posted"
    if location and not re.search(r"\b\d{1,5}\s+[A-Za-z]|virtual|live ?stream|zoom", location, re.I):
        location = None   # e.g. bare "Panama City FL 32401" without a venue
    m = {"board": board, "title": re.sub(r"\s+", " ", title or "").strip(),
         "date": date, "hh": hh, "mm": mm, "location": location,
         "agenda_url": agenda_url, "packet_url": packet_url, "minutes_url": minutes_url,
         "detail_url": detail_url, "source": source, "status": status}
    if cancelled is None:
        cancelled = bool(re.search(r"\bcancel+ed\b", m["title"], re.I))
    if cancelled:
        m["cancelled"] = True
    if items:
        m["items"] = items
    if time_from_schedule:
        m["time_from_schedule"] = True
    return m


# --------------------------------------------------------------------------
# Source adapters
# --------------------------------------------------------------------------

PRIMEGOV = "https://baycountyfl.primegov.com"


def src_primegov_bocc(board, today):
    out = []
    raw = []
    for path in ["/api/v2/PublicPortal/ListUpcomingMeetings",
                 "/api/v2/PublicPortal/ListArchivedMeetings?year=%d" % today.year,
                 "/api/v2/PublicPortal/ListArchivedMeetings?year=%d" % (today.year + 1)]:
        try:
            raw.extend(fetch_json(PRIMEGOV + path) or [])
        except Exception as e:
            note_error(board, "PrimeGov", PRIMEGOV + path, e)
    seen = set()
    for r in raw:
        if r.get("id") in seen:
            continue
        seen.add(r.get("id"))
        try:
            st = dt.datetime.fromisoformat(r["dateTime"][:19])
        except Exception:
            continue
        agenda = packet = html_tid = None
        for doc in r.get("documentList") or []:
            tid = doc.get("templateId")
            name = (doc.get("templateName") or "").lower()
            if doc.get("compileOutputType") == 3 or "html" in name:
                html_tid = tid
                agenda = "%s/Portal/Meeting?meetingTemplateId=%s" % (PRIMEGOV, tid)
            elif doc.get("compileOutputType") == 1:
                packet = "%s/Public/CompiledDocument?meetingTemplateId=%s&compileOutputType=1" % (PRIMEGOV, tid)
            if "minutes" in name:
                pass
        m = meeting(board, (r.get("title") or "").strip(), st.date(), st.hour, st.minute,
                    location=(r.get("location") or None) or None,
                    agenda_url=agenda, packet_url=packet,
                    source="PrimeGov:" + PRIMEGOV + "/public/portal",
                    detail_url=r.get("videoUrl"))
        m["_html_template"] = html_tid
        out.append(m)
    note_ok(board, "PrimeGov", len(out))
    return out


def primegov_items(m):
    tid = m.get("_html_template")
    if not tid:
        return None, None, None
    page = fetch("%s/Portal/Meeting?meetingTemplateId=%s" % (PRIMEGOV, tid))
    text = clean(page)
    text = text.replace("Combine item's attachments into one PDF and view", " ")
    titles = []
    for mm_ in re.finditer(r"(?:^|\s)\d{1,2}\.\s+(.{5,200}?)\s+Staff Recommendation:\s*(.{5,500}?)"
                           r"(?=\s+(?:County Commissioner|Background Document|\d{1,2}\.\s|[A-Z]\.\s[A-Z]{3,}))",
                           text):
        titles.append("%s - %s" % (mm_.group(1).strip(), mm_.group(2).strip()))
    loc = None
    lm = re.search(r"(BAY COUNTY GOVERNMENT CENTER\s+840 WEST 11\s*th STREET\s+PANAMA CITY,\s*FLORIDA)", text)
    if lm:
        loc = "Bay County Government Center, 840 W. 11th St., Panama City, FL"
    return money_items(titles), loc, agenda_items(titles)


# ---- CivicClerk (Lynn Haven) ----------------------------------------------

LH_CC_API = "https://lynnhavenfl.api.civicclerk.com/v1"
LH_CC_PORTAL = "https://lynnhavenfl.portal.civicclerk.com"


def src_civicclerk_lh(today, days):
    start = (today - dt.timedelta(days=120)).isoformat()
    end = (today + dt.timedelta(days=days + 1)).isoformat()
    q = urllib.parse.urlencode({
        "$filter": "startDateTime ge %sT00:00:00Z and startDateTime lt %sT00:00:00Z" % (start, end),
        "$orderby": "startDateTime"})
    url = "%s/Events?%s" % (LH_CC_API, q)
    out = {"lh": [], "lh-cra": []}
    events = []
    try:
        nxt, pages = url, 0
        while nxt and pages < 20:          # OData paging (@odata.nextLink)
            data = fetch_json(nxt)
            if isinstance(data, dict):
                events.extend(data.get("value") or [])
                nxt = data.get("@odata.nextLink")
            else:
                events.extend(data or [])
                nxt = None
            pages += 1
    except Exception as e:
        note_error("lh", "CivicClerk", url, e)
        note_error("lh-cra", "CivicClerk", url, e)
        return out
    for ev in events:
        name = ev.get("eventName") or ""
        cat = ev.get("categoryName") or ""
        if re.search(r"\bCRA\b|Redevelopment", name, re.I):
            board = "lh-cra"
        elif cat == "City Commission" or re.search(r"commission (meeting|workshop)|budget (workshop|hearing)|special (commission )?meeting", name, re.I):
            if re.search(r"planning commission|charter", name, re.I):
                continue
            board = "lh"
        else:
            continue
        # CivicClerk stores local wall-clock time with a "Z" suffix.
        s = (ev.get("startDateTime") or "")[:16]
        try:
            st = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M")
        except ValueError:
            continue
        files = ev.get("publishedFiles") or []
        def f(kind):
            for x in files:
                if (x.get("type") or "").lower() == kind:
                    return "%s/v1/Meetings/GetMeetingFileStream(fileId=%s,plainText=false)" % (
                        LH_CC_API.rsplit("/v1", 1)[0], x.get("fileId"))
            return None
        loc = ev.get("eventLocation") or {}
        locs = ", ".join(x for x in [loc.get("address1"), loc.get("city")] if x) or None
        m = meeting(board, name, st.date(), st.hour, st.minute, location=locs,
                    agenda_url=f("agenda"), packet_url=f("agenda packet"), minutes_url=f("minutes"),
                    source="CivicClerk:" + LH_CC_PORTAL,
                    detail_url="%s/event/%s/files" % (LH_CC_PORTAL, ev.get("id")))
        m["_cc_agenda"] = ev.get("agendaId") if ev.get("hasAgenda") else None
        out[board].append(m)
    note_ok("lh", "CivicClerk", len(out["lh"]))
    note_ok("lh-cra", "CivicClerk", len(out["lh-cra"]))
    return out


def civicclerk_plain_titles(url):
    """Numbered items ("12. Resolution ...") from CivicClerk's plain-text agenda file. Continuation lines are joined."""
    text = fetch(url.replace("plainText=false", "plainText=true"))
    titles, cur = [], None
    for line in text.splitlines():
        l = line.strip()
        if not l or l.startswith("**"):
            continue
        mm_ = re.match(r"^(\d{1,2})\.\s+(.*)$", l)
        if mm_:
            if cur:
                titles.append(cur)
            cur = mm_.group(2)
        elif cur is not None and re.match(r"^[A-Z][A-Z &/'-]{3,}$", l):   # section heading ends an item
            titles.append(cur)
            cur = None
        elif cur is not None and not re.match(r"^[A-Z]\.\s", l):
            cur += " " + l
    if cur:
        titles.append(cur)
    # a line that ran two items together ("2027 11. Resolution ...")
    out = []
    for t in titles:
        out.extend(x.strip() for x in re.split(r"\s(?=\d{1,2}\.\s+[A-Z])", t))
    return out


def civicclerk_items(m):
    """(money items, all agenda items). Uses the structured agenda; if it has no items yet, the plain-text agenda file."""
    aid = m.get("_cc_agenda")
    titles = []
    if aid:
        d = fetch_json("%s/Meetings/%s" % (LH_CC_API, aid))

    def walk(items):
        for x in items or []:
            t = clean(x.get("agendaObjectItemName") or "")
            if x.get("agendaObjectItemDescription"):
                t += " - " + clean(x.get("agendaObjectItemDescription"))
            titles.append(t)
            walk(x.get("childItems"))
    if aid:
        walk(d.get("items"))
    if not titles and m.get("agenda_url") and "GetMeetingFileStream" in m["agenda_url"]:
        titles = civicclerk_plain_titles(m["agenda_url"])
    if not aid and not titles:
        return None, None
    return money_items(titles), agenda_items(titles)


# ---- CivicPlus AgendaCenter (Panama City, Callaway) -----------------------

def src_agendacenter(host, today, days, cat_map):
    """cat_map: list of (regex on category name, board id). Returns {board:[...]}."""
    start = (today - dt.timedelta(days=120)).strftime("%m/%d/%Y")
    end = (today + dt.timedelta(days=days)).strftime("%m/%d/%Y")
    url = ("https://%s/AgendaCenter/Search/?term=&CIDs=all&startDate=%s&endDate=%s"
           "&dateRange=&dateSelector=" % (host, start, end))
    boards = {b for _, b in cat_map}
    out = {b: [] for b in boards}
    try:
        page = fetch(url)
    except Exception as e:
        for b in boards:
            note_error(b, "AgendaCenter", url, e)
        return out
    # split into category sections
    parts = re.split(r'(<div[^>]*id="cat\d+"[^>]*>)', page)
    for i in range(1, len(parts) - 1, 2):
        sec = parts[i + 1]
        hm = re.search(r"<h2[^>]*>(.*?)</h2>", sec, re.S)
        cname = clean(hm.group(1)) if hm else ""
        board = next((b for rx, b in cat_map if re.search(rx, cname, re.I)), None)
        if not board:
            continue
        for row in re.findall(r'<tr[^>]*class="catAgendaRow".*?</tr>', sec, re.S):
            dm = re.search(r'id="h4(\d{2})(\d{2})(\d{4})-(\d+)"', row)
            if not dm:
                continue
            d = dt.date(int(dm.group(3)), int(dm.group(1)), int(dm.group(2)))
            am = re.search(r'<p>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
            title = clean(am.group(2)) if am else cname
            href = am.group(1) if am else None
            base = "https://" + host
            agenda = urllib.parse.urljoin(base, href) if href else None
            mins = re.search(r'<td class="minutes">\s*<a[^>]*href="([^"]+)"', row)
            pk = re.search(r'href="([^"]*ViewFile/Agenda/[^"]*packet=true[^"]*)"', row)
            m = meeting(board, title, d, location=None, agenda_url=agenda,
                        packet_url=urllib.parse.urljoin(base, pk.group(1)) if pk else None,
                        minutes_url=urllib.parse.urljoin(base, mins.group(1)) if mins else None,
                        source="AgendaCenter:https://%s/AgendaCenter" % host)
            m["_category"] = cname
            if agenda and "html=true" in agenda:
                m["_html_agenda"] = agenda
            out[board].append(m)
    for b in boards:
        note_ok(b, "AgendaCenter", len(out[b]))
    return out


def agendacenter_html_items(m):
    url = m.get("_html_agenda")
    if not url:
        return None, None, None
    text = strip_tags(fetch(url), sep="\n")
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    titles, cur = [], []
    for l in lines:
        if re.match(r"^\d{1,2}(\.[a-z0-9]+)*\.$", l):
            if cur:
                titles.append(" ".join(cur))
            cur = []
        elif l.startswith("Documents:") or l.lower().endswith(".pdf"):
            if cur:
                titles.append(" ".join(cur))
            cur = []
        else:
            cur.append(l)
    if cur:
        titles.append(" ".join(cur))
    head = " ".join(lines[:12])
    return money_items(titles), parse_time_text(head), agenda_items(titles)


# ---- Granicus (Panama City Beach) -----------------------------------------

PCB_RSS = "https://pcbgov.granicus.com/ViewPublisherRSS.php?view_id=1&mode=agendas"


def src_granicus_pcb():
    out = []
    try:
        root = ET.fromstring(fetch(PCB_RSS).encode("utf-8"))
    except Exception as e:
        note_error("pcb", "Granicus RSS", PCB_RSS, e)
        return out
    ns = {"gran": "https://www.granicus.com/schema/rss-supplements"}
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not re.match(r"city council", title, re.I):
            continue
        tm = re.search(r"-\s*([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})", title)
        if not tm:
            continue
        d = parse_date_text("%s %s, %s" % tm.groups())
        if not d:
            continue
        link = (it.findtext("link") or "").strip()
        hh = mm = None
        archived = "clip_id=" in link
        if archived:
            # for archived clips the feed's pubDate is the meeting start (Pacific)
            parts = it.find("gran:pubDateParts", ns)
            try:
                pdt = dt.datetime.strptime((it.findtext("pubDate") or "")[:25].strip(),
                                           "%a, %d %b %Y %H:%M:%S")
                tz = (it.findtext("pubDate") or "")[26:].strip()
                off = int(tz[:3]) if re.match(r"[+-]\d{4}", tz) else -7
                utc = pdt - dt.timedelta(hours=off)
                coff = -5 if central_offset(d) == "-05:00" else -6
                loc = utc + dt.timedelta(hours=coff)
                if loc.date() == d:
                    hh, mm = loc.hour, loc.minute
            except Exception:
                pass
        m = meeting("pcb", re.sub(r"\s+-\s+.*$", "", title), d, hh, mm or 0,
                    location="City Hall Council Chambers, 17007 Panama City Beach Pkwy, Panama City Beach, FL 32413",
                    agenda_url=link or None, source="Granicus:" + PCB_RSS)
        out.append(m)
    note_ok("pcb", "Granicus RSS", len(out))
    return out


# ---- Parker (WordPress "filr" document library) ---------------------------

PARKER_AM = "https://cityofparker.com/government/agendas-minutes/"


def src_parker():
    out = []
    try:
        page = fetch(PARKER_AM)
    except Exception as e:
        note_error("parker", "Agendas & Minutes page", PARKER_AM, e)
        return out
    def rows(table_id_rx):
        tm = re.search(r'<table[^>]*id="%s"[^>]*>(.*?)</table>' % table_id_rx, page, re.S)
        if not tm:
            return []
        res = []
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(1), re.S):
            t = re.search(r'<td class="title">(.*?)</td>', r, re.S)
            h = re.search(r'href="([^"]+)"', r)
            if t and h:
                res.append((clean(t.group(1)), h.group(1)))
        return res
    minutes = {}
    for title, href in rows(r"filr-library-minutes[^\"]*"):
        d = parse_date_text(title)
        if d and not re.search(r"planning|magistrate", title, re.I):
            minutes.setdefault(d, href)
    for title, href in rows(r"filr-library-agendas[^\"]*"):
        if re.search(r"planning|magistrate|code enforcement|quasi", title, re.I):
            continue
        d = parse_date_text(title)
        if not d:
            continue
        t = parse_time_text(title.split(str(d.year), 1)[-1])
        m = meeting("parker", re.sub(r",?\s*" + DATE_RE.pattern + r".*$", "", title, flags=re.I).strip(" ,") or title,
                    d, t[0] if t else None, t[1] if t else 0,
                    location=None,
                    agenda_url=href, minutes_url=minutes.get(d),
                    source="Parker:" + PARKER_AM)
        m["title"] = re.sub(r"^[*\s]*(updated|amended)?[*\s]*(agenda\s+)?", "", m["title"], flags=re.I) or title
        out.append(m)
    note_ok("parker", "Agendas & Minutes page", len(out))
    return out


# ---- Mexico Beach (city web page) -----------------------------------------

MB_URL = "https://mexicobeachfl.gov/government/council-meetings/"


def src_mexico_beach(today):
    out = []
    try:
        page = fetch(MB_URL)
    except Exception as e:
        note_error("mb", "Council Meetings page", MB_URL, e)
        return out
    chunks = [page]
    im = re.search(r':items="(\[.*?\])"', page, re.S)
    if im:
        try:
            for acc in json.loads(html.unescape(im.group(1))):
                if str(acc.get("title")) in (str(today.year), str(today.year - 1)):
                    chunks.append(acc.get("content") or "")
        except Exception as e:
            note_error("mb", "Council Meetings archive", MB_URL, e)
    seen = set()
    for ch in chunks:
        for card in re.split(r'<div class="space-y-1 p-6', ch)[1:]:
            tm = re.search(r"<span[^>]*>(.*?)</span>", card, re.S)
            if not tm:
                continue
            title = clean(tm.group(1))
            if re.search(r"planning|zoning|\bP&Z\b|code enforcement", title, re.I):
                continue
            d = parse_date_text(title)
            if not d:
                continue
            wm = re.search(r'pb-2"[^>]*>\s*(.*?)</div>', card, re.S)
            t = parse_time_text(clean(wm.group(1))) if wm else None
            links = dict((clean(lbl).lower(), href) for href, lbl in
                         re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', card, re.S))
            key = (d, title.lower())
            if key in seen:
                continue
            seen.add(key)
            name = DATE_RE.sub("", title).strip(" ,-")
            out.append(meeting("mb", name or title, d, t[0] if t else None, t[1] if t else 0,
                               location=None,
                               agenda_url=links.get("agenda"), packet_url=links.get("packet"),
                               minutes_url=links.get("minutes"), source="MexicoBeach:" + MB_URL,
                               detail_url=links.get("video link") or links.get("video")))
    note_ok("mb", "Council Meetings page", len(out))
    return out


# ---- Springfield (CivicPlus HCMS / Drupal meetings view) ------------------

SP_BASE = "https://www.springfieldfl.net"


def src_springfield():
    out = []
    for path in ["/meetings", "/meetings/recent"]:
        url = SP_BASE + path
        try:
            page = fetch(url)
        except Exception as e:
            note_error("sp", "Meetings list " + path, url, e)
            continue
        tb = re.search(r"<tbody>(.*?)</tbody>", page, re.S)
        for row in re.findall(r"<tr>(.*?)</tr>", tb.group(1) if tb else "", re.S):
            dm = re.search(r'views-field-field-smart-date">(.*?)</td>', row, re.S)
            tm = re.search(r'views-field-title">(.*?)</td>', row, re.S)
            if not (dm and tm):
                continue
            dtxt, title = clean(dm.group(1)), clean(tm.group(1))
            d = parse_date_text(dtxt)
            if not d:
                continue
            t = parse_time_text(dtxt.split("|", 1)[-1])
            def link(kind):
                lm = re.search(r'href="(/media/\d+)" title="PDF %s for' % kind, row)
                return SP_BASE + lm.group(1) if lm else None
            vm = re.search(r'href="(/community/meeting/[^"]+)"', row)
            out.append(meeting("sp", title, d, t[0] if t else None, t[1] if t else 0,
                               location="Springfield City Hall Commission Room, 408 School Ave., Springfield, FL",
                               agenda_url=link("Agenda"), packet_url=link("Agenda Packet"),
                               minutes_url=link("Minutes"), source="Springfield:" + url,
                               detail_url=SP_BASE + vm.group(1) if vm else None))
        note_ok("sp", "Meetings list " + path, len(out))
    return out


# ---- Bay District Schools (Apptegy / Thrillshare district calendar) -------
# The district website (bay.k12.fl.us, an Apptegy site) serves a JavaScript bot challenge to scripts, but the
# calendar behind its Events page is Apptegy's public Thrillshare API (organization 31249). School Board meetings
# are posted there with date, time and venue. Agendas are not in the feed: the district posts them on
# bay.k12.fl.us/school-board-meetings, which scripts can't read, so agenda_url stays empty and the board
# meetings page is the link.

BDS_EVENTS = "https://thrillshare-cmsv2.services.thrillshare.com/api/v4/o/31249/cms/events"
BDS_PAGE = "https://www.bay.k12.fl.us/school-board-meetings"


def src_bds_events(today, days):
    out = []
    q = {"start_date": (today - dt.timedelta(days=120)).isoformat(),
         "end_date": (today + dt.timedelta(days=days + 1)).isoformat()}
    url = BDS_EVENTS + "?" + urllib.parse.urlencode(q)
    nxt, pages, events = url, 0, []
    try:
        while nxt and pages < 10:
            d = fetch_json(nxt)
            events.extend(d.get("events") or [])
            links = (d.get("meta") or {}).get("links") or {}
            new = links.get("next")   # absent on the last page
            nxt = new if new and new != nxt else None
            pages += 1
    except Exception as e:
        note_error("schools", "District calendar (Thrillshare)", url, e)
        return out
    seen = set()
    for ev in events:
        title = (ev.get("title") or "").strip()
        if not re.search(r"school board|board meeting|board workshop", title, re.I):
            continue
        if ev.get("id") in seen:
            continue
        seen.add(ev.get("id"))
        try:
            st = dt.datetime.fromisoformat(re.sub(r"\.\d+", "", ev.get("start_at") or ""))
        except ValueError:
            continue
        timed = not ev.get("all_day")
        venue = (ev.get("venue") or ev.get("address") or "").replace(", USA", "").strip() or None
        out.append(meeting("schools", title, st.date(), st.hour if timed else None, st.minute if timed else 0,
                           location=venue, source="Thrillshare:" + BDS_EVENTS, status="calendar",
                           detail_url=BDS_PAGE))
    note_ok("schools", "District calendar (Thrillshare)", len(out))
    return out


# --------------------------------------------------------------------------
# Board catalogue
# --------------------------------------------------------------------------

BOARDS = [
    {"id": "county", "name": "Bay County Board of County Commissioners", "gov": "county",
     "schedule": "Regular meetings at 9:00 a.m., generally the 1st and 3rd Tuesday of the month "
                 "(dates as posted on the County calendar and PrimeGov; budget hearings at 5:01 p.m. in September).",
     "schedule_source_url": "https://www.baycountyfl.gov/common/modules/iCalendar/iCalendar.aspx?catID=38&feed=calendar",
     "location": "Bay County Government Center, 840 W. 11th St., Panama City, FL 32401",
     "source_url": "https://baycountyfl.primegov.com/public/portal",
     "calendar_url": "https://www.baycountyfl.gov/Calendar.aspx"},
    {"id": "county-planning", "name": "Bay County Planning Commission", "gov": "county",
     "schedule": "Monthly; recent posted dates are the 3rd Tuesday at 1:30 p.m. (per the County calendar).",
     "schedule_source_url": "https://www.baycountyfl.gov/common/modules/iCalendar/iCalendar.aspx?catID=26&feed=calendar",
     "location": "Bay County Government Center, 840 W. 11th St., Panama City, FL 32401",
     "source_url": "https://www.baycountyfl.gov/Calendar.aspx",
     "calendar_url": "https://www.baycountyfl.gov/Calendar.aspx"},
    {"id": "schools", "name": "Bay District School Board", "gov": "schools",
     "schedule": "Regular meetings generally the 2nd and 4th Tuesday at 3:00 p.m. at the district office, "
                 "1311 Balboa Ave. (dates and times as posted on the district calendar). Agendas are posted on the "
                 "district's School Board Meetings page.",
     "schedule_source_url": "https://www.bay.k12.fl.us/events",
     "location": "Bay District Schools, 1311 Balboa Ave., Panama City, FL 32401",
     "source_url": "https://www.bay.k12.fl.us/school-board-meetings",
     "calendar_url": "https://thrillshare-cmsv2.services.thrillshare.com/api/v4/o/31249/cms/events/generate_ical?filter_ids&section_ids"},
    {"id": "pc", "name": "Panama City City Commission", "gov": "pc",
     "schedule": "2nd and 4th Tuesday of each month, unless otherwise stated: 2nd Tuesday at 8 a.m., "
                 "4th Tuesday at 4:30 p.m., at the Bay County Government Center, 840 W. 11th St. "
                 "Virtual workshops are also posted on the city calendar. Holiday months are consolidated on the city calendar.",
     "schedule_source_url": "https://panamacity.gov/401/About-Meetings",
     "location": "Bay County Government Center, 840 W. 11th St., Panama City, FL 32401",
     "source_url": "https://www.panamacity.gov/AgendaCenter",
     "calendar_url": "https://www.panamacity.gov/Calendar.aspx"},
    {"id": "pc-cra", "name": "Panama City Community Redevelopment Agency (CRA) Board", "gov": "pc",
     "schedule": "Beginning October 2026: first Tuesday of the month at 4:30 p.m., alternating monthly between "
                 "a regular CRA Board meeting and a virtual CRA workshop.",
     "schedule_source_url": "https://panamacity.gov/787/CRA-Board",
     "location": "Bay County Government Center, 840 W. 11th St., Panama City, FL 32401 (workshops are virtual)",
     "source_url": "https://www.panamacity.gov/AgendaCenter",
     "calendar_url": "https://www.panamacity.gov/Calendar.aspx"},
    {"id": "pcb", "name": "Panama City Beach City Council", "gov": "pcb",
     "schedule": "2nd and 4th Thursday of every month (except November and December); "
                 "2nd Thursday meetings at 5 p.m., 4th Thursday meetings at 9 a.m.",
     "schedule_source_url": "https://www.pcbfl.gov/185/City-Council",
     "location": "City Council Chambers, City Hall, 17007 Panama City Beach Pkwy, Panama City Beach, FL 32413",
     "source_url": "https://pcbgov.granicus.com/ViewPublisher.php?view_id=1",
     "calendar_url": "https://pcbgov.granicus.com/ViewPublisher.php?view_id=1"},
    {"id": "lh", "name": "Lynn Haven City Commission", "gov": "lh",
     "schedule": "Regular meetings 2nd and 4th Tuesday at 5:30 p.m. in the Walter T. Kelley Commission Chambers, "
                 "825 Ohio Ave. (pattern of dates on the city calendar and CivicClerk; holiday months consolidated).",
     "schedule_source_url": "https://www.cityoflynnhaven.gov/common/modules/iCalendar/iCalendar.aspx?catID=14&feed=calendar",
     "location": "Walter T. Kelley Commission Chambers, 825 Ohio Ave., Lynn Haven, FL 32444",
     "source_url": "https://lynnhavenfl.portal.civicclerk.com/",
     "calendar_url": "https://www.cityoflynnhaven.gov/Calendar.aspx"},
    {"id": "lh-cra", "name": "Lynn Haven Community Redevelopment Agency (CRA) Board", "gov": "lh",
     "schedule": "Recent CRA Board meetings have been held at 5:15 p.m. before City Commission meetings "
                 "(observed on CivicClerk; no standalone published schedule found).",
     "schedule_source_url": "https://lynnhavenfl.portal.civicclerk.com/",
     "location": "825 Ohio Ave., Lynn Haven, FL 32444",
     "source_url": "https://lynnhavenfl.portal.civicclerk.com/", "calendar_url": None},
    {"id": "cw", "name": "Callaway City Commission", "gov": "cw",
     "schedule": "Commission meetings at 6:00 p.m. at the Callaway Arts & Conference Center, 500 Callaway Pkwy; "
                 "2nd and 4th Tuesday pattern on the city calendar (one meeting in Nov/Dec).",
     "schedule_source_url": "https://www.cityofcallaway.com/common/modules/iCalendar/iCalendar.aspx?catID=14&feed=calendar",
     "location": "Callaway Arts & Conference Center, 500 Callaway Pkwy, Callaway, FL 32404",
     "source_url": "https://www.cityofcallaway.com/AgendaCenter",
     "calendar_url": "https://www.cityofcallaway.com/Calendar.aspx"},
    {"id": "cw-cra", "name": "Callaway Community Redevelopment Agency (CRA)", "gov": "cw",
     "schedule": "No published regular schedule found; meetings appear in the AgendaCenter when posted.",
     "schedule_source_url": "https://www.cityofcallaway.com/147/Community-Redevelopment",
     "location": "Callaway Arts & Conference Center, 500 Callaway Pkwy, Callaway, FL 32404 (typical; confirm on agenda)",
     "source_url": "https://www.cityofcallaway.com/AgendaCenter", "calendar_url": None},
    {"id": "sp", "name": "Springfield City Commission", "gov": "sp",
     "schedule": "Commission Meetings the first Monday of the month and Commission Workshops the third Monday, "
                 "at 5:30 p.m., City Hall Commission Room, 408 School Avenue.",
     "schedule_source_url": "https://www.springfieldfl.net/city-commission",
     "location": "Springfield City Hall Commission Room, 408 School Ave., Springfield, FL 32401",
     "source_url": "https://www.springfieldfl.net/meetings",
     "calendar_url": "https://www.springfieldfl.net/calendar"},
    {"id": "parker", "name": "Parker City Council", "gov": "parker",
     "schedule": "Regular meetings 1st and 3rd Tuesday at 5:30 p.m. (pattern of posted agendas; "
                 "no current published schedule statement found - expected dates are marked as such).",
     "schedule_source_url": "https://cityofparker.com/government/agendas-minutes/",
     "location": "Parker City Hall, 1001 West Park Street, Parker, FL 32404 (city contact address; confirm venue on agenda)",
     "source_url": "https://cityofparker.com/government/agendas-minutes/", "calendar_url": None},
    {"id": "mb", "name": "Mexico Beach City Council", "gov": "mb",
     "schedule": "Second and fourth Tuesdays of the month at 9:00 a.m. CT.",
     "schedule_source_url": "https://mexicobeachfl.gov/government/council-meetings/",
     "location": "Venue not stated on the council meetings page; City of Mexico Beach offices: 201 Paradise Path, Mexico Beach, FL 32456",
     "source_url": "https://mexicobeachfl.gov/government/council-meetings/", "calendar_url": None},
]

# Published/observed regular schedules used ONLY for "expected" dates on boards
# that have no official calendar feed. (nth week, weekday Mon=0, hour, minute)
RULES = {
    "pcb": {"slots": [(2, 3, 17, 0), (4, 3, 9, 0)], "skip_months": {11, 12},
            "basis": "published schedule (pcbfl.gov/185/City-Council)"},
    "mb": {"slots": [(2, 1, 9, 0), (4, 1, 9, 0)], "skip_months": set(),
           "basis": "published schedule (mexicobeachfl.gov council-meetings page)"},
    "parker": {"slots": [(1, 1, 17, 30), (3, 1, 17, 30)], "skip_months": set(),
               "basis": "pattern observed in posted agendas (no published schedule found)"},
}


# --------------------------------------------------------------------------
# merge / output
# --------------------------------------------------------------------------

def merge(primary, calendar):
    """Fold calendar entries into agenda-feed entries on the same date."""
    res = list(primary)
    for c in calendar:
        match = None
        for p in res:
            if p["date"] != c["date"]:
                continue
            if p["hh"] is None or c["hh"] is None or p["hh"] == c["hh"]:
                match = p
                break
        if match:
            if match["hh"] is None and c["hh"] is not None:
                match["hh"], match["mm"] = c["hh"], c["mm"]
            if not match.get("location") and c.get("location"):
                match["location"] = c["location"]
            match.setdefault("calendar_source", c["source"])
            if c.get("detail_url") and not match.get("detail_url"):
                match["detail_url"] = c["detail_url"]
        else:
            res.append(c)
    return res


def gen_expected(board_id, existing, today, end):
    rule = RULES.get(board_id)
    if not rule:
        return []
    have = {m["date"] for m in existing}
    out = []
    y, mo = today.year, today.month
    while dt.date(y, mo, 1) <= end:
        if mo not in rule["skip_months"]:
            for n, wd, hh, mm in rule["slots"]:
                d = _nth_weekday(y, mo, wd, n)
                if d and today <= d <= end and d not in have:
                    m = meeting(board_id, "Regular Meeting (expected)", d, hh, mm,
                                source="schedule:" + rule["basis"], status="expected")
                    m["expected"] = True
                    out.append(m)
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


def finalize(m, board, past=False):
    if not m.get("location") and re.search(r"\bvirtual\b", m["title"], re.I):
        m["location"] = "Virtual (live stream on the city website)"
    o = {"board": m["board"], "title": m["title"],
         "start": iso_local(m["date"], m["hh"], m["mm"]),
         "location": m.get("location") or board.get("location"),
         "agenda_url": m.get("agenda_url"), "packet_url": m.get("packet_url"),
         "minutes_url": m.get("minutes_url"), "source": m.get("source"),
         "status": m.get("status")}
    if m.get("detail_url"):
        o["detail_url"] = m["detail_url"]
    if m.get("calendar_source"):
        o["calendar_source"] = m["calendar_source"]
    if past:
        o["past"] = True
    if m.get("expected"):
        o["expected"] = True
        o["agenda_url"] = o["packet_url"] = o["minutes_url"] = None
    if m.get("cancelled"):
        o["cancelled"] = True
    if m.get("time_from_schedule"):
        o["time_from_schedule"] = True
    if m.get("items") is not None:
        o["items"] = m["items"]
    if m.get("agenda_items"):
        o["agenda_items"] = m["agenda_items"]
    return o


def main(argv):
    days = 60
    out_path = DEFAULT_OUT
    if "--days" in argv:
        days = int(argv[argv.index("--days") + 1])
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]

    now = now_central()
    today = now.date()
    end = today + dt.timedelta(days=days)
    per = {b["id"]: [] for b in BOARDS}
    cal = {b["id"]: [] for b in BOARDS}

    def safe(board, name, fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            note_error(board, name, "", "unhandled: %r" % e)
            return None

    # County
    per["county"] += safe("county", "PrimeGov", src_primegov_bocc, "county", today) or []
    cal["county"] += civicplus_ical("county", "www.baycountyfl.gov", 38, r"Board of County Commissioners|BOCC")
    cal["county-planning"] += civicplus_ical("county-planning", "www.baycountyfl.gov", 26, r"Planning Commission")

    # Schools: the district calendar's public API (the website itself blocks scripts).
    cal["schools"] += safe("schools", "District calendar (Thrillshare)", src_bds_events, today, days) or []

    # Panama City + CRA
    r = safe("pc", "AgendaCenter", src_agendacenter, "www.panamacity.gov", today, days,
             [(r"community redevelopment|\bCRA\b", "pc-cra"),
              (r"city commission|budget hearing|public workshop", "pc")]) or {}
    for b, lst in r.items():
        per[b] += lst
    cal["pc"] += civicplus_ical("pc", "www.panamacity.gov", 22, r"^City Commission")
    cal["pc-cra"] += civicplus_ical("pc-cra", "www.panamacity.gov", 22, r"\bCRA\b")

    # Panama City Beach
    per["pcb"] += safe("pcb", "Granicus RSS", src_granicus_pcb) or []
    for m in per["pcb"]:
        if m["hh"] is None and m["date"].month not in RULES["pcb"]["skip_months"]:
            for n, wd, hh, mm in RULES["pcb"]["slots"]:
                if _nth_weekday(m["date"].year, m["date"].month, wd, n) == m["date"]:
                    m["hh"], m["mm"], m["time_from_schedule"] = hh, mm, True

    # Lynn Haven + CRA
    r = safe("lh", "CivicClerk", src_civicclerk_lh, today, days) or {}
    for b, lst in r.items():
        per[b] += lst
    cal["lh"] += civicplus_ical("lh", "www.cityoflynnhaven.gov", 14, r"City Commission")

    # Callaway + CRA
    r = safe("cw", "AgendaCenter", src_agendacenter, "www.cityofcallaway.com", today, days,
             [(r"community redevelopment|\bCRA\b", "cw-cra"), (r"commission", "cw")]) or {}
    for b, lst in r.items():
        per[b] += lst
    cal["cw"] += civicplus_ical("cw", "www.cityofcallaway.com", 14, r"^Commission Meeting|City Commission")

    per["sp"] += safe("sp", "Meetings list", src_springfield) or []
    per["parker"] += safe("parker", "Agendas & Minutes page", src_parker) or []
    per["mb"] += safe("mb", "Council Meetings page", src_mexico_beach, today) or []

    boards_out, meetings_out = [], []
    for b in BOARDS:
        bid = b["id"]
        merged = merge(per[bid], cal[bid])
        upcoming = [m for m in merged if today <= m["date"] <= end]
        upcoming += gen_expected(bid, merged, today, end)
        past = [m for m in merged if m["date"] < today and not m.get("cancelled")]
        last = max(past, key=lambda m: (m["date"], m["hh"] or 0)) if past else None

        # money items for upcoming meetings (and the latest past one)
        for m in upcoming + ([last] if last else []):
            if m.get("expected") or m.get("cancelled"):
                continue
            try:
                if m.get("_html_template"):
                    items, loc, allit = primegov_items(m)
                    m["items"], m["agenda_items"] = items, allit
                    if loc and not m.get("location"):
                        m["location"] = loc
                elif m.get("_cc_agenda") or "GetMeetingFileStream" in (m.get("agenda_url") or ""):
                    items, allit = civicclerk_items(m)
                    if items is not None:
                        m["items"], m["agenda_items"] = items, allit
                elif m.get("_html_agenda"):
                    items, t, allit = agendacenter_html_items(m)
                    m["items"], m["agenda_items"] = items, allit
                    if t and m["hh"] is None:
                        m["hh"], m["mm"] = t
            except Exception as e:
                note_error(bid, "agenda items", m.get("agenda_url") or "", e)

        for m in sorted(upcoming, key=lambda m: (m["date"], m["hh"] or 0)):
            meetings_out.append(finalize(m, b))
        if last:
            meetings_out.append(finalize(last, b, past=True))

        bo = {k: b.get(k) for k in ["id", "name", "gov", "schedule", "location",
                                    "source_url", "calendar_url", "schedule_source_url"]}
        bo["sources"] = SOURCE_LOG.get(bid, {})
        n_live = sum(1 for m in upcoming if m.get("status") == "posted")
        n_cal = sum(1 for m in upcoming if m.get("status") == "calendar")
        n_exp = sum(1 for m in upcoming if m.get("expected"))
        bo["coverage"] = {"agenda_feed": n_live, "calendar": n_cal, "expected": n_exp}
        boards_out.append(bo)

    meetings_out.sort(key=lambda m: (m["start"][:10], m["board"]))
    doc = {"generated": now.replace(microsecond=0).isoformat(),
           "window": {"from": today.isoformat(), "to": end.isoformat()},
           "timezone": "America/Chicago",
           "boards": boards_out, "meetings": meetings_out, "errors": ERRORS,
           "notes": ["status=posted: listed by an official agenda system or the board's own meetings page (agenda_url is set once an agenda is published); status=calendar: posted on the "
                     "government's website calendar, agenda not yet linked; expected=true: generated from "
                     "the regular schedule, not an official posting - confirm before relying on it.",
                     "Each board also includes its most recent past meeting, flagged past=true."]}
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, out_path)
    print("wrote %s: %d meetings, %d boards, %d errors" % (
        out_path, len(meetings_out), len(boards_out), len(ERRORS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
