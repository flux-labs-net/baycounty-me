import re
# Private people are never named in this repo: corrections that concern an individual contributor or payee are keyed
# by name_hash() of the lowercased filed name (sha256, first 20 hex digits). Candidates, businesses and groups stay readable.
import hashlib


def name_hash(name):
    return hashlib.sha256(re.sub(r'\s+', ' ', (name or '')).strip().lower().rstrip('.').encode()).hexdigest()[:20]


# contributor-type corrections keyed on lowercased filed name (applies across candidates)
TYPE_OVERRIDE = {
    'pentecoastal temple church': 'other',
    'panama city beach charitable g': 'other',
    'press print graphics': 'business',
    'scott heillmann': 'self',
    'robert c curti': 'self',
    'robert curti': 'self',
    'robert carl curti': 'self',
    'carlos mario sanchez': 'self',
    'fred g manley': 'self',
}
# personal names, a personal trust and same-surname relatives filed as a business or as the candidate -> individual (aggregated only)
TYPE_OVERRIDE_HASHED = {h: 'individual' for h in {
    '4c750efdc83032567807', '681d1e177db4817dd420', '68549651f17e777a789f', '6f505279c5654e235a5e',
    '6fefd5516525a16b7475', 'a347e3265778acaed37a', 'b74c51f043b3b0326bf3', 'd799d3b9dafdc7188d50',
}}
FIRST_ALIAS = {'dave': 'david', 'jamie': 'james', 'nick': 'nicholas', 'steve': 'steven'}
# expenditure payees who are private people (combined into "Payments to individuals"), by name_hash()
PAYEE_PERSON_HASHED = {
    '0001ec87689b9809504a', '140fd67b6d38d4813b89', '1a6a3269fcb2a896b18d', '277db771e2bb08c94b00',
    '2b109214dc97806419a5', '2ccc5ebf78222212f965', '2fe5fda52158b48788d8', '32807108f5b8351e5fab',
    '370c44f8f4c819229d27', '38823171db957ab74136', '39240fdde4f34365b158', '3a6f88d680b13c38523e',
    '3c070bb62742321dc189', '3c80fa9f1c40b6231ce3', '3d9a3533f920851bcca9', '404103360c0a96fc84b4',
    '440d97b4954d3d99720b', '4c750efdc83032567807', '4cb13ef6a70d6702b8d9', '508266b4cde89dc753a6',
    '50e4ff613888bb727710', '6029debaaade42add44a', '612988e4c60c59bbe7bc', '615879adab161d981b3a',
    '61884e891ecb9ce8adb1', '66aa8596e64a9bfcf471', '6705de58254086a13b10', '6a8f00e8fe83b5dd4de2',
    '6c3c09677c65b2d1b208', '6e00bcf42ec03bc8a4b0', '6e8158fc2b02a31d72c0', '6fefd5516525a16b7475',
    '705f5e1f1af324e47935', '76549c8034f8928d49a3', '7a3e630cbcdc0cb0190a', '7b4284a2b0ab9beab7d4',
    '7cd0f72f4d4fd3214bca', '7e037e489b5aafd599ab', '80752b316858ea3d24c0', '8441df6d8a2c17a9a403',
    '8736f1784286b58ea333', '87c592defa6446d24c2b', '89ad8c98d76902814cf6', '8c35683e4c976a9bfe21',
    '8fee435e63da8ce79905', '91fdf67a500707d848c9', '92f9383549a5e2ea7328', '954ed3ad0668c739c28b',
    '96669c45909878e88c4b', '9a62b9a98745518ad9d4', 'a08ab4be11a39adc8be8', 'a24f378ceadf3f804277',
    'a331c1602b3d18064120', 'a9d052159e641b086f89', 'ae6584d538afe35acc71', 'af005016b666d01c31e0',
    'b5e1a8a6de3d52c05536', 'b74c51f043b3b0326bf3', 'b93abb212a9c2f15c42f', 'bf46f4db763af0076bc6',
    'c45964e2eabc23377a1b', 'c69d55beb7f1536f3dde', 'c9e09a9a97a8bb33828e', 'cc27f89f866732b0303e',
    'ce0cd6fa6214ca3f2cbb', 'd63c32f71c484bff434b', 'db3dc1013800ccd0844c', 'e0c3e64b51356a6c595e',
    'e1917611dfcd9136de18', 'e45b55f9005c478ec241', 'e51d4711648c6718c304', 'e8ada251fc76d1aad21c',
    'ec0460e86f7e19e05d06', 'ee63ac80946320b3f90a', 'f356564eb01917158b55', 'fdc396cf697b602e3356',
}
# payees who are candidates (public), readable
PAYEE_PERSON = {
    'carrie ruscoe', 'cindy hamre', 'david l. lowery', 'jackie kennington', 'karen custer',
    'ralph hammond', 'robert carl curti', 'robert carroll', 'scott duvall', 'scott heilmann',
    'shannon aufdencamp', 'steve cox', 'steven moss', 'timothy campbell', 'tracy smith',
}
PAYEE_ORG = set()
_canon = [
    (r'supervisor of elect|supv of elections|bay county soe|bay co supervisor', 'Bay County Supervisor of Elections'),
    (r'^gagnon', "Gagnon's Sign Depot"), (r'^neves med', 'Neves Media Productions LLC'),
    (r'^political ?marketing', "Political Marketing Int'l Inc"), (r'^vista ?print', 'Vistaprint'),
    (r'^google', 'Google'), (r'^lamar', 'Lamar Advertising'), (r'^hancock', 'Hancock Whitney Bank'),
    (r'^gns embroidery', 'GNS Embroidery'), (r'^who.?dey', 'Who Dey Prints & Embroidery'),
    (r'^sign ?works', 'Signworks PC, Inc'), (r'^s[ia]ngs on the cheap', 'Signs on the Cheap'), (r'^corvus blu', 'Corvus Blue Communications'),
    (r'^burnie thompson', 'Burnie Thompson LLC'), (r'^espn radio', 'ESPN Radio NW Fla'), (r'^name ?cheap', 'Namecheap.com'),
    (r'^a\.?g\.?e\.? graphics', 'A.G.E. Graphics'), (r'^league of wom', 'League of Women Voters'), (r'^facebook', 'Facebook (Meta)'),
    (r'^usps|united states postal|^postmaster', 'U.S. Postal Service'), (r'home depot', 'The Home Depot'), (r'^lowe', "Lowe's"),
    (r'^sam.?s club', "Sam's Club"), (r'^trailhead', 'Trailhead Media'), (r'^iheart', 'iHeart Media'), (r'^webelect', 'WebElect.Net LLC'),
    (r'^apple', 'Apple'), (r'^ups', 'UPS'), (r'^regions bank', 'Regions Bank'), (r'^office (depot|max)', 'Office Depot/OfficeMax'),
    (r'^rivas imag', 'Rivas Imaging'), (r'^winred', 'WinRed'), (r'^roberts (and|&) roberts', 'Roberts & Roberts Inc'),
]
class _Canon(dict):
    def get(self, k, default=None):
        return default
