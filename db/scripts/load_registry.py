"""Load the private business registry (schema `registry`, migration 0031) from data/sunbiz.

Usage:
  DATABASE_URL=postgresql://... python3 db/scripts/load_registry.py [county ...]     # default: every county with data

For each county with data/sunbiz/<county>/entities.csv.gz, runs data/sunbiz/build_sunbiz.py's build() and replaces
that county's entities, people, roles and gift matches in one transaction. Shared-owner groups are upserted so an
admin's review_status survives a reload; groups that no longer appear are deleted. Confirmed groups are then
rewritten to the public shared_owner_groups table (business names only).
Then, when data/nonprofits/<county>/orgs.csv.gz exists, loads nonprofit board members (migration 0034): board people
and seats are replaced, official name matches are upserted so their review survives, and confirmed matches are
rewritten to public.nonprofit_officials.
Then gifts over the per-election limit (data/campaign/over_limit.py, migration 0038) are upserted into
registry.limit_cases so an admin's review and resolution survive; confirmed and resolved cases are rewritten to
public.over_limit_gifts.
Officer and agent names go only to this private schema. Street addresses are never stored.
Run by .github/workflows/sync-db.yml after load.py.
"""
import json, os, subprocess, sys
import psycopg
from psycopg.types.json import Jsonb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'sunbiz'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'nonprofits'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'campaign'))
import build_sunbiz  # noqa: E402
import over_limit  # noqa: E402
import build_nonprofits  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def counties():
    d = os.path.join(ROOT, 'data', 'sunbiz')
    return sorted(k for k in os.listdir(d) if os.path.exists(os.path.join(d, k, 'entities.csv.gz')))


def git_sha():
    try:
        return subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def _copy(cur, table, cols, rows):
    with cur.copy(f'copy {table} ({", ".join(cols)}) from stdin') as cp:
        for r in rows:
            cp.write_row(r)


def load_county(conn, county):
    res = build_sunbiz.build(county)
    E, P, R, G, F = res['entities'], res['people'], res['roles'], res['gifts'], res['findings']
    with conn.transaction():
        cur = conn.cursor()
        for t in ('roles', 'gift_matches', 'people', 'entities'):
            cur.execute(f'delete from registry.{t} where county = %s', (county,))
        _copy(cur, 'registry.entities', ['county', 'doc_number', 'name', 'name_key', 'status', 'filing_type', 'nonprofit', 'file_date',
                                         'last_report_year', 'principal_city', 'principal_zip', 'principal_in_county'],
              ((county, e['doc_number'], e['name'], e['key'], e['status'], e['filing_type'], e['nonprofit'], e['file_date'],
                e['last_report_year'], e['city'], e['zip5'], e['in_county_principal']) for e in E.values()))
        _copy(cur, 'registry.people', ['county', 'person_key', 'display_name', 'name_key', 'city', 'zip5', 'resident', 'address_hash',
                                       'entities_as_officer', 'active_entities_as_officer', 'entities_as_agent', 'corporate_officer', 'agent_service'],
              ((county, p['person_key'], ' '.join(p['display_name'].split()), p['name_key'], p['city'], p['zip5'], p['resident'], p['address_hash'],
                p['entities_as_officer'], p['active_entities_as_officer'], p['entities_as_agent'], p['corporate_officer'], p['agent_service'])
               for p in P.values()))
        seen = set()
        role_rows = []
        for r in R:
            if not r.get('person_key'):
                continue
            k = (r['person_key'], r['doc_number'], r['role'], r['title'])
            if k in seen:
                continue
            seen.add(k)
            role_rows.append((county,) + k)
        _copy(cur, 'registry.roles', ['county', 'person_key', 'doc_number', 'role', 'title'], role_rows)
        _copy(cur, 'registry.gift_matches', ['county', 'gift_source', 'candidate', 'office', 'government_key', 'contributor', 'amount', 'gift_date',
                                             'doc_number', 'match_method', 'report_url'],
              ((county, g['src'], g['candidate'], g.get('office'), build_sunbiz.gov_for(g), g['name'].strip(), g.get('amount'),
                g['date'] if g.get('date') and len(str(g['date'])) == 10 else None, g['doc_number'], g['match_method'], g.get('report_url')) for g in G))
        keep = []
        for f in F:
            keep.append((f['group_id'], f['candidate']))
            cur.execute('''insert into registry.shared_owner_groups (county, group_id, candidate, office, government_key, election, n_businesses, n_checks,
                             n_people, combined_amount, all_at_1000, same_day, businesses, person_keys, report_url, loaded_at)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                           on conflict (county, group_id, candidate) do update set office = excluded.office, government_key = excluded.government_key,
                             election = excluded.election, n_businesses = excluded.n_businesses, n_checks = excluded.n_checks, n_people = excluded.n_people,
                             combined_amount = excluded.combined_amount, all_at_1000 = excluded.all_at_1000, same_day = excluded.same_day,
                             businesses = excluded.businesses, person_keys = excluded.person_keys, report_url = excluded.report_url, loaded_at = now()''',
                        (county, f['group_id'], f['candidate'], f['office'], f['government_key'], f['election'], f['n_businesses'], f['n_checks'],
                         f['n_people'], f['combined_amount'], f['all_at_1000'], f['same_day'], Jsonb(f['businesses']), Jsonb(f['person_keys']), f['report_url']))
        cur.execute('select group_id, candidate from registry.shared_owner_groups where county = %s', (county,))
        gone = [x for x in cur.fetchall() if tuple(x) not in set(keep)]
        for gid, cand in gone:
            cur.execute('delete from registry.shared_owner_groups where county = %s and group_id = %s and candidate = %s', (county, gid, cand))
        cur.execute('select registry.publish_all(%s)', (county,))  # public rows for groups an admin confirmed (migration 0032)
        published = cur.fetchone()[0]
        s = build_sunbiz.summary(res)
        s['published_rows'] = published
        cur.execute('insert into registry.loads (county, git_sha, entities, people, roles, gifts, groups, summary) values (%s,%s,%s,%s,%s,%s,%s,%s)',
                    (county, git_sha(), len(E), len(P), len(role_rows), len(G), len(F), Jsonb(s)))
    print(f'registry {county}: {len(E)} entities, {len(P)} people, {len(role_rows)} roles, {len(G)} gift lines, {len(F)} shared-owner groups')
    if os.path.exists(os.path.join(ROOT, 'data', 'nonprofits', county, 'orgs.csv.gz')):
        load_boards(conn, county, res)
    load_limits(conn, county)


