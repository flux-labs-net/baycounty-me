# 2026 local campaign finance

As of 2026-10-21. `finance_2026.json` has campaign finance figures for every local candidate who opened a campaign account with the Bay County Supervisor of Elections (SOE) for a 2026 election. It reports what the filings show. It does not judge any candidate or contributor.

## Coverage

36 candidates, from three SOE reporting groups:

| Reporting group | Candidates | Offices |
|---|---|---|
| 2026 Primary/General Election (el=35; Aug 18 primary, Nov 3 general) | 29 | County Commission D2 and D4; County Judge Groups 1 and 4; School Board D2, D3 and D5; Callaway Commission Wards 1 and 2; Panama City Beach Council Wards 1 and 3; Lake Powell CDD Seats 2 and 5 |
| 2026 Municipal Super Tuesday (el=36; Apr 21, 2026) | 6 | Mexico Beach Council Groups 4 and 5; Springfield Mayor; Springfield Commission Wards 3 and 4 |
| Lynn Haven Recall (el=34; Jan 20, 2026) | 1 | Lynn Haven Mayor (candidate account only) |

All filed candidates are included, with the status the SOE shows: Qualified (on the Nov 3 ballot), Advanced (to the Nov 3 runoff), Elected (in April, at the Aug 18 primary, or unopposed), Defeated, Withdrawn, or Did not qualify. State and federal offices are left out, because they file with the Florida Division of Elections. The SOE system lists no 2026 races for Panama City, Parker, Lynn Haven (other than the recall), or the county constitutional offices.

Totals for all 36 candidates:

- Raised: $379,891.34. That is $370,837.66 monetary, which includes candidate loans, and $9,053.68 in-kind.
- Spent: $298,537.76 in expenditures and distributions.
- Raised by contributor type:
  - Individuals: $163,499.10, from 597 contributions.
  - Businesses: $92,300.38.
  - PACs and committees: $5,500.00.
  - Candidates' own money and loans: $118,241.13.
  - Other: $350.73 (non-business organizations and bank interest).

## Method

1. Fetched the candidate list for each reporting group from `https://www.voterfocus.com/CampaignFinance/candidate_pr.php?c=bay&el={34,35,36}`. This is the system embedded on `https://www.bayvotesfl.gov/candidates/candidate-committee-finances/`. Took the SOE summary totals (monetary, in-kind, expenditures and distributions) and status from each list.
2. Fetched each candidate page (`report_url`) and parsed its table of reports: report code, period, amended flag, and per-report totals. The per-report rows add up to the list totals for every candidate. `latest_report` and `through` come from the report with the latest period end.
3. Downloaded each itemized CSV (`export_url`) and applied the amendment codes. Each "D" line removes one earlier item with the same name and amount, preferring the same date. It is applied after all items are loaded, because the export does not always list a deletion after the item it deletes. "A" lines are kept as additions.
4. Reconciled the itemized sums to the SOE summary:
   - Monetary: all contribution items except in-kind, including loans, interest and negative refunds.
   - In-kind: IK items.
   - Expenditures: all E items, including refunds to contributors, distributions and reimbursements.
5. Classified contributors by the filer's code (I individual, B business, C/F/E committee, S self, O other). A code was changed only when it was plainly wrong:
   - An LLC or Inc coded as an individual became a business.
   - A personal name coded as a business became an individual. These were Dougles B Dykes, Craig E Dye, Christopher B Forehand, Jorge L Gonzalez and Karen Bailey. A personal living trust was also treated as an individual.
   - The candidate's own money filed under a name variant or the code I was recognized as self, using name variants and the same filed address. Examples: "Robert C Curti" for Carl Curti, "Fred G Manley", "Carlos Mario Sanchez", "Scott Heillmann", "Nicholas A Atkinson", "James Kirkland" and "David L. Lowery".
   - Same-surname relatives at other addresses stayed individuals.
   - A church and a charitable group were coded as other.
   - "Press Print Graphics", coded S, was coded as a business.
   - "Friends of ..." accounts were coded as candidate committees, and counted under `pac` in `by_type_total`.
6. Privacy follows the policy in `data/campaign`. Individual contributors are never named. Each candidate's `from_individuals` holds:
   - The count and net total.
   - Amount bands, counted per contribution: under $100, $100–$499, $500–$999, and $1,000 or more.
   - In-county, out-of-county and unknown location, from the city and ZIP filed. Bay County cities and ZIPs count as in-county; a contribution filed with no address is unknown.
   - An approximate count of unique donors.

   Organizations and the candidate's own money and loans are listed item by item, with the city as filed. Street addresses and occupations are never stored.
7. Expenditures: payee name variants are merged, for example the many spellings of the Supervisor of Elections, Gagnon's Sign Depot and Neves Media. Payees who are individual people were identified by name and combined into "Payments to individuals" or "Refunds to individual contributors". Payments to the candidate, such as loan repayments, reimbursements and returned surplus, are shown as one line. Each candidate keeps up to the 15 largest payees, with the filed purposes.

## Reconciliation

- 29 campaigns with activity: itemized monetary, in-kind and expenditure sums match the SOE summary exactly, after amendments.
- 7 campaigns had no activity: an empty export and all-zero totals. These are the 5 Lake Powell CDD candidates, McDowell and Reid.
- Dr. John L. Haley: the P7 amended report has a deletion line with every field blank, which could not be matched to an earlier item. The SOE totals, which the itemized sums match, therefore include both the original $1,000 loan of 8/12/2026 (coded I) and its amended re-filing (coded S). The loan may be double-counted by $1,000. The site uses the SOE figure and records this in the candidate's notes.

## Caveats

- Active campaigns are reported through G4 (period ending 2026-10-02), or G5 (period ending 2026-10-16) for Birdsell and Overway. Other G5 reports had not been posted by 2026-10-21, and later reports are still to come. Re-run before the election and after the final reports.
- `total_raised` is the SOE monetary total plus in-kind. Candidate loans are included in monetary, as the SOE reports them.
- `cash_on_hand_estimate` is monetary minus expenditures, for open campaigns only. It ignores outstanding loans and timing. Closed campaigns, those with a termination report, are null.
- For closed campaigns, `total_spent` includes refunds to contributors and other disposal of surplus. For example, most of Scott Duvall's contributions were refunded after his termination report.
- Payees have no type code in the filings, so the person-or-organization decision for payees was made by hand from the names.
- `election` names the SOE reporting group. Callaway and Panama City Beach races are filed under the 2026 Primary/General group.
- The two Lynn Haven recall political committees are committees, not candidates, so they are left out.

Working scripts and raw downloads are kept outside the repo in the build scratchpad and are not committed.
