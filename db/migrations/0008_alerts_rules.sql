-- 0008: meeting agenda items, and rule-based email alerts.

-- data/meetings/fetch_meetings.py now publishes every agenda item title (not just money items) as agenda_items.
alter table meetings add column if not exists "agenda_items" jsonb;
