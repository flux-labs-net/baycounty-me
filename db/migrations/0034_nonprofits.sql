-- Nonprofits (data/nonprofits): every nonprofit in a county, who sits on its board, and how they connect to the rest of
-- the site's records.
--
-- Public datasets (same standard columns, public read policy and trigger as 0021), written by the dataset sync:
--   nonprofits, nonprofit_payments, nonprofit_grants, nonprofit_board_members (names as filed with the IRS and the state;
--   the site owner decided on 2026-10-24 that board members are public)
--   nonprofit_officials                                 written by registry.publish_board_officials() (below), only for
--                                                       official/board matches an admin confirmed
-- Private (schema registry, from 0031; no public policy, admin API only): board people with their Sunbiz business
-- links, every seat, and the official name matches waiting for review. Loaded by db/scripts/load_registry.py. Keyed by county.

create table if not exists nonprofits (
  id bigint generated always as identity primary key,
  "nonprofit_id" text,
  "name" text,
  "ein" text,
  "sunbiz_doc_number" text,
  "city" text,
  "zip" text,
  "county" text,
  "kind" text,
  "irs_recognized" boolean,
  "subsection" text,
  "foundation_type" text,
  "ntee_code" text,
  "category" text,
  "ruling_year" bigint,
  "irs_filing_requirement" text,
  "sunbiz_status" text,
  "sunbiz_filed" text,
  "irs_assets" numeric,
  "irs_income" numeric,
  "irs_revenue" numeric,
  "latest_return_form" text,
  "latest_return_year" bigint,
  "total_revenue" numeric,
  "total_expenses" numeric,
  "total_assets" numeric,
  "employees" bigint,
  "returns_on_file" bigint,
  "website" text,
  "mission" text,
  "board_members_listed" bigint,
  "shares_board_with" bigint,
  "gov_payment_records" bigint,
  "gov_dollars_in_records" numeric,
  "paid_by" text,
  "grants_given_count" bigint,
  "grants_given_cash" numeric,
  "grants_from_local_nonprofits" numeric,
  "campaign_gifts_total" numeric,
  "campaign_gift_candidates" text,
  "source_url" text,
  "sunbiz_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists nonprofits_gov_idx on nonprofits (government_key);
create index if not exists nonprofits_gov_id_idx on nonprofits (gov_id);
create index if not exists nonprofits_nonprofit_id_idx on nonprofits ("nonprofit_id");
create index if not exists nonprofits_ein_idx on nonprofits ("ein");
create index if not exists nonprofits_sunbiz_doc_number_idx on nonprofits ("sunbiz_doc_number");

insert into datasets (id, table_name, title, description) values ('nonprofits', 'nonprofits', $t$Nonprofits$t$, $d$Every nonprofit in the county: organizations recognized by the IRS with a local address, and active Florida nonprofit corporations (Sunbiz) based here. Type, IRS subsection, latest 990 revenue, expenses and assets, how many board members its filings list, how many of those sit on another local board, government payment records and grants. Board members are in nonprofit-board-members.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofits enable row level security;
drop policy if exists "public read" on nonprofits;
create policy "public read" on nonprofits for select using (true);

drop trigger if exists nonprofits_touch on nonprofits;
create trigger nonprofits_touch before update on nonprofits for each row execute function touch_updated_at();

create table if not exists nonprofit_payments (
  id bigint generated always as identity primary key,
  "nonprofit_id" text,
  "nonprofit" text,
  "payer" text,
  "record_type" text,
  "record_id" text,
  "payee_as_filed" text,
  "amount" numeric,
  "date" text,
  "what" text,
  "cra_status" text,
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
create index if not exists nonprofit_payments_gov_idx on nonprofit_payments (government_key);
create index if not exists nonprofit_payments_gov_id_idx on nonprofit_payments (gov_id);
create index if not exists nonprofit_payments_nonprofit_id_idx on nonprofit_payments ("nonprofit_id");

insert into datasets (id, table_name, title, description) values ('nonprofit-payments', 'nonprofit_payments', $t$Nonprofits: government payment records$t$, $d$Payment records on the site (contracts, check registers, tourism agency payments, CRA ledger) whose payee is a local nonprofit, matched by name.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofit_payments enable row level security;
drop policy if exists "public read" on nonprofit_payments;
create policy "public read" on nonprofit_payments for select using (true);

drop trigger if exists nonprofit_payments_touch on nonprofit_payments;
create trigger nonprofit_payments_touch before update on nonprofit_payments for each row execute function touch_updated_at();

create table if not exists nonprofit_grants (
  id bigint generated always as identity primary key,
  "grantor_id" text,
  "grantor" text,
  "grantor_ein" text,
  "recipient_id" text,
  "recipient" text,
  "recipient_ein" text,
  "recipient_city" text,
  "recipient_state" text,
  "tax_year" bigint,
  "cash" numeric,
  "noncash" numeric,
  "purpose" text,
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
create index if not exists nonprofit_grants_gov_idx on nonprofit_grants (government_key);
create index if not exists nonprofit_grants_gov_id_idx on nonprofit_grants (gov_id);
create index if not exists nonprofit_grants_grantor_id_idx on nonprofit_grants ("grantor_id");
create index if not exists nonprofit_grants_recipient_id_idx on nonprofit_grants ("recipient_id");

insert into datasets (id, table_name, title, description) values ('nonprofit-grants', 'nonprofit_grants', $t$Nonprofits: grants they gave$t$, $d$Grants to organizations reported on Schedule I of local nonprofits' 990 returns, with the recipient linked when it is also a local nonprofit.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofit_grants enable row level security;
drop policy if exists "public read" on nonprofit_grants;
create policy "public read" on nonprofit_grants for select using (true);

drop trigger if exists nonprofit_grants_touch on nonprofit_grants;
create trigger nonprofit_grants_touch before update on nonprofit_grants for each row execute function touch_updated_at();

create table if not exists nonprofit_board_members (
  id bigint generated always as identity primary key,
  "person_id" text,
  "person" text,
  "nonprofit_id" text,
  "nonprofit" text,
  "ein" text,
  "role" text,
  "titles" text,
  "first_year" bigint,
  "last_year" bigint,
  "current" boolean,
  "hours_per_week" numeric,
  "compensation" numeric,
  "compensation_year" bigint,
  "sources" text,
  "other_current_boards" bigint,
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
create index if not exists nonprofit_board_members_gov_idx on nonprofit_board_members (government_key);
create index if not exists nonprofit_board_members_gov_id_idx on nonprofit_board_members (gov_id);
create index if not exists nonprofit_board_members_person_id_idx on nonprofit_board_members ("person_id");
create index if not exists nonprofit_board_members_nonprofit_id_idx on nonprofit_board_members ("nonprofit_id");

insert into datasets (id, table_name, title, description) values ('nonprofit-board-members', 'nonprofit_board_members', $t$Nonprofits: board members$t$, $d$Officers, directors, trustees and key employees of local nonprofits as listed on their IRS returns (2019 on), 990-N postcards and state corporate filings: one row per person per nonprofit with titles, years on file, reported pay and hours, and how many other current local boards the same name sits on (homeowner associations aside). person_id groups the same name across boards; two people with a common name can share one.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofit_board_members enable row level security;
drop policy if exists "public read" on nonprofit_board_members;
create policy "public read" on nonprofit_board_members for select using (true);

drop trigger if exists nonprofit_board_members_touch on nonprofit_board_members;
create trigger nonprofit_board_members_touch before update on nonprofit_board_members for each row execute function touch_updated_at();

create table if not exists nonprofit_officials (
  id bigint generated always as identity primary key,
  "official_id" text,
  "person_id" text,
  "official" text,
  "official_roles" text,
  "nonprofit_id" text,
  "nonprofit" text,
  "ein" text,
  "titles" text,
  "first_year" bigint,
  "last_year" bigint,
  "current" boolean,
  "sources" text,
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
create index if not exists nonprofit_officials_gov_idx on nonprofit_officials (government_key);
create index if not exists nonprofit_officials_gov_id_idx on nonprofit_officials (gov_id);
create index if not exists nonprofit_officials_official_id_idx on nonprofit_officials ("official_id");
create index if not exists nonprofit_officials_nonprofit_id_idx on nonprofit_officials ("nonprofit_id");

insert into datasets (id, table_name, title, description) values ('nonprofit-officials', 'nonprofit_officials', $t$Officials on nonprofit boards$t$, $d$Elected officials, department leaders and candidates listed as an officer or director of a local nonprofit in its IRS returns or state corporate filings. Only matches checked by hand are listed.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofit_officials enable row level security;
drop policy if exists "public read" on nonprofit_officials;
create policy "public read" on nonprofit_officials for select using (true);

drop trigger if exists nonprofit_officials_touch on nonprofit_officials;
create trigger nonprofit_officials_touch before update on nonprofit_officials for each row execute function touch_updated_at();
-- Connections payees that are local nonprofits (site/connections.py)
alter table connections_payees add column if not exists "nonprofit_id" text;

-- ---------- private: board members ----------

-- One row per person on a county nonprofit board (seats grouped by last + first name, split by middle initial).
create table if not exists registry.board_people (
  county text not null,
  board_key text not null,                    -- stable hash of the grouping key
  display_name text not null,
  name_key text not null,                     -- LAST FIRST (nickname folded)
  middle_initial text,
  n_nonprofits int not null,
  n_current int not null,                     -- boards on the latest filings
  n_current_civic int not null default 0,     -- of them, not homeowner or condo associations
  n_seats int not null,
  official_id text,                           -- data/entities/people.json id when the name matches (a lead until reviewed)
  official_name text,
  official_roles jsonb,
  same_name_people int not null default 0,    -- Sunbiz people in the county with this name (higher = weaker name links)
  registry_person_keys jsonb not null,        -- registry.people with this name
  linked_person_keys jsonb not null,          -- registry.people on this person's own nonprofit Sunbiz filings (name + address)
  n_businesses int not null default 0,        -- active for-profit businesses those people run
  n_donor_businesses int not null default 0,  -- of them, businesses that gave to local campaigns
  donor_gifts_total numeric not null default 0,
  businesses jsonb not null,                  -- [{doc_number, name, status, via, gifts_total, candidates}]
  loaded_at timestamptz not null default now(),
  primary key (county, board_key)
);
create index if not exists registry_board_people_name on registry.board_people (name_key);
create index if not exists registry_board_people_official on registry.board_people (official_id);

-- One row per listing: a person on one filing (990 return year, 990-N postcard, Sunbiz annual report).
create table if not exists registry.board_seats (
  id bigint generated always as identity primary key,
  county text not null,
  board_key text not null,
  nonprofit_id text not null,                 -- public.nonprofits.nonprofit_id
  nonprofit_name text,
  ein text,
  source text not null,                       -- irs_990, irs_990ez, irs_990pf, irs_990n, sunbiz
  name_as_filed text,
  title text,
  tax_year int,
  board boolean not null,                     -- officer, director or trustee (false: key employee or former)
  current boolean not null,                   -- on the organization's latest filing of that kind
  roles text,
  hours numeric,
  compensation numeric,
  object_id text,                             -- IRS e-file id
  source_url text,
  foreign key (county, board_key) references registry.board_people (county, board_key) on delete cascade
);
create index if not exists registry_board_seats_person on registry.board_seats (county, board_key);
create index if not exists registry_board_seats_np on registry.board_seats (county, nonprofit_id);

-- Board members whose name matches an official, department leader or candidate. Upserted on load so the review
-- survives; only confirmed rows are published to public.nonprofit_officials.
create table if not exists registry.board_official_matches (
  county text not null,
  board_key text not null,
  official_id text not null,
  official_name text,
  match_method text not null default 'name',
  review_status text not null default 'unreviewed',  -- unreviewed, confirmed, rejected
  reviewed_by text,
  reviewed_at timestamptz,
  loaded_at timestamptz not null default now(),
  primary key (county, board_key, official_id)
);

do $$ declare t text; begin
  foreach t in array array['board_people', 'board_seats', 'board_official_matches'] loop
    execute format('alter table registry.%I enable row level security', t);
  end loop;
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema registry from anon, authenticated';
  end if;
end $$;

-- Rewrite the public rows for one county from confirmed matches: one row per official and nonprofit.
create or replace function registry.publish_board_officials(p_county text) returns integer
language plpgsql as $$
declare n integer := 0;
begin
  delete from public.nonprofit_officials where origin = 'registry' and county = p_county;
  insert into public.nonprofit_officials (official_id, person_id, official, official_roles, nonprofit_id, nonprofit, ein, titles, first_year, last_year,
      current, sources, county, source_url, origin, record_hash)
    select m.official_id, min(m.board_key), max(m.official_name), max(p.official_roles::text), s.nonprofit_id, max(s.nonprofit_name), max(s.ein),
      string_agg(distinct s.title, ', '), min(s.tax_year), max(s.tax_year), bool_or(s.current),
      string_agg(distinct case s.source when 'sunbiz' then 'State corporate filing' when 'irs_990n' then 'IRS 990-N' else 'IRS ' || upper(replace(s.source, 'irs_', '')) end, ', '),
      p_county, (array_agg(s.source_url order by s.tax_year desc nulls last))[1], 'registry',
      md5(p_county || '|' || m.official_id || '|' || s.nonprofit_id)
    from registry.board_official_matches m
    join registry.board_people p on p.county = m.county and p.board_key = m.board_key
    join registry.board_seats s on s.county = m.county and s.board_key = m.board_key and s.board
    where m.county = p_county and m.review_status = 'confirmed'
    group by m.official_id, s.nonprofit_id;
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function registry.publish_board_officials(text) from public;
