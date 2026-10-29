-- Overlaps between datasets (/connections/overlaps, site/correlations.py): votes that name a company or organization,
-- votes on motions naming a member's donor, companies and organizations on agendas, development projects and the
-- businesses behind them, bids from notice to award, companies paid by one government that share an officer, chamber
-- board overlaps, emergency purchases and campaign gifts, and money raised next to votes won. Built by the site build
-- from data already published; individual donors are never named. Same standard columns, public read policy and
-- updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists vote_mentions (
  id bigint generated always as identity primary key,
  "place_id" text,
  "vote_id" text,
  "date" text,
  "board" text,
  "entity_id" text,
  "entity_name" text,
  "entity_kind" text,
  "entity_url" text,
  "matched_words" text,
  "headline" text,
  "agenda_item" text,
  "category" text,
  "amount" numeric,
  "outcome" text,
  "tally" text,
  "consent_agenda" boolean,
  "roll_call" text,
  "member_ids" text,
  "source_type" text,
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
create index if not exists vote_mentions_gov_idx on vote_mentions (government_key);
create index if not exists vote_mentions_1_idx on vote_mentions ("entity_id");
create index if not exists vote_mentions_2_idx on vote_mentions ("vote_id");

insert into datasets (id, table_name, title, description) values ('vote-mentions', 'vote_mentions', $t$Votes that name a company or organization$t$, $d$One row per recorded vote and each company, nonprofit or registered business its motion names, matched by name from the minutes (hand-researched votes and every vote read from minutes since 2016): the vote, the organization and its profile (entity_id), the words that matched, the roll call (roll_call, 'Name: vote' pairs) and the members' profile ids (member_ids). A match means the minutes name the organization in that motion; consent agendas name many items in one vote.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table vote_mentions enable row level security;
drop policy if exists "public read" on vote_mentions;
create policy "public read" on vote_mentions for select using (true);

drop trigger if exists vote_mentions_touch on vote_mentions;
create trigger vote_mentions_touch before update on vote_mentions for each row execute function touch_updated_at();

create table if not exists donor_votes (
  id bigint generated always as identity primary key,
  "place_id" text,
  "vote_id" text,
  "date" text,
  "board" text,
  "member" text,
  "member_id" text,
  "member_url" text,
  "member_vote" text,
  "donor" text,
  "donor_id" text,
  "donor_url" text,
  "donor_kind" text,
  "company" text,
  "company_id" text,
  "company_url" text,
  "gift_amount" numeric,
  "gift_first_date" text,
  "gift_last_date" text,
  "gift_timing" text,
  "headline" text,
  "amount" numeric,
  "outcome" text,
  "tally" text,
  "consent_agenda" boolean,
  "source_type" text,
  "source_url" text,
  "report_url" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists donor_votes_gov_idx on donor_votes (government_key);
create index if not exists donor_votes_1_idx on donor_votes ("member_id");
create index if not exists donor_votes_2_idx on donor_votes ("company_id");
create index if not exists donor_votes_3_idx on donor_votes ("donor_id");

insert into datasets (id, table_name, title, description) values ('donor-votes', 'donor_votes', $t$Votes on motions naming a member's donor$t$, $d$One row per member vote on a motion that names a company which gave to that member's campaign (donor_kind company) or whose owner gave personally (donor_kind business owner; owners are named only when their name and address match a Sunbiz officer, manager or registered agent). With the gift total, the first and last gift dates and whether the gifts came before or after the vote. A gift near a vote does not show why anyone voted the way they did. Individual donors are never named.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table donor_votes enable row level security;
drop policy if exists "public read" on donor_votes;
create policy "public read" on donor_votes for select using (true);

drop trigger if exists donor_votes_touch on donor_votes;
create trigger donor_votes_touch before update on donor_votes for each row execute function touch_updated_at();

create table if not exists agenda_parties (
  id bigint generated always as identity primary key,
  "place_id" text,
  "board" text,
  "meeting_date" text,
  "meeting" text,
  "item_number" text,
  "title" text,
  "kind" text,
  "rezoning" boolean,
  "amount" numeric,
  "party" text,
  "entity_id" text,
  "entity_name" text,
  "entity_kind" text,
  "entity_url" text,
  "gave_to_members" numeric,
  "gave_to" text,
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
create index if not exists agenda_parties_gov_idx on agenda_parties (government_key);
create index if not exists agenda_parties_1_idx on agenda_parties ("entity_id");

insert into datasets (id, table_name, title, description) values ('agenda-parties', 'agenda_parties', $t$Companies and organizations on agendas$t$, $d$One row per company, organization or government named on a board's agenda (agenda items read from the published agenda packets), linked to its profile where the name matches, with any campaign gifts from it (or from the owners who run it) to people who serve that government (gave_to_members, gave_to). rezoning is true for rezoning and land-use items.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table agenda_parties enable row level security;
drop policy if exists "public read" on agenda_parties;
create policy "public read" on agenda_parties for select using (true);

drop trigger if exists agenda_parties_touch on agenda_parties;
create trigger agenda_parties_touch before update on agenda_parties for each row execute function touch_updated_at();

create table if not exists development_companies (
  id bigint generated always as identity primary key,
  "place_id" text,
  "project_id" text,
  "project" text,
  "description" text,
  "status" text,
  "applied_date" text,
  "approved_date" text,
  "company" text,
  "company_id" text,
  "company_url" text,
  "sunbiz_doc_number" text,
  "match" text,
  "paid_by_this_government" numeric,
  "gave_to_members" numeric,
  "gave_to" text,
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
create index if not exists development_companies_gov_idx on development_companies (government_key);
create index if not exists development_companies_1_idx on development_companies ("company_id");

insert into datasets (id, table_name, title, description) values ('development-companies', 'development_companies', $t$Development projects and the businesses behind them$t$, $d$Development projects on the county and city planning maps whose name is exactly the name of one active Bay County business filing (Sunbiz), with that business's payments from the same government and campaign gifts from it or its owners to that government's officials. The maps don't list owners or developers, so only projects named after their business are matched.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table development_companies enable row level security;
drop policy if exists "public read" on development_companies;
create policy "public read" on development_companies for select using (true);

drop trigger if exists development_companies_touch on development_companies;
create trigger development_companies_touch before update on development_companies for each row execute function touch_updated_at();

create table if not exists bid_trail (
  id bigint generated always as identity primary key,
  "place_id" text,
  "notice_id" text,
  "reference" text,
  "agency" text,
  "published" text,
  "due_date" text,
  "notice_title" text,
  "notice_url" text,
  "stage" text,
  "date" text,
  "what" text,
  "vendor" text,
  "vendor_id" text,
  "amount" numeric,
  "outcome" text,
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
create index if not exists bid_trail_gov_idx on bid_trail (government_key);
create index if not exists bid_trail_1_idx on bid_trail ("notice_id");

insert into datasets (id, table_name, title, description) values ('bid-trail', 'bid_trail', $t$Bids from notice to award$t$, $d$Each bid or proposal request in the public notices, followed by its bid number to the recorded votes and contract records (awards, change orders, emergency purchases) at the same government that carry the same number: one row per step (stage notice, vote, award, change order), oldest notice last.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table bid_trail enable row level security;
drop policy if exists "public read" on bid_trail;
create policy "public read" on bid_trail for select using (true);

drop trigger if exists bid_trail_touch on bid_trail;
create trigger bid_trail_touch before update on bid_trail for each row execute function touch_updated_at();

create table if not exists shared_owner_vendors (
  id bigint generated always as identity primary key,
  "place_id" text,
  "group_id" text,
  "officer" text,
  "company" text,
  "company_id" text,
  "company_url" text,
  "sunbiz_doc_number" text,
  "paid_by_this_government" numeric,
  "companies_in_group" bigint,
  "match" text,
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
create index if not exists shared_owner_vendors_gov_idx on shared_owner_vendors (government_key);
create index if not exists shared_owner_vendors_1_idx on shared_owner_vendors ("company_id");
create index if not exists shared_owner_vendors_2_idx on shared_owner_vendors ("group_id");

insert into datasets (id, table_name, title, description) values ('shared-owner-vendors', 'shared_owner_vendors', $t$Companies paid by one government that share an officer$t$, $d$Companies paid by the same local government that list the same person (same name and Sunbiz address) as an officer or manager, one row per company, government and shared person. Registered agents are left out. Sharing an officer is common among related companies and is not a finding of wrongdoing.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table shared_owner_vendors enable row level security;
drop policy if exists "public read" on shared_owner_vendors;
create policy "public read" on shared_owner_vendors for select using (true);

drop trigger if exists shared_owner_vendors_touch on shared_owner_vendors;
create trigger shared_owner_vendors_touch before update on shared_owner_vendors for each row execute function touch_updated_at();

create table if not exists chamber_overlaps (
  id bigint generated always as identity primary key,
  "place_id" text,
  "chamber" text,
  "chamber_entity_id" text,
  "person" text,
  "person_id" text,
  "person_url" text,
  "title" text,
  "role_group" text,
  "year" bigint,
  "current" boolean,
  "organization" text,
  "organization_id" text,
  "organization_url" text,
  "is_official" boolean,
  "organization_paid_by_governments" numeric,
  "organization_gave_to_campaigns" numeric,
  "person_gave_to_campaigns" numeric,
  "gave_to" text,
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
create index if not exists chamber_overlaps_gov_idx on chamber_overlaps (government_key);
create index if not exists chamber_overlaps_1_idx on chamber_overlaps ("organization_id");
create index if not exists chamber_overlaps_2_idx on chamber_overlaps ("person_id");

insert into datasets (id, table_name, title, description) values ('chamber-overlaps', 'chamber_overlaps', $t$Chamber board members who are donors, vendors or officials$t$, $d$Chamber of commerce board members and staff (chamber-leaders) whose company is paid by a local government or gave to a local campaign, who gave to a campaign themselves as a business owner, or who are elected officials. Rows with none of these are left out.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table chamber_overlaps enable row level security;
drop policy if exists "public read" on chamber_overlaps;
create policy "public read" on chamber_overlaps for select using (true);

drop trigger if exists chamber_overlaps_touch on chamber_overlaps;
create trigger chamber_overlaps_touch before update on chamber_overlaps for each row execute function touch_updated_at();

create table if not exists emergency_purchase_donors (
  id bigint generated always as identity primary key,
  "place_id" text,
  "government" text,
  "vendor" text,
  "vendor_id" text,
  "vendor_url" text,
  "amount" numeric,
  "date" text,
  "purpose" text,
  "basis" text,
  "gave_to_officials_here" numeric,
  "gave_to" text,
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
create index if not exists emergency_purchase_donors_gov_idx on emergency_purchase_donors (government_key);
create index if not exists emergency_purchase_donors_1_idx on emergency_purchase_donors ("vendor_id");

insert into datasets (id, table_name, title, description) values ('emergency-purchase-donors', 'emergency_purchase_donors', $t$Emergency purchases and campaign gifts$t$, $d$Every emergency purchase (bought without the usual bidding), with campaign gifts from the company, or from the owners who run it, to people who serve the government that bought.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table emergency_purchase_donors enable row level security;
drop policy if exists "public read" on emergency_purchase_donors;
create policy "public read" on emergency_purchase_donors for select using (true);

drop trigger if exists emergency_purchase_donors_touch on emergency_purchase_donors;
create trigger emergency_purchase_donors_touch before update on emergency_purchase_donors for each row execute function touch_updated_at();

create table if not exists campaign_results (
  id bigint generated always as identity primary key,
  "place_id" text,
  "election_date" text,
  "election" text,
  "office" text,
  "contest" text,
  "candidate" text,
  "person_id" text,
  "outcome" text,
  "total_raised" numeric,
  "total_spent" numeric,
  "from_businesses" numeric,
  "from_individuals" numeric,
  "own_money" numeric,
  "votes" bigint,
  "vote_pct" numeric,
  "vote_rank" bigint,
  "money_rank" bigint,
  "candidates_with_reports" bigint,
  "cost_per_vote" numeric,
  "report_url" text,
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
create index if not exists campaign_results_gov_idx on campaign_results (government_key);
create index if not exists campaign_results_1_idx on campaign_results ("person_id");

insert into datasets (id, table_name, title, description) values ('campaign-results', 'campaign_results', $t$Money raised and votes won$t$, $d$Each local candidate since 2016 with a campaign report and an official result: money raised and spent, where it came from (individuals summed, never named), votes, vote share, rank in the race by votes and by money, and cost per vote (spent / votes). Joined on election date and candidate name.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table campaign_results enable row level security;
drop policy if exists "public read" on campaign_results;
create policy "public read" on campaign_results for select using (true);

drop trigger if exists campaign_results_touch on campaign_results;
create trigger campaign_results_touch before update on campaign_results for each row execute function touch_updated_at();

