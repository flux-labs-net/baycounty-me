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
    for i, p in enumerate(d['payments']):  # same order as data/prep_dash.py, so i is the ledger record id
        amt = f"${p['amount']:,.0f} · " if p.get('amount') else ''
        out.append({'k': 'CRA record', 't': f"{p.get('payee') or 'Payee not named'}", 's': f"{amt}{p.get('purpose') or ''} ({p['cra']}, {p.get('date_or_fy') or ''})",
                    'u': f'/public-money/cra-spending?id={i}'})
    return out


def _fema():
    d = json.load(open(os.path.join(DATA, 'michael', 'pa_ledger.json')))
    return [{'k': 'FEMA project', 't': r['t'] or f"Project {r['pw']}", 's': f"${r['f']:,.0f} federal · {r['a']} · category {r['c']}",
             'u': '/public-money/hurricane-michael?q=' + str(r['pw'])} for r in d['rows']]


def _surtax():
    d = json.load(open(os.path.join(DATA, 'tourism', 'tourism_surtax.json')))
    from tourism_page import surtax_id
    return [{'k': 'Sales tax project', 't': p['name'], 's': f"{p['government']} · {p.get('category') or ''} · {p['status'].replace('_', ' ')}",
             'u': '/public-money/sales-tax-projects' + (f'?p={surtax_id(p)}' if surtax_id(p) and p.get('lat') is not None else '')} for p in d['infra_surtax']['projects']]


def _audits():
    d = json.load(open(os.path.join(DATA, 'debt_audit', 'debt_audit.json')))
    from debt_audit_page import short, finding_id
    q = __import__('urllib.parse').parse.quote
    return [{'k': 'Audit finding', 't': f"{short(a['government'])}: {f.get('title', '')}", 's': f.get('plain', ''),
             'u': f"/public-money/audits?gov={q(short(a['government']))}#{finding_id(short(a['government']), a, f)}"} for a in d['audits'] for f in a['findings']]


def _contracts():
    d = json.load(open(os.path.join(DATA, 'contracts', 'contracts.json')))
    from contracts_page import SHORT
    q = __import__('urllib.parse').parse.quote
    return [{'k': 'Contract', 't': c['vendor'] or 'Vendor not named', 's': f"${c['amount']:,.0f} · {c['government']} · {c.get('purpose') or ''} ({c.get('date') or ''})",
             'u': f"/public-money/contracts?gov={q(SHORT.get(c['government'], c['government']))}" + (f"&q={q(c['vendor'][:60])}" if c.get('vendor') else '') + '#all'} for c in d['contracts'] if c.get('amount')]


def _votes():
    d = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))
    import re
    names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in d['bodies']}
    return [{'k': 'Vote', 't': v.get('headline') or v.get('plain_summary') or v.get('item'),
             's': f"{names.get(v['body'], v['body'])} · {v.get('date')} · {re.sub(r'[(].*?[)]', '', v.get('tally') or '').strip()} {v.get('outcome') or ''} · {v.get('summary') or ''} {', '.join(v.get('by_member') or {})}",
             'u': '/public-money/votes?q=' + __import__('urllib.parse').parse.quote((v.get('headline') or '')[:40]) + '#all'} for v in d['votes']]


def _agenda_items():
    """Items read from posted agendas (data/agendas/agenda_items.json, written by data/agendas/export_items.py)."""
    d = json.load(open(os.path.join(DATA, 'agendas', 'agenda_items.json')))
    out = []
    for i in d['items']:
        if not i.get('url') or not i.get('title'):
            continue
        amt = f"${i['amount']:,.0f} · " if i.get('amount') is not None and (i.get('kind') or '') not in ('budget', 'resolution', 'ordinance', 'public_hearing') else ''
        who = ', '.join(i.get('parties') or [])
        out.append({'k': 'Agenda item', 't': i['title'],
                    's': f"{i.get('body') or i.get('board')} · {i.get('date') or ''} · {amt}{(i.get('kind') or '').replace('_', ' ')}{' · ' + who if who else ''}",
                    'u': i['url']})
    return out


INDEXERS = [_glossary, _cra, _fema, _surtax, _audits, _contracts, _votes, _agenda_items]


def _vendors():
    from vendor_pages import search_rows
    return search_rows()


INDEXERS.append(_vendors)


def _people():
    from people_pages import search_rows
    return search_rows()


INDEXERS.append(_people)


