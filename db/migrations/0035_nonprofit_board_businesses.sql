-- Nonprofit board members' businesses (data/nonprofits/build_nonprofits.py, dataset nonprofit-board-businesses): one row
-- per board member per Sunbiz business they appear on as an officer or registered agent, with that business's campaign
-- gifts. Public per the site owner (2026-10-24): Sunbiz officer lists and business campaign gifts are public records.
-- A name-only match is published only when one Sunbiz person in the county has that name.

create table if not exists nonprofit_board_businesses (
  id bigint generated always as identity primary key,
  "person_id" text,
  "person" text,
  "doc_number" text,
  "business" text,
  "business_status" text,
  "match" text,
  "campaign_gifts_total" numeric,
  "candidates" text,
  "county" text,
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
create index if not exists nonprofit_board_businesses_gov_idx on nonprofit_board_businesses (government_key);
create index if not exists nonprofit_board_businesses_gov_id_idx on nonprofit_board_businesses (gov_id);
create index if not exists nonprofit_board_businesses_person_id_idx on nonprofit_board_businesses ("person_id");
create index if not exists nonprofit_board_businesses_doc_idx on nonprofit_board_businesses ("doc_number");

insert into datasets (id, table_name, title, description) values ('nonprofit-board-businesses', 'nonprofit_board_businesses', $t$Nonprofits: board members' businesses$t$, $d$Businesses that local nonprofit board members run, from Florida corporate filings (Sunbiz officers and registered agents), with each business's gifts to local campaigns. match is "Name and address" when the person on the nonprofit's own state filing is the same Sunbiz person, or "Name" when only one Sunbiz person in the county has that name. person_id matches nonprofit-board-members.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table nonprofit_board_businesses enable row level security;
drop policy if exists "public read" on nonprofit_board_businesses;
create policy "public read" on nonprofit_board_businesses for select using (true);
drop trigger if exists nonprofit_board_businesses_touch on nonprofit_board_businesses;
create trigger nonprofit_board_businesses_touch before update on nonprofit_board_businesses for each row execute function touch_updated_at();
