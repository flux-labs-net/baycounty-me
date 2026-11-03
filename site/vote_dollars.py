"""Contract dollars behind each official's votes: how much money the contracts and purchases they voted yes (and no) on
added up to, and the list of votes behind each total.

Every vote comes from the recorded votes the site already publishes (data/votes/votes.json, researched by hand, and
data/votes/minutes_votes.json, read from official minutes). Only votes that approve spending on a contract or purchase
are looked at: category contract, a property purchase, or a consent agenda that a contract record is tied to
(data/votes/contract_votes.json).

The dollar figure has to be the one the vote approved, so the rules are strict and a vote without a clear figure is
left out of the totals (and listed with the reason) rather than guessed:

  * the figure comes from the summary of what was approved (headline, then plain summary, then the motion text) and
    there must be exactly one; a vote that names two or more figures (a bid plus contingency, a range, an old and new
    price) is left out, because the minutes' summary does not say which one passed;
  * when the summary has no figure, a contract record tied to the vote (contract_votes.json) supplies it;
  * the largest figure printed anywhere in the minutes (the 'amount' column on votes) is never used on its own: it is
    often a different item's number, the original contract on a change order, or a grant;
  * left out as not new spending: credits and deductive change orders, savings, refunds, sales, revenue, fees and fee
    schedules, leases, payments on a contract already approved, rates (per hour, per ton), grants accepted, and a
    figure that is a contract's new total rather than the amount added;
  * the same item voted on twice by the same government within 300 days (tabled and brought back, or the CRA board
    and the commission both approving it) with the same figure is counted once, on the latest vote;
  * tabled, withdrawn and unclear motions are left out.

A member's yes total counts only motions that passed; yes votes on motions that failed are totalled separately.
unanimous and no_dissent_recorded votes record everyone present as yes, as the minutes do. Figures marked up_to are
ceilings ("not to exceed"); per_year figures are one year's price. The totals start in 2016 (the site's first year).
"""
import collections, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
for _p in (HERE, os.path.join(DATA, 'entities')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cutoff  # noqa: E402
import ids  # noqa: E402
from govs import gov_of_body  # noqa: E402

_C = {}
REPEAT_DAYS = 300

MONEY = re.compile(r'\$\s?(\d(?:[\d,]|\.(?=\d))*)(\s*(?:million|billion|mil\b|m\b|k\b))?', re.I)
SPEND_CATS = {'contract'}
# not new spending, or the figure is not money going out (checked on the vote's own summary words)
NOT_SPENDING = [
    (re.compile(r'\b(deductive|credit|savings?|saved|refund|rebate|reduc\w*|lower\w*|decreas\w*)\b'), 'credit, reduction or savings, not new spending'),
    (re.compile(r'\b(sell|sells|selling|sale|sold|surplus|auction|trade|trading|trade-in|revenue|franchise|royalt\w*|income)\b'), 'money coming in (a sale, revenue or franchise), not spending'),
    (re.compile(r'\b(lease|leases|leasing|rent|rental)\b'), 'a lease: the money can go either way, so it is not totaled'),
    (re.compile(r'\b(fee schedule|fees and fines|impact fees?|permit fees?|user fees?|application fees?|certificate of public convenience)\b'), 'a fee charged to the public, not spending'),
    (re.compile(r'\b(pay request|payment request|pay application|pay app|invoice|final payment|retainage|progress payment|payments? (?:to|of|for)|paying|pay (?:the|for)|disbursement)\b'), 'a payment on work already approved, counted when it was approved'),
    (re.compile(r'\b(accept\w*|receiv\w*|award\w* (?:to )?the (?:city|county)|grant (?:agreement|award) (?:from|with) )\b.*\bgrant\b|\bgrant\b.*\b(accept\w*|receiv\w*)\b'), 'a grant the government receives, not spending'),
    (re.compile(r'\b(reimburs\w*)\b'), 'a reimbursement: the money can go either way, so it is not totaled'),
    (re.compile(r'\b(died for lack of a second|no second|failed for lack)\b'), 'the motion died without a vote'),
    (re.compile(r'\b(per month|a month|monthly)\b'), 'a monthly price, not a total'),
    (re.compile(r'\b(postpon\w*|tabled|tabling|defer\w*|delay\w*|reschedul\w*)\b'), 'postponed, so nothing was decided in this vote'),
    (re.compile(r'\b(salary|salaries|employment (?:agreement|contract)|compensation|pay raise|raises?)\b'), 'pay for an employee or official, not a contract for goods or services'),
    (re.compile(r'\b(negotiate|negotiations?|start\w* talks|budget cuts?|estimat\w*)\b'), 'talks, a target or an estimate: no price was approved in this vote'),
]
RATE = re.compile(r'\$\s?\d[\d,]*(?:\.\d+)?(?:\s*(?:million|k))?\s*(?:per|/|an|a)\s*(?!year\b|fiscal\b)(?:\d+-\w+\s+)?(?:hour|hr|ton|dry|gallon|1000|square|sq|linear|foot|ft|mile|unit|load|roll|cubic|yard|each|piece|household|customer|meter|lot|parcel|acre|day|week|call|trip|visit|bag|cart|can|container|test|sample|person|student|meal)|\bper (?:hour|ton|unit|gallon|day)\b|\bhourly\b|\brates?\b', re.I)
NEW_TOTAL = re.compile(r'\b(total(?:ing)? (?:of |to )?|bringing|brings|increas\w* (?:\w+ ){0,5}to|rais\w* (?:\w+ ){0,5}to|revised (?:contract )?(?:amount|total|price)|new (?:contract )?(?:amount|total|price)|for a total)\s*\$', re.I)
UP_TO = re.compile(r'\b(not to exceed|not-to-exceed|nte|up to|no more than|maximum of|max(?:imum)?|cap(?:ped)? (?:at|of))\b', re.I)
PER_YEAR = re.compile(r'\b(per year|a year|each year|annually|yearly|per fiscal year|annual (?:cost|price|amount|fee|total|value|contract amount))\b', re.I)
PROPERTY_BUY = re.compile(r'\b(purchas\w*|buy|buying|bought|acquir\w*|acquisition)\b', re.I)
KINDS = [(re.compile(r'change order', re.I), 'change order'), (re.compile(r'task order|work order|work authorization', re.I), 'task order'),
         (re.compile(r'\b(renew\w*|extension|extend\w*)\b', re.I), 'renewal or extension'), (re.compile(r'\b(amend\w*|addendum|supplement\w*)\b', re.I), 'amendment'),
         (re.compile(r'\b(purchas\w*|buy|bought|acquir\w*|piggyback)\b', re.I), 'purchase'),
         (re.compile(r'\b(award\w*|bid|rfp|rfq|itb|low bidder)\b', re.I), 'contract award')]


def money_figures(text):
    """Every dollar figure printed in a piece of text ('$1.2 million' -> 1200000.0), in order."""
    out = []
    for m in MONEY.finditer(text or ''):
        s = m.group(1).rstrip('.,')
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:\.\d{2})?', s):  # "$69.497.00": dots typed for commas
            s = s.replace('.', '', s.count('.') - (1 if re.search(r'\.\d{2}$', s) else 0))
        try:
            x = float(s.replace(',', ''))
        except ValueError:
            continue
        u = (m.group(2) or '').strip().lower()
        x *= {'million': 1e6, 'mil': 1e6, 'm': 1e6, 'billion': 1e9, 'k': 1e3}.get(u, 1)
        out.append(round(x, 2))
    return out


