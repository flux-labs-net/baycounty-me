"""Who held each elected seat, year by year: every local government's officeholder terms since 2014.

One term per person per seat, with start and end dates. A stretch nobody could confirm is a gap row (name null,
gap true), never a guess. start null means the person was already in office before FY2015, the first year the site
covers; end null means still in office. *_approx marks a date known only to the month (or the year), from the first
and last meetings the person appears in.

Sources: Bay County Supervisor of Elections results (enr.electionsfl.org), council and commission minutes (roll
calls), budget books (which list the commission), city websites, the governor's appointment notices and local news.
Each term names its source. Appointed staff (managers, clerks, attorneys) are not here: the government pages list
today's staff.

Writes data/civic/officeholders.json, read by site/page_datasets.py officeholder_terms() (dataset officeholder-terms).
Run: python3 data/civic/scripts/officeholders.py
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'officeholders.json')
AS_OF = '2026-10-25'
PLACE = 'fl-bay'
ENR = lambda e: f'https://enr.electionsfl.org/BAY/{e}/Summary/'
S = {
 # elections (Bay County Supervisor of Elections results, enr.electionsfl.org)
 'e2014m': ('2014 municipal elections, Apr 22, 2014 (SOE results)', ENR(1177)),
 'e2015m': ('2015 municipal elections, Apr 21, 2015 (SOE results)', ENR(1281)),
 'e2016m': ('2016 municipal elections, Apr 19, 2016 (SOE results)', ENR(1494)),
 'e2016p': ('2016 primary election, Aug 30, 2016 (SOE results)', ENR(1537)),
 'e2016g': ('2016 general election, Nov 8, 2016 (SOE results)', ENR(1609)),
 'e2017m': ('2017 municipal elections, Apr 18, 2017 (SOE results)', ENR(1712)),
 'e2017r': ('2017 Lynn Haven runoff, May 16, 2017 (SOE results)', ENR(1723)),
 'e2018m': ('2018 municipal elections, Apr 17, 2018 (SOE results)', ENR(1830)),
 'e2018p': ('2018 primary election, Aug 28, 2018 (SOE results)', ENR(1896)),
 'e2019m': ('2019 municipal elections, Apr 16, 2019 (SOE results)', ENR(2088)),
 'e2019r': ('2019 Panama City Ward 2 runoff, May 21, 2019 (SOE results)', ENR(2151)),
 'e2020m': ('2020 municipal elections, Apr 21, 2020 (SOE results)', ENR(2651)),
 'e2020p': ('2020 primary election, Aug 18, 2020 (SOE results)', ENR(2731)),
 'e2020g': ('2020 general election, Nov 3, 2020 (SOE results)', ENR(2754)),
 'e2021m': ('2021 municipal elections, Apr 20, 2021 (SOE results)', ENR(3413)),
 'e2021r': ('2021 Lynn Haven runoff, May 18, 2021 (SOE results)', ENR(2954)),
 'e2022m': ('2022 municipal elections, Apr 19, 2022 (SOE results)', ENR(3159)),
 'e2022p': ('2022 primary election, Aug 23, 2022 (SOE results)', ENR(3256)),
 'e2023m': ('2023 municipal elections, Apr 18, 2023 (SOE results)', ENR(3361)),
 'e2023r': ('2023 municipal runoffs, May 16, 2023 (SOE results)', ENR(3396)),
 'e2024m': ('2024 municipal elections, Apr 16, 2024 (SOE results)', ENR(3592)),
 'e2024p': ('2024 primary election, Aug 20, 2024 (SOE results)', ENR(3662)),
 'e2025m': ('2025 municipal elections, Apr 22, 2025 (SOE results)', ENR(3825)),
 'e2025r': ('2025 municipal runoffs, May 20, 2025 (SOE results)', ENR(3836)),
 'e2026m': ('2026 municipal elections, Apr 21, 2026 (SOE results)', ENR(3948)),
 # county
 'bocc_hist': ('Bay County, History of Bay County: past commissioners by term', 'https://www.baycountyfl.gov/336/History-of-Bay-County'),
 'bocc_now': ('Bay County Board of County Commissioners', 'https://www.baycountyfl.gov/305/County-Commissioners'),
 'griffitts': ('WJHG, Meet the newest Bay County Commissioners (2016)', 'https://www.wjhg.com/content/news/Meet-the-newest-Bay-County-Commissioners-391831481.html'),
 'baker': ('WJHG, Bay County Commissioner arrested on fraud and misconduct charges (Jun 23, 2020)', 'https://www.wjhg.com/2020/06/23/bay-county-commissioner-arrested-on-fraud-and-misconduct-charges/'),
 'moore': ('WJHG, Bay County to hold special election for District 4 commission seat (Aug 14, 2020)', 'https://www.wjhg.com/2020/08/14/bay-county-to-hold-special-election-for-district-4-commission-seat'),
 'pease': ('Office of the Governor, appointment of Clair Pease (Dec 15, 2022)', 'https://flgov.com/2022/12/15/governor-ron-desantis-appoints-clair-pease-to-the-bay-county-board-of-county-commissioners'),
 'gainer': ('Wikipedia, George Gainer', 'https://en.wikipedia.org/wiki/George_Gainer'),
 # schools
 'bds2016': ('Ballotpedia, Bay District Schools elections (2016)', 'https://ballotpedia.org/Bay_District_Schools_elections_(2016)'),
 'littleton': ('WJHG, Ginger Littleton retires from BDS school board after 13 years (Nov 2019)', 'https://www.wjhg.com/content/news/Ginger-Littleton-retires-from-school-board--564827642.html'),
 'mcqueen': ('Office of the Governor, appointment of Mark McQueen (Jul 26, 2023)', 'https://flgov.com/2023/07/26/governor-ron-desantis-appoints-mark-mcqueen-as-bay-countys-superintendent-of-schools'),
 'bds_board': ('Bay District Schools, School Board members', 'https://bay.k12.fl.us/school-board-members'),
 # Lynn Haven
 'lh14': ('Lynn Haven FY2014-15 budget (city commission page)', 'https://www.cityoflynnhaven.gov/Archive/ViewFile/Item/112'),
 'lh17': ('Lynn Haven FY2016-17 budget (city commission page)', 'https://www.cityoflynnhaven.gov/Archive/ViewFile/Item/115'),
 'lh18': ('Lynn Haven FY2017-18 budget (city commission page)', 'https://www.cityoflynnhaven.gov/ArchiveCenter/ViewFile/Item/116'),
 'lh20': ('Lynn Haven FY2019-20 budget (city commission page)', 'https://www.cityoflynnhaven.gov/DocumentCenter/View/720'),
 'lh21': ('Lynn Haven FY2020-21 budget (city commission page)', 'https://www.cityoflynnhaven.gov/DocumentCenter/View/1104'),
 'lh22': ('Lynn Haven FY2021-22 budget (city commission page)', 'https://www.cityoflynnhaven.gov/DocumentCenter/View/1828'),
 'lh24': ('Lynn Haven FY2023-24 budget (city commission page)', 'https://www.cityoflynnhaven.gov/DocumentCenter/View/2684'),
 'lh27': ('Lynn Haven FY2026-27 budget (city commission page)', 'https://www.cityoflynnhaven.gov/DocumentCenter/View/5091'),
 'lh_anderson': ('WFSU, Lynn Haven city commissioners leave mayoral seat vacant (Aug 28, 2020)', 'https://news.wfsu.org/wfsu-local-news/2020-08-28/lynn-haven-city-commissioners-leave-mayoral-seat-vacant'),
 'lh_vandergrift': ('WJHG, New Lynn Haven Commissioner appointed to fill vacant seat (Feb 4, 2023)', 'https://www.wjhg.com/2023/02/04/new-lynn-haven-commissioner-appointed-fill-vacant-seat'),
 'lh_lowery': ('WJHG, Lynn Haven Commissioners appoint new mayor (Jan 14, 2026)', 'https://www.wjhg.com/2026/01/14/lynn-haven-commissioners-appoint-new-mayor/'),
 'lh_tinder26': ('WJHG, City of Lynn Haven releases statement and legal memo ahead of special commission meeting (Sep 16, 2026)', 'https://www.wjhg.com/2026/09/16/city-lynn-haven-releases-statement-legal-memo-ahead-special-commission-meeting/'),
 'lh_langford': ('WMBB, Corey Langford appointed to Lynn Haven commission (Sep 2026)', 'https://www.mypanhandle.com/news/corey-langford-appointed-to-lynn-haven-commission-as-ward-4/'),
 # Panama City
 'pc16': ('Panama City commission minutes, Aug 23, 2016 (roll call)', 'https://www.panamacity.gov/AgendaCenter/ViewFile/Item/1813?fileID=5652'),
 'pc18': ('Panama City Annual Budget FY2018 (city commission page)', 'https://www.panamacity.gov/ArchiveCenter/ViewFile/Item/326'),
 'pc21': ('Panama City Annual Budget FY2021 (city commission page)', 'https://www.panamacity.gov/ArchiveCenter/ViewFile/Item/1449'),
 'pc22': ('Panama City Annual Budget FY2022 (city commission page)', 'https://www.panamacity.gov/ArchiveCenter/ViewFile/Item/1471'),
 'pc_now': ('Panama City, City Commission', 'https://www.panamacity.gov/395/City-Commission'),
 # Panama City Beach
 'pcb_old': ('Panama City Beach council document listing Mayor Mike Thomas and Ward 1 John Reichard', 'https://www.pcbfl.gov/ArchiveCenter/ViewFile/Item/54'),
 'pcb_casto': ('Panama City Beach council document listing Mayor Mike Thomas and Ward 1 Paul Casto', 'https://www.pcbfl.gov/ArchiveCenter/ViewFile/Item/56'),
 'pcb_oberst': ('WJHG, Former Panama City Beach mayor passes away (May 18, 2025)', 'https://www.wjhg.com/2025/05/18/former-panama-city-beach-mayor-passes-away'),
 'pcb_now': ('Panama City Beach, City Council members', 'https://pcbfl.gov/government/city-council/city-council-members'),
 'pcb_2020': ('WFSU, Panama City Beach leaders to take office (Apr 23, 2020)', 'https://news.wfsu.org/wfsu-local-news/2020-04-23/panama-city-beach-leaders-to-take-office-reopen-sand'),
 # Callaway (Board of Commissioners minutes, Archive Center)
 'cw14': ('Callaway commission minutes, Oct 28, 2014 (roll call)', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/1523'),
 'cw16a': ('Callaway commission minutes, Mar 22, 2016', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/1857'),
 'cw16b': ('Callaway commission minutes, Apr 26, 2016', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/1867'),
 'cw17a': ('Callaway commission minutes, Sep 26, 2017', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2232'),
 'cw17b': ('Callaway commission minutes, Oct 24, 2017', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2249'),
 'cw18a': ('Callaway commission minutes, May 8, 2018', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2350'),
 'cw18b': ('Callaway commission minutes, Jun 26, 2018', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2363'),
 'cw20a': ('Callaway commission minutes, Feb 25, 2020', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2705'),
 'cw20b': ('Callaway commission minutes, May 12, 2020', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/2723'),
 'cw22a': ('Callaway commission minutes, Jun 14, 2022', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/3184'),
 'cw22b': ('Callaway commission minutes, Aug 23, 2022', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/3251'),
 'cw25a': ('Callaway commission minutes, Aug 26, 2025', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/3786'),
 'cw25b': ('Callaway commission minutes, Oct 28, 2025', 'https://www.cityofcallaway.com/ArchiveCenter/ViewFile/Item/3848'),
 'cw_now': ('Callaway, Mayor / Commission', 'https://www.cityofcallaway.com/70/Mayor-Commission'),
 # Springfield
 'sp19': ('Springfield commission minutes, Jan 7, 2019 (present)', 'https://www.springfieldfl.net/media/1106'),
 'sp_now': ('Springfield, City Commission', 'https://www.springfieldfl.net/city-commission'),
 'sp_mayor': ('Springfield, Ralph Hammond (mayor since 2013)', 'https://www.springfieldfl.net/city-commission/directory-listing/ralph-hammond'),
 # Parker
 'pk14': ('Parker 2014 council minutes (present)', 'https://www.cityofparker.com/wp-content/uploads/filr/2665/2014%20Official%20Minutes.pdf'),
 'pk17': ('Parker 2017 council minutes (present)', 'https://www.cityofparker.com/wp-content/uploads/filr/2680/2017%20Minutes.pdf'),
 'pk20': ('Parker council minutes, Feb 4, 2020 (present)', 'https://www.cityofparker.com/wp-content/uploads/filr/2903/Feb%204%202020%20MINUTES%20Regular%20Council.pdf'),
 'pk20b': ('Parker council minutes, Dec 15, 2020 (present)', 'https://www.cityofparker.com/wp-content/uploads/filr/2893/Dec%2015%202020%20Minutes%20Regular.pdf'),
 'pk23': ('Parker council agenda and minutes, Jul 18, 2023 (council listed)', 'https://www.cityofparker.com/wp-content/uploads/filr/4409/July%2018,%202023%20Council%20Minutes.pdf'),
 'pk23r': ('WMBB, Two Parker city council members to resign over Florida financial disclosure law (Dec 2023)', 'https://www.mypanhandle.com/news/local-news/bay-county/parker/two-parker-city-council-members-to-resign-over-controversial-florida-law/'),
 'pk24': ('Parker council minutes, Mar 5, 2024 (council listed)', 'https://www.cityofparker.com/wp-content/uploads/filr/5440/March%205,%202024%20REGULAR%20COUNCIL%20MEETING%20PUBLIC%20HEARING%20AGENDA%20MINUTES.pdf'),
 'pk25': ('Parker council minutes, May 2025 (present)', 'https://www.cityofparker.com/wp-content/uploads/filr/6148/Approved-Minutes-Regular-Meeting-052025.pdf'),
 'pk_rega': ('Parker council appoints a replacement for John Haney (Jul 2026)', 'https://citizenportal.ai/articles/8589306/florida/bay-county/parker/parker-council-appoints-and-swears-in-mark-grama-to-fill-vacant-seat'),
 'pk_now': ('Parker, City Council', 'https://cityofparker.com/government/city-council/'),
 'pk_aud': ('Parker audited financial statements, FY2015-FY2019 (addressed to Mayor Richard Musgrave)', 'https://cityofparker.com/wp-content/uploads/filr/3183/September%2030,%202019%20Audited%20Financial%20Statements.pdf'),
 # Mexico Beach
 'mb_cathey': ('WMBB, Remembering Al Cathey (2026): mayor 2006-2015 and 2017-2023', 'https://www.mypanhandle.com/news/local-news/bay-county/mexico-beach/remembering-al-cathey-the-man-who-helped-rebuild-mexico-beach/'),
 'mb_recall': ('WMBB, Mexico Beach recalls Mayor Michele Miller, votes in Richard Wolff (Apr 2024)', 'https://www.mypanhandle.com/news/local-news/politics-news/mexico-beach-recalls-mayor-michele-miller-votes-in-richard-wolff/'),
 'mb_now': ('Mexico Beach, Mayor and Council', 'https://mexicobeachfl.gov/government/mayor-and-council/'),
 'votes': ('BayCounty.me vote records (roll calls in commission minutes, 2024-2026)', 'https://baycounty.me/public-money/votes'),
}

def T(name, start, end=None, how=None, src=None, note=None, sa=False, ea=False):
    return {k: v for k, v in dict(name=name, start=start, end=end, how=how, src=src, note=note, start_approx=sa or None, end_approx=ea or None).items() if v is not None}
def GAP(start, end, note, src=None):
    """A stretch with no confirmed holder. A note that starts 'Vacant' is a known vacancy (vacant true); any other gap
    is a holder nobody could confirm."""
    return {k: v for k, v in dict(name=None, start=start, end=end, note=note, src=src, gap=True, vacant=note.startswith('Vacant') or None).items() if v is not None}

G = {}
G['county'] = {'body': 'Board of County Commissioners', 'seats': [
 ('District 1', [T('Mike Nelson', None, '2016-11-22', 'elected', 'bocc_hist', 'Lost the Aug 2016 Republican primary to Tommy Hamm.'),
                 T('Tommy Hamm', '2016-11-22', '2024-11-19', 'elected', 'e2016p', 'Won the 2016 primary; re-elected 2020; lost the 2024 primary.'),
                 T('Daniel Raffield', '2024-11-19', None, 'elected', 'e2024p')]),
 ('District 2', [T('George Gainer', None, '2016-11-22', 'elected', 'gainer', 'Left to run for the Florida Senate in 2016.', ea=True),
                 T('Robert Carroll', '2016-11-22', None, 'elected', 'e2016g', 'Won the Nov 2016 election for the rest of the term; re-elected 2018, 2022 and, unopposed, 2026.')]),
 ('District 3', [T('Bill Dozier', None, '2024-11-19', 'elected', 'bocc_hist', 'William T. Dozier. Re-elected 2016 and 2020.'),
                 T('Doug Crosby', '2024-11-19', None, 'elected', 'bocc_now')]),
 ('District 4', [T('Guy Tunnell', None, '2018-11-20', 'elected', 'bocc_hist', ea=True),
                 T('Keith Baker', '2018-11-20', '2020-06-23', 'elected', 'baker', 'Resigned the day he was arrested, Jun 23, 2020.', sa=True),
                 GAP('2020-06-23', '2020-11-17', 'Vacant until the Nov 3, 2020 special election.', 'moore'),
                 T('Doug Moore', '2020-11-17', None, 'special election', 'e2020g', 'Won the 2020 special election for the last two years of the term; re-elected 2022. Not running in 2026.', sa=True)]),
 ('District 5', [T('Mike Thomas', None, '2016-04-19', 'elected', 'bocc_hist', 'Left the seat after he was elected Panama City Beach mayor in April 2016.', ea=True),
                 GAP('2016-04-19', '2016-06-15', 'Vacant until the governor appointed a replacement in June 2016.', 'griffitts'),
                 T('Philip Griffitts', '2016-06-15', '2022-11-08', 'appointed', 'griffitts', 'Known as Griff. Appointed by Gov. Rick Scott in June 2016; won the seat in the Aug 2016 primary and again in 2020. Left after he was elected to the Florida House in Nov 2022.', sa=True, ea=True),
                 GAP('2022-11-08', '2022-12-15', 'Vacant until the governor appointed a replacement.', 'pease'),
                 T('Clair Pease', '2022-12-15', None, 'appointed', 'pease', 'Appointed by Gov. Ron DeSantis; elected to a full term in 2024.')]),
]}
G['schools'] = {'body': 'School Board and Superintendent', 'seats': [
 ('Superintendent', [T('Bill Husfelt', None, '2023-07-31', 'elected', 'e2016g', 'Re-elected 2016 and 2020; left in summer 2023.', ea=True),
                     T('Mark McQueen', '2023-08-01', None, 'appointed', 'mcqueen', 'Appointed by Gov. Ron DeSantis to finish the term.')]),
 ('District 1', [T('Jerry Register', None, None, 'elected', 'bds2016', 'Unopposed in 2016; re-elected 2020 and 2024.')]),
 ('District 2', [T('Ginger Littleton', None, '2019-11-30', 'elected', 'littleton', 'On the board since 2006; stepped down in late 2019.', ea=True),
                 GAP('2019-11-30', '2020-11-17', 'The governor was to appoint someone until the 2020 election; the appointee is not confirmed.', 'littleton'),
                 T('Brenda Ruthven', '2020-11-17', '2022-11-22', 'elected', 'e2020p'),
                 T('Ann Leonard', '2022-11-22', None, 'elected', 'e2022p', 'Did not seek re-election in 2026; Ginger Littleton won the seat and takes office in Nov 2026.')]),
 ('District 3', [T('Joe Wayne Walker', None, '2018-11-20', 'elected', 'bds2016', 'Lost the Aug 2018 election to Pamm Chapman.'),
                 T('Pamm Chapman', '2018-11-20', '2022-11-22', 'elected', 'e2018p'),
                 T('Chris Moore', '2022-11-22', None, 'elected', 'bds_board', 'Unopposed in 2022; in a Nov 3, 2026 runoff.')]),
 ('District 4', [T('Ryan Neves', None, '2020-11-17', 'elected', 'bds2016', 'Ryan Scott Neves. Unopposed in 2016.'),
                 T('Winston Chester', '2020-11-17', None, 'elected', 'e2020p', 'Re-elected 2024.')]),
 ('District 5', [T('Steve Moss', None, None, 'elected', 'e2018p', 'On the board since 2010; re-elected 2014, 2018 and, unopposed, 2022 and 2026.')]),
]}
G['lh'] = {'body': 'City Commission', 'seats': [
 ('Mayor', [T('Walter Kelley', None, '2015-04-21', 'elected', 'lh14', 'Lost the 2015 election to Margo Anderson.'),
            T('Margo Anderson', '2015-04-21', '2020-08-20', 'elected', 'e2015m', 'Re-elected 2019. Removed by the governor and resigned in August 2020 after a federal indictment.'),
            GAP('2020-08-20', '2021-05-18', 'Vacant. Mayor Pro Tem Dan Russell led the commission until the 2021 special election.', 'lh_anderson'),
            T('Jesse Nelson', '2021-05-18', '2026-01-07', 'special election', 'e2021r', 'Won the 2021 special election runoff; re-elected 2023. Resigned in January 2026 before a recall vote.', ea=True),
            T('Dave Lowery', '2026-01-13', None, 'appointed', 'lh_lowery', 'Appointed by the commission until the 2027 election.', sa=True)]),
 ('Seat 1', [T('Rodney Friend', None, '2019-04-16', 'elected', 'lh14', 'Re-elected 2015.'),
             T('Brandon Aldridge', '2019-04-16', '2023-05-16', 'elected', 'e2019m'),
             T('Sam Peebles', '2023-05-16', None, 'elected', 'e2023r', 'Won the May 2023 runoff.')]),
 ('Seat 2', [T('Antonius Barnes', None, '2019-04-16', 'elected', 'lh18'),
             T('Pat Perno', '2019-04-16', None, 'elected', 'e2019m', 'Re-elected 2023.')]),
 ('Seat 3', [T('Roger Schad', None, '2017-05-16', 'elected', 'lh17', 'Lost the 2017 election.'),
             T('Dan Russell', '2017-05-16', '2021-05-18', 'elected', 'e2017r', 'Mayor Pro Tem and acting head of the commission from August 2020 to May 2021.'),
             T('Jamie Warrick', '2021-05-18', None, 'elected', 'e2021r', 'Re-elected 2025.')]),
 ('Seat 4', [T('Joseph Ashbrook', None, '2017-04-18', 'elected', 'lh17', 'Lost the 2017 election to Judy Tinder.'),
             T('Judy Tinder', '2017-04-18', '2023-02-03', 'elected', 'e2017m', 'Re-elected 2021. Left the seat to run for mayor in 2023.', ea=True),
             T('Judy Vandergrift', '2023-02-03', '2025-05-20', 'appointed', 'lh_vandergrift', 'Appointed until the April 2023 special election, which she won.', sa=True),
             T('Judy Tinder', '2025-05-20', '2026-09-08', 'elected', 'e2025r', 'Won the May 2025 runoff. Resigned at the Sep 8, 2026 meeting.'),
             T('Corey Langford', '2026-09-21', None, 'appointed', 'lh_langford', 'Appointed by the commission to finish the term.', sa=True)]),
]}
G['pc'] = {'body': 'City Commission', 'seats': [
 ('Mayor', [T('Greg Brudnicki', None, '2023-05-16', 'elected', 'pc16', 'Re-elected 2019; lost the May 2023 runoff.'),
            T('Michael Rohan', '2023-05-16', '2025-04-22', 'elected', 'e2023r', 'Michael "Doc" Rohan. Lost the 2025 election.'),
            T('Allan Branch', '2025-04-22', None, 'elected', 'e2025m')]),
 ('Ward 1', [T('John Kady', None, '2017-04-18', 'elected', 'pc16', 'Lost the 2017 election.'),
             T('Jenna Haligas', '2017-04-18', '2025-05-20', 'elected', 'e2017m', 'Jenna Flint Haligas. Re-elected 2021.'),
             T('Robbie Hughes', '2025-05-20', None, 'elected', 'e2025r', 'Won the May 2025 runoff.')]),
 ('Ward 2', [T('Kenneth Brown', None, '2023-04-18', 'elected', 'e2015m', 'Kenneth E. Brown. Re-elected 2015 and 2019 (runoff).'),
             T('Janice Lucas', '2023-04-18', None, 'elected', 'e2023m')]),
 ('Ward 3', [T('Billy Rader', None, '2023-04-18', 'elected', 'pc18', 'Lost the 2023 election.'),
             T('Brian Grainger', '2023-04-18', None, 'elected', 'e2023m')]),
 ('Ward 4', [T('Mike Nichols', None, '2021-04-20', 'elected', 'pc21', 'Lost the 2021 election.'),
             T('Josh Street', '2021-04-20', None, 'elected', 'e2021m', 'Re-elected 2025.')]),
]}
G['pcb'] = {'body': 'City Council', 'seats': [
 ('Mayor', [T('Gayle Oberst', None, '2016-04-19', 'elected', 'pcb_oberst', 'Mayor from 2006; term-limited in 2016.'),
            T('Mike Thomas', '2016-04-19', '2020-04-21', 'elected', 'e2016m'),
            T('Mark Sheldon', '2020-04-21', '2024-04-16', 'elected', 'e2020m', 'Lost the 2024 election.'),
            T('Stuart Tettemer', '2024-04-16', None, 'elected', 'e2024m')]),
 ('Ward 1', [T('John Reichard', None, '2018-04-17', 'elected', 'pcb_old', 'Listed as the Ward 1 member under Mayor Mike Thomas; the year he left is not confirmed.', ea=True),
             T('Paul Casto', '2018-04-17', None, 'elected', 'pcb_casto', 'Already the Ward 1 member under Mayor Mike Thomas (2016-2020); re-elected 2022. Start year not confirmed.', sa=True)]),
 ('Ward 2', [GAP(None, '2016-04-19', 'Holder before 2016 not confirmed.'),
             T('Phil Chester', '2016-04-19', '2024-04-16', 'elected', 'e2020m', 'Two terms; re-elected 2020 by 34 votes.'),
             T('Ethan Register', '2024-04-16', None, 'elected', 'pcb_now', 'Unopposed in 2024.')]),
 ('Ward 3', [T('Josie Strange', None, '2018-04-17', 'elected', 'e2014m', 'Re-elected 2014; term-limited in 2018.'),
             T('Geoff McConnell', '2018-04-17', '2022-04-19', 'elected', 'e2018m', 'Lost the 2022 election.'),
             T('Mary Coburn', '2022-04-19', None, 'elected', 'e2022m', 'On the Nov 3, 2026 ballot.')]),
 ('Ward 4', [GAP(None, '2016-04-19', 'Holder before 2016 not confirmed.'),
             T('Hector Solis', '2016-04-19', '2020-04-21', 'elected', 'e2016m'),
             T('Michael Jarman', '2020-04-21', None, 'elected', 'e2020m', 'Vice Mayor.')]),
]}
G['cw'] = {'body': 'City Commission', 'seats': [
 ('Mayor', [T('Thomas Abbott', None, '2016-04-01', 'elected', 'cw16a', 'Thomas W. Abbott. Last at the Mar 22, 2016 meeting.', ea=True),
            T('Bob Pelletier', '2016-04-01', '2017-10-01', 'commission', 'cw16b', 'Mayor by the Apr 26, 2016 meeting; last presided Sep 26, 2017.', sa=True, ea=True),
            T('Pamn Henderson', '2017-10-01', None, 'commission', 'cw17b', 'Mayor by the Oct 24, 2017 meeting; elected mayor in April 2020 and re-elected 2024.', sa=True)]),
 ('Ward 1', [T('Melba Covey', None, '2018-04-17', 'elected', 'e2014m', 'Lost the 2018 election to Scott Davis.'),
             T('Scott Davis', '2018-04-17', '2025-09-01', 'elected', 'e2018m', 'Last at the Aug 26, 2025 meeting.', ea=True),
             T('Bobby Birdsell', '2025-10-01', None, 'appointed', 'cw25b', 'Appointed in October 2025; on the Nov 3, 2026 ballot.', sa=True)]),
 ('Ward 2', [T('Pamn Henderson', None, '2017-10-01', 'elected', 'cw14', 'Moved to mayor in 2017.', ea=True),
             T('Wayne McLeod', '2017-10-01', '2018-04-17', 'appointed', 'cw17b', 'On the commission from October 2017; lost the April 2018 election.', sa=True),
             T('David Griggs', '2018-04-17', None, 'elected', 'e2018m', 'Mayor Pro Tem. Re-elected 2022; term ends Nov 2026.')]),
 ('Ward 3', [T('Bob Pelletier', None, '2016-04-01', 'elected', 'e2014m', 'Moved to mayor in 2016.', ea=True),
             T('Ron Fairbanks', '2016-04-19', '2020-04-21', 'elected', 'e2016m'),
             T('Bob Pelletier', '2020-04-21', None, 'elected', 'e2020m', 'Re-elected 2024.')]),
 ('Ward 4', [T('Ralph Hollister', None, '2016-04-01', 'elected', 'cw16a', ea=True),
             T('Joseph Townsend', '2016-04-01', '2018-06-01', 'elected', 'cw16b', 'On the commission by Apr 26, 2016; last at the May 8, 2018 meeting.', sa=True, ea=True),
             T('Mike Jones', '2018-06-01', '2020-03-01', 'appointed', 'cw18b', 'On the commission by Jun 26, 2018; at the Feb 25, 2020 meeting.', sa=True, ea=True),
             T('Frank Mancinelli', '2020-03-01', '2022-07-01', None, 'cw20b', 'On the commission by May 12, 2020; last at the Jun 14, 2022 meeting.', sa=True, ea=True),
             T('Kenneth Ayers', '2022-07-01', None, None, 'cw22b', 'Kenneth L. Ayers, Jr. On the commission by Aug 23, 2022; elected 2024.', sa=True)]),
]}
G['sp'] = {'body': 'City Commission', 'seats': [
 ('Mayor', [T('Ralph Hammond', '2013-04-16', None, 'elected', 'sp_mayor', 'Mayor since 2013; re-elected 2022 and 2026.', sa=True)]),
 ('Ward 1', [GAP(None, '2016-04-19', 'Holder before 2016 not confirmed.'),
             T('Carl Curti', '2016-04-19', '2023-04-18', 'elected', 'e2016m', 'In office through at least 2019; ran for mayor in 2022. The year he left is not confirmed.', ea=True),
             T('Jack Griffis', '2023-04-18', None, None, 'sp_now', 'Serving since 2023.', sa=True)]),
 ('Ward 2', [T('Phillip Dykes', None, '2024-04-16', None, 'sp19', 'On the commission in 2018 and 2019 minutes; start and end years not confirmed.', ea=True),
             T('Richard Chval', '2024-04-16', None, None, 'sp_now', 'Serving since 2024.', sa=True)]),
 ('Ward 3', [GAP(None, '2015-04-21', 'Holder before April 2015 not confirmed.'),
             T('Jackie Kennington', '2015-04-21', None, 'elected', 'e2015m', 'Re-elected 2018, 2022 and, unopposed, 2026.')]),
 ('Ward 4', [T('Topeka Humphries', None, '2022-04-19', None, 'sp19', 'On the commission in 2018 and 2019 minutes; start year not confirmed.', ea=True),
             T('Cindy Hamre', '2022-04-19', None, None, 'sp_now', 'Serving since 2022; re-elected unopposed 2026.', sa=True)]),
]}
G['parker'] = {'body': 'City Council', 'seats': [
 ('Mayor', [T('Richard Musgrave', None, '2021-04-20', 'elected', 'pk_aud', 'Rich Musgrave. Lost the 2021 election.'),
            T('Andrew Kelly', '2021-04-20', None, 'elected', 'e2021m', 'Re-elected 2023.')]),
 ('Seat 1', [T('Ken Jones', None, '2020-12-01', 'elected', 'pk14', 'Mayor Pro Tem in 2020. Held seat 1 or seat 3 (the seat number is not confirmed); not at the Dec 15, 2020 meeting.', ea=True),
             GAP('2020-12-01', '2021-04-20', 'Not confirmed.'),
             T('Ron Chaple', '2021-04-20', None, 'elected', 'e2021m', 'Ronald H. Chaple.')]),
 ('Seat 2', [T('Ron Chaple', None, '2019-04-16', 'elected', 'e2015m', 'Re-elected 2015; lost the 2019 election to Tonya Barrow.'),
             T('Tonya Barrow', '2019-04-16', None, 'elected', 'e2019m', 'Mayor Pro Tem. Re-elected 2023.')]),
 ('Seat 3', [T('John Haney', None, '2021-04-20', 'elected', 'pk14', 'Held seat 1 or seat 3 (the seat number is not confirmed).', ea=True),
             T('April Gibson', '2021-04-20', '2023-12-31', 'elected', 'e2021m', 'Resigned in December 2023 over the new financial disclosure law.', ea=True),
             T('Katy Bodiford', '2024-02-01', None, 'appointed', 'pk24', 'On the council by March 2024, filling seat 3 or seat 4 (not confirmed).', sa=True)]),
 ('Seat 4', [T('Michael Miller', None, '2019-04-16', 'elected', 'e2015m', 'Mayor Pro Tem. Re-elected 2015.'),
             T('Stacie Galbreath', '2019-04-16', '2023-12-29', 'elected', 'e2019m', 'Re-elected 2023. Resigned Dec 29, 2023 over the new financial disclosure law.'),
             T('John Haney', '2024-02-01', '2026-07-01', 'appointed', 'pk24', 'Back on the council by March 2024, filling seat 3 or seat 4 (not confirmed); resigned in 2026.', sa=True, ea=True),
             T('Mark Rega', '2026-07-21', None, 'appointed', 'pk_rega', 'Appointed in July 2026 to finish John Haney\'s term.', sa=True)]),
]}
G['mb'] = {'body': 'City Council', 'seats': [
 ('Mayor (Group 1)', [T('Al Cathey', None, '2015-04-21', 'elected', 'mb_cathey', 'Mayor 2006-2015.', ea=True),
                      GAP('2015-04-21', '2017-04-18', 'Mayor from 2015 to 2017 not confirmed (Tom Bailey lost to Al Cathey in 2017).', 'e2017m'),
                      T('Al Cathey', '2017-04-18', '2023-04-18', 'elected', 'e2017m', 'Lost the 2023 election to Michele Miller.'),
                      T('Michele Miller', '2023-04-18', '2024-04-16', 'elected', 'e2023m', 'Recalled by voters Apr 16, 2024.'),
                      T('Richard Wolff', '2024-04-16', None, 'special election', 'e2024m', 'Won the special election held with the recall.')]),
 ('Group 2', [T('Mary Blackburn', '2014-04-22', '2016-04-19', 'elected', 'e2014m', 'Elected 2014 to a two-year term; whether she served past 2016 is not confirmed.', ea=True),
              GAP('2016-04-19', '2019-04-16', 'Holder from 2016 to 2019 not confirmed.'),
              T('Jerry Smith', '2019-04-16', '2025-04-22', 'elected', 'e2019m', 'Re-elected 2023; Mayor Pro Tem in 2024.'),
              T('Erik Fosshage', '2025-04-22', None, 'elected', 'e2025m')]),
 ('Group 3', [GAP(None, '2019-04-16', 'Holder before 2019 not confirmed.'),
              T('Bobby Pollock', '2019-04-16', '2023-04-18', 'elected', 'e2019m', 'Lost the 2023 election.'),
              T('Linda Hamilton', '2023-04-18', None, 'elected', 'e2023m')]),
 ('Group 4', [T('Tanya Castro', '2014-04-22', '2016-04-19', 'elected', 'e2014m', 'Elected 2014 to a two-year term; whether she served past 2016 is not confirmed.', ea=True),
              GAP('2016-04-19', '2022-04-19', 'Holder from 2016 to 2022 not confirmed.'),
              T('Adrian Welle', '2022-04-19', '2024-04-16', 'elected', 'e2022m'),
              T('Jason Adams', '2024-04-16', '2026-04-01', 'elected', 'e2024m', 'Left in 2026.', ea=True),
              T('Lisa Logan', '2026-04-01', None, 'appointed', 'mb_now', 'Appointed April 2026; elected unopposed for the next term.', sa=True)]),
 ('Group 5', [T('Jeff Tendler', '2014-04-22', '2016-04-19', 'elected', 'e2014m', 'Elected 2014 to a two-year term; whether he served past 2016 is not confirmed.', ea=True),
              GAP('2016-04-19', '2020-04-21', 'Holder from 2016 to 2020 not confirmed.'),
              T('Sharon Call', '2020-04-21', '2022-04-19', 'elected', 'e2020m'),
              T('Richard Wolff', '2022-04-19', '2024-04-16', 'elected', 'e2022m', 'Became mayor in 2024.'),
              T('Tim Linderman', '2024-04-16', '2025-06-01', 'special election', 'e2024m', 'The month he left is not confirmed.', ea=True),
              T('Steve Cox', '2025-06-01', None, None, 'mb_now', 'On the council in 2025 and 2026 votes; elected unopposed in 2026.', sa=True)]),
]}


NAMES = {'county': 'Bay County', 'schools': 'Bay District Schools', 'lh': 'City of Lynn Haven', 'pc': 'City of Panama City',
         'pcb': 'City of Panama City Beach', 'cw': 'City of Callaway', 'sp': 'City of Springfield', 'parker': 'City of Parker',
         'mb': 'City of Mexico Beach'}


def check(gov, seat, terms):
    """Terms in a seat follow one another: no overlaps, each starts on or after the last one ended, only the last is open."""
    for a, b in zip(terms, terms[1:]):
        assert a.get('end'), (gov, seat, a, 'only the last term can be open')
        assert b.get('start') and b['start'] >= a['end'], (gov, seat, a, b)
        if b['start'] > a['end'] and (b['start'][:7] != a['end'][:7]) and not (a.get('end_approx') or b.get('start_approx')):
            raise AssertionError((gov, seat, 'unexplained break', a, b))
    for t in terms:
        assert t.get('src') in S or t.get('gap') and t.get('src') in (None, *S), (gov, seat, t)
        assert t.get('gap') or t.get('name'), t


def main():
    govs = []
    for gov, g in G.items():
        seats = []
        for order, (seat, terms) in enumerate(g['seats']):
            check(gov, seat, terms)
            seats.append({'seat': seat, 'order': order, 'terms': terms})
        govs.append({'gov_id': gov, 'government': NAMES[gov], 'body': g['body'], 'seats': seats})
    gaps = [f"{NAMES[g['gov_id']]}, {s['seat']}: {t['note']}" for g in govs for s in g['seats'] for t in s['terms'] if t.get('gap') and not t.get('vacant')]
    json.dump({'as_of': AS_OF, 'place_id': PLACE,
               'notes': ['One term per person per seat. start null = in office before FY2015; end null = in office now.',
                         'A gap row (name null) is a stretch nobody could confirm from the records found, or a known vacancy (vacant true).',
                         '*_approx = the date is known only to the month or year (first or last meeting the person appears in).',
                         'Elected seats only; appointed staff are listed as of today on each government page.'],
               'gaps': gaps, 'sources': {k: {'title': t, 'url': u} for k, (t, u) in S.items()}, 'governments': govs},
              open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('wrote', os.path.relpath(OUT), sum(len(s['terms']) for g in govs for s in g['seats']), 'terms,', len(gaps), 'gaps')


if __name__ == '__main__':
    main()
