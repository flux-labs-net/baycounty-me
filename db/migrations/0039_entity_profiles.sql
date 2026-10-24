-- Entity profiles: one id and profile page for every company, official, candidate, nonprofit, board member, business,
-- committee and government on the site, and every documented connection between them (payments, campaign gifts from
-- organizations, votes on contracts, board seats, businesses, grants, shared projects). Built by site/page_datasets.py
-- from site/entity_graph.py, only from rows already in public datasets. Served by GET /api/v1/entities/{id}
-- (api/_entities.js), which adds hand-checked rows from the database-only datasets.
-- Same standard columns, public read policy and updated_at trigger as every other dataset table (see 0021_page_datasets.sql).

create table if not exists entity_profiles (
  id bigint generated always as identity primary key,
  "entity_id" text,
  "kind" text,
  "kind_label" text,
  "name" text,
  "subtitle" text,
  "page_url" text,
  "aliases" jsonb,
  "connections" bigint,
  "amount_received" numeric,
  "amount_given" numeric,
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
create index if not exists entity_profiles_gov_idx on entity_profiles (government_key);
create index if not exists entity_profiles_gov_id_idx on entity_profiles (gov_id);
create index if not exists entity_profiles_entity_id_idx on entity_profiles ("entity_id");
create index if not exists entity_profiles_kind_idx on entity_profiles ("kind");
create index if not exists entity_profiles_name_idx on entity_profiles (lower("name"));

insert into datasets (id, table_name, title, description) values ('entity-profiles', 'entity_profiles', $t$Profiles: people, companies and organizations$t$, $d$Every company, elected official, candidate, nonprofit, nonprofit board member, registered business, committee and government named in BayCounty.me records, one row each, with its profile page and how many documented connections it has. entity_id (kind:key) joins entity-connections.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table entity_profiles enable row level security;
drop policy if exists "public read" on entity_profiles;
create policy "public read" on entity_profiles for select using (true);

drop trigger if exists entity_profiles_touch on entity_profiles;
create trigger entity_profiles_touch before update on entity_profiles for each row execute function touch_updated_at();

create table if not exists entity_connections (
  id bigint generated always as identity primary key,
  "link_id" text,
  "from_id" text,
  "from_name" text,
  "from_kind" text,
  "from_url" text,
  "to_id" text,
  "to_name" text,
  "to_kind" text,
  "to_url" text,
  "relation" text,
  "relation_label" text,
  "amount" numeric,
  "records" bigint,
  "first_date" text,
  "last_date" text,
  "detail" text,
  "source_url" text,
  "county" text,
  gov_id text,
  government_key text references governments(key),
  origin text not null default 'manual',
  ingest_run_id bigint references ingest_runs(id),
  record_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (origin, record_hash)
);
create index if not exists entity_connections_gov_idx on entity_connections (government_key);
create index if not exists entity_connections_gov_id_idx on entity_connections (gov_id);
create index if not exists entity_connections_from_idx on entity_connections ("from_id");
create index if not exists entity_connections_to_idx on entity_connections ("to_id");

insert into datasets (id, table_name, title, description) values ('entity-connections', 'entity_connections', $t$Connections between people, companies and organizations$t$, $d$Every documented connection between two entities in entity-profiles, totalled per pair and kind: a government paid a payee, an organization gave to an official's or candidate's campaign, an official voted on a company's contracts, a person sits on a nonprofit's board or runs a business, a nonprofit gave a grant, two payees share a project. Each row has its source. Individual campaign donors are never included.$d$)
  on conflict (id) do update set title = excluded.title, description = excluded.description, updated_at = now();

alter table entity_connections enable row level security;
drop policy if exists "public read" on entity_connections;
create policy "public read" on entity_connections for select using (true);

drop trigger if exists entity_connections_touch on entity_connections;
create trigger entity_connections_touch before update on entity_connections for each row execute function touch_updated_at();
