# data/money: who gets paid, and what is borrowed

As of 2026-10-21. Built from public, official sources only. Every amount comes from a source document; nothing is estimated.

## payments.json: vendor payments (check registers)

**What was found.** The only public vendor-payment registers not already on the site are for the three tourist-development-tax agencies. Each monthly "Check Register - Sorted by Dollar Amount" from the Bay County Clerk of Court & Comptroller (attached to BOCC agendas on baycountyfl.primegov.com) has a section for each of them through October 2025. The earlier contracts work counted only the BOCC sections and skipped these.

| gov id | Agency | Months | Payments parsed | Parsed total | Vendors (listed) |
|---|---|---|---|---|---|
| visit_pcb_cvb | Panama City Beach CVB (Visit Panama City Beach), Bay County TDC | 19 | 2,687 | $32,330,519.83 | 557 (top 200) |
| destination_panama_city_cdc | Panama City Community Development Council (Destination Panama City) | 19 | 647 | $2,859,059.51 | 151 |
| mexico_beach_cdc | Mexico Beach Community Development Council | 19 | 443 | $1,341,195.94 | 57 |

- **Months covered:** Jan and Apr-Sep 2024 (FY2024); Oct 2024-Jan 2025 and Mar-Sep 2025 (FY2025); Oct 2025 (FY2026).
- **Accuracy:** the registers are scanned pages. Every row was read with OCR and checked against the printed section total. 54 of 57 agency-months match to the cent. The other three: one has a printed total that OCR misread (rows match the corrected figure), and two are off by $50 and $1,000. Five misread amounts were corrected using the register's dollar order, and only where the correction made the month match its printed total. Each month's reconciliation is in the file.
- **Excluded:** payments to individual people, counted only in `excluded_individuals`. CVB: 179 payments, $397,609.
- **Kept but labeled in `category`:** payroll processors, benefit and tax remittances, credit-card bill payments, unnamed bank transfers, and other governments.
- **November 2024:** the Clerk's register has the CVB and Panama City CDC headings swapped. Rows were assigned to the right agency by check-number series and vendor.
- **Context:** in January 2026 the Clerk posted an action plan for the CVB after what it calls a discovery of fraud, with a criminal investigation and forensic audit described as ongoing. The data records payments only and makes no finding about any of them.

**Gaps (see `gaps` in the file):**

- **Panama City, Panama City Beach, Callaway, Parker, Springfield, Mexico Beach and Bay District Schools:** no check register, warrant list or vendor-payment report is posted on agenda sites, finance pages or transparency portals. pcbfl.gov and bay.k12.fl.us block scripted access, so their searches were partly manual.
- **Visit PCB board packets:** no register, only individual invoice approvals.
- **After October 2025:** CVB and CDC payments are not public. The Clerk's registers from November 2025 cover BOCC only.
- **Missing months for all three agencies:** Oct-Dec 2023, Feb-Mar 2024 and Feb 2025.

Bay County BOCC FY2024-26 and Lynn Haven FY2023-25 registers are already in `data/contracts/contracts.json` and are not repeated here.

## bonds.json: bonds, notes, COPs and loans

There are 61 issues, starting from the audit-based list in `data/debt_audit/debt_audit.json`:

| Type | Count |
|---|---|
| Bonds | 16 |
| Notes | 18 |
| Certificates of participation | 4 |
| Loans (SRF/SIB/bank) | 23 |

They cover the BOCC, Bay District Schools, all seven cities, the airport district and the Port Authority. Two Bay County items from the FY2024 ACFR were added: the Water Tank Purchase Note 2023 and the CIR Bonds 2011.

**What was added to the audit list:**

- **Issue dates** for 25 issues: from the Bay County FY2024 ACFR, the Panama City Beach FY2025 audit and CRA reports, Callaway's audit, and the school board's FY2022 audit and December 2019 board book.
- **Par amounts** for 46 issues, including School COP 2022A ($64,810,000, issued 2022-09-01).
- **Panama City's $150M Series 2023 note** (Truist): terms, purpose and a final maturity no later than 2026-09-01, from the 2023-08-08 commission packet. That date has passed, and repayment or refinancing is not confirmed.
- **Placement type** (public offering or bank/direct placement).
- **Ratings** where an official document states them. Only Panama City Beach's are stated: S&P "A" on the 2020 Front Beach Road bonds, plus Utility System ratings.
- **Status:** issues whose final maturity has passed since the audit are flagged as likely retired (4).

**Not done:**

- **EMMA:** the public search endpoint answered, and issuer pages are listed for 4 publicly offered issues. EMMA's Terms of Use prohibit scraping and robots, so official statements, CUSIPs and current ratings were not pulled. `official_statement_url` is empty for every issue; these need to be attached by hand.
- **Issuers' own websites:** none was found to post official statements.
- **Florida Division of Bond Finance:** its new filing system (bondissue.sbafla.com) needs a login.
- **CDD and conduit bonds** are out of scope.

## Files and method

- `payments.json`, `bonds.json`, `README_money.md`
- Build scripts are in the session scratchpad and are not committed: `plan.py` (finds section pages by header OCR), `parse_tdc.py` (row parsing and reconciliation), `build_payments.py` (vendor merge and classification), `final_payments.py`, `build_bonds.py`.
