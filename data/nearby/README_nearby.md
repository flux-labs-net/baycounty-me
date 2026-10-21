# Nearby development activity: data sources

As of 2026-10-21. Machine-readable inventory: `layers.json` in this folder. It lists every candidate layer with its URL, its key fields, the live record count, the date range, whether it sends CORS headers, a spatial-query check, and up to 3 sanitized sample records.

## How every layer was tested

- I sent all requests with `Origin: https://baycounty.me`. Every layer below returns `Access-Control-Allow-Origin`. The county ArcGIS server echoes `https://baycounty.me`, and the ArcGIS Online orgs return `*`.
- Spatial test: a point in `inSR=4326`, `distance=0.5`, `units=esriSRUnit_StatuteMile`, `spatialRel=esriSpatialRelIntersects`, plus `outSR=4326`. Zoning, FLU and overlay layers were tested at distance 0, which is a point-in-polygon lookup at the address.
- Test points came from the county address points layer (`Admin_A12/MapServer/3`):
  - 1614 Ohio Ave, Lynn Haven is at -85.649355, 30.233401. That is about 1.3 km south of the approximate point in the brief.
  - 7038 W Highway 98 is at -85.759502, 30.190644. The county lists it as UNINCORPORATED, near Hathaway Bridge, not inside PCB city limits.
  - Two extra check points: one inside PCB city limits (-85.818632, 30.184243) and one in Panama City (501 Harrison Ave).

### Query quirks to handle in the browser

1. **Always pass `outSR=4326`.** The Panama City layers (`services3.arcgis.com/RfAh242jlP6Nb5vP`) are stored in WKID 103024/6441. Their distance queries fail with "SRID is not valid" unless `outSR` is set. It does no harm on the other layers.
2. **Always pass an explicit `outFields` list, never `*`.** Several layers carry owner names: `A2OWNAME`, `Property_Owner`, `Submitting_Engineer`, sale grantor/grantee fields and `APPLICANTS`. The `out` lists in `layers.json` are privacy-safe.
3. `Departmental/CodeEnforcementCases/*` is backed by a shapefile. It rejects `resultRecordCount` ("Pagination is not supported") and `outStatistics`.
4. Date fields come back as epoch milliseconds.

## What exists, by kind

### Zoning and future land use at the address: good, current
| id | Source | Count | Latest ordinance date |
|---|---|---|---|
| `bc_zoning` (recommended) | County `LandUsePlanning/MapServer/1`, countywide; the `Label` suffix gives the jurisdiction: (BC) county, (LH) Lynn Haven, (PCB) Panama City Beach | 8,555 | 2026-09-08 (reloaded 2026-09-30) |
| `bc_flu` (recommended) | County `LandUsePlanning/MapServer/2` | 9,609 | 2026-07-21 (reloaded 2026-08-11) |
| `pc_zoning` / `pc_flu` | Panama City's own ArcGIS Online org, parcel-level, with `previouszone` / `previousflu` | 18,835 / 17,301 | 2026-08-11 / 2026-12-16 (likely a data-entry error) |
| `pcb_zoning` / `pcb_flu` | PCB public map on the county server | 632 / 697 | 2025-07-24 |
| `bc_zoning_agol` | ArcGIS Online copy of `bc_zoning` | 8,555 | same |

Note: at 1614 Ohio Ave the countywide zoning layer returns `ZONING = "See FLU"` (Label `See FLU(LH)`). In this data, Lynn Haven parcels carry the district in the FLU layer, so for Lynn Haven show FLU (here `COM(LH)`). 7038 W Hwy 98 returns C-3 (BC) / GCOM (BC). Extra layer: `planning_overlays` (60 overlay districts with ordinance numbers and Municode links).

### Rezonings and land-use changes: usable, but adopted changes only
I found no layer of rezoning applications or cases. Three options:
- `bc_rezonings` (recommended): zoning polygons whose `ORD_NUM`/`ORD_DATE` record the adopting ordinance. `COMMENTS` often gives the prior district ("pre. C-1"). There are 1,856 polygons with `ORD_DATE >= 2016`, the latest dated 2026-09-08. Results within 0.5 mi: 1 near Ohio Ave, 5 near 7038 W Hwy 98.
- `bc_flu_amendments`: the same approach on the FLU layer. 1,763 since 2016, latest 2026-07-21.
- `bc_zoning_conditions`: 376 points for conditional uses, conditional rezonings and plan amendments, with condition text. It has no approval date. Example near Ohio Ave: PLCUP20260087.
- `pc_rezonings`: Panama City parcels with an ordinance and `previouszone`. 6,000 since 2020; 234 within 0.5 mi of City Hall.

