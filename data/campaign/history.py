"""Every local campaign from 2016 through 2025, from the Bay County Supervisor of Elections (SOE).

campaign.json covers each sitting official's latest win and ../elections/finance_2026.json every 2026 candidate. This
file fills in the rest: every candidate who opened a campaign account with the SOE for a local race in the 2016 to 2025
elections, winners and losers, with the same totals and the same privacy rules.

Usage: python3 data/campaign/history.py [WORKDIR]
  Downloads the SOE (VoterFocus) lists, candidate pages and itemized exports for the reporting groups below into WORKDIR
  (reused when lists.json is already there), runs ../elections/scripts/pages.py and build.py on them and writes
  campaign_history.json. These campaigns are closed, so this is run by hand, not by the daily refresh.

Privacy (same as campaign.json and finance_2026.json): individual contributors are never named; they appear only as a
count and a total. Organizations and the candidate's own money are listed item by item, with the city as filed.
Expenditures are kept only as totals here, because payees who are private people would otherwise be named.

The SOE's online system starts with the 2016 elections, which is also the site's first year (data/entities/cutoff.py):
itemized gifts dated before 2016 (early money for the 2016 races) are left out of the lists, not the totals.
"""
import datetime, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402  the site's first year (2016)
SCRIPTS = os.path.join(HERE, '..', 'elections', 'scripts')
OUT = os.path.join(HERE, 'campaign_history.json')

# SOE reporting group id -> election date (the general election, or the municipal election day)
GROUPS = {'14': '2016-11-08', '15': '2016-04-19', '16': '2017-04-18', '18': '2018-04-17', '19': '2018-11-06', '20': '2019-04-16',
          '21': '2020-11-03', '22': '2020-04-21', '25': '2021-04-20', '27': '2022-11-08', '28': '2022-04-19', '30': '2023-04-18',
          '26': '2024-11-05', '31': '2024-04-16', '32': '2025-04-22'}
PRIMARY = {'14': '2016-08-30', '19': '2018-08-28', '21': '2020-08-18', '27': '2022-08-23', '26': '2024-08-20'}

# SOE office name -> (government id, office label). Party posts and federal offices that file locally are left out.
OFFICES = [
    (r'^County Commissioner, District (\d)', 'county', 'Bay County Commission, District {}'),
    (r'^School Board Member, District (\d)', 'schools', 'School Board, District {}'),
    (r'^Superintendent of Schools', 'schools', 'Superintendent of Schools'),
    (r'^Sheriff', 'sheriff', 'Sheriff'),
    (r'^Clerk of Court', 'clerk', 'Clerk of Court and Comptroller'),
    (r'^Property Appraiser', 'property_appraiser', 'Property Appraiser'),
    (r'^Tax Collector', 'tax_collector', 'Tax Collector'),
    (r'^Supervisor Of Elections', 'soe', 'Supervisor of Elections'),
    (r'^County Judge, Group (\d)', 'county_court', 'Bay County Judge, Group {}'),
    (r'^Panama City Beach Mayor', 'pcb', 'Panama City Beach Mayor'),
    (r'^Panama City Beach Council Ward (\d)', 'pcb', 'Panama City Beach Council, Ward {}'),
    (r'^Panama City Mayor', 'pc', 'Panama City Mayor'),
    (r'^Panama City Commissioner Ward (\d)', 'pc', 'Panama City Commission, Ward {}'),
    (r'^Lynn Haven Mayor', 'lh', 'Lynn Haven Mayor'),
    (r'^Lynn Haven Commissioner Seat (\d)', 'lh', 'Lynn Haven Commission, Seat {}'),
    (r'^Callaway Mayor', 'cw', 'Callaway Mayor'),
    (r'^Callaway Commissioner Ward (\d)', 'cw', 'Callaway Commission, Ward {}'),
    (r'^Springfield Mayor', 'sp', 'Springfield Mayor'),
    (r'^Springfield Commissioner Ward (\d)', 'sp', 'Springfield Commission, Ward {}'),
    (r'^Parker Mayor', 'parker', 'Parker Mayor'),
    (r'^Parker Council Member Seats 1 & 3', 'parker', 'Parker Council, Seats 1 and 3'),
    (r'^Parker Council Member Seat (\d)', 'parker', 'Parker Council, Seat {}'),
    (r'^Mexico Beach Mayor ?/ ?Council Group 1\s*\(Special', 'mb', 'Mexico Beach Mayor (special election)'),
    (r'^Mexico Beach Mayor', 'mb', 'Mexico Beach Mayor'),
    (r'^Mexico Beach Council Member Group (\d)', 'mb', 'Mexico Beach Council, Group {}'),
    (r'^Lake Powell CDD Seat (\d)', 'lake_powell_cdd', 'Lake Powell Community Development District, Seat {}'),
    (r'^Beach Mosquito Seat (\d)', 'beach_mosquito', 'Beach Mosquito Control District, Seat {}'),
]
LEFT_OUT = r'Committeeman|Committeewoman|United States'


def office(soe):
    s = re.sub(r'\s+', ' ', soe or '').strip()
    for pat, gid, label in OFFICES:
        m = re.match(pat, s, re.I)
        if m:
            return gid, label.format(*m.groups())
    return None, None


