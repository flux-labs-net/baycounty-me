"""Unit tests for business name matching (ids.vkey, name_match). Run: python3 -m unittest discover data/entities/tests"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'site'))
import ids
import name_match as NM


class Key(unittest.TestCase):
    def test_spacing_and_punctuation_never_matter(self):
        names = ['TK Vandy LLC', 'T K Vandy LLC', 'T.K. Vandy LLC', 'TKVandy LLC', 'TKVandy, LLC', 'TKVANDY LLC', 'T.K. Vandy L.L.C.']
        self.assertEqual({ids.vkey(n) for n in names}, {'tkvandy'})

    def test_dotted_suffixes(self):
        self.assertEqual(ids.vkey('Manuel & Thompson, P.A.'), ids.vkey('Manuel & Thompson PA'))
        self.assertEqual(ids.vkey('Meadows & Kelley P.A.'), 'meadowskelley')

    def test_suffix_cut_at_30_characters(self):
        self.assertEqual(ids.vkey('Freedom Consulting Services LL'), ids.vkey('Freedom Consulting Services, LLC'))
        self.assertEqual(ids.vkey('Dermatology Solutions Group, I'), ids.vkey('Dermatology Solutions Group'))
        self.assertEqual(ids.vkey('Beach Lease, LL'), ids.vkey('Beach Lease, LLC'))

    def test_short_names_keep_their_last_word(self):
        self.assertEqual(ids.vkey('Blairstone I'), 'blairstonei')
        self.assertNotEqual(ids.vkey('Blairstone I'), ids.vkey('Blairstone II'))


class Like(unittest.TestCase):
    def test_spelling_slips(self):
        self.assertEqual(NM.like_reason('emeralcoaststriping', 'emeraldcoaststriping'), 'spelling')
        self.assertEqual(NM.like_reason('beachtimereality', 'beachtimerealty'), 'spelling')

    def test_plural_and_shortened(self):
        self.assertEqual(NM.like_reason('gaccontractor', 'gaccontractors'), 'plural')
        self.assertEqual(NM.like_reason('floridacoastalclosing', 'floridacoastalclosingescr'), 'shortened')

    def test_not_alike(self):
        self.assertIsNone(NM.like_reason('blairstonei', 'blairstoneii'))      # numbered siblings
        self.assertIsNone(NM.like_reason('phase1park', 'phase2park'))        # different numbers
        self.assertIsNone(NM.like_reason('centennial', 'centennialbank'))     # too short to call a cut-off name
        self.assertIsNone(NM.like_reason('abcde', 'abcdf'))                   # too short
        self.assertIsNone(NM.like_reason('tkvandy', 'tkvandy'))

    def test_pairs(self):
        got = NM.like_pairs(['gaccontractor', 'gaccontractors', 'gaccontrators', 'zzzunrelated'])
        self.assertIn(('gaccontractor', 'gaccontractors', 'plural'), got)
        self.assertFalse(any('zzzunrelated' in p for p in got))

    def test_joins(self):
        j = NM.Joins()
        j.join('a', 'b'); j.join('c', 'b')
        self.assertEqual(j.find('c'), 'a')
        self.assertEqual(j.groups(), {'a': {'a', 'b', 'c'}})


class DonorContracts(unittest.TestCase):
    def test_one_row_per_gift(self):
        import app_data
        rows = app_data.donor_contracts()['matches']
        keys = [(r['vendor_id'], r['candidate'], r['election']) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        tk = [r for r in rows if r['vendor_id'] == 'tk-vandy' and r['candidate'] == 'Allan Branch']
        self.assertEqual(len(tk), 1)
        self.assertEqual(tk[0]['contribution_amount'], 1000.0)
        self.assertEqual(set(tk[0]['contract_gov_ids']), {'county', 'pc'})
        self.assertEqual(tk[0]['contract_gov_id'], 'pc')  # the mayor's own government first
        self.assertTrue(tk[0]['same_government_as_office'])


if __name__ == '__main__':
    unittest.main()
