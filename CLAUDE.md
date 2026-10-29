# BayCounty.me: working rules

## Every page's data is in the database and the API

Any new page, section or app screen ships with its data in the database and reachable through `/api/v1`. No data that
exists only inside a page's HTML/JS, a hardcoded list, or an app-only file. Files are fine as ingestion inputs
(`data/**`) and as the published open-data downloads, not as the place a page's data lives.

For a new page:

1. Publish its data as a dataset: add it to `site/opendata.py` `datasets()` (or `site/page_datasets.py` for page data).
   Flat rows, plain column names, a `source_url` where there is one.
2. Add a numbered migration in `db/migrations/` that creates the table (same standard columns, public read policy and
   trigger as `0021_page_datasets.sql`). The sync (`db/scripts/load.py`) fails if a dataset has no table or a column is missing.
3. Add the page to `api/_pages.js` with the datasets and endpoints that hold its data. `api/__tests__/pages.test.js`
   fails when a page is missing, points at an unknown dataset, or a dataset has no migration.
4. A new endpoint (not a dataset) goes in `api/v1.js`, its OpenAPI paths, the MCP tools in `api/mcp.js` when it answers a
   common question, and the endpoint table on `site/developers_page.py`.
5. The iOS app covers the page in `ios/BayCountyKit/.../SitePages.swift` (native, dataset or web).

## Every name links to its profile

Every company, official, candidate, nonprofit, board member, business and government has one entity id (`kind:key`) and
one profile URL, from `site/entity_graph.py` (`page_url`). Link names with `site/entity_links.py` (`a`, `person`,
`vendor`, `gov`) in Python and `BC.href(id)` / `BC.a(id, text)` in page scripts; known names in page text are linked
automatically. A new dataset that names people or organizations should add its connections in `entity_graph.build()`
(public rows only; hand-checked, database-only rows go in `api/_entities.js` `liveConnections`).

## Share and link previews

Every page gets a Share button and every table row, list item and card a Copy / Share menu from `site/share.js` (text
summary + a link that jumps to the record). Lists it can't spot get `data-share-items` (on the list) or
`data-share-record`; a record page can set its own text with `<div hidden data-share-text="...">`. Every page needs a
preview image: static pages get one from `site/og.py` at build; per-record pages without one (restaurants, `/profile/*`)
are drawn on request by `api/og.js` (link-preview crawlers get `/profile/*` titles from `api/meta.js`).

## Privacy

Individual campaign donors are never named (summed totals only), except people who run a registered business: a
donor whose name and street address match a Sunbiz officer, manager or registered agent is listed by name with their
businesses (`data/campaign/owner_gifts.py`, dataset `owner-gifts`; Jeremy, 2026-10-24). Never their address or occupation. Salary data names only elected officials and
department leaders. Unnamed grant recipients stay grouped. Private home addresses are not shown.

## Checks

`python3 site/build_site.py > /dev/null && npm test`. Migrations are checked in CI (`db/scripts/check_migrations.py`).
