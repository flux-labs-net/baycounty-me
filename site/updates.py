"""Change log for baycounty.me: drives the 'Updated' line on each page, /updates and /updates.xml (RSS).

Add an entry at the TOP of CHANGES whenever a page's data changes. 'pages' lists the
paths the change touched; each page shows the date of its most recent entry.
"""
from datetime import date
from email.utils import format_datetime
from datetime import datetime, timezone
import html

CHANGES = [
    {'date': '2026-10-27', 'title': "What's happening in Bay County",
     'text': "The home page now opens its second section with what's happening today and coming soon around the county, and a new Events page lists the next two months in one calendar you can filter by town and kind: city and county events and meetings, library programs, visitor events in Panama City and Mexico Beach, and Panama City Beach Chamber events. Everything is read every morning from each organizer's public calendar, and each title links to the organizer's page. Chamber board and staff photos from the chambers' own websites now appear on the Chambers page. The apps have the same events on their home screens.",
     'pages': ['/', '/events', '/chambers', '/meetings', '/open-data', '/developers']},
    {'date': '2026-10-27', 'title': 'Beaches and parks',
     'text': "Two new pages under a new Outdoors menu. Beaches shows today's beach flag and rip current risk (the flag color beach officials report to the National Weather Service, refreshed when you open the page), the next few days' surf forecast, what each flag means, the state health department's water quality samples at all 15 active sampling sites (each sample since late 2022, rated good, moderate or poor), and all 152 public beach accesses and the county's beach parking lots on a map, with wheelchair and drive-on access. Parks lists 107 public parks with their playgrounds, restrooms, fields, courts, piers and trails, 45 boat ramps and launches, 36 named trails, a map with directions, and each government's page for leagues, programs and rentals. The apps have the same screens.",
     'pages': ['/beaches', '/parks', '/open-data', '/developers']},
    {'date': '2026-10-27', 'title': 'Building, development and road projects',
     'text': "Two new pages. Building and development shows how many new homes are permitted each year since 2016 in the county and each city (from the Census Bureau's permit survey), and the commercial buildings, subdivisions and apartments in the county's planning review, with their status and dates on a map. Road projects shows the state highway work under way and what each FDOT contract costs, FDOT's five-year plan for local roads, the contractors (linked to their profiles, with what local governments paid them), and the county and city road jobs paid for by the half-cent sales tax. Both refresh every week, and the apps list the same records.",
     'pages': ['/development', '/roads', '/public-money/sales-tax-projects', '/open-data', '/developers']},
    {'date': '2026-10-27', 'title': 'Chambers of commerce',
     'text': "A new page covers Bay County's two chambers of commerce, the Bay County Chamber and the Panama City Beach Chamber: who sits on their boards and staff (each name links to a profile with the person's other boards and records), the organizations those board members represent and what local governments paid them, upcoming chamber and community events, regular programs such as First Friday and Friday at the Beach, each chamber's IRS filings, and the tourism agency money paid to them. Board lists are copied from the chambers' own websites; no contact details are published. The apps have the same screen.",
     'pages': ['/chambers', '/connections/nonprofits', '/people', '/open-data', '/developers']},
    {'date': '2026-10-26', 'title': 'Where our data comes from',
     'text': "A new page lists every source behind BayCounty.me: each government's agenda system, calendar, minutes, budgets and fee schedules, and every state and federal database we use (Florida Auditor General, Department of Revenue, EDR, Sunbiz, the Supervisor of Elections, IRS filings, OpenFEMA and more). For each one it shows the link, whether we fetch it automatically or read it by hand, how often, what we take and how we check it, plus a count of every website our records cite. A notice at the top of every page also says the data is still being loaded and checked, so some totals may change.",
     'pages': ['/data-sources', '/about', '/open-data']},
    {'date': '2026-10-25', 'title': 'The site now starts in 2016',
     'text': "BayCounty.me now covers 2016 onward: fiscal year 2016 for budgets and other yearly figures, and 2016 for dated records. Older figures came off every page, download and the API: FY2015 budgets and audited actuals, CRA tax increment from FY2003 to FY2015, CRA spending records from before 2016, officeholder terms that ended before 2016, older events in the Accountability timelines (and the Front Beach Road Segment 1 project, built 2009 to 2013), and nonprofit board seats, grants and charity registrations from before 2016. Year pickers start at 2016.",
     'pages': ['/public-money/budget-compare', '/governments', '/public-money/cra-tax-increment', '/public-money/cra-spending', '/public-money/accountability', '/connections/nonprofits', '/people', '/open-data', '/developers']},
    {'date': '2026-10-25', 'title': 'Every local campaign since 2016',
     'text': "Campaign money now goes back to 2016. A new Past elections page lists every candidate who ran for a local office in Bay County from 2016 through 2025, winners and losers (342 campaigns that raised $5.2M), with what each raised and spent and every business, committee and party that gave. Those gifts also feed the Connections network, the vendor pages' donor matches and people's profiles, and each past candidate has a profile. Gifts from individual people are still counted only in totals. The Supervisor of Elections' online records start in 2016, so 2015 is not included.",
     'pages': ['/elections/past', '/elections', '/connections', '/connections/campaign-gifts', '/people', '/public-money/vendors', '/open-data', '/developers']},
    {'date': '2026-10-25', 'title': 'How much property tax goes to the CRAs',
     'text': "A new page estimates how much property tax Bay County and the cities pay to the seven Community Redevelopment Agencies each year: about $28.7M in FY2025, $25.8M of it from Bay County and three-quarters of it to Panama City Beach's Front Beach Road CRA. It shows who pays, what has been paid since FY2016, sunset dates and what could still be paid under three growth scenarios, checked against the county's own budget figures. The method and the missing years are on the page.",
     'pages': ['/public-money/cra-tax-increment', '/public-money/tax-dollars', '/public-money/amendment-3', '/governments', '/open-data', '/developers']},
    {'date': '2026-10-25', 'title': 'Fewer pages, more on each government',
     'text': "Each government's page now carries its whole budget (every fund and department, and what each service costs per resident), every debt and bond, every audit finding from the last three years, and its savings ideas. Compare shows the side-by-side totals, including cost per resident by service. Tourism agency payments moved onto the Tourist tax page, county officers and officials' pay onto People, and the money map into Connections as Donors and votes. The old pages send you to the new spot.",
     'pages': ['/governments', '/compare', '/public-money/tourist-tax', '/people', '/connections', '/public-money/tax-dollars']},
    {'date': '2026-10-25', 'title': 'Budgets back to 2016',
     'text': "The budget comparison now reaches back further. Bay County has every adopted budget from FY2016 to FY2027, fund by fund, from the county's budget archive. Panama City has FY2017 to FY2022 by fund group, read from its scanned budget books, and its General Fund for FY2016 and FY2023-24 using the city's audited financial reports, and Lynn Haven adds FY2020 with every fund and department. Audited revenue and spending for the county and all seven cities now go back to FY2016. For Panama City Beach, Callaway, Springfield, Parker, Mexico Beach and the school district, the General Fund budget for FY2021 to FY2025 comes from each year's audited financial report (Parker back to FY2016); their older budget books aren't posted online. The page lists which years each government has.",
     'pages': ['/public-money/budget-compare', '/governments', '/open-data']},
    {'date': '2026-10-25', 'title': 'Compare a budget across years',
     'text': "A new page compares any government's budget in two fiscal years, such as Lynn Haven FY2025 and FY2026 or FY2022 and FY2026: the total, the General Fund, every department, every service and every fund, with the dollar and percent change. Lynn Haven has every adopted budget from FY2021 to FY2027 line by line, read from the city's budget documents; the other governments have FY2026 and, where posted, FY2027 lines, plus totals for earlier years. Audited revenue and spending can be compared for FY2021 to FY2024. Lynn Haven's FY2025 budget is now the original adopted figure ($52.2M); the city amended it to $64.9M at mid-year.",
     'pages': ['/public-money/budget-compare', '/public-money/budget-explorer', '/governments', '/developers', '/open-data']},
    {'date': '2026-10-24', 'title': 'Business owners who gave are now named',
     'text': "People who run a registered business and gave to a local campaign are now listed by name, with the businesses they run and every campaign they gave to. A donor is listed only when the name and street address on the campaign filing are the same as an officer, manager or registered agent on the state business registry. Other individual donors are still counted only in totals, and addresses are never shown.",
     'pages': ['/connections/campaign-gifts', '/people']},
    {'date': '2026-10-24', 'title': 'Profiles for every name, linked everywhere',
     'text': "Every elected official, department leader and 2026 candidate now has a profile page with where they serve, campaign gifts from businesses and groups, recorded votes, votes on donors' contracts, pay and a map of their connections. Every other company, nonprofit, nonprofit board member, registered business and committee in the records has a profile too, with every documented connection and its source. Vendor and government pages gained the same connection map. Names of officials, companies and nonprofits are now links to their profiles across the site. Individual campaign donors are still never named, and officials' board seats and businesses appear only after an editor checks the match.",
     'pages': ['/people', '/connections', '/connections/nonprofits', '/public-money/vendors', '/governments', '/developers', '/open-data']},
    {'date': '2026-10-24', 'title': 'Connections: one network for every government',
     'text': "Campaign gifts and payee connections now have their own section, Connections, instead of sitting under the CRA pages. The network covers every government and agency with payment records: the county, the cities, the redevelopment agencies and the tourism agencies, across contracts, change orders, emergency purchases, check registers, tourism payments and the CRA ledger. It shows business gifts to every official who approves that spending, not only CRA board members, so 29 businesses that were paid and gave to a campaign now appear, up from 4. Campaign Money is now Campaign Gifts, and it and the Money map moved into the section; old links still work. Only businesses, PACs and committees are named as donors.",
     'pages': ['/connections', '/connections/campaign-gifts', '/connections/money-map', '/public-money/cra-spending']},
    {'date': '2026-10-23', 'title': 'Savings finder: where governments could spend less',
     'text': "A new page lists places Bay County's local governments could spend less, found in records already on the site: Front Beach Road segments still ahead after the finished ones ran over, CRA capital budgets left mostly unspent, engineering bought in many separate task orders, and services such as plate readers and paving bought separately. Each opportunity shows the projects or ledger rows it rests on, a low and high estimate with its stated assumption, the next question to ask and a ready-to-send records request. Estimates are illustrative, not findings that money was wasted.",
     'pages': ['/public-money/savings', '/public-money/accountability', '/public-money/cra-spending']},
    {'date': '2026-10-23', 'title': 'CRA network: payees, connections and campaign gifts',
     'text': "A new page shows every payee in the CRA ledger as a network: who each redevelopment agency paid, payees tied to each other by the same project, address or subcontract, and business campaign gifts to the officials who sit as each CRA's board. Four businesses both received money from a CRA record and gave to a campaign. A map and a ranked payee list use the same filters. Only businesses and PACs are shown as donors, and a gift and a payment together are facts about the records, not evidence of why either happened.",
     'pages': ['/connections', '/public-money/cra-spending', '/connections/money-map']},
    {'date': '2026-10-23', 'title': 'Pages now open on the current year',
     'text': "Lists and tables with several years of records now open on the newest year that has records, never past the current fiscal year, with All years one tap away. That covers the Accountability console (and its headline numbers), CRA Spending, Contracts, How They Voted, Sales Tax Projects, the Hurricane Michael FEMA ledger, audit findings and other multi-year tables. A year with only a few stray records is skipped. Who Gets Paid now sorts by FY2026. Add ?year=all (or a year) to any page link to choose. Debt lists still show everything owed today.",
     'pages': ['/public-money/accountability', '/public-money/cra-spending', '/public-money/contracts', '/public-money/votes', '/public-money/sales-tax-projects', '/public-money/hurricane-michael', '/public-money/audits', '/public-money/who-gets-paid']},
    {'date': '2026-10-23', 'title': 'Accountability console: projects from budget to close-out',
     'text': "A new page follows public projects from the first budget to the day they close: approvals, contracts, change orders, the votes on them, payments and the final cost, each with its source. Questions are raised only by nine published rules (cost growth over 10%, running late, figures that don't agree, an unnamed payee and others), the same way for every government, and each is a question for the agency rather than a finding. Each project shows the records that would answer its questions, as ready-to-send records requests, and where the agency's reply stands. It starts with 18 project histories reviewed by hand, 37 contracts with change orders and 39 scheduled sales tax projects.",
     'pages': ['/public-money/accountability', '/records-request', '/open-data']},
    {'date': '2026-10-22', 'title': 'A privacy page, and data for the iPhone app',
     'text': "A new privacy page says what the site and the BayCounty.me iPhone app collect: no accounts, no ads and no tracking. The site now also publishes the files the app reads, in /data/app: the tax and Amendment 3 calculators, the glossary, company and people profiles and the money map. They hold the same information the pages already show.",
     'pages': ['/privacy', '/developers']},
    {'date': '2026-10-21', 'title': 'Company pages, and one map of public money',
     'text': "Every company with more than one record now has its own page: its contracts, change orders, payments, CRA money, gifts from the business to campaigns, and the votes that approved its contracts with how each member voted. A gift near a vote does not show why anyone voted the way they did. A new map shows CRA spending and 1,062 sales tax projects over CRA districts and city limits. Hurricane Michael projects are not on it because FEMA does not publish their locations.",
     'pages': ['/public-money/vendors', '/public-money/map', '/public-money/contracts', '/public-money/who-gets-paid', '/connections/money-map']},
    {'date': '2026-10-21', 'title': 'New votes, FY2027 budgets, contracts and tourism payments',
     'text': "Added 30 votes (Panama City CRA and Commission, Callaway Commission and CRA) with each member's vote; the FY2027 budgets adopted in September for all nine governments; 17 contracts, mostly Springfield and Callaway; and tourism agency payments for 18 more months, each checked against the register's printed totals. Bay County Commission minutes after June 16 are not posted yet.",
     'pages': ['/public-money/votes', '/public-money/tax-dollars', '/public-money/contracts', '/public-money/who-gets-paid', '/public-money/cra-spending']},
    {'date': '2026-10-21', 'title': 'My Address: your officials, nearby spending, and privacy',
     'text': "My Address now links each local official to how they voted and to campaign money, lists CRA spending and sales tax projects near you, and links to your government's contracts, meetings and budget. To protect owners' privacy it no longer shows which kinds of exemptions a parcel gets (such as disability or veteran exemptions); it shows homestead and one total for all other exemptions.",
     'pages': ['/my-address', '/public-money/exemptions']},
    {'date': '2026-10-21', 'title': 'Share any view; alerts you choose; Spanish pages',
     'text': "Filters now stay in the page link, so you can share exactly what you are looking at. Search results open the record itself. You can now get an email when a contract over an amount you pick is approved, when a board member votes, or when an agenda mentions a word you choose, and change what you follow at any time. Tax Dollars, Fees and Bills, Exemptions, Elections and Meetings are now in Spanish.",
     'pages': ['/alerts', '/search', '/updates']},
    {'date': '2026-10-21', 'title': 'Contracts: how much each contract grew',
     'text': "Change orders are now added up for each contract and measured against its original amount, instead of listed one by one. Of the 22 contracts whose original amount is known, 12 grew by more than 10%, the point where Bay County and Panama City rules require board approval for the added cost. Each bar opens to its change orders, reasons and sources. Contracts whose original amount wasn't in the agendas are listed separately, and where an agenda states the new contract total, that total is used. Every individual change order is still listed below.",
     'pages': ['/public-money/contracts']},
    {'date': '2026-10-21', 'title': 'Contracts: one name per company, and company cards',
     'text': "Agendas, check registers and campaign reports spell the same company many ways, so the contract winners list was splitting some firms into two or more entries. The 322 contracts used 206 spellings; they now resolve to the companies behind them. Marshall Brothers, for example, had been listed at $11.1M and is now ranked sixth at $24.0M. A new Look up a company section shows everything on the site for one company: contracts by government next to what each government paid it (where a check register shows it), change orders, emergency purchases, campaign gifts from the company, and votes on its contracts by officials it gave to. Insurance pools owned by governments (Florida League of Cities, PGIT) are no longer counted as contractor wins.",
     'pages': ['/public-money/contracts']},
    {'date': '2026-10-21', 'title': 'Money map: full roll calls on donor contract votes',
     'text': "The table of votes on a donor's contract now shows each vote once, with every board member's vote, not only the members who received a gift from the business. Members who got a gift are listed first, with the amount and date. Most of these contracts passed unanimously on the consent agenda. One vote that had been left out was added: Panama City's June 24, 2025 award of the Millville plant generator bid to Marshall Brothers, which the minutes record under an unrelated plat item.",
     'pages': ['/connections/money-map']},
    {'date': '2026-10-21', 'title': 'Sort, filter and download every list',
     'text': 'Every table and list on the site can now be sorted by clicking a column heading, filtered with a search box (and drop-downs where a column has a few values), and downloaded as a CSV of exactly the rows on screen, in the order shown. Lists open newest first, then A to Z; upcoming meetings open soonest first.',
     'pages': ['/updates']},
    {'date': '2026-10-21', 'title': 'An API for BayCounty.me',
     'text': 'Every dataset on the site is now available through a free, read-only API with filtering, sorting and CSV output, plus an MCP server so AI assistants can look up and cite these records directly.',
     'pages': ['/developers']},
    {'date': '2026-10-21', 'title': 'Correction: Money map',
     'text': "The first version of the Money map overstated connections. It counted a donor's contracts again for every official the donor gave to, which roughly doubled the government totals, and it drew lines from officials to governments they don't serve on. The map now puts each donor in the middle: campaign gifts on one side, the governments that pay the donor on the other, each counted once. It marks only gifts to an official whose own government pays that donor, and lists the recorded votes those officials cast on that donor's contracts. The heat map that credited contract dollars to individual officials was removed.",
     'pages': ['/connections/money-map']},
    {'date': '2026-10-21', 'title': "Who's running in 2026",
     'text': "Every local race on Bay County ballots this year, with each candidate's platform in their own words, links to their campaigns, and their campaign money: what they raised and spent, how much came from individuals, organizations and their own pockets, and every business or committee that gave. Races already decided are shown separately.",
     'pages': ['/elections']},
    {'date': '2026-10-21', 'title': 'Property tax exemptions, and exemptions on My Address',
     'text': "A new page shows every property tax exemption in the 2026 tax roll, from homestead to disabled veterans, with how many homes get each and how much tax it takes off bills. My Address now lists each exemption on a home by name and uses the certified school and non-school taxable values, which corrects estimates for fully exempt homes and for seniors with the county senior exemption.",
     'pages': ['/public-money/exemptions', '/my-address']},
    {'date': '2026-10-21', 'title': 'School Board votes, and more city votes',
     'text': 'How They Voted now includes 104 School Board votes from January 2024 to September 2026 with each member\'s vote, including budgets, millage and major contracts; all 2024 Panama City Beach council votes, including the FY2025 budget; and Springfield votes from mid-2024 to October 2026, including both final budget hearings.',
     'pages': ['/public-money/votes']},
    {'date': '2026-10-21', 'title': 'Money map',
     'text': 'An interactive map of which businesses and groups gave to which officials, and where those same donors hold contracts with a local government, plus heat maps of giving by government and of contract dollars held by each official\'s donors.',
     'pages': ['/connections/money-map']},
    {'date': '2026-10-21', 'title': 'Budget explorer',
     'text': "Open any government's FY2026 budget: spending by fund, General Fund spending by department, and revenue by source. Includes Callaway's and Parker's adopted budgets, which weren't on the site before.",
     'pages': ['/public-money/budget-explorer']},
    {'date': '2026-10-21', 'title': 'Who gets paid: tourism agencies',
     'text': "Payments by Visit Panama City Beach, Destination Panama City and the Mexico Beach CDC, read from the Clerk of Court's check registers and checked against each month's printed total.",
     'pages': ['/public-money/who-gets-paid']},
    {'date': '2026-10-21', 'title': 'Every bond, note and loan',
     'text': 'The Debt page now lists each of 61 bond, note and loan issues with the amount borrowed, what is still owed, the rate, the final payment date and what it paid for.',
     'pages': ['/public-money/debt']},
    {'date': '2026-10-21', 'title': 'A page for each government',
     'text': "Bay County, the School Board and each of the seven cities now have one page that pulls together who runs it, its budget and property tax rate, debt, audit findings, recorded votes, contracts, projects and upcoming meetings.",
     'pages': ['/governments']},
    {'date': '2026-10-21', 'title': 'Compare governments side by side',
     'text': 'Pick any governments and compare budgets, tax rates, debt and staffing, in total or per resident.',
     'pages': ['/compare']},
    {'date': '2026-10-21', 'title': 'Upcoming public meetings',
     'text': "Every board's next meetings, with agenda links and the money items on each agenda, checked daily. Add them all to your phone or computer calendar with one link.",
     'pages': ['/meetings']},
    {'date': '2026-10-21', 'title': 'Campaign money and contracts',
     'text': "The most recent campaign of each current elected official: how much they raised, from individuals and organizations, and which donors also hold contracts with local governments. Individual donors are counted, not named; each official's full report is linked.",
     'pages': ['/connections/campaign-gifts']},
    {'date': '2026-10-21', 'title': 'Request a public record',
     'text': "Pick a government and a record this site is missing, or describe your own, and get a ready-to-send Florida public records request with the right office's contact details.",
     'pages': ['/records-request']},
    {'date': '2026-10-21', 'title': 'Open data downloads',
     'text': 'Every dataset on the site, as CSV and JSON files you can open in a spreadsheet, with a description of each column.',
     'pages': ['/open-data']},
    {'date': '2026-10-21', 'title': 'Zoning and development near your address',
     'text': 'My Address now shows the zoning and future land use at the address, development projects and orders within half a mile, recent rezonings, and conditional uses nearby.',
     'pages': ['/my-address']},
    {'date': '2026-10-21', 'title': 'BayCounty.me en español',
     'text': 'My Address, the records request tool and the glossary are now available in Spanish. Mi dirección, solicitudes de registros y el glosario, en español.',
     'pages': ['/es']},
    {'date': '2026-10-21', 'title': 'Address lookup understands more ways of typing an address',
     'text': 'My Address now finds addresses typed with full street types (Drive, Avenue, Boulevard), directions (North, West), highway forms (Hwy 98, US 98, County Road 2321), Saint or St., spelled-out numbers (Tenth Street), MLK, unit numbers, and a city, state and ZIP on the end. If a street type is wrong, it shows the closest matches.',
     'pages': ['/my-address']},
    {'date': '2026-10-21', 'title': 'Votes: filters and corrections',
     'text': 'Filter recorded votes by government, member, year and outcome, sort by date, amount or closest margin, and share a filtered view by link. Corrections checked against the original minutes: removed two Lynn Haven votes counted twice from a second copy of the same minutes; fixed member votes on a Lynn Haven CRA vote and a Panama City Beach vote that had been misread; restored amounts cut off or misread from scanned pages; and noted fiscal-year and resolution-number typos that appear in the minutes themselves.',
     'pages': ['/public-money/votes']},
    {'date': '2026-10-21', 'title': 'Clearer vote summaries',
     'text': 'Every recorded vote now has a plain-English headline and summary saying what was decided, rewritten from the motion in the minutes. The earlier text was pasted from the minutes and was often hard to read. Each card shows who voted which way and links to the minutes.',
     'pages': ['/public-money/votes']},
    {'date': '2026-10-21', 'title': 'Correction: flood zones on My Address',
     'text': "Flood zones now come live from FEMA's National Flood Hazard Layer, which reflects Bay County's October 24, 2024 flood maps. The earlier lookup used an older county copy that missed high-risk zones for some addresses (about 8% in a sample of 300) and showed outdated base flood elevations. Results now also show the FIRM panel and any map revision, with a link to check the address on FEMA's map. Thanks to the readers who reported it.",
     'pages': ['/my-address']},
    {'date': '2026-10-21', 'title': 'Link previews',
     'text': 'Every page now shows a title, summary and image with its headline number when a link is shared in a text, email or social post.',
     'pages': ['/']},
    {'date': '2026-10-21', 'title': 'Send a correction from the site',
     'text': 'A contact form on the About page sends corrections, records and questions straight to the BayCounty.me team. Email is optional and only used to reply.',
     'pages': ['/about']},
    {'date': '2026-10-21', 'title': 'Correction: Lynn Haven commission, and a cleaner officials page',
     'text': 'Corey Langford is listed as Lynn Haven\'s fifth commissioner; Judy Tinder\'s recorded votes remain on the votes page as a former member. The officials page now shows each board as a simple roster, with notes under names and county officers as cards. Springfield and Parker are described as clerk-run cities with no manager, and Parker\'s City Clerk, Rachelle Stanley, is listed.',
     'pages': ['/who-runs-bay-county', '/public-money/votes']},
    {'date': '2026-10-20', 'title': 'How they voted',
     'text': 'Recorded votes on budgets, tax rates, contracts, land and borrowing, with every member\'s vote and split votes first. Now covers the County Commission and every city: 351 votes, 115 of them split.',
     'pages': ['/public-money/votes']},
    {'date': '2026-10-20', 'title': 'Contracts and vendors',
     'text': 'Major contracts approved by Bay County and its cities since October 2022: winners, how they were awarded, change orders, emergency purchases, the bidding rules, and who the county actually paid the most.',
     'pages': ['/public-money/contracts']},
    {'date': '2026-10-20', 'title': 'Fees, utility bills and who runs Bay County',
     'text': 'Every flat fee on Bay County tax bills, a typical monthly water, sewer and garbage bill in each city, and a guide to every elected seat, appointed manager and top salary. My Address now shows the actual fees on each parcel.',
     'pages': ['/public-money/fees-and-bills', '/who-runs-bay-county', '/my-address']},
    {'date': '2026-10-20', 'title': 'Designed PDF reports, and a new home page',
     'text': 'Export PDF now builds a formatted report on every page, with tables, charts, maps and source links. The home page shows headline numbers and every topic.',
     'pages': ['/', '/my-address', '/public-money/cra-spending', '/public-money/tax-dollars']},
    {'date': '2026-10-20', 'title': 'Tourist tax and sales tax projects',
     'text': 'The 5% bed tax: ten years of collections, how the pennies are split and what Visit Panama City Beach spends. Plus a map of 1,062 half-cent sales tax projects with their status, and the school half-cent.',
     'pages': ['/public-money/tourist-tax', '/public-money/sales-tax-projects']},
    {'date': '2026-10-20', 'title': 'Debt and audit findings',
     'text': 'What every Bay County government owes, including big single payments ahead, and three years of audit findings in plain English, from audits filed with the Florida Auditor General.',
     'pages': ['/public-money/debt', '/public-money/audits']},
    {'date': '2026-10-20', 'title': 'Search, and Hurricane Michael recovery money',
     'text': 'New: search across every page and record. New page tracking FEMA, HUD and state Hurricane Michael money in Bay County, with all 765 FEMA projects.',
     'pages': ['/search', '/public-money/hurricane-michael']},
    {'date': '2026-10-20', 'title': 'My Address',
     'text': 'Look up any Bay County address for a tax estimate, representatives, schools, flood and evacuation zones, and CRA status. Uses the 2026 property roll.',
     'pages': ['/my-address', '/']},
    {'date': '2026-10-20', 'title': 'Amendment 3, and the homestead exemption fix',
     'text': 'New Amendment 3 page with the state\'s estimates for every Bay County government. Calculators now use the inflation-adjusted second homestead exemption ($25,722 for FY2026 bills).',
     'pages': ['/public-money/amendment-3', '/public-money/tax-dollars', '/glossary']},
    {'date': '2026-10-20', 'title': 'Tax dollars and the plain-English guide',
     'text': 'How your tax dollars are allocated: bill calculator, six years of rates and levies, and every government\'s budget. Plus a glossary and tap-to-explain terms across the site.',
     'pages': ['/public-money/tax-dollars', '/glossary', '/public-money/cra-spending']},
    {'date': '2026-10-20', 'title': 'CRA Spending launched',
     'text': 'Map and ledger of Bay County\'s six Community Redevelopment Agencies.',
     'pages': ['/public-money/cra-spending', '/about']},
]


