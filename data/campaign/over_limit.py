"""Gifts over Florida's per-election contribution limit: one contributor (business, PAC or other organization) giving
one candidate more than $1,000 in the same election, as the campaign reported it.

s. 106.08(1)(a), F.S.: $1,000 per election to a county or municipal candidate. The primary and the general are separate
elections, each with its own limit, so for a "primary/general" cycle a gift dated after the primary counts toward
the general. A check written before the primary may be designated for the general; the report doesn't say, so such a
case is still listed and an admin records the explanation when there is one.

Refunds the campaign reported are netted. A case whose gifts went over but whose refunds bring it back to the limit
is kept with resolution "refunded", so the record shows why it is not an open issue.

Individuals are never named, so only organization contributors are checked (records.donations()).
Output: cases(county) -> list of dicts for the private registry.limit_cases table (db/scripts/load_registry.py).
Nothing is public until an admin reviews a case in /admin (migration 0038).
"""
import collections, hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'sunbiz'))

LIMIT = 1000.0
# Florida primary election days (the general follows in November)
PRIMARY_DAY = {'2018': '2018-08-28', '2020': '2020-08-18', '2022': '2022-08-23', '2024': '2024-08-20', '2026': '2026-08-18', '2028': '2028-08-22'}
TYPES = ('business', 'pac', 'committee', 'other')
LEGAL = r'\b(llc|l l c|inc|incorporated|corp|corporation|co|company|pa|p a|ltd|lp|llp|pllc|the|of)\b'


def contributor_key(name):
    s = re.sub(r'[^a-z0-9 ]', ' ', str(name or '').lower().replace('&', ' and '))
    return ' '.join(re.sub(LEGAL, ' ', s).split())


def election_key(label):
    """'2024 primary/general' and '2024 Primary/General (Aug 20 / Nov 5, 2024)' are the same cycle."""
    s = str(label or '')
    y = (re.search(r'\b(19|20)\d\d\b', s) or [None])[0]
    kind = 'municipal' if re.search(r'municipal|super tuesday', s, re.I) else 'primary/general' if re.search(r'primary|general', s, re.I) else 'other'
    return y, kind


def phase(gift_date, year, kind):
    if kind != 'primary/general' or not gift_date or year not in PRIMARY_DAY:
        return ''
    return 'general' if str(gift_date)[:10] > PRIMARY_DAY[year] else 'primary'


def _dedupe_files(gifts):
    """A 2026 candidate who is also an officeholder is in both files: drop the 2026-file copy of an item the
    officeholder file has. Repeats inside one report are kept (they may be the double entry being looked for)."""
    have = collections.Counter((g['candidate'], g['name'].strip().upper(), g.get('amount'), str(g.get('date'))) for g in gifts if g['src'] == 'officeholders')
    out = []
    for g in gifts:
        if g['src'] != 'officeholders':
            k = (g['candidate'], g['name'].strip().upper(), g.get('amount'), str(g.get('date')))
            if have[k]:
                have[k] -= 1
                continue
        out.append(g)
    return out


def cases(county='bay', gifts=None):
    if gifts is None:
        import records
        gifts = records.donations(TYPES) if county == 'bay' else []
    from build_sunbiz import gov_for
    groups = collections.defaultdict(list)
    for g in _dedupe_files(gifts):
        if g.get('amount') is None:
            continue
        y, kind = election_key(g.get('election'))
        ph = phase(g.get('date'), y, kind)
        groups[(g['candidate'], y, kind, ph, contributor_key(g['name']))].append(g)
    out = []
    for (cand, y, kind, ph, ck), items in groups.items():
        pos = [g for g in items if g['amount'] > 0]
        refunds = [g for g in items if g['amount'] < 0]
        gross = round(sum(g['amount'] for g in pos), 2)
        net = round(gross + sum(g['amount'] for g in refunds), 2)
        if len(pos) < 2 or gross <= LIMIT + 0.005:
            continue
        names = collections.Counter(g['name'].strip() for g in pos)
        first = sorted(pos, key=lambda g: str(g.get('date')))[0]
        dates = [str(g.get('date'))[:10] for g in pos if g.get('date')]
        same = collections.Counter((str(g.get('date')), g['amount']) for g in pos)
        out.append({
            'case_id': 'l_' + hashlib.sha1('|'.join([county, cand, y or '', kind, ph, ck]).encode()).hexdigest()[:10],
            'candidate': cand, 'office': first.get('office'), 'government_key': gov_for(first), 'election': first.get('election'),
            'election_year': y, 'election_phase': ph, 'contributor': names.most_common(1)[0][0], 'contributor_type': first.get('type') or '',
            'spellings': sorted(names), 'n_items': len(pos), 'gross_amount': gross, 'refunds': round(gross - net, 2), 'net_amount': net,
            'over_by': round(max(net - LIMIT, 0), 2),
            # the same amount on the same day twice reads like a double entry in the report
            'possible_double_entry': any(n > 1 for n in same.values()),
            'auto_resolution': 'refunded' if net <= LIMIT + 0.005 else None,
            'items': sorted(({'date': str(g.get('date'))[:10] if g.get('date') else None, 'amount': g['amount'], 'kind': g.get('kind') or '',
                              'filed_as': g['name'].strip()} for g in items), key=lambda i: (i['date'] or '', -i['amount'])),
            'first_date': min(dates) if dates else None, 'last_date': max(dates) if dates else None,
            'report_url': first.get('report_url'),
        })
    out.sort(key=lambda c: (-(c['over_by'] or 0), c['candidate']))
    return out


if __name__ == '__main__':
    import json
    cs = cases(sys.argv[1] if len(sys.argv) > 1 else 'bay')
    for c in cs:
        print(json.dumps({k: c[k] for k in ('candidate', 'election', 'election_phase', 'contributor', 'gross_amount', 'net_amount', 'over_by', 'possible_double_entry', 'auto_resolution')}))
    print(len(cs), 'cases')
