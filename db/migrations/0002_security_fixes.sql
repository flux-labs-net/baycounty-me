-- Supabase security advisor fixes.
-- Pin the trigger function's search_path so it can't be redirected to another schema.
alter function public.touch_updated_at() set search_path = '';
-- rls_auto_enable() is Supabase's helper that turns on RLS for new tables. It shouldn't be callable through the public API.
do $$ begin
  if exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname = 'rls_auto_enable') then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end $$;
-- schema_migrations is internal bookkeeping: RLS on with no policy keeps it private, which is intended.
