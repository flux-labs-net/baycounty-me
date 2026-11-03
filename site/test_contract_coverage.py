"""Checks for site/contract_coverage.py: contract votes in the minutes checked against the contract list."""
import json, os, unittest

import contract_coverage as C

HERE = os.path.dirname(os.path.abspath(__file__))
STATUSES = {'in_list', 'under_threshold', 'after_review', 'no_amount', 'missing'}


class ContractCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = C.rows()
        cls.d = json.load(open(os.path.join(HERE, '..', 'data', 'contracts', 'contracts.json')))

    def test_statuses(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            self.assertIn(r['status'], STATUSES, r['vote_id'])
            self.assertEqual(r['in_contract_list'], r['status'] == 'in_list')
            self.assertGreaterEqual(r['date'], C.START)

    def test_every_government_has_a_review_date_and_threshold(self):
        for name, r in self.d['review'].items():
            self.assertRegex(r['through'], r'^\d{4}-\d{2}-\d{2}$', name)
            self.assertGreater(r['threshold'], 0, name)

    def test_hand_checks_point_at_real_votes(self):
        ids = {v['vote_id'] for v in json.load(open(os.path.join(HERE, '..', 'data', 'votes', 'minutes_votes.json')))['votes']}
        for vid, h in self.d['minutes_check'].items():
            self.assertIn(vid, ids, f'{vid}: no such vote in minutes_votes.json')
            self.assertIn(h['status'], STATUSES | {'not_an_award'}, vid)
            self.assertTrue(h.get('why'), vid)

    def test_no_spending_votes_left_out(self):
        heads = ' '.join(r['headline'].lower() for r in self.rows)
        for w in ('mutual aid', 'certificate of public convenience', 'rescind'):
            self.assertNotIn(w, heads)

    def test_lynn_haven_2026_read_in(self):
        """Lynn Haven's 2026 packets were read in full (2026-10-31): the corridor award is matched, nothing is left unread."""
        lh = [r for r in self.rows if r['gov_id'] == 'lh' and r['year'] == 2026]
        self.assertFalse([r['vote_id'] for r in lh if r['status'] in ('missing', 'after_review') and not r['checked_note']])
        corridor = [r for r in lh if 'Ohio Ave' in r['headline']]
        self.assertTrue(corridor and all(r['status'] == 'in_list' for r in corridor))


if __name__ == '__main__':
    unittest.main()
