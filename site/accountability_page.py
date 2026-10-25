"""Accountability console: each public project from first budget to close-out, with flags from published rules.

Sources, all already on the site:
  data/projects/seed.json       hand-reviewed project histories (mostly CRA), every event sourced
  data/contracts/contracts.json awards and change orders; change orders grouped per contract by change_growth
  data/votes/contract_votes.json + votes.json   the recorded vote on an award or change order
  sales tax schedule matches    county half-cent projects with programmed years (opendata.schedule_by_project)
  data/projects/responses.json  what each agency said when sent its flags (right of reply)

Writes public/data/accountability.json (read by assets/accountability.js and listed on /open-data).
A flag is a question for the agency, not a finding of wrongdoing. Wording here has to stay that way.
"""
import json, os, re, html
from datetime import datetime, timezone

import vendors as V
import change_growth as CG
from city_filter import city_bar, scope
from entity_graph import build as entity_graph

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
e = lambda s: html.escape(str(s if s is not None else ''))
GOVK = {'Bay County': 'county', 'Panama City': 'pc', 'Panama City Beach': 'pcb', 'Lynn Haven': 'lh', 'Callaway': 'cw',
        'Springfield': 'sp', 'Parker': 'parker', 'Mexico Beach': 'mb'}
GOVN = {v: k for k, v in GOVK.items()}
TODAY_FY = 2027  # FY2027 began Oct 1, 2026; a programmed year up to FY2026 is over

# The rules. Each flag the console raises names one of these. 'sev' explains how its level is set.
RULES = [
    {'id': 'growth', 'title': 'Cost grew more than 10%',
     'when': 'The latest firm figure (final cost, current contract total or current project estimate) is more than 10% above the first firm figure (the award or first budget). Over 25% is marked high.',
     'means': 'The project costs noticeably more than the public was first told. Bay County and Panama City require board approval once change orders pass 10%.',
     'not': 'It does not mean money was wasted. Scope added on purpose, design and land costs, and price changes all raise totals. The flag asks the agency to explain the difference.'},
    {'id': 'late', 'title': 'Running late',
     'when': 'A source reports the project finished more than 90 days after its schedule, or a sales tax project is not complete after the last year it was programmed for. Over a year is marked high.',
     'means': 'The public waited longer than planned, which often costs money too.',
     'not': 'Delays are often caused by utilities, permits, storms or grant timing outside the agency\'s control.'},
    {'id': 'conflict', 'title': "Figures don't agree",
     'when': 'Two or more public documents give different amounts for the same project and period.',
     'means': 'Residents cannot tell from the public record what the project costs or what was spent.',
     'not': 'The documents may count different things (one phase, the CRA share, the whole project). The agency can settle it with one breakdown.'},
    {'id': 'payee', 'title': "Who was paid isn't public yet",
     'when': 'Money was spent or committed, but no record we have names the contractor or seller, or states the price.',
     'means': 'The public cannot check who received the money or for how much.',
     'not': 'The information usually exists in the agency\'s files; it just wasn\'t in the report we read. A records request will usually get it.'},
    {'id': 'mixed', 'title': 'Local share unclear',
     'when': 'The project mixes CRA or city money with state or federal grants, and no record says how much is local tax money.',
     'means': 'The totals shown overstate what local taxpayers paid, by an unknown amount.',
     'not': 'Grants are good for local taxpayers. The flag is only about knowing the split.'},
    {'id': 'budget', 'title': 'Budgeted, but spending not shown',
     'when': 'A budget was set, but actual spending is under half of it for a year that has ended, or no record of actual spending was found.',
     'means': 'The money may be sitting unspent, may have been moved, or the work stalled.',
     'not': 'Unspent budgets often roll over to the next year, and a delayed project may still be on track overall.'},
    {'id': 'approval', 'title': 'Approval not found in the minutes',
     'when': 'A change order appeared on an agenda, but the meeting minutes we read do not record a vote approving it.',
     'means': 'We could not confirm the board approved the added cost.',
     'not': 'It may have been approved on a consent agenda, in minutes we have not read, or by staff within their authority.'},
    {'id': 'stack', 'title': 'More than one incentive, same place',
     'when': 'One address or company receives more than one grant or rebate from the same agency.',
     'means': 'The total public support is easy to miss when each award is reported on its own.',
     'not': 'Programs usually allow this. The flag adds it up; it does not say it was wrong.'},
    {'id': 'removed', 'title': 'Dropped from the schedule',
     'when': 'A project was struck from the sales tax project schedule.',
     'means': 'Money promised to voters for this project went elsewhere or is on hold.',
     'not': 'Schedules are amended when costs, grants or priorities change; the replacement project may be listed.'},
]
RULE_IDS = {r['id'] for r in RULES}
SEV_ORDER = {'high': 0, 'warn': 1, 'info': 2}