# pages folded into others (2026-10-25): old entries link to where the content lives now
MOVED = {'/public-money/budget-explorer': '/compare', '/public-money/savings': '/governments', '/public-money/debt': '/compare',
         '/public-money/audits': '/governments', '/public-money/who-gets-paid': '/public-money/tourist-tax', '/public-money/map': '/public-money/sales-tax-projects',
         '/who-runs-bay-county': '/people', '/connections/money-map': '/connections'}
for _c in CHANGES:
    _c['pages'] = list(dict.fromkeys(MOVED.get(p, p) for p in _c['pages']))

LABELS = {'/people': 'People', '/': 'Home', '/my-address': 'My Address', '/public-money/tax-dollars': 'Tax Dollars', '/public-money/fees-and-bills': 'Fees & Bills',
          '/public-money/tourist-tax': 'Tourist Tax', '/public-money/amendment-3': 'Amendment 3', '/public-money/cra-spending': 'CRA Spending',
          '/public-money/sales-tax-projects': 'Sales Tax Projects', '/public-money/hurricane-michael': 'Hurricane Michael',
          '/public-money/contracts': 'Contracts', '/public-money/votes': 'How They Voted', '/public-money/debt': 'Debt',
          '/public-money/audits': 'Audit Findings', '/who-runs-bay-county': 'Officials', '/glossary': 'Glossary', '/search': 'Search',
          '/about': 'About', '/updates': "What's new", '/governments': 'Governments', '/compare': 'Compare', '/meetings': 'Meetings',
          '/connections': 'Connections', '/connections/campaign-gifts': 'Campaign Gifts', '/records-request': 'Records Request', '/open-data': 'Open Data', '/alerts': 'Email Alerts',
          '/es': 'En español', '/public-money/budget-explorer': 'Budget Explorer', '/public-money/who-gets-paid': 'Who Gets Paid', '/connections/money-map': 'Money Map', '/elections': '2026 Elections', '/elections/past': 'Past Elections', '/developers': 'API', '/public-money/exemptions': 'Exemptions'}


