"""Static site generator for baycounty.me.

Pages share one layout: head, top menu (with sub-menus), and a 'Powered by Flux Labs' footer.
Add a new page by adding it to site/site_menu.py (for the menu) and to PAGES (for the file).
"""
import json, os, re, shutil, base64, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from tax_page import tax_page
from amend_page import amend_page
from addr_page import addr_page
from michael_page import michael_page
from search_page import search_page, build_index
from ask_page import ask_page, ASK_ICON
from tourism_page import bedtax_page, surtax_page
from fees_page import fees_page
from contracts_page import contracts_page
from votes_page import votes_page
from accountability_page import accountability_page
from correspondence_page import correspondence_page
from shared_owners_page import shared_owners_page
from nonprofits_page import nonprofits_page
from chambers_page import chambers_page
from volunteer_page import volunteer_page
from business_ties_page import business_ties_page
from updates import updates_page, rss, last_updated, nice as nice_date
OUT = os.path.join(ROOT, 'public')
from place import SITE, DOMAIN, LABEL as PLACE_LABEL, EMAIL, OPERATOR, OFFICIALS, wordmark_html, governments as _place_govs
PREVIEW = {}  # path -> (title, summary) for link previews, filled from og.preview_text()
from es_pages import ES_ALT, updated_key as es_updated_key  # Spanish page -> English twin (hreflang, language switch)
EN_TO_ES = {v: k for k, v in ES_ALT.items()}
OG_VER = {}  # path -> image content hash, filled by og.build_og before pages are written

# Menu: six question-named sections (site/site_menu.py, also published as the site-menu dataset).
from site_menu import menu, links as menu_links, ELECTIONS_READY
MENU = menu()

TOKENS = open(os.path.join(ROOT, 'tokens.css')).read()
SITE_CSS = open(os.path.join(ROOT, 'site.css')).read() + '\n' + open(os.path.join(ROOT, 'ui.css')).read()  # ui.css: shared page pieces


def hreflang(path):
    en = ES_ALT.get(path) if path.startswith('/es') else (path if path in EN_TO_ES else None)
    if not en:
        return ''
    es = EN_TO_ES[en]
    return (f'\n<link rel="alternate" hreflang="en" href="{DOMAIN}{en}">\n<link rel="alternate" hreflang="es" href="{DOMAIN}{es}">'
            f'\n<link rel="alternate" hreflang="x-default" href="{DOMAIN}{en}">')


def alternates(path):
    en = ES_ALT.get(path) if path.startswith('/es') else (path if path in EN_TO_ES else None)
    return [('en', en), ('es', EN_TO_ES[en]), ('x-default', en)] if en else []


CHEV = '<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'
SEARCH_ICON = '<svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><circle cx="9" cy="9" r="5.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M13.2 13.2L17 17" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>'


def _link(c, active):
    cur = ' aria-current="page"' if c['href'] == active else ''
    kd = f'<span class="kd">{c["desc"]}</span>' if c.get('desc') else ''
    return f'<li><a href="{c["href"]}"{cur}><span class="k">{c["label"]}</span>{kd}</a></li>'


def _section(m, active):
    """One drop-down. A section with a start page gets the compact layout: its links in two columns and the start page
    as a card (first in the phone menu). The Spanish menu's sections keep the column-per-group layout."""
    on = any(c['href'] == active for c in menu_links(m))
    q = f'<span class="st-q">{m["question"]}</span>' if m.get('question') else ''
    btn = f'<button type="button" class="sub-toggle" aria-expanded="false"><span class="st-l">{m["label"]}{q}</span>{CHEV}</button>'
    if m.get('start'):
        st = m['start']
        cur = ' aria-current="page"' if st['href'] == active else ''
        card = (f'<a class="nav-start" href="{st["href"]}"{cur}><span class="ns-e">Start here</span><span class="ns-t">{st["label"]}</span>'
                f'<span class="ns-d">{st["desc"]}</span><span class="ns-go" aria-hidden="true">Open →</span></a>')
        cols = ''.join(f'<div class="nav-col"><span class="nav-gh">{g["group"]}</span><ul class="nav-links">'
                       + ''.join(_link(c, active) for c in g['items']) + '</ul></div>' for g in m['groups'])
        sub = f'<div class="nav-sub nav-mega has-start">{card}{cols}</div>'
    else:
        sub = '<ul class="nav-sub nav-mega">' + ''.join(
            f'<li class="nav-grp"><span class="nav-gh">{g["group"]}</span><ul>' + ''.join(_link(c, active) for c in g['items']) + '</ul></li>'
            for g in m['groups']) + '</ul>'
    return f'<li class="has-sub{" on" if on else ""}">{btn}{sub}</li>'


