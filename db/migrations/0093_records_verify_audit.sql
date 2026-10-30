-- Two-step intake and a locked audit trail (records submission).
--
--  1. Governments only SEND files. A sent file is checked against records BayCounty.me collects on its own (adopted
--     budgets, the state annual financial report, agenda approvals and votes, contracts, check numbers, published pay).
--     gov.verifications keeps every check with its result and the source it was checked against. A file that passes
--     every check publishes on its own; any mismatch, gap or record we can't confirm waits for the BayCounty.me admin.
--  2. gov.audit_log: an append-only, hash-chained record of everything that happens to a file or a workspace. Each row's
--     hash covers the row and the hash before it, so changing or removing any row breaks the chain
--     (gov.audit_chain_breaks() finds where). Rows can't be updated or deleted, not even by the service role.
--  3. Locks: activity rows, sent files and verification results can't be deleted, and a sent file's content (its hash,
--     name, rows, who sent it and when) can never change. Only its status moves forward.
-- Idempotent.

-- 1. Sent files gain a received status (sent by staff, waiting for our checks) and a held status (checked, waiting
--    for review).
alter table gov.submissions drop constraint if exists submissions_status_check;
alter table gov.submissions add constraint submissions_status_check
  check (status in ('preview', 'received', 'held', 'published', 'withdrawn'));
alter table gov.submissions add column if not exists sent_at timestamptz;
alter table gov.submissions add column if not exists sent_by text;

create table if not exists gov.verifications (
  file_id text primary key,                         -- 'c<submission id>' or 'f<finance upload id>'
  workspace_id text not null references gov.workspaces(id),
  kind text not null,
  file_sha256 text not null,
  status text not null check (status in ('verified', 'discrepancies', 'unverified')),
  checks jsonb not null default '[]',               -- [{check, status: match|mismatch|missing|unconfirmed, detail, expected, found, source_url}]
  counts jsonb not null default '{}',               -- {match, mismatch, missing, unconfirmed}
  checked_at timestamptz not null default now(),
  decision text check (decision in ('publish', 'hold')),
  decided_by text,
  decided_at timestamptz,
  note text
);
create index if not exists gov_verifications_ws on gov.verifications (workspace_id, checked_at desc);
create index if not exists gov_verifications_open on gov.verifications (status) where decision is null;
alter table gov.verifications enable row level security;

-- 2. The audit log.
create table if not exists gov.audit_log (
  id bigint generated always as identity primary key,
  at timestamptz not null default clock_timestamp(),
  actor text not null,
  action text not null,
  workspace_id text,
  subject text,                                     -- the file or record it is about ('c12', 'f9', a URL ...)
  file_sha256 text,
  source_url text,
  detail jsonb not null default '{}',
  prev_hash text not null,
  hash text not null unique
);
create index if not exists gov_audit_ws on gov.audit_log (workspace_id, id desc);
create index if not exists gov_audit_subject on gov.audit_log (subject, id);
alter table gov.audit_log enable row level security;

