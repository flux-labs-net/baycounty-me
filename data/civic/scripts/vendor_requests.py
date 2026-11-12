"""Draft public records requests about one vendor's dealings with a government: the contracts, quotes, invoices, payments,
renewals and the mail about them, since the site's first year (data/entities/cutoff.py).

Each entry in VENDORS is one request letter for each listed government. Writes data/civic/vendor_requests.json, which
/admin seeds into corr.records_requests (kind 'vendor') as drafts. Nothing is sent from here: an admin reviews each draft
and presses Send in the "Records requests" tab.

Run: python3 data/civic/scripts/vendor_requests.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, os.path.join(ROOT, 'data', 'entities'))
sys.path.insert(0, HERE)
import cutoff  # noqa: E402
from records_requests import INTAKE  # noqa: E402

OUT = os.path.join(HERE, '..', 'vendor_requests.json')
START = f'January 1, {cutoff.FIRST_YEAR}'

# Records contacts, checked by hand on CHECKED against each city's own published page.
CHECKED = '2026-11-12'
CUSTODIANS = {
    'pc': ('City of Panama City', 'Public Records, City Clerk’s Office', 'publicrecords@panamacity.gov',
           'https://panamacity.gov/581/Public-Records-Request',
           'Panama City’s records contacts page lists the City Clerk’s Office at publicrecords@panamacity.gov, (850) 872-3021, '
           '501 Harrison Avenue (checked 2026-11-12). Its 2025 records policy says the clerk sends each request on to the departments that hold the records.'),
    'lh': ('City of Lynn Haven', 'Public Records Request, City of Lynn Haven', 'publicrecordsrequest@cityoflynnhaven.com',
           'https://www.cityoflynnhaven.gov/DocumentCenter/View/2545/Public-Records-Request-Form-updated-April-2023',
           'Lynn Haven’s public records request form (updated April 2023) says to email requests to publicrecordsrequest@cityoflynnhaven.com '
           'or mail them to 825 Ohio Avenue (checked 2026-11-12). The city has since moved its website to cityoflynnhaven.gov, and the commission '
           'took up changes to its records policy in January 2026, so a call to 850-265-2121 to confirm the address costs little.'),
}

# One letter per vendor. names: every name the company or its products go by, for the email search.
VENDORS = {
    'civicplus': {
        'title': 'CivicPlus agreements',
        'vendor': 'CivicPlus, LLC',
        'govs': ['lh', 'pc'],
        'names': ['CivicPlus', 'Civic Plus', 'civicplus.com', 'CivicEngage', 'CivicClerk', 'CivicReady', 'CivicRec', 'CivicHR', 'CivicSend',
                  'SeeClickFix', 'Municode', 'Municipal Code Corporation'],
        'about': ('CivicPlus, LLC (also known as Civic Plus), including its predecessors, subsidiaries and affiliates, such as Municipal Code '
                  'Corporation (Municode) and SeeClickFix, and any reseller or cooperative-purchasing contract through which the city bought '
                  'CivicPlus products. This covers every CivicPlus product or service, for example the city website and its hosting and '
                  'redesigns, agenda and meeting management, mass notification, recreation, HR or permitting modules, 311 or citizen request '
                  'tools, and code of ordinances codification and hosting.'),
    },
}


def letter(gov_key, v):
    gov = CUSTODIANS[gov_key][0]
    names = ', '.join(f'“{n}”' for n in v['names'])
    intake = (f'\nIf it’s easier, the files can also be emailed to {INTAKE[gov_key]}@ingest.baycounty.me or uploaded at https://baycounty.me/staff '
              '(we can give your clerk’s staff a free sign-in).\n') if gov_key in INTAKE else ''
    return f'''Under Chapter 119, Florida Statutes, I’m requesting copies of the following public records of the {gov} relating to {v['about']}

The period is {START} to the date of your search.

1. Agreements: every contract, master services agreement, order form, quote or proposal, statement of work, renewal, amendment, addendum, change order, price increase or renewal notice, and termination or non-renewal notice, with all exhibits, schedules and attachments.
2. Purchasing: any request for proposals, request for quotes or bid and the responses received, evaluation or scoring sheets, sole-source or cooperative-contract (piggyback) justifications, requisitions and purchase orders.
3. Approvals: agenda items, staff reports or memos, resolutions, and the minutes or approvals for each purchase, renewal or amendment.
4. Money: every invoice and credit memo, and the payment records for each (check or ACH register entries, purchasing card charges), plus the budget account or line each was charged to.
5. Communications: emails (with attachments), letters, text messages and meeting notes or calendar entries between any city official or employee and anyone at the company, and city officials’ and employees’ internal communications about these agreements, products or invoices. A search of city email accounts for these terms should find most of them: {names}.
6. Service records: implementation and project plans, acceptance or sign-off documents, support tickets or escalations, service-level or performance reports, complaints, security or data incident notices, data ownership or export terms, and certificates of insurance.
7. Any list or summary of the CivicPlus products the city uses now or has used since {cutoff.FIRST_YEAR}, with the yearly cost of each, if one exists.

Electronic copies are preferred: documents as PDF or in their original format, spreadsheets in Excel or CSV, and emails as PDF or in their native format with the sender, recipients and date shown. If any of this is already posted online, a link is all I need.

Please send the agreements, invoices and payment records as soon as they’re ready, and the communications after, rather than holding the whole request until everything is gathered. If any record or part of one is withheld or redacted, please cite the statute for each exemption, as section 119.07(1)(e) requires, and release the rest.
{intake}
These records will be shown to residents on BayCounty.me, an independent public-records site for Bay County. If fulfilling the request will cost more than $25, please send an estimate before starting.

Thank you,
Jeremy McSpadden
BayCounty.me'''


def drafts():
    out = []
    for vk, v in VENDORS.items():
        for g in v['govs']:
            gov, who, email, url, note = CUSTODIANS[g]
            out.append({'key': f'vendor-{vk}-{g}', 'kind': 'vendor', 'check_title': v['title'], 'government': gov, 'government_key': g,
                        'recipient_name': who, 'recipient_email': email, 'contact_url': url,
                        'subject': f'Public records request: {v["vendor"]} agreements, invoices and communications since {cutoff.FIRST_YEAR}',
                        'body': letter(g, v),
                        'gaps': [{'vendor': v['vendor'], 'since': f'{cutoff.FIRST_YEAR}-01-01', 'names': v['names'],
                                  'need': 'Contracts, quotes, renewals, amendments, purchasing, approvals, invoices, payments, communications and service records'}],
                        'notes': note})
    return out


def main():
    d = drafts()
    json.dump({'as_of': CHECKED, 'about': 'Records request drafts about one vendor’s dealings with a government (contracts, invoices, payments, '
               'communications). Seeded into corr.records_requests and sent only from /admin.', 'requests': d},
              open(OUT, 'w'), indent=1, ensure_ascii=False)
    for r in d:
        print(r['key'], r['recipient_email'], r['subject'])


if __name__ == '__main__':
    main()
