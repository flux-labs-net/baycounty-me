-- Progress view fix: "captured" counted minutes files whose download failed (no stored copy yet). Count only stored
-- files, and add the failed downloads as their own column (new columns go last in a replaced view).
create or replace view public.minutes_progress as
with inv as (
  select board, year, listed, year_files, listed_at from agendas.minutes_inventory where year >= 2016
), docs as (
  select d.board, extract(year from d.meeting_date)::int as year, count(*) filter (where d.current_sha256 is not null)::int as captured,
         count(*) filter (where d.current_sha256 is null)::int as failed,
         count(r.id) filter (where r.status = 'ok')::int as read,
         count(r.id) filter (where r.status = 'submitted')::int as reading,
         count(r.id) filter (where r.status in ('failed', 'no_text'))::int as unreadable,
         count(r.id) filter (where r.status = 'ok' and r.read_at > now() - interval '7 days')::int as read_7d,
         coalesce(sum(r.ocr_pages) filter (where r.status = 'ok'), 0)::int as ocr_pages,
         coalesce(sum(r.pages) filter (where r.status = 'ok'), 0)::int as pages,
         max(r.read_at) as last_read_at, max(d.first_seen_at) as last_captured_at
    from agendas.documents d
    left join agendas.minutes_reads r on r.document_id = d.id and r.sha256 = d.current_sha256
   where d.kind = 'minutes' and d.meeting_date >= date '2016-01-01' and d.board is not null
   group by 1, 2
), mo as (
  select board, extract(year from meeting_date)::int as year, count(*)::int as motions,
         count(*) filter (where review_status <> 'rejected' and (check_status = 'passed' or review_status = 'approved'))::int as passed,
         count(*) filter (where check_status = 'flagged' and review_status = 'unreviewed')::int as flagged,
         count(*) filter (where check_status = 'flagged' and review_status <> 'unreviewed')::int as reviewed
    from agendas.motions where meeting_date >= date '2016-01-01'
   group by 1, 2
)
select coalesce(inv.board, docs.board, mo.board) as board, coalesce(inv.year, docs.year, mo.year) as year,
       inv.listed, coalesce(inv.year_files, 0) as year_files, inv.listed_at,
       coalesce(docs.captured, 0) as captured, coalesce(docs.read, 0) as read, coalesce(docs.reading, 0) as reading,
       coalesce(docs.unreadable, 0) as unreadable, coalesce(docs.read_7d, 0) as read_7d,
       coalesce(docs.pages, 0) as pages, coalesce(docs.ocr_pages, 0) as ocr_pages,
       docs.last_read_at, docs.last_captured_at,
       coalesce(mo.motions, 0) as motions, coalesce(mo.passed, 0) as passed, coalesce(mo.flagged, 0) as flagged,
       coalesce(mo.reviewed, 0) as reviewed, coalesce(docs.failed, 0) as failed
  from inv
  full join docs on docs.board = inv.board and docs.year = inv.year
  full join mo on mo.board = coalesce(inv.board, docs.board) and mo.year = coalesce(inv.year, docs.year);
grant select on public.minutes_progress to anon, authenticated;