def search_dialog():
    """The full-screen search dialog the header's search icon opens (site/search.js). Before typing it lists each
    section's start page."""
    pop = ''.join(f'<li><a href="{m["start"]["href"]}"><b>{m["start"]["label"]}</b><span>{m["label"]} · {m["start"]["desc"]}</span></a></li>'
                  for m in MENU if m.get('start'))
    return f'''<div class="sx" id="sx" role="dialog" aria-modal="true" aria-label="Search {SITE}" hidden>
  <div class="sx-top"><span class="wordmark" aria-hidden="true"><span>{wordmark_html()}</span></span>
    <button type="button" class="sx-x" aria-label="Close search"><kbd>Esc</kbd><svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button></div>
  <div class="sx-body">
    <label class="sx-box">{SEARCH_ICON}<input id="sxq" type="search" autocomplete="off" enterkeyhint="search" aria-label="Search" placeholder="Search BayCounty.me"></label>
    <p class="sx-n" id="sxn" aria-live="polite"></p>
    <div class="sx-res" id="sxr"></div>
    <section class="sx-g sx-e" id="sxe"><h2>Start here</h2><ul>{pop}</ul></section>
    <p class="sx-keys"><span><kbd>↑</kbd> <kbd>↓</kbd> to move</span><span><kbd>Enter</kbd> to open</span><span><kbd>/</kbd> or <kbd>Ctrl K</kbd> opens search on any page</span></p>
  </div>
</div>'''


def nav_html(active):
    es = active.startswith('/es')
    items = []
    for m in (ES_MENU if es else MENU):
        if 'groups' in m:
            items.append(_section(m, active))
        else:
            cur = ' aria-current="page"' if m['href'] == active else ''
            items.append(f'<li><a href="{m["href"]}"{cur}>{m["label"]}</a></li>')
    # The Spanish pages keep a way back to English; the English pages have no language link for now (Jeremy, 2026-10-24).
    cur = ' aria-current="page"' if active == '/ask' else ''
    ask = '' if es else f'<a class="ask-btn" href="/ask"{cur}>{ASK_ICON}<span>Ask</span></a>'
    lang = '<a class="lang-link" href="__LANGHREF__" lang="__LANGCODE__" hreflang="__LANGCODE__">__LANGLABEL__</a>' if es else ''
    return f'''<header class="site-head"><div class="site-head-in">
  <a class="wordmark" href="{'/es' if es else '/'}" aria-label="{SITE} {'inicio' if es else 'home'}"><span>{wordmark_html()}</span></a>
  <nav aria-label="Main"><ul id="site-menu" class="menu">{"".join(items)}</ul></nav>
  {lang}
  {ask}
  <a class="search-btn" href="/search" aria-label="Search" aria-keyshortcuts="/ Control+K">{SEARCH_ICON}</a>
  <button type="button" class="theme-btn" id="themeBtn" aria-label="Theme: match system"><svg class="ti ti-system" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 3.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg><svg class="ti ti-light" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="3.6" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 2v2.2M10 15.8V18M2 10h2.2M15.8 10H18M4.3 4.3l1.6 1.6M14.1 14.1l1.6 1.6M4.3 15.7l1.6-1.6M14.1 5.9l1.6-1.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg><svg class="ti ti-dark" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M16 12.6A6.6 6.6 0 0 1 7.4 4a6.6 6.6 0 1 0 8.6 8.6z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg><span class="theme-lbl">System</span></button>
  <button type="button" class="menu-btn" aria-expanded="false" aria-controls="site-menu"><span class="sr">Menu</span><svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path d="M3 6h14M3 10h14M3 14h14" stroke="currentColor" stroke-width="1.8"/></svg></button>
</div></header>
{search_dialog()}'''


FOOTER = f'''<footer class="site-foot"><div class="site-foot-in">
  <div class="foot-brand"><a class="wordmark" href="/"><span>{wordmark_html()}</span></a>
  <p>Public records for {PLACE_LABEL}, in plain view: what governments collect, what they spend, what they owe and what the auditors found.</p></div>
  <nav class="foot-cols" aria-label="Footer">
    <div><b>Follow the money</b><a href="/public-money/tax-dollars">Tax dollars</a><a href="/governments">Governments</a><a href="/compare">Compare governments</a><a href="/public-money/contracts">Contracts</a></div>
    <div><b>Accountability</b><a href="/public-money/accountability">Accountability console</a><a href="/public-money/votes">How they voted</a><a href="/connections">Connections</a></div>
    <div><b>Take part</b><a href="/meetings">Meetings</a><a href="/alerts">Email alerts</a><a href="/records-request">Request a record</a><a href="/open-data">Open data &amp; API</a></div>
  </nav>
  <div class="foot-base">
    <p class="muted foot-links">__UPDATED__<a href="/updates">What's new</a> · <a href="/updates.xml">RSS</a> · <a href="/data-sources">Where our data comes from</a> · <a href="/about">About</a> · <a href="/privacy">Privacy</a> · <a href="/about#contact">Send a correction</a> · <span class="sel">{EMAIL}</span></p>
    <a class="powered" href="{OPERATOR['url']}" target="_blank" rel="noopener"><span>Powered by</span><img src="{OPERATOR['logo']}" alt="{OPERATOR['name']}" width="140" height="25"></a>
  </div>
</div></footer>'''

