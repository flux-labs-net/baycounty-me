"""Where BayCounty.me's data comes from: every source we take records from, which government it covers, the link,
how we get it, how often, and what we do with it. Published as datasets `data-sources` (one row per source) and
`data-source-sites` (every website the site's records cite, counted from the data files) and shown on /data-sources.

Add a row here when a new source is ingested. Meeting and agenda rows are built from data/meetings/meetings.json,
so a board added to the meetings fetch shows up here on its own.
"""
import collections, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')

# Columns of the matrix, in order. 'state' = state and federal databases, 'county-wide' = one county source that covers everyone.
GOVS = [
    ('county', 'Bay County'), ('schools', 'Bay District Schools'), ('pc', 'Panama City'), ('pcb', 'Panama City Beach'),
    ('lh', 'Lynn Haven'), ('cw', 'Callaway'), ('sp', 'Springfield'), ('parker', 'Parker'), ('mb', 'Mexico Beach'),
    ('officers', 'Constitutional officers and districts'), ('county-wide', 'County-wide sources'), ('state', 'State and federal databases'),
]
GOV_NAME = dict(GOVS)

AUTO_DAILY = 'Automatic, daily'
AUTO_WEEKLY = 'Automatic, weekly'
AUTO_30 = 'Automatic, every 30 minutes on weekdays'
BY_HAND = 'Downloaded and read by hand'
BULK = 'State or federal bulk data file'
LIVE = 'Live lookup (nothing stored)'

