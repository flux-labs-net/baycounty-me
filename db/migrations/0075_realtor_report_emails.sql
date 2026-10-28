-- Realtor console: reports an agent emailed from the console (api/_realtor.js action=email).
--
-- Private, like the rest of schema `realtor` (migration 0074). The email goes out from hello@baycounty.me with the
-- agent's name and Reply-To set to the agent, and the PDF attached. This table keeps only what the daily send limit
-- and the admin counts need: who sent, which report and how many people it went to. Recipient addresses and the
-- message are not stored.
create table if not exists realtor.report_emails (
  id bigint generated always as identity primary key,
  agent_id uuid not null references realtor.agents(id) on delete cascade,
  report_id bigint references realtor.reports(id) on delete set null,
  recipients smallint not null check (recipients between 1 and 10),
  resend_id text,
  sent_at timestamptz not null default now()
);
create index if not exists realtor_report_emails_agent_idx on realtor.report_emails (agent_id, sent_at desc);

alter table realtor.agents add column if not exists reports_emailed integer not null default 0;

alter table realtor.report_emails enable row level security;
