"""Site search for baycounty.me.

build_index() runs after every page is written: it reads the built HTML for page
titles and section headings, then adds glossary terms and records from each dataset.
Add a new dataset by appending to INDEXERS.
"""
import json, os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def _pages(out_dir, pages):
    rows = []
    for path, title, desc, _ in pages:
        if path == '/search':
            continue
        fp = os.path.join(out_dir, path.strip('/'), 'index.html') if path != '/' else os.path.join(out_dir, 'index.html')
        h = open(fp).read()
        main = re.search(r'<main[^>]*>(.*)</main>', h, re.S)
        body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', main.group(1) if main else '', flags=re.S)
        body = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', body))).strip()
        rows.append({'k': 'Page', 't': title, 's': desc, 'u': path, 'x': body[:30000]})
        for m in re.finditer(r'<h2[^>]*id="([^"]+)"[^>]*>(.*?)</h2>', h, re.S):
            txt = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
            if txt:
                rows.append({'k': 'Section', 't': txt, 's': title, 'u': f'{path}#{m.group(1)}'})
    return rows


def _glossary():
    from glossary import TERMS
    return [{'k': 'Glossary', 't': t['term'], 's': t['simple'], 'u': f"/glossary#{t['id']}"} for t in TERMS]


def _cra():
    d = json.load(open(os.path.join(DATA, 'merged.json')))
    out = []
    for p in d['payments']:
        amt = f"${p['amount']:,.0f} · " if p.get('amount') else ''
        out.append({'k': 'CRA record', 't': f"{p.get('payee') or 'Payee not named'}", 's': f"{amt}{p.get('purpose') or ''} ({p['cra']}, {p.get('date_or_fy') or ''})",
                    'u': '/public-money/cra-spending'})
    return out


def _fema():
    d = json.load(open(os.path.join(DATA, 'michael', 'pa_ledger.json')))
    return [{'k': 'FEMA project', 't': r['t'] or f"Project {r['pw']}", 's': f"${r['f']:,.0f} federal · {r['a']} · category {r['c']}",
             'u': '/public-money/hurricane-michael?q=' + str(r['pw'])} for r in d['rows']]


def _surtax():
    d = json.load(open(os.path.join(DATA, 'tourism', 'tourism_surtax.json')))
    return [{'k': 'Sales tax project', 't': p['name'], 's': f"{p['government']} · {p.get('category') or ''} · {p['status'].replace('_', ' ')}", 'u': '/public-money/sales-tax-projects'} for p in d['infra_surtax']['projects']]


def _audits():
    d = json.load(open(os.path.join(DATA, 'debt_audit', 'debt_audit.json')))
    from debt_audit_page import short
    return [{'k': 'Audit finding', 't': f"{short(a['government'])}: {f.get('title', '')}", 's': f.get('plain', ''), 'u': '/public-money/audits'} for a in d['audits'] for f in a['findings']]


def _contracts():
    d = json.load(open(os.path.join(DATA, 'contracts', 'contracts.json')))
    return [{'k': 'Contract', 't': c['vendor'] or 'Vendor not named', 's': f"${c['amount']:,.0f} · {c['government']} · {c.get('purpose') or ''} ({c.get('date') or ''})", 'u': '/public-money/contracts'} for c in d['contracts'] if c.get('amount')]


INDEXERS = [_glossary, _cra, _fema, _surtax, _audits, _contracts]


def build_index(out_dir, pages):
    rows = _pages(out_dir, pages)
    for fn in INDEXERS:
        try:
            rows += fn()
        except FileNotFoundError:
            pass
    json.dump(rows, open(os.path.join(out_dir, 'data', 'search.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    return len(rows)


def search_page():
    return '''<div class="page tax srch">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Search</span><h1>Search BayCounty.me</h1>
    <p class="lede">Every page, every glossary term, and every record in the site's ledgers: CRA payments and FEMA projects so far.</p></div></header>
  <section class="addr-search" role="search">
    <label for="sq" class="fld"><span>Search for a name, place, project or term</span></label>
    <div class="ac"><input id="sq" type="search" autocomplete="off" placeholder="e.g. Crowder Gulf, millage, St. Andrews, pier"></div>
    <p class="muted small" id="sCount"></p>
  </section>
  <ol class="results" id="sRes" aria-live="polite"></ol>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script>
(() => {
  const inp = document.getElementById('sq'), res = document.getElementById('sRes'), cnt = document.getElementById('sCount');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const norm = s => String(s || '').toLowerCase().normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '');
  let IDX = null, t;
  const W = {Page: 6, Section: 4, Glossary: 5};
  async function load() { if (!IDX) { IDX = (await (await fetch('/data/search.json')).json()).map(r => ({...r, _t: norm(r.t), _s: norm(r.s), _x: norm(r.x)})); } return IDX; }
  function hl(s, words) { let h = esc(s); words.forEach(w => { if (w.length > 1) h = h.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'ig'), '<mark>$1</mark>'); }); return h; }
  async function run() {
    const q = inp.value.trim(), words = norm(q).split(/\\s+/).filter(Boolean);
    const u = new URL(location.href); if (q) u.searchParams.set('q', q); else u.searchParams.delete('q'); history.replaceState(null, '', u);
    if (!words.length) { res.innerHTML = ''; cnt.textContent = ''; return; }
    const idx = await load();
    const hits = [];
    for (const r of idx) {
      let sc = 0, ok = true;
      for (const w of words) { const it = r._t.indexOf(w), is = r._s.indexOf(w), ix = r._x ? r._x.indexOf(w) : -1; if (it < 0 && is < 0 && ix < 0) { ok = false; break; } sc += it >= 0 ? (it === 0 ? 4 : 3) : is >= 0 ? 1 : 0.5; }
      if (ok) hits.push([sc + (W[r.k] || 0), r]);
    }
    hits.sort((a, b) => b[0] - a[0]);
    cnt.textContent = hits.length ? `${hits.length.toLocaleString()} result${hits.length === 1 ? '' : 's'}${hits.length > 100 ? ', showing the top 100' : ''}` : 'No results. Try fewer or different words.';
    const snip = r => { if (!r.x || words.some(w => r._s.includes(w))) return r.s; const i = r._x.indexOf(words[0]); return i < 0 ? r.s : '…' + r.x.slice(Math.max(0, i - 80), i + 140) + '…'; };
    res.innerHTML = hits.slice(0, 100).map(([, r]) => `<li><a href="${esc(r.u)}"><span class="r-k">${esc(r.k)}</span><b>${hl(r.t, words)}</b><span class="r-s">${hl(snip(r), words)}</span></a></li>`).join('');
  }
  inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(run, 150); });
  const q0 = new URL(location.href).searchParams.get('q'); if (q0) { inp.value = q0; run(); } else inp.focus({preventScroll: true});
})();
</script>'''
