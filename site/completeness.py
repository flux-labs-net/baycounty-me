"""How complete each government's data is: for every portion of its records (budgets, audited spending, tax rates,
debt, audits, officials), how many of the years since 2016 we have on file, as a percent with a green / yellow / red
status. Published as dataset `data-completeness` and shown near the name on each government page and on the
/governments cards.

Votes from minutes are not in the dataset: they change every few hours as the backfill runs, so the pages read them
live from GET /api/v1/import-progress (completeness.js) and add them to the overall percent.
"""
import html, json, os
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
FIRST = 2016
GREEN, YELLOW = 100, 50   # complete at 100%, partial from 50%, under 50% is mostly missing

PORTIONS = [
    # id, label, page section, what one unit is
    ('budgets', 'Adopted budgets', 'money', 'Fiscal years with the adopted budget on file'),
    ('actuals', 'Audited spending', 'money', 'Fiscal years with audited revenue and spending from the state'),
    ('tax', 'Tax rates', 'rate', 'Fiscal years with the property tax rate on file'),
    ('debt', 'Debt', 'debt', 'Fiscal years with audited debt totals'),
    ('audits', 'Audit findings', 'audits', 'Fiscal years whose audit we have read'),
    ('officials', 'Officials by year', 'who', 'Share of the time since 2016 where we know who held each seat'),
]
LABEL = {p[0]: p[1] for p in PORTIONS}
VOTES_LABEL = 'Votes from minutes'


def status(pct):
    return 'complete' if pct >= GREEN else 'partial' if pct >= YELLOW else 'missing'


STATUS_TEXT = {'complete': 'Complete', 'partial': 'Partial', 'missing': 'Mostly missing'}


def _fy(s):
    try:
        return int(str(s).upper().replace('FY', '')[:4])
    except ValueError:
        return None


def _cur_fy(key, today=None):
    today = today or date.today()
    start = 7 if key == 'schools' else 10
    return today.year + 1 if today.month >= start else today.year


def _years_text(ys):
    """FY2017, FY2019-FY2021 style list of missing years."""
    ys = sorted(ys)
    out, i = [], 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        out.append(f'FY{ys[i]}' if i == j else f'FY{ys[i]}–FY{ys[j]}')
        i = j + 1
    return ', '.join(out)


def _row(g, pid, have, expected, period, missing='', detail='', unit='years'):
    pct = round(100 * have / expected, 1) if expected else 0.0
    pct = min(100.0, pct)
    return {'gov_id': g['key'], 'government': g['short'], 'portion_id': pid, 'portion': LABEL[pid], 'period': period,
            'have': have, 'expected': expected, 'unit': unit, 'pct': pct, 'status': status(pct), 'missing': missing or None,
            'detail': detail, 'page_url': f'/governments/{g["slug"]}#{dict((p[0], p[2]) for p in PORTIONS)[pid]}',
            'source_url': '/data-sources#matrix'}


def rows(today=None):
    from govs import GOVS, profile
    from page_datasets import government_years, officeholder_terms
    today = today or date.today()
    gy = {}
    for r in government_years():
        y = _fy(r['fiscal_year'])
        if y and y >= FIRST:
            gy.setdefault(r['gov_id'], {})[y] = r
    # audited figures stop at the latest year any government has filed with the state
    last_actual = max((y for g in gy.values() for y, r in g.items() if r.get('actual_spending') is not None or r.get('actual_revenue') is not None), default=FIRST)
    seat = {}
    for t in officeholder_terms():
        a = max(date(FIRST, 1, 1), date.fromisoformat(t['start_date'][:10]) if t['start_date'] else date(FIRST, 1, 1))
        b = min(today, date.fromisoformat(t['end_date'][:10]) if t['end_date'] else today)
        d = max(0, (b - a).days)
        s = seat.setdefault(t['gov_id'], [0, 0])
        s[1] += d
        if t['confirmed']:
            s[0] += d
    out = []
    for g in GOVS:
        key = g['key']
        ys = gy.get(key, {})
        cur = _cur_fy(key, today)

        def years(field_ok, last):
            exp = list(range(FIRST, last + 1))
            have = [y for y in exp if y in ys and field_ok(ys[y])]
            return have, exp

        have, exp = years(lambda r: r.get('budget_total') is not None or r.get('general_fund') is not None, cur)
        out.append(_row(g, 'budgets', len(have), len(exp), f'FY{FIRST}–FY{cur}', _years_text(set(exp) - set(have)),
                        'Adopted budget total or General Fund for each fiscal year.'))
        have, exp = years(lambda r: r.get('actual_spending') is not None or r.get('actual_revenue') is not None, last_actual)
        out.append(_row(g, 'actuals', len(have), len(exp), f'FY{FIRST}–FY{last_actual}', _years_text(set(exp) - set(have)),
                        f'From the state\'s Local Government Financial Reports, filed through FY{last_actual}.'))
        have, exp = years(lambda r: r.get('millage') is not None, cur)
        out.append(_row(g, 'tax', len(have), len(exp), f'FY{FIRST}–FY{cur}', _years_text(set(exp) - set(have)),
                        'The property tax rate (millage) adopted for each fiscal year.'))
        audits = [_fy(a.get('fy')) for a in (profile(key).get('audits') or [])]
        audits = sorted({y for y in audits if y and y >= FIRST})
        last_audit = max(audits) if audits else last_actual
        have, exp = years(lambda r: r.get('debt_total') is not None, last_audit)
        out.append(_row(g, 'debt', len(have), len(exp), f'FY{FIRST}–FY{last_audit}', _years_text(set(exp) - set(have)),
                        'Total debt from each year\'s audited financial statements.'))
        exp = list(range(FIRST, last_audit + 1))
        out.append(_row(g, 'audits', len(audits), len(exp), f'FY{FIRST}–FY{last_audit}', _years_text(set(exp) - set(audits)),
                        'Audits filed with the Florida Auditor General, read for findings and the auditor\'s opinion.'))
        ok, tot = seat.get(key, [0, 0])
        if tot:
            yrs_ok, yrs_tot = round(ok / 365.25, 1), round(tot / 365.25, 1)
            r = _row(g, 'officials', yrs_ok, yrs_tot, f'{FIRST}–{today.year}', '',
                     'Seat-years since 2016 where the officeholder is confirmed from a record.', unit='seat-years')
            r['pct'] = min(100.0, round(100 * ok / tot, 1))
            r['status'] = status(r['pct'])
            out.append(r)
    return out


