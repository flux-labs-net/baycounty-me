"""Link contracts (and change orders / emergency purchases) to the recorded votes that approved them.

Writes data/votes/contract_votes.json and data/votes/contract_votes_review.json. Run by data/build.py.
A vote is linked to a contract record when all of these hold:
  * same government (vote body -> gov_id; a CRA board counts as its city),
  * vote date within 45 days of the record's agenda date (either side),
  * and the vote agrees with the record in at least two ways, from:
      vendor_name  - the vote text names the vendor by one of its aliases (whole words, at least 6 letters),
      item_number  - the vote text and the record share a bid/contract/RFQ number such as "PC24-005" or "24-18",
      agenda_item  - the vote text and the record's description share at least 3 distinctive words (not the vendor's name),
      amount       - the vote amount equals the record amount to the dollar (and the vote names no other vendor);
    or the vendor is named in a vote on the same day, both amounts are given and within 3%, and no other vendor is named;
    or the number matches on the same day.
When several votes qualify, the one with the most kinds of agreement (then the closest date) is kept. Everything weaker
(amount only, description only, vendor named but amounts differ) goes to the review file. A link shows that the minutes record a vote on the item; it does not show why anyone voted as they did.
"""
import collections, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..')
sys.path.insert(0, os.path.join(DATA, 'entities'))
import ids  # noqa: E402
import records  # noqa: E402

BODY_GOV = [('bay-', 'county'), ('pcb-', 'pcb'), ('pc-', 'pc'), ('lh-', 'lh'), ('cw-', 'cw'), ('sp-', 'sp'), ('parker-', 'parker'), ('mb-', 'mb'), ('bds-', 'schools')]
NUM = re.compile(r'\b(?:(?:ITB|RFP|RFQ|IFB|Bid|Contract|PC)[\s#-]*)?([A-Z]{0,3}\d{2}[-.]\d{2,3}(?:[-.]\d{2,3})?)\b', re.I)
GENERIC = {'construction', 'contracting', 'engineering', 'services', 'company', 'florida', 'associates', 'group', 'consultants', 'solutions', 'systems'}


def body_gov(b):
    return next((g for p, g in BODY_GOV if b.startswith(p)), None)


def dt(s):
    try:
        return datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def norm(s):
    return ' ' + re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', (s or '').lower().replace('&', ' and '))).strip() + ' '


def alias_phrases(vid):
    """Distinctive phrases for finding a vendor in vote text: each alias without legal suffixes, at least 6 letters,
    not a single generic word. 'C.W. Roberts' also yields 'cw roberts' / 'c w roberts'."""
    v = ids.vendor(vid)
    out = set()
    for a in v['aliases'] + [v['name']]:
        a = re.sub(r'\(.*?\)', ' ', a)
        n = norm(a).strip()
        toks = n.split()
        while len(toks) > 1 and toks[-1] in ids.TRAIL:
            toks = toks[:-1]
        if toks and toks[0] == 'the':
            toks = toks[1:]
        p = ' '.join(toks)
        if len(p.replace(' ', '')) >= 6 and not (len(toks) == 1 and toks[0] in GENERIC) and not a.isupper():
            out.add(p)
            out.add(re.sub(r'\b([a-z]) (?=[a-z]\b)', r'\1', p))  # "c w roberts" -> "cw roberts"
    # parentheticals that are names (e.g. "(GCUC)", "(Emerald Coast Site Construction)")
    for a in v['aliases']:
        for m in re.findall(r'\(([^)]+)\)', a):
            n = norm(m).strip()
            if len(n.replace(' ', '')) >= 4 and not re.search(r'\d|award|bid|consult|program|camera|with ', n):
                out.add(n)
    return {p for p in out if p}


STOP = set('the a an of and to for in on at by with from or as is be this that its their it per up plus not exceed amount total contract contracts award awarded bid bids itb rfp rfq ifb '
           'approval approve approved consideration consent agenda item items city county board commission council resolution res project projects services service '
           'construction improvements improvement phase cra new fy fy24 fy25 fy26 florida bay panama beach inc llc co change order orders task 1 2 3 4 5 6 7 8 9 10 '
           'contingency with including additional agreement agreements authorize authorization execute mayor manager'.split())


def item_words(text, vids):
    """Distinctive words of a record's description, without the vendor's own name words."""
    vw = set()
    for vid in vids:
        for a in (ids.vendor(vid) or {}).get('aliases', []):
            vw |= set(norm(a).split())
    return {w for w in norm(text).split() if w not in STOP and w not in vw and len(w) > 2 and not w.isdigit()}


def nums(text):
    return {m.group(1).upper().replace('.', '-') for m in NUM.finditer(text or '')}


def vote_text(v):
    return ' '.join([v.get('item') or '', v.get('headline') or '', v.get('summary') or '', v.get('plain_summary') or ''])


