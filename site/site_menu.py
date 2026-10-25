"""The site menu: one list that the header, the page picker on the corrections form, link previews and the
site-menu dataset (database + /api/v1/datasets/site-menu) all read.

Six sections, each named for a question people ask. Every section has a 'start here' page shown as a card in the
drop-down and first in the phone menu. Government names come from place.json, so another place gets its own menu
from its own config.
"""
import os
from place import PLACE, OFFICIALS, governments

ROOT = os.path.dirname(os.path.abspath(__file__))
# Checkbook and budget tracker: hidden until a government sends its registers (Jeremy, 2026-10-25). The pages aren't
# built or linked, but the datasets, /api/v1/checkbook, /api/v1/budget-actual and publishing from /finance keep working.
OPEN_BOOKS_PUBLIC = False
ELECTIONS_READY = os.path.exists(os.path.join(ROOT, '..', 'data', 'elections', 'candidates_2026.json'))


def _i(label, href, desc=''):
    return {'label': label, 'href': href, 'desc': desc}


def menu():
    govs = governments()
    return [
        {'label': 'Governments', 'question': 'Who runs what',
         'start': _i(OFFICIALS['label'], OFFICIALS['href'], OFFICIALS['desc']),
         'groups': [{'group': 'Local governments', 'items': [
             *[_i(g['short'], f"/governments/{g['slug']}", g.get('menu_desc') or '') for g in govs if g['kind'] != 'city'],
             *[_i(g['short'], f"/governments/{g['slug']}") for g in govs if g['kind'] == 'city'],
             _i('All governments', '/governments', 'Every local government at a glance'),
             _i('Compare governments', '/compare', 'Budgets, taxes and debt per resident'),
         ]}]},
        {'label': 'Taxes', 'question': 'What you pay',
         'start': _i('My address', '/my-address', 'Your tax bill, districts, fees and meetings for one address'),
         'groups': [{'group': 'What you pay', 'items': [
             _i('Tax dollars', '/public-money/tax-dollars', 'Your property tax bill, slice by slice'),
             _i('Fees & bills', '/public-money/fees-and-bills', 'Tax-bill fees, water and garbage'),
             _i('Exemptions', '/public-money/exemptions', 'Homestead, veterans, seniors and more'),
             _i('Tourist tax', '/public-money/tourist-tax', 'The 5% bed tax visitors pay'),
             _i('Amendment 3', '/public-money/amendment-3', 'What the ballot amendment would change'),
         ]}]},
        {'label': 'Spending', 'question': 'Where it goes',
         'start': _i('Budget explorer', '/public-money/budget-explorer', 'Each budget by fund and department, per resident'),
         'groups': [{'group': 'Where it goes', 'items': [
             *([_i('Budget tracker', '/public-money/budget-tracker', 'Spending against the budget, month by month'),
                _i('Checkbook', '/public-money/checkbook', 'Every payment, from the government\'s own books')] if OPEN_BOOKS_PUBLIC else []),
             _i('Budgets by year', '/public-money/budget-compare', 'Compare any two years, line by line'),
             _i('CRA spending', '/public-money/cra-spending', 'What redevelopment agencies paid for'),
             _i('CRA tax increment', '/public-money/cra-tax-increment', 'Property tax paid to the CRAs, by year'),
             _i('Sales tax projects', '/public-money/sales-tax-projects', 'Half-cent projects: promised vs built'),
             _i('Hurricane Michael', '/public-money/hurricane-michael', 'FEMA, HUD and state recovery money'),
             _i('Debt', '/public-money/debt', 'What each government owes'),
             _i('Spending map', '/public-money/map', 'CRA and sales tax projects, mapped'),
         ]}]},
        {'label': 'Watchdog', 'question': 'Is it spent well?',
         'start': _i('Accountability console', '/public-money/accountability', 'Big projects from approval to close, with open questions'),
         'groups': [{'group': 'Is it spent well?', 'items': [
             _i('Contracts', '/public-money/contracts', 'Who wins them, and how'),
             _i('Vendors', '/public-money/vendors', 'Every company paid, with its contracts and votes'),
             _i('Who gets paid', '/public-money/who-gets-paid', 'Every payment by the tourism agencies'),
             _i('How they voted', '/public-money/votes', 'Every recorded vote on money decisions'),
             _i('Savings finder', '/public-money/savings', 'Where governments could spend less'),
             _i('Audit findings', '/public-money/audits', 'What outside auditors flagged'),
         ]}]},
        {'label': 'People', 'question': "Who decides, and who's connected",
         'start': _i('Connections network', '/connections', 'Who every government paid, and who gave to officials'),
         'groups': [{'group': "Who decides, and who's connected", 'items': [
             *([_i('2026 Elections', '/elections', "Who's running, their platforms and money")] if ELECTIONS_READY else []),
             _i('Campaign gifts', '/connections/campaign-gifts', 'Who funds campaigns, and donors with contracts'),
             _i('Money map', '/connections/money-map', 'Donors, officials and votes on their contracts'),
             _i('Business ties', '/connections/business-ties', "Officials' and candidates' businesses"),
             _i('Shared owners', '/connections/shared-owners', 'Companies with a shared owner giving to one candidate'),
             _i('Nonprofits', '/connections/nonprofits', 'Public money, and officials on their boards'),
         ]}]},
        {'label': 'Take part', 'question': 'Show up, ask, reuse',
         'start': _i('Meetings', '/meetings', 'When every board meets, with agendas'),
         'groups': [{'group': 'Show up, ask, reuse', 'items': [
             _i('Email alerts', '/alerts', 'Weekly updates for your government'),
             _i('Request a record', '/records-request', 'Write a public records request'),
             _i('Letters to officials', '/correspondence', 'What we asked, and what they said'),
             _i('Glossary', '/glossary', 'Government money, explained simply'),
             _i('Open data', '/open-data', 'Download every dataset'),
             _i('API', '/developers', 'Connect apps and AI assistants'),
             _i("What's new", '/updates', 'New pages, data and corrections'),
             _i('About', '/about', 'Sources, method and corrections'),
         ]}]},
    ]


def links(m):
    """Every link in one section: its start page first, then its groups."""
    return ([m['start']] if m.get('start') else []) + [i for g in m.get('groups', []) for i in g['items']]


def site_menu_rows():
    """Rows for the site-menu dataset: one per menu link, English and Spanish, keyed by place."""
    from es_pages import ES_MENU
    rows = []
    for lang, sections in (('en', menu()), ('es', ES_MENU)):
        for si, m in enumerate(sections, 1):
            if m.get('href'):
                rows.append({'place_id': PLACE['id'], 'lang': lang, 'section': m['label'], 'section_order': si, 'question': None,
                             'item_group': None, 'item_order': 0, 'label': m['label'], 'href': m['href'], 'description': None, 'start_here': False})
                continue
            n = 0
            if m.get('start'):
                s = m['start']
                rows.append({'place_id': PLACE['id'], 'lang': lang, 'section': m['label'], 'section_order': si, 'question': m.get('question'),
                             'item_group': None, 'item_order': n, 'label': s['label'], 'href': s['href'], 'description': s['desc'] or None, 'start_here': True})
            for g in m['groups']:
                for i in g['items']:
                    n += 1
                    rows.append({'place_id': PLACE['id'], 'lang': lang, 'section': m['label'], 'section_order': si, 'question': m.get('question'),
                                 'item_group': g['group'], 'item_order': n, 'label': i['label'], 'href': i['href'], 'description': i.get('desc') or None, 'start_here': False})
    return rows
