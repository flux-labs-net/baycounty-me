#!/usr/bin/env python3
"""Crime counts and police staffing for the county's law enforcement agencies -> data/safety/<county>/fbi.json.

    python3 data/safety/fetch_cde.py [--county bay]

Source: the FBI Crime Data Explorer (cde.ucr.cjis.gov), the public site that publishes what each agency reports to the
FBI's Uniform Crime Reporting program. Agencies are the ones in data/safety/<county>/agencies.json with an fbi_ori.

- Offenses: one call per agency and offense (violent and property totals plus the eight main offenses), monthly counts
  summed by year. A year with no reported months is stored as null (not reported), never as zero.
- The statewide rate per 100,000 people for each offense and year comes with every call and is kept once,
  for years when agencies covering at least 75% of the state reported (2021 is left out).
- Staffing: sworn officers and civilian employees on Oct 31 each year (the FBI's police employee count).

Florida agencies sent the FBI one yearly summary (filed under December) until 2024 and moved to monthly incident
reports (NIBRS, through FDLE's FIBRS) in 2025, so 2025 counts are not directly comparable with earlier years. Nothing
was reported to the FBI by Florida agencies for 2021, so a year with no violent or property crime at all is dropped as
not reported. The current year is kept with the number of months reported so far. Years before 2016 are not read (data/entities/cutoff.py).
"""
import argparse, datetime as dt, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'entities'))
import cutoff  # noqa: E402

API = 'https://cde.ucr.cjis.gov/LATEST'
UA = 'Mozilla/5.0 (compatible; BayCounty.me public data reader; +https://baycounty.me/about)'
STATE_NAME = 'Florida'
OFFENSES = [('V', 'Violent crime', 'violent'), ('P', 'Property crime', 'property'),
            ('HOM', 'Murder', 'violent'), ('RPE', 'Rape', 'violent'), ('ROB', 'Robbery', 'violent'), ('ASS', 'Aggravated assault', 'violent'),
            ('BUR', 'Burglary', 'property'), ('LAR', 'Larceny-theft', 'property'), ('MVT', 'Motor vehicle theft', 'property'), ('ARS', 'Arson', 'property')]


def get(path, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={'User-Agent': UA, 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def by_year(series, first, last):
    """Monthly {'MM-YYYY': n} -> {year: total or None when no month was reported}, plus months reported."""
    out = {}
    for y in range(first, last + 1):
        vals = [series.get(f'{m:02d}-{y}') for m in range(1, 13)]
        got = [v for v in vals if v is not None]
        out[str(y)] = {'count': sum(got) if got else None, 'months': len(got)}
    return out


def offenses(ori, first, last, state):
    rows = {}
    for code, label, group in OFFENSES:
        d = get(f'/summarized/agency/{ori}/{code}?from=01-{first}&to=12-{last}')
        act = (d.get('offenses') or {}).get('actuals') or {}
        key = next((k for k in act if k.endswith(' Offenses') and not k.startswith(('Florida ', 'United States '))), None)
        clr = next((k for k in act if k.endswith(' Clearances') and not k.startswith(('Florida ', 'United States '))), None)
        pop = (d.get('populations') or {}).get('population') or {}
        pkey = next((k for k in pop if k not in ('Florida', 'United States')), None)
        rates = (d.get('offenses') or {}).get('rates') or {}
        st = rates.get(f'{STATE_NAME} Offenses') or {}
        for y in range(first, last + 1):  # statewide rate per 100,000 people: monthly rates added up over a full year
            vals = [st.get(f'{m:02d}-{y}') for m in range(1, 13)]
            cov = (((d.get('tooltips') or {}).get('Percent of Population Coverage') or {}).get(STATE_NAME) or {}).get(f'12-{y}')
            if all(v is not None for v in vals) and (cov or 0) >= 75:  # 2021: only half the state reported
                state.setdefault(str(y), {})[code] = round(sum(vals), 1)
        yrs = by_year(act.get(key) or {}, first, last)
        cl = by_year(act.get(clr) or {}, first, last)
        for y, v in yrs.items():
            p = (pop.get(pkey) or {}).get(f'12-{y}') if pkey else None
            rows.setdefault(y, {})[code] = {'label': label, 'group': group, 'count': v['count'], 'cleared': cl[y]['count'], 'months': v['months'], 'population': p}
        time.sleep(.3)
    return rows


def staffing(ori, first, last):
    d = get(f'/pe/agency/{ori}?from={first}&to={last}')
    act, pop = d.get('actuals') or {}, ((d.get('populations') or {}).get('Participated Population') or {})
    rate = ((d.get('rates') or {}).get('Law Enforcement Employees per 1,000 People') or {})
    out = {}
    for y in range(first, last + 1):
        y = str(y)
        mo, fo, mc, fc = (act.get(k, {}).get(y) for k in ('Male Officers', 'Female Officers', 'Male Civilians', 'Female Civilians'))
        if all(v is None for v in (mo, fo, mc, fc)):
            continue
        out[y] = {'male_officers': mo, 'female_officers': fo, 'officers': (mo or 0) + (fo or 0), 'civilians': (mc or 0) + (fc or 0),
                  'per_1000': rate.get(y), 'population': pop.get(y)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    a = ap.parse_args()
    ag = json.load(open(os.path.join(HERE, a.county, 'agencies.json')))
    path = os.path.join(HERE, a.county, 'fbi.json')
    old = json.load(open(path)) if os.path.exists(path) else {'agencies': {}}
    first, last = int(cutoff.FIRST_DATE[:4]), dt.date.today().year
    out, errors, state = {}, [], {}
    for r in ag['agencies']:
        ori = r.get('fbi_ori')
        if not ori or ori in out:
            continue
        try:
            off = offenses(ori, first, last, state)
            # A year with no violent and no property crime at all is a year the agency did not report (2021 statewide,
            # Lynn Haven 2022); a real year with none of either does not happen here.
            off = {y: v for y, v in off.items() if (v['V']['count'] or 0) + (v['P']['count'] or 0) > 0}
            out[ori] = {'agency_id': r['agency_id'], 'offenses': off, 'staffing': staffing(ori, first, last)}
            print(f"{r['agency']}: {len(off)} years of offenses, {len(out[ori]['staffing'])} years of staffing")
        except Exception as e:  # noqa: BLE001  keep what we had
            errors.append({'ori': ori, 'error': f'{type(e).__name__}: {e}'[:300]})
            if ori in old['agencies']:
                out[ori] = old['agencies'][ori]
            print(f"{r['agency']}: failed ({e}); kept what was on file", file=sys.stderr)
    json.dump({'as_of': dt.date.today().isoformat(), 'source_url': 'https://cde.ucr.cjis.gov/', 'errors': errors,
               'state': {'name': STATE_NAME, 'per_100k': state or old.get('state', {}).get('per_100k', {})}, 'agencies': out},
              open(path, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(out)} agencies -> {path}')


if __name__ == '__main__':
    main()
