"""Link-preview (Open Graph) images for baycounty.me: one 1200x630 PNG per page.

Rendered with Playwright from an HTML card (site fonts, Bay County map), written to
public/og/<slug>.png. Cards are cached by content hash, so only changed ones re-render.
"""
import hashlib, html, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
W, H = 1200, 630
FONT = '/usr/share/fonts/truetype/google-fonts'

SECTION = {
    '/': 'Bay County, Florida', '/my-address': 'My Address', '/who-runs-bay-county': 'Officials',
    '/glossary': 'Plain-English guide', '/updates': "What's new", '/search': 'Search', '/about': 'About',
}


SUBTITLE = {
    '/my-address': 'Tax estimate, representatives, schools, flood zone and more for any Bay County address.',
    '/glossary': 'CRAs, millage, rolled-back rates and every other term on the site, explained simply.',
    '/updates': 'New pages, new data and corrections, newest first.',
    '/search': 'Search every page and record: payments, projects, contracts, votes and audits.',
    '/about': 'An independent project putting Bay County public records in plain view.',
}


def slug(path):
    return 'home' if path == '/' else path.strip('/').replace('/', '-')


def _map_svg():
    """County outline with city limits, projected to a 430x470 box."""
    b = json.load(open(os.path.join(ROOT, 'geo', 'basemap.json')))
    polys = [p for p in b['county']]
    xs = [x for p in polys for r in p for x, _ in r]; ys = [y for p in polys for r in p for _, y in r]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    k = min(380 / ((x1 - x0) * 0.866), 430 / (y1 - y0))  # cos(30N) aspect

    def path(ps):
        return ''.join('M' + 'L'.join(f'{(x - x0) * 0.866 * k:.1f},{(y1 - y) * k:.1f}' for x, y in r) + 'Z' for p in ps for r in p)
    w, h = (x1 - x0) * 0.866 * k, (y1 - y0) * k
    cities = ''.join(f'<path d="{path(ps)}"/>' for ps in b['cities'].values())
    return (f'<svg viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'<path class="county" d="{path(polys)}"/><g class="city">{cities}</g></svg>')


TONE = {'gov': 'Government', 'person': 'Official', 'vendor': 'Vendor', 'money': 'Public money', 'page': 'BayCounty.me'}


def _fit(t, sizes):
    for n, px in sizes:
        if len(t) <= n:
            return px
    return sizes[-1][1]


def _card(c, mapsvg):
    """Direction A: deep navy, one big amber figure, faint county outline, four-color strip."""
    e = html.escape
    stat = c.get('stat') or ''
    ss = _fit(stat, [(6, 168), (9, 140), (13, 110), (99, 84)])
    title = c['title']
    ts = _fit(title, [(18, 76), (28, 60), (44, 50), (70, 44), (999, 38)]) if stat else _fit(title, [(28, 76), (44, 64), (70, 54), (999, 46)])
    body = (f'<div class="stat"><b class="num">{e(stat)}</b><span>{e(c.get("label") or "")}</span></div>' if stat
            else f'<p class="desc">{e(c.get("desc") or "")}</p>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Regular.ttf);font-weight:400}}
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Medium.ttf);font-weight:500}}
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-SemiBold.ttf);font-weight:600}}
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Bold.ttf);font-weight:700}}
*{{box-sizing:border-box;margin:0}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:#14295A;color:#fff;font-family:P,sans-serif;position:relative;-webkit-font-smoothing:antialiased}}
.glow{{position:absolute;inset:0;background:radial-gradient(900px 500px at 85% 20%,#24488F 0%,transparent 60%)}}
.map{{position:absolute;right:-30px;top:60px;opacity:.13;transform:scale(1.35);transform-origin:top right}}
.map .county{{fill:#fff;stroke:none}} .map .city path{{fill:#14295A}}
.in{{position:absolute;inset:56px 72px 0 72px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;gap:24px}}
.wm{{display:flex;align-items:center;gap:10px;font-weight:700;font-size:30px;letter-spacing:-.01em;flex:none}} .wm i{{font-style:normal;color:#E5564A}}
.chip{{font-size:19px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#14295A;background:#E8A33D;padding:8px 16px;border-radius:999px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:640px}}
h1{{margin-top:44px;font-size:{ts}px;line-height:1.1;font-weight:600;letter-spacing:-.02em;max-width:{'900' if stat else '960'}px;text-wrap:balance}}
.sub{{margin-top:14px;font-size:28px;line-height:1.3;font-weight:500;color:#fff;opacity:.9;max-width:900px;text-wrap:balance;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}
.stat{{margin-top:auto;margin-bottom:58px}}
.stat b{{display:block;font-size:{ss}px;line-height:.95;font-weight:700;letter-spacing:-.035em;color:#E8A33D;font-variant-numeric:tabular-nums;white-space:nowrap}}
.stat span{{display:block;margin-top:16px;font-size:26px;line-height:1.3;color:#C9D6EE;max-width:820px}}
.desc{{margin-top:auto;margin-bottom:64px;font-size:30px;line-height:1.4;color:#C9D6EE;max-width:820px;text-wrap:pretty}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:12px;display:flex}} .bar i{{flex:1}}
</style></head><body><div class="glow"></div><div class="map">{mapsvg}</div>
<div class="in"><div class="top"><div class="wm"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M12 2C7.6 2 4 5.5 4 9.9 4 15.6 12 22 12 22s8-6.4 8-12.1C20 5.5 16.4 2 12 2z" fill="#fff"/><circle cx="12" cy="10" r="3.2" fill="#14295A"/></svg><span>BayCounty<i>.me</i></span></div><div class="chip">{e(c['eyebrow'])}</div></div>
<h1>{e(title)}</h1>{f'<p class="sub">{e(c["sub"])}</p>' if c.get('sub') else ''}{body}</div>
<div class="bar"><i style="background:#E5564A"></i><i style="background:#E8A33D"></i><i style="background:#1F8A7A"></i><i style="background:#3F6FB0"></i></div>
</body></html>"""


def _money(n):
    return f'${n/1e9:,.2f}B' if n >= 1e9 else f'${n/1e6:,.1f}M' if n >= 1e6 else f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}'


def _short(desc, n=150):
    return desc if len(desc) <= n else desc[:desc.rfind(' ', 0, n - 3)] + '…'


def gov_cards():
    """Government profiles: the adopted budget, else debt, else population."""
    from govs import GOVS, profile
    out = {}
    for g in GOVS:
        p = profile(g['key'])
        b = p.get('budget') or {}
        pr = (p.get('per_resident') or {}).get('budget')
        debt = (p.get('debt') or {}).get('total')
        if b.get('total'):
            stat, label = _money(b['total']), 'FY2026 budget' + (f', about ${pr:,.0f} per resident' if pr else '')
        elif debt:
            stat, label = _money(debt), 'owed in bonds, loans and other debt'
        else:
            stat, label = f"{p['population']:,}", 'residents'
        out[f"/governments/{g['slug']}"] = dict(kind='gov', eyebrow=g['short'] if g['kind'] != 'city' else f"City of {g['short']}",
                                                 title=f"{g['short']}: budget, taxes, debt and votes", stat=stat, label=label)
    return out


def person_cards():
    """Officials and candidates: recorded votes, else campaign money, else pay, else just their role."""
    import entity_graph as EG
    import people_pages as PP
    G = EG.build()
    mv, fin, cand = PP._by_person('member-votes'), PP._by_person('campaign-finance'), PP._by_person('candidates-2026')
    pay = {k: PP._by_person('officials-pay').get(k, []) + PP._by_person('salary-leaders').get(k, []) for k in [p['id'] for p in PP._people()]}
    out = {}
    for p in PP._people():
        pid = p['id']
        x = G.ents['person:' + pid]
        votes = mv.get(pid, [])
        raised = next((r['total_raised'] for r in cand.get(pid, []) + fin.get(pid, []) if r.get('total_raised')), None)
        sal = next((r.get('annual') or r.get('salary') for r in pay[pid] if (r.get('annual') or r.get('salary'))), None)
        if len(votes) >= 3:
            no = sum(1 for r in votes if str(r.get('vote')).lower() == 'no')
            stat, label = f'{len(votes):,} votes', 'recorded on budgets, taxes and contracts' + (f', {no} of them no' if no else ', every one shown')
        elif raised:
            stat, label = _money(raised), 'raised in their most recent campaign on file'
        elif sal:
            stat, label = _money(sal), 'annual pay, latest on file'
        else:
            stat, label = '', ''
        role = x.get('subtitle') or ''
        chip = '2026 candidate' if role.lower().startswith('2026 candidate') else 'Past candidate' if role.lower().startswith('ran for') else 'Official'
        out[f'/people/{pid}'] = dict(kind='person', eyebrow=chip, title=x['name'], sub=role, stat=stat, label=label,
                                     desc=('Campaign money, platform and connections, from public records.' if chip != 'Official'
                                           else 'Where they serve, campaign gifts from businesses and groups, recorded votes and connections.'))
    return out


def vendor_cards():
    """Vendors: contracts awarded, else payments found."""
    import vendor_pages as VP
    from govs import BY_KEY
    out = {}
    for vid, p in VP.build().items():
        n = len(p.get('gk') or p.get('govs') or [])
        where = f'{n} Bay County governments' if n > 1 else (BY_KEY[p['gk'][0]]['short'] if p.get('gk') and p['gk'][0] in BY_KEY else 'Bay County governments')
        nc = p['cnt'].get('contract', 0)
        if p.get('awarded'):
            stat, label = _money(p['awarded']), f"in {nc} contract{'s' if nc != 1 else ''} from {where}"
        elif p.get('paid'):
            stat, label = _money(p['paid']), f'in payments from {where}'
        else:
            stat, label = '', ''
        out[f'{VP.BASE}/{vid}'] = dict(kind='vendor', eyebrow='Vendor', title=p['v']['name'], stat=stat, label=label,
                                       desc='Contracts, payments, campaign gifts and how officials voted on its contracts.')
    return out


def cards_for(pages, MENU):
    """Card content per page path."""
    import sys
    sys.path.insert(0, HERE)
    from home import stats, topics
    s = stats()
    tp = {t[0]: t for t in topics(s)}
    from site_menu import links
    grp = {i['href']: i['label'] for m in MENU for i in links(m)}
    v = json.load(open(os.path.join(ROOT, 'data', 'votes', 'votes.json')))
    paths = {p for p, *_ in pages}
    extra = {}
    for f in (gov_cards, person_cards, vendor_cards):
        extra.update({k: c for k, c in f().items() if k in paths})
    out = {}
    for path, title, desc, _ in pages:
        if path in extra:
            out[path] = extra[path]
            continue
        t = tp.get(path)
        stat, label = (t[4], t[5]) if t else ('', '')
        head = t[2] if t else title
        if path == '/':
            head, stat, label = 'Your money. Their decisions. Follow it.', f'${s["lv_tot"]/1e6:,.1f}M', 'in property tax levied by Bay County governments, FY2026'
        elif path == '/who-runs-bay-county':
            head, stat, label = 'Who runs Bay County', '9 governments', 'every elected seat, appointed manager and top salary'
        elif path == '/public-money/votes':
            head, stat, label = 'How they voted', f'{len(v["votes"])} votes', 'on budgets, tax rates, contracts and borrowing'
        elif path == '/my-address':
            head = 'What does your address pay, and who represents it?'
        sub = SUBTITLE.get(path)
        out[path] = dict(kind='money' if path.startswith('/public-money') else 'page', eyebrow=grp.get(path, SECTION.get(path, 'En español' if path.startswith('/es') else 'BayCounty.me')),
                         title=head, stat=stat, label=label, desc=sub or _short(desc))
    return out


def _shrink(fn):
    """Cut the PNG to a 128-color palette (about a third of the size, no visible change on these flat cards)."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(fn).convert('RGB')
    im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(fn, optimize=True)


def _browser():
    """OG_CHROMIUM=/path/to/chrome uses an installed browser when the Python Playwright's own isn't downloaded."""
    exe = os.environ.get('OG_CHROMIUM')
    return {'executable_path': exe} if exe else {}


def build_og(out_dir, pages, menu):
    dest = os.path.join(HERE, 'og-cache'); os.makedirs(dest, exist_ok=True)
    cache_f = os.path.join(dest, '.cache.json')
    try:
        cache = json.load(open(cache_f))
    except Exception:
        cache = {}
    cards = cards_for(pages, menu)
    todo = {}
    for path, c in cards.items():
        h = hashlib.sha1(json.dumps(c, sort_keys=True).encode() + b'v6').hexdigest()[:12]
        fn = os.path.join(dest, slug(path) + '.png')
        if cache.get(path) != h or not os.path.exists(fn):
            todo[path] = (c, fn, h)
    if todo:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print('og: playwright not installed, keeping existing images'); todo = {}
    if todo:
        mapsvg = _map_svg()
        tmp = os.path.join(dest, '_card.html')
        with sync_playwright() as p:
            b = p.chromium.launch(**_browser()); pg = b.new_page(viewport={'width': W, 'height': H})
            for path, (c, fn, h) in todo.items():
                open(tmp, 'w').write(_card(c, mapsvg))
                pg.goto('file://' + tmp); pg.evaluate('document.fonts.ready')
                pg.screenshot(path=fn); _shrink(fn); cache[path] = h
            b.close()
        os.remove(tmp)
        cache = {k: v for k, v in cache.items() if k in cards}
        json.dump(cache, open(cache_f, 'w'), indent=0, sort_keys=True)
    icon = os.path.join(dest, 'apple-touch-icon.png')
    if not os.path.exists(icon):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(**_browser()); pg = b.new_page(viewport={'width': 180, 'height': 180})
            pg.set_content('<body style="margin:0;width:180px;height:180px;background:#1E3A76;display:grid;place-items:center"><svg width="112" height="112" viewBox="0 0 24 24"><path d="M12 2C7.6 2 4 5.5 4 9.9 4 15.6 12 22 12 22s8-6.4 8-12.1C20 5.5 16.4 2 12 2z" fill="#fff"/><circle cx="12" cy="10" r="3.2" fill="#1E3A76"/></svg></body>')
            pg.screenshot(path=icon); b.close()
    import shutil
    os.makedirs(os.path.join(out_dir, 'og'), exist_ok=True)
    for path in cards:
        f = os.path.join(dest, slug(path) + '.png')
        if os.path.exists(f):
            shutil.copy(f, os.path.join(out_dir, 'og', slug(path) + '.png'))
    if os.path.exists(icon):
        shutil.copy(icon, os.path.join(out_dir, 'apple-touch-icon.png'))
    print(f'og: {len(todo)} rendered, {len(cards) - len(todo)} cached')
    return {k: v for k, v in cache.items() if k in cards}


def preview_text():
    """Title and summary shown when a page link is pasted (og/twitter + meta description). Numbers come from the data."""
    import sys
    sys.path.insert(0, HERE)
    from home import stats
    import re

    def is_split(x):  # same rule as votes_page
        if isinstance(x.get('by_member'), dict) and 'no' in x['by_member'].values():
            return True
        m = re.search(r'(\d+)\s*(?:-|to)\s*(\d+)', x.get('tally') or '')
        return bool(m and int(m.group(2)) > 0)
    s = stats()
    v = json.load(open(os.path.join(ROOT, 'data', 'votes', 'votes.json')))['votes']
    nv, ns = len(v), sum(1 for x in v if is_split(x))
    M = lambda n: f'${n/1e9:,.2f}B' if n >= 1e9 else f'${n/1e6:,.1f}M'
    return {
        '/': ('Bay County, Florida: where the public money goes',
              'Look up your address, see where your property taxes go, and check spending, contracts, votes and debt for Bay County and every city. Sources on every figure.'),
        '/my-address': ('Look up your Bay County address',
                        "Your estimated property tax bill, who represents you, your zoned schools, flood and evacuation zones, and whether you're in a redevelopment district."),
        '/public-money/cra-spending': ("Where Bay County's CRA money goes",
                                       f"{M(s['cra_spent'])} across {s['cra_n']} records: what Bay County's six Community Redevelopment Agencies bought, built and granted, and who was paid. Mapped, with sources."),
        '/public-money/cra-tax-increment': ('How much property tax goes to the CRAs',
                                            "Bay County and its cities pay about $28.7M a year to seven Community Redevelopment Agencies, three-quarters of it to Front Beach Road. Year by year, who pays, and what's still to come."),
        '/public-money/tax-dollars': ('Where your Bay County property tax goes',
                                      f"{M(s['lv_tot'])} levied in FY2026. Estimate your own bill, see each government's slice, and track six years of tax rates for the county, schools and every city."),
        '/public-money/amendment-3': ('Amendment 3: what it would mean for Bay County',
                                      f"The state estimates Bay County governments would collect {M(s['a3'])} less in FY2029. See your bill before and after, and each government's share. No position taken."),
        '/public-money/hurricane-michael': ('Hurricane Michael: where the recovery money went',
                                            f"{M(s['fema'])} in FEMA rebuilding money across {s['fema_n']} Bay County projects, plus household aid, Rebuild Florida awards and debris costs. Every project listed."),
        '/public-money/tourist-tax': ("Bay County's bed tax: what visitors pay and where it goes",
                                      f"{M(s['bt25'])} collected in FY2025, {s['pcb_share']:.0%} from the Panama City Beach zone. Ten years of collections, how the 5% is split, and what Visit Panama City Beach spends."),
        '/public-money/sales-tax-projects': ('Half-cent sales tax projects: promised vs built',
                                             f"{s['sp_done']:,} of {s['sp_n']:,} Bay County infrastructure sales tax projects are marked complete. Every project on a map with its status, plus the school half-cent."),
        '/public-money/fees-and-bills': ('Fees on your Bay County tax bill, and utility bills',
                                         '$28.1M in flat fees on FY2026 tax bills, from fire to stormwater, plus a typical monthly water, sewer and garbage bill in each city.'),
        '/who-runs-bay-county': ('Who runs Bay County',
                                 'Every elected seat and appointed manager for Bay County, its seven cities and the school district, plus what top officials are paid.'),
        '/public-money/contracts': ("Who gets Bay County's contracts",
                                    f"{s['ct_n']} major contracts since 2022 from Bay County and its cities: who won, how they were awarded, change orders, emergency purchases and the biggest payees."),
        '/public-money/votes': ('How Bay County officials voted on money',
                                f"{nv} recorded votes on budgets, tax rates, contracts, land and borrowing, with every member's vote. {ns} were split, and those are listed first."),
        '/public-money/debt': ("What Bay County's governments owe",
                               f"{M(s['debt'])} owed by the county, schools, cities and authorities, including big single payments ahead and pension promises, from audited financial reports."),
        '/public-money/audits': ('What the auditors found in Bay County',
                                 f"{s['findings']} audit findings across Bay County governments in three years, explained in plain English, including {s['repeats']} repeated in the latest audits."),
        '/glossary': ('Government money, explained simply',
                      "What's a CRA? A mill? A rolled-back rate? Plain-English definitions of every term used on BayCounty.me, with examples."),
        '/updates': ("What's new on BayCounty.me", 'New pages, new data and corrections to BayCounty.me, newest first. Subscribe by RSS.'),
        '/search': ('Search Bay County public records',
                    'Search every BayCounty.me page and record: CRA payments, FEMA projects, contracts, votes, audit findings and glossary terms.'),
        '/about': ('About BayCounty.me',
                   'An independent project putting Bay County, Florida public records in plain view, built by Flux Labs in Panama City. Send a correction or a record.'),
    }
