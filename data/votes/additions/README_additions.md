# Votes additions (researched 2026-10-21)

New vote records to merge into `data/votes/votes.json`. Each file has the shape
`{"source_notes": [...], "votes": [...]}` and uses the same vote schema as `votes.json`.
No new bodies or members were needed: all names match the existing `bds-board`, `pcb-council`
and `sp-commission` rosters. The PCB file also uses the former members already listed
there (Mark Sheldon, Phil Chester).

| File | Votes | Period | Source |
|---|---|---|---|
| `school_board.json` | 105 | Jan 2024 – Sept 2026 | BoardDocs minutes and agenda attachments |
| `pcb_2024.json` | 73 | Jan 2024 – Feb 2025 | Draft minutes printed in the next meeting's agenda packet |
| `springfield.json` | 53 | Aug 2024 – Oct 2026 | Scanned minutes from the city document library, read with OCR |
| `updates_2026.json` | 0 | — | Nothing new was posted (see below) |
| `cra_2026.json` | 15 | Oct 2025 – Sept 2026 | Panama City CRA minutes (June 2, Aug 4, Sept 1, 2026) and Callaway CRA minutes (Oct 28, 2025) |

## What was found

### Bay District School Board (`school_board.json`)
- **Where the records are.** The district site bay.k12.fl.us blocks scripts with a JavaScript
  challenge. Its "School Board Meetings" page (on the Thrillshare host) links to
  **BoardDocs at `go.boarddocs.com/fl/bcsdfl`**. BoardDocs has full minutes for every board
  meeting from Jan 9, 2024 to Sept 22, 2026, and every motion lists "Yes:" and "No:" by name.
- **Amounts.** Dollar amounts come from the staff cover memos and backup PDFs attached to each
  item. Many of those PDFs are scans, so their text was produced by OCR.
- **What is included:**
  - all tentative and final budget and millage votes for FY2024-25, FY2025-26 and FY2026-27,
    with roll calls
  - construction prices (GMPs), purchases and contracts of about $500,000 or more
  - the Chartwells food contract and the sheriff's school deputy contracts
  - land, easement and insurance items
  - **every non-unanimous or failed vote** (35 split or failed votes in all; split motions to adjourn were skipped)
- **Notable split or failed votes:**
  - Feb 2025 TPG visiting teachers
  - Oct 2025 Invo Healthcare (3-2)
  - July 14, 2026: the $250,000 Connected Leadership Partners contract failed 2-3. A revised
    $110,000 version later passed 5-0.
  - Sept 22, 2026: a $3.05 million MacBook student-device purchase failed 2-3
  - Jerry Register cast most of the lone "no" votes, including on the Chartwells renewals, the
    sheriff's deputy contract, salary schedules and charter items.
- **Replace two existing entries.** `votes.json` has two news-based entries, 2024-09-10 and
  2025-07-31. The minutes-based entries here, which have roll calls, should replace them.

### Panama City Beach 2024 (`pcb_2024.json`)
- **Where the records are.** The Granicus archive posts 2024 minutes for March only, but each
  agenda packet (on CloudFront, linked from ViewPublisher view_id=1) includes the draft minutes
  of the previous meeting for approval. These are text PDFs, so no OCR was needed. Every 2024
  council meeting is covered, including:
  - the Aug. 6 budget workshop
  - the Sept. 12 meeting, which adopted the FY2024-25 budget (Res. 24-163) and the CRA budget
    (Res. 24-164)
  - the Sept. 26 meeting
- **No millage vote.** PCB levies no city property tax, so there is no millage vote. The budget
  was adopted on Sept. 12, and Sept. 26 had only a consent agenda.
- **What is included:**
  - regular-agenda money items: contracts, purchases, grants, fees, assessments, land and
    budget amendments
  - consent items of $250,000 or more
  - all split votes: the Ordinance 1651 move to November elections (3-2 twice, 4-1 once), the
    animal control ordinance, board appointments, 206 N. Arnold Road land use and rezoning
    denials (3-1 with one abstention), and a budget-workshop lighting deferral
- **Two 2025 meetings added.** Jan. 9 and Feb. 13, 2025 (the $2.15 million Arnold Road office
  purchase) were also missing from the dataset and are included.
- **Draft minutes.** The packets hold draft minutes. Each was approved without changes being
  noted at the next meeting, but check against final minutes if PCB ever posts them.

