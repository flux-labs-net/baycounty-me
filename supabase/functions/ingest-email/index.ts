// ingest-email: Resend "email.received" webhook for <city>@ingest.baycounty.me. Verifies the Svix signature, picks the
// source from the To address, checks the sender against that source's allowed_senders (or the government's workspace
// members who may send records), then downloads each CSV or Excel
// attachment from Resend, stores it in the private ingest-raw bucket and logs it in ingest.raw (duplicates skipped).
// New files are then sent to the site's /finance importer (POST /api/finance?action=intake), which files them as unreviewed
// imports in the source's finance workspace; after that, if the source has auto_normalize on, they go to ingest-normalize
// (rows still need approval). Finance first, so budget and bank files are marked finance-only before normalizing.
// Deployed with verify_jwt off: the Svix signature is the authentication.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { Webhook } from "npm:svix@1";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const supabase = createClient(SUPABASE_URL, SERVICE_KEY);
const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY") ?? "";
const WEBHOOK_SECRET = Deno.env.get("RESEND_WEBHOOK_SECRET") ?? "";
const SITE_URL = (Deno.env.get("SITE_URL") ?? "https://baycounty.me").replace(/\/$/, "");

const json = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json" } });
const addr = (v: string) => (v.match(/<([^>]+)>/)?.[1] ?? v).trim().toLowerCase();

async function sha256(buf: ArrayBuffer) {
  const h = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function resend(path: string) {
  const r = await fetch(`https://api.resend.com${path}`, { headers: { Authorization: `Bearer ${RESEND_API_KEY}` } });
  if (!r.ok) throw new Error(`Resend ${path} ${r.status}`);
  return r.json();
}

async function toFinance(rawIds: string[]) {
  try {
    const r = await fetch(`${SITE_URL}/api/finance?action=intake`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${SERVICE_KEY}` },
      body: JSON.stringify({ raw_ids: rawIds }),
    });
    if (!r.ok) console.error("finance intake", r.status, await r.text()); // the daily sweep picks these up
  } catch (e) { console.error("finance intake", String(e)); }
}

async function autoNormalize(rawIds: string[]) {
  try {
    const r = await fetch(`${SUPABASE_URL}/functions/v1/ingest-normalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${SERVICE_KEY}`, apikey: SERVICE_KEY },
      body: JSON.stringify({ raw_ids: rawIds }),
    });
    if (!r.ok) console.error("auto-normalize", r.status, await r.text());
  } catch (e) { console.error("auto-normalize", String(e)); }
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
  const body = await req.text();

  let event: any;
  try {
    event = new Webhook(WEBHOOK_SECRET).verify(body, {
      "svix-id": req.headers.get("svix-id") ?? "",
      "svix-timestamp": req.headers.get("svix-timestamp") ?? "",
      "svix-signature": req.headers.get("svix-signature") ?? "",
    });
  } catch {
    return json({ error: "invalid signature" }, 401);
  }
  if (event.type !== "email.received") return json({ ignored: event.type });

  const d = event.data ?? {};
  const sender = addr(d.from ?? "");
  const toList: string[] = (Array.isArray(d.to) ? d.to : [d.to]).filter(Boolean).map(addr);

  let source: any = null;
  for (const to of toList) {
    const { data } = await supabase.rpc("ingest_lookup_source", { p_to: to });
    if (data?.length) { source = data[0]; break; }
  }
  if (!source || !source.active) return json({ rejected: "unknown address", to: toList });

  const allowed = (source.allowed_senders ?? []).map((s: string) => s.toLowerCase());
  let senderOk = allowed.includes(sender) || allowed.some((a: string) => a.startsWith("@") && sender.endsWith(a));
  // Anyone in the government's BayCounty.me workspace who may send records (migration 0091).
  if (!senderOk) {
    const { data: staff } = await supabase.rpc("ingest_sender_is_staff", { p_source_id: source.id, p_sender: sender });
    senderOk = staff === true;
  }
  if (!senderOk) {
    await supabase.rpc("ingest_register_raw", { p_source_id: source.id, p_sender: sender, p_file_name: null, p_file_hash: `rejected-${event.data?.email_id ?? crypto.randomUUID()}`, p_storage_path: null, p_payload: { subject: d.subject, to: toList }, p_status: "failed", p_error: "sender not allowed" });
    return json({ rejected: "sender not allowed" });
  }

  const emailId = d.email_id ?? d.id;
  let attachments: any[] = d.attachments ?? [];
  if (emailId) {
    try { const list = await resend(`/emails/receiving/${emailId}/attachments`); attachments = list.data ?? attachments; } catch (_) { /* fall back to event data */ }
  }
  // CSV and Excel (.xlsx): the /finance importer reads both. Only CSVs go on to the row normalizer.
  const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const isXlsx = (a: any) => /\.xlsx$/i.test(a.filename ?? "") || a.content_type === XLSX;
  const csvs = attachments.filter((a) => /\.csv$/i.test(a.filename ?? "") || /csv/i.test(a.content_type ?? "") || isXlsx(a));
  const results: any[] = [];

  for (const a of csvs) {
    try {
      const url = a.download_url ?? (await resend(`/emails/receiving/${emailId}/attachments/${a.id}`)).download_url;
      const buf = await (await fetch(url)).arrayBuffer();
      const hash = await sha256(buf);
      const path = `${source.id}/${new Date().toISOString().slice(0, 10)}/${hash}-${a.filename}`;
      await supabase.storage.from("ingest-raw").upload(path, buf, { contentType: isXlsx(a) ? XLSX : "text/csv", upsert: false });
      const { data: rawId } = await supabase.rpc("ingest_register_raw", { p_source_id: source.id, p_sender: sender, p_file_name: a.filename, p_file_hash: hash, p_storage_path: path, p_payload: { subject: d.subject, email_id: emailId } });
      results.push({ file: a.filename, raw_id: rawId, duplicate: !rawId, csv: !isXlsx(a) });
    } catch (e) {
      results.push({ file: a.filename, error: String(e) });
    }
  }

  const fresh = results.filter((r) => r.raw_id).map((r) => r.raw_id as string);
  const auto = !!source.auto_normalize && fresh.length > 0;
  if (fresh.length) {
    const freshCsv = results.filter((r) => r.raw_id && r.csv).map((r) => r.raw_id as string);
    const job = (async () => { await toFinance(fresh); if (auto && freshCsv.length) await autoNormalize(freshCsv); })();
    // Answer Resend right away; finish normalizing in the background where the runtime allows it.
    // deno-lint-ignore no-explicit-any
    const rt = (globalThis as any).EdgeRuntime;
    if (rt?.waitUntil) rt.waitUntil(job); else await job;
  }
  return json({ source: source.entity_name, files: results, auto_normalize: auto });
});
