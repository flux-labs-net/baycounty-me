# data/money: who gets paid, and what is borrowed

As of 2026-10-21. Built from public, official sources only. Every amount comes from a source document; nothing is estimated.

## payments.json: vendor payments (check registers)

**What was found.** The only public vendor-payment registers not already on the site are for the three tourist-development-tax agencies. Each monthly "Check Register - Sorted by Dollar Amount" from the Bay County Clerk of Court & Comptroller has a section for each of them.

**Refreshed 2026-10-21.** The Clerk's OnBase public records search ("BOCC - Check Registry Search", https://bayforms.baycoclerk.com/PublicAccess/PublicRecordSearch/, queried through its JSON API) holds text-PDF copies of the registers, including months that were never attached to BOCC agendas and the months after October 2025, which do still include the three agency sections. All months were re-parsed from these text PDFs, so no OCR was needed except December 2024 (missing from OnBase; read by OCR from the Feb 4, 2025 agenda scan).

| gov id | Agency | Months | Payments | Total | Payees |
|---|---|---|---|---|---|
| visit_pcb_cvb | Panama City Beach CVB (Visit Panama City Beach), Bay County TDC | 31 | 4,309 | $53,971,860.73 | 654 (top 200 listed) |
| destination_panama_city_cdc | Panama City Community Development Council (Destination Panama City) | 31 | 1,020 | $4,554,616.57 | 174 |
| mexico_beach_cdc | Mexico Beach Community Development Council | 31 | 799 | $2,192,655.60 | 72 |

- **Months covered:** every month Oct 2023 – Nov 2025 (FY2024 and FY2025 complete), plus Mar – Jul 2026.
- **Accuracy:** all 93 agency-months match the printed section total to the cent. No amounts were corrected. The earlier OCR-based figures had small misreads (e.g. CDC July and Oct 2024); those are now fixed by the text copies.
- **Excluded:** payments to individual people, counted only in `excluded_individuals` (CVB 414 payments, $971,244.62). Individuals were picked out by name pattern; check before quoting.
- **Kept but labeled in `category`:** payroll processors, benefit and tax remittances, credit-card bill payments, unnamed bank transfers, and other governments.
- **November 2024:** the register has the CVB and Panama City CDC headings swapped; rows are assigned by content.
- **Context:** in January 2026 the Clerk posted an action plan for the CVB after what it calls a discovery of fraud, with a criminal investigation and forensic audit described as ongoing. The data records payments only and makes no finding about any of them.

**Gaps (see `gaps` in the file):**

- **Still missing:** Dec 2025 – Feb 2026 (not listed in OnBase; the agenda scan for those months has BOCC payments only) and Aug – Sep 2026 (not posted yet).
- **Panama City, Panama City Beach, Callaway, Parker, Springfield, Mexico Beach and Bay District Schools:** no check register, warrant list or vendor-payment report is posted.
- **Visit PCB board packets:** no register, only individual invoice approvals.
- **Site text:** `site/money_pages.py` still says "Registers through October 2025" and describes the registers as scans read by OCR; it needs a small wording update (not done here: site code is outside this data stream).

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
- Build scripts are in the session scratchpad and are not committed. The 2026-10-21 refresh used `parse_cr.py` (text-PDF row parsing and reconciliation), `rebuild_pay.py` (vendor merge, individual exclusion, categories) and `finalize_pay.py`.
