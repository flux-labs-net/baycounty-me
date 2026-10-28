#!/usr/bin/env python3
"""Official election results for every Bay County election since 2016 -> data/elections/results.json.

    python3 data/elections/scripts/fetch_results.py            # refresh: re-reads open elections, adds new ones
    python3 data/elections/scripts/fetch_results.py --all      # re-read every election

Source: the Supervisor of Elections' election night reporting site (enr.electionsfl.org/BAY, run by VR Systems for
the SOE). The list of elections comes from the SOE's results archive (voterfocus.com enrarchive.php, the page shown on
bayvotesfl.gov/elections/election-results/); each election's Summary page has every contest with votes by Election
Day, early voting and vote by mail. Nothing from before 2016 (site rule).

The archive also lists per-city views of a municipal election day (e.g. "Parker Election" beside "Municipal Super
Tuesday") and the 2018 machine and manual recounts. The city views repeat contests already in the countywide
election, so a contest is kept once per election day. Recount figures replace the first count for the contests that
were recounted (the recount is the certified result).

A closed election is read once; elections in the last 60 days are re-read on every run, so election night results
fill in as the SOE posts them (the refresh workflow runs this every morning and every 20 minutes on election night).
"""
import argparse, datetime as dt, html, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'results.json')
ENR = 'https://enr.electionsfl.org/BAY'
ARCHIVE = 'https://www.voterfocus.com/enr_php/enrarchive.php?county=Bay&election='
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 BayCounty.me results reader'
FIRST_YEAR = 2016
CITY = r'(Panama City Beach|Panama City|Lynn Haven|Mexico Beach|Callaway|Springfield|Parker)'


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def txt(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def num(s):
    s = txt(s).replace(',', '').replace('%', '')
    if s in ('', '-'):
        return None  # a dash: 1 to 29 votes, withheld by law (s. 98.0981(3)(a))
    try:
        return float(s) if '.' in s else int(s)
    except ValueError:
        return None


def archive():
    """[(election_id, date, name)] from the SOE results archive, 2016 on."""
    t = get(ARCHIVE)
    out = []
    for eid, d, name in re.findall(r'value="BAY\|(\d+)"[^>]*>\s*\((\d\d/\d\d/\d{4})\)\s*([^<]+)', t):
        m, dd, y = d.split('/')
        if int(y) >= FIRST_YEAR:
            out.append((int(eid), f'{y}-{m}-{dd}', txt(name)))
    return out


def kind_of(name):
    n = name.lower()
    if 'recount' in n:
        return 'recount'
    if 'presidential preference' in n:
        return 'presidential preference primary'
    if 'runoff' in n:
        return 'runoff'
    if 'primary' in n:
        return 'primary'
    if 'general' in n:
        return 'general'
    if 'recall' in n:
        return 'recall'
    if 'referendum' in n and not re.search('municipal', n):
        return 'referendum'
    return 'municipal'


def summary(eid):
    t = get(f'{ENR}/{eid}/Summary/')
    t = re.sub(r'src="data:[^"]*"', '', t)
    t = re.sub(r'<(script|style|svg)[^>]*>.*?</\1>', '', t, flags=re.S)
    head = txt(t[:t.find('showFavorites')] if 'showFavorites' in t else t[:20000])
    def stat(label):
        m = re.search(label + r':\s*([\d,./%]+(?:\s*/\s*[\d,]+)?)', head)
        return m.group(1) if m else None
    pr = stat('Precincts Reporting') or ''
    prm = re.match(r'(\d+)\s*/\s*(\d+)', pr)
    upd = re.search(r'last updated at:\s*([\d/]+ [\d:]+ [ap]m)', head, re.I)
    info = {'registered_voters': num(stat('Registered Voters') or ''), 'ballots_cast': num(stat('Ballots Cast') or stat('Ballots Counted') or ''),
            'turnout_pct': num(stat('Voter Turnout') or ''), 'precincts_reporting': int(prm.group(1)) if prm else None,
            'precincts_total': int(prm.group(2)) if prm else None,
            'complete': bool(re.search(r'Election Day:\s*Completely Reported', head)) or (bool(prm) and prm.group(1) == prm.group(2)),
            'updated': None}
    if upd:
        try:
            info['updated'] = dt.datetime.strptime(upd.group(1).upper(), '%m/%d/%Y %I:%M:%S %p').isoformat()
        except ValueError:
            pass
    contests = []
    blocks = re.split(r'<div id="(\d+)" class="Race row">', t)
    for i in range(1, len(blocks), 2):
        cid, b = int(blocks[i]), blocks[i + 1]
        nm = re.search(r'<label>([^<]+)</label>', b)
        if not nm:
            continue
        stats = dict((txt(k).rstrip(':').lower().replace(' ', ''), num(v)) for k, v in re.findall(r'RaceStatsLabel[^>]*>(.*?)</div>\s*<div class="RaceStatsValue[^>]*>(.*?)</div>', b, re.S))
        cols = [txt(h) for h in re.findall(r'<th class="DetailResultsHeader[^"]*">(.*?)</th>', b, re.S)]
        tbody = re.search(r'<table class="DetailResults".*?<tbody>(.*?)</tbody>', b, re.S)
        choices = []
        for row in re.findall(r'<tr>(.*?)</tr>', tbody.group(1) if tbody else '', re.S):
            cm = re.search(r'<td class="ChoiceColumn">(.*?)<div', row, re.S)
            cells = [num(c) for c in re.findall(r'<td class="DetailResultsColumn[^"]*">(.*?)</td>', row, re.S)]
            if not cm:
                continue
            label = txt(cm.group(1))
            if label.upper() in ('OVER VOTES', 'UNDER VOTES'):  # older elections list these as rows, not stats
                tv = [c for c in cells if c is not None]
                stats[label.lower().replace(' ', '')] = tv[-2] if len(tv) > 1 and isinstance(tv[-1], float) else (tv[-1] if tv else None)
                continue
            pm = re.match(r'(.*?)\s*\(([A-Z]{2,4})\)$', label)
            ch = {'choice': pm.group(1) if pm else label, 'party': pm.group(2) if pm else None}
            for c, v in zip(cols, cells):
                ch[{'Election Day': 'election_day', 'Early Votes': 'early_voting', 'Vote By Mail': 'vote_by_mail', 'Provisional': 'provisional',
                    'Total Votes': 'votes', 'Percentage': 'pct'}.get(c, c.lower().replace(' ', '_'))] = v
            choices.append(ch)
        if not choices:  # some elections only have the simple view: choice, bar, percent, votes
            for row in b.split('<div class="row ResultsRow">')[1:]:
                row = row.split('<div class="row">')[0]
                cm = re.search(r'<div class="ChoiceColumn[^"]*">(.*?)</div>', row, re.S)
                vals = [num(v) for v in re.findall(r'<div class="ResultsColumn[^"]*"[^>]*>(.*?)</div>', row, re.S)]
                if not cm or not vals:
                    continue
                if len(vals) == 1:  # votes only; the percent is the bar's width
                    w = re.search(r'InnerBar[^"]*" style="width:\s*([\d.]+)%', row)
                    vals = [float(w.group(1)) if w else None] + vals
                label = txt(cm.group(1))
                if label.upper() in ('OVER VOTES', 'UNDER VOTES'):
                    stats[label.lower().replace(' ', '')] = vals[-1]
                    continue
                pm = re.match(r'(.*?)\s*\(([A-Z]{2,4})\)$', label)
                choices.append({'choice': pm.group(1) if pm else label, 'party': pm.group(2) if pm else None, 'votes': vals[-1], 'pct': vals[0]})
        contests.append({'contest_id': cid, 'contest': txt(nm.group(1)), 'over_votes': stats.get('overvotes'),
                         'under_votes': stats.get('undervotes'), 'choices': choices})
    return info, contests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    old = {}
    if os.path.exists(OUT):
        old = {e['election_id']: e for e in json.load(open(OUT))['elections']}
    today = dt.date.today()
    errors, elections = [], []
    for eid, d, name in archive():
        prev = old.get(eid)
        recent = (today - dt.date.fromisoformat(d)).days <= 60
        if prev and prev.get('contests') and all(c['choices'] for c in prev['contests']) and prev.get('complete') and not recent and not a.all:
            elections.append(prev)
            continue
        try:
            info, contests = summary(eid)
        except Exception as ex:
            errors.append({'election_id': eid, 'error': str(ex)[:200]})
            if prev:
                elections.append(prev)
            continue
        elections.append({'election_id': eid, 'date': d, 'name': name, 'kind': kind_of(name),
                          'source_url': f'{ENR}/{eid}/Summary/', **info, 'contests': contests})
        time.sleep(0.5)
    elections.sort(key=lambda e: (e['date'], e['election_id']))
    json.dump({'as_of': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'source': ENR,
               'archive': ARCHIVE, 'first_year': FIRST_YEAR, 'errors': errors, 'elections': elections},
              open(OUT, 'w'), indent=1)
    n = sum(len(e['contests']) for e in elections)
    print(f'{len(elections)} elections, {n} contests, {len(errors)} errors -> {os.path.relpath(OUT)}')
    return 0 if elections else 1


if __name__ == '__main__':
    sys.exit(main())