def money(n):
    if n is None:
        return '—'
    sign, n = ('−' if n < 0 else ''), abs(n)
    return sign + (f'${n/1e6:,.1f}M' if n >= 1e6 else (f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}'))


def sort_key(d, k=''):
    """Sortable ISO date for '2024-05-28', '2021-03', '2019', 'FY2024'. A fiscal year's budget sits at its start
    (Oct 1 of the year before); anything else in a fiscal year sits at its end (Sep 30)."""
    d = str(d or '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d):
        return d
    if re.fullmatch(r'\d{4}-\d{2}', d):
        return d + '-15'
    m = re.fullmatch(r'FY(\d{4})', d)
    if m:
        y = int(m.group(1))
        return f'{y-1}-10-01' if k == 'budget' else f'{y}-09-30'
    if re.fullmatch(r'\d{4}', d):
        return d + '-07-01'
    m = re.search(r'(\d{4})', d)
    return (m.group(1) + '-07-01') if m else '9999'


def nice_date(d):
    d = str(d or '')
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d):
            return datetime.strptime(d, '%Y-%m-%d').strftime('%b %-d, %Y')
        if re.fullmatch(r'\d{4}-\d{2}', d):
            return datetime.strptime(d, '%Y-%m').strftime('%b %Y')
    except ValueError:
        pass
    return d


def _votes():
    vj = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))
    cv = json.load(open(os.path.join(DATA, 'votes', 'contract_votes.json')))
    by = {}
    for l in cv['links']:
        by.setdefault(l['record_id'], []).append(vj['votes'][l['vote_index']])
    return by


def _vote_event(v, what):
    return {'d': v['date'], 'k': 'vote', 't': f"{what}: {v.get('outcome') or 'vote'} {v.get('tally') or ''}".strip(), 'u': v.get('source_url'),
            'tally': v.get('tally'), 'members': v.get('by_member') or {}}


# ---------- 1. Hand-reviewed projects ----------
def curated():
    S = json.load(open(os.path.join(DATA, 'projects', 'seed.json')))
    out = []
    for p in S['projects']:
        ev = []
        for x in p['events']:
            y = dict(x)
            if y.get('payee'):
                vid, vn, vt = V.resolve(y['payee'])
                if vt == 'business' and 'vendor:' + vid in entity_graph().ents:  # links to the company's profile
                    y['vid'] = vid
            ev.append(y)
        flags = [{'r': c['rule'], 'sev': 'warn', 'note': c['note']} for c in p.get('checks', [])]
        q = {'id': p['id'], 'n': p['name'], 'gk': p['gov'], 'g': GOVN.get(p['gov'], p['gov']), 'agency': p['agency'], 'where': p.get('where'),
             'what': p.get('what'), 'funding': p.get('funding'), 'status': p['status'], 'src': 'reviewed', 'ev': ev, 'flags': flags,
             'gaps': [{'q': g['q'], 'gk': g.get('gov', p['gov'])} for g in p.get('gaps', [])], 'cos': p.get('cos', [])}
        if p.get('baseline'):
            q['base'] = p['baseline']
        # growth is only measured like for like: a contract against itself. A project total (design, land,
        # inspection and construction) is shown beside the award but never compared with it as 'growth'.
        if p.get('contract'):
            q['now'] = {'a': p['contract']['now'], 't': 'contract total after change orders'}
        if p.get('final'):
            q['total'] = p['final']
        if p.get('contract'):
            q['contract'] = p['contract']
        if p.get('late_days'):
            q['late_days'] = p['late_days']
        # the latest project estimate on a 'spent' event, when no final figure was given
        est = [x for x in ev if x.get('estimate')]
        if est and 'total' not in q:
            q['total'] = {'a': est[-1]['estimate'], 't': 'current total project cost', 'open': True}
        out.append(q)
    return out


