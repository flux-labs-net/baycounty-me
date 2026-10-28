# Volunteer needs: open needs from public volunteer boards, and nonprofits that use volunteers

| File | What it is |
|---|---|
| `fetch_needs.py` | Reads open volunteer needs in the county from United Way of Northwest Florida's volunteer center (volunteer.unitedwaynwfl.org) and Idealist's listings for the county's towns. Keeps needs in a county town or ZIP. Title, organization, what volunteers do, when, city, ZIP and the sign-up link only; emails and phone numbers are taken out of descriptions. Runs daily in `refresh-meetings.yml`. A board that fails keeps its needs on file until they close. `python3 data/volunteer/fetch_needs.py --county bay` |
| `fetch_990_volunteers.py` | The volunteer count (Form 990 Part I line 6) from each county nonprofit's latest e-filed 990, read from the same IRS e-file mirror as `data/nonprofits/fetch_irs.py`. Rerun after refreshing the nonprofits data. |
| `<county>/needs.json`, `volunteers_990.csv` | The fetch output: ingestion inputs. |
| `<county>/organizations.json` | Hand-checked: board organization names that don't match a nonprofit's filed name exactly (`aliases`), and a plain cause for nonprofits whose IRS category doesn't say what volunteers do (`causes`). |

Datasets (`site/volunteer_data.py`, migration `0072_volunteer_board.sql`): `volunteer-needs` (one row per open need) and
`volunteer-orgs` (local nonprofits that reported volunteers or have a need open). Page: `/volunteer`.

Blocked or not used: VolunteerMatch now redirects to Idealist; Volunteer Florida turns cloud servers away (403); the
United Way board shows only its current open needs (no paging), so the count is small and real.
