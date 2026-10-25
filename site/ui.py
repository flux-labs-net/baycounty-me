"""Shared page pieces, first built for the government pages (PR #78) and now used site-wide.

ico()      an icon (a CSS mask in ui.css, so it takes the text color); with a tone it sits in a tinted square
icon_for() picks an icon and tone for a section heading or stat label from its words
enhance()  gives a page built on the standard skeleton (header.tx-top, the government bar, section headings,
           .kpis) the shared look: a header with an icon badge and a picker card, section tiles with a one-line
           preview, an icon on each section heading and stat card, and a friendlier "simple version" box.
           layout() runs it on every page, so a new page gets it by using the same skeleton.
"""
import html
import re

TONES = ['blue', 'teal', 'amber', 'salmon']


def ico(name, tone=None):
    i = f'<span class="ico i-{name}" aria-hidden="true"></span>'
    return f'<span class="ui-ti t-{tone}">{i}</span>' if tone else i


def avatar(name, tone, icon=None):
    """Initials (or an icon) in a tinted circle, for people and organizations."""
    if icon:
        return f'<span class="ui-av t-{tone}">{ico(icon)}</span>'
    parts = [w for w in re.sub(r'["(].*', '', name or '').split() if w[:1].isalpha()]
    ini = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper() if parts else '?'
    return f'<span class="ui-av t-{tone}" aria-hidden="true">{html.escape(ini)}</span>'


def tone_of(text):
    """A steady tone for a name, so the same person or company gets the same color on every page."""
    return TONES[sum(map(ord, text or '')) % len(TONES)]


# words in a heading or label -> (icon, tone); the first match wins
WORDS = [
    (r'\bvot|split', 'vote', 'amber'),
    (r'meeting|agenda|coming up|schedule', 'calendar', 'salmon'),
    (r'change order|grew|growth|went up|increase', 'trend', 'salmon'),
    (r'emergenc', 'flag', 'salmon'),
    (r'contract|award|\bbid', 'file', 'blue'),
    (r'\brules?\b|\blaws?\b|threshold|statute', 'gavel', 'blue'),
    (r'compiled|sources?\b|\bgaps?\b|method|caveat|fine print|couldn', 'info', 'teal'),
    (r'debt|\bowe|borrow|loan|bond|pension', 'dollar', 'salmon'),
    (r'audit|finding|flag', 'search', 'teal'),
    (r'saving|spend less|could save', 'piggy', 'teal'),
    (r'hurricane|michael|fema|recovery|disaster', 'storm', 'teal'),
    (r'\bcra\b|redevelop', 'columns', 'teal'),
    (r'tourism|tourist|visitor|bed tax|beach', 'sun', 'amber'),
    (r'exempt|homestead', 'home', 'teal'),
    (r'tax rate|millage|\bmills?\b|rate', 'percent', 'amber'),
    (r'\btax|\bbill|\bfee|garbage|water|utilit', 'receipt', 'amber'),
    (r'gift|donor|donat|campaign|raised|contribut', 'heart', 'salmon'),
    (r'nonprofit|charit|foundation', 'heart', 'teal'),
    (r'connection|network|\bties\b|linked|shared|money map', 'network', 'blue'),
    (r'salar|\bpay\b|paid to|employee|staff|position', 'briefcase', 'blue'),
    (r'paid|payment|payee|check register|warrant|spent|spending', 'dollar', 'blue'),
    (r'budget|fund|department|revenue|expens', 'wallet', 'blue'),
    (r'project|built|construction|road|sales tax', 'crane', 'salmon'),
    (r'grant', 'wallet', 'teal'),
    (r'business|compan|vendor|owner|firm|corporat', 'store', 'blue'),
    (r'official|people|person|everyone|who |candidate|running|member|seat|board|elected|commission|council', 'users', 'blue'),
    (r'\bmaps?\b|location|district|zone', 'map', 'teal'),
    (r'letter|request|record|ask|correspond|email|alert', 'mail', 'blue'),
    (r'download|\bdata|csv|\bapi\b|dataset', 'download', 'blue'),
    (r'update|what.s new|change ?log|news', 'news', 'blue'),
    (r'search|look up|find', 'search', 'blue'),
    (r'compar|side by side|\bvs\b', 'compare', 'teal'),
    (r'trend|over time|history|year|since', 'trend', 'blue'),
    (r'address|property|home|parcel', 'pin', 'teal'),
    (r'glossary|term|word|explain|read', 'book', 'teal'),
    (r'school|student', 'school', 'amber'),
    (r'\bcit(y|ies)\b|government', 'city', 'blue'),
]
_WORDS = [(re.compile(p, re.I), i, t) for p, i, t in WORDS]