# ---------- 2. Contracts with change orders ----------
def contract_projects(absorb):
    d = json.load(open(os.path.join(DATA, 'contracts', 'contracts.json')))
    votes = _votes()
    cos_index = {(x.get('date'), x.get('change_amount'), x.get('project')): j for j, x in enumerate(d['change_orders'])}
    out, absorbed = [], {}
    for r in CG.co_contracts(d):
        gk = GOVK.get(r['g'], r['g'])
        key = None
        for pid, (g, vid, word) in absorb:
            if r['g'] == g and r['vid'] == vid and word in r['title'].lower():
                key = pid
        ev = []
        # the award: same government and company, and the same original amount or contract number
        m = CG._TAG.search(r['title'])
        aw = None
        for i, c in enumerate(d['contracts']):
            if CG.SHORT.get(c['government']) != r['g'] or V.resolve(c['vendor'])[0] != r['vid']:
                continue
            if (r['orig'] and c.get('amount') and abs(c['amount'] - r['orig']) < 1) or (m and m.group(1).lower() in (c.get('purpose') or '').lower()):
                aw = (i, c)
                break
        if aw:
            i, c = aw
            ev.append({'d': c['date'], 'k': 'award', 'a': c['amount'], 't': f"Contract awarded ({c.get('method') or 'method not stated'})", 'payee': r['vn'],
                       'vid': r['vid'] if not r['public'] else None, 'u': c.get('source_url')})
            for v in votes.get(f'contract:{i}', []):
                ev.append(_vote_event(v, 'Award vote'))
        elif r['orig']:
            ev.append({'d': None, 'k': 'award', 'a': r['orig'], 't': 'Original contract amount, as stated on the change-order agenda item', 'payee': r['vn'],
                       'vid': r['vid'] if not r['public'] else None, 'u': r['cos'][0].get('u')})
        for n, c in enumerate(r['cos'], 1):
            ev.append({'d': c['d'], 'k': 'change', 'a': c['a'], 't': (c.get('p') or 'Change order') + (f" · {c['why']}" if c.get('why') else ''), 'payee': r['vn'],
                       'vid': r['vid'] if not r['public'] else None, 'u': c.get('u')})
            j = cos_index.get((c['d'], c['a'], c['p']))
            for v in votes.get(f'change_order:{j}', []) if j is not None else []:
                ev.append(_vote_event(v, 'Change-order vote'))
        flags, gaps = [], []
        if r['pct'] is not None and r['pct'] > 10 and not r['unsure']:
            flags.append({'r': 'growth', 'sev': 'high' if r['pct'] > 25 else 'warn',
                          'note': f"Change orders add {r['pct']:.0f}%{'+' if r['atleast'] else ''} ({money(r['added'])}) to the {money(r['orig'])} original."})
        if r['appr'] == 'not confirmed':
            flags.append({'r': 'approval', 'sev': 'warn', 'note': 'At least one change order here was on an agenda, but the minutes we read do not record its approval.'})
        if not r['orig']:
            gaps.append({'q': f"The original contract amount and every change order (with amounts and reasons) for the {r['g']} contract with {r['vn']}: {r['title']}", 'gk': gk})
        item = {'ev': ev, 'flags': flags, 'gaps': gaps, 'orig': r['orig'], 'added': r['added'], 'pct': r['pct']}
        if key:
            absorbed.setdefault(key, []).append(item)
            continue
        now = (r['orig'] + r['added']) if r['orig'] else None
        st = 'contract'
        out.append({'id': 'co-' + re.sub(r'[^a-z0-9]+', '-', f"{gk}-{r['vid']}-{r['title'].lower()}")[:70].strip('-'), 'n': r['title'], 'gk': gk, 'g': r['g'],
                    'agency': r['g'], 'what': f"Contract with {r['vn']}.", 'status': st, 'src': 'contracts', 'ev': ev, 'flags': flags, 'gaps': gaps,
                    **({'base': {'a': r['orig'], 't': 'original contract'}, 'now': {'a': now, 't': 'contract with change orders so far', 'open': True}} if r['orig'] else {}),
                    'vendor': r['vid'] if not r['public'] else None, 'vn': r['vn']})
    return out, absorbed


