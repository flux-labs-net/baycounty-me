"""How complete the contract list is: every contract vote in the minutes checked against data/contracts/contracts.json.

The contract list (data/contracts/contracts.json) is read by hand from agendas, packets and minutes. It holds awards of
about $250,000 and up for Bay County, Panama City and Panama City Beach and about $100,000 and up for the smaller
cities (its `review` block gives each government's threshold and the last meeting date read). Anything newer than
that date, or smaller than the threshold, is not in it. So a low count on a government page can mean "the list has
not caught up", not "the city approved little".

This module makes that visible. Every passed contract vote read from the minutes since the list starts
(October 2022) gets one row, with a status:

  in_list          the vote is tied to a contract, change order or emergency purchase in the list
                   (data/votes/contract_votes.json), or within 45 days of one gives the same amount or names the
                   same company (with no figure, or one within 3%)
  under_threshold  the vote's one clear dollar figure is below the government's list threshold
  after_review     the meeting is after the last date the list was read for this government
  no_amount        the minutes give no single clear dollar figure, so we can't tell if it belongs in the list
  missing          a figure at or above the threshold, before the review date, and not in the list: a gap to fix

A vote looked at by hand is recorded in contracts.json `minutes_check` (vote id -> status and why), for example a
figure that is really a budget amendment, or an award whose minutes don't name the seller (still missing, with the
reason). A vote marked not_an_award there is left out.

Consent agendas are left out (one vote, many items). Votes that approve no spending (mutual aid, interlocal
agreements, terminations, rejected bids, rescinded awards, a decision not to renew) are left out too.

Published as dataset `contract-minutes-check`; the government pages read it to say how many contract votes in the
picked year aren't in the list yet, and list them with their source.
"""
import json, os, re

import sys

import vote_dollars as VD
from city_filter import gkey

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
START = '2022-10-01'   # the contract list starts with FY2023
SAME_DAYS = 45
for _p in (os.path.join(DATA, 'campaign'), os.path.join(DATA, 'entities')):
    if _p not in sys.path:
        sys.path.append(_p)

# votes on a contract that approve no new spending
NOT_AN_APPROVAL = re.compile(
    r'\b(mutual aid|interlocal|multi-?jurisdiction\w*|memorandum of (?:understanding|agreement)|terminat\w*|reject\w*|rescind\w*|'
    r'not to renew|not renew|declin\w*|cancel\w*|withdr\w*|died|tabled?|postpon\w*|defer\w*|surplus|development agreement|'
    r'franchise|lease|right[- ]of[- ]way|easement|bond for|accept(?:ed|ing)? the bond|certificate of public convenience|'
    r'joint (?:participation|use) agreement|license agreement|negotiat\w*|rebid|re-bid|rebate|performance agreement|no[- ]cost|'
    r'conceptual design)\b', re.I)

_C = {}


def _review():
    d = json.load(open(os.path.join(DATA, 'contracts', 'contracts.json')))
    rv = {}
    for name, r in (d.get('review') or {}).items():
        k = gkey(name)
        if k:
            rv[k] = {'through': r.get('through'), 'threshold': r.get('threshold'), 'note': r.get('note')}
    return d, rv


def _checked(d):
    """Votes looked at by hand (contracts.json minutes_check): vote id -> {status, why, amount?}."""
    return d.get('minutes_check') or {}


def _register(d):
    """gov key -> [(date, amount, record id, vendor name phrases)] for every contract, change order and emergency
    purchase in the list."""
    import build_contract_votes as BCV
    import ids
    out, ph = {}, {}
    for src, rows, amt in (('contract', d['contracts'], 'amount'), ('change_order', d.get('change_orders') or [], 'change_amount'),
                           ('emergency', d.get('emergency_purchases') or [], 'amount')):
        for i, r in enumerate(rows):
            k = gkey(r.get('government'))
            if k:
                vids = ids.vendor_ids(r.get('vendor') or '')
                names = set()
                for v in vids:
                    if v not in ph:
                        try:
                            ph[v] = BCV.alias_phrases(v)
                        except Exception:
                            ph[v] = set()
                    names |= ph[v]
                out.setdefault(k, []).append((VD._d(r.get('date')), r.get(amt), f'{src}:{i}', names))
    return out


