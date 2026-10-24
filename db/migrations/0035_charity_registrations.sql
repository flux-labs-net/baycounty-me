-- Florida charitable solicitation registrations (FDACS Check-A-Charity, data/nonprofits/fetch_fdacs.py), joined to the
-- nonprofits from 0034 by FEIN, then by exact name.
--
-- Public dataset (same standard columns, public read policy and trigger as 0021), written by the dataset sync:
--   charity_registrations   one row per registration with a county address: status, dates, the financial summary the
--                           charity reported to the state, its fundraising firms. Officers and directors go to
--                           nonprofit_board_members (source "FDACS charity registration"; public per the site owner, 2026-10-24).
-- nonprofits gains the registration number, status and reported figures. registry.publish_board_officials() learns the
-- "fdacs" seat source.

create table if not exists charity_registrations (
  id bigint generated always as identity primary key,
  "registration_number" text,
  "nonprofit_id" text,
  "name" text,
  "dba" text,
  "fein" text,
  "matched_by" text,
  "status" text,
  "status_detail" text,
  "registration_date" text,
  "expiration_date" text,
  "city" text,
  "zip" text,
  "website" text,
  "fiscal_year_end" text,
  "total_revenue" numeric,
  "contributions" numeric,
  "government_grants" numeric,
  "program_expenses" numeric,
  "fundraising_expenses" numeric,
  "management_expenses" numeric,
  "total_expenses" numeric,
  "program_percent" numeric,
  "fundraising_percent" numeric,
  "fundraising_consultants" text,
  "officers_listed" bigint,
  "other_registrations" text,
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
create index if not exists charity_registrations_gov_idx on charity_registrations (government_key);
create index if not exists charity_registrations_gov_id_idx on charity_registrations (gov_id);
create index if not exists charity_registrations_nonprofit_id_idx on charity_registrations ("nonprofit_id");
create index if not exists charity_registrations_registration_number_idx on charity_registrations ("registration_number");
create index if not exists charity_registrations_fein_idx on charity_registrations ("fein");

insert into datasets (id, table_name, title, description) values ('charity-registrations', 'charity_registrations', $t$Nonprofits: Florida charity registrations$t$, $d$Charities with a county address registered with the Florida Department of Agriculture and Consumer Services to ask the public for donations (Check-A-Charity): registration status and dates, the revenue and the program, fundraising and management spending each reported to the state, and the professional fundraising firms it uses. nonprofit_id links to the nonprofits dataset (joined by FEIN, then by exact name); the officers and directors each registration lists are in nonprofit-board-members.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table charity_registrations enable row level security;
drop policy if exists "public read" on charity_registrations;
create policy "public read" on charity_registrations for select using (true);

drop trigger if exists charity_registrations_touch on charity_registrations;
create trigger charity_registrations_touch before update on charity_registrations for each row execute function touch_updated_at();

alter table nonprofits add column if not exists "fdacs_registration" text;
alter table nonprofits add column if not exists "fdacs_status" text;
alter table nonprofits add column if not exists "fdacs_expires" text;
alter table nonprofits add column if not exists "fdacs_fiscal_year_end" text;
alter table nonprofits add column if not exists "fdacs_revenue" numeric;
alter table nonprofits add column if not exists "fdacs_program_expenses" numeric;
alter table nonprofits add column if not exists "fdacs_fundraising_expenses" numeric;
alter table nonprofits add column if not exists "fdacs_management_expenses" numeric;
alter table nonprofits add column if not exists "fdacs_url" text;
create index if not exists nonprofits_fdacs_registration_idx on nonprofits ("fdacs_registration");

-- Same as 0034, with the FDACS registration named as a source.
create or replace function registry.publish_board_officials(p_county text) returns integer
language plpgsql as $$
declare n integer := 0;
begin
  delete from public.nonprofit_officials where origin = 'registry' and county = p_county;
  insert into public.nonprofit_officials (official_id, person_id, official, official_roles, nonprofit_id, nonprofit, ein, titles, first_year, last_year,
      current, sources, county, source_url, origin, record_hash)
    select m.official_id, min(m.board_key), max(m.official_name), max(p.official_roles::text), s.nonprofit_id, max(s.nonprofit_name), max(s.ein),
      string_agg(distinct s.title, ', '), min(s.tax_year), max(s.tax_year), bool_or(s.current),
      string_agg(distinct case s.source when 'sunbiz' then 'State corporate filing' when 'irs_990n' then 'IRS 990-N'
                                       when 'fdacs' then 'FDACS charity registration' else 'IRS ' || upper(replace(s.source, 'irs_', '')) end, ', '),
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