# How we work each kind of record. Steps are the same for every government; a source row adds what is specific to it.
TOPICS = [
    ('meetings', 'Meetings and agendas', '/meetings',
     'Each government\'s agenda system is checked every 30 minutes on weekdays (when a notice email arrives) and swept twice a day. '
     'Every agenda, packet and minutes file is downloaded and fingerprinted; a changed file is kept as a new version. '
     'An AI model reads each new agenda into a list of items using only the agenda\'s own words (it is told not to guess). '
     'The meetings list combines the agenda system with the government\'s calendar; boards with no calendar get dates from their regular schedule, marked "expected".',
     'Failed fetches are logged and emailed to the site admins. Every version of every file is kept.'),
    ('votes', 'Votes', '/public-money/votes',
     'Money votes are read from adopted minutes (or draft minutes printed in the next agenda packet). Each motion is recorded with the roll call by name; '
     'the amount comes from the staff memo or resolution attached to the item. Scanned minutes are read with OCR.',
     'Names are checked against each board\'s roster. Every split or failed vote found is included.'),
    ('contracts', 'Contracts and change orders', '/public-money/contracts',
     'Awards, change orders and emergency purchases are taken from agenda items and their attached memos and resolutions. '
     'An agenda item is a proposal, so where minutes exist the record is checked against them.',
     'Panama City records were checked against 124 of 126 meetings\' minutes and Panama City Beach against 38 of 50; Bay County and Lynn Haven come from agendas only. Known changes are noted on the record.'),
    ('budgets', 'Budgets', '/public-money/budget-compare',
     'Adopted budget books are downloaded from each government\'s website and the totals, funds and departments typed into the data. '
     'Where a budget book is not posted, the Annual Financial Report the government files with the state is used. Audited revenue and spending come from the state\'s Local Government Financial Reports.',
     'Totals are added back up and compared with the printed totals. Each year links to its document.'),
    ('audits', 'Audits and debt', '/governments',
     'Audited financial statements filed with the Florida Auditor General are read for debt (bonds, notes, loans, leases), audit findings and the auditor\'s opinion.',
     'Only audited figures are used. When a government\'s latest audit is not yet filed, the previous year is used and labeled.'),
    ('property-tax', 'Property tax', '/public-money/tax-dollars',
     'Tax rates (millage) come from state Department of Revenue and EDR files and the governments\' adopted budgets. Assessments and exemptions come from the state\'s parcel and assessment roll files.',
     'Rates are checked against each government\'s adopted millage resolution where posted.'),
    ('salaries', 'Pay', '/governments',
     'Pay comes from budget pay plans, published salary schedules, job postings and the state\'s report on officials\' salaries.',
     'Only elected officials and department leaders are named. Other staff are counted, not named.'),
    ('campaign', 'Campaign money', '/connections/campaign-gifts',
     'Summary totals and the itemized export for each campaign are downloaded from the Supervisor of Elections\' campaign finance system every day. '
     'Amended and deleted lines are applied, then businesses are matched to state corporate records.',
     'Itemized sums are checked against the Supervisor\'s summary totals. Individual donors are only counted, never named, unless they run a registered business.'),
    ('elections', 'Elections', '/elections',
     'Candidate lists, status and official results come from the Supervisor of Elections. Platforms come from candidates\' own sites.',
     'Office names are checked against the Notice of General Election.'),
    ('businesses', 'Businesses and owners', '/connections/business-ties',
     'The state\'s full corporate file (about 18 GB, updated quarterly) is filtered to businesses with an address in the county. '
     'Officers, managers and registered agents are grouped into people and matched to officials and donors.',
     'A name match is only a lead: nothing about a person is published until it is checked by hand. Street addresses are never stored or shown.'),
    ('nonprofits', 'Nonprofits', '/connections/nonprofits',
     'Every tax-exempt organization with a county address is pulled from IRS data, with every 990, 990-EZ and 990-PF e-filed since 2019 (board members, pay, grants, revenue). '
     'State charity registrations and state corporate filings are joined in.',
     'Organizations are joined by EIN, then by exact name. Official-to-board matches are checked by hand before they are tagged.'),
    ('chambers', 'Chambers of commerce', '/chambers',
     "Board, staff and program lists are copied by hand from each chamber's website. Upcoming events are read every day from the Panama City Beach Chamber's public calendar feed; the Bay County Chamber's calendar platform turns automated readers away.",
     'Board members are joined to other local filings by first and last name, and to an official only where the chamber names their government post. Organizations are joined to governments, paid companies, nonprofits or one Sunbiz filing with the exact same name.'),
    ('outdoors', 'Beaches and parks', '/beaches',
     "The beach flag, rip current risk and surf forecast are read every morning from the National Weather Service surf zone forecast (and again in the visitor's browser). Water quality samples are read every day from the Florida Department of Health's Healthy Beaches lookup. Beach accesses, parking, parks, boat ramps and trails come from the county's and Panama City Beach's public GIS maps and the state's coastal access survey.",
     "Each beach access is joined to the state's coastal access survey only when the two points are within about 200 feet. Parks in the county's park guide are joined to its parks inventory by name. Samples before 2016 are dropped; samples already on file are kept when the state's lookup stops showing them."),
    ('cra', 'Redevelopment agencies (CRAs)', '/public-money/cra-spending',
     'CRA spending is read from CRA annual reports, agendas, budgets and audits, one ledger line per payment or project. '
     'Tax increment comes from CRA reports, audits and budgets, split between the county and city by millage.',
     'Each line carries its source and a confidence level; amounts inside a larger total are shown but counted once. Estimates are checked against official county figures.'),
    ('michael', 'Hurricane Michael', '/public-money/hurricane-michael',
     'FEMA Public Assistance projects and applicants for disaster DR-4399 are downloaded from OpenFEMA every week.',
     'The data is FEMA\'s own; nothing is retyped.'),
    ('sales-tax', 'Sales tax projects', '/public-money/sales-tax-projects',
     'Infrastructure sales tax projects are downloaded from Bay County\'s map server every week and matched to the published project schedule.',
     'Matches between the map and the schedule are listed with their method.'),
    ('tourist-tax', 'Tourist tax', '/public-money/tourist-tax',
     'Bed tax collections come from the Clerk\'s monthly reports. Payments by the three tourism agencies come from the Clerk\'s monthly check registers, read from text PDFs in the Clerk\'s public records search. State tax rates and history come from EDR.',
     'Every agency-month matches the register\'s printed total to the cent. Payments to private individuals are counted, not listed.'),
    ('fees', 'Fees and bills', '/public-money/fees-and-bills',
     'Assessments come from the state\'s non-ad valorem assessment roll file. Utility rates and fees come from city and county fee schedules and budget books.',
     'Where a code-to-name match is inferred rather than published, it is labeled.'),
    ('address', 'My Address lookups', '/my-address',
     'Address lookups go straight from your browser to the county\'s and FEMA\'s public map servers at the moment you search.',
     'Nothing you look up is sent to or stored by BayCounty.me.'),
    ('officials', 'Officials by year', '/people',
     'Who held each seat since 2016 is built from election results, minutes, budget books, city websites and news reports.',
     'Each term names its source. Stretches nobody could confirm are marked unconfirmed, not guessed.'),
    ('records', 'Public records contacts', '/records-request',
     'Records custodians, portals and policies are taken from each agency\'s official pages.',
     'Only portals linked from an official page are listed.'),
    ('news', 'News and context', '/updates',
     'Local news reports are cited for context (for example an arrest, a resignation or a policy change) when no official document says it.',
     'News is never the only source for a dollar figure.'),
]
TOPIC = {t[0]: t for t in TOPICS}