def outcome(status):
    """Plain outcome from the SOE status ('Elected', 'Defeated', 'Withdrawn', ...)."""
    s = (status or '').lower()
    for k, v in (('elected', 'won'), ('unopposed', 'won'), ('defeated', 'lost'), ('withdr', 'withdrew'), ('did not qualify', 'did not qualify'), ('not qualif', 'did not qualify'),
                 ('runoff', 'lost'), ('qualified', 'on the ballot')):
        if k in s:
            return v
    return None


def run(work):
    if not os.path.exists(os.path.join(work, 'lists.json')):
        subprocess.run([sys.executable, os.path.join(SCRIPTS, 'fetch.py'), work, *GROUPS], check=True)
    subprocess.run([sys.executable, os.path.join(SCRIPTS, 'pages.py'), work], check=True, stdout=subprocess.DEVNULL)
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'build.py'), work, os.path.join(work, 'out.json')], check=True, capture_output=True, text=True)
    review = [l for l in r.stdout.splitlines() if l.startswith('REVIEW') or 'MISMATCH' in l]
    return json.load(open(os.path.join(work, 'out.json'))), review


def main():
    work = sys.argv[1] if len(sys.argv) > 1 else os.path.join('/tmp', 'campaign_history')
    C, review = run(work)
    out, left = [], []
    for c in C:
        e = str(c['election_id'])
        gid, label = office(c['soe_office'])
        if not gid:
            left.append(f"{re.sub(r'\\s+', ' ', c['soe_office']).strip()} ({c['year'] if 'year' in c else c['election'][:4]})")
            if not re.search(LEFT_OUT, c['soe_office']):
                print('UNMAPPED OFFICE', c['soe_office'], file=sys.stderr)
            continue
        c.pop('top_expenditures', None)  # payees can be private people: totals only here
        c.pop('cash_on_hand_estimate', None)
        c['contributors'] = [x for x in c['contributors'] if x.get('type') != 'individual']
        for x in c['contributors']:
            x['name'] = (x.get('name') or '').replace("\\'", "'")  # the SOE pages escape apostrophes (Adam\'s Pharmacy)
        early = [x for x in c['contributors'] if not cutoff.keep(x.get('date'))]
        if early:  # the site starts in 2016: itemized gifts dated earlier are left out; the campaign totals stay whole
            c['contributors'] = [x for x in c['contributors'] if cutoff.keep(x.get('date'))]
            c.setdefault('notes', []).append(f'{len(early)} itemized gifts from organizations dated before 2016 are not listed (the site starts in 2016); the totals cover the whole campaign.')
        c.update({'office': label, 'gov_id': gid, 'election_date': GROUPS[e], 'primary_date': PRIMARY.get(e), 'year': int(GROUPS[e][:4]),
                  'outcome': outcome(c['soe_status'])})
        out.append(c)
    out.sort(key=lambda c: (-c['year'], c['election_date'], c['gov_id'], c['office'], c['name']))
    left_counts = {}
    for x in left:
        left_counts[x] = left_counts.get(x, 0) + 1
    doc = {
        'as_of': datetime.date.today().isoformat(),
        'source': 'Bay County Supervisor of Elections campaign finance system (VoterFocus), https://www.voterfocus.com/ws/WScand/candidate_pr.php?c=Bay, '
                  'embedded at https://www.bayvotesfl.gov/candidates/candidate-committee-finances/. Reporting groups (el=): ' + ', '.join(GROUPS) +
                  '. Per-candidate itemized CSV export: https://www.voterfocus.com/CampaignFinance/export.php?op=CFINANCE&cand_id={id}&dhc=0&county=bay',
        'method': 'Same build as ../elections/finance_2026.json (data/elections/scripts/build.py): SOE summary totals per campaign, itemized exports with '
                  'amendments applied and reconciled to the summary, contributors classified by the filed code and corrected only where plainly wrong. '
                  'Individuals are counted and summed, never named. Expenditures are totals only.',
        'summary': {'campaigns': len(out), 'years': sorted({c['year'] for c in out}), 'total_raised_all': round(sum(c['total_raised'] for c in out), 2),
                    'reconciled': sum(1 for c in out if c['reconciliation'] == 'itemized matches summary'),
                    'no_activity': sum(1 for c in out if c['reconciliation'].startswith('no activity')),
                    'not_reconciled': sum(1 for c in out if c['reconciliation'] != 'itemized matches summary' and not c['reconciliation'].startswith('no activity'))},
        'gaps': ['Left out (party posts and a federal race that file with the SOE): ' + '; '.join(f'{k} x{v}' if v > 1 else k for k, v in sorted(left_counts.items())) + '.',
                 'Campaigns whose itemized lines do not add up to the SOE summary are flagged in reconciliation; the SOE summary figures are used for totals.',
                 'Political committees (for example referendum committees) are not candidates and are not included.'],
        'candidates': out,
    }
    json.dump(doc, open(OUT, 'w'), indent=1, ensure_ascii=False)
    for r in review:
        print(r)
    print(json.dumps(doc['summary']))


if __name__ == '__main__':
    main()
