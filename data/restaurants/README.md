# Restaurant inspections

Food service inspections and licenses from the Florida Department of Business and Professional Regulation (DBPR),
Division of Hotels and Restaurants: https://www2.myfloridalicense.com/hotels-restaurants/public-records/

| File | What it is |
|---|---|
| `fetch_dbpr.py` | Reads the state's files and keeps one county. Daily (refresh-meetings.yml): this fiscal year's inspections and today's license list. `--history` (one time, needs openpyxl and xlrd) adds every fiscal year back to July 2015, keeping rows from 2016 on. |
| `<county>/inspections.csv` | One row per inspection visit, merged by visit id so past years stay when the state's current-year file rolls over in July. Violation items as `code:count`. |
| `<county>/licenses.csv` | Every food service license in the county today. The licensee's mailing address and phone are dropped. |
| `<county>/fetch.json` | When each file was read, and any error. |

`site/page_datasets.py` turns these into the `restaurants` and `restaurant-inspections` datasets (migration 0070), which
feed `/restaurants`. New businesses (`new-businesses`, `/new-businesses`) come from `data/sunbiz/<county>/entities.csv.gz`.
To add a county, add its DBPR county number and region to `COUNTIES` in `fetch_dbpr.py`.
