# Bay County government salaries: county and constitutional officers

As of 2026-10-21. Current fiscal year is **FY2027** (Oct 1, 2026 to Sep 30, 2027). All records used are public under Florida Ch. 119.

## Files

| File | Employer | What's in it |
|---|---|---|
| `bocc.json` | Bay County Board of County Commissioners (all departments, including Fire Rescue/EMS, Emergency Management, 911, Animal Services, Mosquito Control, Public Works, Utilities, Parks, Library) | 462 title/department rows covering all 832 FY2027 authorized positions, with FY2027 and FY2026 FTE. The full BOCC pay plan (effective 1/1/2026) has 46 grade step tables (B80, B76, EX, BCO, FR). There are 57 FY2027 personnel-cost rows by cost center plus an all-BOCC total row and the Sheriff/Jail transfers. 8 leaders. |
| `sheriff.json` | Bay County Sheriff's Office | 12 posted entry rates (deputy, detention, dispatch, jail medical, civilian). Sheriff salary (statutory). Command staff names (salaries not published). BOCC funding transfers. |
| `clerk.json` | Clerk of Court & Comptroller | Clerk salary (statutory). BOCC Board Finance transfer. |
| `property_appraiser.json` | Property Appraiser | PA salary (statutory). BOCC payment. |
| `tax_collector.json` | Tax Collector | FY2027 and FY2026 DR-584 personnel detail (82 positions, salaries, OT, FRS, health). Official's salary. |
| `soe.json` | Supervisor of Elections | FY2025-26 approved personnel budget detail. Supervisor salary. Deputy names. |
| `airport.json` | Panama City-Bay County Airport & Industrial District (ECP) | FY2027 pay range for 48 titles (min/mid/max), plus 3 rate-only rows (Police Administrative Clerk and 2 ambiguous rate-sheet labels). FY2027 staffing (91 FTE). 94 unnamed per-position hourly rates converted to annual. Executive Director and Deputy salaries. |
| `port.json` | Panama City Port Authority | FY2025-26 personnel budget totals. ED name. (This is a City of Panama City agency.) |

`schools.json` and `README_salaries_schools.md` in this folder come from a separate task and are not covered here.

## Method

- **Pay plan (BOCC).** From the "BOCC Compensation Tables" PDF (DocumentCenter 19058, effective 1/1/2026, updated 1/26/2026), extracted with `pdftotext -layout`.
  - **B80 grades** are hourly; annual = hourly × 2,080.
  - **B76 grades** are 76 regular + 8 built-in overtime hours per pay period. The plan states 2,288 annual hours, so annual = hourly × 2,288.
  - **EX and BCO grades** are annual; hourly = annual ÷ 2,080, which we derived.
  - **FR grades (Emergency Services only)** are annual and the table gives no hours. Every FR step except FR-5 divides evenly by 2,990 hours (2,912 hours for a 56-hour week plus 78 hours of FLSA 7(k) overtime premium). We report that hourly figure as *derived*. FR-5's hourly is null.
  - **BSE-2 and BE-1** are min/max ranges only.
  - **Spot checks.** Several grade values were checked against current Workday job postings: B80-1, B80-3, B80-4 b, B80-6 and EX-12 all match to the cent. BCO-6 matches the March 2026 Chief of Emergency Services posting reported in the press.
- **Title → grade.** The county does not post a crosswalk from job title to grade. A title has `pay_min`/`pay_max` only when its grade is confirmed by a current job posting, a budget regrade note, or the executive-grade labels on the pay table. All other BOCC titles have null pay fields.
- **Authorized positions.** Taken from the "FY 2027 Position Count" table in the FY2027 Tentative Commissioner Book (09-15-26). `budgeted_fte` is the FY2027 column and `budgeted_fte_fy2026` is the FY2026 Approved column.
  - Parsed totals match the source exactly: 809 full-time + 23 part-time = 832, the same as the 09-23-26 final hearing presentation. FY2026 was 791 + 44 = 835.
  - Some FTEs are fractional because one position's cost is split across cost centers. For example, Fire Rescue staff are split 70/30 between Fire Services 0320 and EMS 0529.
  - Rows with 0 FTE in FY2027 (eliminated titles) are omitted, so the FY2026 FTE column does not add up to 835.
