"""Change log for baycounty.me: drives the 'Updated' line on each page, /updates and /updates.xml (RSS).

Add an entry at the TOP of CHANGES whenever a page's data changes. 'pages' lists the
paths the change touched; each page shows the date of its most recent entry.
"""
from datetime import date
from email.utils import format_datetime
from datetime import datetime, timezone
import html

CHANGES = [
    {'date': '2026-10-20', 'title': 'Contracts and vendors',
     'text': 'Major contracts approved by Bay County and its cities since October 2022: winners, how they were awarded, change orders, emergency purchases, the bidding rules, and who the county actually paid the most.',
     'pages': ['/public-money/contracts']},
    {'date': '2026-10-20', 'title': 'Fees, utility bills and who runs Bay County',
     'text': 'Every flat fee on Bay County tax bills, a typical monthly water, sewer and garbage bill in each city, and a guide to every elected seat, appointed manager and top salary. My Address now shows the actual fees on each parcel.',
     'pages': ['/public-money/fees-and-bills', '/who-runs-bay-county', '/my-address']},
    {'date': '2026-10-20', 'title': 'Designed PDF reports, and a new home page',
     'text': 'Export PDF now builds a formatted report on every page, with tables, charts, maps and source links. The home page shows headline numbers and every topic.',
     'pages': ['/', '/my-address', '/public-money/cra-spending', '/public-money/tax-dollars']},
    {'date': '2026-10-20', 'title': 'Tourist tax and sales tax projects',
     'text': 'The 5% bed tax: ten years of collections, how the pennies are split and what Visit Panama City Beach spends. Plus a map of 1,062 half-cent sales tax projects with their status, and the school half-cent.',
     'pages': ['/public-money/tourist-tax', '/public-money/sales-tax-projects']},
    {'date': '2026-10-20', 'title': 'Debt and audit findings',
     'text': 'What every Bay County government owes, including big single payments ahead, and three years of audit findings in plain English, from audits filed with the Florida Auditor General.',
     'pages': ['/public-money/debt', '/public-money/audits']},
    {'date': '2026-10-20', 'title': 'Search, and Hurricane Michael recovery money',
     'text': 'New: search across every page and record. New page tracking FEMA, HUD and state Hurricane Michael money in Bay County, with all 765 FEMA projects.',
     'pages': ['/search', '/public-money/hurricane-michael']},
    {'date': '2026-10-20', 'title': 'My Address',
     'text': 'Look up any Bay County address for a tax estimate, representatives, schools, flood and evacuation zones, and CRA status. Uses the 2026 property roll.',
     'pages': ['/my-address', '/']},
    {'date': '2026-10-20', 'title': 'Amendment 3, and the homestead exemption fix',
     'text': 'New Amendment 3 page with the state\'s estimates for every Bay County government. Calculators now use the inflation-adjusted second homestead exemption ($25,722 for FY2026 bills).',
     'pages': ['/public-money/amendment-3', '/public-money/tax-dollars', '/glossary']},
    {'date': '2026-10-20', 'title': 'Tax dollars and the plain-English guide',
     'text': 'How your tax dollars are allocated: bill calculator, six years of rates and levies, and every government\'s budget. Plus a glossary and tap-to-explain terms across the site.',
     'pages': ['/public-money/tax-dollars', '/glossary', '/public-money/cra-spending']},
    {'date': '2026-10-20', 'title': 'CRA Spending launched',
     'text': 'Map and ledger of Bay County\'s six Community Redevelopment Agencies.',
     'pages': ['/public-money/cra-spending', '/about']},
]


def last_updated(path):
    for c in CHANGES:
        if path in c['pages']:
            return c['date']
    return CHANGES[-1]['date']


def nice(d):
    return date.fromisoformat(d).strftime('%b %-d, %Y')


def updates_page():
    items = ''.join(f'''<li><span class="tl-d">{nice(c["date"])}</span><span><b>{html.escape(c["title"])}.</b> {html.escape(c["text"])} {" · ".join(f'<a href="{p}">{p}</a>' for p in c["pages"])}</span></li>''' for c in CHANGES)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">What's new</span><h1>Updates</h1>
    <p class="lede">New pages, new data and corrections, newest first. Subscribe with any feed reader to get them as they happen: <a href="/updates.xml">RSS feed</a>.</p></div></header>
  <ol class="timeline">{items}</ol>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''


def rss(domain):
    def item(c):
        dt = datetime.fromisoformat(c['date']).replace(hour=12, tzinfo=timezone.utc)
        link = domain + (c['pages'][0] if c['pages'] else '/updates')
        return f'''<item><title>{html.escape(c["title"])}</title><link>{link}</link><guid isPermaLink="false">{c["date"]}-{html.escape(c["title"])}</guid><pubDate>{format_datetime(dt)}</pubDate><description>{html.escape(c["text"])}</description></item>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BayCounty.me updates</title><link>{domain}/updates</link><description>New pages, data and corrections on BayCounty.me</description><language>en-us</language>
{''.join(item(c) for c in CHANGES)}
</channel></rss>
'''
