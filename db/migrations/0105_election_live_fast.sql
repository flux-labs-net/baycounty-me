-- Faster election night reads and statewide totals for /elections/live (api/_election_live.js).
-- statewide: the Florida Division of Elections' county-by-county file added up per race (state and federal races,
-- amendments, retention), read at most once a minute.
alter table election_live add column if not exists statewide jsonb;
alter table election_live add column if not exists statewide_at timestamptz;

-- Read every 20 seconds tonight instead of every minute. The command does nothing outside election night and the job
-- removes itself the next morning, so the 20-second schedule doesn't run forever.
do $$ begin
  if exists (select 1 from pg_extension where extname = 'pg_cron') and exists (select 1 from pg_extension where extname = 'pg_net') then
    begin
      perform cron.schedule('election-live-fast', '20 seconds',
        $c$select net.http_get(url := 'https://baycounty.me/api/v1/election-live?poll=1', timeout_milliseconds := 15000)
             where now() between timestamptz '2026-11-03 23:30:00+00' and timestamptz '2026-11-04 14:00:00+00';
           select cron.unschedule('election-live-fast') where now() > timestamptz '2026-11-04 14:00:00+00'$c$);
    exception when others then raise notice 'election live fast schedule skipped: %', sqlerrm;
    end;
  end if;
end $$;
