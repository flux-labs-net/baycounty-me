-- Votes read from meeting minutes (data/minutes/). Minutes files are captured into agendas.documents (kind
-- 'minutes') by the agenda watcher and the archive crawl; read_minutes.py pulls their text (OCR for scans), sends it
-- to a Claude model through the Message Batches API, and stores every motion with its roll call. match.py turns the
-- printed names into officeholders and checks the tally; motions that fail a check wait for review on /admin
-- ("Votes from minutes"). export_votes.py publishes passing and approved motions to data/votes/minutes_votes.json,
-- which feeds the votes and member-votes datasets. Admin-only, like the rest of the agendas schema.

-- One Message Batches API batch (up to a few hundred minutes files, split into chunks).
create table if not exists agendas.minutes_batches (
  id bigint generated always as identity primary key,
  batch_id text unique not null,              -- msgbatch_...
  model text not null,
  status text not null default 'in_progress', -- in_progress, ended, collected, failed
  requests integer not null default 0,
  est_cost_usd numeric(10,4),
  cost_usd numeric(10,4),
  submitted_at timestamptz not null default now(),
  ended_at timestamptz,
  collected_at timestamptz,
  error text
);

-- One read of one minutes file version.
create table if not exists agendas.minutes_reads (
  id bigint generated always as identity primary key,
  document_id bigint not null references agendas.documents(id) on delete cascade,
  sha256 text not null,
  status text not null default 'submitted',   -- submitted, ok, no_text, failed
  error text,
  attempts integer not null default 1,
  model text,
  batch_id text,
  chunks integer not null default 1,          -- requests the file was split into
  chunks_done integer not null default 0,
  results jsonb not null default '[]',        -- the model's answer per chunk, kept until every chunk is back
  pages integer,
  text_method text,                           -- text, ocr, mixed
  ocr_pages integer,
  text_chars integer,
  text text,                                  -- page-marked text, capped (for review and re-reading)
  meetings integer not null default 0,
  motion_count integer not null default 0,
  input_tokens integer,
  output_tokens integer,
  cost_usd numeric(10,4),                     -- batch price (half the per-token price)
  submitted_at timestamptz not null default now(),
  read_at timestamptz,
  ingest_run_id bigint references ingest_runs(id),
  unique (document_id, sha256)
);
create index if not exists minutes_reads_status on agendas.minutes_reads (status, submitted_at);
create index if not exists minutes_reads_batch on agendas.minutes_reads (batch_id);

-- Every motion, with what the minutes printed and what match.py made of it.
create table if not exists agendas.motions (
  id bigint generated always as identity primary key,
  read_id bigint not null references agendas.minutes_reads(id) on delete cascade,
  document_id bigint not null references agendas.documents(id) on delete cascade,
  board text not null,                        -- fetch_meetings board id: county, pc, pc-cra ...
  meeting_date date,
  meeting_type text,                          -- regular, special, workshop, budget_hearing, other
  position integer not null,                  -- order in the file
  item_number text,
  item_title text,
  motion text,                                -- the motion as printed (trimmed)
  summary text,                               -- one plain sentence
  kind text,                                  -- contract, purchase, budget, ordinance, appointment ...
  consent boolean not null default false,
  mover text,
  seconder text,
  outcome text,                               -- passed, failed, tabled, withdrawn, unclear
  tally_printed text,
  printed jsonb not null default '{}',        -- {yes: [...], no: [...], abstain: [...], absent: [...], unanimous: bool}
  amounts jsonb not null default '[]',
  amount numeric(16,2),                       -- largest amount in the motion
  ordinances jsonb not null default '[]',
  resolutions jsonb not null default '[]',
  parties jsonb not null default '[]',
  page integer,
  votes jsonb not null default '{}',          -- {officeholder name: yes|no|abstain|absent}
  vote_method text,                           -- roll_call, unanimous, no_dissent_recorded, outcome_only
  tally text,                                 -- from votes, e.g. 4-1
  unmatched jsonb not null default '[]',      -- printed names that matched no officeholder
  checks jsonb not null default '[]',         -- failed check codes; empty = passed
  check_status text not null,                 -- passed, flagged
  sampled boolean not null default false,     -- passing motion also picked for a spot check
  review_status text not null default 'unreviewed', -- unreviewed, approved, rejected
  review_note text,
  reviewed_by text,
  reviewed_at timestamptz,
  motion_key text not null,                   -- board|date|item|motion start: keeps a review when a file is re-read
  created_at timestamptz not null default now()
);
create index if not exists motions_read on agendas.motions (read_id, position);
create index if not exists motions_review on agendas.motions (check_status, review_status, meeting_date desc);
create index if not exists motions_board on agendas.motions (board, meeting_date desc);
create index if not exists motions_key on agendas.motions (motion_key);

alter table agendas.minutes_batches enable row level security;
alter table agendas.minutes_reads enable row level security;
alter table agendas.motions enable row level security;

-- The public votes datasets gain the minutes votes: where each row came from and how it was checked.
alter table votes add column if not exists source_type text;      -- researched | minutes
alter table votes add column if not exists verified text;         -- hand-checked | auto-checked | reviewed
alter table votes add column if not exists vote_method text;      -- roll_call, unanimous, no_dissent_recorded
alter table votes add column if not exists mover text;
alter table votes add column if not exists seconder text;
alter table votes add column if not exists source_page integer;
alter table member_votes add column if not exists source_type text;
alter table member_votes add column if not exists vote_id text;
create index if not exists votes_vote_id_idx on votes (vote_id);
create index if not exists member_votes_vote_id_idx on member_votes (vote_id);

update datasets set description = $d$Votes by the County Commission, School Board, city commissions and CRA boards since 2016, with how each member voted: hand-researched money votes plus every motion read from the official minutes.$d$, updated_at = now() where id = 'votes';

-- How many minutes files each archive lists, per board and year, written by every crawl (crawl_minutes.py, also
-- --inventory on its own). The progress dashboards compare it with what was captured and read.
create table if not exists agendas.minutes_inventory (
  board text not null,                        -- same board ids as agendas.documents
  year integer not null,
  listed integer not null default 0,          -- files the archive lists (0 = none posted online)
  year_files integer not null default 0,      -- of those, whole-year files holding many meetings (Parker 2016-17)
  sources text not null default '',           -- archive keys, comma list
  listed_at timestamptz not null default now(),
  primary key (board, year)
);
alter table agendas.minutes_inventory enable row level security;

-- Progress of the minutes backfill per board and year, counts only (no motion text, no names, no costs), for
-- /data-sources, GET /api/v1/import-progress and the /admin dashboard. A plain view runs with its owner's rights,
-- so the public can read these totals while the agendas tables stay admin-only.
create or replace view public.minutes_progress as
with inv as (
  select board, year, listed, year_files, listed_at from agendas.minutes_inventory where year >= 2016
), docs as (
  select d.board, extract(year from d.meeting_date)::int as year, count(*)::int as captured,
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
       coalesce(mo.reviewed, 0) as reviewed
  from inv
  full join docs on docs.board = inv.board and docs.year = inv.year
  full join mo on mo.board = coalesce(inv.board, docs.board) and mo.year = coalesce(inv.year, docs.year);
grant select on public.minutes_progress to anon, authenticated;
