"""llms.txt and llms-full.txt: a plain-text map of the site for AI assistants and answer engines (https://llmstxt.org).

llms.txt is the short version: what the site is, the menu sections with one line each, and where the data and API are.
llms-full.txt adds every public page (title, address, summary) and every dataset with its download links.
Both are written by build_site.main() from the same menu, page list and open-data catalog the site uses, so they never
drift from the pages. No product or model names here: assistants are "AI assistants".
"""
import json
import os

from place import SITE, DOMAIN, LABEL, EMAIL, OPERATOR

PRIVATE = ('/admin', '/finance', '/staff', '/profile', '/404', '/account')
SUMMARY = (f'{SITE} is a free, independent guide to the public records of {LABEL}: its county, cities, school district '
           'and special districts. It shows where tax money goes, budgets, contracts and the vendors paid, how officials '
           'voted, campaign money, meetings, elections, public notices, schools, restaurant inspections, emergencies '
           'and more, each figure linked to its government source.')
RULES = [
    'Every number links to the public record it came from (budgets, audits, minutes, state and federal filings). /data-sources lists each source and how often it is read.',
    'The site covers 2016 to today. Earlier years are not included.',
    'Individual campaign donors are not named; gifts are summed. The exception is a donor who runs a registered business, listed by name with their businesses. Home addresses are never shown.',
    'Salaries are named only for elected officials and department leaders.',
    'Corrections: /about explains how to report one; each fix is logged on /updates.',
]


def _line(href, label, desc):
    return f'- [{label}]({DOMAIN}{href})' + (f': {desc}' if desc else '')


def _catalog(out_dir):
    fp = os.path.join(out_dir, 'downloads', 'index.json')
    if not os.path.exists(fp):
        return {'datasets': []}
    return json.load(open(fp))


def _sections(menu, links, pages):
    """[(section label, [(href, label, desc)])] from the site menu, with descriptions from the page list when the menu has none."""
    desc = {p: d for p, _, d, _ in pages}
    out = []
    for m in menu:
        items = []
        for c in links(m):
            h = c['href'].split('#')[0]
            if h.startswith(PRIVATE):
                continue
            items.append((h, c['label'], c.get('desc') or desc.get(h, '')))
        if items:
            out.append((m['label'], items))
    return out


def llms_txt(menu, links, pages, es_alt, catalog):
    home = next((d for p, _, d, _ in pages if p == '/'), SUMMARY)
    rows = sum(1 for d in catalog.get('datasets', []) if d.get('rows'))
    out = [f'# {SITE}', '', f'> {SUMMARY}', '', home, '',
           f'Run by {OPERATOR["name"]} ({OPERATOR["url"]}), {OPERATOR.get("about", "")}. Contact: {EMAIL}. Free to use; the data is open (see Open data).'.replace(', .', '.'), '']
    for label, items in _sections(menu, links, pages):
        out += [f'## {label}', ''] + [_line(*x) for x in items] + ['']
    out += ['## Data and API', '',
            _line('/open-data', 'Open data', f'{rows} datasets as CSV and JSON, refreshed daily'),
            _line('/downloads/index.json', 'Dataset catalog (JSON)', 'every dataset with its columns and download links'),
            _line('/developers', 'API and assistant connector', 'REST API, OpenAPI description and an MCP server for AI assistants'),
            _line('/api/v1/openapi.json', 'OpenAPI description', 'the /api/v1 endpoints'),
            _line('/api/mcp', 'MCP server', 'tools that answer common questions from the same data'),
            _line('/data-sources', 'Data sources', 'every source, link and how often it is read'),
            '', '## En español', '']
    out += [_line(p, t, '') for p, t, _, _ in pages if p in es_alt or p == '/es']
    out += ['', '## Optional', '',
            _line('/llms-full.txt', 'llms-full.txt', 'every page and dataset in one file'),
            _line('/sitemap.xml', 'Sitemap', 'every public page'),
            _line('/sitemap-profiles.xml', 'Profile sitemap', 'a profile for every government, company, business, nonprofit, political committee, board member and business owner in the records'),
            _line('/updates.xml', 'What is new (RSS)', 'new pages, data and corrections'),
            _line('/glossary', 'Glossary', 'CRA, millage, homestead and other terms in plain words'),
            _line('/about', 'About', 'who runs the site, method and corrections'), '']
    return '\n'.join(out)


def llms_full_txt(menu, links, pages, es_alt, catalog):
    out = [f'# {SITE}: every page and dataset', '', f'> {SUMMARY}', '', '## How to read this site', '']
    out += [f'- {r}' for r in RULES] + ['']
    seen = set()
    for label, items in _sections(menu, links, pages):
        out += [f'## {label}', '']
        for h, lab, d in items:
            seen.add(h)
            out += [f'### {lab}', f'URL: {DOMAIN}{h}', d, '']
    groups = [
        ('Governments', lambda p: p.startswith('/governments/')),
        ('Officials and candidates', lambda p: p.startswith('/people/')),
        ('Public money pages', lambda p: p.startswith('/public-money/')),
        ('Connections pages', lambda p: p.startswith('/connections')),
        ('Elections pages', lambda p: p.startswith('/elections')),
        ('Restaurants (one page per state license, every inspection since 2016)', lambda p: p.startswith('/restaurants/')),
        ('En español', lambda p: p == '/es' or p in es_alt),
        ('Other pages', lambda p: True),
    ]
    rest = [x for x in pages if x[0] not in seen and not x[0].startswith(PRIVATE)]
    for label, test in groups:
        got = [x for x in rest if test(x[0])]
        rest = [x for x in rest if not test(x[0])]
        if not got:
            continue
        out += [f'## {label}', '']
        for p, t, d, _ in sorted(got, key=lambda x: x[0]):
            out.append(f'- [{t}]({DOMAIN}{p})' + (f': {d}' if d and not p.startswith('/restaurants/') else ''))
        out.append('')
    out += ['## Datasets', '', f'Catalog: {DOMAIN}/downloads/index.json. API: {DOMAIN}/api/v1/datasets/<id> (filters, sort, paging; see {DOMAIN}/developers).', '']
    for d in catalog.get('datasets', []):
        if not d.get('rows'):
            continue
        cols = ', '.join(c['name'] for c in d.get('columns', []))
        out += [f'### {d["title"]} ({d["id"]})', d.get('description', ''), f'Rows: {d["rows"]:,}. Columns: {cols}',
                f'CSV: {DOMAIN}{d["csv"]} · JSON: {DOMAIN}{d["json"]}', '']
    return '\n'.join(out)


def write_llms(out_dir, menu, links, pages, es_alt):
    pub = [x for x in pages if not x[0].startswith(PRIVATE)]
    cat = _catalog(out_dir)
    a = llms_txt(menu, links, pub, es_alt, cat)
    b = llms_full_txt(menu, links, pub, es_alt, cat)
    open(os.path.join(out_dir, 'llms.txt'), 'w').write(a)
    open(os.path.join(out_dir, 'llms-full.txt'), 'w').write(b)
    return len(a), len(b)
