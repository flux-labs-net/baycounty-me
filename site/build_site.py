"""Static site generator for baycounty.me.

Pages share one layout: head, top menu (with sub-menus), and a 'Powered by Flux Labs' footer.
Add a new page by adding an entry to MENU (for the menu) and to PAGES (for the file).
"""
import json, os, re, shutil, base64

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'public')
SITE = 'BayCounty.me'
DOMAIN = 'https://baycounty.me'

# Menu: top-level items; an item with 'children' becomes a drop-down.
MENU = [
    {'label': 'Home', 'href': '/'},
    {'label': 'Public Money', 'children': [
        {'label': 'CRA Spending', 'href': '/public-money/cra-spending',
         'desc': 'Where the six redevelopment agencies spend tax increment'},
    ]},
    {'label': 'About', 'href': '/about'},
]

TOKENS = open(os.path.join(ROOT, 'tokens.css')).read()
SITE_CSS = open(os.path.join(ROOT, 'site.css')).read()


def nav_html(active):
    items = []
    for m in MENU:
        if 'children' in m:
            on = any(c['href'] == active for c in m['children'])
            kids = ''.join(
                f'<li><a href="{c["href"]}"{" aria-current=\"page\"" if c["href"] == active else ""}>'
                f'<span class="k">{c["label"]}</span><span class="kd">{c["desc"]}</span></a></li>'
                for c in m['children'])
            items.append(
                f'<li class="has-sub{" on" if on else ""}"><button type="button" class="sub-toggle" aria-expanded="false">'
                f'{m["label"]}<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>'
                f'<ul class="nav-sub">{kids}</ul></li>')
        else:
            cur = ' aria-current="page"' if m['href'] == active else ''
            items.append(f'<li><a href="{m["href"]}"{cur}>{m["label"]}</a></li>')
    return f'''<header class="site-head"><div class="site-head-in">
  <a class="wordmark" href="/" aria-label="{SITE} home"><svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.6 2 4 5.5 4 9.9 4 15.6 12 22 12 22s8-6.4 8-12.1C20 5.5 16.4 2 12 2z" fill="var(--blue)"/><circle cx="12" cy="10" r="3.2" fill="var(--bg)"/></svg><span>BayCounty<b>.me</b></span></a>
  <button type="button" class="theme-btn" id="themeBtn" aria-label="Theme: match system"><svg class="ti ti-system" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg><svg class="ti ti-light" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 2v2.2M10 15.8V18M2 10h2.2M15.8 10H18M4.3 4.3l1.6 1.6M14.1 14.1l1.6 1.6M4.3 15.7l1.6-1.6M14.1 5.9l1.6-1.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><svg class="ti ti-dark" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M16 12.6A6.6 6.6 0 0 1 7.4 4a6.6 6.6 0 1 0 8.6 8.6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg><span class="theme-lbl">System</span></button>
  <button type="button" class="menu-btn" aria-expanded="false" aria-controls="site-menu"><span class="sr">Menu</span><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" stroke-width="1.8"/></svg></button>
  <nav aria-label="Main"><ul id="site-menu" class="menu">{"".join(items)}</ul></nav>
</div></header>'''


FOOTER = '''<footer class="site-foot"><div class="site-foot-in">
  <div class="foot-about"><p><b>BayCounty.me</b> puts Bay County, Florida public records in plain view: maps, money, and the documents behind them.</p>
  <p class="muted">Found an error or have a record to add? Email <span class="sel">hello@fluxlabs.net</span>.</p></div>
  <a class="powered" href="https://fluxlabs.net/" target="_blank" rel="noopener"><span>Powered by</span><img src="/assets/flux-labs.webp" alt="Flux Labs" width="140" height="25"></a>
</div></footer>'''

