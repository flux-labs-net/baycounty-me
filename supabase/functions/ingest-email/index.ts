// ingest-email: Resend "email.received" webhook for <city>@ingest.baycounty.me. Verifies the Svix signature, then asks
// ingest_sender_check who the address belongs to and whether the sender is one of its exact allowed addresses
// (migration 0093). Anyone else gets nothing opened: a sender from the government's own domain gets one short reply a
// day naming who may send; mail from anywhere else is dropped unread. The sender's mail server must also pass
// DMARC (or an aligned SPF or DKIM check), so a forged From address is dropped too. Every decision goes in the
// audit log, and every email that reaches an intake address gets one locked row in gov.intake_emails (envelope, every
// timestamp, the decision and each file's SHA-256) for the admin's intake report. An accepted email then has each
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

// Never answer automated mail, lists or no-reply senders (no loops), and at most one reply a day per address.
async function mayReply(d: any, sender: string) {
  const h = Object.fromEntries(Object.entries(d.headers ?? {}).map(([k, v]) => [k.toLowerCase(), String(v)]));
  if (/^(auto-|bulk|list|junk)/i.test(h["auto-submitted"] ?? "") && !/^no$/i.test(h["auto-submitted"] ?? "")) return false;
  if (/bulk|list|junk/i.test(h["precedence"] ?? "") || h["list-id"]) return false;
  if (/^(no-?reply|mailer-daemon|postmaster)@/i.test(sender)) return false;
  const { data } = await supabase.rpc("ingest_notice_sent_recently", { p_sender: sender });
  return data !== true;
}

function noticeText(source: any) {
  const list = (source.authorized ?? []) as string[];
  const who = list.length ? list.map((a) => `  • ${a}`).join("\n") : "  (no one yet)";
  const text = `We didn't accept the email you sent to ${source.to}.\n\nOnly these addresses can send records for ${source.entity_name}:\n${who}\n\n` +
    `To be added, ask an owner of ${source.entity_name}'s BayCounty.me workspace. Nothing from your email was opened or kept.\n\nBayCounty.me`;
  return text;
}

async function notifyNotAuthorized(sender: string, source: any) {
  const text = noticeText(source);
  await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: "BayCounty.me <hello@baycounty.me>", to: [sender], subject: `Not accepted: records for ${source.entity_name}`, text,
      headers: { "Auto-Submitted": "auto-replied" } }),
  }).catch(() => {});
}

// The received email as the mail service has it (headers, text), fetched once.
const fetched = new Map<string, any>();
async function received(emailId: string | undefined) {
  if (!emailId) return {};
  if (!fetched.has(emailId)) { try { fetched.set(emailId, await resend(`/emails/receiving/${emailId}`)); } catch (_) { fetched.set(emailId, {}); } }
  return fetched.get(emailId);
}
const headerOf = (e: any, name: string) => Object.entries(e?.headers ?? {}).filter(([k]) => k.toLowerCase() === name)
  .map(([, v]) => (Array.isArray(v) ? v.join("; ") : String(v))).join("; ");

// The receiving server's Authentication-Results header for this email ("" when Resend doesn't give one).
async function authResults(emailId: string | undefined) {
  return headerOf(await received(emailId), "authentication-results");
}
const isoOrNull = (v: unknown) => { const t = v ? new Date(String(v)) : null; return t && !isNaN(+t) ? t.toISOString() : null; };