def icon_for(text, i=0):
    """The icon and tone for a heading or label; unmatched text gets a neutral chart icon in a rotating tone."""
    for rx, ic, tone in _WORDS:
        if rx.search(text or ''):
            return ic, tone
    return 'chart', TONES[i % len(TONES)]


# the six menu sections: their icon and tone, for the kicker above a page title
SECTION_LOOK = {'Governments': ('county', 'blue'), 'Taxes': ('receipt', 'amber'), 'Spending': ('wallet', 'teal'),
                'Watchdog': ('shield', 'salmon'), 'People': ('users', 'blue'), 'Take part': ('megaphone', 'teal')}
# each page's badge icon (its tone comes from its menu section)
PAGE_ICON = {
    '/who-runs-bay-county': 'users', '/governments': 'county', '/compare': 'compare',
    '/my-address': 'pin', '/public-money/tax-dollars': 'receipt', '/public-money/fees-and-bills': 'drop',
    '/public-money/exemptions': 'home', '/public-money/tourist-tax': 'sun', '/public-money/amendment-3': 'vote',
    '/public-money/budget-explorer': 'wallet', '/public-money/budget-compare': 'trend', '/public-money/checkbook': 'wallet', '/public-money/budget-tracker': 'columns', '/public-money/cra-spending': 'columns', '/public-money/sales-tax-projects': 'crane',
    '/public-money/hurricane-michael': 'storm', '/public-money/debt': 'dollar', '/public-money/map': 'map',
    '/public-money/accountability': 'shield', '/public-money/contracts': 'file', '/public-money/vendors': 'store',
    '/public-money/who-gets-paid': 'dollar', '/public-money/votes': 'vote', '/public-money/savings': 'piggy',
    '/public-money/audits': 'search', '/connections': 'network', '/elections': 'flag', '/connections/campaign-gifts': 'heart',
    '/connections/money-map': 'link', '/connections/business-ties': 'store', '/connections/shared-owners': 'network',
    '/connections/nonprofits': 'heart', '/meetings': 'calendar', '/alerts': 'bell', '/records-request': 'mail',
    '/correspondence': 'mail', '/glossary': 'book', '/open-data': 'download', '/developers': 'code', '/updates': 'news',
    '/about': 'info', '/privacy': 'shield', '/search': 'search', '/people': 'users', '/profile': 'user',
}
_SECTION_OF = {}


def _section_of(path):
    if not _SECTION_OF:
        from site_menu import menu
        for m in menu():
            hrefs = [m['start']['href']] + [it['href'] for g in m.get('groups', []) for it in g['items']]
            for h in hrefs:
                _SECTION_OF.setdefault(h, m['label'])
        _SECTION_OF.update({'/people': 'People', '/profile': 'People', '/search': 'Take part', '/privacy': 'Take part'})
    if path in _SECTION_OF:
        return _SECTION_OF[path]
    for pre, lab in (('/people/', 'People'), ('/public-money/vendors/', 'Watchdog'), ('/governments/', 'Governments')):
        if path.startswith(pre):
            return lab
    return None


def _block(s, start, tag='div'):
    """The end index of the balanced <tag ...>...</tag> that opens at s[start]."""
    rx = re.compile(rf'<{tag}\b|</{tag}>')
    depth = 0
    for m in rx.finditer(s, start):
        depth += 1 if m.group(0) != f'</{tag}>' else -1
        if depth == 0:
            return m.end()
    return len(s)


def _text(h):
    return html.unescape(re.sub(r'<[^>]+>', '', h or '')).strip()


def _short(t, n=64):
    t = re.sub(r'\s+', ' ', t).strip()
    return t if len(t) <= n else t[:n].rsplit(' ', 1)[0].rstrip(',;:·') + '…'


