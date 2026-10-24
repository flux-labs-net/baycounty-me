"""Unit tests for people's name casing. Run: python3 -m unittest discover data/entities/tests"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import ids


class PersonCase(unittest.TestCase):
    def test_all_caps(self):
        cases = {
            'JOHN A MCDANIEL III': 'John A McDaniel III',
            "MARY O'NEAL-SMITH": "Mary O'Neal-Smith",
            'BARBARA MACGREGOR': 'Barbara MacGregor',
            'JAMES MACK': 'James Mack',
            'JOE MACHADO': 'Joe Machado',
            'ROBERT SMITH JR.': 'Robert Smith Jr.',
            'J. T. SMITH': 'J. T. Smith',
            "ANN D'ANGELO": "Ann D'Angelo",
            'JOHN SMITH, MD': 'John Smith, MD',
            'jamie mcdonald': 'Jamie McDonald',
        }
        for raw, want in cases.items():
            self.assertEqual(ids.person_case(raw), want)

    def test_mixed_case_kept_but_slips_fixed(self):
        self.assertEqual(ids.person_case('Allan Branch'), 'Allan Branch')
        self.assertEqual(ids.person_case('Barbara Macgregor'), 'Barbara Macgregor')  # as filed
        self.assertEqual(ids.person_case('Rebecca Mcauliffe'), 'Rebecca McAuliffe')
        self.assertEqual(ids.person_case('John Smith Iii'), 'John Smith III')
        self.assertEqual(ids.person_case('Kathy LAWSON'), 'Kathy Lawson')
        self.assertEqual(ids.person_case('MAC McVICAR'), 'Mac McVicar')

    def test_credentials_stay_caps(self):
        cases = {
            'JOHN SMITH ESQ': 'John Smith ESQ', 'JANE DOE, DDS': 'Jane Doe, DDS', 'BOB LEE DMD': 'Bob Lee DMD',
            'AMY POE PHD': 'Amy Poe PhD', 'TOM RAY APRN': 'Tom Ray APRN', 'JOHN SMITH, DO': 'John Smith, DO',
            'Jane Doe Dds': 'Jane Doe DDS', 'John Smith Esq.': 'John Smith ESQ.',
            'ANH THI DO': 'Anh Thi Do', 'LIN MA': 'Lin Ma', 'Mary Ann Gri': 'Mary Ann Gri',  # names, not credentials
        }
        for raw, want in cases.items():
            self.assertEqual(ids.person_case(raw), want)

    def test_sunbiz_fixed_width(self):
        self.assertEqual(ids.sunbiz_person('SELLICK             DAVID         E'), 'David E Sellick')
        self.assertEqual(ids.sunbiz_person('DOE                 JANE          JR'), 'Jane Doe Jr')
        self.assertEqual(ids.sunbiz_person('SMITH, JOHN A'), 'John A Smith')
        self.assertEqual(ids.sunbiz_person('JOHN SMITH, JR'), 'John Smith, Jr')

    def test_matching_keys_unchanged(self):
        # recasing never changes how a name matches
        self.assertEqual(ids.person_key('JOHN A MCDANIEL III'), ids.person_key(ids.person_case('JOHN A MCDANIEL III')))


if __name__ == '__main__':
    unittest.main()