def _d(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def _kind(text, cat):
    if cat == 'property':
        return 'property purchase'
    return next((k for rx, k in KINDS if rx.search(text)), 'contract or agreement')


def _words(text):
    stop = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'board', 'commission', 'council', 'city', 'county', 'approved', 'approve',
            'awarded', 'award', 'contract', 'agreement', 'project', 'services', 'inc', 'llc', 'phase', 'bid', 'motion', 'item', 'consent'}
    return {w for w in re.findall(r'[a-z][a-z0-9]{3,}', (text or '').lower()) if w not in stop}


def _load():
    """Every vote with an id, in the same order as the votes dataset: hand-researched first, then read from minutes."""
    vj = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))
    names = {b['id']: re.sub(r'\bCity City\b', 'City', b['name']) for b in vj['bodies']}
    vids = ids.vote_ids(vj['votes'])
    mp = os.path.join(DATA, 'votes', 'minutes_votes.json')
    mv = (json.load(open(mp)) if os.path.exists(mp) else {}).get('votes') or []
    return names, [(v, vids[i], 'researched') for i, v in enumerate(vj['votes'])] + [(v, v.get('vote_id'), 'minutes') for v in mv]


def _links():
    """vote id -> contract records tied to it (data/votes/contract_votes.json)."""
    p = os.path.join(DATA, 'votes', 'contract_votes.json')
    out = collections.defaultdict(list)
    for l in (json.load(open(p)) if os.path.exists(p) else {}).get('links') or []:
        if l.get('record_amount'):
            out[l['vote_id']].append(l)
    return out


