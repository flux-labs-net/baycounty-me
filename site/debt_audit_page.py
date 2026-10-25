"""Shared helpers for the debt and audit records (data/debt_audit/debt_audit.json): short names, fiscal-year labels and
finding ids. The records are drawn on each government's page (site/gov_detail.py); /public-money/debt and
/public-money/audits now redirect there and to /compare."""
import json, os, re, html
from city_filter import city_bar, data_g, by_city, gkey, KEYS, LABEL

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'data', 'debt_audit', 'debt_audit.json')

SHORT = [('Bay County', 'Bay County'), ('Bay District Schools', 'Bay District Schools'), ('City of Panama City Beach', 'Panama City Beach'),
         ('Panama City Beach Community', 'Panama City Beach CRA'), ('City of Panama City', 'Panama City'), ('Panama City Community Redevelopment', 'Panama City CRA'),
         ('Panama City Port', 'Port Panama City'), ('Panama City-Bay County Airport', 'Airport district'), ('City of Lynn Haven', 'Lynn Haven'),
         ('City of Callaway', 'Callaway'), ('City of Springfield', 'Springfield'), ('City of Parker', 'Parker'), ('City of Mexico Beach', 'Mexico Beach')]
TYPES = [('revenue_bonds', 'Revenue bonds'), ('general_obligation_bonds', 'Voter-approved (GO) bonds'), ('notes_loans', 'Notes and loans'),
         ('certificates_of_participation', 'Certificates of participation'), ('leases', 'Leases'), ('sbitas', 'Software subscriptions'), ('financed_purchases', 'Financed purchases')]


def finding_id(gov_short, a, f):
    return 'f-' + re.sub(r'[^a-z0-9]+', '-', f"{gov_short} {fy_label(a['fy'])} {f.get('id') or ''}".lower()).strip('-')


def short(g):
    for k, v in SHORT:
        if g.startswith(k):
            return v
    return g


def e(s):
    return html.escape(str(s if s is not None else ''))


def money(n, digits=1):
    if n is None:
        return '—'
    n = float(n)
    if abs(n) >= 1e6:
        return f'${n/1e6:,.{digits}f}M'
    if abs(n) >= 1e3:
        return f'${n/1e3:,.0f}K'
    return f'${n:,.0f}'


def fy_label(s):
    m = re.match(r'(FY\d{4})', s or '')
    return m.group(1) if m else (s or '')


def load():
    return json.load(open(SRC))
