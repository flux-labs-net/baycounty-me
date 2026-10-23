-- Agenda contents (data/agendas/extract_agendas.py). Each captured agenda version gets its text pulled out and read
-- by a Claude model into numbered items with dollar amounts, parties and addresses. One extraction per document
-- version; an amended agenda gets a new extraction. Admin-only, like the rest of the agendas schema.

create table if not exists agendas.extractions (
  id bigint generated always as identity primary key,
  document_id bigint not null references agendas.documents(id) on delete cascade,
  sha256 text not null,                       -- the version that was read
  status text not null,                       -- ok, no_text (scanned/image PDF), failed, skipped
  error text,
  model text,
  meeting_body text,                          -- as the agenda states it
  meeting_date date,
  meeting_time text,
  meeting_location text,
  item_count integer not null default 0,
  text_chars integer,
  text_truncated boolean not null default false,
  input_tokens integer,
  output_tokens integer,
  cost_usd numeric(10,4),                     -- estimate from the published per-token price
  text text,                                  -- the extracted text (for search and re-reading), capped
  extracted_at timestamptz not null default now(),
  ingest_run_id bigint references ingest_runs(id),
  unique (document_id, sha256)
);
create index if not exists extractions_doc on agendas.extractions (document_id, extracted_at desc);

create table if not exists agendas.items (
  id bigint generated always as identity primary key,
  extraction_id bigint not null references agendas.extractions(id) on delete cascade,
  document_id bigint not null references agendas.documents(id) on delete cascade,
  position integer not null,                  -- order on the agenda
  item_number text,                           -- as printed: "7.b", "IV.3"
  section text,                               -- "Consent Agenda", "Regular Agenda" ...
  title text not null,
  summary text,                               -- one plain-English sentence, from the agenda's own words
  kind text,                                  -- contract, purchase, change_order, budget, grant, rezoning, ...
  amounts jsonb not null default '[]',        -- [{amount: 123456.78, text: "$123,456.78"}]
  total_amount numeric(16,2),                 -- largest amount stated on the item
  parties jsonb not null default '[]',        -- vendors, applicants, agencies named
  addresses jsonb not null default '[]'       -- street addresses / parcels named
);
create index if not exists items_doc on agendas.items (document_id, position);
create index if not exists items_amount on agendas.items (total_amount desc) where total_amount is not null;

alter table agendas.extractions enable row level security;
alter table agendas.items enable row level security;
