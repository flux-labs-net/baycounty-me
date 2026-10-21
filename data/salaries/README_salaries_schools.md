# Bay District Schools: salary data (`schools.json`)

**Employer:** Bay District Schools (The School Board of Bay County, Florida)
**Compiled:** 2026-10-21
**Pay year:** 2025-26 negotiated rates. The Board-approved 2026-27 Salary Placement Schedule (June 23, 2026) carries these rates forward unchanged. Elected-official salaries and budget totals are for FY2026-27.

## What's in the file

| Key | Contents |
|---|---|
| `positions` | 249 job classifications. Each has a pay grade, a min, mid and max, the pay basis (annual or hourly), contract days, the union, and a `budgeted_fte` count where the 2026-27 org chart gives one. |
| `steps` | Full grids for each schedule: teacher Performance Pay steps 0-25 (BA, MA, Specialist, Doctorate), the grandfathered teacher schedule, Support Schedule 3, Non-Bargaining NB206-NB231, Confidential Schedule 4, Licensed Schedule 5 (steps 0-25) and Safety & Security Schedule 6. |
| `supplements` | 74 items. Coaching and extra-duty supplements are figured as a percentage of the $50,500 BA step-0 salary. Also included: advanced-degree, high-risk school, turnaround, police rank and education incentive, therapist and interpreter, ESP, and bargaining-team supplements. |
| `leaders` | The Superintendent, the five School Board members, the four deputy superintendents and the Executive Director of HR. Only elected officials and district leaders at director level or above are named. |
| `department_totals` | FY2026-27 General Fund salaries and benefits by function from the Final Budget, plus the Food Service fund. |
| `union_contracts` | ABCE and BESPA terms for 2024-25 and 2025-26, and the status of 2026-27. |
| `stats` | Headline figures (see below). |
| `gaps` | Known limitations. |

## Headline figures

- **Starting teacher salary:** $50,500 (BA, pay grade 0-3). This is the Performance Pay schedule, effective 7/30/2025 and implemented 12/15/2025. The BA maximum is $59,300 at pay grade 25. Degree supplements add $2,500 (Master's), $5,100 (Specialist) or $7,800 (Doctorate).
- **2025-26 ABCE deal:** a $500 raise, and starting pay went from $50,000 to $50,500. The tentative agreement was reached in October 2025 and approved by the Board the week of Oct. 27, 2025, as reported by WJHG and WMBB.
- **2025-26 BESPA deal:** every support job was reclassified using the Evergreen compensation study onto a new 10-grade hourly schedule of $15.00-$22.50, with credit for up to 25 years of service. Employees who don't gain from re-placement get $250. It is effective 7/1/2025 and was implemented 1/26/2026.
- **Average teacher salary:** $52,167. This is FLDOE data shown in the Florida Education Association's chart, for the data year labeled 2024 (probably 2024-25). It covers 1,878 teachers and ranks 43rd of 76 districts; the state average in that chart was $54,875.
- **Superintendent Mark McQueen:** $199,754 in FY2026-27 under the elected-superintendent formula in s. 1001.47 F.S. ($198,466 in FY2025-26).
- **School Board members:** $47,321 each in FY2026-27 under s. 1001.395 F.S. ($46,970 in FY2025-26).
- **Administrators:** they are paid hourly on the Non-Bargaining schedule, and the annual figures here are estimates (hourly rate × 8 hours × 247 paid days on the FY2026-27 12-month administrative calendar).

| Role | Grade | Estimated annual pay |
|---|---|---|
| Deputy superintendent | NB230 | about $111.5k-$117.5k |
| Executive director | NB227 | about $96.3k-$102.3k |
| High school principal | NB226 | about $91.7k-$97.7k |
| Elementary principal | NB223 | about $79.3k-$85.2k |

- **District police officer:** $21.0184/hour on a 184-day calendar, about $30.9k base before supplements. The org chart shows 23 full-time and 3 part-time officers, plus a chief (NB222).
- **General Fund payroll (FY2026-27 budget):** $144.65M in salaries and $54.99M in benefits.

## Sources

- [Salary Placement Schedule 2026-2027](https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/5786/Bds/3b14ebee-2a6e-4fec-ad9b-6eff9a3f50bc/Salary-Placement-Schedule-2026-2027-apprv-062326.pdf) (75 pages, Board approved 6/23/2026). This is the main source. The grids were parsed directly from the PDF text layer, and the payroll-calendar pages were read with OCR.
- [Organizational Chart 2026-27](https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/5786/Bds/ba86225d-a249-4236-8ebe-e583674d044a/BDS-Organizational-Chart-26-27-appv-052626-rev-062326.pdf), the source of the position counts. Counts where the text layout was ambiguous were checked against page images.
- [Final Budget FY 2026-2027](https://files-backend.assets.thrillshare.com/documents/asset/uploaded_file/5786/Bds/a789a2df-7a40-493f-a70a-02a7777eb566/Final-Budget-FY-2026-2027.pdf)
- Florida EDR salary reports for elected officials: [FY 2026-27](https://www.edr.state.fl.us/Content/local-government/reports/finsal26.pdf) and [FY 2025-26](https://www.edr.state.fl.us/Content/local-government/reports/FY%202025-26%20Salaries.pdf)
- [BDS Union Negotiations page](https://www.bay.k12.fl.us/o/bds/page/union-negotiations): 2025 ABCE and BESPA proposals. These are scanned PDFs and were read with OCR.
- [FEA chart dataset of FLDOE average teacher salary](https://datawrapper.dwcdn.net/jrjmy/8/dataset.csv)
- News coverage: WMBB (Oct. 15-16 and Nov. 6, 2025) and WJHG (Oct. 30, 2025 and Nov. 12, 2024)

## Gaps and caveats

- **BoardDocs** returns HTTP 403 to automated access. Exact ratification dates and the ratified master contracts could not be retrieved.
- **No individual salaries.** The file holds schedule ranges only. Deputy superintendents and executive directors are shown by pay grade range.
- **FLDOE 2025-26 files** (teacher salary data, district staff salaries, staff counts) return 403. Average administrator salaries and FLDOE staff counts by category are therefore missing.
- **Support (ESP) positions** are hourly, and hours vary by position, so no annual figure is computed for most of them.
- **Food service** workers are employed by Chartwells K12, not the district.
- **BCSO school resource deputies** and **charter schools** are excluded.
- **No 2026-27 raise** had been found as of 2026-10-21.

## Privacy

Names appear only for elected officials and for district leaders at director level or above. Principals and all other staff appear by title, category and pay only.

## Rebuild

The build script is `build_schools.py`. It and the downloaded source documents live in the session scratchpad, not in this repository.