def _hero(body, path):
    m = re.search(r'<header class="tx-top">', body)
    if not m:
        return body
    h0, h1 = m.start(), body.index('</header>', m.start()) + len('</header>')
    head = body[h0:h1]
    # the government bar right after the header moves into the picker card, as on the government pages
    rest = body[h1:]
    lead = len(rest) - len(rest.lstrip())
    scope = ''
    if rest.lstrip().startswith('<div class="scope"'):
        s0 = h1 + lead
        s1 = _block(body, s0)
        scope, body = body[s0:s1], body[:s0] + body[s1:]
    stamp = ''
    sm = re.search(r'<div class="stamp">', head)
    if sm:
        s1 = _block(head, sm.start())
        stamp, head = head[sm.start():s1], head[:sm.start()] + head[s1:]
    es = path.startswith('/es')
    sec = None if es else _section_of(path)
    sec_icon, tone = SECTION_LOOK.get(sec, ('grid', 'blue'))
    title = _text((re.search(r'<h1[^>]*>(.*?)</h1>', head, re.S) or [None, ''])[1])
    badge = PAGE_ICON.get(path) or ('user' if path.startswith('/people/') else 'store' if path.startswith('/public-money/vendors/') else icon_for(title)[0])
    # the kicker: the menu section, with its icon (pages whose eyebrow is a real breadcrumb keep it)
    em = re.search(r'<span class="eyebrow">(.*?)</span>', head, re.S)
    if em and sec and '<a ' not in em.group(1):
        head = head[:em.start()] + f'<span class="eyebrow ui-kick k-{tone}">{ico(sec_icon)}{html.escape(sec)}</span>' + head[em.end():]
    elif em:
        head = head[:em.start()] + f'<span class="eyebrow ui-kick k-{tone}">{em.group(1)}</span>' + head[em.end():]
    inner = head[len('<header class="tx-top">'):]
    inner = inner[:-len('</header>')] if inner.endswith('</header>') else inner
    pick = ''
    links = re.findall(r'<a class="pill"([^>]*)>(.*?)</a>', stamp, re.S)
    if stamp and not scope and links and not re.sub(r'<a class="pill"[^>]*>.*?</a>|<div class="stamp">|</div>|\s', '', stamp, flags=re.S):
        # only links to related pages: they become tags under the title, not a card
        tags = ''.join(f'<a class="ui-tag"{a}>{ico(icon_for(_text(t))[0])}{t}</a>' for a, t in links)
        inner_tags = f'<div class="ui-tags">{tags}</div>'
        stamp = ''
    else:
        inner_tags = ''
    if scope or stamp:
        stamp = stamp.replace('<div class="stamp">', '<div class="stamp ui-stamp">', 1)
        pick = f'<div class="ui-pick{" no-scope" if not scope else ""}" data-report="skip">{scope}{stamp}</div>'
    if path.startswith('/people/') and title:
        # a person's page: their initials, in the same color as their card in the People directory
        ini = re.search(r'>([^<]*)</span>$', avatar(title, 'blue')).group(1)
        badge_h = f'<span class="ui-badge ui-badge-av t-{tone_of(title)}" aria-hidden="true">{ini}</span>'
    elif path.startswith('/public-money/vendors/') and title:
        badge_h = f'<span class="ui-badge t-{tone_of(title)}">{ico(badge)}</span>'
    else:
        badge_h = f'<span class="ui-badge t-{tone}">{ico(badge)}</span>'
    new = (f'<header class="tx-top ui-hero"><div class="ui-id">{badge_h}'
           f'<div class="ui-hd">{inner}{inner_tags}</div></div>{pick}</header>')
    return body[:h0] + new + body[h1:]


def _sections(body):
    """Icons on section headings; returns the new body and the tiles for sections whose heading has an id."""
    tiles = []
    n = [0]

    def sub(m):
        attrs, hd = m.group(1), m.group(2)
        if 'ui-ti' in hd:
            return m.group(0)
        h2 = re.search(r'<h2([^>]*)>(.*?)</h2>', hd, re.S)
        if not h2:
            return m.group(0)
        name = _text(h2.group(2))
        short = re.search(r'\bdata-tile="([^"]+)"', h2.group(1))  # a shorter name for the tile, when the heading is long
        ic, tone = icon_for(name, n[0])
        n[0] += 1
        hid = re.search(r'\bid="([^"]+)"', h2.group(1))
        if hid and ' hidden' not in attrs and 'method' not in attrs:
            mu = re.search(r'<span class="muted"', hd)
            sub_txt = _text(hd[mu.start():_block(hd, mu.start(), 'span')]) if mu else ''
            tiles.append((hid.group(1), ic, tone, html.unescape(short.group(1)) if short else name, _short(sub_txt, 80)))
        return f'<section{attrs}><div class="sec-hd">{ico(ic, tone)}{hd}'
    body = re.sub(r'<section([^>]*\btx-sec\b[^>]*)>\s*<div class="sec-hd">(.*?)(?=</div>)', sub, body, flags=re.S)
    return body, tiles


def _kpis(body):
    n = [0]

    def sub(m):
        cls, attrs, label = m.group(1), m.group(2), m.group(3)
        if 'ui-k' in cls:
            return m.group(0)
        ic, tone = icon_for(_text(label), n[0])
        n[0] += 1
        return f'<div class="{cls} ui-k"{attrs}><span class="kh">{ico(ic, tone)}<span class="eyebrow">{label}</span></span>'
    return re.sub(r'<div class="(kpi(?: [\w-]+)*)"([^>]*)>\s*<span class="eyebrow">(.*?)</span>', sub, body, flags=re.S)


