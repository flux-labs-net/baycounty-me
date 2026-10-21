import json, sys
C = json.load(open(sys.argv[1]))
order = {'35': 0, '36': 1, '34': 2, '37': 3}
def okey(c):
    e = c['report_url'].split('&e=')[1].split('&')[0]
    return (order[e], c['office'], c['name'])
C.sort(key=okey)
gaps = [
 'Lake Powell Community Development District (Seats 2 and 5): five candidates are listed in the SOE system with no reports and $0 totals; nothing to itemize.',
 'Suzanne McDowell and Sunny Reid (County Commission District 4, both Withdrawn): no reports or itemized activity listed.',
 'Lynn Haven recall (Jan 20, 2026): the two recall political committees ("Lynn Haven Recall", "Recall Mayor Nelson") are committees, not candidates, and are excluded. Only the candidate account for the mayor\'s seat is included.',
 'No 2026 elections were listed in the SOE system for Panama City, Lynn Haven (other than the recall), Parker, or for county constitutional offices; Panama City and Parker hold municipal elections in odd years (2025, 2027).',
 'Campaigns still active through Nov 3 have filed through G4 (period ending 2026-10-02) or, for two Callaway candidates, G5 (period ending 2026-10-16). The G5 report for the others (period 10/3 to 10/16) was not posted as of 2026-10-21, and the G6 report is due after the election. Figures will change.',
 'Dr. John L. Haley: one blank deletion line in an amended report could not be matched; SOE totals may double-count one $1,000 candidate loan (see candidate notes).',
 'Expenditure payees have no type code in the filings. Payees were judged to be individual people by name and aggregated as "Payments to individuals" (or "Refunds to individual contributors"); a few business names that are personal names could be misjudged.',
 'In-county vs out-of-county is based on the city/ZIP filed for each individual contribution (Bay County cities and ZIPs). Contributions with no address filed are counted as location_unknown.',
]
tot = round(sum(c['total_raised'] for c in C), 2)
out = {
 'as_of': __import__('datetime').date.today().isoformat(),
 'source': 'Bay County Supervisor of Elections campaign finance system (VoterFocus), https://www.voterfocus.com/ws/WScand/candidate_pr.php?c=Bay, embedded at https://www.bayvotesfl.gov/candidates/candidate-committee-finances/. Reporting groups: 2026 Primary/General Election (el=35), 2026 Municipal Super Tuesday (el=36), Lynn Haven Recall 1/20/2026 (el=34). Per-candidate itemized CSV export: https://www.voterfocus.com/CampaignFinance/export.php?op=CFINANCE&cand_id={id}&dhc=0&county=bay',
 'field_notes': {
  'total_raised': 'SOE monetary contributions plus SOE in-kind contributions. Monetary includes candidate loans and bank interest as filed.',
  'monetary': 'SOE "Monetary Contributions" (sum of all reports, including amendments), net of contribution refunds reported as negative items.',
  'in_kind': 'SOE "In-Kind Contributions".',
  'total_spent': 'SOE "Expenditures and Distributions". For closed campaigns this includes refunds to contributors, loan repayments to the candidate and other surplus distributions.',
  'cash_on_hand_estimate': 'monetary minus total_spent for campaigns that have not filed a termination report; null for closed campaigns or campaigns with no reports. Does not account for outstanding loans or uncashed checks.',
  'through': 'End date of the latest report period filed.',
  'latest_report': 'Report code, period covered and SOE due date, as listed on the candidate page.',
  'from_individuals': 'Contributions from individual people: count of positive items and net total (after any refunds). Bands are per contribution item (under $100, $100-$499, $500-$999, $1,000 and over). in_county/out_of_county/location_unknown split by the city/ZIP filed. unique_donors_approx counts distinct filed names and is approximate. No names are stored.',
  'contributors': 'Organizations (business, pac, committee, party, other) and the candidate\'s own money and loans, item by item, as filed. Negative amounts are refunds the campaign reported. kind is the filed item type.',
  'by_type_total': 'Net contribution totals by contributor type (monetary and in-kind). Candidate committees ("Friends of ...") are counted under pac. Bank interest is under other. Sums to total_raised.',
  'top_expenditures': 'Up to 15 largest payees by total. Payee name variants are merged. Payments to individual people are aggregated as "Payments to individuals" or "Refunds to individual contributors". purpose lists the filed descriptions, most money first.',
 },
 'summary': {'candidates': len(C), 'total_raised_all': tot,
             'total_monetary_all': round(sum(c['monetary'] for c in C), 2), 'total_in_kind_all': round(sum(c['in_kind'] for c in C), 2),
             'total_spent_all': round(sum(c['total_spent'] for c in C), 2),
             'reconciled': sum(1 for c in C if c['reconciliation'] == 'itemized matches summary'),
             'no_activity': sum(1 for c in C if c['reconciliation'].startswith('no activity'))},
 'candidates': C, 'gaps': gaps}
json.dump(out, open(sys.argv[2], 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out['summary'], indent=1))
