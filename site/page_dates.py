"""The real 'Page updated' date for every page: the last day its built content changed.

The footer stamp, the 'Data updated' stamps, the JSON-LD dateModified and the sitemap lastmod used to
come only from the hand-kept What's new log (site/updates.py), so a page refreshed every morning could
still say it was last updated weeks ago. Now each build hashes the page with its date stamps taken out
and compares it with the hash it had last time (site/page_updated.json): same content keeps the old date,
new content gets today's date in Bay County (Central time). A What's new entry for the page still counts
if it is newer.
"""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(ROOT, 'page_updated.json')

EN = r'[A-Z][a-z]{2} \d{1,2}, \d{4}'
ES = r'\d{1,2} de [a-z]+ de \d{4}'
STAMPS = [
    re.compile(r'Page updated ' + EN),
    re.compile(r'Página actualizada el ' + ES),
    re.compile(r'Data updated ' + EN),
    re.compile(r'Datos actualizados el ' + ES),
    re.compile(r'"dateModified": ?"\d{4}-\d{2}-\d{2}"'),
]

_saved = None   # path -> {'h': hash, 'd': 'YYYY-MM-DD'} as last committed
_now = {}       # path -> same, for pages written in this build


def today():
    return datetime.now(ZoneInfo('America/Chicago')).date().isoformat()


def _load():
    global _saved
    if _saved is None:
        try:
            _saved = json.load(open(FILE))
        except (OSError, ValueError):
            _saved = {}
    return _saved


def _strip(html):
    for r in STAMPS:
        html = r.sub('', html)
    return html


def _hash(html):
    return hashlib.sha256(_strip(html).encode()).hexdigest()[:20]


def _git(*args):
    try:
        r = subprocess.run(['git', *args], cwd=os.path.dirname(ROOT), capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _committed(fp, h):
    """First run only (no saved hash): if the committed copy of the page says the same thing, the day it
    was last committed. The build wipes site/public first, so the old copy is read from git."""
    rel = os.path.relpath(os.path.abspath(fp), os.path.dirname(ROOT)).replace(os.sep, '/')
    old = _git('show', 'HEAD:' + rel)
    if old is None or _hash(old) != h:
        return None
    return (_git('log', '-1', '--format=%cd', '--date=short', '--', rel) or '').strip() or None


def updated(path, html, fp, floor=None):
    """Date (YYYY-MM-DD) this page's content last changed. floor: its newest What's new entry."""
    h = _hash(html)
    old = _load().get(path)
    if old and old['h'] == h:
        d = old['d']
    elif old:
        d = today()
    else:
        d = _committed(fp, h) or today()
    if floor and floor > d:
        d = floor
    _now[path] = {'h': h, 'd': d}
    return d


def get(path, default=None):
    e = _now.get(path) or _load().get(path)
    return e['d'] if e else default


def save():
    """Write page_updated.json for the pages this build wrote (a removed page drops out)."""
    data = dict(sorted(_now.items()))
    with open(FILE, 'w') as f:
        f.write('{\n' + ',\n'.join(f'  {json.dumps(p)}: {json.dumps(e)}' for p, e in data.items()) + '\n}\n')
    return len(data)
