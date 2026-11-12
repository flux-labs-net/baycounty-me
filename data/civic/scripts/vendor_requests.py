"""Draft public records requests about one vendor's dealings with a government: its contracts (with renewals and amendments)
and invoices, from each vendor's 'since' year. A records request may reach back before the site's 2016 cutoff
(data/entities/cutoff.py); anything older that comes back is kept as a file and not shown on the site.

Each entry in VENDORS is one request letter for each listed government. Writes data/civic/vendor_requests.json, which
/admin seeds into corr.records_requests (kind 'vendor') as drafts. Nothing is sent from here: an admin reviews each draft
and presses Send in the "Records requests" tab.

Run: python3 data/civic/scripts/vendor_requests.py
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..', '..', '..')
sys.path.insert(0, HERE)

OUT = os.path.join(HERE, '..', 'vendor_requests.json')

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

# One letter per vendor. since: the first year asked for.
VENDORS = {
    'civicplus': {
        'title': 'CivicPlus agreements',
        'vendor': 'CivicPlus, LLC',
        'govs': ['lh', 'pc'],
        'since': 2000,  # Jeremy, 2026-11-12: contracts and invoices only, since 2000
        'about': ('CivicPlus, LLC (also known as Civic Plus), including its predecessors, subsidiaries and affiliates, such as Municipal Code '
                  'Corporation (Municode) and SeeClickFix, and any reseller or cooperative-purchasing contract through which the city bought '
                  'CivicPlus products. This covers every CivicPlus product or service, for example the city website and its hosting and '
                  'redesigns, agenda and meeting management, mass notification, recreation, HR or permitting modules, 311 or citizen request '
                  'tools, and code of ordinances codification and hosting.'),
    },
}


def letter(gov_key, v):
    gov = CUSTODIANS[gov_key][0]
    # No ingest-address line yet: neither city has allowed senders, so emailed files would be refused (Jeremy, 2026-11-12).
    return f'''Under Chapter 119, Florida Statutes, I’m requesting copies of the following public records of the {gov} relating to {v['about']}

The period is January 1, {v['since']} to the date of your search.

1. Contracts: every contract, agreement, order form, renewal and amendment, with their exhibits and attachments.
2. Invoices: every invoice and credit memo the city received.

Electronic copies are preferred, as PDF or in their original format. If any of this is already posted online, a link is all I need. If a year can’t be found, please send what exists rather than holding the rest, and if any record or part of one is withheld or redacted, please cite the statute for each exemption, as section 119.07(1)(e) requires.

These records will be used by BayCounty.me, an independent public-records site for Bay County. If fulfilling the request will cost more than $25, please send an estimate before starting.

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
                        'subject': f'Public records request: {v["vendor"]} contracts and invoices since {v["since"]}',
                        'body': letter(g, v),
                        'gaps': [{'vendor': v['vendor'], 'since': f'{v["since"]}-01-01', 'need': 'Contracts (with renewals and amendments) and invoices'}],
                        'notes': note})
    return out


def main():
    d = drafts()
    json.dump({'as_of': CHECKED, 'about': 'Records request drafts for one vendor’s contracts and invoices with a government. '
               'Seeded into corr.records_requests and sent only from /admin.', 'requests': d},
              open(OUT, 'w'), indent=1, ensure_ascii=False)
    for r in d:
        print(r['key'], r['recipient_email'], r['subject'])


if __name__ == '__main__':
    main()
