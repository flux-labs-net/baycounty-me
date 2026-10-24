-- Gifts over Florida's $1,000-per-election limit (data/campaign/over_limit.py): one organization giving one candidate
-- more than the limit in the same election, as the campaign reported it.
--
-- registry.limit_cases is private and reviewed by an admin in /admin (Business owners tab). Only cases marked
-- "confirmed" (over the limit as reported, no explanation found) or "resolved" (explained: a reporting error, an
-- amended report, a refund, a check designated for the general election, a Florida Elections Commission ruling) are
-- written to the public over_limit_gifts table, with the explanation and its source. Rows there have origin =
-- 'registry', so the dataset sync leaves them alone. Only organizations are listed; individual donors are never named.

create table if not exists registry.limit_cases (
  county text not null,
  case_id text not null,                      -- stable hash of county, candidate, election, phase and contributor
  candidate text not null,
  office text,
  government_key text,
  election text,
  election_year text,
  election_phase text,                        -- primary, general, or '' for a single election
  contributor text not null,
  contributor_type text,
  spellings jsonb not null default '[]',
  n_items int not null,
  gross_amount numeric not null,
  refunds numeric not null default 0,
  net_amount numeric not null,
  over_by numeric not null,
  possible_double_entry boolean not null default false,
  auto_resolution text,                       -- 'refunded' when reported refunds bring it back to the limit
  items jsonb not null,                       -- [{date, amount, kind, filed_as}]
  first_date date,
  last_date date,
  report_url text,
  in_current_data boolean not null default true,     -- false once the reports no longer show it (e.g. amended); kept if reviewed
  review_status text not null default 'unreviewed',   -- unreviewed, confirmed, resolved, rejected
  resolution text,                            -- reporting_error, amended_report, refunded, designated_general, elections_commission, other
  resolution_note text,
  resolution_url text,
  reviewed_by text,
  reviewed_at timestamptz,
  loaded_at timestamptz not null default now(),
  primary key (county, case_id)
);
alter table registry.limit_cases enable row level security;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then execute 'revoke all on registry.limit_cases from anon, authenticated'; end if;
end $$;

create table if not exists over_limit_gifts (
  id bigint generated always as identity primary key,
  "case_id" text,
  "candidate" text,
  "office" text,
  "election" text,
  "election_phase" text,
  "contributor" text,
  "contributor_type" text,
  "gifts" bigint,
  "gross_amount" numeric,
  "refunds" numeric,
  "net_amount" numeric,
  "over_by" numeric,
  "gift_list" text,
  "first_date" text,
  "last_date" text,
  "possible_double_entry" boolean,
  "status" text,
  "resolution" text,
  "resolution_note" text,
  "resolution_url" text,
  "reviewed_on" text,
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
create index if not exists over_limit_gifts_gov_idx on over_limit_gifts (government_key);
create index if not exists over_limit_gifts_gov_id_idx on over_limit_gifts (gov_id);

insert into datasets (id, table_name, title, description) values ('over-limit-gifts', 'over_limit_gifts', $t$Gifts over the contribution limit$t$, $d$Organizations that gave one local candidate more than Florida's $1,000-per-election limit, as the campaign reported it (s. 106.08, F.S.), net of reported refunds. The primary and general are separate elections. Each case was checked by hand. status is Open (over the limit as reported, no explanation found) or Resolved (resolution says why: a reporting error, an amended report, a refund, a check designated for the general election, or a Florida Elections Commission ruling). A reported overage is not a finding of wrongdoing. Individual donors are not listed.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table over_limit_gifts enable row level security;
drop policy if exists "public read" on over_limit_gifts;
create policy "public read" on over_limit_gifts for select using (true);

drop trigger if exists over_limit_gifts_touch on over_limit_gifts;
create trigger over_limit_gifts_touch before update on over_limit_gifts for each row execute function touch_updated_at();

-- Rewrite the public row for one case: published when confirmed or resolved, removed otherwise.
create or replace function registry.publish_limit_case(p_county text, p_case text) returns integer
language plpgsql as $$
declare n integer := 0;
begin
  delete from public.over_limit_gifts where origin = 'registry' and county = p_county and case_id = p_case;
  insert into public.over_limit_gifts (case_id, candidate, office, election, election_phase, contributor, contributor_type, gifts, gross_amount,
      refunds, net_amount, over_by, gift_list, first_date, last_date, possible_double_entry, status, resolution, resolution_note, resolution_url,
      reviewed_on, county, source_url, gov_id, government_key, origin, record_hash)
    select c.case_id, c.candidate, c.office, c.election, c.election_phase, c.contributor, c.contributor_type, c.n_items, c.gross_amount,
      c.refunds, c.net_amount, c.over_by,
      (select string_agg(concat_ws(' ', i->>'date', to_char((i->>'amount')::numeric, 'FM$999,999,990.00'), nullif(i->>'kind', '')), '; ' order by i->>'date')
         from jsonb_array_elements(c.items) i),
      c.first_date::text, c.last_date::text, c.possible_double_entry,
      case c.review_status when 'resolved' then 'Resolved' else 'Open' end,
      case when c.review_status = 'resolved' then c.resolution end,
      case when c.review_status = 'resolved' then c.resolution_note end,
      case when c.review_status = 'resolved' then c.resolution_url end,
      c.reviewed_at::date::text, c.county, c.report_url, c.government_key,
      (select key from public.governments where key = c.government_key), 'registry',
      md5(c.county || '|' || c.case_id)
    from registry.limit_cases c
    where c.county = p_county and c.case_id = p_case and c.review_status in ('confirmed', 'resolved');
  get diagnostics n = row_count;
  return n;
end $$;

create or replace function registry.publish_limit_all(p_county text) returns integer
language plpgsql as $$
declare n integer := 0; r record;
begin
  delete from public.over_limit_gifts where origin = 'registry' and county = p_county;
  for r in select case_id from registry.limit_cases where county = p_county and review_status in ('confirmed', 'resolved') loop
    n := n + registry.publish_limit_case(p_county, r.case_id);
  end loop;
  return n;
end $$;

revoke all on function registry.publish_limit_case(text, text) from public;
revoke all on function registry.publish_limit_all(text) from public;
