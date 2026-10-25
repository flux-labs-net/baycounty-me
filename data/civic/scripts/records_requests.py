"""Draft public records requests for every budget year BayCounty.me is missing, one draft per government.

Reads what the budget-years dataset holds (site/page_datasets.py budget_years) for FY2015 to FY2027 and asks each
government for the adopted budget of every year where we have no fund-level lines. Writes
data/civic/records_requests.json, which /admin seeds into corr.records_requests as drafts. Nothing is sent from here:
an admin reviews each draft and presses Send in the "Records requests" tab.

Run: python3 data/civic/scripts/records_requests.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'site'))
OUT = os.path.join(HERE, '..', 'records_requests.json')
FIRST, LAST = 2015, 2027

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
    'county': 'Optional: the county’s fund totals are complete for every year; this asks only for General Fund department detail.',
    'schools': 'The district asks for a name, mailing address and phone number in each request; add them to the signature before sending.',
}
FY = lambda y, school: f'FY{y} ({y - 1}-{str(y)[2:]} school year)' if school else f'FY{y} (Oct 1, {y - 1} to Sep 30, {y})'


def spans(years):
    """[2015, 2016, 2017, 2020] -> 'FY2015-FY2017 and FY2020'."""
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
            if g == 'county':
                if 'department' not in s:
                    need.append({'fiscal_year': y, 'need': 'General Fund appropriations by department'})
            elif 'fund' not in s:
                need.append({'fiscal_year': y, 'need': 'adopted budget by fund' + ('' if s else ' (nothing on record)')})
        out[g] = need
    return out


def body(g, need):
    school = g == 'schools'
    years = [n['fiscal_year'] for n in need]
    lines = '\n'.join(f'- {FY(y, school)}' for y in years)
    if g == 'county':
        ask = ('the adopted budget’s General Fund appropriations by department (or division) for each of these fiscal years. '
               'The “Summary of All Funds” tables are already posted on the county website; what I’m missing is the department-level '
               'breakdown of the General Fund:')
    elif school:
        ask = ('the final adopted district budget for each of these fiscal years, showing appropriations by fund and, for the General '
               'Fund, by function or department (the budget summary adopted at the September final hearing is fine):')
    else:
        ask = ('the adopted (final) budget for each of these fiscal years, showing total appropriations by fund and General Fund '
               'appropriations by department. The budget book, the budget ordinance or resolution with its exhibits, or the '
               'summary presented at the final September hearing would each work:')
    return f'''Under Chapter 119, Florida Statutes, I’m requesting copies of {ask}

{lines}

Electronic copies (PDF or spreadsheet) by email are preferred. If any of these are already posted online, a link is all I need. If a year can’t be found, please say so and I’ll take what exists.

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
        what = 'General Fund department budgets' if g == 'county' else 'adopted budgets'
        drafts.append({'key': f'budgets-{FIRST}-{g}', 'government': gov, 'government_key': g, 'recipient_name': who, 'recipient_email': email,
                       'contact_url': url, 'subject': f'Public records request: {what}, {spans(years)}', 'body': body(g, n), 'gaps': n,
                       'notes': NOTES.get(g)})
    out = {'as_of': '2026-10-25', 'about': 'Records request drafts for the budget years BayCounty.me is missing (FY2015 onward). Seeded into corr.records_requests and sent only from /admin.',
           'requests': drafts}
    json.dump(out, open(OUT, 'w'), indent=1, ensure_ascii=False)
    for d in drafts:
        print(d['government_key'], len(d['gaps']), d['subject'], d['recipient_email'] or '(no address)')


if __name__ == '__main__':
    main()