LIMIT_COLS = ['candidate', 'office', 'government_key', 'election', 'election_year', 'election_phase', 'contributor', 'contributor_type', 'spellings',
              'n_items', 'gross_amount', 'refunds', 'net_amount', 'over_by', 'possible_double_entry', 'auto_resolution', 'items', 'first_date',
              'last_date', 'report_url']


def load_limits(conn, county):
    cur = conn.cursor()
    cur.execute("select to_regclass('registry.limit_cases') is not null")
    if not cur.fetchone()[0]:
        print('registry: limit_cases missing (migration 0038), over-limit gifts skipped')
        return
    cs = over_limit.cases(county)
    with conn.transaction():
        for c in cs:
            vals = [Jsonb(c[k]) if k in ('spellings', 'items') else c[k] for k in LIMIT_COLS]
            cur.execute(f'''insert into registry.limit_cases (county, case_id, {', '.join(LIMIT_COLS)}, loaded_at)
                            values (%s, %s, {', '.join(['%s'] * len(LIMIT_COLS))}, now())
                            on conflict (county, case_id) do update set {', '.join(f'{k} = excluded.{k}' for k in LIMIT_COLS)}, in_current_data = true, loaded_at = now()''',
                        [county, c['case_id']] + vals)
        keep = {c['case_id'] for c in cs}
        # a case the reports no longer show (an amended report, a corrected file) is kept once reviewed, so its
        # resolution stays on record; unreviewed ones are dropped
        cur.execute('select case_id, review_status from registry.limit_cases where county = %s', (county,))
        for cid, st in cur.fetchall():
            if cid in keep:
                continue
            if st == 'unreviewed':
                cur.execute('delete from registry.limit_cases where county = %s and case_id = %s', (county, cid))
            else:
                cur.execute('update registry.limit_cases set in_current_data = false where county = %s and case_id = %s', (county, cid))
        cur.execute('select registry.publish_limit_all(%s)', (county,))
        published = cur.fetchone()[0]
    print(f'registry {county}: {len(cs)} over-limit cases, {published} published')