create or replace function gov.audit_payload(a gov.audit_log) returns text language sql immutable as $$
  select concat_ws('|', a.prev_hash, to_char(a.at at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'), a.actor, a.action,
    coalesce(a.workspace_id, ''), coalesce(a.subject, ''), coalesce(a.file_sha256, ''), coalesce(a.source_url, ''), a.detail::text)
$$;

-- Chain each new row to the one before it. One writer at a time, so the chain never forks.
create or replace function gov.audit_chain() returns trigger language plpgsql as $$
begin
  perform pg_advisory_xact_lock(hashtext('gov.audit_log'));
  new.at := clock_timestamp();
  new.prev_hash := coalesce((select hash from gov.audit_log order by id desc limit 1), repeat('0', 64));
  new.hash := encode(sha256(convert_to(gov.audit_payload(new), 'UTF8')), 'hex');
  return new;
end $$;
drop trigger if exists audit_chain on gov.audit_log;
create trigger audit_chain before insert on gov.audit_log for each row execute function gov.audit_chain();

create or replace function gov.no_change() returns trigger language plpgsql as $$
begin
  raise exception '% is locked: rows can''t be changed or deleted', tg_table_schema || '.' || tg_table_name;
end $$;
drop trigger if exists audit_locked on gov.audit_log;
create trigger audit_locked before update or delete on gov.audit_log for each row execute function gov.no_change();
drop trigger if exists audit_no_truncate on gov.audit_log;
create trigger audit_no_truncate before truncate on gov.audit_log execute function gov.no_change();

-- Ids of rows whose hash no longer matches (empty when the trail is intact).
create or replace function gov.audit_chain_breaks() returns table (id bigint, problem text) language sql stable as $$
  with c as (select a as r, a.id, a.hash, a.prev_hash, lag(a.hash) over (order by a.id) as before from gov.audit_log a)
  select c.id, case when c.prev_hash <> coalesce(c.before, repeat('0', 64)) then 'does not follow the row before it'
                    else 'row was changed' end
  from c
  where c.prev_hash <> coalesce(c.before, repeat('0', 64))
     or c.hash <> encode(sha256(convert_to(gov.audit_payload(c.r), 'UTF8')), 'hex')
$$;

create or replace function gov.audit(p_actor text, p_action text, p_workspace text, p_subject text, p_sha text, p_source text, p_detail jsonb)
returns void language sql as $$
  insert into gov.audit_log (actor, action, workspace_id, subject, file_sha256, source_url, detail, prev_hash, hash)
  values (coalesce(nullif(p_actor, ''), 'system'), p_action, p_workspace, p_subject, p_sha, p_source, coalesce(p_detail, '{}'), '', '')
$$;

-- Everything staff do (gov.activity) goes into the chain too.
create or replace function gov.activity_to_audit() returns trigger language plpgsql as $$
begin
  perform gov.audit(new.email, new.action, new.workspace_id, new.detail->>'file', null, new.detail->>'source_url', new.detail);
  return new;
end $$;
drop trigger if exists activity_audit on gov.activity;
create trigger activity_audit after insert on gov.activity for each row execute function gov.activity_to_audit();
drop trigger if exists activity_locked on gov.activity;
create trigger activity_locked before update or delete on gov.activity for each row execute function gov.no_change();

-- Sent files: every new file and every status change is recorded with the file's hash.
create or replace function gov.submission_audit() returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    perform gov.audit(new.submitted_by, 'file_received', new.workspace_id, 'c' || new.id, new.sha256, null,
      jsonb_build_object('kind', new.kind, 'name', new.original_name, 'rows', new.row_count, 'bytes', new.bytes, 'storage_path', new.storage_path));
  elsif new.status is distinct from old.status then
    perform gov.audit(coalesce(new.withdrawn_by, new.published_by, new.sent_by, 'system'), 'file_' || new.status, new.workspace_id, 'c' || new.id, new.sha256, null,
      jsonb_build_object('kind', new.kind, 'from', old.status, 'to', new.status));
  end if;
  return new;
end $$;
drop trigger if exists submission_audit on gov.submissions;
create trigger submission_audit after insert or update on gov.submissions for each row execute function gov.submission_audit();

create or replace function gov.submission_lock() returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' then raise exception 'gov.submissions is locked: sent files can''t be deleted'; end if;
  if new.sha256 is distinct from old.sha256 or new.original_name is distinct from old.original_name or new.rows is distinct from old.rows
     or new.storage_path is distinct from old.storage_path or new.submitted_by is distinct from old.submitted_by
     or new.submitted_at is distinct from old.submitted_at or new.kind is distinct from old.kind or new.workspace_id is distinct from old.workspace_id
     or new.row_count is distinct from old.row_count then
    raise exception 'gov.submissions is locked: a sent file''s content can''t change; send a new file instead';
  end if;
  return new;
end $$;
drop trigger if exists submission_lock on gov.submissions;
create trigger submission_lock before update or delete on gov.submissions for each row execute function gov.submission_lock();

-- Finance uploads (check registers and budget reports): recorded the same way; the file's hash and name never change.
create or replace function gov.upload_audit() returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    perform gov.audit(new.uploaded_by, 'file_received', new.workspace_id, 'f' || new.id, new.sha256, null,
      jsonb_build_object('shape', new.shape, 'name', new.original_name, 'storage_path', new.storage_path));
  elsif new.status is distinct from old.status or new.published_at is distinct from old.published_at then
    perform gov.audit(coalesce(new.published_by, new.uploaded_by, 'system'),
      case when new.published_at is distinct from old.published_at then (case when new.published_at is null then 'file_unpublished' else 'file_published' end)
           else 'file_' || new.status end,
      new.workspace_id, 'f' || new.id, new.sha256, null, jsonb_build_object('shape', new.shape, 'from', old.status, 'to', new.status));
  end if;
  return new;
end $$;
drop trigger if exists upload_audit on finance.uploads;
create trigger upload_audit after insert or update on finance.uploads for each row execute function gov.upload_audit();

create or replace function gov.upload_lock() returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' then raise exception 'finance.uploads is locked: files can''t be deleted'; end if;
  if new.sha256 is distinct from old.sha256 or new.original_name is distinct from old.original_name or new.storage_path is distinct from old.storage_path then
    raise exception 'finance.uploads is locked: a file''s hash, name and stored copy can''t change';
  end if;
  return new;
end $$;
drop trigger if exists upload_lock on finance.uploads;
create trigger upload_lock before update or delete on finance.uploads for each row execute function gov.upload_lock();

-- Verification results: written once per check run; only the admin's decision is added afterwards.
create or replace function gov.verification_lock() returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' then raise exception 'gov.verifications is locked: check results can''t be deleted'; end if;
  if new.checks is distinct from old.checks or new.status is distinct from old.status or new.file_sha256 is distinct from old.file_sha256
     or new.checked_at is distinct from old.checked_at or (old.decision is not null and new.decision is distinct from old.decision) then
    raise exception 'gov.verifications is locked: check results can''t change, and a decision is final';
  end if;
  return new;
end $$;
drop trigger if exists verification_lock on gov.verifications;
create trigger verification_lock before update or delete on gov.verifications for each row execute function gov.verification_lock();

create or replace function gov.verification_audit() returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    perform gov.audit('system', 'file_checked', new.workspace_id, new.file_id, new.file_sha256, null,
      jsonb_build_object('status', new.status, 'counts', new.counts, 'checks', new.checks));
  elsif new.decision is distinct from old.decision then
    perform gov.audit(new.decided_by, 'review_' || new.decision, new.workspace_id, new.file_id, new.file_sha256, null,
      jsonb_build_object('note', new.note));
  end if;
  return new;
end $$;
drop trigger if exists verification_audit on gov.verifications;
create trigger verification_audit after insert or update on gov.verifications for each row execute function gov.verification_audit();

-- 4. Email intake security. Each intake address accepts files only from the exact addresses on its allowed list
--    (no whole domains, and being a workspace member is not enough). The ingest-email function asks
--    ingest_sender_check first and, for anyone not on the list, opens nothing: someone writing from the
--    government's own domain gets one short reply a day saying who may send; anyone else is dropped unread.
--    Every accepted, refused or dropped email is written to the audit log (sender, address and reason only).
alter table ingest.sources add column if not exists gov_domain text;
update ingest.sources set gov_domain = coalesce(gov_domain, (select substr(a, 2) from unnest(allowed_senders) a where a like '@%' limit 1)),
  allowed_senders = array(select a from unnest(allowed_senders) a where a not like '@%')
where exists (select 1 from unnest(allowed_senders) a where a like '@%');
create or replace function ingest.exact_senders(a text[]) returns boolean language sql immutable as $$
  select coalesce(bool_and(x ~ '^[a-z0-9._%+''-]+@[a-z0-9.-]+\.[a-z]{2,}$'), true) from unnest(a) x
$$;
alter table ingest.sources drop constraint if exists sources_exact_senders;
alter table ingest.sources add constraint sources_exact_senders check (ingest.exact_senders(allowed_senders));

drop function if exists public.ingest_sender_is_staff(uuid, text);

-- One call before anything is opened: which source the address belongs to and whether this sender may send.
-- status: authorized | same_domain (writes from the government's domain but isn't on the list) | outside | unknown_address
create or replace function public.ingest_sender_check(p_to text, p_sender text)
returns table (source_id uuid, entity_name text, workspace_id text, status text, authorized text[], active boolean, auto_normalize boolean)
language sql stable security definer set search_path = '' as $$
  select s.id, s.entity_name, s.finance_workspace_id,
    case when lower(p_sender) = any(s.allowed_senders) then 'authorized'
         when s.gov_domain is not null and lower(p_sender) like '%@' || lower(s.gov_domain) then 'same_domain'
         else 'outside' end,
    s.allowed_senders, s.active, s.auto_normalize
  from ingest.sources s where lower(s.inbound_address) = lower(p_to) limit 1
$$;

-- Was a "who may send" reply already sent to this address in the last day? (Stops reply loops and floods.)
create or replace function public.ingest_notice_sent_recently(p_sender text)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from gov.audit_log where action = 'intake_notice_sent' and subject = lower(p_sender) and at > now() - interval '1 day')
$$;