def _same(rec, vd, amt, text):
    """A list record and a vote are the same award: within 45 days, and the same amount or the vote names the vendor."""
    dd, a, _, names = rec
    if not dd or abs((dd - vd).days) > SAME_DAYS:
        return False
    if amt and a and abs(a - amt) < 1:
        return True
    return bool(names) and any(' ' + n + ' ' in text for n in names) and (not amt or not a or abs(a - amt) <= 0.03 * a)


def rows():
    """One row per passed contract vote since October 2022 for the governments the contract list covers."""
    if 'rows' in _C:
        return _C['rows']
    d, rv = _review()
    reg = _register(d)
    hand = _checked(d)
    out = []
    for r in VD.items():
        if r['source_type'] != 'minutes' or (r['date'] or '') < START or r['gov_id'] not in rv:
            continue
        cat = (r['category'] or '').lower()
        if cat != 'contract' or (r['outcome'] or '').lower() != 'passed':
            continue
        head = r['headline'] or ''
        if NOT_AN_APPROVAL.search(f"{head} {r['agenda_item'] or ''}"):
            continue
        g = rv[r['gov_id']]
        th, through = g['threshold'], g['through']
        amt = r['amount'] if r['counted'] or r['same_item_as'] else None
        ids_ = r['contract_record_ids']
        if not ids_:
            import build_contract_votes as BCV
            vd, text = VD._d(r['date']), BCV.norm(f"{head} {r['agenda_item'] or ''}")
            ids_ = '; '.join(rec[2] for rec in reg.get(r['gov_id'], []) if _same(rec, vd, amt, text)) or None
        why = None
        if r['vote_id'] in hand:
            h = hand[r['vote_id']]
            st, why, amt = h['status'], h.get('why'), h.get('amount', amt)
        elif ids_:
            st = 'in_list'
        elif amt is not None and th and amt < th:
            st = 'under_threshold'
        elif through and r['date'] > through:
            st = 'after_review'
        elif amt is None:
            st = 'no_amount'
        else:
            st = 'missing'
        if st == 'not_an_award':
            continue
        out.append({'vote_id': r['vote_id'], 'gov_id': r['gov_id'], 'board': r['board'], 'date': r['date'], 'year': int(r['date'][:4]),
                    'headline': head, 'kind': r['kind'], 'amount': amt, 'up_to': r['up_to'] if amt else None,
                    'status': st, 'checked_note': why, 'in_contract_list': st == 'in_list', 'contract_record_ids': ids_,
                    'list_threshold': th, 'list_reviewed_through': through, 'source_title': r['source_title'], 'source_url': r['source_url']})
    out.sort(key=lambda x: (x['gov_id'], x['date'], x['vote_id']))
    _C['rows'] = out
    return out


def summary():
    """gov key -> {threshold, through, note, years: {year: {status: count}}} for the pages."""
    _, rv = _review()
    out = {k: {**v, 'years': {}} for k, v in rv.items()}
    for r in rows():
        y = out[r['gov_id']]['years'].setdefault(str(r['year']), {})
        y[r['status']] = y.get(r['status'], 0) + 1
    return out


DATASETS = [
    ('contract-minutes-check', 'Contract votes checked against the contract list',
     "Every passed contract vote read from the minutes since October 2022 (consent agendas and votes that approve no spending, such as mutual aid, "
     "interlocal agreements, terminations and rejected bids, left out), checked against the contracts dataset. status: in_list (tied to a contract, "
     "change order or emergency purchase there, contract_record_ids), under_threshold (the vote's one clear figure is below list_threshold, the "
     "smallest award the list collects for that government), after_review (the meeting is after list_reviewed_through, the last meeting date read "
     "into the list), no_amount (the minutes give no single clear dollar figure), or missing (at or above the threshold, before the review date, "
     "and not in the list). amount is the vote's one clear figure from contract-vote-dollars. checked_note explains a vote looked at by hand (for example, the minutes don't name the seller). Rules: site/contract_coverage.py.", rows),
]
