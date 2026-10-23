"""Savings finder (/public-money/savings): where Bay County governments could spend less, from records already on the site.

Sources:
  data/savings/opportunities.json  reviewed opportunities: what each rests on, the assumption and the next step
  data/projects/seed.json          project histories, through accountability_page.build() (first and final figures, spending)
  data/merged.json                 the CRA ledger (payments), matched by the selectors in opportunities.json

Every dollar figure is computed here from those records; opportunities.json holds only estimate rates and reviewed unit
counts (such as blocks of sidewalk). A selector that stops matching the records it expects fails the build.

Writes public/data/savings.json (read by assets/savings.js) and feeds the savings-opportunities and savings-evidence
datasets (site/page_datasets.py), so the page's data is in the database and /api/v1.
An opportunity is a question worth asking, with an illustrative estimate, not a finding that money was wasted.
"""
import json, os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))

KINDS = {'project_progress', 'project_growth', 'budget_vs_spent', 'ledger', 'ledger_share'}
FIELDS = {'amount', 'compare', 'gap'}


def _load():
    cfg = json.load(open(os.path.join(DATA, 'savings', 'opportunities.json')))
    ledger = json.load(open(os.path.join(DATA, 'merged.json')))['payments']
    from accountability_page import build, GOVN
    projects = {p['id']: p for p in build()['projects']}
    return cfg, ledger, projects, GOVN


def _matches(row, m):
    if m.get('cra') and row.get('cra') != m['cra']:
        return False
    purpose, payee = row.get('purpose') or '', row.get('payee') or ''
    if m.get('purpose_starts') and not purpose.startswith(m['purpose_starts']):
        return False
    if m.get('purpose_has') and not any(s in purpose for s in m['purpose_has']):
        return False
    if m.get('payee_has') and not any(s in payee for s in m['payee_has']):
        return False
    return True


def _select(ledger, m, expect, where):
    rows = [r for r in ledger if _matches(r, m)]
    assert len(rows) == expect, f'{where}: selector {m} matched {len(rows)} ledger rows, expected {expect}'
    return rows


_SHARE = re.compile(r'CRA share of (?:a |an )?\$([\d,]+(?:\.\d+)?)\s*(M|million)?', re.I)


def _share_total(purpose):
    """Total project cost from a ledger description such as '(CRA share of $310,000)' or 'CRA share of a $2.4M project'."""
    m = _SHARE.search(purpose or '')
    if not m:
        return None
    n = float(m.group(1).replace(',', ''))
    return n * 1e6 if m.group(2) else n


def _spent(p):
    """Latest 'spent to date' figure on a project timeline."""
    xs = [x for x in p['ev'] if x['k'] == 'spent' and x.get('a') is not None]
    return max(xs, key=lambda x: x.get('s') or '') if xs else None


def _first_firm(p):
    if p.get('base'):
        return p['base']
    xs = [x for x in p['ev'] if x['k'] in ('award', 'budget', 'approval') and x.get('a')]
    return {'a': xs[0]['a'], 't': xs[0]['t']} if xs else None


def _row(op, g, label, amount, amount_is=None, compare=None, compare_is=None, url=None, project_id=None, payee=None, units=None):
    r = {'opportunity_id': op['id'], 'group_id': g['id'], 'group_title': g['title'], 'kind': g['kind'], 'label': label,
         'amount': amount, 'amount_is': amount_is, 'compare': compare, 'compare_is': compare_is,
         'gap': (compare - amount) if compare is not None and amount is not None else None,
         'ratio': (amount / compare) if compare and amount is not None else None,
         'units': units, 'unit': g.get('unit') if units else None,
         'per_unit': (amount / units) if units and amount is not None else None,
         'paid_to': payee, 'project_id': project_id, 'source_url': url}
    return r


