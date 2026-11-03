-- Public mail viewer (/correspondence): every email between BayCounty.me and officials or governments is public and
-- readable start to finish, read-only (Jeremy, 2026-10-30: "visible, viewable and readable online"). Sign-in codes
-- and links are never part of it. Residents' email addresses, phone numbers and street addresses are hidden when the
-- mail is shown (api/_redact.js); a resident's name or anything else the admin marks is hidden with corr.redactions.
--  1. Conversations are public by default. The admin can still take one down, but only with a reason, which is shown
--     in its place.
--  2. corr.redactions: words or phrases hidden on the public page, for one conversation or everywhere.
-- Admin-only tables (RLS on, no public policy): the public page reads through /api/v1/mail with the server connection.
-- Idempotent.

alter table corr.threads alter column published set default true;
alter table corr.threads add column if not exists hidden_reason text;
update corr.threads set published = true, published_at = coalesce(published_at, created_at), published_by = coalesce(published_by, 'automatic')
where not published and hidden_reason is null;

create table if not exists corr.redactions (
  id bigint generated always as identity primary key,
  thread_key text,                                  -- 'c<thread id>', 'e<intake email id>', 'm<message id>' or null for everywhere
  phrase text not null check (length(phrase) between 2 and 200),
  reason text,
  added_by text not null,
  added_at timestamptz not null default now()
);
create unique index if not exists redactions_one on corr.redactions (coalesce(thread_key, ''), lower(phrase));
alter table corr.redactions enable row level security;