MENU_JS = '''(() => {
  const root = document.documentElement, tb = document.getElementById('themeBtn');
  const I = window.BCM_I18N || {}, NAMES = I.theme || {system: 'System', light: 'Light', dark: 'Dark'}, NEXT = {system: 'light', light: 'dark', dark: 'system'};
  const current = () => root.getAttribute('data-theme') || 'system';
  const show = m => { tb.dataset.mode = m; tb.querySelector('.theme-lbl').textContent = NAMES[m]; tb.setAttribute('aria-label', (I.themeLabel || 'Theme: ') + (m === 'system' ? I.themeSystem || 'match system' : NAMES[m].toLowerCase()) + (I.themeClick || '. Click to change.')); };
  show(current());
  tb.addEventListener('click', () => {
    const m = NEXT[current()];
    if (m === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', m);
    try { if (m === 'system') localStorage.removeItem('theme'); else localStorage.setItem('theme', m); } catch (e) {}
    show(m);
  });
  const btn = document.querySelector('.menu-btn'), menu = document.getElementById('site-menu');
  const setMenu = o => { btn.setAttribute('aria-expanded', o); menu.classList.toggle('open', o); document.documentElement.classList.toggle('nav-locked', o); if (o) menu.scrollTop = 0;
    // phone menu: open on the section that holds this page
    const here = o && menu.querySelector('.has-sub.on > .sub-toggle'); if (here && !menu.querySelector('.sub-toggle[aria-expanded="true"]')) here.setAttribute('aria-expanded', 'true'); };
  btn.addEventListener('click', () => setMenu(btn.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', e => { if (e.target.closest('a')) setMenu(false); });
  const mq = matchMedia('(min-width:981px)'), onMq = e => { if (e.matches) setMenu(false); };
  if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq);
  document.querySelectorAll('.sub-toggle').forEach(t => t.addEventListener('click', e => {
    e.stopPropagation(); const o = t.getAttribute('aria-expanded') === 'true';
    document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false'));
    t.setAttribute('aria-expanded', !o); }));
  // Line each mega menu up under its own button, nudged left only if it would run off the right edge.
  const placeMega = li => { const m = li.querySelector('.nav-mega'); if (!m || innerWidth <= 980) return;
    const l = li.getBoundingClientRect().left, w = Math.min(760, innerWidth - 32);
    m.style.setProperty('--mx', Math.max(16 - l, Math.min(0, innerWidth - 16 - w - l)) + 'px'); };
  document.querySelectorAll('.has-sub').forEach(li => ['mouseenter', 'focusin', 'click'].forEach(ev => li.addEventListener(ev, () => placeMega(li))));
  document.addEventListener('click', e => { if (!e.target.closest('.has-sub, .menu-btn')) document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.querySelectorAll('.sub-toggle').forEach(x => x.setAttribute('aria-expanded', 'false')); if (menu.classList.contains('open')) { setMenu(false); btn.focus(); } } });
})();
'''


# Shared helpers (window.BCM): URL state for data-param controls (?gov= etc.) and announce. Tables use tables.js.
DEEPLINK_JS = open(os.path.join(ROOT, 'site_helpers.js')).read() + open(os.path.join(ROOT, 'ui.js')).read()
# name casing shared with the API (api/_names.js): window.BCNames and BC.bizCase / BC.personCase / BC.nameCase
NAMES_JS = open(os.path.join(ROOT, '..', 'api', '_names.js')).read() + '\nwindow.BC = Object.assign(window.BC || {}, window.BCNames);\n'
SEARCH_JS = open(os.path.join(ROOT, 'search.js')).read()  # header search dialog + the engine the /search page uses