Pending or denied applications, and hearing dates, are not in any layer.

### Development orders and site plans: good for county, Lynn Haven and PCB
| id | Jurisdiction | Count | Freshness |
|---|---|---|---|
| `bc_dev_orders` (recommended) | Bay County (unincorporated) `Departmental/Planning/MapServer/18` | 204 | apps received through 2026-10-16, DOs issued through 2026-10-14 |
| `lh_dev_projects` | Lynn Haven (ArcGIS Online) | 15 | approvals 2024-12 to 2026-03; has DO expiration |
| `pcb_planning_projects` | Panama City Beach (ArcGIS Online "Editing" service) | 61 | applied through 2026-06-12, edited through 2026-08-21 |
| `pcb_developments_legacy` | PCB (county server) | 115 | stale; ends 2022 |

For the "Nearby" list, query all three current layers and merge them. Each covers only its own jurisdiction. I found no development-order layer for Panama City, Callaway, Springfield or Parker.

### Code enforcement: only historical snapshots, nothing current
| id | Contents | Freshness |
|---|---|---|
| `bc_code_cases_2023` | County open cases by address point, 822 records | case numbers up to CE23/HM23; loaded March–April 2023; not updated since 2023-04-25 |
| `bc_open_code_cases` | County open cases by parcel, 1,395 records | no dates; case numbers CE15–CE20 / HM19–HM20 (about 2020) |
| `bc_unsafe_structures_2019` (+ PPDR and Blighted Parcel siblings) | Post-Hurricane Michael lists | 2019; case fields are empty |
| `springfield_code_closed` (+ sibling layers) | City of Springfield | 2014–2018 |

**Recommendation:** don't present any of these as current code enforcement activity. If you show `bc_code_cases_2023` at all, label it "2023 snapshot". No public code-case layer was found for Panama City, PCB, Lynn Haven or Callaway. The county's `Admin_A12/MapServer/33` "Code Enforcement Zones" only says which zone covers an address.

### Building permits: no public API anywhere
No jurisdiction publishes building permits as a GIS layer or open API. Only portals exist:
- **Bay County (unincorporated):** https://portal.baycountyfl.gov/Permit/Locator. This is a CityView portal and its search sits behind a CAPTCHA.
- **Panama City Beach:** https://panamacitybeach.portal.iworq.net/PANAMACITYBEACH/permits/602. A public iWorQ search with no documented API.
- **Panama City:** Cloudpermit, which needs a login (https://us.cloudpermit.com/gov/login). Info page: https://www.panamacity.gov/803/Cloudpermit
- **Lynn Haven:** https://www.cityoflynnhaven.com/543/Building-Permitting. Applications only; no public permit search found.
- **Callaway:** https://www.cityofcallaway.com/189/Building-Permits. No public search found; the site was unreliable.

Possible partial substitutes:
- `bc_elevation_certificates`: 3,432 certificates, dated through 2026-10-02, each with a PDF. Not permits, but a current signal of new or substantially improved construction in flood areas (unincorporated county). There were 87 within 0.5 mi of 7038 W Hwy 98.
- The `BuildingPermit` / `OccupancyDate` fields on the PCB project layers are almost entirely empty.
- Florida law requires local building departments to post permit and inspection utilization reports. These are aggregate statistics, not addresses.

### Other / statewide
- `fdep_coastal_permits`: FDEP Coastal Environmental Permits, current through 2026-10-16. Only 65 points fall in the Bay County bounding box, and none was within 0.5 mi of the test points. Useful only for beachfront parcels.
- `pc_capital_projects`: Panama City utility and capital project areas (SRF/CDBG). Public works, not private development.
- `bc_puds`: 8 PUD polygons, last edited 2022.

## Recommended per kind (see `recommended` in layers.json)
- zoning: `bc_zoning` (plus `pc_zoning` for Panama City parcel detail)
- flu: `bc_flu`
- rezoning: `bc_rezonings` + `bc_zoning_conditions` (+ `pc_rezonings` for Panama City)
- dev_orders: `bc_dev_orders` + `lh_dev_projects` + `pcb_planning_projects`
- code: none current; `bc_code_cases_2023` only as a labelled historical snapshot
- permits: none; link to the jurisdiction's portal instead

## Not checked or not found
- Panama City: no development-order or code-case GIS layer in its ArcGIS Online org (`GIS4CPC`).
- Callaway, Springfield, Parker, Mexico Beach: no planning-case layers beyond the Springfield code layers. Parker has a "Property Liens" layer, not reviewed.
- The county ArcGIS Online org (`services1.arcgis.com/QB0VWfqR9MD4lF0F`) hosts 548 services. I looked only at the ones whose names relate to permits, zoning, planning, code or development.
