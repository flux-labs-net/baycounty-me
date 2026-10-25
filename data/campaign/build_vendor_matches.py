"""Build data/campaign/vendor_matches.json: organization contributors that are also paid by a local government.

Run by data/build.py (after data/entities/build_entities.py). Inputs:
  gifts:  business contributors in campaign.json (current officeholders) and ../elections/finance_2026.json (2026 candidates)
  money:  every record in data/entities/records.py: contracts, change orders, emergency purchases, check registers,
          TDC agency payments and the CRA ledger
A gift and a payment match when both names resolve to the same vendor_id in data/entities/vendors.json (exact key or a
hand-reviewed join; nothing fuzzy). One row per contributor spelling, candidate and paying government, the same shape
the Campaign Money and Money Map pages already read, plus vendor_id, source and record ids.
"""
import collections, datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import ids  # noqa: E402
import records  # noqa: E402

LABEL = {'contract': 'Contract', 'change_order': 'Change order', 'emergency': 'Emergency purchase', 'register': 'check register, top-vendor list',
         'tdc': 'Tourism agency payments', 'cra': 'CRA ledger'}
# paying-government names as the pages show them (money_map.GOV_KEY reads these)
GOVNAME = {'county': 'Bay County BOCC', 'pc': 'City of Panama City', 'pcb': 'City of Panama City Beach', 'lh': 'City of Lynn Haven', 'cw': 'City of Callaway',
           'sp': 'City of Springfield', 'parker': 'City of Parker', 'mb': 'City of Mexico Beach', 'schools': 'Bay District Schools'}
OFFICE_GOV = lambda office: ids.gov_id(office, contains=True)


def usd(n):
    return f'${n:,.2f}'


def describe(r):
    """One line per record, in the wording the pages already parse (they read the last $ amount on award lines)."""
    a = r['amount']
    if r['src'] == 'contract':
        return f'Contract {r["date"]}: {r["what"]} ({usd(a)})' if a is not None else f'Contract {r["date"]}: {r["what"]} (amount not stated)'
    if r['src'] == 'change_order':
        return f'Change order {r["date"]}: {r["what"]} (change {usd(a)})' if a is not None else f'Change order {r["date"]}: {r["what"]}'
    if r['src'] == 'emergency':
        return f'Emergency purchase {r["date"]}: {r["what"]} ({usd(a)})'
    if r['src'] == 'register':
        return f'{r["date"]} check register, top-vendor list: {usd(a)} paid'
    if r['src'] == 'tdc':
        fy = ', '.join(sorted((r['extra'].get('by_fy') or {}).keys()))
        return f'{r["what"].split(":")[0]} check register ({fy}): {usd(a)} paid in {r["extra"].get("n_payments")} payments'
    if r['src'] == 'cra':
        st = r['extra'].get('status')
        cnt = '' if r['extra'].get('count') else ' (not counted in CRA totals: ' + (r['extra'].get('overlap') or 'see ledger') + ')'
        return f'{r["extra"]["cra"]} {st.lower() if st else "record"} {r["date"]}: {r["what"]}' + (f' ({usd(a)})' if a is not None else '') + cnt
    return r['what']


def rid(r):
    return f'{r["src"]}:{r["idx"]}'


