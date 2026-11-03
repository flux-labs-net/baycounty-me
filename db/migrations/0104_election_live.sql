-- Live election night results (/elections/live, GET /api/v1/election-live). api/_election_live.js reads the Supervisor
-- of Elections' results site (enr.electionsfl.org) at most about once a minute, keeps the latest count here and adds a
-- snapshot each time the SOE posts an update, so the page can show how each race moved through the night.
-- Rows are written only by the API (server connection); anyone can read them.

create table if not exists election_live (
  election_id bigint primary key,
  place_id text not null default 'fl-bay',
  name text,
  election_date date,
  source_url text,
  stamp text,                 -- the SOE site's update stamp (stampedtime.js); changes when new results post
  soe_updated text,           -- "Website last updated at" as the SOE shows it
  registered_voters bigint,
  ballots_cast bigint,
  turnout_pct numeric,
  precincts_reporting int,
  precincts_total int,
  reported jsonb not null default '{}',   -- {election_day, early_voting, vote_by_mail}: Not Reported / Partially / Completely Reported
  contests jsonb not null default '[]',  -- [{contest_id, contest, over_votes, under_votes, stats, choices:[{choice, party, votes, pct, election_day, early_voting, vote_by_mail, provisional}]}]
  checked_at timestamptz,     -- last time the SOE site was read
  changed_at timestamptz,     -- last time the numbers changed
  claim_at timestamptz,       -- one reader at a time (the API claims a read before fetching)
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists election_live_snapshots (
  id bigint generated always as identity primary key,
  election_id bigint not null references election_live(election_id) on delete cascade,
  taken_at timestamptz not null default now(),
  soe_updated text,
  ballots_cast bigint,
  precincts_reporting int,
  precincts_total int,
  totals jsonb not null default '{}'      -- {contest_id: {choice: votes}}
);
create index if not exists election_live_snapshots_idx on election_live_snapshots (election_id, taken_at);

alter table election_live enable row level security;
drop policy if exists "public read" on election_live;
create policy "public read" on election_live for select using (true);
alter table election_live_snapshots enable row level security;
drop policy if exists "public read" on election_live_snapshots;
create policy "public read" on election_live_snapshots for select using (true);

drop trigger if exists election_live_touch on election_live;
create trigger election_live_touch before update on election_live for each row execute function touch_updated_at();

-- Election night: read the SOE every minute from 6:30 p.m. Central on Nov 3, 2026 (23:30 UTC) until 8 a.m. Central on
-- Nov 4, even when nobody has the page open. Visitors' page loads keep it current outside those hours (at most once a
-- minute). The API refuses to read elections outside its own list, so the yearly repeat of these lines does nothing.
do $$ begin
  if exists (select 1 from pg_available_extensions where name = 'pg_cron') and exists (select 1 from pg_available_extensions where name = 'pg_net') then
    begin
      create extension if not exists pg_cron with schema pg_catalog;
      create extension if not exists pg_net with schema extensions;
      perform cron.schedule('election-live-eve', '30-59 23 3 11 *',
        $c$select net.http_get(url := 'https://baycounty.me/api/v1/election-live?poll=1', timeout_milliseconds := 30000)$c$);
      perform cron.schedule('election-live-night', '* 0-13 4 11 *',
        $c$select net.http_get(url := 'https://baycounty.me/api/v1/election-live?poll=1', timeout_milliseconds := 30000)$c$);
    exception when others then raise notice 'election live schedule skipped: %', sqlerrm;
    end;
  end if;
end $$;
