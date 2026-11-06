-- Planning and zoning boards (site/planning_boards.py): each government's appointed planning board and board of
-- adjustment, and who sits on them. planning-boards has one row per board (what it decides, who appoints it, next and
-- last meeting from the meetings dataset, same board ids); planning-board-members one row per member (from the city's
-- own board page, or the roll call in the board's latest posted minutes). Shown in the "Planning and zoning board"
-- section of each government page and on members' profiles. Same standard columns, public read policy and updated_at
-- trigger as 0021_page_datasets.sql.

create table if not exists planning_boards (
  id bigint generated always as identity primary key,
  "board_id" text,
  "name" text,
  "kind" text,
  "also" text,
  "what_it_does" text,
  "recommends_to" text,
  "appointed_by" text,
  "seats" bigint,
  "alternates" bigint,
  "term_years" bigint,
  "members_listed" bigint,
  "roster_as_of" date,
  "roster_source" text,
  "roster_source_url" text,
  "roster_note" text,
  "records_online" text,
  "next_meeting" text,
  "next_meeting_status" text,
  "next_agenda_url" text,
  "last_meeting" text,
  "last_agenda_url" text,
  "last_minutes_url" text,
  "page_url" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists planning_boards_gov_idx on planning_boards (government_key);
create index if not exists planning_boards_gov_id_idx on planning_boards (gov_id);
create index if not exists planning_boards_board_idx on planning_boards ("board_id");

insert into datasets (id, table_name, title, description) values ('planning-boards', 'planning_boards', $t$Planning and zoning boards$t$, $d$Each government's appointed planning board and board of adjustment: what it decides, who it recommends to, who appoints it, seats and terms, how many members are listed and from what record, the next and last meeting (board_id matches meetings.board) and what records the government posts online.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table planning_boards enable row level security;
drop policy if exists "public read" on planning_boards;
create policy "public read" on planning_boards for select using (true);

drop trigger if exists planning_boards_touch on planning_boards;
create trigger planning_boards_touch before update on planning_boards for each row execute function touch_updated_at();

create table if not exists planning_board_members (
  id bigint generated always as identity primary key,
  "board_id" text,
  "board" text,
  "sort_order" bigint,
  "name" text,
  "role" text,
  "seat" text,
  "term_end" date,
  "appointed_by" text,
  "person_entity_id" text,
  "person_url" text,
  "person_match" text,
  "as_of" date,
  "source_title" text,
  "source_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists planning_board_members_gov_idx on planning_board_members (government_key);
create index if not exists planning_board_members_gov_id_idx on planning_board_members (gov_id);
create index if not exists planning_board_members_board_idx on planning_board_members ("board_id");
create index if not exists planning_board_members_entity_idx on planning_board_members ("person_entity_id");

insert into datasets (id, table_name, title, description) values ('planning-board-members', 'planning_board_members', $t$Planning and zoning board members$t$, $d$Who sits on each planning and zoning board: name, role, seat and term end where the city lists them, and who appoints the board. Public appointees, named as the government publishes them; no addresses, phone numbers or emails. From the city's own board page or the roll call in the board's latest posted minutes (as_of).$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table planning_board_members enable row level security;
drop policy if exists "public read" on planning_board_members;
create policy "public read" on planning_board_members for select using (true);

drop trigger if exists planning_board_members_touch on planning_board_members;
create trigger planning_board_members_touch before update on planning_board_members for each row execute function touch_updated_at();
