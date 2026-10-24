"""Data files for the BayCounty.me iOS app, written to /data/app/ on every build.

The app reads the same /downloads datasets as everyone else. These files carry what the website keeps inside its
page scripts and page HTML: the tax and Amendment 3 calculator models, the address lookup's rate tables, the glossary,
each page's lead paragraph, the updates log, the company and people profiles and the money map. Nothing here is new
information; it's what the site already publishes, in a form an app can read. The same privacy rules apply:
businesses only for campaign donors, and only officials, department leaders and candidates as people.
"""
import html as _html
import json
import os
import re
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = 1  # bump when a file's shape changes in a way older app builds can't read


def _dump(out_dir, name, obj):
    d = os.path.join(out_dir, 'data', 'app')
    os.makedirs(d, exist_ok=True)
    json.dump(obj, open(os.path.join(d, name), 'w'), ensure_ascii=False, separators=(',', ':'))
    return name


def _text(s):
    return re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', '', s or ''))).strip()


def _lede(out_dir, path):
    """The lead paragraph a page opens with, as plain text."""
    f = os.path.join(out_dir, path.strip('/'), 'index.html') if path != '/' else os.path.join(out_dir, 'index.html')
    if not os.path.exists(f):
        f = os.path.join(out_dir, path.strip('/') + '.html')
    if not os.path.exists(f):
        return None
    m = re.search(r'<p class="lede">(.*?)</p>', open(f).read(), re.S)
    return _text(m.group(1)) if m else None


def _first_section(out_dir, path):
    """The first explainer section on a page ("How X works"): heading + its paragraphs, plain text."""
    f = os.path.join(out_dir, path.strip('/'), 'index.html')
    if not os.path.exists(f):
        return None
    s = open(f).read()
    m = re.search(r'<h2[^>]*>(How [^<]*|What[^<]*\?)</h2>(.*?)(?=<h2|<section|</section>)', s, re.S)
    if not m:
        return None
    paras = [_text(p) for p in re.findall(r'<p(?: class="[^"]*")?>(.*?)</p>', m.group(2), re.S)]
    paras = [p for p in paras if len(p) > 40][:3]
    return {'heading': _text(m.group(1)), 'paragraphs': paras} if paras else None


def pages(out_dir, page_list):
    out = []
    for path, title, desc, _ in page_list:
        if path.startswith('/es') or path.startswith(('/public-money/vendors/', '/people/', '/profile')) or path.startswith('/admin'):
            continue
        out.append({'path': path, 'title': title, 'description': desc, 'lede': _lede(out_dir, path),
                    'explainer': _first_section(out_dir, path)})
    return out


def glossary():
    from glossary import GROUPS, TERMS
    return {'groups': [{'id': g, 'name': n} for g, n in GROUPS],
            'terms': [{k: t.get(k) or None for k in ('id', 'group', 'term', 'simple', 'more', 'example')} for t in TERMS]}


def updates():
    from updates import CHANGES
    return [{'date': c['date'], 'title': c['title'], 'text': c['text'], 'pages': c.get('pages', [])} for c in CHANGES]


def vendors():
    v = json.load(open(os.path.join(HERE, '..', 'data', 'entities', 'vendors.json')))
    slugs = {}
    try:
        from vendor_pages import build as _vb
        slugs = {s: True for s in _vb()}
    except Exception:
        pass
    return {'about': v.get('about'), 'vendors': [
        {'id': x['id'], 'name': x['name'], 'aliases': [a for a in x.get('aliases', []) if a != x['name']],
         'gov_ids': x.get('gov_ids', []), 'records': x.get('records', {}), 'type': x.get('site_vendor_type'),
         'page': f'/public-money/vendors/{x["id"]}' if x['id'] in slugs else None}
        for x in v['vendors']]}


def people():
    p = json.load(open(os.path.join(HERE, '..', 'data', 'entities', 'people.json')))
    return {'about': p.get('about'), 'people': [
        {'id': x['id'], 'name': x['name'], 'district': x.get('district'), 'gov_ids': x.get('gov_ids', []),
         'roles': [{'role': r.get('role'), 'gov_id': r.get('gov_id'), 'seat': r.get('seat')} for r in x.get('roles', [])]}
        for x in p['people']]}


def donor_contracts():
    """Business donors that also hold local government contracts (the campaign money page's list)."""
    m = json.load(open(os.path.join(HERE, '..', 'data', 'campaign', 'vendor_matches.json')))
    keep = ('contributor', 'vendor', 'vendor_id', 'candidate', 'person_id', 'office', 'office_gov_id', 'election',
            'contribution_amount', 'contribution_dates', 'contract_ids_or_descriptions', 'record_ids', 'contract_source_urls',
            'contract_government', 'contract_gov_id', 'record_types', 'match_confidence', 'note', 'campaign_report_url',
            'same_government_as_office', 'refunded_by_campaign')
    return {'as_of': m.get('as_of'), 'method': m.get('method'), 'matches': [{k: x.get(k) for k in keep} for x in m['matches']]}


def write_app_data(out_dir, page_list):
    from tax_page import build_data
    from addr_page import address_data
    from amend_page import amend_data
    files = [
        _dump(out_dir, 'tax.json', build_data()),
        _dump(out_dir, 'address.json', address_data()),
        _dump(out_dir, 'amendment3.json', amend_data()),
        _dump(out_dir, 'glossary.json', glossary()),
        _dump(out_dir, 'pages.json', pages(out_dir, page_list)),
        _dump(out_dir, 'updates.json', updates()),
        _dump(out_dir, 'vendors.json', vendors()),
        _dump(out_dir, 'people.json', people()),
        _dump(out_dir, 'donor-contracts.json', donor_contracts()),
    ]
    try:
        from money_map import map_data
        files.append(_dump(out_dir, 'money-map.json', map_data()))
    except FileNotFoundError:
        pass
    _dump(out_dir, 'index.json', {'version': VERSION, 'built': date.today().isoformat(), 'files': files})
    return len(files)
