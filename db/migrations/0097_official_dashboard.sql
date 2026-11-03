-- Elected officials' dashboard (Jeremy, 2026-10-30: "commissioners ... login and see their dashboard with agendas and
-- clean pdf/reports of numbers/votes"). A commissioner or council member signs in to the government workspace (/staff)
-- with the same emailed code as staff and gets their own dashboard: upcoming agendas for their board, their voting
-- record and their government's numbers, each with a PDF report.
--
-- An official is a member of their government's workspace with role 'official', tied to their seat on record by
-- person_id (the officeholder-terms dataset's person_id, the same id as their /profile page). Officials read only:
-- like staff, they can flag a record that looks wrong but never change one (api/_gov.js). Everything they open or
-- download is logged in gov.activity.
-- Idempotent.

alter table gov.members drop constraint if exists members_role_check;
alter table gov.members add constraint members_role_check
  check (role in ('owner', 'alert_sender', 'publisher', 'records', 'viewer', 'auditor', 'official'));

-- The official's seat on record (officeholder_terms.person_id). Null for staff.
alter table gov.members add column if not exists person_id text;
create index if not exists gov_members_person on gov.members (person_id) where person_id is not null;