def build():
    money = collections.defaultdict(list)  # vendor_id -> records
    for r in records.all_records():
        for v in ids.vendor_ids(r['name']):
            money[v].append(r)
    gifts = [g for g in records.donations() if ids.vendor_id(g['name'])]
    # gifts from one spelling to one candidate are summed (as the filings list them item by item)
    # one pair per vendor and candidate; a refund line (negative amount) reduces nothing here but is reported as refunded
    pairs = collections.OrderedDict()
    for g in gifts:
        k = (ids.vendor_id(g['name']), g['candidate'], g['src'])
        p = pairs.setdefault(k, {'g': g, 'amount': 0.0, 'refund': 0.0, 'dates': [], 'items': [], 'names': collections.Counter()})
        amt = g['amount'] or 0
        if amt < 0 or g.get('kind') == 'refund':
            p['refund'] += -amt if amt < 0 else amt
        else:
            p['amount'] += amt; p['dates'].append(g['date']); p['items'].append(g.get('kind') or 'check'); p['names'][g['name'].strip()] += amt
    rows = []
    for (vid, cand, src), p in pairs.items():
        g = p['g']; v = ids.vendor(vid)
        name = p['names'].most_common(1)[0][0] if p['names'] else g['name'].strip()
        office_gov = OFFICE_GOV(g['office'])
        bygov = collections.defaultdict(list)
        for r in money[vid]:
            if r['gov_id']:
                bygov[r['gov_id']].append(r)
        exact = ids.vkey(name) == ids.vkey(v['name']) or any(ids.vkey(name) == ids.vkey(a) for a in v['aliases'] if a != name and not a.isupper())
        for gov, rs in sorted(bygov.items()):
            rs = sorted(rs, key=lambda r: (str(r['date']), r['src']))
            seen, desc, urls, rids = set(), [], [], []
            for r in rs:
                d = describe(r)
                if d in seen:
                    continue
                seen.add(d); desc.append(d); rids.append(rid(r))
                if r['url'] and r['url'] not in urls:
                    urls.append(r['url'])
            gname = GOVNAME.get(gov) or (ids.gov(gov) or {}).get('name') or gov
            rows.append({
                'contributor': name, 'contributor_spellings': sorted(p['names']) if len(p['names']) > 1 else None, 'vendor': ' / '.join(sorted({r['name'] for r in rs})), 'vendor_id': vid, 'vendor_entity': v['name'],
                'candidate': cand, 'person_id': ids.person_id(cand), 'office': g['office'], 'election': g['election'],
                'gift_source': {'officeholders': 'current officeholders (campaign.json)', 'candidates_2026': '2026 candidates (finance_2026.json)'}.get(src, 'past campaigns 2016-2025 (campaign_history.json)'),
                'contribution_amount': round(p['amount'], 2), 'refunded_by_campaign': round(p['refund'], 2) or None,
                'contribution_dates': sorted(set(p['dates'])), 'contribution_items': p['items'],
                'contract_ids_or_descriptions': desc, 'record_ids': rids, 'contract_source_urls': urls,
                'contract_government': gname, 'contract_gov_id': gov, 'record_types': sorted({r['src'] for r in rs}),
                'match_confidence': 'exact' if exact else 'likely',
                'note': ('Names match after removing punctuation and legal suffixes.' if exact else
                         f'The filing spells the name "{name}"; matched to {v["name"]} by a hand-checked spelling join. ' + (v.get('merge_evidence') or '')).strip(),
                'campaign_report_url': g['report_url'], 'office_gov_id': office_gov, 'same_government_as_office': office_gov == gov,
            })
    rows.sort(key=lambda r: (r['gift_source'], r['candidate'], r['contributor'], r['contract_gov_id']))
    pairs_set = {(r['contributor'], r['candidate']) for r in rows}
    conf = collections.Counter(next(r['match_confidence'] for r in rows if (r['contributor'], r['candidate']) == p) for p in pairs_set)
    out = {
        'as_of': datetime.date.today().isoformat(),
        'method': ('Business contributors to current officeholders (campaign.json), 2026 local candidates (../elections/finance_2026.json) and every other local campaign since 2016 (campaign_history.json) were compared with every payee on this site: '
                   'contracts, change orders and emergency purchases (../contracts/contracts.json), Bay County and Lynn Haven check registers, payments by the three tourism agencies '
                   '(../money/payments.json) and the CRA ledger (../merged.json). Both sides are resolved to vendor ids in ../entities/vendors.json: names are matched after removing '
                   'punctuation, "&"/"and" and legal suffixes, plus hand-checked joins of truncated or misspelled names (each with its evidence in vendors.json). Nothing is fuzzy-matched. '
                   '"exact" = the filed name matches the vendor\'s name; "likely" = the filing truncates, abbreviates or misspells it. One row per contributor spelling, candidate and paying '
                   'government. A match shows only that an organization with the same name appears in both public records; it does not show why a gift was made or how a contract was awarded. '
                   'Built by build_vendor_matches.py.'),
        'count_rows': len(rows), 'count_contributor_candidate_pairs': len(pairs_set), 'count_distinct_vendors': len({r['vendor_id'] for r in rows}),
        'count_by_confidence_pairs': dict(conf),
        'pairs_where_contract_government_matches_office': len({(r['contributor'], r['candidate']) for r in rows if r['same_government_as_office']}),
        'count_by_gift_source_pairs': dict(sorted(collections.Counter(next(r['gift_source'] for r in rows if (r['contributor'], r['candidate']) == p) for p in pairs_set).items())),
        'count_by_record_type_rows': dict(collections.Counter(t for r in rows for t in r['record_types'])),
        'matches': rows,
    }
    return out


def main():
    out = build()
    json.dump(out, open(os.path.join(HERE, 'vendor_matches.json'), 'w'), indent=1, ensure_ascii=False)
    print('vendor matches:', out['count_rows'], 'rows,', out['count_contributor_candidate_pairs'], 'pairs,', out['count_distinct_vendors'], 'vendors', out['count_by_gift_source_pairs'])


if __name__ == '__main__':
    main()
