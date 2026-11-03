-- Email intake functions are for the ingest-email edge function only (it signs in with the service role).
-- 0093 revoked them from PUBLIC, but Supabase also grants EXECUTE straight to anon and authenticated on new
-- functions in the public schema, so anyone with the public API key could call them through /rest/v1/rpc and
-- write fake rows into the locked intake log and audit trail. Take those grants away; the service role keeps its own.
do $$ begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    revoke execute on function public.ingest_sender_check(text, text), public.ingest_notice_sent_recently(text),
      public.ingest_audit(text, text, text, text, text, jsonb), public.ingest_email_log(jsonb),
      public.ingest_email_finish(bigint, jsonb) from anon;
  end if;
  if exists (select 1 from pg_roles where rolname = 'authenticated') then
    revoke execute on function public.ingest_sender_check(text, text), public.ingest_notice_sent_recently(text),
      public.ingest_audit(text, text, text, text, text, jsonb), public.ingest_email_log(jsonb),
      public.ingest_email_finish(bigint, jsonb) from authenticated;
  end if;
end $$;
