-- Findings from the 2026-10-25 connections and pipelines audit.

-- raw_files holds a copy of every data/**/*.json file, including review files and samples that are not published
-- datasets. Nothing on the site, API or app reads it with the public key, so close it to the public.
drop policy if exists "public read" on raw_files;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke select on raw_files from anon, authenticated';
  end if;
end $$;

-- The old CRA network tables stopped syncing in 0026 (replaced by the connections-* datasets) but stayed publicly
-- readable with stale rows. Close them; the tables are kept so nothing is lost.
drop policy if exists "public read" on cra_network_payees;
drop policy if exists "public read" on cra_network_links;
drop policy if exists "public read" on cra_network_gifts;

-- The agenda inbox and correspondence schemas (residents' messages) get the same explicit lockout as registry.
revoke all on schema agendas from public;
revoke all on schema corr from public;
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on schema agendas from anon, authenticated';
    execute 'revoke all on schema corr from anon, authenticated';
  end if;
end $$;

-- budget_per_resident was the one dataset table without the updated_at trigger.
drop trigger if exists budget_per_resident_touch on budget_per_resident;
create trigger budget_per_resident_touch before update on budget_per_resident for each row execute function touch_updated_at();
