"""Static site generator for baycounty.me.

Pages share one layout: head, top menu (with sub-menus), and a 'Powered by Flux Labs' footer.
Add a new page by adding an entry to MENU (for the menu) and to PAGES (for the file).
"""
import json, os, re, shutil, base64, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from tax_page import tax_page
from amend_page import amend_page
from addr_page import addr_page
from michael_page import michael_page
from search_page import search_page, build_index
from debt_audit_page import debt_page, audits_page
from tourism_page import bedtax_page, surtax_page
from fees_page import fees_page, who_page
from contracts_page import contracts_page
from votes_page import votes_page
from updates import updates_page, rss, last_updated, nice as nice_date
OUT = os.path.join(ROOT, 'public')
SITE = 'BayCounty.me'
DOMAIN = 'https://baycounty.me'

# Menu: top-level items; an item with 'children' becomes a drop-down.
MENU = [
    {'label': 'Home', 'href': '/'},
    {'label': 'My Address', 'href': '/my-address'},
    {'label': 'Public Money', 'groups': [
        {'group': 'What you pay', 'items': [
            {'label': 'Tax Dollars', 'href': '/public-money/tax-dollars', 'desc': 'Your property tax bill, slice by slice'},
            {'label': 'Fees & Bills', 'href': '/public-money/fees-and-bills', 'desc': 'Fees on your tax bill, water and garbage'},
            {'label': 'Tourist Tax', 'href': '/public-money/tourist-tax', 'desc': 'The 5% bed tax visitors pay'},
            {'label': 'Amendment 3', 'href': '/public-money/amendment-3', 'desc': 'What the ballot amendment would change'},
        ]},
        {'group': 'Where it goes', 'items': [
            {'label': 'CRA Spending', 'href': '/public-money/cra-spending', 'desc': 'What redevelopment agencies paid for'},
            {'label': 'Sales Tax Projects', 'href': '/public-money/sales-tax-projects', 'desc': 'Half-cent projects: promised vs built'},
            {'label': 'Hurricane Michael', 'href': '/public-money/hurricane-michael', 'desc': 'FEMA, HUD and state recovery money'},
        ]},
        {'group': 'Accountability', 'items': [
            {'label': 'Contracts', 'href': '/public-money/contracts', 'desc': 'Who wins contracts, and how'},
            {'label': 'How They Voted', 'href': '/public-money/votes', 'desc': 'Every recorded vote on money decisions'},
            {'label': 'Debt', 'href': '/public-money/debt', 'desc': 'What each government owes'},
            {'label': 'Audit Findings', 'href': '/public-money/audits', 'desc': 'What outside auditors flagged'},
        ]},
    ]},
    {'label': 'Officials', 'href': '/who-runs-bay-county'},
    {'label': 'Glossary', 'href': '/glossary'},
    {'label': 'Search', 'href': '/search'},
    {'label': 'About', 'href': '/about'},
]

TOKENS = open(os.path.join(ROOT, 'tokens.css')).read()
SITE_CSS = open(os.path.join(ROOT, 'site.css')).read()


def nav_html(active):
    items = []
    for m in MENU:
        if 'groups' in m:
            on = any(c['href'] == active for g in m['groups'] for c in g['items'])
            cols = ''.join(
                f'<li class="nav-grp"><span class="nav-gh">{g["group"]}</span><ul>' + ''.join(
                    f'<li><a href="{c["href"]}"{" aria-current=\"page\"" if c["href"] == active else ""}>'
                    f'<span class="k">{c["label"]}</span><span class="kd">{c["desc"]}</span></a></li>' for c in g['items']) + '</ul></li>'
                for g in m['groups'])
            items.append(
                f'<li class="has-sub{" on" if on else ""}"><button type="button" class="sub-toggle" aria-expanded="false">'
                f'{m["label"]}<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>'
                f'<ul class="nav-sub nav-mega">{cols}</ul></li>')
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
  <p class="muted">Found an error or have a record to add? <a href="/about#contact">Send a correction</a> or email <span class="sel">hello@fluxlabs.net</span>.</p>
  <p class="muted foot-links">__UPDATED__<a href="/updates">What's new</a> · <a href="/updates.xml">RSS</a> · <a href="/about">Sources and method</a></p></div>
  <a class="powered" href="https://fluxlabs.net/" target="_blank" rel="noopener"><span>Powered by</span><img src="/assets/flux-labs.webp" alt="Flux Labs" width="140" height="25"></a>