def _group_rows(op, g, ledger, projects):
    where = f"{op['id']}/{g['id']}"
    assert g['kind'] in KINDS, f'{where}: unknown kind {g["kind"]}'
    out = []
    if g['kind'] in ('project_progress', 'project_growth', 'budget_vs_spent'):
        for pid in g['projects']:
            assert pid in projects, f'{where}: no Accountability project {pid}'
            p = projects[pid]
            if g['kind'] == 'project_progress':
                s, t = _spent(p), p.get('total')
                assert s and t, f'{where}: {pid} needs a spent-to-date event and a total project cost'
                out.append(_row(op, g, p['n'], s['a'], 'spent to date', t['a'], t['t'], s.get('u'), pid))
            elif g['kind'] == 'project_growth':
                f, t = _first_firm(p), p.get('total') or p.get('now')
                assert f and t, f'{where}: {pid} needs a first firm figure and a final figure'
                out.append(_row(op, g, p['n'], f['a'], f['t'], t['a'], t['t'], next((x.get('u') for x in reversed(p['ev']) if x.get('a') == t['a']), None), pid))
            else:
                xs = [x for x in p['ev'] if x['k'] == 'spent' and x.get('budget') and x['d'] == g['fy']]
                assert len(xs) == 1, f'{where}: {pid} has {len(xs)} {g["fy"]} spent events with a budget, expected 1'
                x = xs[0]
                out.append(_row(op, g, f"{p.get('agency') or p['n']}, {g['fy']}", x['a'], 'spent', x['budget'], 'capital budget', x.get('u'), pid))
    elif g['kind'] == 'ledger':
        if 'items' in g:
            for it in g['items']:
                r = _select(ledger, it['match'], 1, where)[0]
                out.append(_row(op, g, it.get('label') or r['purpose'], r['amount'], r.get('date_or_fy'), url=r.get('source_url'),
                                payee=r.get('payee'), units=it.get('units')))
        else:
            for r in _select(ledger, g['match'], g['expect'], where):
                out.append(_row(op, g, r['purpose'].split(' (')[0], r['amount'], r.get('date_or_fy'), url=r.get('source_url'), payee=r.get('payee')))
    else:  # ledger_share: every row whose own description gives the full project cost
        for r in ledger:
            if _matches(r, g['match']) and r.get('amount') and _share_total(r.get('purpose')):
                out.append(_row(op, g, r['purpose'].split(' (')[0], r['amount'], 'CRA share', _share_total(r['purpose']), 'total project cost',
                                r.get('source_url'), payee=r.get('payee')))
        assert out, f'{where}: no ledger rows state a CRA share of a total cost'
    for r in out:
        assert r['amount'] is not None, f'{where}: {r["label"]} has no amount'
    return out


def build():
    cfg, ledger, projects, GOVN = _load()
    ops, evidence = [], []
    ids = [o['id'] for o in cfg['opportunities']]
    assert len(ids) == len(set(ids)), 'duplicate opportunity ids'
    for op in cfg['opportunities']:
        rows = []
        for g in op['groups']:
            rows += _group_rows(op, g, ledger, projects)
        ip = op.get('in_play')
        in_play = None
        if ip:
            assert ip['field'] in FIELDS, f"{op['id']}: in_play field must be one of {sorted(FIELDS)}"
            sel = [r for r in rows if r['group_id'] == ip['group']]
            assert sel, f"{op['id']}: in_play group {ip['group']} has no rows"
            in_play = round(sum(r[ip['field']] or 0 for r in sel), 2)
        rate = op.get('rate')
        low = round(in_play * rate['low'], 2) if rate and in_play is not None else None
        high = round(in_play * rate['high'], 2) if rate and in_play is not None else None
        estimate = 'range' if rate else ('records' if op.get('records_needed') else 'none')
        for o in op.get('overlaps', []):
            assert o in ids, f"{op['id']}: overlaps unknown opportunity {o}"
        urls = list(dict.fromkeys(r['source_url'] for r in rows if r.get('source_url')))
        ops.append({'id': op['id'], 'title': op['title'], 'govs': op['govs'], 'government': ', '.join(GOVN.get(g, g) for g in op['govs']),
                    'lever': op['lever'], 'confidence': op['confidence'], 'basis': op['basis'], 'assumption': op.get('assumption') or None,
                    'next_step': op['next_step'], 'in_play': in_play, 'in_play_is': (ip or {}).get('is'),
                    'rate_low': rate['low'] if rate else None, 'rate_high': rate['high'] if rate else None,
                    'savings_low': low, 'savings_high': high, 'estimate': estimate, 'overlaps': op.get('overlaps') or [],
                    'groups': [{'id': g['id'], 'title': g['title'], 'kind': g['kind'], 'note': g.get('note'), 'unit': g.get('unit')} for g in op['groups']],
                    'requests': [{'q': q['q'], 'gk': q['gov']} for q in op.get('records_needed', [])], 'sources': urls})
        evidence += rows
    ops.sort(key=lambda o: (-(o['savings_high'] if o['savings_high'] is not None else -1), -(o['in_play'] or 0)))
    for i, o in enumerate(ops, 1):
        o['rank'] = i
    stats = {'opportunities': len(ops), 'in_play': round(sum(o['in_play'] or 0 for o in ops), 2),
             'savings_low': round(sum(o['savings_low'] or 0 for o in ops), 2), 'savings_high': round(sum(o['savings_high'] or 0 for o in ops), 2),
             'needs_records': sum(1 for o in ops if o['estimate'] == 'records'), 'requests': sum(len(o['requests']) for o in ops)}
    return {'about': 'BayCounty.me Savings finder: places Bay County governments could spend less, each with the records it rests on, an illustrative estimate and its assumption. An opportunity is a question worth asking, not a finding that money was wasted.',
            'stats': stats, 'opportunities': ops, 'evidence': evidence, 'general_requests': cfg.get('general_requests', [])}


