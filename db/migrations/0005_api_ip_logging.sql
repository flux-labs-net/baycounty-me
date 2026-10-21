-- Store the caller's IP address on each API request (kept 90 days), and let admins block addresses or ranges.
alter table apiadmin.requests add column if not exists ip inet;
create index if not exists requests_ip_at_idx on apiadmin.requests (ip, at desc);

create table if not exists apiadmin.blocks (
  id bigint generated always as identity primary key,
  network cidr not null unique,          -- a single address (1.2.3.4/32) or a range
  reason text,
  expires_at timestamptz,                -- null = until removed
  created_by text,
  created_at timestamptz not null default now()
);
alter table apiadmin.blocks enable row level security;

-- Blocklist check in front of the key and throttle check.
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
  return apiadmin.check_request(p_key_hash, p_ip_hash);
end $$;
revoke all on function apiadmin.check_request(text, text, text) from public;