MENU_JS = '''<script>
(() => {
  const root = document.documentElement, tb = document.getElementById('themeBtn');
  const NAMES = {system: 'System', light: 'Light', dark: 'Dark'}, NEXT = {system: 'light', light: 'dark', dark: 'system'};
  const current = () => root.getAttribute('data-theme') || 'system';
  const show = m => { tb.dataset.mode = m; tb.querySelector('.theme-lbl').textContent = NAMES[m]; tb.setAttribute('aria-label', 'Theme: ' + (m === 'system' ? 'match system' : NAMES[m].toLowerCase()) + '. Click to change.'); };
  show(current());
  tb.addEventListener('click', () => {
    const m = NEXT[current()];
    if (m === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', m);
    try { if (m === 'system') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    show(m);
  });
  const btn = document.querySelector('.menu-btn'), menu = document.getElementById('site-menu');
  btn.addEventListener('click', () => { const o = btn.getAttribute('aria-expanded') === 'true'; btn.setAttribute('aria-expanded', !o); menu.classList.toggle('open', !o); });
  document.querySelectorAll('.sub-toggle').forEach(t => t.addEventListener('click', e => {
    e.stopPropagation(); const o = t.getAttribute('aria-expanded') === 'true';
    document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false'));
    t.setAttribute('aria-expanded', !o); }));
  document.addEventListener('click', e => { if (!e.target.closest('.has-sub')) document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); });
})();
</script>'''


