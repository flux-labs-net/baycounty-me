"""Draft public records requests for every budget year BayCounty.me is missing, one draft per government.

Reads what the budget-years dataset holds (site/page_datasets.py budget_years) for FY2016 (the site's first year, data/entities/cutoff.py) to FY2027 and asks each
government for the adopted budget of every year where we have no department-level lines. Writes
data/civic/records_requests.json, which /admin seeds into corr.records_requests as drafts. Nothing is sent from here:
an admin reviews each draft and presses Send in the "Records requests" tab.

Run: python3 data/civic/scripts/records_requests.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'site'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
import cutoff  # noqa: E402
OUT = os.path.join(HERE, '..', 'records_requests.json')
FIRST, LAST = cutoff.FIRST_YEAR, 2027

# Who handles records requests. recipient_email is blank where no address is published; the admin fills it in.
RECIPIENTS = {
    'county': ('Bay County Board of County Commissioners', 'Joel Schubert, County Manager (records custodian)', 'jschubert@baycountyfl.gov',
               'https://www.baycountyfl.gov/307/Communications-Office'),
    'pc': ('City of Panama City', 'Public Records, City Clerk’s Office', 'publicrecords@panamacity.gov', 'https://panamacity.gov/581/Public-Records-Request'),
    'pcb': ('City of Panama City Beach', 'Lynne Fasone, City Clerk', '', 'https://www.pcbfl.gov/about-us/city-news'),
    'lh': ('City of Lynn Haven', 'City Clerk', 'cityhall@cityoflynnhaven.com', 'https://www.cityoflynnhaven.com/'),
    'cw': ('City of Callaway', 'Ashley Robyck, City Clerk', 'arobyck@cityofcallaway.com', 'https://www.cityofcallaway.com/directory.aspx'),
    'sp': ('City of Springfield', 'Teresa Cox, City Clerk', '', 'https://www.springfieldfl.net/email-contact/node/3842/field_email'),
    'parker': ('City of Parker', 'Rachelle Stanley, City Clerk', 'clerk@cityofparker.com', 'https://cityofparker.com/'),
    'mb': ('City of Mexico Beach', 'Tammy Brunson, City Clerk', 't.brunson@mexicobeachfl.gov', 'https://www.mexicobeachfl.gov/'),
    'schools': ('Bay District Schools (School Board of Bay County)', 'Office of Communications (public records)', 'BDSComm@bay.k12.fl.us',
                'https://bay.k12.fl.us/uploads/PUBLIC%20RECORD%20REQUESTS.htm'),
}
NOTES = {
    'pcb': 'No published email for the City Clerk (pcbfl.gov blocks automated reads). Add the clerk’s address before sending.',
    'sp': 'Springfield publishes only a contact form for the clerk. Add an address, or paste this text into the form and mark the request sent.',
    'county': 'We already have fund totals for every year; this asks for the department and line-item detail behind them.',
    'schools': 'The district asks for a name, mailing address and phone number in each request; add them to the signature before sending.',
}
# Each government's intake address (migration 0091). Files emailed there, or sent from Send records in the BayCounty.me
# government workspace, come in straight from the government's own system. The School Board has no workspace yet.
INTAKE = {'county': 'baycounty', 'pc': 'panamacity', 'pcb': 'panamacitybeach', 'lh': 'lynnhaven', 'cw': 'callaway', 'sp': 'springfield',
          'parker': 'parker', 'mb': 'mexicobeach'}
FY = lambda y, school: f'FY{y} ({y - 1}-{str(y)[2:]} school year)' if school else f'FY{y} (Oct 1, {y - 1} to Sep 30, {y})'


def spans(years):
    """[2016, 2017, 2018, 2021] -> 'FY2016-FY2018 and FY2021'."""
    out, ys = [], sorted(years)
    i = 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        out.append(f'FY{ys[i]}' if i == j else f'FY{ys[i]}-FY{ys[j]}')
        i = j + 1
    return ', '.join(out[:-1]) + (' and ' if len(out) > 1 else '') + out[-1]


def gaps():
    from page_datasets import budget_years
    have = {}
    for r in budget_years():
        if r['basis'] == 'adopted':
            have.setdefault(r['gov_id'], {}).setdefault(r['fiscal_year'], set()).add(r['section'])
    out = {}
    for g in RECIPIENTS:
        yrs = have.get(g, {})
        need = []
        for y in range(FIRST, LAST + 1):
            s = yrs.get(y, set())
            if 'department' in s:
                continue
            have_txt = 'nothing on record' if not s else ('fund totals only' if 'fund' in s else 'total only')
            need.append({'fiscal_year': y, 'need': f'line-item budget by fund, department and account ({have_txt})'})
        out[g] = need
    return out


def body(g, need):
    school = g == 'schools'
    years = [n['fiscal_year'] for n in need]
    lines = '\n'.join(f'- {FY(y, school)}' for y in years)
    unit = 'function, cost center or school/department' if school else 'department and division (cost center)'
    send = (f'\nTo save a step, you can email the files to {INTAKE[g]}@ingest.baycounty.me, or upload them at https://baycounty.me/staff '
            '(we can give your finance or clerk staff a free sign-in). Nothing is published until it has been checked, and the same address '
            'works for future check registers, budget reports and contract lists.\n') if g in INTAKE else ''
    return f'''Under Chapter 119, Florida Statutes, I’m requesting the complete adopted budget, in as much detail as your records hold, for each of these fiscal years:

{lines}

For each year, please include:

1. Appropriations (expenditures) for every fund, broken down by {unit} and by account or object code (personnel services, operating expenses, capital outlay, debt service, grants and aids, transfers, reserves), with the line-item amounts.
2. Revenues for every fund by source and account (taxes, fees, intergovernmental, grants, charges for services, transfers in, fund balance carried forward).
3. Authorized positions (FTEs) by department, if the budget lists them.
4. The adopted capital improvement program or capital budget for that year.
5. The budget ordinance or resolution that adopted it, with its exhibits, and, if available, the final amended budget at year end.

A line-item report or export from your financial system (Excel or CSV) is ideal. The full budget book in PDF works too. If any of these are already posted online, a link is all I need, and if a year or item can’t be found, please send what exists rather than holding the rest.
{send}
This is a non-commercial request. These records will be used to show residents how the budget has changed over time on BayCounty.me, an independent public-records site for Bay County. If fulfilling it will cost more than $25, please send an estimate before starting.

Thank you,
Jeremy McSpadden
BayCounty.me'''


def main():
    need = gaps()
    drafts = []
    for g, (gov, who, email, url) in RECIPIENTS.items():
        n = need[g]
        if not n:
            continue
        years = [x['fiscal_year'] for x in n]
        what = 'line-item budgets by fund and department'
        drafts.append({'key': f'budgets-{FIRST}-{g}', 'government': gov, 'government_key': g, 'recipient_name': who, 'recipient_email': email,
                       'contact_url': url, 'subject': f'Public records request: {what}, {spans(years)}', 'body': body(g, n), 'gaps': n,
                       'notes': NOTES.get(g)})
    out = {'as_of': '2026-10-25', 'about': 'Records request drafts for the budget years BayCounty.me is missing (FY2016 onward). Seeded into corr.records_requests and sent only from /admin.',
           'requests': drafts}
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    for d in drafts:
        print(d['government_key'], len(d['gaps']), d['subject'], d['recipient_email'] or '(no address)')


if __name__ == '__main__':
    main()