def build_index(out_dir, pages):
    """Write data/search.json (the full index, read by the API) and data/search/*.json for the search page.

    The page loads the split files so the first results come from a small file: core.json (pages, sections,
    glossary; ~8 KB gzipped), then the page text and one file per dataset, in the background. Concatenated in
    the order listed in core.json they are exactly search.json, so the final results are unchanged."""
    rows = _pages(out_dir, pages) + _glossary()
    core = [{k: v for k, v in r.items() if k != 'x'} for r in rows]
    text = [r.get('x', '') for r in rows if r['k'] == 'Page']
    parts = []
    for fn in INDEXERS[1:]:
        try:
            got = fn()
        except FileNotFoundError:
            continue
        if got:
            parts.append((fn.__name__.strip('_'), got))
            rows += got
    sd = os.path.join(out_dir, 'data', 'search')
    os.makedirs(sd, exist_ok=True)
    dump = lambda obj, fp: json.dump(obj, open(fp, 'w'), ensure_ascii=False, separators=(',', ':'))
    dump(rows, os.path.join(out_dir, 'data', 'search.json'))
    dump({'rows': core, 'parts': [n for n, _ in parts]}, os.path.join(sd, 'core.json'))
    dump(text, os.path.join(sd, 'text.json'))
    for n, got in parts:  # one kind per file, so 'k' is stored once
        dump({'k': got[0]['k'], 'rows': [[r['t'], r['s'], r['u']] for r in got]} if all(r['k'] == got[0]['k'] and set(r) <= {'k', 't', 's', 'u'} for r in got) else {'rows': got},
             os.path.join(sd, n + '.json'))
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
  let IDX = null, t, pending = 0;
  const W = {Page: 6, Section: 4, Glossary: 5};
  const prep = r => ({...r, _t: norm(r.t), _s: norm(r.s), _x: norm(r.x)});
  // The index comes in pieces: core.json (pages, sections, glossary) first, then page text and each dataset.
  // Results show as soon as core.json arrives and refresh as the rest lands; once all is in, IDX matches search.json in order.
  let coreP = null;
  function load() {
    if (coreP) return coreP;
    coreP = fetch('/data/search/core.json').then(r => r.json()).then(c => {
      const core = c.rows.map(prep), parts = c.parts.map(() => []);
      const rebuild = () => { IDX = core.concat(...parts); };
      rebuild(); pending = c.parts.length + 1;
      const done = () => { pending--; rebuild(); if (inp.value.trim()) run(); };
      fetch('/data/search/text.json').then(r => r.json()).then(tx => { let i = 0; core.forEach(r => { if (r.k === 'Page') { r.x = tx[i++] || ''; r._x = norm(r.x); } }); }).catch(() => {}).finally(done);
      c.parts.forEach((n, i) => fetch('/data/search/' + n + '.json').then(r => r.json()).then(p => { parts[i] = p.k ? p.rows.map(([t, s, u]) => prep({k: p.k, t, s, u})) : p.rows.map(prep); }).catch(() => {}).finally(done));
      return IDX;
    });
    return coreP;
  }
  const getIdx = async () => { await load(); return IDX; };
  function hl(s, words) { let h = esc(s); words.forEach(w => { if (w.length > 1) h = h.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&') + ')', 'ig'), '<mark>$1</mark>'); }); return h; }
  async function run() {
    const q = inp.value.trim(), words = norm(q).split(/\\s+/).filter(Boolean);
    const u = new URL(location.href); if (q) u.searchParams.set('q', q); else u.searchParams.delete('q'); history.replaceState(null, '', u);
    if (!words.length) { res.innerHTML = ''; cnt.textContent = ''; return; }
    const idx = await getIdx();
    const hits = [];
    for (const r of idx) {
      let sc = 0, ok = true;
      for (const w of words) { const it = r._t.indexOf(w), is = r._s.indexOf(w), ix = r._x ? r._x.indexOf(w) : -1; if (it < 0 && is < 0 && ix < 0) { ok = false; break; } sc += it >= 0 ? (it === 0 ? 4 : 3) : is >= 0 ? 1 : 0.5; }
      if (ok) hits.push([sc + (W[r.k] || 0), r]);
    }
    hits.sort((a, b) => b[0] - a[0]);
    cnt.textContent = (hits.length ? `${hits.length.toLocaleString()} result${hits.length === 1 ? '' : 's'}${hits.length > 100 ? ', showing the top 100' : ''}` : pending ? 'No results yet.' : 'No results. Try fewer or different words.') + (pending ? ' Still loading records…' : '');
    const snip = r => { if (!r.x || words.some(w => r._s.includes(w))) return r.s; const i = r._x.indexOf(words[0]); return i < 0 ? r.s : '…' + r.x.slice(Math.max(0, i - 80), i + 140) + '…'; };
    res.innerHTML = hits.slice(0, 100).map(([, r]) => `<li><a href="${esc(r.u)}"><span class="r-k">${esc(r.k)}</span><b>${hl(r.t, words)}</b><span class="r-s">${hl(snip(r), words)}</span></a></li>`).join('');
  }
  inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(run, 150); });
  inp.addEventListener('focus', load, {once: true}); // start fetching the small core file before the first keystroke
  const q0 = new URL(location.href).searchParams.get('q'); if (q0) { inp.value = q0; run(); } else inp.focus({preventScroll: true});
})();
</script>'''