- **Actual salaries (BOCC).** These are the current salaries printed for incumbents in the FY27 Personnel Requests table. We used only rows funded 100% from one cost center, and we did not store names. Budgeted salaries for new or reclassified positions are in `notes`.
- **Department totals (BOCC).** From the FY2027 Final Budget Detailed Revenues & Expenditures, using personnel object codes by cost center:
  - **salaries:** 5101200
  - **overtime:** 5101400
  - **benefits:** FICA 5102100 + FRS 5102200 + life/health 5102300/5102302 + workers' comp 5102400

  We checked each row: salaries + overtime + benefits = the source's "PERSONNEL TOTAL" in every cost center. The BOCC-wide FY2027 personnel budget is about $92.5M. These are **budgeted** amounts, not actual spending.
- **Elected officials.** Salaries are the Ch. 145, F.S. amounts for Bay County, from the Florida EDR reports for FY2025-26 (Sept 22, 2025) and FY2026-27 (Sept 2026).
  - The `salary` field is FY2026-27. `salary_fy2025_26` is also included.
  - Officers who complete the state certification program can get up to $2,000/yr more ("special qualification salary"). That amount is not included. For example, the Tax Collector's own budget carries $200,466, which is the FY26 base of $198,466 + $2,000.
  - Officials' names come from each office's website.
- **Airport.**
  - **Pay ranges** are OCR'd with tesseract from the official scanned PDF. Every row passes two checks: max = 1.8 × min (1.2 × min for grade 100), and mid = (min+max)/2. The airport's HTML version has errors (grade 120 midpoint/max, ARFF Lieutenant max), so the PDF values are used.
  - **Per-position hourly rates** come from the FY2027 "Positions & Rates" sheet, × 2,080. Where the sheet's short labels were matched to pay-range titles, the notes say so. Two ambiguous labels, "Lieutenant" and "Maintenance Worker", are kept as separate rows.
  - **ARFF caveat.** ARFF works 24-hour shifts, so annualizing at 2,080 hours understates ARFF pay.
- **Privacy.** Only elected officials and top leaders are named: County Manager, Deputy County Manager, Chief Infrastructure Officer, the Sheriff's chief deputy and majors, SOE deputies, and the airport/port executive directors. All other rows are title / department / category / pay only.

## Caveats

- Job-posting rows (`sheriff.json`, some BOCC titles) are entry or posted rates, not actual pay.
- Department totals are FY2027 budget, except Port and SOE, which are FY2025-26. Constitutional officers' rows in `bocc.json` are BOCC *transfers*, not personnel detail.
- "Leaders" with `salary: null` are named, but their pay is not published online.
- No collective bargaining agreement was found online for the BOCC (fire/EMS or general) or the Sheriff. No BOCC union contract approval appears in 2025-26 agenda packets.

## Notable gaps (records to request)

1. **BOCC HR:** a classification list giving every job title its pay grade, plus a payroll/position roster as of 10/1/2026 (title, department, grade/step, annual rate).
2. **BOCC Fire Rescue:** which FR grade each rank is assigned to, and the paramedic/certification incentive schedule.
3. **Sheriff:** the FY2026-27 budget as submitted to the BOCC under s. 30.49 F.S. (positions by rank, personal services detail), and the BCSO pay plan for sworn, detention and civilian staff.
4. **Clerk:** the pay plan / position roster, and the CCOC court budget plus the Board Finance budget with personnel detail.
5. **Property Appraiser:** the FY2026-27 DR-484 budget with Schedule I salaries. The posted FY25-26 PDF is blocked by Cloudflare.
6. **Tax Collector:** a position roster with titles and rates. The DR-584 form summarizes all 81 non-elected positions in one line.
7. **SOE:** the FY2026-27 approved budget and a position roster.
8. **Port:** the FY2026-27 budget, a staff roster with salaries, and the 2026 Executive Director employment agreement.
9. **Not separate employers / not covered:** Mosquito Control is a BOCC division (cost center 0315 in `bocc.json`). We found no publicly funded pay data for the TDC/Visit PCB. Public Defender and State Attorney (14th Circuit) pay is not Bay-specific.
