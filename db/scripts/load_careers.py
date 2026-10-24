"""Load officials' business ties (schema `careers`, migration 0033) from data/careers/build_careers.py.

Usage:
  DATABASE_URL=postgresql://... python3 db/scripts/load_careers.py [county ...]     # default: every county with Sunbiz data

Per county, in one transaction:
  - matches (official / Sunbiz person pairs) are upserted so an admin's review_status survives; pairs no longer found
    are deleted;
  - roles and links are replaced;
  - role_seen stamps first_seen / last_seen for every officer and agent in the Sunbiz file, so start and end dates
    accumulate from the first load on;
  - careers.publish() rewrites the public official_businesses / official_business_links rows for confirmed pairs.
Run by .github/workflows/sync-db.yml after load_registry.py.
"""
import datetime, os, sys
from psycopg.types.json import Jsonb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'data', 'careers'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_careers  # noqa: E402
from load_registry import counties, git_sha, _copy  # noqa: E402

LINK_COLS = ['link_type', 'person_id', 'other_person_id', 'candidate', 'office', 'gov_id', 'payer', 'own_government', 'self_gift', 'doc_number',
             'entity_name', 'related_doc', 'related_name', 'shared_people', 'shared_person_keys', 'amount', 'items', 'first_date', 'last_date',
             'record_types', 'detail', 'requires', 'source_url', 'report_url']
JSON_COLS = {'shared_person_keys', 'record_types', 'requires'}


def load_county(conn, county, today=None):
    today = today or datetime.date.today()
    out = build_careers.build(county)
    M, R, L = out['matches'], out['roles'], out['links']
    n_biz = {}
    for r in R:
        n_biz[(r['person_id'], r['person_key'])] = n_biz.get((r['person_id'], r['person_key']), 0) + 1
    with conn.transaction():
        cur = conn.cursor()
        for m in M:
            cur.execute('''insert into careers.matches (county, person_id, person_key, official_name, label, gov_ids, score, confidence, reasons, n_businesses, loaded_at)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                           on conflict (county, person_id, person_key) do update set official_name = excluded.official_name, label = excluded.label,
                             gov_ids = excluded.gov_ids, score = excluded.score, confidence = excluded.confidence, reasons = excluded.reasons,
                             n_businesses = excluded.n_businesses, loaded_at = now()''',
                        (county, m['person_id'], m['person_key'], m['official_name'], m['label'], Jsonb(m['gov_ids']), m['score'], m['confidence'],
                         Jsonb(m['reasons']), n_biz.get((m['person_id'], m['person_key']), 0)))
        keep = {(m['person_id'], m['person_key']) for m in M}
        cur.execute('select person_id, person_key from careers.matches where county = %s', (county,))
        for pid, pk in cur.fetchall():
            if (pid, pk) not in keep:
                cur.execute('delete from careers.matches where county = %s and person_id = %s and person_key = %s', (county, pid, pk))
        cur.execute('delete from careers.roles where county = %s', (county,))
        cur.execute('delete from careers.links where county = %s', (county,))
        _copy(cur, 'careers.roles', ['county', 'person_id', 'person_key', 'doc_number', 'entity_name', 'titles', 'role_kind', 'entity_status', 'filing_type',
                                     'nonprofit', 'principal_city', 'file_date', 'closed_year', 'source_url'],
              ((county, r['person_id'], r['person_key'], r['doc_number'], r['entity_name'], r['titles'], r['role_kind'], r['entity_status'], r['filing_type'],
                r['nonprofit'], r['principal_city'], r['file_date'], r['closed_year'], r['source_url']) for r in R))
        _copy(cur, 'careers.links', ['county'] + LINK_COLS,
              ([county] + [(Jsonb(l.get(c)) if c in JSON_COLS and l.get(c) is not None else l.get(c)) for c in LINK_COLS] for l in L))
        # first / last seen for every officer and agent in this Sunbiz file
        cur.execute('create temp table _seen (doc_number text, name_key text, title text) on commit drop')
        seen = {(r['doc_number'], r['name_key'], r['title'] or '') for r in out['registry']['roles'] if r.get('name_key')}
        _copy(cur, '_seen', ['doc_number', 'name_key', 'title'], seen)
        cur.execute('''insert into careers.role_seen (county, doc_number, name_key, title, first_seen, last_seen)
                       select %s, doc_number, name_key, title, %s, %s from _seen
                       on conflict (county, doc_number, name_key, title) do update set last_seen = excluded.last_seen''', (county, today, today))
        cur.execute('select careers.publish(%s)', (county,))
        published = cur.fetchone()[0]
        s = build_careers.summary(out)
        s['published_rows'] = published
        cur.execute('insert into careers.loads (county, git_sha, matches, roles, links, summary) values (%s,%s,%s,%s,%s,%s)',
                    (county, git_sha(), len(M), len(R), len(L), Jsonb(s)))
    print(f'careers {county}: {len(M)} matches, {len(R)} roles, {len(L)} links, {published} public rows')


def main():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise SystemExit('DATABASE_URL is not set.')
    from load import connect
    wanted = sys.argv[1:] or counties()
    with connect(url) as conn:
        cur = conn.cursor()
        cur.execute("select to_regclass('careers.matches') is not null")
        if not cur.fetchone()[0]:
            raise SystemExit('careers schema is missing: run load.py --migrate first (migration 0033).')
        for c in wanted:
            load_county(conn, c)


if __name__ == '__main__':
    main()