def by_gov(key, rs=None):
    return [r for r in (rs if rs is not None else rows()) if r['gov_id'] == key]


def overall(rs):
    return round(sum(r['pct'] for r in rs) / len(rs)) if rs else 0


def _bar(pct, st):
    return f'<span class="dc-bar"><span class="dc-fill dc-{st}" style="width:{max(2, pct):.0f}%"></span></span>'


def _num(r):
    if r['unit'] == 'years':
        return f'{r["have"]:g} of {r["expected"]:g} yrs'
    return f'{r["pct"]:g}% confirmed'


def chip(key, rs):
    """The percent next to the name: overall share loaded, colored by status. completeness.js adds votes when live."""
    pct = overall(rs)
    st = status(pct)
    tot = sum(r['pct'] for r in rs)
    return (f'<a class="dc-chip dc-{st}" href="#data-status" data-dc-chip data-dc-gov="{key}" data-sum="{tot:g}" data-n="{len(rs)}" '
            f'title="How much of this government\'s data since {FIRST} is loaded"><span class="dc-dot"></span>'
            f'<b data-dc-pct>{pct}%</b> data loaded</a>')


def card_chip(key, rs):
    pct = overall(rs)
    tot = sum(r['pct'] for r in rs)
    return (f'<span class="dc-mini dc-{status(pct)}" data-dc-chip data-dc-gov="{key}" data-sum="{tot:g}" data-n="{len(rs)}">'
            f'<span class="dc-dot"></span><b data-dc-pct>{pct}%</b> loaded</span>')


def _missing(r):
    return f'<small>Missing {html.escape(r["missing"])}</small>' if r['missing'] else ''


def table(key, rs, short):
    """The small status table: one row per portion with a bar, the count and a green / yellow / red status."""
    e = html.escape
    body = ''.join(
        f'<tr><th scope="row"><a href="{e(r["page_url"])}">{e(r["portion"])}</a><small>{e(r["period"])}</small></th>'
        f'<td>{_bar(r["pct"], r["status"])}</td><td class="num">{r["pct"]:.0f}%</td><td class="dc-n">{_num(r)}</td>'
        f'<td class="dc-sc"><span class="dc-st dc-{r["status"]}" title="{STATUS_TEXT[r["status"]]}"><span class="dc-dot"></span><span class="dc-sx">{STATUS_TEXT[r["status"]]}</span></span>'
        f'{_missing(r)}</td></tr>'
        for r in rs)
    votes = (f'<tr data-dc-votes hidden><th scope="row"><a href="/data-sources#progress">{VOTES_LABEL}</a><small>{FIRST}–{date.today().year}, live</small></th>'
             f'<td>{_bar(0, "missing")}</td><td class="num" data-v-pct>…</td><td class="dc-n" data-v-n></td>'
             f'<td class="dc-sc"><span class="dc-st dc-missing" data-v-st><span class="dc-dot"></span><span class="dc-sx">Loading</span></span></td></tr>')
    return f'''<section class="tx-sec dc" id="data-status" aria-labelledby="dcH" data-dc-gov="{key}">
  <div class="sec-hd"><h2 id="dcH" data-tile="Data status">How complete {e(short)}’s data is</h2><span class="muted">Since {FIRST}</span></div>
  <div class="dc-key" aria-hidden="true"><span><span class="dc-dot dc-complete"></span>Complete</span><span><span class="dc-dot dc-partial"></span>Partial ({YELLOW}–99%)</span><span><span class="dc-dot dc-missing"></span>Mostly missing (under {YELLOW}%)</span></div>
  <div class="tablewrap"><table class="dc-t" data-tt="off" data-stack="off"><thead><tr><th scope="col">Records</th><th scope="col"><span class="sr">Progress</span></th><th scope="col" class="num">Loaded</th><th scope="col" class="dc-n">On file</th><th scope="col" class="dc-sh"><span>Status</span></th></tr></thead>
  <tbody>{body}{votes}</tbody></table></div>
  <p class="muted small">Counts every fiscal year since {FIRST} we have a record for. Votes update live as we read each board’s minutes. Data: <a href="/api/v1/datasets/data-completeness">data-completeness</a> and <a href="/api/v1/import-progress">import-progress</a>. <a href="/data-sources">Where our data comes from</a>.</p>
</section>'''