def layout(title, desc, path, body, extra_head=''):
    full = f'{title} · {SITE}' if path != '/' else f'{SITE} · {title}'
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{DOMAIN}{path}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{DOMAIN}{path}">
<meta property="og:type" content="website">
<meta name="theme-color" content="#1E3A76">
<script>try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/site.css">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{nav_html(path)}
<main id="main">
{body}
</main>
{FOOTER}
{MENU_JS}
</body>
</html>
'''


def write(path, html):
    fp = os.path.join(OUT, path.strip('/'), 'index.html') if path != '/' else os.path.join(OUT, 'index.html')
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    open(fp, 'w').write(html)


PRINT_CSS = """
.stamp{display:flex;flex-direction:column;align-items:flex-end;gap:10px}
.pdf-btn{display:inline-flex;align-items:center;gap:7px;padding:7px 14px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font:500 .84rem var(--f-body);cursor:pointer}
.pdf-btn:hover{border-color:var(--blue);color:var(--blue)}
.print-meta{display:none}
@media print{
  @page{size:letter;margin:.5in .45in}
  :root:not(#print){--bg:#FFFFFF;--surface:#FFFFFF;--sunken:#F1F4F8;--ink:#161B24;--muted:#5A6372;--faint:#8A93A1;--line:#D9DFE7;
    --navy:#1E3A76;--blue:#3F6FB0;--salmon:#E5564A;--amber:#FFB84D;
    --water:#C9DCEF;--land:#FBFCFD;--landline:#AFC2D8;--city:#EEF1F5;--cityline:#CDD6E1;
    --c-pc:#3F6FB0;--c-pcb:#E5564A;--c-lh:#D18A1E;--c-cw:#22897C;--c-sf:#7B5FBF;--c-pk:#2F95C4;
    --good:#1F7A4D;--warn:#A86A00;--none:#8A93A1;color-scheme:light}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .filters,.maptools,.tip,.rail,#more,#csv,.pdf-btn,.prof p{display:none!important}
  .wrap{max-width:none;padding:0;gap:14px}
  header.top{padding-bottom:10px}
  .print-meta{display:block;font-size:8.5pt;color:var(--muted);margin:0}
  .kpis{grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
  .kpi{padding:8px 10px}.kpi .v{font-size:15pt}
  .stage{display:block}
  .mapbox{min-height:0;height:4.4in;break-inside:avoid}
  .legend{font-size:7pt}
  .profiles{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
  .prof{break-inside:avoid;padding:8px 10px;gap:6px}
  .tablewrap{overflow:visible;border:0;border-radius:0}
  table{min-width:0;font-size:7.5pt}
  th,td{padding:4px 5px}
  thead th{position:static}
  tr{break-inside:avoid}
  tbody tr:hover td{background:none}
  td a{color:inherit;text-decoration:none}
  td a::after{content:attr(href);display:block;font-size:6pt;color:var(--muted);word-break:break-all}
  .ctx{grid-template-columns:1fr;gap:8px}
  .print-hide{display:none!important}
  thead th[aria-sort]::after{content:none}
  details.cx{padding:8px 10px}
  details.cx summary,details.cx h4{break-after:avoid}
  details.cx li{break-inside:avoid}
  details.cx summary::after{content:none}
  details.cx a::after{content:" (" attr(href) ")";font-size:6.5pt;word-break:break-all;color:var(--muted)}
  .method{break-inside:avoid}
}
"""


def cra_page():
    t = open(os.path.join(ROOT, '..', 'assets', 'template.html')).read()
    data = json.load(open(os.path.join(ROOT, '..', 'data', 'dash_data.json')))
    t = re.sub(r'<title>.*?</title>\s*', '', t, flags=re.S)
    t = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\s*', '', t)
    t = re.sub(r'<link rel="preconnect"[^>]*>\s*<link rel="stylesheet"[^>]*>\s*', '', t, count=1)
    t = re.sub(r'\s*<img src="data:image/webp;base64,__LOGO__" alt="Flux Labs">', '', t)
    t = t.replace('<div class="brand">', '<div class="brand"><span class="eyebrow">Public Money · CRA Spending</span>', 1)
    t = t.replace('body{background:var(--bg);color:var(--ink);font:400 15px/1.55 var(--f-body);\n  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}', '')
    t = t.replace('.wrap{max-width:1360px;margin:0 auto;', '.wrap{max-width:1360px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));')
    t = t.replace('<div class="stamp">Research compiled Oct 20, 2026<br>Six CRAs · 14 districts</div>',
                  '<div class="stamp"><button type="button" id="pdf" class="pdf-btn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Research compiled Oct 20, 2026<br>Six CRAs · 14 districts</span></div>')
    t = t.replace('</header>\n\n  <div class="kpis" id="kpis"></div>', '</header>\n  <p class="print-meta" id="printMeta"></p>\n\n  <div class="kpis" id="kpis"></div>', 1)
    t = t.replace('</style>', PRINT_CSS + '</style>', 1)
    t = t.replace('<div class="hd"><h2>Ledger</h2><span class="muted" id="ledgerCount" style="font-size:.82rem"></span></div>',
                  '<div class="hd"><h2>Ledger</h2><span class="muted" style="font-size:.82rem"><span id="ledgerCount"></span> · <button type="button" id="csv" class="reset" style="padding:0">Download CSV</button></span></div>')
    # split script out; it loads its data from /data/*.json
    js = re.search(r'<script>(.*)</script>', t, re.S).group(1)
    t = t[:t.index('<script>')] + '<script src="/assets/cra.js" defer></script>\n'
    js = js.replace('const D = __DATA__;', '')
    csv_js = r"""
document.getElementById('csv').onclick = () => {
  const cols = ['CRA','District','Amount','Paid to','For what','Type','When','Status','Counted in totals','Why not counted','Location','Source type','Source','Notes'];
  const q = v => { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
  const rows = filtered().map(p => [CRA[p.cra].name, p.district, p.amount, p.payee, p.purpose, p.cat, p.when, p.status, p.count ? 'Yes' : 'No', p.overlap, p.loc || p.addr, p.conf, p.url, p.notes].map(q).join(','));
  const blob = new Blob([cols.join(',') + '\n' + rows.join('\n')], {type: 'text/csv'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'bay-county-cra-ledger.csv'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
"""
    pdf_js = r"""
const STATUS_LABEL = {Other:'Incoming / not CRA-funded'};
function filterSummary(){
  const parts = [S.cras.size ? [...S.cras].map(i=>SHORT[i]).join(', ') : 'All six CRAs'];
  if (S.status !== 'all') parts.push('Status: ' + (STATUS_LABEL[S.status] || S.status));
  if (S.cat !== 'all') parts.push('Type: ' + S.cat);
  if (S.q) parts.push('Search: "' + S.q + '"');
  if (!S.nc) parts.push('Rows left out of totals hidden');
  return parts.join(' · ');
}
let printState = null;
function beforePrint(){
  if (printState) return;
  printState = {showAll: S.showAll, open: [...document.querySelectorAll('details.cx')].map(d => d.open), vb: {...VB}};
  S.showAll = true; renderLedger(filtered());
  document.querySelectorAll('details.cx').forEach((d, i) => { d.open = true; d.classList.toggle('print-hide', S.cras.size > 0 && !S.cras.has(ORDER[i])); });
  document.querySelectorAll('.prof').forEach(b => b.classList.toggle('print-hide', S.cras.size > 0 && !S.cras.has(b.dataset.c)));
  const day = new Date().toLocaleDateString('en-US', {year:'numeric', month:'long', day:'numeric'});
  document.getElementById('printMeta').innerHTML = '<b>Report:</b> ' + esc(filterSummary()) + '<br><b>Exported</b> ' + day + ' from baycounty.me/public-money/cra-spending';
  fitView();
}
function afterPrint(){
  if (!printState) return;
  S.showAll = printState.showAll; renderLedger(filtered());
  document.querySelectorAll('details.cx').forEach((d, i) => d.open = printState.open[i]);
  document.querySelectorAll('.print-hide').forEach(e => e.classList.remove('print-hide'));
  setVB(printState.vb); printState = null;
}
window.addEventListener('beforeprint', beforePrint);
window.addEventListener('afterprint', afterPrint);
document.getElementById('pdf').onclick = () => { beforePrint(); setTimeout(() => window.print(), 60); };
"""
    js = ("(async () => {\n"
          "const [M, G, P1, P2] = await Promise.all(['/data/cra-meta.json','/data/cra-geo.json','/data/cra-pay-1.json','/data/cra-pay-2.json'].map(u => fetch(u).then(r => r.json())));\n"
          "const D = Object.assign({}, M, G, {payments: P1.concat(P2)});\n" + js + csv_js + pdf_js + "\n})();\n")
    # drop gap notes made obsolete by the official county GIS boundaries; tidy internal wording
    data['gaps'] = [g for g in data['gaps'] if 'boundary shapefiles' not in g['text'] and 'no GIS boundary file' not in g['text']]
    for g in data['gaps']:
        g['text'] = g['text'].replace(' The schema has no field for these.', '').replace('Several topics in the brief turned up nothing', 'Several topics turned up nothing')
    pays = data['payments']; half = len(pays) // 2
    files = {
        'data/cra-meta.json': {k: data[k] for k in ('cras', 'tif', 'controversies', 'gaps')},
        'data/cra-geo.json': {k: data[k] for k in ('districts', 'land', 'county', 'cities')},
        'data/cra-pay-1.json': pays[:half], 'data/cra-pay-2.json': pays[half:],
    }
    for fp, obj in files.items():
        json.dump(obj, open(os.path.join(OUT, fp), 'w'), separators=(',', ':'))
    open(os.path.join(OUT, 'assets', 'cra.js'), 'w').write(js)
    return t


def home_page():
    d = json.load(open(os.path.join(ROOT, '..', 'data', 'merged.json')))
    pays = d['payments']
    spent = sum(p['amount'] for p in pays if p['count'] and p['amount'] and p['status'] in ('Spent', 'Committed'))
    n = len(pays)
    return f'''<div class="page home">
  <section class="hero">
    <span class="eyebrow">Bay County, Florida</span>
    <h1>Local government, in plain view.</h1>
    <p class="lede">Maps, money and the public records behind them, for Panama City, Panama City Beach, Lynn Haven, Callaway, Springfield, Parker and the rest of Bay County. Every figure links to its source.</p>
  </section>

  <section class="section">
    <div class="sec-hd"><h2>Public Money</h2><span class="muted">Where tax dollars go, and who receives them</span></div>
    <a class="feature" href="/public-money/cra-spending">
      <div class="feature-txt">
        <span class="eyebrow">CRA Spending</span>
        <h3>Where Bay County's CRA money goes</h3>
        <p>The six Community Redevelopment Agencies keep part of the property tax growth inside their districts. This map and ledger show what they bought, built and granted, and who was paid.</p>
        <span class="go">Open the map →</span>
      </div>
      <dl class="feature-stats">
        <div><dt>CRAs</dt><dd>6</dd></div>
        <div><dt>Districts mapped</dt><dd>14</dd></div>
        <div><dt>Records</dt><dd>{n}</dd></div>
        <div><dt>Spent or committed, documented</dt><dd>${spent/1e6:.1f}M</dd></div>
      </dl>
    </a>
  </section>

  <section class="section how">
    <div class="sec-hd"><h2>How this site works</h2></div>
    <div class="cols">
      <div><h3>Public records only</h3><p>Figures come from audits, adopted budgets, annual reports, council resolutions and local reporting. If a number is not in a record, it is not on the site.</p></div>
      <div><h3>Sources on every row</h3><p>Each payment, grant or contract links to the document it came from, so you can check it yourself.</p></div>
      <div><h3>Gaps stated plainly</h3><p>Where a city does not publish something, such as a check register, the page says so and names the record to request.</p></div>
    </div>
  </section>