S = []  # (topic, gov, source name, url, method, refresh, what we take)


def src(topic, gov, name, url, method, refresh, what):
    S.append((topic, gov, name, url, method, refresh, what))


# --- Votes -----------------------------------------------------------------------------------------------------------
src('votes', 'county', 'County Commission minutes (PrimeGov)', 'https://baycountyfl.primegov.com/public/portal', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')
src('votes', 'county', 'Clerk of Court public records search (OnBase)', 'https://bayforms.baycoclerk.com/PublicAccess/PublicRecordSearch/', BY_HAND, 'As needed', 'Adopted minutes and resolutions')
src('votes', 'schools', 'School Board minutes (BoardDocs)', 'https://go.boarddocs.com/fl/bcsdfl/Board.nsf/Public', BY_HAND, 'As minutes are adopted', 'Every motion with Yes and No by name, Jan 2024 on')
src('votes', 'pc', 'City Commission and CRA minutes (AgendaCenter)', 'https://www.panamacity.gov/AgendaCenter', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')
src('votes', 'pcb', 'City Council minutes (Granicus)', 'https://pcbgov.granicus.com/ViewPublisher.php?view_id=1', BY_HAND, 'As minutes are adopted', 'Draft minutes printed in the next agenda packet')
src('votes', 'lh', 'City Commission minutes (CivicClerk)', 'https://lynnhavenfl.portal.civicclerk.com/', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')
src('votes', 'cw', 'City Commission and CRA minutes (AgendaCenter)', 'https://www.cityofcallaway.com/AgendaCenter', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')
src('votes', 'sp', 'City Commission minutes (city document library)', 'https://www.springfieldfl.net/meetings', BY_HAND, 'As minutes are adopted', 'Scanned minutes read with OCR')
src('votes', 'parker', 'City Council agendas and minutes', 'https://cityofparker.com/government/agendas-minutes/', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')
src('votes', 'mb', 'City Council meetings page', 'https://mexicobeachfl.gov/government/council-meetings/', BY_HAND, 'As minutes are adopted', 'Money votes and roll calls')

# --- Contracts -------------------------------------------------------------------------------------------------------
src('contracts', 'county', 'County Commission agendas (PrimeGov)', 'https://baycountyfl.primegov.com/public/portal', BY_HAND, 'Each meeting', 'Awards, change orders and emergency purchases from every regular-meeting agenda since 2022')
src('contracts', 'pc', 'City Commission agendas and minutes (AgendaCenter)', 'https://www.panamacity.gov/AgendaCenter', BY_HAND, 'Each meeting', 'Awards and change orders, checked against minutes')
src('contracts', 'pcb', 'City Council agendas and minutes (Granicus)', 'https://pcbgov.granicus.com/ViewPublisher.php?view_id=1', BY_HAND, 'Each meeting', 'Awards and change orders, checked against minutes')
src('contracts', 'lh', 'City Commission agendas (CivicClerk)', 'https://lynnhavenfl.portal.civicclerk.com/', BY_HAND, 'Each meeting', 'Awards and change orders')
src('contracts', 'cw', 'City Commission agendas (AgendaCenter)', 'https://www.cityofcallaway.com/AgendaCenter', BY_HAND, 'Each meeting', 'Awards and change orders')
src('contracts', 'sp', 'City Commission meetings', 'https://www.springfieldfl.net/meetings', BY_HAND, 'Each meeting', 'Awards and change orders')
src('contracts', 'parker', 'City Council agendas and minutes', 'https://cityofparker.com/government/agendas-minutes/', BY_HAND, 'Each meeting', 'Awards and change orders')
src('contracts', 'mb', 'City Council meetings page', 'https://mexicobeachfl.gov/government/council-meetings/', BY_HAND, 'Each meeting', 'Awards and change orders')

# --- Budgets ---------------------------------------------------------------------------------------------------------
src('budgets', 'county', 'Bay County budget books (Archive Center)', 'https://www.baycountyfl.gov/Archive.aspx?ADID=329', BY_HAND, 'Each year, when adopted', 'Adopted budget, funds, departments and constitutional officers\' budgets')
src('budgets', 'schools', 'District Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/dsb_efile%20rpts/2025%20bay%20county%20district%20school%20board.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'pc', 'Panama City budget books (Archive Center)', 'https://www.panamacity.gov/ArchiveCenter/', BY_HAND, 'Each year, when adopted', 'Adopted budget, funds and departments')
src('budgets', 'pcb', 'Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/mun_efile%20rpts/2025%20panama%20city%20beach.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'lh', 'Lynn Haven budget books (Document Center)', 'https://www.cityoflynnhaven.gov/DocumentCenter', BY_HAND, 'Each year, when adopted', 'Adopted budget, funds and departments')
src('budgets', 'cw', 'Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/mun_efile%20rpts/2025%20callaway.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'cw', 'Callaway adopted budget', 'https://www.cityofcallaway.com/DocumentCenter/View/5704/Final-Budget-2627', BY_HAND, 'Each year, when adopted', 'Adopted budget and pay')
src('budgets', 'sp', 'Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/mun_efile%20rpts/2025%20springfield.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'parker', 'Parker audits and financial statements', 'https://cityofparker.com/', BY_HAND, 'Each year', 'Older years\' totals (2016 to 2019)')
src('budgets', 'parker', 'Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/mun_efile%20rpts/2025%20parker.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'mb', 'Mexico Beach adopted budgets', 'https://mexicobeachfl.gov/uploads/2026/10/FY26-27-Budget.pdf', BY_HAND, 'Each year, when adopted', 'Adopted budget and pay')
src('budgets', 'mb', 'Annual Financial Reports (Florida Auditor General)', 'https://flauditor.gov/pages/mun_efile%20rpts/2025%20mexico%20beach.pdf', BY_HAND, 'Each year', 'Revenue, spending and fund totals')
src('budgets', 'state', 'Local Government Financial Reports (Florida EDR)', 'https://edr.state.fl.us/content/local-government/data/revenues-expenditures/', BULK, 'Each year', 'Audited revenue by source and spending by function for every government')

# --- Audits and debt -------------------------------------------------------------------------------------------------
src('audits', 'state', 'Local government audit reports (Florida Auditor General)', 'https://flauditor.gov/', BY_HAND, 'Each year, as audits are filed', 'Audited debt, findings and opinions for every city, the county, the school district, CRAs, the port and the airport')
src('audits', 'state', 'Municipal bond disclosures (MSRB EMMA)', 'https://emma.msrb.org/', BY_HAND, 'As needed', 'Publicly sold bonds and their official statements')
src('audits', 'county', 'Clerk of Court Annual Comprehensive Financial Reports', 'https://apps.baycoclerk.com/', BY_HAND, 'Each year', 'County debt and audited totals')

# --- Property tax ----------------------------------------------------------------------------------------------------
src('property-tax', 'state', 'Florida Department of Revenue property tax data portal', 'https://floridarevenue.com/property/dataportal/', BULK, 'Each year', 'Millage by authority, parcel roll (for exemptions) and the non-ad valorem assessment roll')
src('property-tax', 'state', 'Florida EDR local government data', 'https://edr.state.fl.us/content/local-government/data/revenues-expenditures/', BULK, 'Each year', 'Millage and taxable value history')
src('property-tax', 'state', 'Florida EDR Revenue Estimating Conference (Amendment 3 impact)', 'https://edr.state.fl.us/Content/conferences/revenueimpact/archives/2026F/_pdf/impact0710.pdf', BY_HAND, 'Once', 'Estimated tax impact of the 2026 homestead amendment by county')
src('property-tax', 'state', 'Florida Department of Education school funding (FEFP)', 'https://www.fldoe.org/', BY_HAND, 'Each year', 'School Required Local Effort millage')
src('property-tax', 'county', 'Bay County budget books', 'https://www.baycountyfl.gov/Archive.aspx?ADID=329', BY_HAND, 'Each year', 'Adopted county and MSTU millage')
src('property-tax', 'schools', 'School Board budget hearings (BoardDocs)', 'https://go.boarddocs.com/fl/bcsdfl/Board.nsf/Public', BY_HAND, 'Each year', 'Adopted school millage')

# --- Pay -------------------------------------------------------------------------------------------------------------
src('salaries', 'county', 'County budget and pay plan (PrimeGov attachments)', 'https://baycountyfl.primegov.com/public/portal', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'schools', 'District salary schedules (district website)', 'https://www.bay.k12.fl.us/', BY_HAND, 'Each year', 'Superintendent and leaders\' pay')
src('salaries', 'pc', 'Panama City budget and job postings', 'https://www.governmentjobs.com/careers/pcgov', BY_HAND, 'Each year', 'Department leaders\' pay and pay ranges')
src('salaries', 'pcb', 'Panama City Beach budget and job postings', 'https://www.governmentjobs.com/careers/pcbgov', BY_HAND, 'Each year', 'Department leaders\' pay and pay ranges')
src('salaries', 'lh', 'Lynn Haven budget and job postings', 'https://cityoflynnhaven.com/DocumentCenter/View/4411', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'cw', 'Callaway adopted budget', 'https://www.cityofcallaway.com/DocumentCenter/View/5704/Final-Budget-2627', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'sp', 'Springfield city directory and budget', 'https://www.springfieldfl.net/directory', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'parker', 'Parker city pages and job postings', 'https://cityofparker.com/government/city-council/', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'mb', 'Mexico Beach adopted budget', 'https://mexicobeachfl.gov/uploads/2026/10/FY26-27-Budget.pdf', BY_HAND, 'Each year', 'Department leaders\' pay')
src('salaries', 'officers', 'Constitutional officers\' budgets (county budget book)', 'https://www.baycountyfl.gov/DocumentCenter/View/21091/FY-2027-Final-Budget-Detailed-Revenues-and-Expenditures', BY_HAND, 'Each year', 'Sheriff, Clerk, Property Appraiser, Tax Collector and Supervisor of Elections budgets')
src('salaries', 'officers', 'Airport and Port budgets', 'https://www.iflybeaches.com/airport-district/leadership', BY_HAND, 'Each year', 'Airport and Port leaders\' pay')
src('salaries', 'state', 'Florida EDR elected officials\' salaries report', 'https://www.edr.state.fl.us/Content/local-government/reports/FY%202025-26%20Salaries.pdf', BY_HAND, 'Each year', 'Pay set by state law for county officers and school board members')

# --- Campaign money and elections ------------------------------------------------------------------------------------
src('campaign', 'county-wide', 'Supervisor of Elections campaign finance (VoterFocus)', 'https://www.voterfocus.com/ws/WScand/candidate_pr.php?c=Bay', AUTO_DAILY, 'Daily', 'Summary totals and itemized contributions and expenses for every local campaign since 2016')
src('campaign', 'county-wide', 'Supervisor of Elections candidate finance page', 'https://www.bayvotesfl.gov/candidates/candidate-committee-finances/', BY_HAND, 'Each election', 'Which reporting groups and elections exist')
src('elections', 'county-wide', 'Supervisor of Elections (offices up for election, snapshots)', 'https://www.bayvotesfl.gov/', BY_HAND, 'Each election', 'Races, candidates and status')
src('elections', 'state', 'Florida election night results (Bay County)', 'https://enr.electionsfl.org/BAY/', BY_HAND, 'Each election', 'Official results')

# --- Businesses and nonprofits ---------------------------------------------------------------------------------------
src('businesses', 'state', 'Florida Division of Corporations (Sunbiz) quarterly data file', 'https://dos.fl.gov/sunbiz/other-services/data-downloads/', BULK, 'Quarterly', 'Every business with a county address, its officers, managers and registered agents')
src('businesses', 'state', 'Sunbiz business search', 'https://search.sunbiz.org/', BY_HAND, 'As needed', 'Links to each business\'s state record, used to check matches')
src('chambers', 'county', 'Bay County Chamber of Commerce website (board, staff and programs)', 'https://panamacity.org/board-of-directors/', BY_HAND, 'As boards change', 'Board, staff and past chairs since 2016 by name, title and organization; regular programs')
src('chambers', 'county', 'Panama City Beach Chamber of Commerce website (board, staff and programs)', 'https://pcbeach.org/board-of-directors/', BY_HAND, 'As boards change', 'Board and staff by name, title and organization; regular programs')
src('chambers', 'county', 'Panama City Beach Chamber events calendar feed', 'https://pcbeach.org/local-events/', AUTO_DAILY, 'Daily', 'Upcoming chamber and community events: title, time, venue and link')
src('outdoors', 'state', 'National Weather Service Tallahassee surf zone forecast (coastal Bay County)', 'https://www.weather.gov/beach/tae', AUTO_DAILY, 'Daily, and live on the page', 'The beach flag color reported by beach officials, rip current risk, surf height, UV index, water temperature and beach alerts')
src('outdoors', 'state', 'Florida Department of Health, Florida Healthy Beaches Program', 'https://www.floridahealth.gov/community-environmental-public-health/environmental-public-health/water-quality/beach-water-quality/', AUTO_DAILY, 'Daily', 'Sampling sites and every published enterococcus sample, rating and health advisory')
src('outdoors', 'state', 'Florida DEP coastal access sites', 'https://services1.arcgis.com/nRHtyn3uE1kyzoYc/arcgis/rest/services/BEACH_ACCESS_SITES/FeatureServer', AUTO_DAILY, 'Daily', 'Parking, restrooms, showers, lifeguards and boardwalks at beach accesses')
src('outdoors', 'county', 'Bay County GIS: beach accesses, beach parking, parks inventory, park guide, boat ramps and trails', 'https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services', AUTO_DAILY, 'Daily', 'Every public beach access, county beach lot, park (all governments), boat ramp and trail, with amenities')
src('outdoors', 'pcb', 'Panama City Beach GIS: recreation (beach access, trails)', 'https://services7.arcgis.com/HMHYRsYOvuxpp8zD/arcgis/rest/services/Recreation/FeatureServer', AUTO_DAILY, 'Daily', 'Wheelchair-accessible beach accesses and Conservation Park trails')
src('outdoors', 'county-wide', "Each government's parks and recreation pages", 'https://www.baycountyfl.gov/289/Parks-Recreation', BY_HAND, 'As pages change', 'Links for program and league sign-ups')
src('nonprofits', 'state', 'IRS exempt organization and 990 data (GivingTuesday 990 data lake)', 'https://990data.givingtuesday.org/', BULK, 'As new filings post', 'Organizations, 990, 990-EZ, 990-PF and 990-N filings since 2019: board members, pay, grants and finances')
src('nonprofits', 'state', 'ProPublica Nonprofit Explorer', 'https://projects.propublica.org/nonprofits/', BY_HAND, 'As needed', 'Links to each organization\'s filings')
src('nonprofits', 'state', 'Florida Check-A-Charity (Department of Agriculture and Consumer Services)', 'https://csapp.fdacs.gov/', BULK, 'As needed', 'Charity registrations, reported finances, fundraisers, officers and directors')
src('nonprofits', 'state', 'Sunbiz nonprofit corporations', 'https://search.sunbiz.org/', BULK, 'Quarterly', 'Active nonprofit corporations and their officers')

# --- CRAs ------------------------------------------------------------------------------------------------------------
src('cra', 'pc', 'Panama City CRA reports, agendas and budgets', 'https://www.panamacity.gov/AgendaCenter', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'pcb', 'Front Beach Road CRA reports and budgets', 'https://pcbfl.gov/', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'lh', 'Lynn Haven CRA reports and agendas', 'https://www.cityoflynnhaven.com/', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'cw', 'Callaway CRA agendas and audits', 'https://www.cityofcallaway.com/AgendaCenter', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'sp', 'Springfield CRA documents', 'https://www.springfieldfl.net/', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'parker', 'Parker CRA documents and audits', 'https://cityofparker.com/', BY_HAND, 'As reports post', 'Ledger of CRA payments and projects')
src('cra', 'county', 'Bay County budget books (tax increment paid to CRAs)', 'https://www.baycountyfl.gov/Archive.aspx?ADID=329', BY_HAND, 'Each year', 'County payments to each CRA, used to check the estimate')
src('cra', 'state', 'Florida Statutes, Chapter 163 Part III (CRA law)', 'https://www.leg.state.fl.us/', BY_HAND, 'As needed', 'Rules for CRA sunsets and spending')

# --- Disaster, sales tax, tourist tax --------------------------------------------------------------------------------
src('michael', 'state', 'OpenFEMA Public Assistance (DR-4399-FL)', 'https://www.fema.gov/api/open', AUTO_WEEKLY, 'Weekly', 'Every funded project and applicant for Hurricane Michael')
src('sales-tax', 'county', 'Bay County GIS: sales tax projects map', 'https://gis.baycountyfl.gov/arcgis/rest/services/SurtaxProjects/MapServer', AUTO_WEEKLY, 'Weekly', 'Every infrastructure sales tax project, its status and location')
src('sales-tax', 'county', 'Bay County half-cent sales tax site', 'https://bayhalfcent.com/', BY_HAND, 'As updated', 'Project schedule and spending reports')
src('sales-tax', 'lh', 'Lynn Haven sales tax project list', 'https://www.cityoflynnhaven.com/', BY_HAND, 'As updated', 'City share of sales tax projects')
src('tourist-tax', 'officers', 'Clerk of Court monthly tourist development tax reports', 'https://www.baycoclerk.com/', BY_HAND, 'Monthly', 'Bed tax collections by zone')
src('tourist-tax', 'officers', 'Clerk of Court check registers (OnBase public records search)', 'https://bayforms.baycoclerk.com/PublicAccess/PublicRecordSearch/', BY_HAND, 'Monthly', 'Payments by Visit Panama City Beach, Destination Panama City and the Mexico Beach CDC')
src('tourist-tax', 'county-wide', 'Bay County tourist tax zones (ArcGIS)', 'https://services1.arcgis.com/', BY_HAND, 'As updated', 'Bed tax collection zone map')
src('tourist-tax', 'state', 'Florida EDR local option tax data (tourist and sales tax rates, history)', 'https://edr.state.fl.us/Content/local-government/data/data-a-to-z/', BULK, 'Each year', 'Tax rates, collections history and realized tourism tax')

# --- Fees, address lookups, officials, records, news -----------------------------------------------------------------
src('fees', 'state', 'Florida DOR non-ad valorem assessment roll (NAV file)', 'https://floridarevenue.com/property/dataportal/', BULK, 'Each year', 'Every special assessment levied on county parcels')
src('fees', 'county', 'Bay County fee schedules and budget', 'https://www.baycountyfl.gov/', BY_HAND, 'Each year', 'Stormwater, solid waste and other county fees')
src('fees', 'pc', 'Panama City utility rates and fees', 'https://www.panamacity.gov/', BY_HAND, 'Each year', 'Water, sewer, trash and fire assessment rates')
src('fees', 'pcb', 'Panama City Beach utility rates and fees', 'https://www.pcbfl.gov/', BY_HAND, 'Each year', 'Utility and fire assessment rates')
src('fees', 'lh', 'Lynn Haven utility rates and fees', 'https://cityoflynnhaven.com/', BY_HAND, 'Each year', 'Utility rates')
src('fees', 'cw', 'Callaway utility rates and fees', 'https://www.cityofcallaway.com/', BY_HAND, 'Each year', 'Utility rates')
src('fees', 'sp', 'Springfield utility rates and fees', 'https://www.springfieldfl.net/', BY_HAND, 'Each year', 'Utility and fire assessment rates')
src('fees', 'parker', 'Parker utility rates and fees', 'https://cityofparker.com/', BY_HAND, 'Each year', 'Utility rates')
src('address', 'county-wide', 'Bay County GIS map server', 'https://gis.baycountyfl.gov/arcgis/rest/services', LIVE, 'Each search', 'Parcels, tax districts, zoning, commission districts, school zones and evacuation zones')
src('address', 'state', 'FEMA National Flood Hazard Layer', 'https://hazards.fema.gov/arcgis/rest/services', LIVE, 'Each search', 'Flood zone at the address')
src('address', 'pc', 'Panama City map layers (ArcGIS)', 'https://services3.arcgis.com/RfAh242jlP6Nb5vP/arcgis/rest/services', LIVE, 'Each search', 'City zoning and nearby development')
src('address', 'county-wide', 'Bay County Property Appraiser', 'https://www.baypa.net/', LIVE, 'Each search', 'Link to the parcel\'s official record')
src('officials', 'county-wide', 'Election results, minutes and budget books', 'https://www.bayvotesfl.gov/', BY_HAND, 'As seats change', 'Who held each seat and when')
src('records', 'county-wide', 'Each agency\'s official public records page', 'https://www.baycountyfl.gov/', BY_HAND, 'As pages change', 'Records custodians, portals, emails and policies for 24 agencies')
src('news', 'county-wide', 'Local news (WJHG, News Herald, WMBB and others)', 'https://www.wjhg.com/', BY_HAND, 'As needed', 'Context where no official document says it')
src('news', 'state', 'U.S. Department of Justice press releases', 'https://www.justice.gov/', BY_HAND, 'As needed', 'Public corruption cases involving local officials')


def _meeting_rows():
    """One row per board's agenda system and calendar, from the meetings fetch."""
    try:
        boards = json.load(open(os.path.join(DATA, 'meetings', 'meetings.json')))['boards']
    except (OSError, ValueError, KeyError):
        return []
    out = []
    for b in boards:
        gov = b.get('gov') if b.get('gov') in GOV_NAME else 'county-wide'
        systems = b.get('sources') or {}
        names = ', '.join(systems) if isinstance(systems, dict) else ''
        out.append(('meetings', gov, f"{b['name']}: agendas{f' ({names})' if names else ''}", b.get('source_url') or '', AUTO_30, 'Every 30 minutes on weekdays, and twice a day',
                    'Meeting dates, agendas, packets, minutes and agenda items'))
        cal = b.get('calendar_url')
        if cal and cal != b.get('source_url'):
            out.append(('meetings', gov, f"{b['name']}: calendar", cal, AUTO_DAILY, 'Daily', 'Upcoming meeting dates and times'))
    return out


def rows():
    """Rows for dataset data-sources: one per source."""
    out = []
    for topic, gov, name, url, method, refresh, what in _meeting_rows() + S:
        t = TOPIC[topic]
        out.append({'topic': t[1], 'topic_id': topic, 'government': GOV_NAME[gov], 'government_id': gov,
                    'source_name': name, 'source_url': url, 'method': method, 'refresh': refresh, 'what_we_take': what,
                    'how_we_process': t[3], 'checks': t[4], 'page': t[2]})
    return out


# Data folders -> the topic their records belong to, for counting cited websites.
FOLDER_TOPIC = {
    'agendas': 'meetings', 'meetings': 'meetings', 'votes': 'votes', 'contracts': 'contracts', 'budgets': 'budgets',
    'debt_audit': 'audits', 'money': 'audits', 'tax': 'property-tax', 'amendment3': 'property-tax', 'exemptions': 'property-tax',
    'salaries': 'salaries', 'campaign': 'campaign', 'elections': 'elections', 'sunbiz': 'businesses', 'careers': 'businesses',
    'nonprofits': 'nonprofits', 'chambers': 'chambers', 'outdoors': 'outdoors', 'cra': 'cra', 'merged.json': 'cra', 'michael': 'michael', 'surtax': 'sales-tax',
    'tourism': 'tourist-tax', 'fees': 'fees', 'nearby': 'address', 'civic': 'records', 'projects': 'contracts',
}
SKIP_HOSTS = {'baycounty.me', 'www.baycounty.me', 'aptg.co'}
URL_RE = re.compile(r'https?://[^\s"\'<>)\\]+')


def site_rows():
    """Rows for dataset data-source-sites: every website the site's data files cite, with how many distinct
    documents and pages from it, per topic."""
    seen = collections.defaultdict(set)
    for f in glob.glob(os.path.join(DATA, '**', '*.json'), recursive=True):
        rel = os.path.relpath(f, DATA).split(os.sep)
        topic = FOLDER_TOPIC.get(rel[0])
        if not topic or os.path.getsize(f) > 80_000_000:
            continue
        try:
            text = open(f, encoding='utf-8').read()
        except (OSError, UnicodeDecodeError):
            continue
        for u in URL_RE.findall(text):
            host = u.split('/')[2].lower().split(':')[0]
            if host in SKIP_HOSTS or '.' not in host:
                continue
            seen[(host, topic)].add(u.rstrip('.,;'))
    out = []
    for (host, topic), urls in seen.items():
        out.append({'website': host.removeprefix('www.'), 'topic': TOPIC[topic][1], 'topic_id': topic, 'documents_cited': len(urls),
                    'source_url': f'https://{host}/'})
    # merge www. and bare hosts
    merged = {}
    for r in out:
        k = (r['website'], r['topic_id'])
        if k in merged:
            merged[k]['documents_cited'] += r['documents_cited']
        else:
            merged[k] = r
    return sorted(merged.values(), key=lambda r: (-r['documents_cited'], r['website'], r['topic']))