# ---------- 3. Half-cent sales tax projects with a programmed schedule ----------
def surtax_projects():
    from tourism_page import load, surtax_id
    from opendata import schedule_by_project
    P = load()['infra_surtax']['projects']
    sb = schedule_by_project()
    out = []
    for i, p in enumerate(P):
        sx = sb.get(i)
        if not sx:
            continue
        ev = []
        for x in sx:
            for fy, amt in sorted(x['fy_amounts'].items()):
                ev.append({'d': f'FY{fy}', 'k': 'budget', 'a': amt, 't': f"Programmed in the county's sales tax schedule: {x['schedule_name']} ({(x['schedule_status'] or 'status not given').replace('_', ' ')})", 'u': x['source_url']})
        ms = p.get('gis_last_edited_epoch_ms')
        when = datetime.fromtimestamp(ms / 1000, timezone.utc).strftime('%Y-%m-%d') if ms else None
        pct = p.get('pct_complete')
        stt = {'completed': 'complete', 'in_progress': 'construction', 'not_started': 'budgeted'}.get(p['status'], 'unknown')
        ev.append({'d': when, 'k': 'complete' if stt == 'complete' else 'milestone',
                   't': f"County project map: {p['status'].replace('_', ' ')}{f', {pct}% complete' if pct is not None else ''}", 'u': p.get('source_url')})
        flags = []
        fys = [int(fy) for x in sx for fy in x['fy_amounts']]
        last_fy = max(fys) if fys else None
        removed = all('removed' in (x['schedule_status'] or '') for x in sx)
        if removed:
            flags.append({'r': 'removed', 'sev': 'info', 'note': 'Struck through on the schedule.'})
        elif stt != 'complete' and last_fy and last_fy < TODAY_FY:
            yrs = TODAY_FY - 1 - last_fy  # whole fiscal years since the last programmed year ended
            flags.append({'r': 'late', 'sev': 'high' if yrs >= 3 else 'warn',
                          'note': f"Programmed for FY{last_fy}; the county map shows it {p['status'].replace('_', ' ')}{f' at {pct}%' if pct is not None else ''}."})
        prog = sum(x['programmed_total'] or 0 for x in sx)
        out.append({'id': 'st-' + surtax_id(p), 'n': p['name'], 'gk': GOVK.get(p['government'], 'county'), 'g': p['government'],
                    'agency': f"{p['government']} (half-cent infrastructure sales tax)", 'where': p.get('location'), 'what': (p.get('description') or '')[:300],
                    'funding': 'Half-cent infrastructure sales tax', 'status': 'removed' if removed else stt, 'src': 'surtax', 'ev': ev, 'flags': flags, 'gaps': [],
                    'base': {'a': prog, 't': 'programmed in the schedule'}, 'surtax': surtax_id(p), 'pct': pct})
    return out


def _finish(p, responses):
    for x in p['ev']:
        x['s'] = x.get('s') or sort_key(x.get('d'), x.get('k'))
    p['ev'].sort(key=lambda x: x['s'])
    # growth on the project's own baseline (reviewed projects)
    b, n = (p.get('base') or {}).get('a'), (p.get('now') or {}).get('a')
    if b and n and p['src'] == 'reviewed':
        pct = (n - b) / b * 100
        p['growth'] = round(pct, 1)
        if pct > 10 and not any(f['r'] == 'growth' for f in p['flags']):
            p['flags'].append({'r': 'growth', 'sev': 'high' if pct > 25 else 'warn',
                               'note': f"{money(n)} ({(p['now'].get('t') or 'latest figure')}) is {pct:.0f}% above {money(b)} ({p['base'].get('t') or 'first figure'})."})
    elif b and n:
        p['growth'] = round((n - b) / b * 100, 1)
    if p.get('late_days', 0) > 90:
        p['flags'].append({'r': 'late', 'sev': 'high' if p['late_days'] > 365 else 'warn', 'note': f"Reported about {p['late_days']} days behind schedule."})
    # budget vs actual on any 'spent' event that carries its budget
    for x in p['ev']:
        if x['k'] == 'spent' and x.get('budget') and (x.get('a') or 0) < 0.5 * x['budget'] and not any(f['r'] == 'budget' and x['d'] in f['note'] for f in p['flags']):
            p['flags'].append({'r': 'budget', 'sev': 'warn', 'note': f"{x['d']}: spent {money(x.get('a') or 0)} of a {money(x['budget'])} budget ({(x.get('a') or 0) / x['budget']:.0%})."})
    assert all(f['r'] in RULE_IDS for f in p['flags']), p['id']
    p['flags'].sort(key=lambda f: SEV_ORDER[f['sev']])
    p['sev'] = p['flags'][0]['sev'] if p['flags'] else None
    r = responses.get(p['id']) or {}
    p['reply'] = {'status': r.get('status', 'not_sent'), 'sent': r.get('sent'), 'date': r.get('date'), 'text': r.get('text'), 'u': r.get('url')}
    dated = [x['s'] for x in p['ev'] if x['s'] != '9999']
    p['first'], p['last'] = (min(dated), max(dated)) if dated else (None, None)
    p['money'] = (p.get('total') or {}).get('a') or n or b or max([x.get('a') or 0 for x in p['ev'] if x['k'] in ('award', 'budget', 'approval', 'spent', 'complete')] or [0])
    p.pop('cos', None)
    return p


