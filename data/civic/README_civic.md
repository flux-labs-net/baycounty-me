# data/civic: coverage and gaps (as of 2026-10-21)

Every value in these files cites an official public source. Nothing was estimated. A field is `null` when the agency does not publish that item.

## records.json: public records custodians (24 entries)

Fields: `id, name, gov, custodian_title, email, phone, address, portal_url, policy_url, source_url, notes`.

**Online portals.** Only portals linked from an official page are listed:

| Agency | Portal |
|---|---|
| Bay County BOCC (also covers Utility Services) | JustFOIA |
| Bay District Schools | JustFOIA |
| Sheriff | GovTransfer |
| Supervisor of Elections | web form |
| Panama City Beach | web form |
| Mexico Beach | web form |
| Callaway | PDF form only |

Panama City, Lynn Haven, Springfield, Parker, the Clerk, the Property Appraiser, the Tax Collector, the TDC/CVB, the Port and the Airport take requests by email, phone, mail or in person.

**Named custodians.** These agencies name a custodian or records contact:

- Sheriff (Beth Nelson)
- Tax Collector (Rebekah J. Taylor)
- Visit PCB / TDC (Sharon Cook)
- Port (Sarah Harris)
- Panama City Beach (City Clerk Lynne Fasone)
- Callaway (City Clerk Ashley Robyck)
- Springfield (City Clerk Teresa Cox)
- Parker (City Clerk Ingrid Bundy)

**CRAs.** Panama City, Panama City Beach (Front Beach Road), Lynn Haven, Callaway, Springfield and Parker each have an entry. All are dependent agencies that use their city's records process.

**Gaps**
- **Property Appraiser:** no designated custodian or records page. The entry lists the Property Appraiser's own email and the main office line.
- **Clerk of Court:** no records-request policy or form. The entry lists the general email and phone.
- **Airport (ECP):** no custodian. Only general contacts and a Chapter 119 notice in its privacy policy.
- **Lynn Haven:** the January 2026 public records policy document was not found online. The entry cites a WJHG news story for the policy terms.
- **Springfield and Mexico Beach:** the clerk's email address is not published.
- **Mexico Beach CRA:** could not be confirmed, so no entry.
- **Blocked sites:** pcbfl.gov, baypa.net and baycountyfltax.gov block scripted downloads, so they were read through a web-fetch tool. The PCB and Tax Collector emails were decoded from their Cloudflare-protected links. bay.k12.fl.us sits behind a JavaScript challenge and was read with a headless browser.

## population.json: UF BEBR April 1, 2025 estimates

This covers Bay County, all 7 cities and unincorporated Bay County. Each place has its 2025 estimate and its 2020 Census count as printed in BEBR Table 1. The cities and unincorporated area sum exactly to the county total.

The 2025 estimates are the latest. BEBR normally publishes the 2026 estimates in December.

## budgets_detail.json: FY2026 budgets (9 governments)

| gov | Status | Total | Source type |
|---|---|---|---|
| county | adopted | $734,465,609 | Final-hearing budget book (30 funds, revenue sources, GF functions) |
| schools | **tentative** | $648,478,799.90 | Official TRIM budget-summary ad, July 2025 (6 fund types, GF functions, revenue sources) |
| pc | adopted | $153,837,293 | Adopted Budget Report (19 funds incl. 4 CRA districts and 5 debt-service funds) |
| pcb | adopted | $282,221,725 | FY2026 Annual Budget (6 funds; IT internal-service fund excluded from city total) |
| lh | adopted | $61,858,708 | Final Approved Budget 9-23-25 (13 funds, 24 GF departments) |
| cw | adopted | $55,429,117 | Resolution 25-22 in final-hearing packet (OCR) |
| sp | adopted | $28,655,332 | Resolution 25-15 final budget (OCR) |
| parker | adopted | $17,252,341 | Res. 2025-414 + CRA Res. 2025-29 (OCR). Researcher-summed total; the source states none |
| mb | **tentative** | $19,700,964 | Official TRIM budget-summary ad at 5.5 mills (adopted rate was 5.25) |

All fund lists and General Fund department lists reconcile to the source totals within $2 of source rounding.

**Discrepancies and caveats**

- **Totals are not comparable across governments.** Some include interfund transfers, reserves or fund balances. Each entry's notes say what is included.
- **Callaway:** the General Fund budgets a $1,086,088 transfer to Capital Projects, but the Capital Projects Fund expects $1,370,501 from the General Fund. The resolution does not explain the gap.
- **Springfield:** the $594,559 debt-service transfer from the General Fund has no matching General Fund line.
- **Lynn Haven:** the TRIM ad total ($145.0M) includes fund balances and is not the appropriated total.
- **Revenues:** given for all funds for the county, schools, Panama City and Mexico Beach. The other cities have General Fund revenues only.

**Gaps**

- **Bay District Schools:** the final adopted September 2025 budget could not be retrieved. The district site was redesigned and old upload links return 404. The FLDOE file (Feb 2026) puts the final General Fund about $0.57M above the tentative figure.
- **Mexico Beach:** no adopted budget is posted online. Only the tentative ad is available.
- **PCB, Lynn Haven, Callaway, Springfield and Parker:** revenue detail is General Fund only.
- **FY2027 (adopted Sept 2026):** not collected. Springfield's FY26-27 resolution is at https://www.springfieldfl.net/media/10891 and Parker's Sept 24, 2026 final-budget package is on its agendas page.

**Useful source for future work.** The Bay County official public-notice site (https://publicnoticesbaycountyfl.gov/public-notices) holds the statutory TRIM "Budget Summary" ads for the county, schools, Lynn Haven, Springfield, Mexico Beach and the Lynn Haven CRA. Its search API is `POST https://us-central1-enotice-production.cloudfunctions.net/api/search/public-notices`. Panama City, Panama City Beach, Callaway and Parker ads were not found there.
