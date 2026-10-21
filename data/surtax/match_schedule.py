"""Join the county's surtax program schedule (programmed dollars by year) to the surtax GIS projects.

Input:  ../tourism/tourism_surtax.json  infra_surtax.county_program_schedule (105 county projects from the county's
        "Public Works First 5 Years / List of Projects" PDFs) and infra_surtax.projects (the county GIS layer).
Output: schedule_matches.json  {matches: [...], unmatched: [...], review: [...], match_rate}
Run by data/build.py; tourism_page / the public-money map read the matches to show programmed amounts.

Match rules (same government only: the schedule is Bay County's own list, so only "Bay County" GIS projects):
  * names are reduced to road/place words: lowercase, numbers kept, generic words (road, rd, ave, phase, grant,
    project, sidewalk...) and funding notes in parentheses dropped; road-name abbreviations normalized (CR, SR, St, Dr...);
  * score = shared distinctive tokens / tokens in the shorter name, + a bonus when the schedule's extra words
    (from, to, @, between) name the same cross streets, and when the category word agrees (bridge, sidewalk, turn lane,
    intersection, drainage/stormwater, resurfacing/paving);
  * confident: exact normalized name, or every distinctive word of the shorter name is shared, the category agrees, and no
    other GIS project scores as high (ties, e.g. several GIS segments with one road name, go to review);
  * "(program)" rows, transfers and "Future Capacity Project" are county-wide lines with no single place: never matched.
Programmed amounts are attached with the schedule's source_url. Nothing is copied to a project the match isn't sure of.
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', 'tourism', 'tourism_surtax.json')

ABBR = {'road': 'rd', 'avenue': 'ave', 'av': 'ave', 'street': 'st', 'drive': 'dr', 'boulevard': 'blvd', 'parkway': 'pkwy', 'highway': 'hwy', 'circle': 'cir',
        'lane': 'ln', 'county': 'cr', 'c.r.': 'cr', 's.r.': 'sr', 'state': 'sr', 'east': 'e', 'west': 'w', 'north': 'n', 'south': 's', 'u.s.': 'us', 'fb': 'front beach'}
GENERIC = set('rd ave st dr blvd pkwy hwy cir ln road the and of at to from between project projects improvement improvements phase ph i ii iii iv grant surtax non sales tax funds '
              'program design construction construct replacement replace repair rehabilitation rehab sidewalk sidewalks bike lane lanes turn left right sb nb eb wb intersection '
              'stabilization drainage paving resurfacing widening connector regional facility land purchase study model basin outfall bridge'.split())
CAT = [('bridge', r'bridge'), ('sidewalk', r'sidewalk|multi.?use|bike|path|trail'), ('turn', r'turn lane|intersection|@'), ('drain', r'drain|stormwater|outfall|basin|nov|v-?\d|dep'),
       ('pave', r'resurfac|paving|dirt|stabiliz|road rehab|reconstruct')]
NO_PLACE = re.compile(r'\(program\)|transfer|future capacity|annual resurfacing program', re.I)


def norm_tokens(s):
    s = (s or '').lower()
    s = re.sub(r'\$[\d,.]+k?|\d+%', ' ', s)
    s = re.sub(r'\((?:[^)]*(grant|fdot|lms|dep|hmgp|cdbg|surtax|funds|trip|pcb|lh|county|design|construction|non)[^)]*)\)', ' ', s)
    s = s.replace('&', ' and ').replace('@', ' at ')
    toks = re.sub(r'[^a-z0-9. ]', ' ', s).split()
    out = []
    for t in toks:
        t = t.strip('.')
        t = ABBR.get(t, t)
        out.extend(t.split())
    return out


def core(s):
    """Distinctive tokens of the main name (before 'from/to/between/@/(')."""
    main = re.split(r'\(|\bfrom\b|\bbetween\b|\s@\s|\bat\b', (s or '').lower())[0]
    return {t for t in norm_tokens(main) if t not in GENERIC and len(t) > 1}


def all_tokens(s):
    return {t for t in norm_tokens(s) if t not in GENERIC and len(t) > 1}


def cats(s):
    s = (s or '').lower()
    return {c for c, rx in CAT if re.search(rx, s)}


def build():
    d = json.load(open(T))
    inf = d['infra_surtax']
    sched = inf['county_program_schedule']
    gis = [(i, p) for i, p in enumerate(inf['projects']) if p['government'] == 'Bay County']
    gis_core = {i: core(p['name']) for i, p in gis}
    gis_all = {i: all_tokens(p['name'] + ' ' + (p.get('location') or '') + ' ' + (p.get('description') or '')[:200]) for i, p in gis}
    gis_cat = {i: cats(p['name'] + ' ' + (p.get('category') or '')) for i, p in gis}
    exact = collections.defaultdict(list)
    for i, p in gis:
        exact[' '.join(norm_tokens(p['name']))].append(i)
    matches, unmatched, review = [], [], []
    for si, s in enumerate(sched):
        rec = {'schedule_index': si, 'schedule_name': s['name'], 'category': s['category'], 'programmed_total': s['programmed_total'], 'fy_amounts': s['fy_amounts'],
               'schedule_status': s['status'], 'source_url': s['source_url']}
        if NO_PLACE.search(s['name']):
            unmatched.append(dict(rec, reason='county-wide program line, no single location')); continue
        key = ' '.join(norm_tokens(s['name']))
        if len(exact.get(key, [])) == 1:
            matches.append(dict(rec, project_index=exact[key][0], project_name=inf['projects'][exact[key][0]]['name'], method='exact name', score=1.0)); continue
        sc, sa, scat = core(s['name']), all_tokens(s['name']), cats(s['name'] + ' ' + s['category'])
        if not sc:
            unmatched.append(dict(rec, reason='no distinctive name words')); continue
        scored = []
        for i, p in gis:
            shared = sc & gis_core[i]
            if not shared:
                continue
            base = len(shared) / min(len(sc), len(gis_core[i]) or 1)
            extra = sa - sc
            cross = len(extra & gis_all[i]) / len(extra) if extra else 0
            catok = bool(scat & gis_cat[i])
            scored.append((round(base + 0.5 * cross + (0.25 if catok else 0), 3), i, sorted(shared), catok, round(cross, 2), base))
        scored.sort(reverse=True)
        if not scored:
            unmatched.append(dict(rec, reason='no GIS project shares its road or place name')); continue
        top = scored[0]
        tied = [x for x in scored if x[0] == top[0]]
        if top[5] >= 0.99 and top[3] and len(tied) == 1:
            matches.append(dict(rec, project_index=top[1], project_name=inf['projects'][top[1]]['name'], method='name words + category' + (' + cross streets' if top[4] else ''),
                                score=top[0], shared_words=top[2]))
        else:
            why = 'several GIS projects score the same' if len(tied) > 1 else ('category differs' if not top[3] else 'not every name word matches (possible misspelling)')
            review.append(dict(rec, reason=why, candidates=[{'project_index': x[1], 'project_name': inf['projects'][x[1]]['name'], 'score': x[0], 'shared_words': x[2]} for x in scored[:4]]))
            unmatched.append(dict(rec, reason='uncertain: ' + why))
    # one GIS project can only take one schedule line per name; two schedule lines on one project (phases) are both kept
    used = collections.Counter(m['project_index'] for m in matches)
    total = sum(s['programmed_total'] or 0 for s in sched)
    mt = sum(m['programmed_total'] or 0 for m in matches)
    return {'about': __doc__.strip().split('\n\n')[0], 'method': __doc__.strip().split('\n\n', 1)[1],
            'schedule_rows': len(sched), 'matched_rows': len(matches), 'match_rate': round(len(matches) / len(sched), 3),
            'programmed_total': total, 'programmed_matched': mt, 'programmed_match_rate': round(mt / total, 3) if total else None,
            'exact_name_matches': sum(1 for m in matches if m['method'] == 'exact name'),
            'gis_projects_with_two_schedule_lines': [k for k, n in used.items() if n > 1],
            'matches': matches, 'unmatched': unmatched, 'review': review}


def main():
    out = build()
    json.dump(out, open(os.path.join(HERE, 'schedule_matches.json'), 'w'), indent=1, ensure_ascii=False)
    print(f"surtax schedule: {out['matched_rows']}/{out['schedule_rows']} rows matched ({out['match_rate']:.0%}; {out['exact_name_matches']} exact), "
          f"${out['programmed_matched']:,.0f} of ${out['programmed_total']:,.0f} programmed ({out['programmed_match_rate']:.0%}); review {len(out['review'])}")


if __name__ == '__main__':
    main()
