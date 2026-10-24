# Going statewide

BayCounty.me covers one Florida county. The goal is to run the same site for other counties and cities, and eventually
the whole state. This note says what's already set up for that, what's still tied to Bay County, and the order to fix it.

## What's in place

- **One place config per county.** `places/<id>/place.json` holds everything that changes from county to county:
  the site name and domain, the wordmark, the contact email, the "who runs it" page, and the list of local governments
  (with the name each dataset uses for each government). Bay County is `places/fl-bay/`.
- **`site/place.py`** loads it. Pick a county with the `PLACE` environment variable (default `fl-bay`).
- **The shared chrome reads from it.** The header wordmark, the Governments menu, the footer, the link-preview tags
  and the Spanish footer all come from the place config. `site/govs.py` builds its government list from it.
- **The design is token-based.** `site/tokens.css` (light and dark) and `site/site.css` style every page. A county
  could get its own accent by overriding tokens, without touching page code.

## What's still Bay County only

About 700 mentions of Bay County live in page copy, data paths and the API. The biggest:

| Where | What |
| --- | --- |
| `site/build_site.py` | page titles and descriptions in `PAGES`, About and Privacy copy |
| `site/og.py` | link-preview image text |
| `site/updates.py` | the changelog (fine to leave: it's history) |
| `site/tax_page.py` | authority names, district list, DOR source links |
| `site/address.js`, `site/addr_page.py` | Bay County GIS map servers for address lookups |
| `api/v1.js`, `api/mcp.js`, `api/_emails.js` | API descriptions, MCP tool text, email templates |
| `data/**` | one folder per topic, all Bay County |
| `ios/` | app name and copy |

## Plan

1. **Chrome and governments** (done in this change): place config, shared header/footer/menu, government list.
2. **Data by place.** Move `data/<topic>/` to `data/<place>/<topic>/` and give every loader the place's folder.
   Statewide sources come first because one fetch covers every county: DOR millage and levies (TACD, Table 1),
   Auditor General audit reports, EDR revenue and spending, FEMA public assistance, and Division of Elections data.
3. **Page copy from the config.** Replace "Bay County" in titles, ledes and descriptions with the place name. Keep
   county-specific explainers (Hurricane Michael, Amendment 3 estimates) behind a per-place feature list in
   `place.json`, so a page only builds where its data exists.
4. **Database and API by place.** Add a `place_id` column to every dataset table (a migration plus `load.py`),
   and accept `?place=fl-bay` on `/api/v1` with Bay County as the default so current clients keep working.
5. **Address lookups by place.** Each county's parcel and district map servers go in `place.json`.
6. **Hosting.** Two options, to decide before the second county ships:
   - one site per county (e.g. a domain per county, same code, `PLACE` set per Vercel project), or
   - one statewide site with each county under a path (e.g. `/fl/bay/...`) and a state landing page.
   One statewide site is cheaper to run and lets people compare counties; per-county domains keep local branding.

## Adding a county (once steps 2 to 5 are done)

1. Copy `places/fl-bay/place.json` to `places/fl-<county>/place.json` and fill it in.
2. Run the statewide fetchers for the new place, then the county-only ones that exist.
3. `PLACE=fl-<county> python3 site/build_site.py`.
