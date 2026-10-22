-- Columns the Oct 21, 2026 data changes added to two datasets but no migration created.
alter table public.officials_pay add column if not exists row_type text;
alter table public.salary_positions add column if not exists fte_only boolean;
alter table public.salary_positions add column if not exists pay_status text;

-- The first sync after the entity-id change (Oct 22, 2026 00:23 UTC) saw every contract, change order and
-- member vote as new, because new id fields changed every row's record_hash, and queued 3,413 alert events
-- for records that were not new. None were processed (the alert run is daily at 13:40 UTC). Remove them.
-- load.py now decides "new" by each record's identity fields, not its hash, so this can't recur.
delete from alerts.events
 where processed_at is null
   and detected_at < timestamptz '2026-10-22 01:30:00+00';
