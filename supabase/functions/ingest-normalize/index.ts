// ingest-normalize: maps a raw accounting file (ingest.raw) into review rows (ingest.staging) using its source's column_map.
// Called by /admin (api/_ledger.js, "Normalize") and by ingest-email when a source has auto_normalize on.
// Deployed with verify_jwt off: the public anon key is also a valid JWT, so instead the caller must present a key that
// can run the service-role-only RPCs below. Body: {raw_id} or {all: true}.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";
import { missingColumns, parseRecords } from "./parse.ts";

const URL_ = Deno.env.get("SUPABASE_URL")!;
const sb = createClient(URL_, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);

const json = (b: unknown, s = 200) => new Response(JSON.stringify(b), { status: s, headers: { "Content-Type": "application/json" } });

// True only if the presented key can call a service-role-only function (works for legacy JWT and sb_secret_ keys).
async function isServiceKey(req: Request) {
  const bearer = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  const key = bearer || (req.headers.get("apikey") ?? "").trim();
  if (!key) return false;
  try {
    const probe = createClient(URL_, key, { auth: { persistSession: false } });
    const { error } = await probe.rpc("ingest_pending_raw", { p_limit: 1 });
    return !error;
  } catch { return false; }
}

async function sha256(t: string) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function parseDate(v: string, fmt?: string): string | null {
  if (!v) return null;
  v = v.trim();
  let m = v.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})$/);
  if (m && (!fmt || fmt.startsWith("MM"))) {
    let y = +m[3]; if (y < 100) y += 2000;
    return `${y}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
  }
  m = v.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  return null;
}

function parseAmount(v: string): number | null {
  if (v == null) return null;
  let s = String(v).trim();
  const neg = /^\(.*\)$/.test(s) || s.startsWith("-");
  s = s.replace(/[()$,\s-]/g, "");
  if (!s || isNaN(+s)) return null;
  return neg ? -+s : +s;
}

// Florida local government fiscal year: Oct 1 - Sep 30, named for the ending year
const fiscalYear = (iso: string) => { const [y, mo] = iso.split("-").map(Number); return mo >= 10 ? y + 1 : y; };

function pick(row: Record<string, string>, spec: any): string {
  if (!spec) return "";
  const col = typeof spec === "string" ? spec : spec.col;
  const key = col in row ? col : Object.keys(row).find((k) => k.toLowerCase() === String(col).toLowerCase());
  return (key ? row[key] ?? "" : "").toString().trim();
}

async function normalizeOne(rawId: string) {
  const { data: ctx, error } = await sb.rpc("ingest_normalize_context", { p_raw_id: rawId });
  if (error || !ctx) return { raw_id: rawId, ok: false, error: error?.message ?? "not found" };
  // New files, and failed ones being retried (e.g. after fixing the column map). Normalized files are never redone.
  if (!["received", "failed"].includes(ctx.status) || !ctx.storage_path) return { raw_id: rawId, ok: false, error: ctx.storage_path ? `already ${ctx.status}` : "no stored file (sender was rejected)" };
  const map = ctx.column_map;
  if (!map) { await sb.rpc("ingest_fail_raw", { p_raw_id: rawId, p_msg: "no column_map for source" }); return { raw_id: rawId, ok: false, error: "no column_map" }; }

  const { data: file, error: dlErr } = await sb.storage.from("ingest-raw").download(ctx.storage_path);
  if (dlErr || !file) return { raw_id: rawId, ok: false, error: dlErr?.message ?? "download failed" };
  const text = await file.text();

  let records: Record<string, string>[], headers: string[];
  try { ({ records, headers } = parseRecords(text)); }
  catch (e) { await sb.rpc("ingest_fail_raw", { p_raw_id: rawId, p_msg: `csv parse: ${e}` }); return { raw_id: rawId, ok: false, error: `csv parse: ${e}` }; }
  const missing = missingColumns(map, headers);
  if (missing.length) {
    const msg = `Columns not in this file: ${missing.join(", ")}. File has: ${headers.join(", ") || "(none)"}. Fix the export or the source's column map.`;
    await sb.rpc("ingest_fail_raw", { p_raw_id: rawId, p_msg: msg });
    return { raw_id: rawId, ok: false, error: msg };
  }

  const rows: any[] = []; const problems: string[] = []; const seen = new Map<string, number>();
  for (let i = 0; i < records.length; i++) {
    const r = records[i];
    if (Object.values(r).every((v) => !v || !String(v).trim())) continue;
    const amount = parseAmount(pick(r, map.amount));
    if (amount === null) { problems.push(`row ${i + 2}: bad amount`); continue; }
    const ds = map.txn_date ? parseDate(pick(r, map.txn_date), map.txn_date.format) : null;
    const out: any = {
      txn_date: ds, fiscal_year: ds ? fiscalYear(ds) : null,
      fund_code: pick(r, map.fund_code) || null, account_code: pick(r, map.account_code) || null,
      vendor_name: pick(r, map.vendor_name) || null, description: pick(r, map.description) || null,
      check_number: pick(r, map.check_number) || null, amount, source_row: r,
    };
    const base = [ds, out.fund_code, out.account_code, out.vendor_name, amount.toFixed(2), out.check_number, out.description].join("|");
    const n = (seen.get(base) ?? 0) + 1; seen.set(base, n);
    out.row_hash = await sha256(`${base}|${n}`);
    rows.push(out);
  }
  if (rows.length === 0) { await sb.rpc("ingest_fail_raw", { p_raw_id: rawId, p_msg: `no valid rows. ${problems.join("; ")}` }); return { raw_id: rawId, ok: false, error: "no valid rows", problems }; }

  const { data: res, error: stErr } = await sb.rpc("ingest_stage_rows", { p_raw_id: rawId, p_rows: rows });
  if (stErr) return { raw_id: rawId, ok: false, error: stErr.message };
  return { raw_id: rawId, ok: true, ...res, skipped: problems };
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  if (!(await isServiceKey(req))) return json({ error: "service role required" }, 401);
  const body = await req.json().catch(() => ({}));
  let ids: string[] = [];
  if (body.raw_id) ids = [String(body.raw_id)];
  else if (Array.isArray(body.raw_ids)) ids = body.raw_ids.map(String).slice(0, 20);
  else if (body.all) { const { data } = await sb.rpc("ingest_pending_raw", { p_limit: 20 }); ids = (data ?? []).map((x: any) => (typeof x === "string" ? x : Object.values(x)[0])); }
  else return json({ error: "pass raw_id or all:true" }, 400);
  const results = [];
  for (const id of ids) results.push(await normalizeOne(id));
  return json({ processed: results.length, results });
});