def last_updated(path):
    if path == '/updates':
        return CHANGES[0]['date']
    for c in CHANGES:
        if path in c['pages']:
            return c['date']
    return CHANGES[-1]['date']


def nice(d):
    return date.fromisoformat(d).strftime('%b %-d, %Y')


def coverage():
    """How far back each dataset reaches, read from the data so it stays accurate."""
    import json, os, re
    D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
    j = lambda *p: json.load(open(os.path.join(D, *p)))
    mon = lambda d: date.fromisoformat(d[:10]).strftime('%B %Y')
    rows = []
    try:
        from tax_page import build_data
        y = build_data()['years']; rows.append(('Property tax rates and levies', f'Tax years {y[0]}\u2013{y[-1]}', '/public-money/tax-dollars'))
    except Exception:
        pass
    fy = sorted({int(m.group(1)) for c in j('tourism', 'tourism_surtax.json')['bed_tax']['collections'] for m in [re.match(r'(\d{4})', str(c['fy']))] if m})
    part = [c for c in j('tourism', 'tourism_surtax.json')['bed_tax']['collections'] if c.get('partial') and str(c['fy']).startswith(str(fy[-1]))]
    rows.append(('Tourist (bed) tax collections', f'FY{fy[0]}\u2013FY{fy[-1]}' + (f" (FY{fy[-1]} through {part[0]['period'].split('through ')[-1].split(' (')[0]})" if part and 'through' in part[0].get('period', '') else ''), '/public-money/tourist-tax'))
    rows.append(('Hurricane Michael recovery money', 'October 2018 disaster declaration to date', '/public-money/hurricane-michael'))
    ds = sorted(c['date'] for c in j('contracts', 'contracts.json')['contracts'] if c.get('date'))
    rows.append(('Contracts and change orders', f'Since {mon(ds[0])}', '/public-money/contracts'))
    fa = sorted({m.group(0) for a in j('debt_audit', 'debt_audit.json')['audits'] for m in [re.match(r'FY\d{4}', a.get('fy') or '')] if m})
    rows.append(('Audit findings', f'{fa[0]}\u2013{fa[-1]} audits', '/governments'))
    vd = sorted(v['date'] for v in j('votes', 'votes.json')['votes'] if v.get('date'))
    rows.append(('Recorded votes', f'{mon(vd[0])} to {mon(vd[-1])}', '/public-money/votes'))
    rows.append(('Property values (My Address)', '2026 property roll, live from Bay County GIS', '/my-address'))
    return rows


