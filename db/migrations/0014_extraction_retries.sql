-- Retry bookkeeping for agenda reading. A failed extraction is retried after a cooldown, up to 3 attempts.
alter table agendas.extractions add column if not exists attempts integer not null default 1;

-- The first run (Oct 23, 2026) failed every agenda on setup problems, not the agendas themselves: pdftotext wasn't
-- installed and the API key needed a workspace. Nothing was read or billed. Clear them so they're read again.
delete from agendas.extractions where status = 'failed' and extracted_at < timestamptz '2026-10-23 03:00:00+00';