def build():
    rp = os.path.join(DATA, 'projects', 'responses.json')
    responses = json.load(open(rp)).get('responses', {}) if os.path.exists(rp) else {}
    cur = curated()
    absorb = [(p['id'], tuple(c)) for p in cur for c in p.get('cos', [])]
    cps, absorbed = contract_projects(absorb)
    for p in cur:  # change orders filed under a reviewed project join its timeline
        for item in absorbed.get(p['id'], []):
            have = {(x.get('d'), x.get('a')) for x in p['ev']}
            p['ev'] += [x for x in item['ev'] if x['k'] in ('change', 'vote') and (x.get('d'), x.get('a')) not in have]
            p['flags'] += [f for f in item['flags'] if f['r'] == 'approval']
    projects = [_finish(p, responses) for p in cur + cps + surtax_projects()]
    try:  # link a company only when it has its own page
        import vendor_pages
        pages = set(vendor_pages.build())
    except Exception:
        pages = set()
    for p in projects:
        if p.get('vendor') not in pages:
            p['vendor'] = None
        for x in p['ev']:
            if x.get('vid') not in pages:
                x.pop('vid', None)
    ids = [p['id'] for p in projects]
    assert len(ids) == len(set(ids)), 'duplicate project ids'
    stats = {'projects': len(projects), 'flagged': sum(1 for p in projects if p['flags']), 'flags': sum(len(p['flags']) for p in projects),
             'gaps': sum(len(p['gaps']) for p in projects), 'replied': sum(1 for p in projects if p['reply']['status'] == 'replied'),
             'sent': sum(1 for p in projects if p['reply']['status'] in ('sent', 'replied')), 'money': sum(p['money'] or 0 for p in projects)}
    return {'about': 'BayCounty.me Accountability console: public projects from first budget to close-out, with timeline events, flags from published rules, records still missing, and each agency\'s reply. A flag is a question for the agency, not a finding of wrongdoing.',
            'rules': RULES, 'stats': stats, 'projects': projects}


