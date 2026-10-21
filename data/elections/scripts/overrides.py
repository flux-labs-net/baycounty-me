import re
# contributor-type corrections keyed on lowercased filed name (applies across candidates)
TYPE_OVERRIDE = {
    # personal names filed as business (B) -> individual (aggregated only)
    'dougles b dykes': 'individual', 'craig e dye': 'individual', 'christopher b forehand': 'individual',
    'jorge l gonzalez': 'individual', 'karen bailey': 'individual',
    # personal trust -> individual (site policy, as in data/campaign)
    'allen living trust': 'individual',
    # non-business organizations
    'pentecoastal temple church': 'other', 'panama city beach charitable g': 'other',
    # business coded S (self)
    'press print graphics': 'business',
    # candidate (self) filed under a variant name
    'scott heillmann': 'self', 'robert c curti': 'self', 'robert curti': 'self', 'robert carl curti': 'self',
    'carlos mario sanchez': 'self', 'fred g manley': 'self',
    # same-surname relatives in other states, coded I; keep as individuals (not self)
    'carlos a sanchez': 'individual', 'carlos andres sanchez': 'individual',
}
FIRST_ALIAS = {'dave': 'david', 'jamie': 'james', 'nick': 'nicholas', 'steve': 'steven'}
_persons = """Adrien A Rivard|Allen G Bense|Arthur Cullen|Beverly Wall|Beverly Walls|Brad Tilghman|Brian R Graninger|Brittany Rivas|Carla K Dykes|Casey Miller|
Cassandra Smith|Charles G Lindsey|Charles H Coram|Charles Handrop|Charles W Roberts|Chase A Curti|Christopher B Forehand|Christopher C Cramer|Clara Young Pease|
Clay S Cox|Clyde A Mills|Craig E Dye|Crystal Michel|Darrell Rizzuto|David L Trepanier|David S Barger|David Spencer|Dennis Isadore|Derek Clay McDavid|Dominck Hughes|
Dominick Hughes|Dominique Hughes|Douglas B Dykes|Edward Wachtfeitl|Frank A Hall|George Roberts|Gerald Quave Jr.|Greg Abrams|Greg Brudnicki|Jacksonf Cole Davis|
Jacob Lethio|James Brooks|James D Morris|James E Ray|Jason L Toole|Jay M Trumbull Sr|Jerry E Bolin|John J Trubia|John Stephen Wilson|Jorge L Gonzalez|Karen Verhonich|
Keith Gross|Kristy Strickland|Kyle Shoots|Larry R Basford|Lauren Dodge|Marsha Greer|Mckenzie Duvall|Michael L Nichols|Michael R Bennett|Peter C Overstreet|
Raymond W Greer|Rex reid|Ronald J Leake|Ross M Clemons|Russell S Prothro|Steve Nail|Stoney Thompson|Thomas Lee Furr|Todd Haney|Troy Syfrett|Walt Eisenbrown|
William Cramer|William G Harrison, Jr.|Zachary B Taylor|JANET Waves|
Carrie Ruscoe|Cindy Hamre|David L. Lowery|Jackie Kennington|Karen Custer|Ralph Hammond|Robert Carl Curti|Robert Carroll|Scott Duvall|Scott Heilmann|Shannon Aufdencamp|
Steve Cox|Steven Moss|Timothy Campbell|Tracy Smith"""
PAYEE_PERSON = {re.sub(r'\s+', ' ', x).strip().lower() for x in _persons.split('|')}
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