def build():
    votes = json.load(open(os.path.join(DATA, 'votes', 'votes.json')))['votes']
    VIDS = ids.vote_ids(votes)
    for i, v in enumerate(votes):
        v['_id'] = VIDS[i]; v['_i'] = i; v['_gov'] = body_gov(v['body']); v['_d'] = dt(v['date']); v['_t'] = norm(vote_text(v)); v['_n'] = nums(vote_text(v)); v['_w'] = set(v['_t'].split()) - STOP
    recs = [r for r in records.all_records() if r['src'] in ('contract', 'change_order', 'emergency')]
    allv = json.load(open(os.path.join(DATA, 'entities', 'vendors.json')))['vendors']
    phrases = {v['id']: alias_phrases(v['id']) for v in allv}
    # which vendors each vote names
    for v in votes:
        v['_vend'] = {vid for vid, ps in phrases.items() if any(' ' + p + ' ' in v['_t'] for p in ps)}
    links, review = [], []
    for r in recs:
        vids = ids.vendor_ids(r['name'])
        rd = dt(r['date'])
        if not rd or not r['gov_id']:
            continue
        rn = nums(r['what'])
        cands = []
        for v in votes:
            if v['_gov'] != r['gov_id'] or not v['_d']:
                continue
            gap = abs((v['_d'] - rd).days)
            if gap > 45:
                continue
            by_name = bool(vids) and any(x in v['_vend'] for x in vids)
            by_num = bool(rn & v['_n'])
            amt_eq = r['amount'] is not None and v.get('amount') is not None and abs(float(v['amount']) - float(r['amount'])) < 1
            amt_ok = r['amount'] is None or v.get('amount') is None or amt_eq or (r['amount'] and abs(float(v['amount']) - float(r['amount'])) <= 0.03 * abs(float(r['amount'])))
            shared = item_words(r['what'], vids) & v['_w']
            by_item = len(shared) >= 3
            other_vendor = bool(v['_vend'] - set(vids))
            methods = [m for m, ok in (('vendor_name', by_name), ('item_number', by_num), ('agenda_item', by_item), ('amount', amt_eq and not other_vendor)) if ok]
            if not methods or methods == ['amount'] or methods == ['agenda_item']:
                if methods:
                    cands.append({'vote': v, 'gap': gap, 'methods': methods, 'confident': False, 'shared': sorted(shared)})
                continue
            # an item-number match must also name the vendor or agree on the amount: minutes can file another motion under
            # the same item number (a budget vote once landed on a parking-lot contract)
            confident = ((by_num and (by_name or amt_eq or by_item or gap == 0) and (by_name or amt_ok)) or (by_name and (amt_eq or (by_item and (gap == 0 or amt_ok)))) or (by_name and gap == 0 and amt_ok and not other_vendor and r['amount'] is not None and v.get('amount') is not None)
                         or (by_item and amt_eq))
            cands.append({'vote': v, 'gap': gap, 'methods': methods, 'confident': confident, 'shared': sorted(shared)})
        conf = [c for c in cands if c['confident']]
        # several confident votes for one record: keep the ones with the most kinds of agreement, then the closest in time
        if len(conf) > 1:
            best = max((len(c['methods']), -c['gap']) for c in conf)
            keep = [c for c in conf if (len(c['methods']), -c['gap']) == best]
            review += [dict(_review(r, c), reason='another vote matched more closely in time') for c in conf if c not in keep]
            conf = keep
        for c in conf:
            links.append({'record_id': f'{r["src"]}:{r["idx"]}', 'record_type': r['src'], 'vendor_ids': vids, 'gov_id': r['gov_id'], 'record_date': r['date'], 'record_amount': r['amount'],
                          'record_what': r['what'], 'record_url': r['url'], 'vote_index': c['vote']['_i'], 'vote_id': vote_id(c['vote']), 'vote_date': c['vote']['date'],
                          'days_apart': c['gap'], 'match_method': '+'.join(c['methods'])})
        for c in cands:
            if not c['confident']:
                review.append(dict(_review(r, c), reason='weak: ' + ('amount only' if c['methods'] == ['amount'] else 'description words only' if c['methods'] == ['agenda_item'] else f'{"+".join(c["methods"])}, {c["gap"]} days apart' + (', vote also names another vendor' if c['vote']['_vend'] - set(vids) else '') + ('' if 'amount' in c['methods'] else ', amounts differ'))))
    return votes, links, review


def vote_id(v):
    return v['_id']


def _review(r, c):
    v = c['vote']
    return {'record_id': f'{r["src"]}:{r["idx"]}', 'record': f'{r["name"]} · {r["date"]} · {r["what"]}', 'record_amount': r['amount'], 'vote_id': vote_id(v),
            'vote': f'{v["date"]} · {v.get("item")}', 'vote_amount': v.get('amount'), 'days_apart': c['gap'], 'match_method': '+'.join(c['methods']), 'shared_words': c.get('shared')}


def main():
    votes, links, review = build()
    per_rec = collections.defaultdict(list)
    for l in links:
        per_rec[l['record_id']].append(l['vote_id'])
    out = {'as_of': datetime.date.today().isoformat(),
           'method': __doc__.strip().split('\n', 2)[2].strip(),
           'count_links': len(links), 'count_records_linked': len(per_rec), 'count_votes_linked': len({l['vote_id'] for l in links}),
           'count_contracts_linked': len({l['record_id'] for l in links if l['record_type'] == 'contract'}),
           'by_method': dict(collections.Counter(l['match_method'] for l in links)),
           'links': links}
    json.dump(out, open(os.path.join(DATA, 'votes', 'contract_votes.json'), 'w'), indent=1, ensure_ascii=False)
    json.dump({'about': 'Possible contract-vote links that were NOT used: amount-only matches, matches more than 14 days apart, votes that also name another vendor, and second-best votes. For a person to check.',
               'count': len(review), 'review': review}, open(os.path.join(DATA, 'votes', 'contract_votes_review.json'), 'w'), indent=1, ensure_ascii=False)
    print('contract-vote links:', out['count_links'], 'records:', out['count_records_linked'], '(contracts', out['count_contracts_linked'], ') votes:', out['count_votes_linked'], out['by_method'], 'review:', len(review))


if __name__ == '__main__':
    main()
