-- Officials' business ties (data/careers): which registered businesses each named official, department leader and local
-- candidate is listed on in state corporate records, and how those businesses touch campaigns and public money.
--
-- Private: schema `careers`, loaded by db/scripts/load_careers.py. A name match between an official and a Sunbiz person
-- is a lead, so every pair has a review_status; nothing is public until an admin confirms the pair in the admin
-- "Business ties" tab. Links that involve a private person (a shared officer) keep that person's key here only.
-- Public: official_businesses and official_business_links, written by careers.publish() (origin = 'careers', so the
-- dataset sync leaves them alone). They name only officials and candidates, never other people. Keyed by county.

create schema if not exists careers;
revoke all on schema careers from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on schema careers from anon, authenticated'; end if;
end $$;

-- One row per official / Sunbiz person pair found by name. Upserted on load so review decisions survive.
create table if not exists careers.matches (
  county text not null,
  person_id text not null,                    -- data/entities/people.json id
  person_key text not null,                   -- registry.people person_key
  official_name text not null,
  label text,                                 -- 'Panama City Mayor', '2026 candidate: ...'
  gov_ids jsonb not null default '[]',
  score int not null,
  confidence text not null,                   -- high, medium, low
  reasons jsonb not null default '[]',
  n_businesses int not null default 0,
  review_status text not null default 'unreviewed',   -- unreviewed, confirmed, rejected
  reviewed_by text,
  reviewed_at timestamptz,
  loaded_at timestamptz not null default now(),
  primary key (county, person_id, person_key)
);

-- Businesses each matched pair is listed on (replaced on every load).
create table if not exists careers.roles (
  county text not null,
  person_id text not null,
  person_key text not null,
  doc_number text not null,
  entity_name text not null,
  titles text,                                -- MGR, P, VP, RA ...
  role_kind text,                             -- officer, registered_agent
  entity_status text,                         -- A active, I inactive
  filing_type text,
  nonprofit boolean,
  principal_city text,
  file_date date,                             -- the role began on or after this
  closed_year int,                            -- dissolved entities: last annual report or last filing (dissolution), whichever is later
  source_url text,
  primary key (county, person_id, person_key, doc_number)
);

-- Links between those businesses and public life (replaced on every load). requires = ["person_id|person_key", ...]:
-- the pairs that must all be confirmed before the link is published.
create table if not exists careers.links (
  id bigint generated always as identity primary key,
  county text not null,
  link_type text not null,                    -- shared_business, own_business_gift, partner_business_gift, public_payee
  person_id text not null,
  other_person_id text,
  candidate text,
  office text,
  gov_id text,
  payer text,                                 -- public_payee: the paying government's short name
  own_government boolean,
  self_gift boolean,
  doc_number text,
  entity_name text,
  related_doc text,
  related_name text,
  shared_people int,
  shared_person_keys jsonb,                   -- private: never published
  amount numeric,
  items int,
  first_date text,
  last_date text,
  record_types jsonb,
  detail text,
  requires jsonb not null,
  source_url text,
  report_url text
);
create index if not exists careers_links_county_idx on careers.links (county, link_type);

-- Sunbiz lists only current officers. Each load stamps when a (business, name, title) was first and last seen, so
-- start and end dates build up from the first load on.
create table if not exists careers.role_seen (
  county text not null,
  doc_number text not null,
  name_key text not null,
  title text not null default '',
  first_seen date not null,
  last_seen date not null,
  primary key (county, doc_number, name_key, title)
);

create table if not exists careers.loads (
  id bigint generated always as identity primary key,
  county text not null,
  loaded_at timestamptz not null default now(),
  git_sha text,
  matches int, roles int, links int,
  summary jsonb
);

do $$ declare t text; begin
  foreach t in array array['matches', 'roles', 'links', 'role_seen', 'loads'] loop
    execute format('alter table careers.%I enable row level security', t);
  end loop;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema careers from anon, authenticated';
  end if;
end $$;