create or replace function public.ingest_audit(p_actor text, p_action text, p_workspace text, p_subject text, p_sha text, p_detail jsonb)
returns void language sql security definer set search_path = '' as $$
  select gov.audit(p_actor, p_action, p_workspace, p_subject, p_sha, null, p_detail)
$$;

revoke all on function public.ingest_sender_check(text, text), public.ingest_notice_sent_recently(text),
  public.ingest_audit(text, text, text, text, text, jsonb) from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function public.ingest_sender_check(text, text), public.ingest_notice_sent_recently(text),
      public.ingest_audit(text, text, text, text, text, jsonb) to service_role;
  end if;
end $$;

-- 5. Email intake log: one row for every email that reaches an intake address, with its timestamps (sent, received by
--    the mail service, signed by the webhook, logged, finished), who it was from and to, the authentication result,
--    what we decided and why, and every attachment's name, size and SHA-256 with the import it became. Rows can't be
--    deleted; a row is finished once (finished_at set) and then never changes. Refused and dropped emails keep only the
--    envelope (from, to, times, reason): no subject and nothing from inside them. gov.intake_report() joins each email
--    to its audit-log events for the admin's downloadable report.
create table if not exists gov.intake_emails (
  id bigint generated always as identity primary key,
  email_id text unique,                             -- the mail service's id for the email
  message_id text,                                  -- the email's own Message-ID header
  sent_at timestamptz,                              -- Date header (the sender's clock)
  received_at timestamptz,                          -- when the mail service received it
  webhook_at timestamptz,                           -- the signed webhook timestamp
  logged_at timestamptz not null default clock_timestamp(),
  finished_at timestamptz,
  sender text not null,
  recipients text[] not null default '{}',
  intake_address text,
  source_id uuid,
  workspace_id text,
  subject text,                                     -- kept only for accepted email
  body_text text,                                   -- the email's text, kept only for accepted email
  decision text not null default 'received'
    check (decision in ('received', 'accepted', 'refused', 'dropped', 'unauthenticated', 'failed')),
  reason text,
  auth_results text,
  notice_sent boolean not null default false,
  notice_text text,                                 -- the "who may send" reply we sent, word for word
  attachments jsonb not null default '[]',          -- [{name, size, content_type, sha256, raw_id, duplicate, error, stored_at}]
  payload_sha256 text not null                      -- SHA-256 of the signed webhook body exactly as received
);
create index if not exists gov_intake_emails_at on gov.intake_emails (logged_at desc);
create index if not exists gov_intake_emails_ws on gov.intake_emails (workspace_id, logged_at desc);
alter table gov.intake_emails enable row level security;

create or replace function gov.intake_email_lock() returns trigger language plpgsql as $$
begin
  if tg_op = 'DELETE' then raise exception 'gov.intake_emails is locked: email records can''t be deleted'; end if;
  if old.finished_at is not null then raise exception 'gov.intake_emails is locked: a finished email record can''t change'; end if;
  if new.email_id is distinct from old.email_id or new.sender is distinct from old.sender or new.recipients is distinct from old.recipients
     or new.logged_at is distinct from old.logged_at or new.received_at is distinct from old.received_at or new.webhook_at is distinct from old.webhook_at
     or new.sent_at is distinct from old.sent_at or new.payload_sha256 is distinct from old.payload_sha256 or new.message_id is distinct from old.message_id then
    raise exception 'gov.intake_emails is locked: an email''s envelope and timestamps can''t change';
  end if;
  return new;
end $$;
drop trigger if exists intake_email_lock on gov.intake_emails;
create trigger intake_email_lock before update or delete on gov.intake_emails for each row execute function gov.intake_email_lock();

create or replace function gov.intake_email_audit() returns trigger language plpgsql as $$
begin
  if tg_op = 'INSERT' then
    perform gov.audit(new.sender, 'email_logged', new.workspace_id, new.email_id, new.payload_sha256, null,
      jsonb_build_object('to', new.recipients, 'received_at', new.received_at, 'webhook_at', new.webhook_at, 'sent_at', new.sent_at));
  elsif new.finished_at is not null and old.finished_at is null then
    perform gov.audit('system', 'email_finished', new.workspace_id, new.email_id, new.payload_sha256, null,
      jsonb_build_object('decision', new.decision, 'reason', new.reason, 'notice_sent', new.notice_sent,
        'files', (select coalesce(jsonb_agg(jsonb_build_object('name', a->>'name', 'sha256', a->>'sha256', 'raw_id', a->>'raw_id')), '[]')
                  from jsonb_array_elements(new.attachments) a)));
  end if;
  return new;
end $$;
drop trigger if exists intake_email_audit on gov.intake_emails;
create trigger intake_email_audit after insert or update on gov.intake_emails for each row execute function gov.intake_email_audit();

-- Called by ingest-email as soon as the webhook signature checks out, before anything else. A webhook sent twice
-- (the mail service retries) returns the first row's id with existing = true, so it's never handled twice.
create or replace function public.ingest_email_log(p jsonb)
returns table (id bigint, existing boolean) language plpgsql security definer set search_path = '' as $$
declare v bigint;
begin
  select e.id into v from gov.intake_emails e where e.email_id = p->>'email_id';
  if v is not null then return query select v, true; return; end if;
  insert into gov.intake_emails (email_id, message_id, sent_at, received_at, webhook_at, sender, recipients, payload_sha256)
  values (p->>'email_id', p->>'message_id', (p->>'sent_at')::timestamptz, (p->>'received_at')::timestamptz, (p->>'webhook_at')::timestamptz,
    lower(coalesce(p->>'sender', '')), coalesce(array(select lower(x) from jsonb_array_elements_text(p->'recipients') x), '{}'), p->>'payload_sha256')
  returning gov.intake_emails.id into v;
  return query select v, false;
end $$;

-- Finishes the row once: the decision, why, where it went and what was stored. Subject and text only when accepted.
create or replace function public.ingest_email_finish(p_id bigint, p jsonb)
returns void language sql security definer set search_path = '' as $$
  update gov.intake_emails set
    decision = p->>'decision', reason = p->>'reason', intake_address = p->>'intake_address',
    source_id = (p->>'source_id')::uuid, workspace_id = p->>'workspace_id',
    subject = case when p->>'decision' = 'accepted' then left(p->>'subject', 300) end,
    body_text = case when p->>'decision' = 'accepted' then left(p->>'body_text', 50000) end,
    auth_results = left(p->>'auth_results', 2000), notice_sent = coalesce((p->>'notice_sent')::boolean, false), notice_text = p->>'notice_text',
    attachments = coalesce(p->'attachments', '[]'), finished_at = clock_timestamp()
  where id = p_id and finished_at is null
$$;

-- The admin's report: every email in the window with its envelope, timestamps, decision, files and the audit-log
-- events about it or its files (each with the event's chain hash, so a printed report can be checked later).
create or replace function gov.intake_report(p_from timestamptz, p_to timestamptz, p_workspace text default null)
returns table (id bigint, email_id text, message_id text, sent_at timestamptz, received_at timestamptz, webhook_at timestamptz,
  logged_at timestamptz, finished_at timestamptz, sender text, recipients text[], intake_address text, workspace_id text,
  subject text, decision text, reason text, auth_results text, notice_sent boolean, attachments jsonb, payload_sha256 text, events jsonb)
language sql stable as $$
  select e.id, e.email_id, e.message_id, e.sent_at, e.received_at, e.webhook_at, e.logged_at, e.finished_at, e.sender, e.recipients,
    e.intake_address, e.workspace_id, e.subject, e.decision, e.reason, e.auth_results, e.notice_sent, e.attachments, e.payload_sha256,
    coalesce((select jsonb_agg(jsonb_build_object('id', a.id, 'at', a.at, 'actor', a.actor, 'action', a.action, 'subject', a.subject,
        'file_sha256', a.file_sha256, 'detail', a.detail, 'hash', a.hash) order by a.id)
      from gov.audit_log a
      where a.subject = e.email_id
         or (a.file_sha256 is not null and a.file_sha256 in (select x->>'sha256' from jsonb_array_elements(e.attachments) x where x->>'sha256' is not null))), '[]')
  from gov.intake_emails e
  where e.logged_at >= p_from and e.logged_at < p_to and (p_workspace is null or e.workspace_id = p_workspace)
  order by e.logged_at
$$;

revoke all on function public.ingest_email_log(jsonb), public.ingest_email_finish(bigint, jsonb) from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    grant execute on function public.ingest_email_log(jsonb), public.ingest_email_finish(bigint, jsonb) to service_role;
  end if;
end $$;
