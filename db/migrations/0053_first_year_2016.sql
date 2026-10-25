-- The site starts in 2016 (Jeremy, 2026-10-25): nothing from fiscal year 2015 or earlier, or dated before 2016, is
-- kept. Ingestion leaves older records out (data/entities/cutoff.py, api/_cutoff.js) and the next sync replaces the
-- site_build rows; this removes older rows of every origin (hand-entered and scraped too) right away.
--
-- site_year_of(v) is the year a value points at, the same rule as cutoff.year_of(): the latest four-digit year in it
-- ('FY2015' -> 2015, '2015-09-30' -> 2015, 'Sep 2009 - Nov 2011' -> 2011, '2008 purchase; final payment FY2022' -> 2022).
-- A row is deleted when the column that dates it points before 2016; empty values (still in office, no end) are kept.

create or replace function site_year_of(v text) returns int language sql immutable set search_path = pg_catalog as $$
  select max(m[1]::int) from regexp_matches(coalesce(v, ''), '(?<![0-9])((?:19|20)[0-9]{2})(?![0-9])', 'g') as m
$$;

do $$
declare
  r record;
begin
  for r in select * from (values
    -- dataset tables: the column that dates each row (date_end where the row has structured dates)
    ('budget_years', 'fiscal_year'), ('government_years', 'fiscal_year'), ('cra_tax_increment', 'fiscal_year'),
    ('cra_increment_checks', 'fiscal_year'), ('cra_payments', 'date_end'), ('officeholder_terms', 'end_date'),
    ('accountability_events', 'sort_date'), ('connections_payments', 'date'), ('nonprofit_payments', 'date'),
    ('nonprofit_grants', 'tax_year'), ('nonprofit_board_members', 'last_year'), ('nonprofit_officials', 'last_year'),
    ('charity_registrations', 'expiration_date'), ('entity_connections', 'last_date'), ('official_businesses', 'closed_year'),
    ('official_business_links', 'last_date'), ('business_donor_sunbiz', 'last_date'), ('over_limit_gifts', 'last_date'),
    ('owner_gifts', 'last_date'), ('checkbook_payments', 'fiscal_year'), ('budget_actuals', 'fiscal_year'),
    ('property_tax_rates', 'tax_year'), ('votes', 'date'), ('member_votes', 'date'), ('contracts', 'date'),
    ('change_orders', 'date'), ('emergency_purchases', 'date'), ('campaign_contributions_2026', 'date'), ('campaign_contributions_history', 'date'), ('meetings', 'start'),
    ('debt', 'date_end'), ('audit_findings', 'date_end'), ('sales_tax_projects', 'date_end'), ('bed_tax_collections', 'date_end'),
    ('fees_assessments', 'date_end'), ('officials_pay', 'date_end'), ('salary_positions', 'date_end'),
    ('salary_leaders', 'date_end'), ('budget_detail', 'date_end'), ('budget_per_resident', 'date_end')
  ) as t(tbl, col) loop
    if exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = r.tbl and column_name = r.col) then
      execute format('delete from public.%I where site_year_of(%I::text) < 2016', r.tbl, r.col);
    end if;
  end loop;
end $$;

-- a term that began before 2016 and ran past it keeps its row; its start is left blank ("in office before 2016")
update officeholder_terms set start_date = null, start_approx = null, date_start = null where site_year_of(start_date) < 2016;

-- the Front Beach Road Segment 1 project (built 2009-2013) left the Accountability console
delete from accountability_projects where project_id = 'pcb-south-thomas';

-- records request drafts for FY2015 onward are now drafts for FY2016 onward (key budgets-2016-<gov>); the old drafts go
-- unless an admin edited or sent them
do $$ begin
  if to_regclass('corr.records_requests') is not null then
    delete from corr.records_requests where key like 'budgets-2015-%' and status = 'draft' and origin = 'file';
  end if;
end $$;