def tiles_html(tiles):
    t = ''.join(f'<a href="#{i}" data-jump="{i}">{ico(ic, tone)}<span><b>{html.escape(name)}</b>{f"<small>{html.escape(sub)}</small>" if sub else ""}</span></a>'
                for i, ic, tone, name, sub in tiles)
    mini = ''.join(f'<a href="#{i}">{ico(ic)}{html.escape(_short(name, 22))}</a>' for i, ic, tone, name, sub in tiles)
    return (f'<nav class="ui-tiles" aria-label="On this page" data-report="skip">{t}</nav>'
            f'<nav class="ui-mini" aria-label="Sections" data-off data-report="skip">{mini}</nav>')


def enhance(body, path):
    """The shared look for a page built on the standard skeleton. Pages that already use it (the government pages)
    and pages without the skeleton pass through unchanged."""
    if 'class="tx-top"' not in body or path.startswith('/admin'):
        return body
    body = re.sub(r'<div class="page tax(?=[ "])', '<div class="page tax ui', body, count=1)
    body = _hero(body, path)
    body, tiles = _sections(body)
    body = _kpis(body)
    body = body.replace('<span class="eyebrow">The simple version</span>',
                        f'<span class="ui-ex-hd">{ico("bulb", "amber")}<span class="eyebrow">The simple version</span></span>')
    body = body.replace('<span class="eyebrow">La versión sencilla</span>',
                        f'<span class="ui-ex-hd">{ico("bulb", "amber")}<span class="eyebrow">La versión sencilla</span></span>')
    if len(tiles) >= 3:
        end = body.index('</header>', body.index('ui-hero')) + len('</header>')
        body = body[:end] + tiles_html(tiles) + body[end:]
    return body



def dir_card(href, name, sub='', where='', count='', kinds='', govs='', n=0, av=None, tone=None, also='', city=''):
    """One card in a directory: initials (or an icon), the name (the whole card opens it), a line under it,
    where they serve (links of their own) and a small count. kinds/govs feed the chips and the government filter;
    city is a data_g() attribute when the page's government bar should hide cards of other governments."""
    tone = tone or tone_of(name)
    sub_h = f'<small>{html.escape(sub)}</small>' if sub else ''
    where_h = f'<span class="ui-dc-w">{ico("city")}<span>{where}</span></span>' if where else ''
    count_h = f'<span class="ui-dc-n">{count}</span>' if count else ''
    return (f'<div class="ui-dc" data-n="{html.escape(name)}" data-s="{html.escape((name + ' ' + also + ' ' + sub).lower())}" data-k="{html.escape(kinds)}" data-gv="{html.escape(govs)}" data-c="{n}"{city}>'
            f'{av or avatar(name, tone)}<span class="ui-dc-t"><a class="ui-dc-a" href="{html.escape(href)}">{html.escape(name)}</a>{sub_h}{where_h}</span>{count_h}</div>')


def directory(cards, label, chips=(), govs=(), search='Search', sorts=(('c', 'Most connected'), ('az', 'A to Z')), csv=None, csv_head='name,role,serves,connections,link'):
    """A searchable card grid. chips: [(kind, label, count)], the first shows everyone. govs: [(key, label)].
    sorts: 'c' by the card's number, 'az' by last name, 'name' by the whole name.
    csv: the file name for Download CSV (each card's name, line, place and count). ui.js does the filtering."""
    ch = ''.join(f'<button type="button" class="ui-chip" data-k="{k}" aria-pressed="{"true" if i == 0 else "false"}">{html.escape(t)} <b>{n}</b></button>'
                 for i, (k, t, n) in enumerate(chips))
    gs = ('<select data-dir-g aria-label="Government"><option value="">All governments</option>'
          + ''.join(f'<option value="{k}">{html.escape(t)}</option>' for k, t in govs) + '</select>') if govs else ''
    so = ('<select data-dir-s aria-label="Sort">' + ''.join(f'<option value="{k}">{html.escape(t)}</option>' for k, t in sorts) + '</select>') if sorts else ''
    chips_h = f'<div class="ui-chips" role="group" aria-label="Show">{ch}</div>' if ch else ''
    csv_h = f'<button type="button" class="ui-link" data-dir-csv="{html.escape(csv)}" data-head="{html.escape(csv_head)}">{ico("download")}Download CSV</button>' if csv else ''
    return (f'<div class="ui-dirbox"><div class="ui-find" data-report="skip"><label class="ui-q">{ico("search")}<input type="search" data-dir-q placeholder="{html.escape(search)}" aria-label="{html.escape(search)}"></label>{gs}{so}</div>'
            f'{chips_h}<div class="ui-dir-bar" data-report="skip"><span class="muted small" data-dir-count aria-live="polite"></span>{csv_h}</div>'
            f'<div class="ui-dir" data-ui-dir aria-label="{html.escape(label)}">{"".join(cards)}</div>'
            '<p class="muted ui-dir-none" data-dir-none hidden>No matches. Try fewer words or another filter.</p></div>')
