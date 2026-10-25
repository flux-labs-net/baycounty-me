"""The site's earliest year. Nothing from before it is kept, shown or loaded (Jeremy, 2026-10-25).

FIRST_YEAR is the first kept year: fiscal year 2016 for fiscal data (Oct 2015 - Sep 2016 for most governments) and
calendar 2016 for dated records. A record is kept when it reaches FIRST_YEAR: a fiscal year or tax year of 2016 or
later, a date in 2016 or later, or a span (a term in office, a loan) that runs into 2016. Records with no date are kept.

Every ingestion script and the open-data build call these helpers, so older rows are dropped where data comes in.
The API's copy of the number is api/_cutoff.js (a test keeps the two equal); db/migrations/0052_first_year_2016.sql
removed the older rows already in the database.
"""
import re

FIRST_YEAR = 2016
FIRST_DATE = f'{FIRST_YEAR}-01-01'
FIRST_FY = f'FY{FIRST_YEAR}'


def year_of(value):
    """The year a value points at: 2015 for 2015, 'FY2015', 'FY2014-15', '2015-09-30', 'Sep 2015' or 'September 30, 2015'.
    For a span ('2009 - 2011', 'FY2014-FY2016') it is the last year. None when there is no year."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if 1900 <= value <= 2200 else None
    t = str(value)
    m = re.search(r'\bFY\s?(\d{4})\s?-\s?(\d{2})\b(?!\d)', t, re.I)
    if m and int(m.group(2)) == (int(m.group(1)) + 1) % 100:
        return int(m.group(1)) + 1
    ys = [int(y) for y in re.findall(r'(?<!\d)(19\d\d|20\d\d)(?!\d)', t)]
    return max(ys) if ys else None


def keep(value):
    """True when the value is FIRST_YEAR or later, or has no year."""
    y = year_of(value)
    return y is None or y >= FIRST_YEAR


def keep_span(start=None, end=None):
    """A span (term in office, loan, project) is kept when it runs into FIRST_YEAR: no end (still going), or an end in
    FIRST_YEAR or later. start is ignored; it is there so calls read as the span they test."""
    return end in (None, '') or keep(end)


def trim(rows, *cols):
    """Rows whose first non-empty column of cols is FIRST_YEAR or later (or has no year)."""
    out = []
    for r in rows:
        v = next((r.get(c) for c in cols if r.get(c) not in (None, '')), None)
        if keep(v):
            out.append(r)
    return out


def clamp_start(date):
    """A start date before FIRST_YEAR becomes None ('already there before the first year the site covers')."""
    return date if keep(date) else None
