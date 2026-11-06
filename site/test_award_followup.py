"""Checks for site/award_followup.py: contract awards in the minutes with no later record."""
import os, unittest

os.environ.setdefault('BC_TODAY', '2026-11-06')
import award_followup as A  # noqa: E402

STATUSES = {'followed_up', 'no_follow_up', 'too_soon', 'as_needed', 'cant_check'}


class AwardFollowUp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = A.rows()

    def test_statuses(self):
        self.assertTrue(self.rows)
        for r in self.rows:
            self.assertIn(r['status'], STATUSES, r['vote_id'])
            self.assertGreaterEqual(r['award_date'], '2016-01-01')
            self.assertEqual(r['status'] == 'followed_up', r['later_records'] > 0, r['vote_id'])
            if r['status'] == 'cant_check':
                self.assertIsNone(r['company'])
            if r['first_later_date']:
                self.assertGreater(r['first_later_date'], r['award_date'], r['vote_id'])

    def test_flag_waits_six_months(self):
        for r in self.rows:
            if r['status'] == 'no_follow_up':
                self.assertLessEqual(r['flag_after'], os.environ['BC_TODAY'], r['vote_id'])
            if r['status'] == 'too_soon':
                self.assertGreater(r['flag_after'], os.environ['BC_TODAY'], r['vote_id'])

    def test_follow_ups_are_not_awards(self):
        """Change orders, amendments and renewals are later records of an award, not awards of their own."""
        for r in self.rows:
            self.assertNotRegex(r['headline'].lower(), r'change order|amendment|renewal', r['vote_id'])

    def test_standing_agreements_not_flagged(self):
        for r in A.flagged():
            self.assertFalse(A.AS_NEEDED.search(r['headline']), r['headline'])

    def test_award_with_change_order_is_followed(self):
        """Panama City's MLK Recreation Center award to Burke Construction (2024-01-23) has a change order on file, so it is followed up."""
        burke = [r for r in self.rows if r['gov_id'] == 'pc' and r['award_date'] == '2024-01-23' and r['company'] and 'Burke' in r['company']]
        self.assertTrue(burke)
        self.assertTrue(all(r['status'] == 'followed_up' and 'Change order' in r['later_kinds'] for r in burke))

    def test_text_names(self):
        self.assertEqual([n for n, _ in A.text_names('The commission approved a service agreement with HST Utility Contractors for the survey')],
                         ['HST Utility Contractors'])
        self.assertEqual(A.text_names('The board approved the purchase of instructional materials.'), [])


if __name__ == '__main__':
    unittest.main()
