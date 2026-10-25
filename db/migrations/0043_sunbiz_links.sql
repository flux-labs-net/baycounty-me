-- Shared-owner groups: fix the Sunbiz links. A document-number "SearchResultDetail" link without Sunbiz's internal
-- aggregate id lands on "not a functioning page". Link to the entity-name search results instead (the business is
-- listed first, with its document number). Same rule as data/entities/ids.py sunbiz_url().

create or replace function registry.urlencode(p text) returns text
language sql immutable strict as $$
  select coalesce(string_agg(
    case when ch ~ '^[A-Za-z0-9._~-]$' then ch
         else (select string_agg('%' || upper(lpad(to_hex(get_byte(convert_to(ch, 'UTF8'), i)), 2, '0')), '' order by i)
               from generate_series(0, octet_length(convert_to(ch, 'UTF8')) - 1) i) end, '' order by n), '')
  from regexp_split_to_table(p, '') with ordinality t(ch, n)
$$;

create or replace function registry.sunbiz_url(p_name text, p_doc text) returns text
language sql immutable as $$
  select case
    when coalesce(btrim(p_name), '') = '' then
      case when coalesce(btrim(p_doc), '') = '' then null
           else 'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults?inquiryType=DocumentNumber&searchTerm='
                || registry.urlencode(upper(btrim(p_doc))) end
    when regexp_replace(btrim(p_name), '\s+', ' ', 'g') ~ '[/\\&*%:<>?]' then
      'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults?inquiryType=EntityName&searchTerm='
      || registry.urlencode(regexp_replace(btrim(p_name), '\s+', ' ', 'g'))
    else 'https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/EntityName/'
      || registry.urlencode(regexp_replace(btrim(p_name), '\s+', ' ', 'g')) || '/Page1'
  end
$$;

create or replace function registry.publish_group(p_county text, p_group text, p_candidate text) returns integer
language plpgsql as $$
declare n integer := 0;
begin
  delete from public.shared_owner_groups where origin = 'registry' and county = p_county and group_id = p_group and candidate = p_candidate;
  insert into public.shared_owner_groups (group_id, candidate, office, election, business, sunbiz_doc_number, business_status, business_amount,
      business_dates, group_businesses, group_checks, group_total, all_checks_1000, same_day, shared_people, county, source_url,
      campaign_report_url, gov_id, government_key, origin, record_hash, business_last_filed)
    select g.group_id, g.candidate, g.office, g.election, b->>'entity_name', b->>'doc_number',
      case b->>'status' when 'A' then 'Active' when 'I' then 'Inactive' else b->>'status' end,
      (b->>'amount')::numeric, (select string_agg(d, ', ') from jsonb_array_elements_text(b->'dates') d),
      g.n_businesses, g.n_checks, g.combined_amount, g.all_at_1000, g.same_day, g.n_people, g.county,
      registry.sunbiz_url(coalesce(e.name, b->>'entity_name'), b->>'doc_number'),
      g.report_url, g.government_key, (select key from public.governments where key = g.government_key), 'registry',
      md5(g.county || '|' || g.group_id || '|' || g.candidate || '|' || (b->>'doc_number')),
      case when b->>'status' = 'A' then null else e.last_report_year end
    from registry.shared_owner_groups g cross join lateral jsonb_array_elements(g.businesses) b
    left join registry.entities e on e.county = g.county and e.doc_number = b->>'doc_number'
    where g.county = p_county and g.group_id = p_group and g.candidate = p_candidate and g.review_status = 'confirmed';
  get diagnostics n = row_count;
  return n;
end $$;


select registry.publish_all(county) from (select distinct county from registry.shared_owner_groups) c;