-- ---------- public datasets ----------
create table if not exists official_businesses (
  id bigint generated always as identity primary key,
  "person_id" text,
  "official" text,
  "official_role" text,
  "business" text,
  "sunbiz_doc_number" text,
  "titles" text,
  "role_kind" text,
  "business_status" text,
  "filing_type" text,
  "nonprofit" boolean,
  "principal_city" text,
  "filed_date" text,
  "closed_year" bigint,
  "role_first_seen" text,
  "county" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists official_businesses_person_idx on official_businesses ("person_id");
create index if not exists official_businesses_gov_idx on official_businesses (government_key);

create table if not exists official_business_links (
  id bigint generated always as identity primary key,
  "link_type" text,
  "person_id" text,
  "official" text,
  "other_person_id" text,
  "other_official" text,
  "candidate" text,
  "office" text,
  "business" text,
  "sunbiz_doc_number" text,
  "related_business" text,
  "related_doc_number" text,
  "shared_people" bigint,
  "payer" text,
  "own_government" boolean,
  "self_gift" boolean,
  "amount" numeric,
  "items" bigint,
  "first_date" text,
  "last_date" text,
  "detail" text,
  "county" text,
  "source_url" text,
  "report_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists official_business_links_person_idx on official_business_links ("person_id");
create index if not exists official_business_links_gov_idx on official_business_links (government_key);

insert into datasets (id, table_name, title, description) values
  ('official-businesses', 'official_businesses', $t$Officials' businesses$t$, $d$Registered businesses (Florida Division of Corporations) that list an elected official, department leader or local candidate as an officer, manager or registered agent, with the filing date and status. Each official-to-record match was checked by hand. Only officials and candidates are named.$d$),
  ('official-business-links', 'official_business_links', $t$Officials' business ties$t$, $d$How officials' and candidates' registered businesses connect to public life: two officials on the same business, an official's business giving to a campaign, a donor business that shares an officer with a candidate's business (the shared person is counted, not named), and an official's business paid by a local government. Published only for hand-checked matches.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

do $$ declare t text; begin
  foreach t in array array['official_businesses', 'official_business_links'] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists "public read" on %I', t);
    execute format('create policy "public read" on %I for select using (true)', t);
    execute format('drop trigger if exists %I on %I', t || '_touch', t);
    execute format('create trigger %I before update on %I for each row execute function touch_updated_at()', t || '_touch', t);
  end loop;
end $$;

-- Rewrite a county's public rows from the private tables: confirmed pairs only.
create or replace function careers.publish(p_county text) returns integer
language plpgsql as $$
declare n integer := 0; m integer := 0;
begin
  delete from public.official_businesses where origin = 'careers' and county = p_county;
  delete from public.official_business_links where origin = 'careers' and county = p_county;

  insert into public.official_businesses (person_id, official, official_role, business, sunbiz_doc_number, titles, role_kind, business_status,
      filing_type, nonprofit, principal_city, filed_date, closed_year, role_first_seen, county, source_url, gov_id, government_key, origin, record_hash)
    select distinct on (r.person_id, r.doc_number)
      r.person_id, m.official_name, m.label, r.entity_name, r.doc_number, r.titles, r.role_kind,
      case r.entity_status when 'A' then 'Active' when 'I' then 'Inactive' else r.entity_status end,
      r.filing_type, r.nonprofit, initcap(r.principal_city), r.file_date::text, r.closed_year,
      (select min(s.first_seen)::text from careers.role_seen s where s.county = r.county and s.doc_number = r.doc_number),
      r.county, r.source_url, m.gov_ids->>0, (select key from public.governments where key = m.gov_ids->>0), 'careers',
      md5(r.county || '|' || r.person_id || '|' || r.doc_number)
    from careers.roles r join careers.matches m on m.county = r.county and m.person_id = r.person_id and m.person_key = r.person_key
    where r.county = p_county and m.review_status = 'confirmed'
    order by r.person_id, r.doc_number, r.role_kind;
  get diagnostics n = row_count;

  insert into public.official_business_links (link_type, person_id, official, other_person_id, other_official, candidate, office, business,
      sunbiz_doc_number, related_business, related_doc_number, shared_people, payer, own_government, self_gift, amount, items, first_date, last_date,
      detail, county, source_url, report_url, gov_id, government_key, origin, record_hash)
    select l.link_type, l.person_id,
      (select official_name from careers.matches x where x.county = l.county and x.person_id = l.person_id limit 1),
      l.other_person_id,
      (select official_name from careers.matches x where x.county = l.county and x.person_id = l.other_person_id limit 1),
      l.candidate, l.office, l.entity_name, l.doc_number, l.related_name, l.related_doc, l.shared_people,
      l.payer, l.own_government, l.self_gift, l.amount, l.items, l.first_date, l.last_date,
      l.detail, l.county, l.source_url, l.report_url, l.gov_id, (select key from public.governments where key = l.gov_id), 'careers',
      md5(l.county || '|' || l.link_type || '|' || l.person_id || '|' || coalesce(l.other_person_id, '') || '|' || coalesce(l.candidate, '') || '|'
          || coalesce(l.doc_number, '') || '|' || coalesce(l.related_doc, '') || '|' || coalesce(l.gov_id, ''))
    from careers.links l
    where l.county = p_county
      and not exists (select 1 from jsonb_array_elements_text(l.requires) q
                      where not exists (select 1 from careers.matches x where x.county = l.county and x.review_status = 'confirmed'
                                        and x.person_id || '|' || x.person_key = q))
    on conflict (origin, record_hash) do nothing;
  get diagnostics m = row_count;
  return n + m;
end $$;

revoke all on function careers.publish(text) from public;
