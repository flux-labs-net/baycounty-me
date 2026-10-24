-- Public view of shared-owner campaign gifts (/connections/shared-owners): groups of businesses that share an officer,
-- manager or registered agent and gave to the same candidate. Only groups an admin marked "confirmed" in the
-- Business owners tab (registry.shared_owner_groups.review_status) are published, one row per business. No person
-- names: the people who link the businesses appear only as a count.
--
-- Rows here have origin = 'registry' (never 'site_build'), so the dataset sync leaves them alone. They are written by
-- registry.publish_group(), which the admin review action and db/scripts/load_registry.py call.

create table if not exists shared_owner_groups (
  id bigint generated always as identity primary key,
  "group_id" text,
  "candidate" text,
  "office" text,
  "election" text,
  "business" text,
  "sunbiz_doc_number" text,
  "business_status" text,
  "business_amount" numeric,
  "business_dates" text,
  "group_businesses" bigint,
  "group_checks" bigint,
  "group_total" numeric,
  "all_checks_1000" boolean,
  "same_day" boolean,
  "shared_people" bigint,
  "county" text,
  "source_url" text,
  "campaign_report_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists shared_owner_groups_gov_idx on shared_owner_groups (government_key);
create index if not exists shared_owner_groups_gov_id_idx on shared_owner_groups (gov_id);
create index if not exists shared_owner_groups_group_idx on shared_owner_groups ("group_id", "candidate");

insert into datasets (id, table_name, title, description) values ('shared-owner-groups', 'shared_owner_groups', $t$Shared-owner campaign gifts$t$, $d$Businesses that share an officer, manager or registered agent (state corporate records) and gave to the same local candidate, one row per business. Only groups checked by hand are listed. People are not named. Each company is its own contributor under Florida law, so a group is legal when each company is a real contributor.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table shared_owner_groups enable row level security;
drop policy if exists "public read" on shared_owner_groups;
create policy "public read" on shared_owner_groups for select using (true);

drop trigger if exists shared_owner_groups_touch on shared_owner_groups;
create trigger shared_owner_groups_touch before update on shared_owner_groups for each row execute function touch_updated_at();

-- Rewrite the public rows for one group and candidate from the private registry: removed unless confirmed.
create or replace function registry.publish_group(p_county text, p_group text, p_candidate text) returns integer
language plpgsql as $$
declare n integer := 0;
begin
  delete from public.shared_owner_groups where origin = 'registry' and county = p_county and group_id = p_group and candidate = p_candidate;
  insert into public.shared_owner_groups (group_id, candidate, office, election, business, sunbiz_doc_number, business_status, business_amount,
      business_dates, group_businesses, group_checks, group_total, all_checks_1000, same_day, shared_people, county, source_url,
      campaign_report_url, gov_id, government_key, origin, record_hash)
    select g.group_id, g.candidate, g.office, g.election, b->>'entity_name', b->>'doc_number',
      case b->>'status' when 'A' then 'Active' when 'I' then 'Inactive' else b->>'status' end,
      (b->>'amount')::numeric, (select string_agg(d, ', ') from jsonb_array_elements_text(b->'dates') d),
      g.n_businesses, g.n_checks, g.combined_amount, g.all_at_1000, g.same_day, g.n_people, g.county,
      'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResultDetail?inquirytype=DocumentNumber&directionType=Initial&searchTerm=' || (b->>'doc_number'),
      g.report_url, g.government_key, (select key from public.governments where key = g.government_key), 'registry',
      md5(g.county || '|' || g.group_id || '|' || g.candidate || '|' || (b->>'doc_number'))
    from registry.shared_owner_groups g cross join lateral jsonb_array_elements(g.businesses) b
    where g.county = p_county and g.group_id = p_group and g.candidate = p_candidate and g.review_status = 'confirmed';
  get diagnostics n = row_count;
  return n;
end $$;

-- Rewrite every public row for a county (after a reload).
create or replace function registry.publish_all(p_county text) returns integer
language plpgsql as $$
declare n integer := 0; r record;
begin
  delete from public.shared_owner_groups where origin = 'registry' and county = p_county;
  for r in select group_id, candidate from registry.shared_owner_groups where county = p_county and review_status = 'confirmed' loop
    n := n + registry.publish_group(p_county, r.group_id, r.candidate);
  end loop;
  return n;
end $$;

revoke all on function registry.publish_group(text, text, text) from public;
revoke all on function registry.publish_all(text) from public;