</div>'''


def about_page():
    return '''<div class="page prose">
  <span class="eyebrow">About</span>
  <h1>About BayCounty.me</h1>
  <p>BayCounty.me is an independent project that collects Bay County, Florida public records and turns them into maps and tables anyone can read. It starts with how local governments spend public money and will grow from there.</p>
  <h2>Where the information comes from</h2>
  <p>Everything on the site comes from documents the public can already request or download: city and county budgets, annual reports, audits filed with the Florida Auditor General, council and commission resolutions, Bay County GIS map layers, and reporting by local newsrooms. Each figure carries a link to its source.</p>
  <h2>What the labels mean</h2>
  <ul>
    <li><b>Spent</b>: the record reports the money as paid.</li>
    <li><b>Committed</b>: a contract or award has been approved but is not fully paid.</li>
    <li><b>Budgeted</b> or <b>Proposed</b>: a plan or appropriation, not a payment.</li>
  </ul>
  <p>Totals count each dollar once. When one record is part of another (a change order inside a project total, for example), it stays visible but is left out of the totals.</p>
  <h2>Corrections</h2>
  <p>If you find an error, or have a public record that fills a gap, email <span class="sel">hello@fluxlabs.net</span> with a link or a copy of the document. Corrections are dated on the page they affect.</p>
  <h2>Who runs it</h2>
  <p>BayCounty.me is built and hosted by <a href="https://fluxlabs.net/" target="_blank" rel="noopener">Flux Labs</a>, a managed IT services company in Panama City.</p>
