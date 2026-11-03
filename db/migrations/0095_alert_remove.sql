-- Admins can take an alert off the public pages (a test post, a mistake) without deleting it: the live row keeps who
-- removed it, when and why (api/_gov.js adminRemoveAlert, /admin > Emergency alerts), and every public reader skips
-- rows with removed_at set. A removed staff alert is marked 'removed' in gov.alerts so the next check doesn't send it
-- again.
alter table emergency_live add column if not exists removed_at timestamptz;
alter table emergency_live add column if not exists removed_by text;
alter table emergency_live add column if not exists removed_note text;

alter table gov.alerts drop constraint if exists alerts_status_check;
alter table gov.alerts add constraint alerts_status_check check (status in ('pending', 'sent', 'ended', 'cancelled', 'removed'));

-- How many phones, inboxes and texts each alert was sent to is for staff and admins only, not the public: the server
-- connection still reads and writes it (api/_emergency_feed.js timeline with admin, api/gov.js alerts).
drop policy if exists "public read" on emergency_reach;