def accountability_page(out_dir):
    D = build()
    json.dump(D, open(os.path.join(out_dir, 'data', 'accountability.json'), 'w'), separators=(',', ':'))
    open(os.path.join(out_dir, 'assets', 'accountability.js'), 'w').write(open(os.path.join(HERE, 'accountability.js')).read())
    open(os.path.join(out_dir, 'assets', 'accountability.css'), 'w').write(open(os.path.join(HERE, 'accountability.css')).read())
    S = D['stats']
    govs = sorted({p['g'] for p in D['projects']}, key=lambda g: (g != 'Bay County', g))
    rules = ''.join(f'''<details class="acct-rule" id="rule-{r["id"]}"><summary><b>{e(r["title"])}</b></summary>
      <dl><dt>When it's raised</dt><dd>{e(r["when"])}</dd><dt>What it means</dt><dd>{e(r["means"])}</dd><dt>What it doesn't mean</dt><dd>{e(r["not"])}</dd></dl></details>''' for r in RULES)
    ORDER = ['county', 'schools', 'pc', 'pcb', 'lh', 'cw', 'sp', 'parker', 'mb']
    gk = sorted({p['gk'] for p in D['projects'] if p.get('gk') in ORDER}, key=ORDER.index)
    ropts = ''.join(f'<option value="{r["id"]}">{e(r["title"])}</option>' for r in RULES)
    return f'''<div class="page tax acct">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Public Money · Accountability</span><h1>Accountability console</h1>
    <p class="lede">Public projects followed from the first budget to the day they close: what was promised, what was approved, every change order and payment we can find, and what it cost in the end. Where the record raises a question, it's flagged by a published rule and sent to the agency for an answer.</p></div></header>
  {city_bar(gk, legacy='g')}
  <div class="acct-stats" role="list">
    <div role="listitem"><b id="acsN">{S["projects"]:,}</b><span id="acsNl">projects tracked</span></div>
    <div role="listitem"><b id="acsM">{money(S["money"])}</b><span>in those projects</span></div>
    <div role="listitem"><b id="acsF">{S["flagged"]:,}</b><span>with a question</span></div>
    <div role="listitem"><b id="acsG">{S["gaps"]:,}</b><span>records still missing</span></div>
    <div role="listitem"><b id="acsR">{S["replied"]:,}</b><span>agency replies</span></div>
  </div>
  <section class="explain"><div class="ex-txt"><span class="eyebrow">How it works</span><h2>Four steps for every project</h2>
    <ol class="ex-steps">
      <li><b>One timeline.</b> Budgets, approvals, contracts, change orders, votes and payments from the site's records are put in order for each project, each with its source.</li>
      <li><b>Promised vs. delivered.</b> The first firm figure is compared with the latest, and the planned finish with the real one.</li>
      <li><b>Flags follow rules.</b> A flag is raised only by one of the <a href="#rules">published rules</a> below, the same way for every government. A flag is a question, not an accusation.</li>
      <li><b>Agencies get to answer.</b> Flags are sent to the agency, and its reply is posted beside them. Records we're missing become <a href="#missing">ready-to-send requests</a>.</li>
    </ol></div></section>
  <section class="tx-sec" id="list"><div class="sec-hd"><h2>Projects</h2><span class="muted" id="acCount" aria-live="polite"></span></div>
    <div class="filters-row acct-filters">
      {scope('<select id="acY" aria-label="Year of activity"><option value="">All years</option></select>', 'Year')}
      <input id="acQ" type="search" placeholder="Search project, company or place" aria-label="Search projects">
      <select id="acG" aria-label="Government" data-city-link hidden><option value="">All governments</option>{''.join(f'<option>{e(g)}</option>' for g in govs)}</select>
      <select id="acF" aria-label="Flag"><option value="">Any flag or none</option><option value="any">Any flag</option>{ropts}</select>
      <select id="acS" aria-label="Source"><option value="">All projects</option><option value="reviewed">Reviewed project histories</option><option value="contracts">Contracts with change orders</option><option value="surtax">Sales tax projects</option></select>
      <select id="acO" aria-label="Sort"><option value="flags">Most questions first</option><option value="money">Biggest first</option><option value="new">Latest activity first</option><option value="growth">Most cost growth</option></select>
      <button type="button" class="pill sm" id="acCsv">Download CSV</button></div>
    <div id="acList" class="acct-list"><p class="muted">Loading projects…</p></div>
    <button type="button" class="pill" id="acMore" hidden>Show more</button></section>
  <section class="tx-sec" id="rules"><div class="sec-hd"><h2>The flag rules</h2></div>
    <p class="small muted">Every flag on this page comes from one of these rules. Each project's flags link back here. If a rule is unfair or applied wrong, <a href="/about#contact">tell us</a>.</p>{rules}</section>
  <section class="tx-sec" id="missing"><div class="sec-hd"><h2>Records still missing</h2><span class="muted" id="acGapCount"></span></div>
    <p class="small muted">The questions above can usually be answered from records the agency already keeps. Each one opens a Florida public records request, written and ready to send.</p>
    <ul class="plain acct-gaps" id="acGaps"></ul></section>
  <section class="tx-sec method" id="reply"><div class="sec-hd"><h2>Right of reply, and how this was built</h2></div>
    <ul class="plain">
      <li>Before a project's flags are treated as final, the agency is sent the flags and the records behind them, and asked to correct or explain. Its answer is posted with the project, in full or linked. Each project shows where that stands.</li>
      <li>Reviewed project histories were put together by hand from the CRA ledger, city capital schedules, resolutions and news reports. Contract timelines come from the contracts and change orders on the <a href="/public-money/contracts">Contracts</a> page, and votes from <a href="/public-money/votes">How They Voted</a>. Sales tax projects come from the county's project schedule and map.</li>
      <li>News reports are marked as news. When an event's figure comes from a note on a source record rather than the document itself, it says so.</li>
      <li>Dollar totals add each project's latest figure once. Grants are included, so totals are more than local tax money alone.</li>
      <li>Download everything as <a href="/data/accountability.json">JSON</a>. Corrections: <a href="/about#contact">send one</a>.</li>
    </ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<link rel="stylesheet" href="/assets/accountability.css">
<script src="/assets/accountability.js" defer></script>'''


if __name__ == '__main__':
    D = build()
    print(json.dumps(D['stats']))
    from collections import Counter
    print(Counter(f['r'] for p in D['projects'] for f in p['flags']))
    print(Counter(p['src'] for p in D['projects']))