def load_boards(conn, county, sunbiz_res):
    cur = conn.cursor()
    cur.execute("select to_regclass('registry.board_people') is not null")
    if not cur.fetchone()[0]:
        print('registry: board tables missing (migration 0034), nonprofit boards skipped')
        return
    res = build_nonprofits.build(county, sunbiz_res)
    O, S, P = res['orgs'], res['seats'], res['people']
    with conn.transaction():
        cur.execute('delete from registry.board_seats where county = %s', (county,))
        cur.execute('delete from registry.board_people where county = %s', (county,))
        _copy(cur, 'registry.board_people', ['county', 'board_key', 'display_name', 'name_key', 'middle_initial', 'n_nonprofits', 'n_current', 'n_current_civic', 'n_seats',
                                             'official_id', 'official_name', 'official_roles', 'same_name_people', 'registry_person_keys', 'linked_person_keys',
                                             'n_businesses', 'n_donor_businesses', 'donor_gifts_total', 'businesses'],
              ((county, p['board_key'], p['display_name'], p['name_key'], p['mid'] or None, p['n_nonprofits'], p['n_current'], p['n_current_civic'], p['n_seats'],
                p['official_id'], p['official_name'], Jsonb(p['official_roles']), p['same_name_people'], Jsonb(p['registry_person_keys']),
                Jsonb(p['linked_person_keys']), p['n_businesses'], p['n_donor_businesses'], p['donor_gifts_total'], Jsonb(p['businesses'])) for p in P.values()))
        _copy(cur, 'registry.board_seats', ['county', 'board_key', 'nonprofit_id', 'nonprofit_name', 'ein', 'source', 'name_as_filed', 'title', 'tax_year',
                                            'board', 'current', 'roles', 'hours', 'compensation', 'object_id', 'source_url'],
              ((county, s['board_key'], s['nonprofit_id'], O[s['nonprofit_id']]['name'], O[s['nonprofit_id']]['ein'] or None, s['source'], s['raw_name'],
                s['title'] or None, s['tax_year'], s['board'], s['current'], s['roles'] or None, s['hours'], s['compensation'], s['object_id'], s['source_url'])
               for s in S))
        keep = set()
        for p in P.values():
            if p['official_id']:
                keep.add((p['board_key'], p['official_id']))
                cur.execute('''insert into registry.board_official_matches (county, board_key, official_id, official_name, loaded_at) values (%s,%s,%s,%s, now())
                               on conflict (county, board_key, official_id) do update set official_name = excluded.official_name, loaded_at = now()''',
                            (county, p['board_key'], p['official_id'], p['official_name']))
        cur.execute('select board_key, official_id from registry.board_official_matches where county = %s', (county,))
        for bk, oid in [tuple(x) for x in cur.fetchall()]:
            if (bk, oid) not in keep:
                cur.execute('delete from registry.board_official_matches where county = %s and board_key = %s and official_id = %s', (county, bk, oid))
        cur.execute('select registry.publish_board_officials(%s)', (county,))
        published = cur.fetchone()[0]
        s = build_nonprofits.summary(res)
        s['published_official_rows'] = published
        cur.execute('insert into registry.loads (county, git_sha, entities, people, roles, gifts, groups, summary) values (%s,%s,%s,%s,%s,%s,%s,%s)',
                    (county + ':nonprofits', git_sha(), len(O), len(P), len(S), None, len(keep), Jsonb(s)))
    print(f'registry {county} nonprofits: {len(O)} organizations, {len(P)} board people, {len(S)} seats, {len(keep)} official matches, {published} published')


def main():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit('DATABASE_URL is not set.')
    from load import connect  # same pooler / TLS handling as the dataset sync
    wanted = sys.argv[1:] or counties()
    with connect(url) as conn:
        cur = conn.cursor()
        cur.execute("select to_regclass('registry.entities') is not null")
        if not cur.fetchone()[0]:
            raise SystemExit('registry schema is missing: run load.py --migrate first (migration 0031).')
        for c in wanted:
            load_county(conn, c)


if __name__ == '__main__':
    main()
