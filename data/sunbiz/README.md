# Sunbiz: who runs which business

Links county residents (officers, managers and registered agents in the Florida Division of Corporations file) to
the businesses they run, and business campaign gifts to those businesses.

| File | What it is |
|---|---|
| `sunbiz_filter.py` | Streams the state's quarterly corporate file (10 files, ~18 GB) and keeps entities with any principal, mailing, registered-agent or officer address in the county. `python3 data/sunbiz/sunbiz_filter.py <folder> --county bay` (no `--active-only`: dissolved companies are needed for older gifts). |
| `counties.py` | County keys, FIPS and ZIPs. Add a county here to run another one. |
| `<county>/entities.csv.gz`, `<county>/officers.csv.gz` | The filter output: ingestion inputs. They hold officer names and addresses as Sunbiz publishes them, so they are never published as site data. |
| `build_sunbiz.py` | Groups people, matches gifts to entities, finds shared-owner groups (method in its docstring). Run by `data/build.py`. Writes only the business-level `<county>/business_donor_sunbiz.json`. |
| `donor_overrides.json` | Optional hand review: `{"overrides": {"<name as filed>": "<doc number>" or null}}`. |

Where the data goes:

- **Public** (dataset `business-donor-sunbiz`, `/api/v1/datasets/business-donor-sunbiz`): each business donor and its
  Sunbiz record. No person names.
- **Private** (schema `registry`, migration 0031, loaded by `db/scripts/load_registry.py` in the Sync database workflow):
  entities, people (name, city, ZIP, address hash; street addresses are not stored), roles, gift matches and shared-owner
  groups with a review status. Read only by the admin API (`/api/admin?action=registry...`, the Business owners tab).

Shared-owner groups are research leads, not findings of wrongdoing: in Florida each company is its own contributor with
its own limit. Nothing about a specific person is published without the site owner's sign-off.

Refresh: download the new quarterly file, rerun `sunbiz_filter.py`, commit the two `.csv.gz` files. The sync does the rest.