def updates_page():
    launch = nice(CHANGES[-1]['date'])
    cov = ''.join(f'<tr><th scope="row"><a href="{u}">{html.escape(n)}</a></th><td>{html.escape(r)}</td></tr>' for n, r, u in coverage())
    items = ''.join(f'''<li data-d="{html.escape(c["date"])}" data-n="{html.escape(c["title"])}"><span class="tl-d">{nice(c["date"])}</span><span><b>{html.escape(c["title"])}.</b> {html.escape(c["text"])} {" · ".join(f'<a href="{p}">{LABELS.get(p, p)}</a>' for p in c["pages"])}</span></li>''' for c in CHANGES)
    return f'''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">What's new</span><h1>Updates</h1>
    <p class="lede">New pages, new data and corrections, newest first. Subscribe with any feed reader to get them as they happen: <a href="/updates.xml">RSS feed</a>.</p></div></header>
  <aside class="callout launch"><b>BayCounty.me launched on {launch}.</b> The first entries below are the initial pages going live. From here on, each new dataset, data refresh and correction gets its own dated entry.</aside>
  <section class="tx-sec"><div class="sec-hd"><h2 id="log">Change log</h2></div><ol class="timeline" data-tt-list aria-label="Change log">{items}</ol></section>
  <section class="tx-sec"><div class="sec-hd"><h2 id="covers">What the data covers</h2><span class="muted">The site is new; many of the records go back years</span></div>
    <div class="tablewrap"><table class="tx-table cov-table"><thead><tr><th scope="col">Records</th><th scope="col">Period covered</th></tr></thead><tbody>{cov}</tbody></table></div>
    <p class="note">Each page lists its own sources and the date its data was gathered. See <a href="/about">About</a> for how records are collected.</p></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">'''


def rss(domain):
    def item(c):
        dt = datetime.fromisoformat(c['date']).replace(hour=12, tzinfo=timezone.utc)
        link = domain + (c['pages'][0] if c['pages'] else '/updates')
        return f'''<item><title>{html.escape(c["title"])}</title><link>{link}</link><guid isPermaLink="false">{c["date"]}-{html.escape(c["title"])}</guid><pubDate>{format_datetime(dt)}</pubDate><description>{html.escape(c["text"])}</description></item>'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BayCounty.me updates</title><link>{domain}/updates</link><description>New pages, data and corrections on BayCounty.me</description><language>en-us</language>
{''.join(item(c) for c in CHANGES)}
</channel></rss>
'''
