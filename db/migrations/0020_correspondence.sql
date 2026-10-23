-- Correspondence with officials: the admin "Write to officials" and "Correspondence" tabs, and the public
-- /correspondence page. Each official gets their own copy of a message (never one email to a whole board), so
-- replies come only to hello@baycounty.me and no one can reply-all to other members (Florida Sunshine Law).
-- Admin-only tables: RLS is on with no public policy. The public page reads published threads through /api/v1,
-- which uses the server connection and returns only published rows.
create schema if not exists corr;

-- Who can be written to. Seeded from data/civic/official_contacts.json; edits in /admin are kept (origin = 'manual').
create table if not exists corr.contacts (
  id bigint generated always as identity primary key,
  government text not null,                    -- display name, e.g. "City of Lynn Haven"
  government_key text,                         -- short key used by the site (lh, pc, county ...), null if none
  seat text not null,                          -- "Ward 1", "Mayor", "City Manager"
  name text,
  email text,
  source_url text,                             -- where the address was published
  elected boolean not null default true,
  active boolean not null default true,
  notes text,
  origin text not null default 'file',         -- file (from the JSON) or manual (edited in /admin)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- Seat labels repeat ("Commissioner", "Council Member"), so a person is one government + seat + name.
-- When a seat changes hands, the old holder's row is turned off rather than overwritten.
create unique index if not exists contacts_person on corr.contacts (government, seat, coalesce(name, ''));

-- One compose: a subject and body sent to one or more officials. Each recipient gets their own thread.
create table if not exists corr.batches (
  id bigint generated always as identity primary key,
  subject text not null,
  body_text text not null,
  government text,                             -- set when every recipient is in one government
  recipient_count integer not null default 0,
  created_by text not null,
  created_at timestamptz not null default now()
);

-- One conversation with one official.
create table if not exists corr.threads (
  id bigint generated always as identity primary key,
  token text unique not null,                  -- in our Message-ID so replies can be matched
  batch_id bigint references corr.batches(id) on delete set null,
  contact_id bigint references corr.contacts(id) on delete set null,
  official_name text,                          -- copied at send time, so renaming a seat doesn't rewrite history
  official_seat text,
  government text,
  email text,
  subject text not null,
  status text not null default 'awaiting',     -- awaiting (no reply yet), replied, closed
  published boolean not null default false,
  published_at timestamptz,
  published_by text,
  created_at timestamptz not null default now(),
  last_at timestamptz not null default now()
);
create index if not exists threads_last on corr.threads (last_at desc);
create index if not exists threads_email on corr.threads (lower(email));

-- Every email in or out. thread_id is null for mail to hello@ that couldn't be matched to a thread.
create table if not exists corr.messages (
  id bigint generated always as identity primary key,
  thread_id bigint references corr.threads(id) on delete cascade,
  direction text not null check (direction in ('out', 'in')),
  from_addr text,
  to_addr text,
  cc jsonb not null default '[]',
  subject text,
  body_text text,
  body_html text,                              -- inbound only, never shown publicly
  message_id text,                             -- RFC 822 Message-ID
  in_reply_to text,
  resend_id text unique,                       -- sent email id or received email id
  status text not null default 'sent',         -- out: Resend's last event; in: received
  attachments jsonb not null default '[]',     -- [{filename, content_type, size}] (metadata only)
  matched_by text,                             -- in: header, token, address or null
  at timestamptz not null default now()
);
create index if not exists messages_thread on corr.messages (thread_id, at);
create index if not exists messages_unmatched on corr.messages (at desc) where thread_id is null;
create unique index if not exists messages_msgid on corr.messages (message_id) where message_id is not null;

alter table corr.contacts enable row level security;
alter table corr.batches enable row level security;
alter table corr.threads enable row level security;
alter table corr.messages enable row level security;
