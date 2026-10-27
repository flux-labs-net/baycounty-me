-- Name variants: one company, one name.
--
-- 1. donor_contracts is one row per gift now (a company's gift to one campaign), not one row per gift and paying
--    government. vendor_name is the company's one name on the site; contract_governments / contract_gov_ids list every
--    government that paid it (built by site/app_data.py donor_contracts()).
-- 2. name_match_reviews holds an admin's call on two business names that look alike ("Emeral Coast Striping" and
--    "Emerald Coast Striping"): confirmed = one company, rejected = keep apart. The candidates come from
--    data/entities/build_entities.py (vendor_review.json look_alike_names); data/entities/export_name_decisions.py writes
--    these rows to data/entities/name_decisions.json in the daily refresh, and the next build joins or separates the names.
--    Admin only (no public read policy); read and written by api/_names.js.

alter table donor_contracts add column if not exists "vendor_name" text;
alter table donor_contracts add column if not exists "contract_governments" jsonb;
alter table donor_contracts add column if not exists "contract_gov_ids" jsonb;

create table if not exists name_match_reviews (
  id bigint generated always as identity primary key,
  a_key text not null,                 -- ids.vkey() of each name, stored in sorted order (a_key < b_key)
  b_key text not null,
  a_name text,
  b_name text,
  status text not null check (status in ('confirmed', 'rejected')),
  note text,
  reviewed_by text,
  reviewed_at timestamptz not null default now(),
  unique (a_key, b_key)
);
alter table name_match_reviews enable row level security;
