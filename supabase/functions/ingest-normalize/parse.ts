// Pure CSV helpers for ingest-normalize (no network or env), so they can be unit tested.
import { parse } from "jsr:@std/csv@1";

// Pure: parse CSV text into records. Handles the file Excel writes when CSV text is pasted into one column and saved
// (every line wrapped in quotes as a single cell) by unwrapping once.
export function parseRecords(text: string): { records: Record<string, string>[]; headers: string[]; unwrapped: boolean } {
  text = text.replace(/^\uFEFF/, "");
  let rows = parse(text) as string[][];
  let unwrapped = false;
  if (rows.length && rows[0].length === 1 && rows[0][0].includes(",")) {
    rows = parse(rows.map((r) => r[0] ?? "").join("\n")) as string[][];
    unwrapped = true;
  }
  const headers = (rows[0] ?? []).map((h) => h.trim());
  const records = rows.slice(1).map((r) => Object.fromEntries(headers.map((h, i) => [h, (r[i] ?? "").trim()])));
  return { records, headers, unwrapped };
}

// Pure: mapped columns that the file doesn't have (matched without regard to case).
export function missingColumns(map: any, headers: string[]): string[] {
  const have = new Set(headers.map((h) => h.toLowerCase()));
  const out: string[] = [];
  for (const [field, spec] of Object.entries(map ?? {})) {
    const col = typeof spec === "string" ? spec : (spec as any)?.col;
    if (col && !have.has(String(col).toLowerCase())) out.push(`${col} (${field})`);
  }
  return out;
}
