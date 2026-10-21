# Campaign money and contracts

As of 2026-10-21. This folder covers who gave money to the most recent campaign of each current local elected official in Bay County, Florida, and which organizations that gave money also appear as vendors in this site's contract data. It reports only what the public filings show. A name appearing in both datasets is a fact about the records. It says nothing about why a contribution was made or how a contract was awarded.

## Files

- `campaign.json`: one record per officeholder. Each record has totals from the Supervisor of Elections (SOE) summary, a count and total for contributions from individuals, contributions from organizations listed item by item, and links to the source report and the itemized CSV export.
- `vendor_matches.json`: organization contributors whose names match vendors in `../contracts/contracts.json`. There is one row per contributor, candidate and contracting government.

## Coverage

48 officeholders, all with figures pulled from the Bay County SOE campaign finance system:

| Body | Officeholders covered | Election used |
|---|---|---|
| Bay County Commission | Raffield (D1), Carroll (D2), Crosby (D3), D. Moore (D4), Pease (D5) | 2024; Carroll 2026; Moore 2022 |
| School Board | Register (D1), Leonard (D2), C. Moore (D3), Chester (D4), Moss (D5) | 2024 / 2022 / 2026 |
| Constitutional officers | McQueen (Superintendent), Ford, Kinsaul, Sowell, Perdue, Ward | 2024 |
| Panama City | Branch, Hughes, Lucas, Grainger, Street | 2025 / 2023 municipal |
| Panama City Beach | Tettemer, Casto, E. Register, Coburn, Jarman | 2024 / 2022 municipal; Coburn 2026 |
| Lynn Haven | Lowery, Peebles, Perno, Warrick | 2026 recall election / 2023 / 2025 |
| Callaway | Henderson, Birdsell, Griggs, Pelletier, Ayers | 2024 / 2026 / 2022 |
| Springfield | Hammond, Griffis, Chval, Kennington, Hamre | 2026 / 2024 municipal |
| Parker | Kelly, Barrow, Chaple, Bodiford | 2025 / 2023 municipal |
| Mexico Beach | Wolff, Fosshage, Hamilton, Cox | 2025 / 2026 municipal |

Each official's most recent campaign for the seat they hold now was used. That includes 2026 races still in progress for incumbents (C. Moore, Coburn, Birdsell), whose figures run only through the latest report filed.

Not covered:
- Corey Langford (Lynn Haven) and Mark Rega (Parker): no campaign account was found under any 2022–2027 election in the SOE system. Both may have been appointed, but that was not verified.

## Method

1. The SOE page `https://www.bayvotesfl.gov/candidates/candidate-committee-finances/` embeds the VoterFocus campaign finance system: `https://www.voterfocus.com/ws/WScand/candidate_pr.php?c=Bay`. That system has per-election candidate lists for county, school board, special-district and municipal ("Municipal Super Tuesday") elections. All the offices in scope file locally with the SOE. The Florida Division of Elections handles only state and multi-county offices, so it was not needed for figures.
2. For each officeholder, the candidate list for the relevant election gave the campaign's summary totals: monetary contributions, in-kind contributions, and total expenditures and distributions. The candidate page is `report_url`.
3. The itemized CSV export for each campaign (`export_url`) was downloaded and parsed. Amendment codes were applied: a "D" line deletes a matching earlier item, and "A" lines are added. After that, the itemized sums matched the SOE summary totals for all 48 campaigns. The one exception is Ayers's expenditures, where the itemized lines are $100 higher; the SOE summary figure is used.
4. Contributor types follow the filer's code (I individual, B business, C/F/E committee, S self, O other). They were corrected only where the name plainly showed otherwise:
   - An "LLC" or "Inc" coded as an individual was changed to a business.
   - A personal name, personal trust or estate coded as a business was changed to an individual.
   - "Friends of ..." accounts were marked as candidate committees.
   - Realtors committees were marked as PACs.
5. Privacy: individual people are never named. Each candidate has only `from_individuals` (count and total). Organizations are listed by name, with city as filed. Street addresses and occupations are not stored. The candidate's own money appears as one aggregate line.
6. Vendor matching: names were normalized to lowercase, with punctuation and "&"/"and" removed and suffixes such as Inc/LLC/Co/Corp/PA dropped. They were compared with vendors in `contracts`, `change_orders`, `emergency_purchases` and the check-register `top_vendors` lists, and every candidate pair was reviewed by hand.
   - `exact`: the normalized names are identical.
   - `likely`: the filing truncates, abbreviates or misspells an otherwise identical name, for example "American Sand and Asphalt Pavi", "Marshall Bothers", "Mr Fence", "Southeastern Outdoor Mgmt" or "Dewberry".
   - Weak or fuzzy similarities were left out.

## Results

- 633 itemized organization/self lines across 48 campaigns. Individual contributions are aggregated only.
- Vendor matches:
  - 37 contributor–candidate pairs (29 exact, 8 likely), involving 19 distinct vendor organizations.
  - These expand to 92 rows, one per contracting government.
  - In 21 of the pairs, the contracting government is the same body the official serves on.
- The rows involve 11 officials:
  - County commissioners: Raffield, Crosby, Pease.
  - City officials: Branch, Hughes, E. Register, Warrick, Griggs.
  - Others: Ford, Kinsaul, Chester.
- Most matched vendors are road, utility, construction and engineering firms, for example Roberts and Roberts, Gulf Coast Utility Contractors, Marshall Brothers, C.W. Roberts, ECSC, Dewberry and Panhandle Engineering.

## Gaps and caveats

- `total_spent` is the SOE's "Total Expenditures & Distributions". For closed campaigns, Florida law requires surplus funds to be disposed of (returned, donated or moved to an office account), so this figure often equals the amount raised.
- Ethan Register's 2024 campaign reported pro-rata refunds to many contributors. These appear as negative amounts and as `refunded_by_campaign` in the matches.
- The contract data covers the Bay County BOCC and the seven cities from FY2023 to FY2026. It does not cover Bay District Schools or the constitutional officers' own purchasing. Lynn Haven warrant-list names are cut off at 15 characters in the source.
- Contributions from business owners or employees acting as individuals are not matched.
- Possible matches left out as unclear:
  - "Halls Contracting" (Ford) vs "Hall Contracting & Construction, Inc."
  - "ESCS LLC" (Ford) vs "ECSC, LLC"
  - "RJ Gorman Construction" (Ford), which could be either of two RJ Gorman entities
  - "Emerald Coast Civil Constructi" (Crosby) vs "Emerald Coast Site Construction"
- Left out of scope:
  - Mexico Beach Group 4 is marked not elected in `fees_pay_officials.json`.
  - Ginger Littleton, the incoming School Board D2 member, takes office in Nov 2026.
  - Both are noted in `campaign.json` `gaps`.
- `www.bayvotes.gov` could not be reached from the build environment because the proxy refused it. The SOE's current domain, `www.bayvotesfl.gov`, worked.
