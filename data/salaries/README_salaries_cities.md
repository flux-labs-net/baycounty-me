# Bay County city salaries: the seven municipalities

As of 2026-10-21. These are public records under Florida Ch. 119. City fiscal years run Oct 1 to Sep 30, so FY2027 began Oct 1, 2026.

## Files

| File | Employer | Fiscal year used | What's in it |
|---|---|---|---|
| `pc.json` | City of Panama City | FY2026 positions; FY2026 and FY2027 department costs | 301 position rows: every title in the FY2026 personnel schedules (645 funded FTE), plus current job-posting rates. 89 department personnel-cost rows (FY2026 adopted, FY2027 adopted). 19 leaders. |
| `pcb.json` | City of Panama City Beach | FY2026 budget; pay ranges current | 183 classification specs with pay grade and min/max (the city's GovernmentJobs class-spec list), plus current postings. Org-chart counts for police, dispatch, fire, Beach Safety and code. Staffing table (473 FT). 13 department personnel-cost rows (FY2026). 7 leaders. |
| `lh.json` | City of Lynn Haven | FY2027 (adopted 9/22/2026) | 129 title rows with class codes and FY2027 FTE (190.4; the FY2026 count is in notes). 23 department personnel-cost rows (FY2027). Current posting pay. Budgeted salary for single-position departments. 6 leaders. |
| `cw.json` | City of Callaway | FY2027 (Res. 26-13) | Personnel Budget Detail by department (99 FTE; current wages, proposed wages, total employee cost). City Manager salary and allowances. 7 leaders. Police is a Sheriff contract. |
| `sp.json` | City of Springfield | FY2026 | Department appropriations only (Res. 25-15). 9 leaders, with no salaries. Little salary data is published. |
| `parker.json` | City of Parker | FY2026 line items (draft); FY2027 department totals | Salary, overtime and benefit lines by department (FY2025-26 requested). FY2027 adopted department totals. 2 job postings with pay. 7 leaders. |
| `mb.json` | City of Mexico Beach | FY2027 (budget posted Oct 2026) | Department salary, overtime and benefit lines, with each position's percentage allocation. Mayor and council pay. 7 leaders. Police is a Sheriff contract. |

## Schema notes

- The schema follows the county files. `source` on a position, leader or department-total row is a **URL**, not an index into `sources`.
- `department_totals` rows carry a `fiscal_year` field, because some cities have both FY2026 and FY2027 rows. Some rows add fields the source reports separately: `personal_services_total`, `other_pay`, `incentive_and_allowances`, `vehicle_allowance`, `department_total_appropriation`, `total_employee_cost` and `positions_charged`.
- **Annual pay from an hourly rate** is computed at 2,080 hours. The exception is 24-hour-shift fire suppression titles at Panama City Beach, where the annual figure is left null; the current PCB firefighter posting annualizes at about 2,756 hours.
- **`actual_salaries`** is filled only where a budget line can belong to just one position. That happens when a department has exactly one budgeted FTE, as with the Lynn Haven Planning Director, HR Coordinator and Code Enforcement Officer, the Callaway City Manager and HR position, and the Mexico Beach Code Officer. It is also filled where the budget states the amount outright (Mexico Beach mayor and council).
- **Privacy.** Names appear only in `leaders`, and only for elected officials and top leaders: city manager or administrator, assistant manager, clerk, attorney, directors, and police and fire chiefs. Position rows have no names.

## How it was built, and checks

- **Panama City.** The FY2026 Adopted Budget Report was parsed with `pdftotext -layout`. Every department's title rows sum to the printed Grand Total, and fund totals sum to 645 funded FTE. The book omits the 23-FTE Residential Trash schedule, so that is one row. FY2027 personnel costs come from the 9/17/2026 Updated Budget Report, which was adopted 9/22/2026.
- **Panama City Beach.**
  - pcbfl.gov blocks scripts, and later blocked this session's IP (HTTP 403), so the FY2026 budget book was read through a web-fetch tool. Each department's personnel lines were re-added and equal its printed TOTAL PERSONNEL. For example, Law Enforcement comes to $12,596,350, Fire/EMS to $7,979,100 and Beach Safety to $1,682,800.
  - Pay ranges come from the city's class-spec listing on GovernmentJobs. One spec, Communications Director, shows an impossible range ($171 million and up) and was nulled.
- **Lynn Haven.** The FY2027 approved budget was parsed. Position sums equal the printed totals (190.4 FTE, and 219.5 for FY2026). Department salary lines were checked against TOTAL PERSONNEL SERVICES, which matched to within $1 of rounding.
- **Callaway.** The scanned Personnel Budget Detail was read from page images. Columns sum to the printed General Fund totals; the citywide total differs by $1 of rounding in the source. Cross-checked against the OCR of the account-detail pages.
- **Parker.**
  - FY2026 values are the draft line-item budget's requested column. The police benefit lines re-add exactly to the parsed total ($355,838).
  - FY2027 department totals were read from the scanned Res. 2026-416 page image. They sum to $5,528,051, but the source prints $5,528,053.
- **Mexico Beach.** The scanned FY26-27 budget was read from page images, one department sheet at a time. For Fire, salaries plus volunteer pay plus overtime plus benefits equals total personnel within $1.

## Emergency services coverage

| City | Police | Fire | Dispatch | Beach safety | Code |
|---|---|---|---|---|---|
| Panama City | 155 funded FTE by title (e.g., 46 Police Officer I, 22 PO II, 12 Sergeants, 6 Lieutenants, 4 Captains). Starting pay for Police Officer I is $51,958.40 (posting). FY26 PS $15.2M; FY27 regular salaries $9.18M, OT $660K | 82 FTE by title (33 Firefighters, 18 Fire Engineers, 13 Shift Lieutenants, 5 Station Captains, 3 Battalion Chiefs). FY27 regular salaries $6.23M, OT $430K | 12 Telecommunicators plus supervisors and trainers | none | 5 Code Compliance Inspectors + 1 Senior |
| Panama City Beach | 111 FT. Ranges: Officer $27.52-$35.08/hr; Sergeant $32.10-$40.93; Lieutenant $38.24-$48.75; Captain $89,364-$113,940; Chief $121,758-$158,285. FY26 PS $12.6M | 88 FT incl. Beach Safety. Firefighter $48,580-$70,442; FF/EMT and FF/Paramedic $53,560-$77,662 + incentive; Fire Chief $129,800-$168,740. FY26 Fire/EMS PS $7.98M | 14 Communications Officers, $23.10-$29.46/hr | 17 Beach Rescue Responders at $22.76-$29.02/hr; FY26 PS $1.68M | 5 officers, $21.80-$31.22/hr |
| Lynn Haven | 39 FTE in FY27 (down from 48). Officer posting $51,500.03. Sworn salaries $1.93M | 28 FTE (9 FF/EMT, 6 Driver-Operators, 6 Lt/EMT, 3 BCs). Firefighter salaries $1.55M | 5 Communication Officers + manager | none | 1 officer, $47,943 budgeted |
| Callaway | Sheriff contract, $2.93M | 20 FTE; regular salaries $1.28M; OT $159K | via Sheriff | none | 3 FTE, $177,731 |
| Springfield | Dept total $3.80M (FY26) | Dept total $2.15M (FY26) | none found | none | Dept total $268,900 |
| Parker | Regular salaries $514,088 (FY26 requested); FY27 dept $1.31M | Regular salaries $213,784; FY27 dept $591,692 | none found | none | Regular salaries $55,199 |
| Mexico Beach | Sheriff contract, $1.37M | Fire Chief + 9 firefighters; salaries $485,555 | via Sheriff | none | 1 officer, $54,621 |

## Leaders with a published salary

- **Callaway City Manager Ed Cook:** $163,225 (FY2027), plus a $6,000 auto allowance, $600 phone allowance and $590 bonus.
- **Panama City City Manager Jonathan Hayes:** $175,000 base under the January 2024 contract, plus the COLAs given since.
- **Panama City City Clerk-Treasurer Leslie Glaze:** $145,000 in a proposed contract on the September 8, 2026 agenda; approval is not confirmed.
- **Panama City Beach City Manager Drew Whitman:** $150,000 base under his 2021 contract. The current class-spec range for the job is $140,000 to $180,000.
- **Mexico Beach mayor and council:** the Mayor gets $13,200 and each council member $8,400.

Combined elected-body pay lines:

| City | Combined line |
|---|---|
| Panama City | City Commission regular salaries $204,217 (FY2026) and $187,653 (FY2027). This includes a half-time assistant. |
| Panama City Beach | $125,000 |
| Lynn Haven | $86,060 |
| Callaway | $50,000 |
| Parker | $26,400 |

## Reconciliation with `data/fees/fees_pay_officials.json`

- **Callaway City Manager ($163,225) and Parker stipends ($26,400):** these match.
- **Panama City Beach City Manager ($150,000, 2021):** this matches. A class-spec range is added.
- **Lynn Haven:** the fees file has $86,560 from the FY2025-26 approved book. The amended FY2026 budget and FY2027 both carry $86,060. These are different budget versions, not a conflict.
- **Panama City City Manager:** the fees file says only that Hayes asked for a $175,000 minimum. The contract presented January 9, 2024 sets a $175,000 base salary, so the salary is now sourced.
- **Panama City City Clerk-Treasurer:** Janette Smith (named in the FY2026 book) left August 10, 2026. Brandy Waldron is interim, and Leslie Glaze's contract was proposed September 8, 2026.
- **Parker City Clerk:** the September 2026 agenda names Rachelle Stanley, as the fees file does. `data/civic/records.json` lists Ingrid Bundy, so that file needs an update.

## Not online (records to request)

Each city file's `gaps` array has the exact requests. The main ones:

1. **Pay plans and step tables.** None of the seven cities posts its classification and pay plan. Panama City Beach comes closest, with min/max ranges on its class specs. Request each city's current pay plan, and the police and fire step or rank tables.
2. **Union contracts.** No collective bargaining agreement was found for any city.
   - Panama City Beach firefighters unionized in December 2023 (Professional Firefighters Association Local 5147).
   - Lynn Haven firefighters petitioned for a bargaining unit in 2024-25.
   - Request the CBAs or PERC certifications.
3. **Chief and director salaries.** Police chiefs', fire chiefs' and directors' salaries are unpublished in every city. Request FY2027 budgeted salary by position, without names.
4. **Specific documents not downloaded:**
   - PCB insurance-bid census with salaries (PCB26-46 Exhibit 2), PCB pay plan Res. 23-208 and the PCB clerk contract Res. 26-170. These were blocked or scanned.
   - Springfield FY2027 budget Res. 26-12, which was unavailable during a CivicPlus outage on 2026-10-21.
   - The Lynn Haven City Manager contract.
   - Parker's and Springfield's position lists.

## Scripts

Builders and parsers are in the session scratchpad (`salaries/cities/`): `parse_pc*.py`, `parse_lh*.py`, `parse_parker.py`, `build_<city>.py` and `common.py`, which holds the category rules.
