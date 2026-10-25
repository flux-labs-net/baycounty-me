-- Public records requests (Chapter 119, Florida Statutes) drafted and tracked in the admin "Records requests" tab.
-- Drafts are seeded from data/civic/records_requests.json; nothing is sent until an admin presses Send. A sent request
-- becomes a corr.threads conversation, so the reply lands in Correspondence like any other.
-- Admin-only: RLS is on with no public policy, and the corr schema is closed to anon (0044).
create table if not exists corr.records_requests (
  id bigint generated always as identity primary key,
  key text unique not null,                    -- e.g. "budgets-2015-pcb": one draft per request in the seed file
  government text not null,                    -- display name, e.g. "City of Panama City Beach"
  government_key text,                         -- short site key (pc, pcb, schools ...)
  recipient_name text,                         -- "City Clerk" or a person
  recipient_email text,
  contact_url text,                            -- where the records contact was published, or a contact form
  subject text not null,
  body text not null,
  gaps jsonb not null default '[]',            -- [{fiscal_year, need}] what the request is for
  status text not null default 'draft' check (status in ('draft', 'sent', 'received', 'closed')),
  thread_id bigint references corr.threads(id) on delete set null,
  notes text,
  origin text not null default 'file',         -- file (follows the seed while still a draft) or manual (edited in /admin)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  sent_at timestamptz,
  sent_by text
);

alter table corr.records_requests enable row level security;
revoke all on corr.records_requests from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on corr.records_requests from anon, authenticated';
  end if;
end $$;
