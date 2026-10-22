-- Agenda watcher (data/agendas/watch_agendas.py). Notice emails (CivicPlus "Notify Me" and similar) arrive in a
-- mailbox polled over POP3; each one triggers a rescan of that government's agenda system, and every agenda,
-- packet and minutes file found is downloaded, hashed and stored. A changed hash is a new version (an amended
-- agenda). Admin-only: RLS is on with no public policy, so only the service role / DATABASE_URL can read it.
create schema if not exists agendas;

-- One row per email pulled from the inbox.
create table if not exists agendas.notices (
  id bigint generated always as identity primary key,
  uidl text,                                  -- POP3 unique id
  message_id text,
  received_at timestamptz,                    -- the email's Date header
  pulled_at timestamptz not null default now(),
  from_addr text,
  subject text,
  body_text text,                             -- plain text, trimmed to 20k chars
  links jsonb not null default '[]',          -- every URL in the email
  attachments jsonb not null default '[]',    -- [{filename, content_type, bytes, sha256, storage_path}]
  sources jsonb not null default '[]',        -- source keys the email triggered (pc, cw, lh ...)
  status text not null default 'new',         -- new, processed, unmatched, failed
  error text,
  ingest_run_id bigint references ingest_runs(id)
);
create unique index if not exists notices_uidl on agendas.notices (uidl) where uidl is not null;
create unique index if not exists notices_msgid on agendas.notices (message_id) where message_id is not null;

-- One row per document URL (agenda, packet, minutes, or a link straight from an email).
create table if not exists agendas.documents (
  id bigint generated always as identity primary key,
  url text unique not null,
  source_key text not null,                   -- pc, cw, lh, county, pcb, sp, parker, mb, email
  board text,
  government_key text,
  kind text not null,                         -- agenda, packet, minutes, linked, attachment
  title text,
  meeting_date date,
  first_seen_at timestamptz not null default now(),
  last_checked_at timestamptz,
  last_changed_at timestamptz,
  version_count integer not null default 0,
  current_sha256 text,
  content_type text,
  bytes bigint,
  status text not null default 'pending',     -- pending, new, updated, unchanged, failed
  error text,
  notice_id bigint references agendas.notices(id) on delete set null
);
create index if not exists documents_seen on agendas.documents (first_seen_at desc);
create index if not exists documents_board on agendas.documents (board, meeting_date desc);

-- Every distinct file content ever fetched for a document.
create table if not exists agendas.versions (
  id bigint generated always as identity primary key,
  document_id bigint not null references agendas.documents(id) on delete cascade,
  sha256 text not null,
  bytes bigint,
  content_type text,
  fetched_at timestamptz not null default now(),
  storage_path text,                          -- Supabase Storage path in the "agendas" bucket, null if not stored
  ingest_run_id bigint references ingest_runs(id),
  unique (document_id, sha256)
);

-- Problems during a run: mailbox, source scan, download, storage.
create table if not exists agendas.errors (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  stage text not null,                        -- inbox, parse, scan, download, store, notify
  source_key text,
  url text,
  message text not null,
  notice_id bigint references agendas.notices(id) on delete set null,
  document_id bigint references agendas.documents(id) on delete set null,
  ingest_run_id bigint references ingest_runs(id),
  resolved_at timestamptz
);
create index if not exists errors_open on agendas.errors (at desc) where resolved_at is null;

alter table agendas.notices enable row level security;
alter table agendas.documents enable row level security;
alter table agendas.versions enable row level security;
alter table agendas.errors enable row level security;