PAYEE_CANON = _Canon()
def canon_payee(n):
    low = n.lower().strip()
    for pat, c in _canon:
        if re.search(pat, low): return c
    return n
NOTES = {
 '728': ['The 2026 P7 amended report contains a deletion line with every field blank (rpt 5796, line 1) that could not be matched to an earlier item. The SOE summary counts both the original 8/12/2026 $1,000 candidate loan (coded I) and the amended re-filing of that loan (coded S, rpt 5796 line 2), so the $1,000 loan may be double-counted in the SOE totals. Figures here follow the SOE summary.'],
 '716': ['Lynn Haven recall election (Jan 20, 2026): campaign closed after running unopposed; contributions refunded per the filing. The two recall political committees (Lynn Haven Recall; Recall Mayor Nelson) are committees, not candidates, and are not included.'],
 '736': ['SOE status "Did not qualify": campaign account opened but candidate did not qualify for the ballot.'],
 '748': ['SOE status "Did not qualify": campaign account opened but candidate did not qualify for the ballot.'],
 '740': ['Amended report replaced a $1,000 contribution first filed as from a business with a contribution from an individual (D/A pair applied).'],
 '727': ['Amended report re-coded one $1,000 contribution from "self" to individual (D/A pair applied).'],
 '719': ['The other three District 4 candidates show SOE status Withdrawn. This campaign filed a termination report (TRQ) and its expenditures include refunds of most contributions; total_spent includes those refunds.'],
}
