# 2026 Bay County local elections: candidates and platforms

File: `candidates_2026.json` (as of 2026-10-21; general election 2026-11-03). Campaign finance totals live separately in `../campaign/`.

## Coverage
19 local contests from the 2026 cycle (county, school board, county court, special district, and municipal):

- **On the Nov 3 ballot (7):** School Board District 3 (runoff, Moore vs. Haley), Callaway Wards 1 and 2, Panama City Beach Wards 1 and 3, and Lake Powell CDD Seats 2 and 5 (CDD voters only).
- **Decided in the Aug 18 primary (1):** School Board District 2 (Littleton).
- **Elected unopposed at qualifying (9):** County Commission Districts 2 and 4, County Judge Groups 1 and 4, School Board District 5, Springfield Wards 3 and 4, and Mexico Beach Groups 4 and 5.
- **Decided earlier in 2026 (2):** Springfield Mayor (Apr 21) and Lynn Haven Mayor, partial term. For Lynn Haven, the Jan 20 recall vote was canceled after the mayor resigned, and the commission appointed Dave Lowery.

Withdrawn and non-qualified filers are kept in their races and marked with their `status`.

Not included: state, federal and multi-county races (including Circuit Judge Groups 7 and 10), and ballot measures such as the Lynn Haven charter amendments. According to the SOE, no mosquito-control or soil and water seats are on the 2026 ballot. Panama City, Parker and the other Lynn Haven and Mexico Beach seats are up in April 2027.

## Method
1. **Roster and status:** taken from the Bay County SOE "Offices up for Election" page, the SOE snapshot PDFs, and the SOE VoterFocus candidate lists for three reporting groups: 2026 Primary/General, 2026 Municipal (Apr 21), and Lynn Haven Recall. Statuses such as Elected, Withdrawn and Did not qualify come from those lists. Office names were checked against the Notice of General Election.
2. **Results:** taken from SOE official results (enr.electionsfl.org/BAY 4001 for the primary and 3948 for April). The only exception is Lynn Haven, which has no SOE result; that outcome comes from local news reports, as noted in the file.
3. **Incumbents:** confirmed from official city, school district and county pages where possible. Unconfirmed incumbents are left `null` and listed in `gaps`.
4. **Platforms:** written only from the candidate's own materials: campaign websites and the candidate statement each candidate files with the SOE, shown on their VoterFocus page. Third-party guides were used only to find candidate-owned links, never as text. News coverage was not used for platforms.
   - Each candidate gets 3 to 6 neutral bullets phrased as the candidate's position ("Wants…", "Says…"). Contact details, family details and endorsements are left out.
   - If no material was found, `platform` is `[]` and `platform_note` explains why.
   - Every bullet traces to a URL in `platform_sources`.
5. **Names:** shown as printed on the 2026 ballots where available. Otherwise they follow the SOE filing names.

## Status values
- `race.status`: `on_ballot_nov3`, `decided_primary`, `elected_unopposed`, `decided_earlier_2026`.
- `candidate.status`: `on_ballot`, `won`, `lost_primary`, `lost`, `withdrew`, `did_not_qualify`, `elected_unopposed`, `appointed`. The values `lost`, `did_not_qualify` and `appointed` extend the original schema.

See the file's `status_legend` and `gaps` arrays for details and known limitations. The main limitation is that campaign Facebook pages could not be read.
