"""Contracts page: change orders added up per contract, measured against the original amount.

Each change order on an agenda is one step; what matters to a reader is how far the whole contract grew.
Change orders are grouped by government, company (vendors.resolve) and contract number when the agenda gives
one (PC24-037, ITB 23-25, contract 25-42, Task Order 32), otherwise by the project name.
"""
import re
import html
import vendors as V

e = lambda s: html.escape(str(s if s is not None else ''))
SHORT = {'Bay County BOCC': 'Bay County', 'City of Panama City': 'Panama City', 'City of Panama City Beach': 'Panama City Beach', 'City of Lynn Haven': 'Lynn Haven',
         'City of Callaway': 'Callaway', 'City of Springfield': 'Springfield', 'City of Parker': 'Parker', 'City of Mexico Beach': 'Mexico Beach'}

# Change-order rules that set a growth level needing board approval (from the bidding-rules records on the page)
CO_RULE = {'Bay County': 'change orders that add up to more than 10% of the original, or more than $150,000, need approval at the level that approved the contract',
           'Panama City': 'change orders that add up to more than 10% of the contract price or $100,000, whichever is less, need City Commission approval'}
_TAG = re.compile(r'(PC\d{2}-\d{3}|ITB \d{2}-\d{2}|contract \d{2}-\d{2}|Task Order [\d-]+[A-Z]*|PO \d+)', re.I)
_STRIP = re.compile(r',?\s*\(?(final |deductive |add )?(change orders?|amendment|additional change-order contingency)\b.*$', re.I)
# change orders filed under different wording that belong to the same contract (reviewed by hand)
_SAME = {('City of Panama City', 'cbc', 'cdbg-dr area a-2 subsection a'): 'PC24-006',
         ('City of Lynn Haven', 'tetra-tech', 'hurricane michael fema public assistance consulting'): 'TASK ORDER 1-2018-FRS'}
# the source itself isn't sure which contract the change order belongs to: listed, not ranked
_UNSURE = re.compile(r'may attach to a different|does not say which subsection', re.I)


def money(n):
    if n is None:
        return '—'
    sign, n = ('−' if n < 0 else ''), abs(n)
    return sign + (f'${n/1e6:,.1f}M' if n >= 1e6 else (f'${n/1e3:,.0f}K' if n >= 1e3 else f'${n:,.0f}'))


def co_contracts(d):
    groups = {}
    for x in sorted(d['change_orders'], key=lambda x: x.get('date') or ''):
        vid, vn, vt = V.resolve(x.get('vendor'))
        m = _TAG.search(x.get('project') or '')
        base = _STRIP.sub('', x.get('project') or '').strip()
        g = x['government']
        tag = m.group(1).upper() if m else base.lower()
        tag = _SAME.get((g, vid, tag), tag)
        r = groups.setdefault((g, vid, tag), {'g': SHORT.get(g, g), 'vid': vid, 'vn': vn, 'public': vt == 'public', 'title': base, 'orig': None,
                                              'added': 0.0, 'stated': None, 'cos': [], 'atleast': False, 'unsure': False, 'appr': set()})
        r['orig'] = r['orig'] or x.get('original_amount')
        r['added'] += x.get('change_amount') or 0
        if x.get('new_total'):
            r['stated'] = x['new_total']
        n = (x.get('notes') or '').lower()
        r['atleast'] |= 'change order 1 amount not found' in n
        r['unsure'] |= bool(_UNSURE.search(n))
        r['appr'].add('confirmed' if 'approval confirmed' in n else 'not confirmed' if 'action not confirmed' in n else 'agenda')
        r['cos'].append({'d': x.get('date'), 'a': x.get('change_amount'), 'p': x.get('project'), 'u': x.get('source_url'), 'why': x.get('reason')})
    out = []
    for r in groups.values():
        # an agenda's stated new contract total nets every change order to date, including any not in this list
        if r['stated'] and r['orig']:
            r['added'] = r['stated'] - r['orig']
            r['atleast'] = False
        r['pct'] = round(r['added'] / r['orig'] * 100, 1) if r['orig'] else None
        r['rule'] = r['g'] in CO_RULE
        r['appr'] = 'confirmed' if r['appr'] == {'confirmed'} else 'not confirmed' if 'not confirmed' in r['appr'] else None
        out.append(r)
    return out


