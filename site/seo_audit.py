"""SEO audit of the built site (site/public).

Run after build_site.py:  python3 seo_audit.py  [--json]
Exits non-zero when any page has an error, so it can gate CI.
"""
import json, os, re, sys
from collections import defaultdict
from html.parser import HTMLParser

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')
SITE = 'https://baycounty.me'
SKIP = ('admin',)          # private pages, noindex by design


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None; self.title = ''; self._in = None
        self.meta = {}; self.links = []; self.canon = None; self.alts = []
        self.h1 = []; self.heads = []; self.jsonld = []; self.hreflang = {}
        self.imgs_noalt = 0; self.imgs = 0; self._buf = ''

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == 'html': self.lang = a.get('lang')
        elif tag == 'title': self._in = 'title'
        elif tag == 'meta':
            k = a.get('name') or a.get('property')
            if k: self.meta[k.lower()] = a.get('content', '')
        elif tag == 'link':
            rel = (a.get('rel') or '').lower()
            if rel == 'canonical': self.canon = a.get('href')
            if rel == 'alternate' and a.get('hreflang'): self.hreflang[a['hreflang']] = a.get('href')
        elif tag == 'a' and a.get('href'): self.links.append(a['href'])
        elif tag == 'img':
            self.imgs += 1
            if a.get('alt') is None: self.imgs_noalt += 1
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._in = tag; self._buf = ''
        elif tag == 'script' and a.get('type') == 'application/ld+json': self._in = 'ld'; self._buf = ''

    def handle_endtag(self, tag):
        if tag == 'title' and self._in == 'title': self._in = None
        elif self._in == tag and tag.startswith('h') and len(tag) == 2:
            t = re.sub(r'\s+', ' ', self._buf).strip()
            self.heads.append(int(tag[1]))
            if tag == 'h1': self.h1.append(t)
            self._in = None
        elif tag == 'script' and self._in == 'ld':
            try: self.jsonld.append(json.loads(self._buf))
            except Exception: self.jsonld.append('INVALID')
            self._in = None

    def handle_data(self, d):
        if self._in == 'title': self.title += d
        elif self._in: self._buf += d


def url_for(path):
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
    if rel == 'index.html': return '/'
    rel = rel[:-5]
    if rel.endswith('/index'): rel = rel[:-6]
    return '/' + rel


def audit():
    pages = {}
    for d, _, files in os.walk(ROOT):
        for f in files:
            if f.endswith('.html'):
                p = os.path.join(d, f); u = url_for(p)
                if u.strip('/').split('/')[0] in SKIP or u == '/404': continue
                pg = Page(); pg.feed(open(p, encoding='utf-8').read()); pages[u] = pg
    known = set(pages) | {'/404'}
    files = set()
    for d, _, fs in os.walk(ROOT):
        for f in fs: files.add('/' + os.path.relpath(os.path.join(d, f), ROOT).replace(os.sep, '/'))

    issues = defaultdict(list)
    titles, descs = defaultdict(list), defaultdict(list)
    for u, p in sorted(pages.items()):
        E = lambda m: issues[u].append(('error', m)); W = lambda m: issues[u].append(('warn', m))
        t = re.sub(r'\s+', ' ', p.title).strip(); d = p.meta.get('description', '').strip()
        if not t: E('missing <title>')
        elif len(t) > 60: W(f'title {len(t)} chars (>60): {t}')
        elif len(t) < 15: W(f'title short ({len(t)}): {t}')
        titles[t].append(u)
        if not d: E('missing meta description')
        elif len(d) > 160: W(f'description {len(d)} chars (>160)')
        elif len(d) < 70: W(f'description short ({len(d)})')
        descs[d].append(u)
        if not p.lang: E('missing <html lang>')
        elif u.startswith('/es') and not p.lang.startswith('es'): E(f'Spanish page has lang="{p.lang}"')
        want = SITE + ('' if u == '/' else u)
        if not p.canon: E('missing canonical')
        elif p.canon.rstrip('/') != want.rstrip('/'): E(f'canonical {p.canon} != {want}')
        if len(p.h1) == 0: E('no <h1>')
        elif len(p.h1) > 1: W(f'{len(p.h1)} <h1> tags')
        prev = 0
        for h in p.heads:
            if prev and h > prev + 1: W(f'heading skips h{prev} -> h{h}'); break
            prev = h
        if 'robots' in p.meta and 'noindex' in p.meta['robots']: W('page is noindex')
        if not p.meta.get('og:title'): W('missing og:title')
        if not p.meta.get('og:image'): W('missing og:image')
        if p.imgs_noalt: E(f'{p.imgs_noalt}/{p.imgs} <img> without alt')
        if any(x == 'INVALID' for x in p.jsonld): E('invalid JSON-LD')
        if not p.jsonld: W('no structured data (JSON-LD)')
        for h in set(p.links):
            if h.startswith(('http', 'mailto:', 'tel:', '#', 'javascript:', 'webcal:')) or h.startswith('//'): continue
            path = h.split('#')[0].split('?')[0]
            if not path or not path.startswith('/'): continue
            if path.startswith('/api/') or path == '/alerts/manage': continue
            if path.rstrip('/') in known or path in files or (path.rstrip('/') or '/') in known: continue
            E(f'broken internal link {h}')
    for t, us in titles.items():
        if t and len(us) > 1:
            for u in us: issues[u].append(('warn', f'duplicate title shared with {len(us)-1} other page(s)'))
    for d, us in descs.items():
        if d and len(us) > 1:
            for u in us: issues[u].append(('warn', f'duplicate description shared with {len(us)-1} other page(s)'))
    site = []
    if not os.path.exists(os.path.join(ROOT, 'robots.txt')): site.append(('error', 'no robots.txt'))
    if not os.path.exists(os.path.join(ROOT, 'sitemap.xml')): site.append(('error', 'no sitemap.xml'))
    return pages, issues, site


if __name__ == '__main__':
    pages, issues, site = audit()
    errs = sum(1 for v in issues.values() for s, _ in v if s == 'error') + sum(1 for s, _ in site if s == 'error')
    warns = sum(1 for v in issues.values() for s, _ in v if s == 'warn')
    if '--json' in sys.argv:
        print(json.dumps({'pages': len(pages), 'site': site, 'issues': issues}, indent=1)); sys.exit(1 if errs else 0)
    for s, m in site: print(f'[{s}] SITE: {m}')
    for u in sorted(issues):
        for s, m in issues[u]: print(f'[{s}] {u}: {m}')
    print(f'\n{len(pages)} pages, {errs} errors, {warns} warnings')
    sys.exit(1 if errs else 0)