def opportunity_rows():
    return [{'opportunity_id': o['id'], 'rank': o['rank'], 'title': o['title'], 'government': o['government'], 'gov_ids': o['govs'],
             'lever': o['lever'], 'confidence': o['confidence'], 'in_play': o['in_play'], 'in_play_is': o['in_play_is'],
             'rate_low': o['rate_low'], 'rate_high': o['rate_high'], 'savings_low': o['savings_low'], 'savings_high': o['savings_high'],
             'estimate': o['estimate'], 'basis': o['basis'], 'assumption': o['assumption'], 'next_step': o['next_step'],
             'overlaps': o['overlaps'] or None, 'records_needed': [r['q'] for r in o['requests']] or None,
             'source_url': (o['sources'] or [None])[0]} for o in build()['opportunities']]


def evidence_rows():
    return build()['evidence']


def money(n):
    if n is None:
        return '—'
    return f'${n/1e6:,.1f}M' if n >= 1e6 else (f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}')


def savings_page(out_dir):
    D = build()
    json.dump(D, open(os.path.join(out_dir, 'data', 'savings.json'), 'w'), separators=(',', ':'))
    for f in ('savings.js', 'savings.css'):
        open(os.path.join(out_dir, 'assets', f), 'w').write(open(os.path.join(HERE, f)).read())
    S = D['stats']
    reqs = ''.join(f'<li><b>{e(r["q"])}</b><br><span class="muted small">{e(r["why"])}</span> <a class="pill sm" href="/records-request?d={e(r["q"])}">Request this record</a></li>' for r in D['general_requests'])
    return f'''<div class="page tax sav">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Accountability</span><h1>Savings finder</h1>
    <p class="lede">Places Bay County's local governments could spend less, found in records already on this site: projects that ran over, money budgeted but not spent, services bought separately that could be bought together. Each one shows the records it rests on, an estimate with its assumption, and the question to ask next.</p></div></header>
  <div class="sav-stats" role="list">
    <div role="listitem"><b id="svM">{money(S["in_play"])}</b><span>spending these touch</span></div>
    <div role="listitem"><b id="svL">{money(S["savings_low"])}</b><span>potential savings, low estimate</span></div>
    <div role="listitem"><b id="svH">{money(S["savings_high"])}</b><span>potential savings, high estimate</span></div>
    <div role="listitem"><b id="svN">{S["needs_records"]:,}</b><span>need records before an estimate</span></div>
  </div>
  <section class="tx-sec" id="list"><div class="sec-hd"><h2>Opportunities</h2><span class="muted" id="svCount" aria-live="polite"></span></div>
    <p class="small muted">Ranked by the high estimate. Estimates are illustrative: each states its assumption, and some overlap, so treat the totals as a scale, not a promise.</p>
    <div class="sav-filters" id="svF" role="group" aria-label="Filter by kind of saving"></div>
    <div id="svList" class="sav-list"><p class="muted">Loading opportunities…</p></div></section>
  <section class="tx-sec" id="records"><div class="sec-hd"><h2>Records that would find more</h2></div>
    <p class="small muted">The CRA ledger covers projects and grants, not every payment. These records, asked of each city and the county, would show subscriptions, duplicate payments and price differences.</p>
    <ul class="plain sav-reqs">{reqs}</ul></section>
  <section class="tx-sec method" id="how"><div class="sec-hd"><h2>How this was built</h2></div>
    <ul class="plain">
      <li>Every figure comes from records already on the site: project histories on the <a href="/public-money/accountability">Accountability console</a> and rows of the <a href="/public-money/cra-spending">CRA ledger</a>. Each opportunity links the documents behind it.</li>
      <li>An estimate multiplies the spending in play by a low and a high rate. The rate is the stated assumption, not a measured result. Where the records can't support a rate, the opportunity says which records are needed instead.</li>
      <li>Totals add each opportunity once, but some overlap (engineering fees are part of project cost). Grants are included in project costs, so totals are more than local tax money alone.</li>
      <li>Download everything as <a href="/data/savings.json">JSON</a>, or use the <a href="/open-data">open data</a> and <a href="/developers">API</a>. Corrections: <a href="/about#contact">send one</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/savings.css">
<script src="/assets/savings.js" defer></script>'''


if __name__ == '__main__':
    D = build()
    print(json.dumps(D['stats']))
    for o in D['opportunities']:
        print(o['rank'], o['id'], o['in_play'], o['savings_low'], o['savings_high'])