</div>'''


PAGES = [
    ('/', 'Bay County public records, mapped', 'Maps, money and public records for Bay County, Florida, with a source on every figure.', home_page),
    ('/public-money/cra-spending', 'CRA Spending',
     'Interactive map and ledger of Bay County, Florida\'s six Community Redevelopment Agencies: who was paid, where, and for what.', cra_page),
    ('/about', 'About', 'What BayCounty.me is, where its information comes from, and how to send a correction.', about_page),
]


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'assets'))
    os.makedirs(os.path.join(OUT, 'data'))
    open(os.path.join(OUT, 'assets', 'site.css'), 'w').write(TOKENS + '\n' + SITE_CSS)
    shutil.copy(os.path.join(ROOT, '..', 'assets', 'logo_small.webp'), os.path.join(OUT, 'assets', 'flux-labs.webp'))
    shutil.copy(os.path.join(ROOT, 'favicon.svg'), os.path.join(OUT, 'favicon.svg'))
    for path, title, desc, fn in PAGES:
        write(path, layout(title, desc, path, fn()))
    open(os.path.join(OUT, '404.html'), 'w').write(layout('Page not found', 'Page not found', '/404',
        '<div class="page prose"><h1>That page isn\'t here.</h1><p><a href="/">Back to the home page</a></p></div>'))
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(dp, f); print(os.path.relpath(p, OUT), os.path.getsize(p))


if __name__ == '__main__':
    main()