def _classify(v, linked, researched=False):
    """(amount, amount_from, kind, up_to, per_year, reason) for one vote; amount None with a reason when not counted."""
    cat = (v.get('category') or '').lower()
    head = ' '.join(x for x in (v.get('headline'), v.get('plain_summary')) if x)
    item = v.get('item') or ''
    text = f'{item} {head} {v.get("summary") or ""}'
    kind = _kind(f'{item} {head}', cat)
    consent = bool(v.get('consent')) or cat == 'consent agenda' or 'consent agenda' in item.lower()
    if consent:
        if not linked:
            return None, None, 'consent agenda', False, False, 'consent agenda: many items in one vote, and the minutes do not give each item\'s cost'
        recs = {l['record_id']: l for l in linked}
        return round(sum(l['record_amount'] for l in recs.values()), 2), 'contract record', 'consent agenda item', False, False, None
    low = head.lower() + ' ' + item.lower() + ' ' + (v.get('summary') or '').lower()
    for rx, why in NOT_SPENDING:
        if rx.search(low):
            return None, None, kind, False, False, why
    # the figure: the summary of what was approved, then the motion text, then a contract record tied to the vote
    figs, src = [], None
    fields = (('headline', 'vote summary'), ('plain_summary', 'vote summary'))
    if not researched:  # minutes votes: summary is the motion as made; on researched votes it is background
        fields += (('summary', 'motion text'),)
    for field, label in fields:
        f = sorted(set(money_figures(v.get(field))))
        if f:
            figs, src = f, label
            seg = v.get(field)
            break
    if len(figs) > 1:
        return None, None, kind, False, False, 'several dollar figures in the vote (for example a bid and its contingency), so which one passed is not clear'
    if figs:
        if RATE.search(seg):
            return None, None, kind, False, False, 'a rate (per hour, per ton and so on), not a total'
        if NEW_TOTAL.search(seg):
            return None, None, kind, False, False, 'the figure is the new total of an earlier contract, not the amount added'
        if not figs[0]:
            return None, None, kind, False, False, 'no dollar amount in the record of the vote'
        return figs[0], src, kind, bool(UP_TO.search(seg)), bool(PER_YEAR.search(seg)), None
    if linked:
        recs = {l['record_id']: l for l in linked}
        return round(sum(l['record_amount'] for l in recs.values()), 2), 'contract record', kind, False, False, None
    if v.get('amount'):
        return None, None, kind, False, False, 'a dollar figure is printed in the minutes but not tied to this approval in the summary'
    return None, None, kind, False, False, 'no dollar amount in the record of the vote'


