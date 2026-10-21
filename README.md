# BayCounty.me

Bay County, Florida public records in plain view: maps, money, and the documents behind them. Powered by [Flux Labs](https://fluxlabs.net/).

Live at **https://baycounty.me** (Vercel project `baycounty-me`, team Flux Labs Projects). Every push to `main` deploys.

## Layout

```
site/
  build_site.py   static site generator: layout, menu, footer, pages
  tokens.css      color and type tokens (Flux palette, Poppins)
  site.css        header, menu, footer, home, prose and glossary styles
  glossary.py     plain-English terms: one-line simple version, detail, example
  tax_page.py     Tax Dollars page: builds its dataset from data/tax/ and writes assets/tax.js
  tax.js, tax.css calculator, charts and government explorer for the Tax Dollars page
  public/         built output; this is what Vercel serves
assets/
  template.html   CRA Spending page (markup, styles, map/ledger script)
  logo_small.webp Flux Labs logo for the "Powered by" footer
data/
  panama_city.json, lynn_haven.json, pcb.json, others.json   research files, one per CRA group
  verify_results.json   independent source check of the 30 largest records
  tax/            millage.json (DOR rates and levies 2020-2025), budgets.json (FY2026 budgets),
                  finances.json (EDR audited actuals FY2021-FY2024), scripts/ used to extract them
  build.py        merges research files; sets status, counted-in-totals and overlap notes
  prep_dash.py    turns merged data + map geometry into the dashboard dataset
geo/
  basemap.py      simplifies coastline, county, city and CRA district shapes
  cra_gis.json    official CRA district boundaries (Bay County GIS, Admin_A12/MapServer/27)
  *.json          city limits (U.S. Census TIGER) and Bay County outline
```

## Rebuild

```bash
cd data && python3 build.py && python3 prep_dash.py
cd ../site && python3 build_site.py
git add -A && git commit -m "Update" && git push
```

`geo/basemap.py` also needs `geo/land.json` (Natural Earth 10m land, not committed because it is 10 MB):
`curl -o geo/land.json https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson`

## Adding a page

1. Add it to `MENU` in `site/build_site.py` (a top-level link, or a child under a drop-down such as Public Money).
2. Add a `(path, title, description, render_function)` entry to `PAGES`.
3. Rebuild and push.

## Plain-English terms

Every term on the site lives in `site/glossary.py`. Wrap a word with `term('id', 'text')` in `build_site.py` (or `<span class="term" data-term="id">text</span>` in page JS) and it gets a dotted underline; hover, tap or Tab to it for the simple explanation, with a link to `/glossary#id`. Write the `simple` line so a fifth-grader can follow it.

## Data rules

- Every figure comes from a public record with a linked source. Nothing is estimated.
- Status: **Spent** (reported paid), **Committed** (awarded, not fully paid), **Budgeted** / **Proposed** (plans), **Incoming** (money to the CRA), **Not CRA-funded**.
- Totals count each dollar once. Components of a listed project total, possible duplicates and non-CRA money stay in the ledger but are left out of totals (`count: false` with an `overlap` reason).
- Corrections go to hello@fluxlabs.net.