TERM_JS = r"""
(() => {
  const ES = document.documentElement.lang === 'es', G = ES ? __GLOSSARY_ES__ : __GLOSSARY__;
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
    const a = pop.querySelector('a'); a.href = (ES ? '/es/glosario#' : '/glossary#') + el.dataset.term; a.textContent = ES ? 'M\u00e1s en el glosario \u2192' : 'More in the glossary \u2192';
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
    from ui import enhance
    out = _layout(title, desc, path, enhance(body, path), extra_head)
    return localize_chrome(out) if path.startswith('/es') else out


def _layout(title, desc, path, body, extra_head=''):
    import html as _h
    from og import slug as _slug
    from seo import head_title, meta_desc, jsonld
    from ui import data_notice
    full = _h.escape(head_title(title, path), quote=False)
    pt, pd = PREVIEW.get(path, (title, desc))
    t, d = _h.escape(pt, quote=True), _h.escape(pd, quote=True)
    md = _h.escape(meta_desc(pd), quote=True)
    es = path.startswith('/es')
    ver = OG_VER.get(path, '')
    img = f'{DOMAIN}/og/{_slug(path) if path in OG_VER else "home"}.png' + (f'?v={ver}' if ver else '')
    robots = '<meta name="robots" content="noindex, follow">\n' if path in ('/404', '/profile') else '<meta name="robots" content="index, follow, max-image-preview:large">\n'
    ld = '' if path == '/404' else jsonld(path, pt, pd, PAGE_LABELS, modified=last_updated(es_updated_key(path)), out_dir=OUT,
                                           kind=page_kind(path), about=page_about(path))
    return f'''<!doctype html>
<html lang="{'es-US' if es else 'en-US'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{full}</title>
<meta name="description" content="{md}">
{robots}<link rel="canonical" href="{DOMAIN}{path}">{hreflang(path)}
<meta property="og:site_name" content="{SITE}">
<meta property="og:locale" content="{'es_US' if es else 'en_US'}">
<meta property="og:locale:alternate" content="{'en_US' if es else 'es_US'}">
<meta property="og:type" content="website">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{DOMAIN}{path}">
<meta property="og:image" content="{img}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{t}: {SITE}, public records for {PLACE_LABEL}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{img}">
<meta name="twitter:image:alt" content="{t}: {SITE}, public records for {PLACE_LABEL}">
{ld}<meta name="theme-color" content="#1E3A76" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#0E131B" media="(prefers-color-scheme: dark)">
<script>try{{var t=localStorage.getItem('theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}}catch(e){{}}</script>
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/assets/site.css">
<link rel="alternate" type="application/rss+xml" title="{SITE} updates" href="/updates.xml">
<script>window.va=window.va||function(){{(window.vaq=window.vaq||[]).push(arguments)}};window.si=window.si||function(){{(window.siq=window.siq||[]).push(arguments)}};</script>
<script defer src="/_vercel/insights/script.js"></script>
<script defer src="/_vercel/speed-insights/script.js"></script>
<script src="/assets/tables.js" defer></script>
<script src="/assets/site.js" defer></script>
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{nav_html(path).replace('__LANGHREF__', ES_ALT.get(path, '/') if path.startswith('/es') else (EN_TO_ES.get(path) or '/es')).replace('__LANGCODE__', 'en' if path.startswith('/es') else 'es').replace('__LANGLABEL__', 'English' if path.startswith('/es') else 'Español')}
{data_notice(path.startswith('/es')) if path != '/404' else ''}
<main id="main">
{body}
</main>
{FOOTER.replace('__UPDATED__', ('Page updated ' + nice_date(last_updated(es_updated_key(path))) + ' · ') if path not in ('/404',) else '')}
<script src="/assets/report.js" defer></script>
</body>
</html>
'''


def write(path, html):
    # keep each page's 'Data updated' stamp in step with its latest What's new entry
    html = re.sub(r'Data updated [A-Z][a-z]{2} \d{1,2}, \d{4}', 'Data updated ' + nice_date(last_updated(path)), html)
    html = linkify_html(html)
    html = link_names(html, path)  # official, company and nonprofit names -> their profiles (site/entity_links.py)
    html = us_dates_html(html, es=path.startswith('/es'))  # 2025-02-10 -> Feb 10, 2025 in page text (site/dates.py)
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
    from city_filter import city_bar as _city_bar, CRA_CODE as _CRA_CODE
    t = t.replace('</header>\n\n  <div class="kpis" id="kpis"></div>', '</header>\n' + _city_bar(list(_CRA_CODE), legacy='cra cras', label='City', all_label='All six CRAs') + '\n  <p class="print-meta" id="printMeta"></p>\n\n  <div class="kpis" id="kpis"></div>', 1)
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
  const rows = (S.lastSorted || filtered()).map(p => [CRA[p.cra].name, p.district, p.amount, p.payee, p.purpose, p.cat, p.when, p.status, p.count ? 'Yes' : 'No', p.overlap, p.loc || p.addr, p.conf, p.url, p.notes].map(q).join(','));
  const blob = new Blob(['\ufeff' + cols.join(',') + '\n' + rows.join('\n')], {type: 'text/csv;charset=utf-8'});
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


from home import home_page
from gov_pages import gov_page, govs_index
from compare_page import compare_page
from opendata import opendata_page
from records_page import records_page
from alerts_page import alerts_page
from meetings_page import meetings_page
from campaign_page import campaign_page
from budget_compare_page import budget_compare_page
from cra_increment_page import cra_increment_page
import open_books_page
from open_books_page import checkbook_page, budget_tracker_page
from linkify import linkify_html, LINKIFY_JS
from dates import us_dates_html, DATES_JS  # noqa: E402
from developers_page import developers_page
from elections_page import elections_page
from past_elections_page import past_elections_page
from exemptions_page import exemptions_page
from es_pages import ES_MENU, localize_chrome, es_home, es_addr_page, es_glossary_page, es_records_page, glossary_es_terms, write_report_es, es_tax_page, es_fees_page, es_exemptions_page, es_elections_page, es_meetings_page, prune as prune_es
from govs import GOVS as GOVLIST  # noqa: E402

def page_options():
    import html
    def o(h, l): return f'<option value="{h}">{html.escape(l)}</option>'
    out = '<option value="">Not about a specific page</option><optgroup label="Main pages">' + o('/', 'Home') + o('/search', 'Search') + '</optgroup>'
    for m in MENU:
        out += f'<optgroup label="{html.escape(m["label"])}">' + ''.join(o(i['href'], i['label']) for i in menu_links(m)) + '</optgroup>'
    return out


def data_sources_page():
    from data_sources_page import data_sources_page as page
    return page(OUT)


def about_page():
    return '''<div class="page prose">
  <span class="eyebrow">About</span>
  <h1>About BayCounty.me</h1>
  <p>BayCounty.me is an independent project that collects Bay County, Florida public records and turns them into maps and tables anyone can read. It starts with how local governments spend public money and will grow from there.</p>
  <h2>Where the information comes from</h2>
  <p>Everything on the site comes from documents the public can already request or download: city and county budgets, annual reports, audits filed with the Florida Auditor General, council and commission resolutions, Bay County GIS map layers, and reporting by local newsrooms. Each figure carries a link to its source. <a href="/data-sources">See every source we use</a>, with links and how we process each one.</p>
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
      <label class="cf-f"><span>Page <em>(optional)</em></span><select name="page">__PAGE_OPTS__</select></label>
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
    ref = ref.replace(/\\/+$/, '') || (ref ? '/' : '');
    if (ref) { if (![...f.page.options].some(x => x.value === ref)) f.page.add(new Option(ref, ref), 1); f.page.value = ref; f.topic.value = 'correction'; }
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
</div>'''.replace('__PAGE_OPTS__', page_options())


def privacy_page():
    return '''<div class="page prose">
  <h1>Privacy</h1>
  <p class="lede">BayCounty.me doesn't sell, share or track you. There are no accounts, no ads and no tracking cookies, on the website or in the iPhone and Android apps.</p>
  <h2>The website</h2>
  <ul>
    <li><b>Visits.</b> The site counts page views with Vercel Web Analytics, which uses no cookies and doesn't identify you.</li>
    <li><b>Email alerts.</b> If you sign up, we keep your email address and what you chose to follow, so we can send the emails. Every email has a link to change or stop them. To have your address deleted entirely, email us.</li>
    <li><b>Contact form.</b> Your message, name and email come to us by email so we can answer. They aren't added to any list.</li>
    <li><b>API.</b> Requests to the public API are logged with the caller's IP address for 90 days to stop abuse, then deleted.</li>
    <li><b>Ask.</b> Questions you type on the <a href="/ask">Ask</a> page are sent to an AI service to write the answer, along with the public records it looks up. BayCounty.me doesn't save your questions or the answers; it logs only how many were asked (with a scrambled form of your IP address, to enforce limits) and what they cost. Please don't type personal information.</li>
    <li><b>My Address.</b> Address lookups go straight from your browser to Bay County's and FEMA's public map servers. BayCounty.me doesn't receive or store what you look up.</li>
  </ul>
  <h2>The iPhone and Android apps</h2>
  <ul>
    <li><b>No data collected.</b> The app has no accounts, analytics or advertising, and sends nothing about you to BayCounty.me.</li>
    <li><b>Your address and location.</b> If you save a home address, it stays on your phone. If you tap "Use my location," the app asks permission first and uses your location once to find your address on Bay County's public map server. It isn't stored or sent anywhere else.</li>
    <li><b>Downloaded data.</b> The app saves copies of the public records it shows so it works offline. Deleting the app deletes them.</li>
    <li><b>Maps.</b> The Android app draws its maps with OpenStreetMap tiles, so OpenStreetMap's servers see your IP address when they send them, as any website would. The iPhone app uses Apple Maps.</li>
    <li><b>Crash reports.</b> If you've allowed it in your phone's settings, Apple or Google may share anonymous crash reports with the developer.</li>
  </ul>
  <h2>Questions</h2>
  <p>Email <a href="mailto:hello@fluxlabs.net">hello@fluxlabs.net</a> or use the <a href="/about#contact">contact form</a>. BayCounty.me is run by <a href="https://fluxlabs.net/" target="_blank" rel="noopener">Flux Labs</a> in Panama City, Florida.</p>
</div>'''


PAGES = [
    ('/', 'Bay County public records, mapped', 'Maps, money and public records for Bay County, Florida, with a source on every figure.', home_page),
    ('/my-address', 'My Address', 'Look up any Bay County address: property tax estimate, who represents you, zoned schools, flood and evacuation zones, and whether it is in a redevelopment district.', lambda: addr_page(OUT)),
    ('/public-money/cra-spending', 'CRA Spending',
     'Interactive map and ledger of Bay County, Florida\'s six Community Redevelopment Agencies: who was paid, where, and for what.', cra_page),
    ('/public-money/cra-tax-increment', 'How much property tax goes to the CRAs',
     "How much property tax Bay County and the cities pay to the seven Community Redevelopment Agencies each year, who pays it, what has been paid so far and what it could add up to before each CRA ends, with the method and the missing years.", lambda: cra_increment_page(OUT)),
    ('/public-money/tax-dollars', 'How your tax dollars are allocated',
     'Estimate your Bay County property tax bill and see who gets each slice, plus where the county, schools and every city get their money and what they spend it on.', lambda: tax_page(OUT, gov_panel=False)),
    ('/public-money/amendment-3', 'Amendment 3: what changes in Bay County',
     'What Florida\'s 2026 Amendment 3 would do to Bay County property tax bills and local budgets, using the state\'s own estimates. Before-and-after calculator; both sides\' arguments; no position taken.', lambda: amend_page(OUT)),
    ('/public-money/hurricane-michael', 'Where the Hurricane Michael money went', 'FEMA, HUD and state recovery money in Bay County after Hurricane Michael: every FEMA project, household aid by city, Rebuild Florida awards, debris costs and the Lynn Haven case.', lambda: michael_page(OUT)),
    ('/public-money/tourist-tax', 'The bed tax: what visitors pay and where it goes', "Bay County's 5% tourist development tax: ten years of collections by zone, how the pennies are split, what Visit Panama City Beach spends, and who decides.", lambda: bedtax_page(OUT)),
    ('/public-money/sales-tax-projects', 'Half-cent sales taxes: promised vs built', "Every infrastructure sales tax project on Bay County's map with its status, the county's surtax money by year, and the school half-cent.", lambda: surtax_page(OUT)),
    ('/public-money/fees-and-bills', 'Fees on your tax bill, and utility bills', 'Fire, stormwater and other flat fees on Bay County tax bills, and a typical monthly water, sewer and garbage bill in each city.', fees_page),
    ('/governments', "Bay County's local governments", 'A profile of every local government in Bay County, Florida: officials, budget, tax rate, debt, audits, votes, contracts and projects.', govs_index),
    ('/compare', 'Compare Bay County governments', 'Compare Bay County, its cities and the school district side by side: budget, property tax, debt, staff, audit findings, split votes and utility bills, per resident.', lambda: compare_page(OUT)),
    ('/open-data', 'Download the data', 'Every BayCounty.me dataset as CSV and JSON: votes, contracts, CRA spending, tax rates, debt, audits, FEMA projects and more.', lambda: opendata_page(OUT)),
    ('/developers', 'API for developers', 'Connect apps, spreadsheets and AI assistants to BayCounty.me: a free, read-only API and MCP server for Bay County public records.', lambda: developers_page(OUT)),
    ('/es', 'Registros públicos en español', 'BayCounty.me en español: estimado de impuestos por dirección, solicitudes de registros públicos y un glosario de términos de dinero público.', es_home),
    ('/es/mi-direccion', 'Mi dirección', 'Busque cualquier dirección del condado de Bay: estimado de impuestos a la propiedad, quién lo representa, escuelas, zonas de inundación y evacuación, y distritos de reurbanización.', lambda: es_addr_page(OUT)),
    ('/es/glosario', 'Glosario en lenguaje sencillo', 'Cada término de BayCounty.me explicado de forma sencilla: CRA, incremento de impuestos, millaje, exención de vivienda principal, presupuestos y más.', es_glossary_page),
    ('/es/solicitar-registros', 'Solicite un registro público', 'Escriba una solicitud de registros públicos de Florida a cualquier gobierno del condado de Bay en un minuto.', lambda: es_records_page(OUT)),
    ('/es/impuestos', 'A dónde va su impuesto a la propiedad', 'Calcule su factura del impuesto a la propiedad en el condado de Bay y vea qué parte recibe cada gobierno, de dónde saca el resto de su dinero y en qué lo gasta.', lambda: es_tax_page(OUT)),
    ('/es/tarifas-y-facturas', 'Tarifas en su factura de impuestos, y facturas de servicios', 'Las tarifas fijas de bomberos, aguas pluviales y otras en las facturas de impuestos del condado de Bay, y una factura típica de agua, alcantarillado y basura en cada ciudad.', es_fees_page),
    ('/es/exenciones', 'Exenciones del impuesto a la propiedad', 'Quién recibe una exención del impuesto a la propiedad en el condado de Bay, desde el homestead hasta los veteranos con discapacidad, cuántas casas y cuánto impuesto quita cada una, según el registro de 2026.', es_exemptions_page),
    *([('/es/elecciones', 'Quiénes son candidatos en 2026', 'Cada contienda local en las boletas del condado de Bay en 2026: los candidatos, sus propuestas, enlaces a sus campañas y de dónde viene el dinero de su campaña.', es_elections_page)] if ELECTIONS_READY else []),
    ('/es/reuniones', 'Próximas reuniones públicas en el condado de Bay', 'Cuándo y dónde se reúnen la Comisión del Condado, la Junta Escolar y cada comisión de ciudad, con enlaces a las agendas y los temas de dinero de cada una.', es_meetings_page),
    ('/records-request', 'Request a public record', 'Write a Florida public records request to any Bay County government in a minute: pick a record the site is missing or describe your own.', lambda: records_page(OUT)),
    ('/alerts', 'Get BayCounty.me updates by email', 'Follow Bay County, the school district or your city and get a short weekly email with new votes, data, corrections and upcoming meetings.', lambda: alerts_page(OUT)),
    ('/meetings', 'Upcoming public meetings in Bay County', 'When and where the County Commission, School Board and every city commission meet, with agenda links and the money items on each agenda.', lambda: meetings_page(OUT)),
    ('/connections/campaign-gifts', 'Campaign gifts and contracts', "Who funded the campaigns of Bay County's current elected officials, from Supervisor of Elections reports, and which donors also hold local government contracts.", campaign_page),
    ('/public-money/budget-compare', 'Compare budgets across years', "Compare any Bay County government's budget in two fiscal years, such as Lynn Haven FY2025 and FY2026: what grew, what shrank and what's new, by department, service and fund, in dollars and percent.", lambda: budget_compare_page(OUT, None)),
    *([('/elections', "Who's running in 2026", 'Every local race on Bay County ballots in 2026: the candidates, their platforms in their own words, links to their campaigns, and where their campaign money comes from.', elections_page)] if ELECTIONS_READY else []),
    ('/elections/past', 'Past local elections, 2016 to 2025', 'Every candidate who ran for a local office in Bay County from 2016 through 2025, winners and losers, with what each raised and spent and which businesses and groups gave.', past_elections_page),
    ('/public-money/exemptions', 'Property tax exemptions', 'Who gets a property tax exemption in Bay County, from homestead to disabled veterans, how many homes, and how much tax each one takes off bills, from the 2026 tax roll.', lambda: exemptions_page(OUT)),
    ('/public-money/contracts', 'Who gets the contracts', 'Major contracts approved by Bay County and its cities since 2022: winners, how they were awarded, change orders, emergency purchases and who the county paid most.', lambda: contracts_page(OUT)),
    ('/correspondence', 'Letters to officials',
     'Emails BayCounty.me sent to Bay County elected officials and managers, and their replies, published as public records.', lambda: correspondence_page(OUT)),
    ('/connections/shared-owners', 'Shared-owner campaign gifts',
     'Groups of Bay County businesses that share an owner or officer in state corporate records and each gave to the same local candidate, checked by hand. People are not named.', lambda: shared_owners_page(OUT)),
    ('/connections/nonprofits', 'Nonprofits in Bay County',
     'Every nonprofit in Bay County: what each reports to the IRS, the government money and grants that reach it, and public officials who sit on its board.', lambda: nonprofits_page(OUT)),
    ('/chambers', 'Chambers of commerce',
     "Bay County's two chambers of commerce, the Bay County Chamber and the Panama City Beach Chamber: who sits on their boards and staff, upcoming events and programs, their IRS filings, the public money they get, and board members' businesses that do work for local governments.", lambda: chambers_page(OUT)),
    ('/volunteer', 'Volunteer in Bay County',
     'Open volunteer needs from Bay County nonprofits, read every day from public volunteer boards, and the local nonprofits that rely on volunteers year-round, by cause.', lambda: volunteer_page(OUT)),
    ('/connections/business-ties', "Officials' businesses",
     'Registered businesses and nonprofits that list a Bay County official, department leader or candidate, checked by hand, and where those businesses meet campaigns and public money.', lambda: business_ties_page(OUT)),
    ('/public-money/accountability', 'Accountability console: projects from budget to close-out',
     'Bay County public projects followed from first budget to close-out: approvals, contracts, change orders, votes, payments and final cost, with questions raised by published rules, missing records and each agency\'s reply.', lambda: accountability_page(OUT)),
    ('/public-money/votes', 'How they voted', 'How Bay County commissioners, city officials and school board members voted on budgets, tax rates, contracts, land and borrowing, from official minutes.', lambda: votes_page(OUT)),
    ('/glossary', 'Plain-English guide', 'Every term on BayCounty.me explained simply: CRAs, tax increment, millage, homestead exemptions, budgets and more.', glossary_page),
    ('/updates', 'Updates', 'New pages, new data and corrections on BayCounty.me, newest first, with an RSS feed.', updates_page),
    ('/search', 'Search', 'Search every page, glossary term and public-money record on BayCounty.me.', search_page),
    ('/ask', 'Ask BayCounty.me', 'Ask a question in your own words about Bay County budgets, taxes, votes, contracts, meetings or officials, and get an answer from the public records on BayCounty.me, with links to each source.', ask_page),
    ('/about', 'About', 'What BayCounty.me is, where its information comes from, and how to send a correction.', about_page),
    ('/data-sources', 'Where our data comes from', 'Every source behind BayCounty.me: each government\'s agenda systems, websites and documents, and every state and federal database, with links, how often we check them and how we process the records.', data_sources_page),
    ('/privacy', 'Privacy', 'What BayCounty.me and its iPhone and Android apps collect: no accounts, no ads, no tracking.', privacy_page),
]


from vendor_pages import pages as vendor_page_list, index_page as vendors_index  # noqa: E402
from connections import connections_page  # noqa: E402
if open_books_page.PUBLIC:  # checkbook and budget tracker, hidden until registers arrive
    PAGES += [
        ('/public-money/checkbook', 'Checkbook', "Every payment a Bay County government makes, from its own check register: who got paid, how much, when and from which fund. Search any company, or see the money month by month.", lambda: checkbook_page(OUT)),
        ('/public-money/budget-tracker', 'Budget tracker', "How each department of a Bay County government is spending against its budget this year, from the government's own monthly budget report: spent, committed, and whether it's ahead of the calendar.", lambda: budget_tracker_page(OUT)),
    ]
PAGES += [('/connections', 'Connections: who governments paid, and who gave to officials', 'Who every Bay County government and agency paid, how those payees connect, and which businesses gave to the officials who approve the spending.', lambda: connections_page(OUT))]
PAGES += [(p, t, d, fn or (lambda: vendors_index(OUT))) for p, t, d, fn in vendor_page_list()]
from people_pages import pages as people_page_list, copy_assets as copy_profile_assets  # noqa: E402
from entity_links import link_names, write_names as write_entity_names, entity_js  # noqa: E402
PAGES += people_page_list()

PAGES += [(f'/governments/{g["slug"]}', g['short'] + ': budget, taxes, debt, votes and more',
           f'{g["short"]}, Florida: who runs it, the budget and property tax rate, debt, audit findings, how officials voted, contracts and projects, from public records.',
           (lambda k: (lambda: gov_page(k)))(g['key'])) for g in GOVLIST]
prune_es({p[0] for p in PAGES})
EN_TO_ES = {v: k for k, v in ES_ALT.items()}


PROFILE_PREFIXES = ('/public-money/vendors/', '/people/', '/profile')
PAGE_LABELS = {}  # path -> short label for breadcrumbs, filled in main()


def _labels():
    from es_pages import ES_MENU
    lab = {}
    for menu in (MENU, ES_MENU):
        for m in menu:
            if m.get('href'):
                lab[m['href']] = m['label']
            for c in menu_links(m):
                lab.setdefault(c['href'].split('#')[0], c['label'])
    for p, t, _, _ in PAGES:
        lab.setdefault(p, t)
    lab.pop('/', None); lab.pop('/es', None)
    return lab


def page_kind(path):
    return 'collection' if path in ('/governments', '/public-money/vendors', '/updates', '/open-data', '/glossary', '/es/glosario', '/meetings', '/es/reuniones') else None


def page_about(path):
    """What a profile page is about, so search engines can tie it to the real government or company."""
    if path.startswith('/governments/'):
        g = next((g for g in GOVLIST if f'/governments/{g["slug"]}' == path), None)
        if g:
            area = 'Bay County, Florida' if g.get('kind') in ('county', 'schools') else g['short'] + ', Florida'
            return {'@type': 'GovernmentOrganization', 'name': g.get('name') or g['short'],
                    'areaServed': {'@type': 'AdministrativeArea', 'name': area}}
    if path.startswith('/public-money/vendors/'):
        t = next((t for p, t, _, _ in PAGES if p == path), '')
        n = t.rsplit(': contracts', 1)[0]
        return {'@type': 'Organization', 'name': n} if n else None
    return None


def main():
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'assets'))
    os.makedirs(os.path.join(OUT, 'data'))
    open(os.path.join(OUT, 'assets', 'site.css'), 'w').write(TOKENS + '\n' + SITE_CSS)
    from glossary import TERMS
    gl = {t['id']: {'term': t['term'], 'simple': t['simple']} for t in TERMS}
    from city_filter import js_table as _city_js
    open(os.path.join(OUT, 'assets', 'site.js'), 'w').write(_city_js() + NAMES_JS + MENU_JS + SEARCH_JS + DEEPLINK_JS + LINKIFY_JS + entity_js() + DATES_JS + TERM_JS.replace('__GLOSSARY_ES__', json.dumps(glossary_es_terms(), ensure_ascii=False)).replace('__GLOSSARY__', json.dumps(gl, ensure_ascii=False)))
    shutil.copy(os.path.join(ROOT, '..', 'assets', 'logo_small.webp'), os.path.join(OUT, 'assets', 'flux-labs.webp'))
    shutil.copy(os.path.join(ROOT, 'favicon.svg'), os.path.join(OUT, 'favicon.svg'))
    shutil.copytree(os.path.join(ROOT, 'photos'), os.path.join(OUT, 'photos'), dirs_exist_ok=True)  # official photos (data/civic/scripts/official_photos.py)
    shutil.copytree(os.path.join(ROOT, 'email-icons'), os.path.join(OUT, 'assets', 'email'), dirs_exist_ok=True)  # icons in emails (api/_email_ui.js)
    shutil.copy(os.path.join(ROOT, 'tax.css'), os.path.join(OUT, 'assets', 'tax.css'))
    shutil.copy(os.path.join(ROOT, 'gov.js'), os.path.join(OUT, 'assets', 'gov.js'))
    shutil.copy(os.path.join(ROOT, 'completeness.js'), os.path.join(OUT, 'assets', 'completeness.js'))
    shutil.copy(os.path.join(ROOT, 'gov.css'), os.path.join(OUT, 'assets', 'gov.css'))
    shutil.copy(os.path.join(ROOT, 'home.js'), os.path.join(OUT, 'assets', 'home.js'))
    shutil.copy(os.path.join(ROOT, 'report.js'), os.path.join(OUT, 'assets', 'report.js'))
    write_report_es(OUT)
    shutil.copy(os.path.join(ROOT, 'tables.js'), os.path.join(OUT, 'assets', 'tables.js'))
    copy_profile_assets(OUT)
    print('entity names:', write_entity_names(OUT))
    from og import build_og
    from og import preview_text
    PREVIEW.update(preview_text())
    OG_VER.update(build_og(OUT, [x for x in PAGES if x[0] != '/profile'], MENU))  # /profile is a client-side shell: it uses the home card
    PAGE_LABELS.update(_labels())
    from gov_detail import write_savings_data
    write_savings_data(OUT)  # savings ideas on each government's page
    for path, title, desc, fn in PAGES:
        write(path, layout(title, desc, path, fn()))
    print('search index:', build_index(OUT, [x for x in PAGES if not x[0].startswith(PROFILE_PREFIXES)]), 'entries')  # profiles: own indexers
    open(os.path.join(OUT, 'updates.xml'), 'w').write(rss(DOMAIN))
    from app_data import write_app_data
    print('app data:', write_app_data(OUT, PAGES), 'files')
    open(os.path.join(OUT, '404.html'), 'w').write(layout('Page not found', 'Page not found', '/404',
        '<div class="page prose"><h1>That page isn\'t here.</h1><p><a href="/">Back to the home page</a></p></div>'))
    from admin_page import admin_page
    admin_page(OUT)
    from finance_page import finance_page
    finance_page(OUT)
    from seo import write_robots_and_sitemap
    print('sitemap:', write_robots_and_sitemap(OUT, [p for p, *_ in PAGES if p != '/profile'], alternates, lambda p: last_updated(es_updated_key(p))), 'urls')
    for dp, _, fs in os.walk(OUT):
        for f in fs:
            p = os.path.join(dp, f); print(os.path.relpath(p, OUT), os.path.getsize(p))


if __name__ == '__main__':
    main()