def items():
    """One row per vote on a contract, purchase or consent agenda since 2016: the figure it approved and whether it is
    counted in the totals (counted false names the reason)."""
    if 'items' in _C:
        return _C['items']
    names, votes = _load()
    links = _links()
    out = []
    for v, vid, st in votes:
        cat = (v.get('category') or '').lower()
        d = str(v.get('date') or '')[:10]
        if not d or int(d[:4]) < cutoff.FIRST_YEAR or not vid:
            continue
        item = v.get('item') or ''
        consent = bool(v.get('consent')) or cat == 'consent agenda' or 'consent agenda' in item.lower()
        head = ' '.join(x for x in (v.get('headline'), v.get('plain_summary')) if x)
        if not (cat in SPEND_CATS or consent or (cat == 'property' and PROPERTY_BUY.search(head) and not NOT_SPENDING[1][0].search(head.lower()))):
            continue
        linked = links.get(vid) or []
        amount, src, kind, up_to, per_year, why = _classify(v, linked, st == 'researched')
        outcome = (v.get('outcome') or '').lower()
        if why is None and outcome not in ('passed', 'failed'):
            amount, src, why = None, None, f'motion {outcome or "outcome not recorded"}, so nothing was decided'
        out.append({'vote_id': vid, 'gov_id': gov_of_body(v['body']), 'body': v['body'], 'board': names.get(v['body']), 'date': d,
                    'agenda_item': item or None, 'headline': v.get('headline') or item, 'category': v.get('category'), 'kind': kind,
                    'amount': amount, 'amount_from': src, 'up_to': up_to, 'per_year': per_year, 'counted': why is None, 'not_counted_reason': why,
                    'same_item_as': None, 'outcome': v.get('outcome'), 'tally': v.get('tally'), 'vote_method': v.get('vote_method'),
                    'verified': v.get('verified') or ('hand-checked' if st == 'researched' else None),
                    'contract_record_ids': '; '.join(sorted({l['record_id'] for l in linked})) or None,
                    'contract_vendor_ids': '; '.join(sorted({'vendor:' + x for l in linked for x in l.get('vendor_ids') or []})) or None,
                    'source_type': st, 'source_title': v.get('source_title'), 'source_url': v.get('source_url'), 'source_page': v.get('source_page'),
                    '_by': v.get('by_member') or {}, '_words': _words(f'{item} {head}')})
    _dedupe(out)
    _C['items'] = out
    return out


def _dedupe(rows):
    """The same item voted on twice by one government (tabled and brought back, CRA board and commission, a vote read
    from minutes that repeats a researched one): same figure to the cent, within REPEAT_DAYS, sharing two words of the
    item. Only the latest vote is counted; the earlier ones point at it in same_item_as."""
    by = collections.defaultdict(list)
    for r in rows:
        if r['counted']:
            by[(r['gov_id'], r['amount'])].append(r)
    for grp in by.values():
        grp.sort(key=lambda r: (r['date'], r['outcome'] == 'passed', r['source_type'] == 'researched'))
        for i, r in enumerate(grp):
            later = [x for x in grp[i + 1:] if x['counted'] and (_d(x['date']) - _d(r['date'])).days <= REPEAT_DAYS
                     and (len(r['_words'] & x['_words']) >= 2 or (r['contract_record_ids'] and r['contract_record_ids'] == x['contract_record_ids']))]
            if later:
                keep = later[-1]
                r['counted'], r['same_item_as'] = False, keep['vote_id']
                r['not_counted_reason'] = f'the same item ({_money(r["amount"])}) was voted on again on {keep["date"]}; counted once, on that vote'


def _money(x):
    return f'${x:,.0f}' if x is not None else ''


def member_rows():
    """One row per member per counted vote: how they voted on that figure."""
    if 'members' in _C:
        return _C['members']
    out = []
    for r in items():
        if not r['counted']:
            continue
        for name, how in r['_by'].items():
            out.append({'vote_id': r['vote_id'], 'person_id': ids.person_id(name), 'member': name, 'vote': how, 'gov_id': r['gov_id'],
                        'board': r['board'], 'date': r['date'], 'headline': r['headline'], 'kind': r['kind'], 'amount': r['amount'],
                        'up_to': r['up_to'], 'per_year': r['per_year'], 'outcome': r['outcome'], 'tally': r['tally'],
                        'vote_method': r['vote_method'], 'source_url': r['source_url'], 'source_page': r['source_page']})
    _C['members'] = out
    return out


