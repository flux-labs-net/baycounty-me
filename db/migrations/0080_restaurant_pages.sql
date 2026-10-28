-- Restaurant pages (/restaurants/<name>-<license>, site/restaurants_page.py): two new columns on restaurants, built by
-- site/page_datasets.py. recent_results is the result level of the last six inspections, newest first ("ok warning
-- closed ..."), for the track-record strip on the site and in the apps; page_url is the restaurant's page on the site.
alter table restaurants add column if not exists "recent_results" text;
alter table restaurants add column if not exists "page_url" text;
