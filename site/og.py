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


def _card(eyebrow, title, stat, label, desc, mapsvg, logo):
    t = html.escape(title)
    size = 66 if len(title) <= 26 else 58 if len(title) <= 40 else 50
    stat_html = (f'<div class="stat"><b>{html.escape(stat)}</b><span>{html.escape(label)}</span></div>' if stat
                 else f'<p class="desc">{html.escape(desc)}</p>')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Regular.ttf);font-weight:400}}
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Medium.ttf);font-weight:500}}
@font-face{{font-family:P;src:url(file://{FONT}/Poppins-Bold.ttf);font-weight:600}}
*{{box-sizing:border-box;margin:0}}
body{{width:{W}px;height:{H}px;overflow:hidden;background:#F6F8FB;font-family:P,sans-serif;color:#161B24;position:relative}}
.bar{{position:absolute;left:0;top:0;bottom:0;width:14px;background:#1E3A76}}
.l{{position:absolute;left:78px;top:62px;bottom:100px;width:640px;display:flex;flex-direction:column}}
.brand{{display:flex;align-items:center;gap:12px;font-weight:600;font-size:30px;letter-spacing:-.01em}}
.brand i{{font-style:normal;color:#E5564A}}
.eb{{margin-top:50px;font-size:20px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#3F6FB0}}
h1{{margin-top:12px;font-size:{size}px;line-height:1.1;font-weight:600;letter-spacing:-.025em;color:#1E3A76}}
.stat{{margin-top:auto;display:flex;flex-direction:column;gap:2px}}
.stat b{{font-size:54px;font-weight:600;letter-spacing:-.02em;color:#161B24;line-height:1.1}}
.stat span{{font-size:22px;color:#5A6372}}
.desc{{margin-top:auto;font-size:25px;line-height:1.45;color:#5A6372;max-width:620px}}
.r{{position:absolute;right:70px;top:62px}}
.r svg{{display:block}}
.county{{fill:#DCE6F3;stroke:#3F6FB0;stroke-width:2.2;stroke-linejoin:round}}
.city path{{fill:#3F6FB0;opacity:.55}}
.foot{{position:absolute;left:78px;right:70px;bottom:0;height:72px;border-top:1px solid #E1E6ED;display:flex;justify-content:space-between;align-items:center;font-size:18px;color:#8A93A1}}
.foot img{{height:22px}}
.foot span b{{color:#5A6372;font-weight:500}}
</style></head><body><div class="bar"></div>
<div class="l"><div class="brand"><svg width="30" height="30" viewBox="0 0 24 24"><path d="M12 2C7.6 2 4 5.5 4 9.9 4 15.6 12 22 12 22s8-6.4 8-12.1C20 5.5 16.4 2 12 2z" fill="#3F6FB0"/><circle cx="12" cy="10" r="3.2" fill="#fff"/></svg><span>BayCounty<i>.me</i></span></div>
<div class="eb">{html.escape(eyebrow)}</div><h1>{t}</h1>{stat_html}</div>
<div class="r">{mapsvg}</div>
<div class="foot"><span><b>Public records, in plain view</b> · baycounty.me</span>{f'<img src="{logo}">' if logo else ''}</div>
</body></html>'''


def cards_for(pages, MENU):
    """Card content per page path."""
    import sys
    sys.path.insert(0, HERE)
    from home import stats, topics
    s = stats()
    tp = {t[0]: t for t in topics(s)}
    grp = {i['href']: f'{m["label"]} · {i["label"]}' for m in MENU for g in m.get('groups', []) for i in g['items']}
    v = json.load(open(os.path.join(ROOT, 'data', 'votes', 'votes.json')))
    out = {}
    for path, title, desc, _ in pages:
        t = tp.get(path)
        stat, label = (t[4], t[5]) if t else ('', '')
        head = t[2] if t else title
        if path == '/':
            head, stat, label = 'Local government, in plain view.', f'${s["lv_tot"]/1e6:,.0f}M', 'in property tax levied by Bay County governments, FY2026'
        elif path == '/who-runs-bay-county':
            head, stat, label = 'Who runs Bay County', '9 governments', 'every elected seat, appointed manager and top salary'
        elif path == '/public-money/votes':
            head, stat, label = 'How they voted', f'{len(v["votes"])} votes', 'on budgets, tax rates, contracts and borrowing'
        elif path == '/my-address':
            head = 'What does your address pay, and who represents it?'
        sub = SUBTITLE.get(path)
        out[path] = dict(eyebrow=grp.get(path, SECTION.get(path, 'BayCounty.me')), title=head, stat=stat, label=label,
                         desc=sub or (desc if len(desc) < 110 else desc[:desc.rfind(' ', 0, 107)] + '…'))
    return out


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
        h = hashlib.sha1(json.dumps(c, sort_keys=True).encode() + b'v5').hexdigest()[:12]
        fn = os.path.join(dest, slug(path) + '.png')
        if cache.get(path) != h or not os.path.exists(fn):
            todo[path] = (c, fn, h)
    if todo:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print('og: playwright not installed, keeping existing images'); todo = {}
    if todo:
        import base64
        lp = os.path.join(out_dir, 'assets', 'flux-labs.webp')
        logo = 'data:image/webp;base64,' + base64.b64encode(open(lp, 'rb').read()).decode() if os.path.exists(lp) else ''
        mapsvg = _map_svg()
        tmp = os.path.join(dest, '_card.html')
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(viewport={'width': W, 'height': H})
            for path, (c, fn, h) in todo.items():
                open(tmp, 'w').write(_card(c['eyebrow'], c['title'], c['stat'], c['label'], c['desc'], mapsvg, logo))
                pg.goto('file://' + tmp); pg.wait_for_timeout(150)
                pg.screenshot(path=fn); cache[path] = h
            b.close()
        os.remove(tmp)
        json.dump(cache, open(cache_f, 'w'), indent=0, sort_keys=True)
    icon = os.path.join(dest, 'apple-touch-icon.png')
    if not os.path.exists(icon):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(viewport={'width': 180, 'height': 180})
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
