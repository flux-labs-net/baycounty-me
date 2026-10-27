-- The People page's order (Jeremy, 2026-10-27): by government, then title, then last name.
-- people-directory now carries the government each person is listed under, their title rank and group, current or past, and their position,
-- so the site, the apps and the API share one order (site/people_pages.py directory_order).

alter table people_directory add column if not exists "primary_gov_id" text;
alter table people_directory add column if not exists "title_rank" bigint;
alter table people_directory add column if not exists "title_group" text;
alter table people_directory add column if not exists "status" text;
alter table people_directory add column if not exists "sort_order" bigint;
create index if not exists people_directory_sort_idx on people_directory (sort_order);

update datasets set description = $d$Elected officials, department leaders and 2026 candidates named in BayCounty.me records, with their roles. sort_order is the People page's order: by the government they are listed under (primary_gov_id), then title (title_rank 0 mayor, chair or elected officer to 8 past candidate, named in title_group), then last name. status is current (in office, on staff or on the 2026 ballot) or past (former officials and past candidates).$d$, updated_at = now()
  where id = 'people-directory';
