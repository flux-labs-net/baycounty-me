# Nonprofits: every county nonprofit and who sits on its board

| File | What it is |
|---|---|
| `fetch_irs.py` | Pulls the county's tax-exempt organizations from IRS data mirrored in the public GivingTuesday 990 data lake (`s3://gt990datalake-rawdata`): the EO Business Master File, 990-N postcards, and every 990 / 990-EZ / 990-PF e-filed since 2019 (officers, directors, trustees, key employees, Schedule I grants, revenue, expenses, assets). `python3 data/nonprofits/fetch_irs.py --county bay --work /tmp/np`. Uses `data/sunbiz/counties.py` for ZIPs and the Sunbiz filter output for EINs. |
| `<county>/orgs.csv.gz`, `filings.csv.gz`, `officers.csv.gz`, `grants.csv.gz`, `postcards.csv.gz` | The fetch output: ingestion inputs. |
| `fetch_fdacs.py` | Pulls the county's Florida charitable solicitation registrations from FDACS (Business License Lookup, County = Bay, Program = Charitable Organization, every status) and each one's Check-A-Charity record: status, dates, FEIN, the financial summary reported to the state, fundraising firms, and officers and directors. One request at a time with a pause of 3 seconds or more. csapp.fdacs.gov refuses connections from the cloud build sandbox, so run it from a desktop: `python data/nonprofits/fetch_fdacs.py --county bay`. |
| `<county>/fdacs_registrations.csv.gz`, `fdacs_officers.csv.gz` | The FDACS fetch output (city, state and ZIP only; no street addresses). |
| `build_nonprofits.py` | Joins IRS and Sunbiz records into one list of organizations, groups board seats into people, matches them to officials (`data/entities/people.json`) and to Sunbiz officers (their businesses and those businesses' campaign gifts), and matches organizations to payment records and grants. Method in its docstring. Run by `data/build.py`. Writes `<county>/nonprofits.json` (organizations, board members, payments, grants). |

Where the data goes:

- **Public** datasets: `nonprofits` (one row per organization), `nonprofit-board-members` (one row per person per
  nonprofit, names as filed; Jeremy decided on 2026-10-24 that board members are public records and should be shown),
  `nonprofit-payments` (payment records whose payee is a local nonprofit), `nonprofit-grants` (Schedule I grants local
  nonprofits gave). Page: `/connections/nonprofits`. Connections payees that are nonprofits carry `nonprofit_id`.
- **Public** dataset `charity-registrations`: one row per FDACS registration with a county address, joined to `nonprofits` by
  FEIN, then by exact name or DBA (`matched_by`); a registration that matches neither is added as its own nonprofit
  (`np-fd-<registration number>`). `nonprofits` carries the registration number, status, expiration and reported figures
  (`fdacs_*`). The officers and directors listed on a registration are board seats (source "FDACS charity registration") in
  `nonprofit-board-members`; on a lapsed or withdrawn registration they count as past, not current.
  As of the first fetch (2026-10-24, 218 registrations) Check-A-Charity shows no FEIN and no officers: officers are only in
  each registration's uploaded application PDF, which isn't parsed yet, so every join is by name and no FDACS seats exist.
  Registrations outside Check-A-Charity (Law NA, Exempt, Closed, Denied, Not Soliciting) have no financials.
- **Public after review**: `nonprofit-officials`, officials, department leaders and candidates on nonprofit boards. Rows
  are written by `registry.publish_board_officials()` only for name matches an admin confirmed in /admin → Nonprofit boards.
- **Private** (schema `registry`, migration 0034, loaded by `db/scripts/load_registry.py`): official name matches with
  their review status and the businesses each person's name matches in Sunbiz (leads, not findings), plus the seats
  they're built from.

Name matching is a lead, not a finding. People are grouped by last + first name (nicknames folded, split by middle
initial when two differ), so two people with a common name can be merged; `same_name_people` shows how many Sunbiz people
share the name. "Same person" business links (the Sunbiz officer with that name and address is also on the nonprofit's
own state filing) are stronger than "same name" links.

Homeowner and condo associations are included (they are nonprofit corporations) but are left out of shared-board
counts: a developer or management company officer often sits on dozens of them.

Refresh: rerun `fetch_irs.py` (the IRS files update monthly; e-filed returns arrive through the year) and commit the
five `.csv.gz` files. The site build and the Sync database workflow do the rest.

Refresh FDACS: rerun `fetch_fdacs.py` from a desktop (registrations renew yearly) and commit the two `fdacs_*.csv.gz`
files and `fdacs_fetch_log.json`.

Not covered yet: 990s filed on paper (no e-file XML).
