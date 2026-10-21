-- Shared identifiers (data/entities): every dataset row carries gov_id; vendor, person and vote/contract links
-- get their own columns. Ids come from data/entities/*.json. Added columns are nullable, so rows added by hand still load.

-- governments beyond the 9 main ones (constitutional officers, special districts, tourism agencies) are seeded by
-- db/scripts/load.py from data/entities/governments.json; government_aliases gets every alias there.
alter table governments add column if not exists parent_key text;

-- gov_id on every dataset table
do $$
declare t text;
begin
  foreach t in array array['government_profiles','votes','member_votes','contracts','change_orders','emergency_purchases','cra_payments',
    'property_tax_rates','debt','audit_findings','fema_michael_projects','sales_tax_projects','bed_tax_collections','fees_assessments',
    'officials_pay','meetings','campaign_finance','vendor_payments','bonds','budget_detail','budget_per_resident','salary_positions',
    'salary_leaders','candidates_2026','campaign_contributions_2026','property_tax_exemptions']
  loop
    execute format('alter table %I add column if not exists gov_id text', t);
    execute format('create index if not exists %I on %I (gov_id)', t || '_gov_id_idx', t);
  end loop;
end $$;