def totals():
    """One row per official per government: the dollars in counted contract votes they voted yes on (passed and failed
    separately) and no on, the vote counts behind each, and how many of their contract votes are not in the totals."""
    if 'totals' in _C:
        return _C['totals']
    acc = {}
    for r in items():
        for name, how in r['_by'].items():
            pid = ids.person_id(name)
            k = (pid or name, r['gov_id'])
            a = acc.setdefault(k, {'person_id': pid, 'member': name, 'gov_id': r['gov_id'], 'yes_total': 0.0, 'yes_votes': 0, 'yes_failed_total': 0.0,
                                   'yes_failed_votes': 0, 'no_total': 0.0, 'no_votes': 0, 'absent_or_abstained_votes': 0, 'first_date': None, 'last_date': None,
                                   'contract_votes': 0, 'not_counted_consent': 0, 'not_counted_no_amount': 0, 'not_counted_unclear': 0,
                                   'not_counted_not_spending': 0, 'not_counted_repeat': 0})
            a['contract_votes'] += 1
            if not r['counted']:
                why = r['not_counted_reason'] or ''
                key = ('not_counted_consent' if why.startswith('consent') else 'not_counted_repeat' if r['same_item_as'] else
                       'not_counted_no_amount' if why.startswith(('no dollar', 'a dollar figure')) else
                       'not_counted_unclear' if why.startswith(('several', 'motion')) else 'not_counted_not_spending')
                a[key] += 1
                continue
            a['first_date'] = min(filter(None, [a['first_date'], r['date']]))
            a['last_date'] = max(filter(None, [a['last_date'], r['date']]))
            if how == 'yes' and r['outcome'] == 'passed':
                a['yes_total'] += r['amount']; a['yes_votes'] += 1
            elif how == 'yes':
                a['yes_failed_total'] += r['amount']; a['yes_failed_votes'] += 1
            elif how == 'no':
                a['no_total'] += r['amount']; a['no_votes'] += 1
            else:
                a['absent_or_abstained_votes'] += 1
    out = []
    for a in acc.values():
        for f in ('yes_total', 'yes_failed_total', 'no_total'):
            a[f] = round(a[f], 2)
        out.append(a)
    out.sort(key=lambda a: (a['gov_id'] or '', -a['yes_total']))
    _C['totals'] = out
    return out


def item_rows():
    """items() without the private working fields, for the dataset."""
    return [{k: v for k, v in r.items() if not k.startswith('_')} for r in items()]


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('who', nargs='?')
    a = ap.parse_args()
    rs = items()
    c = collections.Counter(r['not_counted_reason'] or 'counted' for r in rs)
    for k, n in c.most_common():
        print(f'{n:6} {k[:110]}')
    if a.who:
        for t in totals():
            if a.who.lower() in t['member'].lower():
                print(json.dumps(t, indent=1))


def _counted_items():
    return item_rows()


DATASETS = [
    ('contract-vote-dollars', 'Contract votes and their dollar figures',
     "Every recorded vote since 2016 on a contract, purchase, change order or task order, or on a consent agenda, with the dollar figure it approved and whether "
     "that figure is counted in the officials' contract-dollar totals. counted false gives not_counted_reason: no figure in the record of the vote, "
     "several figures (which one passed is not clear), a consent agenda (many items in one vote), not new spending (a credit, sale, lease, fee, payment "
     "on work already approved, grant received, rate or new total), or the same item voted on again (same_item_as is the vote that is counted). "
     "amount_from says where the figure came from: the vote summary, the motion text, or a contract record tied to the vote (contract_record_ids). "
     "up_to marks a not-to-exceed ceiling; per_year marks one year's price. Rules: site/vote_dollars.py.", _counted_items),
    ('member-contract-dollars', 'Contract dollars by member vote',
     'One row per board member per counted contract vote (counted true in contract-vote-dollars): how the member voted (yes, no, absent, abstain) on that '
     'dollar figure. Sum amount where vote is yes and outcome is passed for the dollars a member voted to approve.', member_rows),
    ('contract-dollar-totals', 'Contract dollars each official voted on',
     "One row per official per government: the dollars in counted contract votes they voted yes on that passed (yes_total, yes_votes), voted yes on that "
     "failed (yes_failed_total), and voted no on (no_total, no_votes), the dates of the first and last counted vote, every contract vote they took part "
     "in (contract_votes), and how many of those are not in the totals and why (not_counted_*). Only votes with one clear dollar figure are counted, so "
     "the totals are a floor, not everything a board spent.", totals),
]
