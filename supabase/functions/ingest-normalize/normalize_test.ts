// Run: deno test supabase/functions/ingest-normalize/
import { assertEquals } from "jsr:@std/assert@1";
import { missingColumns, parseRecords } from "./parse.ts";

const MAP = { amount: "Amount", txn_date: { col: "Check Date", format: "MM/DD/YYYY" }, vendor_name: "Vendor" };

Deno.test("plain CSV with BOM and quoted commas", () => {
  const { records, headers, unwrapped } = parseRecords('﻿Vendor,Amount,Check Date\r\n"Carr, Riggs & Ingram, LLC",5330.00,10/14/2026\r\n');
  assertEquals(unwrapped, false);
  assertEquals(headers, ["Vendor", "Amount", "Check Date"]);
  assertEquals(records[0], { Vendor: "Carr, Riggs & Ingram, LLC", Amount: "5330.00", "Check Date": "10/14/2026" });
});

Deno.test("Excel single-column paste is unwrapped", () => {
  const text = '﻿"Vendor,Amount,Check Date"\r\n"Gulf Coast Paving LLC,24500.00,10/01/2026"\r\n"""Carr, Riggs & Ingram, LLC"",5330.00,10/14/2026"\r\n';
  const { records, headers, unwrapped } = parseRecords(text);
  assertEquals(unwrapped, true);
  assertEquals(headers, ["Vendor", "Amount", "Check Date"]);
  assertEquals(records.length, 2);
  assertEquals(records[1].Vendor, "Carr, Riggs & Ingram, LLC");
  assertEquals(records[1].Amount, "5330.00");
  assertEquals(missingColumns(MAP, headers), []);
});

Deno.test("missing columns are named, case-insensitive", () => {
  assertEquals(missingColumns(MAP, ["vendor", "AMOUNT"]), ["Check Date (txn_date)"]);
});
