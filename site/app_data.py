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
    """Everyone with a /people page. `subtitle` and `label` are the site's one-line description and kind
    (Elected official, Department leader, Candidate, Former official); `kinds` are the People page's filter chips.
    `photo` is the path of their official photo (dataset official-photos), or null for initials.
    `gov`, `group`, `rank` and `order` are the People list's order (people_pages.directory_order): the government they
    are listed under and its name (the list's heading), their title rank (0 mayor or chair ... 8 past candidate), `status` (current, or past for former officials and past
    candidates) and their position; the list is in that order."""
    import entity_graph as EG
    from ui import photo_of
    from people_pages import _kinds, directory_order, status_of
    p = json.load(open(os.path.join(HERE, '..', 'data', 'entities', 'people.json')))
    G = EG.build()
    order = directory_order(p['people'])

    def ent(pid):
        return G.ents.get('person:' + pid) or {}
    return {'about': p.get('about'), 'people': [
        {'id': x['id'], 'name': x['name'], 'district': x.get('district'), 'gov_ids': x.get('gov_ids', []),
         'subtitle': ent(x['id']).get('subtitle') or None, 'label': ent(x['id']).get('label') or None, 'kinds': _kinds(x),
         'photo': photo_of(x['id']), 'gov': order[x['id']][0] or None,
         'group': (G.ents.get('gov:' + order[x['id']][0]) or {}).get('name') or 'Other offices', 'rank': order[x['id']][1], 'status': status_of(order[x['id']][1]), 'order': order[x['id']][2],
         'roles': [{'role': r.get('role'), 'gov_id': r.get('gov_id'), 'seat': r.get('seat')} for r in x.get('roles', [])]}
        for x in sorted(p['people'], key=lambda x: order[x['id']][2])]}


def donor_contracts():
    """Business donors that also hold local government contracts (the campaign money page's list).

    One row per gift: a company's gift to one campaign. vendor_matches.json repeats a gift once per government that paid
    the company, each time under that government's spelling of the name, so the rows are folded here. vendor_name is the
    company's one name on the site; contract_governments lists every government that paid it; contract_gov_id is the
    official's own government when it is one of them, otherwise the first."""
    import sys
    sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
    import ids
    m = json.load(open(os.path.join(HERE, '..', 'data', 'campaign', 'vendor_matches.json')))
    out = {}
    for x in m['matches']:
        k = (x.get('vendor_id') or x.get('contributor'), x.get('candidate'), x.get('gift_source'))
        r = out.get(k)
        if r is None:
            v = ids.vendor(x.get('vendor_id')) or {}
            r = out[k] = {'contributor': x.get('contributor'), 'vendor_name': v.get('name') or x.get('vendor_entity') or x.get('contributor'),
                          'vendor_id': x.get('vendor_id'), 'candidate': x.get('candidate'), 'person_id': x.get('person_id'), 'office': x.get('office'),
                          'office_gov_id': x.get('office_gov_id'), 'election': x.get('election'), 'contribution_amount': x.get('contribution_amount'),
                          'contribution_dates': x.get('contribution_dates'), 'refunded_by_campaign': x.get('refunded_by_campaign'),
                          'match_confidence': x.get('match_confidence'), 'note': x.get('note'), 'campaign_report_url': x.get('campaign_report_url'),
                          '_spellings': set(), '_govs': [], '_items': [], '_rids': [], '_urls': [], '_types': set(), 'same_government_as_office': False}
        r['_spellings'] |= set((x.get('vendor') or '').split(' / ')) - {''}
        if x.get('contract_gov_id') not in [g for g, _ in r['_govs']]:
            r['_govs'].append((x.get('contract_gov_id'), x.get('contract_government')))
        for d, rid in zip(x.get('contract_ids_or_descriptions') or [], (x.get('record_ids') or []) + [None] * 99):
            if d not in r['_items']:
                r['_items'].append(d); r['_rids'].append(rid)
        r['_urls'] += [u for u in x.get('contract_source_urls') or [] if u not in r['_urls']]
        r['_types'] |= set(x.get('record_types') or [])
        r['same_government_as_office'] |= bool(x.get('same_government_as_office'))
        if x.get('match_confidence') == 'likely':
            r['match_confidence'], r['note'] = 'likely', x.get('note')
    rows = []
    for r in out.values():
        govs = sorted(r.pop('_govs'), key=lambda g: g[0] != r['office_gov_id'])
        items = r.pop('_items'); rids = r.pop('_rids')
        rows.append({**{k: v for k, v in r.items() if not k.startswith('_')},
                     'vendor': ' / '.join(sorted(r['_spellings'])), 'contract_ids_or_descriptions': items, 'record_ids': [x for x in rids if x],
                     'contract_source_urls': r['_urls'], 'contract_government': govs[0][1], 'contract_gov_id': govs[0][0],
                     'contract_governments': [g[1] for g in govs], 'contract_gov_ids': [g[0] for g in govs], 'record_types': sorted(r['_types'])})
    return {'as_of': m.get('as_of'), 'method': (m.get('method') or '').replace('One row per contributor spelling, candidate and paying government.',
                                                                              'One row per gift (company and campaign), with every government that paid the company.'),
            'matches': rows}


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