### Springfield (`springfield.json`)
- **Where the records are.** The city domain is **springfieldfl.net**; springfieldfl.org does
  not resolve. Its document library, category "Minutes", now has minutes for nearly every
  meeting from July 2024 to Oct 5, 2026. All 66 files were downloaded and the scanned PDFs were
  read with OCR.
- **What was found:**
  - **FY2025 final hearing (Sept. 16, 2024).** It is in the "Special Called Commission
    Meeting/Workshop" minutes. Res. 24-22 kept the rate at 4.865 mills (rolled-back rate
    4.6096) and Res. 24-23 adopted a $21,972,273 budget, both 5-0. The existing votes.json
    entry with unknown votes should be replaced.
  - **FY2027 hearings.** The final hearing on Sept. 22, 2026 (Res. 26-11: 4.865 mills,
    rolled-back rate 4.7224; Res. 26-12: $19,589,673, both 5-0) and the tentative hearing on
    Sept. 8, 2026 are both included.
  - **Nov. 2024.** Ordinance 600's 900 Transmitter Road land-use change is the only split vote
    found: the roll call lists the mayor as "nay" but the minutes print "(4-0)", so it is
    recorded here as 4-1. Also in Nov. 2024: the $15 million Regions Bank loan (Res. 24-26).
  - **May 2025.** Flock cameras, the AshBritt price increase and the first CRA budget.
  - **Sept. 2025.** CRA budgets, sidewalk and facade awards, commissioner pay and the
    stream-restoration design.
  - **Other.** The $22.3 million City Complex award (Oct. 2024), the $5.7 million Civic Center
    award (June 2025), the $1.04 million School Ave streetscape (Sept. 2026), SRF loan pledges
    and the insurance switch to PRM.
- **Not repeated.** Items already in `votes.json` were left out.

### CRA boards (`cra_2026.json`, added 2026-10-21)
- **Panama City CRA.** 14 votes from the June 2, Aug 4 and Sept 1, 2026 minutes, all 5-0 with
  named roll calls: TIF rebate approvals (Golden Developments, KBP Properties, Angel's Place,
  416 Jenks), two $15,000 Millville storefront grants, the $8,150 St. Andrews Waterfront
  Partnership match, the 1342 MLK Blvd land transfer to American Legion Post 424, the SPARK
  pilot, the FY2027 CRA budget (Res. CRA20260901.1, $11,492,914 across four districts) and the
  end of CRA funding for FLOCK cameras. Motions only "to open for discussion" were skipped.
  The Oct 13, 2026 meeting has no minutes yet.
- **Callaway CRA.** Only one CRA meeting after Sept 18, 2025 has minutes: Oct 28, 2025 (mobile
  home skirting grant, unanimous). The Sept 17, 2026 CRA budget hearing has an agenda only.
- **Lynn Haven CRA.** No CRA Board meeting after May 26, 2026 is listed in the Agenda Center.

## Still unavailable, and why
- **Bay County BOCC after June 16, 2026.** The Clerk's OnBase minutes search was queried
  directly through its public JSON API. It lists 2026 minutes only through June 16, 2026, so
  there are still no minutes for July 21 (maximum millage) or the Sept. 2026 FY2027 hearings.
  The separate Sept. 3 and Sept. 16, 2025 budget-hearing minutes are also still missing (only
  the regular-meeting minutes for those dates are posted), as are Dec. 2 and Dec. 16, 2025 and
  March 3, 2026. Another option for later: the API returns stable document IDs at
  `https://bayforms.baycoclerk.com/PublicAccess/api/Document/<id>/`, which could serve as direct
  source links.
- **Parker FY2027 final hearing (Sept. 24, 2026).** The council approved these minutes on
  Oct. 6, 2026 (agenda item 1), but they are not yet posted. The newest posted minutes are from
  Sept. 15, 2026.
- **School board Oct. 13, 2026 meeting.** Its minutes are not yet on BoardDocs.
- **PCB seat numbers and term ends.** pcbfl.gov still returns 403 to scripts, so these were not
  checked.
- **School board consent items.** Routine consent-agenda purchases are not itemized, because
  the minutes list them without amounts. The consent motions' roll calls are in BoardDocs if
  wanted.

## Caveats
- OCR text (Springfield minutes, many school board attachments) may carry character errors.
  Check the source PDF before publishing any single amount.
- `plain_summary` includes the vote count and names. `summary` and `headline` avoid both, with
  one exception: PCB appointment headlines name the appointees.
