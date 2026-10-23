"""Search-engine plumbing shared by every page: titles, descriptions, structured data, robots.txt and sitemap.xml.

build_site.layout() calls head_title(), meta_desc() and jsonld(); build_site.main() calls write_robots_and_sitemap().
Check the result with `python3 seo_audit.py` after a build.
"""
import html as _h
import json
import os

DOMAIN = 'https://baycounty.me'
SITE = 'BayCounty.me'
TITLE_MAX = 60
DESC_MAX = 160
PRIVATE = ('/admin',)          # never in the sitemap; robots.txt disallows them
ORG = {'@type': 'Organization', '@id': DOMAIN + '/#org', 'name': 'Flux Labs', 'url': 'https://fluxlabs.net/',
       'logo': DOMAIN + '/assets/flux-labs.webp'}
PLACE = {'@type': 'AdministrativeArea', 'name': 'Bay County, Florida', 'sameAs': 'https://en.wikipedia.org/wiki/Bay_County,_Florida'}


def head_title(title, path):
    """The <title>: page title plus the site name, dropping the suffix (then trimming) when it would run past ~60 characters."""
    if path == '/':
        return f'{SITE} · {title}'
    full = f'{title} · {SITE}'
    if len(full) <= TITLE_MAX:
        return full
    if len(title) <= TITLE_MAX:
        return title
    return _trim(title, TITLE_MAX)


def meta_desc(d):
    """Meta description kept under ~160 characters: whole sentences when they fit, otherwise cut at a word."""
    d = ' '.join(d.split())
    if len(d) <= DESC_MAX:
        return d
    out = ''
    for s in d.replace('. ', '.\n').split('\n'):
        if len(out) + len(s) + 1 > DESC_MAX:
            break
        out = (out + ' ' + s).strip()
    return out if len(out) >= 90 else _trim(d, DESC_MAX)


def _trim(s, n):
    s = s[:n - 1].rsplit(' ', 1)[0].rstrip(' ,;:·-–(')
    return s + '…'


def _crumbs(path, labels):
    """Home > section > page, using menu labels; segments without their own page are skipped."""
    es = path.startswith('/es')
    items = [('BayCounty.me' if not es else 'BayCounty.me en español', '/es' if es else '/')]
    parts = [p for p in path.strip('/').split('/') if p]
    if es:
        parts = parts[1:]
    acc = '/es' if es else ''
    for p in parts:
        acc += '/' + p
        if acc in labels:
            items.append((labels[acc], acc))
    if len(items) < 2:
        return None
    return {'@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': DOMAIN + (u if u != '/' else '/')} for i, (n, u) in enumerate(items)]}


def _datasets(out_dir):
    fp = os.path.join(out_dir, 'downloads', 'index.json')
    if not os.path.exists(fp):
        return None
    d = json.load(open(fp))
    return {'@type': 'DataCatalog', '@id': DOMAIN + '/open-data#catalog', 'name': d.get('name') or 'BayCounty.me open data',
            'url': DOMAIN + '/open-data', 'publisher': {'@id': ORG['@id']}, 'spatialCoverage': PLACE,
            'dataset': [{
                '@type': 'Dataset', 'name': x['title'], 'description': x['description'] if len(x['description']) >= 50 else x['description'] + ' Bay County, Florida public records compiled by BayCounty.me.',
                'url': DOMAIN + '/open-data#' + x['id'], 'identifier': x['id'], 'isAccessibleForFree': True,
                'license': DOMAIN + '/open-data', 'usageInfo': d.get('license', ''),
                'creator': {'@id': ORG['@id']}, 'spatialCoverage': PLACE, 'dateModified': d.get('updated'),
                'distribution': [{'@type': 'DataDownload', 'encodingFormat': 'text/csv', 'contentUrl': DOMAIN + x['csv']},
                                 {'@type': 'DataDownload', 'encodingFormat': 'application/json', 'contentUrl': DOMAIN + x['json']}],
            } for x in d.get('datasets', []) if x.get('csv') and x.get('json')]}


def jsonld(path, title, desc, labels, modified=None, out_dir=None, kind=None, about=None):
    """One JSON-LD graph per page: WebSite + Organization (home), WebPage with breadcrumbs everywhere,
    plus GovernmentOrganization / Organization / DataCatalog / DefinedTermSet where the page is about one."""
    lang = 'es-US' if path.startswith('/es') else 'en-US'
    url = DOMAIN + path
    site = {'@type': 'WebSite', '@id': DOMAIN + '/#site', 'name': SITE, 'url': DOMAIN + '/', 'inLanguage': ['en-US', 'es-US'],
            'publisher': {'@id': ORG['@id']},
            'potentialAction': {'@type': 'SearchAction', 'target': DOMAIN + '/search?q={search_term_string}', 'query-input': 'required name=search_term_string'}}
    graph = []
    if path == '/':
        site['description'] = desc
        graph += [site, ORG]
    page = {'@type': 'CollectionPage' if kind == 'collection' else 'WebPage', '@id': url + '#page', 'url': url, 'name': title,
            'description': desc, 'inLanguage': lang, 'isPartOf': {'@id': DOMAIN + '/#site'}, 'publisher': {'@id': ORG['@id']},
            'spatialCoverage': PLACE}
    if modified:
        page['dateModified'] = modified
    bc = _crumbs(path, labels)
    if bc:
        page['breadcrumb'] = bc
    if about:
        page['about'] = about
    graph.append(page)
    if path == '/open-data' and out_dir:
        cat = _datasets(out_dir)
        if cat:
            graph.append(cat)
            page['mainEntity'] = {'@id': cat['@id']}
    if path in ('/glossary', '/es/glosario'):
        try:
            from glossary import TERMS
            graph.append({'@type': 'DefinedTermSet', '@id': url + '#terms', 'name': title, 'url': url, 'inLanguage': lang,
                          'hasDefinedTerm': [{'@type': 'DefinedTerm', 'name': t['term'], 'description': t['simple'], 'url': f'{DOMAIN}/glossary#{t["id"]}'}
                                             for t in TERMS] if lang == 'en-US' else None})
            if graph[-1]['hasDefinedTerm'] is None:
                graph.pop()
        except Exception:
            pass
    s = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False)
    return '<script type="application/ld+json">' + s.replace('</', '<\\/') + '</script>\n'


def write_robots_and_sitemap(out_dir, pages, alternates, lastmod):
    """robots.txt pointing at sitemap.xml; sitemap lists every public page with lastmod and en/es alternates."""
    open(os.path.join(out_dir, 'robots.txt'), 'w').write(
        'User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\nDisallow: /alerts/manage\n\n'
        f'Sitemap: {DOMAIN}/sitemap.xml\n')
    rows = []
    for path in sorted({p for p in pages if not p.startswith(PRIVATE) and p != '/404'}):
        alt = alternates(path)
        x = f'  <url>\n    <loc>{_h.escape(DOMAIN + path)}</loc>\n'
        m = lastmod(path)
        if m:
            x += f'    <lastmod>{m}</lastmod>\n'
        for lang, u in alt:
            x += f'    <xhtml:link rel="alternate" hreflang="{lang}" href="{_h.escape(DOMAIN + u)}"/>\n'
        rows.append(x + '  </url>')
    open(os.path.join(out_dir, 'sitemap.xml'), 'w').write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + '\n'.join(rows) + '\n</urlset>\n')
    return len(rows)