</div></footer>'''

MENU_JS = '''(() => {
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
'''


TERM_JS = r"""
(() => {
  const G = __GLOSSARY__;
  let pop = null, cur = null, hideT = null, shownAt = 0;
  const ensure = () => {
    if (pop) return pop;
    pop = document.createElement('div'); pop.className = 'term-pop'; pop.id = 'term-pop';
    pop.setAttribute('role', 'tooltip'); pop.hidden = true; document.body.appendChild(pop);
    pop.addEventListener('pointerenter', () => clearTimeout(hideT));
    pop.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') later(); });
    return pop;
  };
  function show(el) {
    const g = G[el.dataset.term]; if (!g) return;
    ensure(); clearTimeout(hideT);
    if (cur && cur !== el) cur.removeAttribute('aria-describedby');
    if (cur !== el || pop.hidden) shownAt = Date.now();
    cur = el;
    pop.innerHTML = '<b></b><p></p><a></a>';
    pop.querySelector('b').textContent = g.term;
    pop.querySelector('p').textContent = g.simple;
    const a = pop.querySelector('a'); a.href = '/glossary#' + el.dataset.term; a.textContent = 'More in the glossary \u2192';
    pop.hidden = false; el.setAttribute('aria-describedby', 'term-pop');
    const r = el.getBoundingClientRect(), w = Math.min(300, innerWidth - 24);
    pop.style.width = w + 'px';
    const x = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 12));
    const h = pop.offsetHeight;
    let y = r.bottom + 8; if (y + h > innerHeight - 8) y = r.top - h - 8;
    pop.style.left = (x + scrollX) + 'px'; pop.style.top = (Math.max(8, y) + scrollY) + 'px';
  }
  function hide() { if (pop) pop.hidden = true; if (cur) cur.removeAttribute('aria-describedby'); cur = null; }
  function later() { clearTimeout(hideT); hideT = setTimeout(hide, 160); }
  const termOf = e => e.target.closest && e.target.closest('.term');
  document.addEventListener('pointerover', e => { if (e.pointerType !== 'mouse') return; const t = termOf(e); if (t) show(t); });
  document.addEventListener('pointerout', e => { if (e.pointerType === 'mouse' && termOf(e)) later(); });
  document.addEventListener('focusin', e => { const t = termOf(e); if (t) show(t); });
  document.addEventListener('focusout', e => { if (termOf(e)) later(); });
  document.addEventListener('click', e => {
    const t = termOf(e);
    if (t) { e.preventDefault(); e.stopPropagation(); if (cur === t && pop && !pop.hidden && Date.now() - shownAt > 500) hide(); else show(t); }
    else if (!(e.target.closest && e.target.closest('.term-pop'))) hide();
  }, true);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hide();
    const t = termOf(e); if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); show(t); }
  });
  addEventListener('scroll', () => { if (cur) show(cur); }, {passive: true});
  const prep = () => document.querySelectorAll('.term:not([tabindex])').forEach(t => { t.tabIndex = 0; t.setAttribute('role', 'button'); });
  prep(); new MutationObserver(prep).observe(document.body, {childList: true, subtree: true});
})();
"""


def term(tid, text):
    return f'<span class="term" data-term="{tid}">{text}</span>'


def glossary_page():
    from glossary import GROUPS, TERMS
    jump = ''.join(f'<a href="#g-{g}">{label}</a>' for g, label in GROUPS)
    out = [f'''<div class="page prose glossary">
  <span class="eyebrow">Glossary</span>
  <h1>Plain-English guide</h1>
  <p class="lede">Government money comes with a lot of jargon. Here is every term on this site, explained simply first, with more detail after. Anywhere on the site, a word with a dotted underline can be tapped for its short explanation.</p>
  <nav class="g-jump" aria-label="Glossary sections">{jump}</nav>''']
    for g, label in GROUPS:
        out.append(f'<section class="g-group" id="g-{g}"><h2>{label}</h2>')
        for t in [t for t in TERMS if t['group'] == g]:
            out.append(f'<article class="g-term" id="{t["id"]}"><h3>{t["term"]}</h3><p class="g-simple">{t["simple"]}</p>'
                       + (f'<p class="g-more">{t["more"]}</p>' if t['more'] else '')
                       + (f'<p class="g-ex"><b>Example:</b> {t["example"]}</p>' if t['example'] else '')
                       + '</article>')
        out.append('</section>')
    out.append('</div>')
    return '\n'.join(out)


CRA_EXPLAINER = f'''
  <section class="explain" aria-labelledby="whatcra">
    <div class="ex-txt">
      <span class="eyebrow">The simple version</span>
      <h2 id="whatcra">What's a CRA?</h2>
      <p>A {term('cra', 'Community Redevelopment Agency')} is like a savings jar for one neighborhood that needs fixing up.</p>
      <ol class="ex-steps">
        <li><b>Take a snapshot.</b> When the CRA starts, the city writes down what all the property inside its {term('cra-district', 'district')} is worth. That's the {term('base-year', 'base year')}.</li>
        <li><b>Watch it grow.</b> As buildings get fixed up and new ones go up, the area becomes worth more.</li>
        <li><b>The growth fills the jar.</b> Property tax on that extra value, the {term('tif', 'tax increment')}, goes into the CRA's {term('trust-fund', 'trust fund')} instead of the city's and county's main budgets. It can only be spent on that neighborhood, until the CRA's {term('sunset', 'end date')}.</li>
      </ol>
      <p class="muted">Why it matters: every dollar in the jar is a dollar the city and county don't have for everything else. This page shows what each jar paid for.</p>
    </div>
    <svg class="ex-fig" viewBox="0 0 320 230" role="img" aria-label="Three bars for year 1, year 5 and year 10. The base value stays the same; the growth above it, which goes to the CRA, gets taller each time.">
      <line x1="20" x2="300" y1="170" y2="170" stroke="var(--line)" stroke-width="1"/>
      <line x1="20" x2="300" y1="110" y2="110" stroke="var(--faint)" stroke-width="1" stroke-dasharray="4 4"/>
      <rect x="40" y="110" width="60" height="60" rx="3" fill="var(--faint)" fill-opacity=".45"/>
      <rect x="130" y="110" width="60" height="60" rx="3" fill="var(--faint)" fill-opacity=".45"/>
      <rect x="130" y="80" width="60" height="30" rx="3" fill="var(--blue)"/>
      <rect x="220" y="110" width="60" height="60" rx="3" fill="var(--faint)" fill-opacity=".45"/>
      <rect x="220" y="35" width="60" height="75" rx="3" fill="var(--blue)"/>
      <text x="70" y="188" text-anchor="middle" font-size="11" fill="var(--muted)">Year 1</text>
      <text x="160" y="188" text-anchor="middle" font-size="11" fill="var(--muted)">Year 5</text>
      <text x="250" y="188" text-anchor="middle" font-size="11" fill="var(--muted)">Year 10</text>
      <rect x="20" y="204" width="10" height="10" rx="2" fill="var(--faint)" fill-opacity=".45"/>
      <text x="36" y="213" font-size="10.5" fill="var(--muted)">Base value: taxes go to city and county</text>
      <rect x="20" y="219" width="10" height="10" rx="2" fill="var(--blue)"/>
      <text x="36" y="228" font-size="10.5" fill="var(--muted)">Growth: taxes go to the CRA</text>
    </svg>
  </section>'''


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
<link rel="alternate" type="application/rss+xml" title="BayCounty.me updates" href="/updates.xml">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{nav_html(path)}
<main id="main">
{body}
</main>
{FOOTER.replace('__UPDATED__', ('Page updated ' + nice_date(last_updated(path)) + ' · ') if path not in ('/404',) else '')}
<script src="/assets/site.js" defer></script>
<script src="/assets/report.js" defer></script>
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
    t = t.replace('<div class="stamp">Data updated Oct 20, 2026<br>Six CRAs · 14 districts</div>',
                  '<div class="stamp"><button type="button" id="pdf" class="pdf-btn"><svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0l-3-3m3 3l3-3M3 12v2h10v-2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Export PDF</button><span>Data updated Oct 20, 2026<br>Six CRAs · 14 districts</span></div>')
    t = t.replace('</header>\n\n  <div class="kpis" id="kpis"></div>', '</header>\n  <p class="print-meta" id="printMeta"></p>\n\n  <div class="kpis" id="kpis"></div>', 1)
    t = t.replace('</style>', PRINT_CSS + '</style>', 1)
    t = t.replace('<p class="print-meta" id="printMeta"></p>', '<p class="print-meta" id="printMeta"></p>' + CRA_EXPLAINER, 1)
    t = t.replace('<p class="lede">Every Community Redevelopment Agency in Bay County', '<p class="lede">Every ' + term('cra', 'Community Redevelopment Agency') + ' in Bay County', 1)
    t = t.replace('>Tax increment revenue by fiscal year, each on its own scale.', '>' + term('tif', 'Tax increment') + ' revenue by ' + term('fiscal-year', 'fiscal year') + ', each on its own scale.', 1)
    t = t.replace('<b>Spent</b> means the record reports money paid. <b>Committed</b> means an awarded contract or multi-year award not yet fully paid. <b>Budgeted</b> and <b>Proposed</b> are plans, not payments.',
                  '<b>' + term('spent', 'Spent') + '</b> means the record reports money paid. <b>' + term('committed', 'Committed') + '</b> means an awarded contract or multi-year award not yet fully paid. <b>' + term('budgeted', 'Budgeted') + '</b> and <b>' + term('proposed', 'Proposed') + '</b> are plans, not payments.', 1)
    t = t.replace('(a change order inside', '(a ' + term('change-order', 'change order') + ' inside', 1)
    t = t.replace('it stays in the ledger struck through and is left out of every total', 'it stays in the ledger struck through and is ' + term('left-out', 'left out of every total'), 1)
    t = t.replace('Vendor-level check registers are not published', 'Vendor-level ' + term('check-register', 'check registers') + ' are not published', 1)
    t = t.replace('a public records request to each city', 'a ' + term('public-records', 'public records request') + ' to each city', 1)
    t = t.replace('<div class="hd"><h2>Ledger</h2><span class="muted" id="ledgerCount" style="font-size:.82rem"></span></div>',
                  '<div class="hd"><h2>Ledger</h2><span class="muted" style="font-size:.82rem"><span id="ledgerCount"></span> · <button type="button" id="csv" class="reset" style="padding:0">Download CSV</button></span></div>')
    # split script out; it loads its data from /data/*.json
    js = re.search(r'<script>(.*)</script>', t, re.S).group(1)
    t = t[:t.index('<script>')] + '<script src="/assets/cra.js" defer></script>\n'
    js = js.replace('const D = __DATA__;', '')
    js = js.replace("['FY2025 tax increment', fmt(tif,true)", "['FY2025 <span class=\\\"term\\\" data-term=\\\"tif\\\">tax increment</span>', fmt(tif,true)", 1)
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
window.BCReportBefore = beforePrint;
window.BCReportAfter = afterPrint;
window.BCReportMeta = () => 'Report: ' + filterSummary();
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


from home import home_page  # noqa: E402

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
  <h2 id="contact">Corrections, records and questions</h2>
  <p>Found an error, or have a public record that fills a gap? Send it here. Corrections are dated on the page they affect and listed under <a href="/updates">What's new</a>.</p>
  <form class="contact" id="contactForm" novalidate>
    <div class="cf-row">
      <label class="cf-f"><span>What's this about?</span>
        <select name="topic"><option value="correction">A correction</option><option value="record">A record or tip</option><option value="question">A question</option><option value="other">Something else</option></select></label>
      <label class="cf-f"><span>Page <em>(optional)</em></span><input name="page" type="text" inputmode="url" placeholder="e.g. /who-runs-bay-county" autocomplete="off"></label>
    </div>
    <label class="cf-f"><span>Message</span><textarea name="message" rows="6" required minlength="10" maxlength="5000" placeholder="What's wrong or missing, and where did you see the correct information? A link to the record helps most."></textarea></label>
    <div class="cf-row">
      <label class="cf-f"><span>Name <em>(optional)</em></span><input name="name" type="text" autocomplete="name" maxlength="120"></label>
      <label class="cf-f"><span>Email <em>(only if you want a reply)</em></span><input name="email" type="email" autocomplete="email" maxlength="200"></label>
    </div>
    <label class="cf-hp" aria-hidden="true">Website <input name="website" type="text" tabindex="-1" autocomplete="off"></label>
    <div class="cf-go"><button type="submit">Send message</button><p class="cf-msg" id="cfMsg" role="status" aria-live="polite"></p></div>
    <p class="cf-note">Messages go to the BayCounty.me team at Flux Labs. Your email address is used only to reply and is never published. To send a document, include a link, or email <span class="sel">hello@fluxlabs.net</span>.</p>
  </form>
  <script>
  (() => {
    const f = document.getElementById('contactForm'), msg = document.getElementById('cfMsg'), btn = f.querySelector('button');
    const t0 = Date.now(), q = new URLSearchParams(location.search);
    let ref = q.get('page') || '';
    try { const r = new URL(document.referrer); if (!ref && r.origin === location.origin && r.pathname !== location.pathname) ref = r.pathname; } catch (e) {}
    if (ref) { f.page.value = ref; f.topic.value = 'correction'; }
    if (q.get('topic') && f.topic.querySelector(`option[value="${q.get('topic')}"]`)) f.topic.value = q.get('topic');
    f.addEventListener('input', () => { if (msg.classList.contains('err')) { msg.textContent = ''; msg.className = 'cf-msg'; } });
    f.addEventListener('submit', async ev => {
      ev.preventDefault();
      const d = Object.fromEntries(new FormData(f)); d.t = t0;
      if ((d.message || '').trim().length < 10) { msg.className = 'cf-msg err'; msg.textContent = 'Please write a little more in your message.'; f.message.focus(); return; }
      if (d.email && !f.email.checkValidity()) { msg.className = 'cf-msg err'; msg.textContent = 'That email address doesn\u2019t look right.'; f.email.focus(); return; }
      btn.disabled = true; btn.textContent = 'Sending\u2026'; msg.className = 'cf-msg'; msg.textContent = '';
      try {
        const r = await fetch('/api/contact', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(d)});
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.ok) throw new Error(j.error || 'Your message couldn\u2019t be sent. Please try again or email hello@fluxlabs.net.');
        f.reset(); f.classList.add('sent'); msg.className = 'cf-msg ok'; msg.textContent = 'Thanks, your message was sent.' + (d.email ? ' We\u2019ll reply by email if needed.' : '');
      } catch (e) { msg.className = 'cf-msg err'; msg.textContent = e.message; }
      btn.disabled = false; btn.textContent = 'Send message';
    });
  })();
  </script>
  <h2>Who runs it</h2>
  <p>BayCounty.me is built and hosted by <a href="https://fluxlabs.net/" target="_blank" rel="noopener">Flux Labs</a>, a managed IT services company in Panama City.</p>
</div>'''


PAGES = [
    ('/', 'Bay County public records, mapped', 'Maps, money and public records for Bay County, Florida, with a source on every figure.', home_page),
    ('/my-address', 'My Address', 'Look up any Bay County address: property tax estimate, who represents you, zoned schools, flood and evacuation zones, and whether it is in a redevelopment district.', lambda: addr_page(OUT)),
    ('/public-money/cra-spending', 'CRA Spending',
     'Interactive map and ledger of Bay County, Florida\'s six Community Redevelopment Agencies: who was paid, where, and for what.', cra_page),
    ('/public-money/tax-dollars', 'How your tax dollars are allocated',
     'Estimate your Bay County property tax bill and see who gets each slice, plus where the county, schools and every city get their money and what they spend it on.', lambda: tax_page(OUT)),
    ('/public-money/amendment-3', 'Amendment 3: what changes in Bay County',
     'What Florida\'s 2026 Amendment 3 would do to Bay County property tax bills and local budgets, using the state\'s own estimates. Before-and-after calculator; both sides\' arguments; no position taken.', lambda: amend_page(OUT)),
    ('/public-money/hurricane-michael', 'Where the Hurricane Michael money went', 'FEMA, HUD and state recovery money in Bay County after Hurricane Michael: every FEMA project, household aid by city, Rebuild Florida awards, debris costs and the Lynn Haven case.', lambda: michael_page(OUT)),
    ('/public-money/tourist-tax', 'The bed tax: what visitors pay and where it goes', "Bay County's 5% tourist development tax: ten years of collections by zone, how the pennies are split, what Visit Panama City Beach spends, and who decides.", lambda: bedtax_page(OUT)),
    ('/public-money/sales-tax-projects', 'Half-cent sales taxes: promised vs built', "Every infrastructure sales tax project on Bay County's map with its status, the county's surtax money by year, and the school half-cent.", lambda: surtax_page(OUT)),
    ('/public-money/fees-and-bills', 'Fees on your tax bill, and utility bills', 'Fire, stormwater and other flat fees on Bay County tax bills, and a typical monthly water, sewer and garbage bill in each city.', fees_page),
    ('/who-runs-bay-county', 'Who runs Bay County', 'Every elected seat and appointed manager for Bay County, its cities and the school district, plus what top officials are paid.', who_page),
    ('/public-money/contracts', 'Who gets the contracts', 'Major contracts approved by Bay County and its cities since 2022: winners, how they were awarded, change orders, emergency purchases and who the county paid most.', lambda: contracts_page(OUT)),
    ('/public-money/votes', 'How they voted', 'How Bay County commissioners, city officials and school board members voted on budgets, tax rates, contracts, land and borrowing, from official minutes.', lambda: votes_page(OUT)),
    ('/public-money/debt', 'What Bay County governments owe', 'Debt owed by Bay County, the school district and every city: bonds, bank loans, big single payments ahead, and pension promises, from audited statements.', debt_page),
    ('/public-money/audits', 'What the auditors found', 'Three years of audit findings for Bay County governments in plain English, including repeat problems and Florida Auditor General reports.', audits_page),
    ('/glossary', 'Plain-English guide', 'Every term on BayCounty.me explained simply: CRAs, tax increment, millage, homestead exemptions, budgets and more.', glossary_page),
    ('/updates', 'Updates', 'New pages, new data and corrections on BayCounty.me, newest first, with an RSS feed.', updates_page),
    ('/search', 'Search', 'Search every page, glossary term and public-money record on BayCounty.me.', search_page),
    ('/about', 'About', 'What BayCounty.me is, where its information comes from, and how to send a correction.', about_page),
]


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'assets'))
    os.makedirs(os.path.join(OUT, 'data'))
    open(os.path.join(OUT, 'assets', 'site.css'), 'w').write(TOKENS + '\n' + SITE_CSS)
    from glossary import TERMS
    gl = {t['id']: {'term': t['term'], 'simple': t['simple']} for t in TERMS}
    open(os.path.join(OUT, 'assets', 'site.js'), 'w').write(MENU_JS + TERM_JS.replace('__GLOSSARY__', json.dumps(gl, ensure_ascii=False)))
    shutil.copy(os.path.join(ROOT, '..', 'assets', 'logo_small.webp'), os.path.join(OUT, 'assets', 'flux-labs.webp'))
    shutil.copy(os.path.join(ROOT, 'favicon.svg'), os.path.join(OUT, 'favicon.svg'))
    shutil.copy(os.path.join(ROOT, 'tax.css'), os.path.join(OUT, 'assets', 'tax.css'))
    shutil.copy(os.path.join(ROOT, 'report.js'), os.path.join(OUT, 'assets', 'report.js'))
    for path, title, desc, fn in PAGES:
        write(path, layout(title, desc, path, fn()))
    print('search index:', build_index(OUT, PAGES), 'entries')
    open(os.path.join(OUT, 'updates.xml'), 'w').write(rss(DOMAIN))
    open(os.path.join(OUT, '404.html'), 'w').write(layout('Page not found', 'Page not found', '/404',
        '<div class="page prose"><h1>That page isn\'t here.</h1><p><a href="/">Back to the home page</a></p></div>'))
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(dp, f); print(os.path.relpath(p, OUT), os.path.getsize(p))


if __name__ == '__main__':
    main()
