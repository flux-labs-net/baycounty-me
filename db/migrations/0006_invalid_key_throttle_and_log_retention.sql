-- 1. Requests with a wrong API key now count against the caller's connection (IP hash), like keyless requests,
--    so guessing keys is throttled. Over the keyless limit they get 429; otherwise 401 invalid_key as before.
-- 2. The request log keeps 180 days: apiadmin.prune_requests() deletes older rows. It runs now and then from
--    check_request (the same place the counters and old IPs are cleaned up) and after every database sync (load.py).

create or replace function apiadmin.check_request(p_key_hash text, p_ip_hash text)
returns jsonb language plpgsql set search_path = '' as $$
declare
  s apiadmin.settings; k apiadmin.keys; subj text; lim_m integer; lim_d integer; used_m integer; used_d integer; bad_key boolean := false;
  day_start timestamptz := (date_trunc('day', now() at time zone 'America/Chicago')) at time zone 'America/Chicago';
begin
  select * into s from apiadmin.settings where id;
  if p_key_hash is not null then
    select * into k from apiadmin.keys where key_hash = p_key_hash;
    if not found then
      bad_key := true;
      subj := 'ip:' || coalesce(p_ip_hash, 'unknown'); lim_m := s.anon_per_minute; lim_d := s.anon_per_day;
    else
      if k.status <> 'active' then return jsonb_build_object('ok', false, 'status', 403, 'reason', 'key_' || k.status, 'key_id', k.id); end if;
      if k.expires_at is not null and k.expires_at < now() then return jsonb_build_object('ok', false, 'status', 403, 'reason', 'key_expired', 'key_id', k.id); end if;
      subj := 'key:' || k.id; lim_m := k.per_minute; lim_d := k.per_day;
      if k.last_used_at is null or k.last_used_at < now() - interval '1 minute' then
        update apiadmin.keys set last_used_at = now() where id = k.id;
      end if;
    end if;
  else
    if s.require_key then return jsonb_build_object('ok', false, 'status', 401, 'reason', 'key_required'); end if;
    subj := 'ip:' || coalesce(p_ip_hash, 'unknown'); lim_m := s.anon_per_minute; lim_d := s.anon_per_day;
  end if;
  insert into apiadmin.counters as c (subject, kind, window_start, count) values (subj, 'm', date_trunc('minute', now()), 1)
    on conflict (subject, kind, window_start) do update set count = c.count + 1 returning c.count into used_m;
  insert into apiadmin.counters as c (subject, kind, window_start, count) values (subj, 'd', day_start, 1)
    on conflict (subject, kind, window_start) do update set count = c.count + 1 returning c.count into used_d;
  if random() < 0.01 then delete from apiadmin.counters where window_start < now() - interval '3 days'; end if;
  if lim_m is not null and used_m > lim_m then
    return jsonb_build_object('ok', false, 'status', 429, 'reason', 'rate_limited', 'key_id', k.id, 'limit', lim_m, 'remaining', 0, 'retry_after', 60 - extract(second from now())::int);
  end if;
  if lim_d is not null and used_d > lim_d then
    return jsonb_build_object('ok', false, 'status', 429, 'reason', 'daily_quota', 'key_id', k.id, 'limit_day', lim_d, 'remaining_day', 0,
      'retry_after', extract(epoch from (day_start + interval '1 day' - now()))::int);
  end if;
  if bad_key then return jsonb_build_object('ok', false, 'status', 401, 'reason', 'invalid_key'); end if;
  return jsonb_build_object('ok', true, 'key_id', k.id, 'key_name', k.name, 'limit', lim_m, 'remaining', case when lim_m is null then null else lim_m - used_m end,
    'limit_day', lim_d, 'remaining_day', case when lim_d is null then null else lim_d - used_d end);
end $$;
revoke all on function apiadmin.check_request(text, text) from public;

-- Deletes request-log rows older than p_days (default 180). Returns how many were deleted.
create or replace function apiadmin.prune_requests(p_days integer default 180)
returns integer language plpgsql set search_path = '' as $$
declare n integer;
begin
  delete from apiadmin.requests where at < now() - make_interval(days => greatest(p_days, 1));
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function apiadmin.prune_requests(integer) from public;

-- Wrapper with the blocklist: same as 0005, plus an occasional 180-day prune of the request log.
create or replace function apiadmin.check_request(p_key_hash text, p_ip_hash text, p_ip text)
returns jsonb language plpgsql set search_path = '' as $$
declare b apiadmin.blocks; addr inet;
begin
  begin addr := p_ip::inet; exception when others then addr := null; end;
  if addr is not null then
    select * into b from apiadmin.blocks where addr <<= network and (expires_at is null or expires_at > now()) limit 1;
    if found then return jsonb_build_object('ok', false, 'status', 403, 'reason', 'blocked'); end if;
  end if;
  if random() < 0.005 then
    update apiadmin.requests set ip = null where ip is not null and at < now() - interval '90 days';
  end if;
  if random() < 0.001 then perform apiadmin.prune_requests(180); end if;
  return apiadmin.check_request(p_key_hash, p_ip_hash);
end $$;
revoke all on function apiadmin.check_request(text, text, text) from public;
