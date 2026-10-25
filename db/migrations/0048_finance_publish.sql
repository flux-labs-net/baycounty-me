-- Which finance files are published to the open-books tables (0047), and by whom. Finance schema only, so
-- api/__tests__/finance-api.test.js applies it with 0015 and 0016.
alter table finance.uploads add column if not exists published_at timestamptz;
alter table finance.uploads add column if not exists published_by text;
