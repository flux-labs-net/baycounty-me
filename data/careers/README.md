# Careers: officials' business ties

Links the officials, department leaders and candidates named in `data/entities/people.json` to the registered
businesses they are listed on in the Florida Division of Corporations (Sunbiz) file, and finds where those businesses
meet campaigns and public money. Method in `build_careers.py`'s docstring.

| Step | Where |
|---|---|
| Build matches, roles and links | `build_careers.py` (uses `data/sunbiz/build_sunbiz.build()` and `data/entities/records.py`) |
| Load the private `careers` schema and publish confirmed rows | `db/scripts/load_careers.py` (Sync database workflow, after `load_registry.py`) |
| Review matches | `/admin`, Business ties tab (`api/_careers.js`) |
| Public page | `/connections/business-ties`, from datasets `official-businesses` and `official-business-links` |

Rules:

- A name match is a lead. Nothing is public until an admin confirms the official / Sunbiz person pair.
- Only officials and candidates are named in public data. Other officers on a business are counted, never named.
- Sunbiz lists current officers only. `careers.role_seen` records the first and last load each officer appears in, so
  start and end dates build up from the first load on.

Run locally: `python3 data/careers/build_careers.py bay` prints a summary (no names).
