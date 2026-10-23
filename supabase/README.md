# Supabase edge functions

Source for the edge functions deployed to the baycounty-me Supabase project. Deploy with the Supabase CLI
(`supabase functions deploy <name> --no-verify-jwt`) or the Supabase MCP. Both run with `verify_jwt` off and do their own auth.

| Function | Called by | Auth |
| --- | --- | --- |
| `ingest-email` | Resend webhook (`email.received`) for `*@ingest.baycounty.me` | Svix signature (`RESEND_WEBHOOK_SECRET`) |
| `ingest-normalize` | `/admin` Ingestion tab (`api/_ledger.js`), and `ingest-email` when a source has auto-normalize on | Caller's key must be able to run service-role-only RPCs |

Secrets (Supabase > Edge Functions > Secrets): `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`. Tables and RPCs: `db/migrations/0022_ledger_ingest.sql`.
