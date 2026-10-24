# Nonprofits: every county nonprofit and who sits on its board

| File | What it is |
|---|---|
| `fetch_irs.py` | Pulls the county's tax-exempt organizations from IRS data mirrored in the public GivingTuesday 990 data lake (`s3://gt990datalake-rawdata`): the EO Business Master File, 990-N postcards, and every 990 / 990-EZ / 990-PF e-filed since 2019 (officers, directors, trustees, key employees, Schedule I grants, revenue, expenses, assets). `python3 data/nonprofits/fetch_irs.py --county bay --work /tmp/np`. Uses `data/sunbiz/counties.py` for ZIPs and the Sunbiz filter output for EINs. |
| `<county>/orgs.csv.gz`, `filings.csv.gz`, `officers.csv.gz`, `grants.csv.gz`, `postcards.csv.gz` | The fetch output: ingestion inputs. Officer names are public IRS records, but they are never published as site data. |
| `build_nonprofits.py` | Joins IRS and Sunbiz records into one list of organizations, groups board seats into people, matches them to officials (`data/entities/people.json`) and to Sunbiz officers (their businesses and those businesses' campaign gifts), and matches organizations to payment records and grants. Method in its docstring. Run by `data/build.py`. Writes only the organization-level `<county>/nonprofits.json`. |

Where the data goes:

- **Public** datasets, no board member names: `nonprofits` (one row per organization), `nonprofit-payments` (payment
  records whose payee is a local nonprofit), `nonprofit-grants` (Schedule I grants local nonprofits gave). Page:
  `/connections/nonprofits`. Connections payees that are nonprofits carry `nonprofit_id`.
- **Public after review**: `nonprofit-officials`, officials, department leaders and candidates on nonprofit boards. Rows
  are written by `registry.publish_board_officials()` only for name matches an admin confirmed in /admin → Nonprofit boards.
- **Private** (schema `registry`, migration 0034, loaded by `db/scripts/load_registry.py`): board people, every seat on
  every filing, official name matches with their review status, and the businesses each person's name matches in Sunbiz.

Name matching is a lead, not a finding. People are grouped by last + first name (nicknames folded, split by middle
initial when two differ), so two people with a common name can be merged; `same_name_people` shows how many Sunbiz people
share the name. "Same person" business links (the Sunbiz officer with that name and address is also on the nonprofit's
own state filing) are stronger than "same name" links.

Homeowner and condo associations are included (they are nonprofit corporations) but are left out of shared-board
counts: a developer or management company officer often sits on dozens of them.

Refresh: rerun `fetch_irs.py` (the IRS files update monthly; e-filed returns arrive through the year) and commit the
five `.csv.gz` files. The site build and the Sync database workflow do the rest.

Not covered yet: Florida charitable solicitation registrations (FDACS) and 990s filed on paper (no e-file XML).