function authenticated(auth: string, sender: string) {
  const a = auth.toLowerCase(), dom = sender.split("@")[1] ?? "";
  if (!a || !dom) return false;
  if (/\bdmarc=pass\b/.test(a)) return true;
  const aligned = (d: string) => d === dom || d.endsWith("." + dom) || dom.endsWith("." + d);
  const dkim = [...a.matchAll(/dkim=pass[^;]*?header\.(?:d|i)=@?([a-z0-9.-]+)/g)].some((m) => aligned(m[1]));
  const spf = [...a.matchAll(/spf=pass[^;]*?smtp\.mailfrom=(?:[^@\s;]*@)?([a-z0-9.-]+)/g)].some((m) => aligned(m[1]));
  return dkim || spf;
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

  // Only mail to an intake address is ours; other webhooks handle the rest of the domain's mail.
  if (!toList.some((t) => t.endsWith("@ingest.baycounty.me"))) return json({ ignored: "not an intake address" });
  const emailId = d.email_id ?? d.id;
  const audit = (action: string, ws: string | null, detail: Record<string, unknown>) =>
    supabase.rpc("ingest_audit", { p_actor: sender || "unknown", p_action: action, p_workspace: ws, p_subject: emailId ?? null, p_sha: null, p_detail: { ...detail, to: toList } });

  // One locked row per email, written before anything else (a retried webhook finds the first row and stops).
  const svixTs = Number(req.headers.get("svix-timestamp") ?? "");
  const { data: logged } = await supabase.rpc("ingest_email_log", { p: {
    email_id: emailId ?? null, message_id: d.message_id ?? null, sent_at: isoOrNull(d.date ?? d.sent_at), received_at: isoOrNull(d.created_at ?? event.created_at),
    webhook_at: svixTs ? new Date(svixTs * 1000).toISOString() : null, sender, recipients: toList, payload_sha256: await sha256(new TextEncoder().encode(body).buffer as ArrayBuffer),
  } });
  const logRow = logged?.[0];
  if (logRow?.existing) return json({ duplicate: true });
  const finish = (p: Record<string, unknown>) => logRow ? supabase.rpc("ingest_email_finish", { p_id: logRow.id, p }) : Promise.resolve();

  let source: any = null;
  for (const to of toList) {
    const { data } = await supabase.rpc("ingest_sender_check", { p_to: to, p_sender: sender });
    if (data?.length) { source = { ...data[0], to }; break; }
  }
  if (!source || !source.active) {
    await audit("intake_dropped", null, { reason: "unknown address" });
    await finish({ decision: "dropped", reason: source ? "intake address turned off" : "unknown intake address" });
    return json({ dropped: "unknown address" });
  }
  const ws = source.workspace_id ?? null;

  if (source.status !== "authorized") {
    // Nothing from this email is opened, downloaded or kept.
    // Reply only when the From address is genuine, so a forged sender can't make us mail a government employee.
    let noticed = false;
    if (source.status === "same_domain" && authenticated(await authResults(emailId), sender) && await mayReply(d, sender)) {
      await notifyNotAuthorized(sender, source);
      noticed = true;
      await supabase.rpc("ingest_audit", { p_actor: "system", p_action: "intake_notice_sent", p_workspace: ws, p_subject: sender, p_sha: null, p_detail: { to: source.to } });
    }
    const reason = source.status === "same_domain" ? "not on the allowed list (government domain)" : "outside sender";
    await audit("intake_refused", ws, { reason });
    await finish({ decision: source.status === "same_domain" ? "refused" : "dropped", reason, intake_address: source.to, source_id: source.source_id,
      workspace_id: ws, notice_sent: noticed, notice_text: noticed ? noticeText(source) : null });
    return json({ dropped: "sender not allowed" });
  }

  // The From address must be genuine: the sending server has to pass DMARC, or SPF/DKIM for the sender's own domain.
  const auth = await authResults(emailId);
  if (!authenticated(auth, sender)) {
    await audit("intake_refused", ws, { reason: "sender could not be authenticated (SPF/DKIM/DMARC)", auth: auth.slice(0, 300) });
    await finish({ decision: "unauthenticated", reason: "sender could not be authenticated (SPF/DKIM/DMARC)", intake_address: source.to,
      source_id: source.source_id, workspace_id: ws, auth_results: auth });
    return json({ dropped: "unauthenticated" });
  }
  await audit("intake_accepted", ws, { source: source.entity_name });

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
      const path = `${source.source_id}/${new Date().toISOString().slice(0, 10)}/${hash}-${a.filename}`;
      await supabase.storage.from("ingest-raw").upload(path, buf, { contentType: isXlsx(a) ? XLSX : "text/csv", upsert: false });
      const { data: rawId } = await supabase.rpc("ingest_register_raw", { p_source_id: source.source_id, p_sender: sender, p_file_name: a.filename, p_file_hash: hash, p_storage_path: path, p_payload: { subject: d.subject, email_id: emailId } });
      results.push({ file: a.filename, raw_id: rawId, duplicate: !rawId, csv: !isXlsx(a), sha256: hash, size: buf.byteLength, content_type: a.content_type, stored_at: new Date().toISOString() });
    } catch (e) {
      results.push({ file: a.filename, error: String(e) });
    }
  }
  // Attachments we don't read (not CSV or Excel) are listed by name and size only.
  const skipped = attachments.filter((a) => !csvs.includes(a)).map((a) => ({ name: a.filename, size: a.size ?? null, content_type: a.content_type ?? null, skipped: "not a CSV or Excel file" }));
  const e = await received(emailId);
  await finish({ decision: "accepted", reason: "on the allowed list and authenticated", intake_address: source.to, source_id: source.source_id, workspace_id: ws,
    subject: d.subject ?? e.subject ?? "", auth_results: auth, body_text: String(e.text ?? d.text ?? "").slice(0, 50000),
    attachments: [...results.map((r) => ({ name: r.file, size: r.size ?? null, content_type: r.content_type ?? null, sha256: r.sha256 ?? null, raw_id: r.raw_id ?? null,
      duplicate: !!r.duplicate, error: r.error ?? null, stored_at: r.stored_at ?? null })), ...skipped] });

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
