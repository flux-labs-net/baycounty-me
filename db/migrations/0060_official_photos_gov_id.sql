-- official_photos was created without the gov_id column every dataset row carries (site/opendata.py add_gov_id),
-- so the sync refused the official-photos dataset. Add it, like data_completeness (0057).

alter table official_photos add column if not exists "gov_id" text;
create index if not exists official_photos_gov_id_idx on official_photos (gov_id);
