"""Unit tests for board titles. Run: python3 -m unittest discover data/nonprofits/tests"""
import os, sys, unittest
HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(HERE, '..', '..'))
from build_nonprofits import sunbiz_title, clean_title


class Titles(unittest.TestCase):
    def test_sunbiz_codes(self):
        cases = {'TD': 'Treasurer, Director', 'Td': 'Treasurer, Director', 'PD': 'President, Director', 'VD': 'Vice President, Director',
                 'DIRE': 'Director', 'SECR': 'Secretary', 'D-VP': 'Director, Vice President', 'S/T': 'Secretary, Treasurer',
                 'STD': 'Secretary, Treasurer, Director', 'VP,': 'Vice President', 'MGRM': 'Managing Member', 'P': 'President', '': 'Officer'}
        for raw, want in cases.items():
            self.assertEqual(sunbiz_title(raw), want, raw)

    def test_unknown_code_kept(self):
        self.assertEqual(sunbiz_title('RIVE'), 'Rive')

    def test_irs_truncation(self):
        cases = {'VICE PRESIDE': 'Vice President', 'EXECUTIVE DI': 'Executive Director', 'Secretary/Tr': 'Secretary/Treasurer',
                 'VP OF COMMUN': 'VP of Communications', 'Ceo': 'CEO', 'Board member': 'Board member', 'DIRECTOR': 'Director',
                 'MEMBER AT LA': 'Member At Large'}
        for raw, want in cases.items():
            self.assertEqual(clean_title(raw), want, raw)


if __name__ == '__main__':
    unittest.main()