def _row(r, mx):
    neg = r['pct'] < 0
    sign = '−' if neg else '+'
    note = []
    if r['atleast']:
        note.append("an earlier change order's amount wasn't found, so the contract grew at least this much")
    if r['appr'] == 'confirmed':
        note.append('approval confirmed in the minutes')
    elif r['appr'] == 'not confirmed':
        note.append('approval not found in the minutes')
    rule = f"{e(r['g'])}'s rule: {e(CO_RULE[r['g']])}." if r['rule'] else f"No change-order rule was found for {e(r['g'])}."
    cos = ''.join(f'<li>{e(c["d"])}: <b>{money(c["a"])}</b>{(" · " + e(c["why"])) if c.get("why") else ""}'
                  f'{(" <a class=\"src\" href=\"" + e(c["u"]) + "\" target=\"_blank\" rel=\"noopener\">Source</a>") if c.get("u") else ""}</li>' for c in r['cos'])
    tick = f'<i class="cg-tick" style="left:{10 / mx * 100:.2f}%"></i>' if r['rule'] else ''
    flag = ' <span class="badge warn">over 10%</span>' if r['pct'] > 10 else ''
    n = len(r['cos'])
    return (f'<details class="cg{" neg" if neg else ""}"><summary>'
            f'<span class="cg-n"><b>{e(r["vn"])}</b> <em>{e(r["g"])} · {e(r["title"])}</em></span>'
            f'<span class="cg-track">{tick}<span class="cg-bar" style="width:{max(.6, abs(r["pct"]) / mx * 100):.2f}%"></span></span>'
            f'<span class="cg-v"><b>{sign}{abs(r["pct"]):.0f}%{"+" if r["atleast"] else ""}</b>{flag}<em>{sign}{money(abs(r["added"])).lstrip(chr(0x2212))} on {money(r["orig"])}</em></span></summary>'
            f'<div class="cg-d small"><p>{n} change order{"s" if n > 1 else ""} in this list{"; " + "; ".join(note) if note else ""}. {rule} '
            f'<button type="button" class="vbtn" data-v="{e(r["vid"])}">Everything on {e(r["vn"])}</button></p><ul class="plain">{cos}</ul></div></details>')


def growth_section(d, all_table):
    G = co_contracts(d)
    ranked = sorted([r for r in G if r['pct'] is not None and not r['unsure'] and not r['public']], key=lambda r: -r['pct'])
    unknown = sorted([r for r in G if r not in ranked], key=lambda r: -abs(r['added']))
    mx = max(100.0, max(abs(r['pct']) for r in ranked))
    over = [r for r in ranked if r['pct'] > 10]
    why = lambda r: ("Another government's agreement, not a contractor" if r['public'] else "The agenda doesn't say which contract it changed" if r['unsure']
                     else 'Original amount not in the agendas reviewed')
    name = lambda r: (f'<button type="button" class="vbtn" data-v="{e(r["vid"])}">{e(r["vn"])}</button>' if r['vid'] != 'unnamed' else '<span class="muted">Contractor not named</span>')
    unk = ''.join(f'<tr><td>{e(r["g"])}</td><td class="wrap">{name(r)}<br><span class="small muted">{e(r["title"])}</span></td><td class="num">{len(r["cos"])}</td>'
                  f'<td class="num">{money(r["added"])}</td><td class="small muted wrap">{why(r)}</td></tr>' for r in unknown)
    govs = ' and '.join(CO_RULE)
    return f'''<section class="tx-sec"><div class="sec-hd"><h2 id="co">How much contracts grew</h2><span class="muted">Each contract's change orders added up, against its original amount</span></div>
    <p class="cg-lede">Of the {len(ranked)} contracts whose original amount is known, <b>{len(over)} grew by more than 10%</b>. The thin line on a bar marks 10%: in {govs}, change orders that add up past it (or past a dollar limit) need the board's approval. These all went to the board, so passing the line means the board was asked to approve the extra cost, not that a rule was broken. Tap a row for each change order, its reason and source.</p>
    <div class="cgs">{''.join(_row(r, mx) for r in ranked)}</div>
    <h3 class="cg-h">Change orders that can't be measured yet <span class="muted">{len(unknown)} contracts · {money(sum(r["added"] for r in unknown))} added</span></h3>
    <div class="tablewrap"><table class="tx-table"><thead><tr><th scope="col">Gov.</th><th scope="col">Contractor and project</th><th scope="col" class="num">Change orders</th><th scope="col" class="num">Added</th><th scope="col">Why</th></tr></thead><tbody>{unk}</tbody></table></div>
    <p class="note">A <a href="/records-request">public records request</a> for the original contract and its change orders would fill these in.</p>
    {all_table}</section>'''
