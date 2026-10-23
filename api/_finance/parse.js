// Turns an uploaded file (CSV, TSV or Excel) into a grid of cells and finds the header row.
// Pure functions except parseXlsx, which uses exceljs. No network or database access.

// RFC 4180 CSV with quoted fields, doubled quotes and embedded newlines. The delimiter is guessed from the first lines.
function sniffDelimiter(text) {
  const head = text.split(/\r?\n/).slice(0, 10).join('\n');
  let best = ',', bestN = -1;
  for (const d of [',', '\t', ';', '|']) {
    const n = head.split(d).length - 1;
    if (n > bestN) { best = d; bestN = n; }
  }
  return best;
}

function parseCsv(text, delimiter) {
  text = String(text).replace(/^﻿/, '');
  const d = delimiter || sniffDelimiter(text);
  const rows = [];
  let row = [], cell = '', inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') {
        if (text[i + 1] === '"') { cell += '"'; i++; } else inQ = false;
      } else cell += c;
    } else if (c === '"' && cell === '') inQ = true;
    else if (c === d) { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); rows.push(row); row = []; cell = '';
    } else cell += c;
  }
  if (cell !== '' || row.length) { row.push(cell); rows.push(row); }
  return rows.map(r => r.map(v => v.trim())).filter(r => r.some(v => v !== ''));
}

// Excel: every sheet is read; the one with the most non-empty rows wins. Dates come back as Date objects,
// formulas as their cached result, rich text as plain text.
function cellValue(v) {
  if (v === null || v === undefined) return '';
  if (v instanceof Date) return v;
  if (typeof v === 'object') {
    if ('result' in v) return cellValue(v.result);
    if (Array.isArray(v.richText)) return v.richText.map(t => t.text).join('');
    if ('text' in v) return String(v.text);
    if ('error' in v) return '';
    return '';
  }
  return v;
}

async function parseXlsx(buffer) {
  const ExcelJS = require('exceljs');
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.load(buffer);
  let best = {name: null, rows: []};
  for (const ws of wb.worksheets) {
    const rows = [];
    ws.eachRow({includeEmpty: false}, r => {
      const vals = r.values.slice(1).map(cellValue).map(v => (typeof v === 'string' ? v.trim() : v));
      if (vals.some(v => v !== '' && v !== null && v !== undefined)) rows.push(vals);
    });
    if (rows.length > best.rows.length) best = {name: ws.name, rows};
  }
  return best;
}

const isXlsx = (name, buf) => /\.xlsx$/i.test(name || '') || (buf && buf[0] === 0x50 && buf[1] === 0x4b);
const isLegacyXls = (name, buf) => /\.xls$/i.test(name || '') || (buf && buf[0] === 0xd0 && buf[1] === 0xcf);

// Returns {sheet, rows} where rows is an array of arrays of cell values (strings, numbers, Dates).
async function readGrid(name, buffer) {
  if (isLegacyXls(name, buffer)) {
    throw Object.assign(new Error('Old .xls files can’t be read. Open it in Excel and save as .xlsx or .csv.'), {status: 415});
  }
  if (/\.pdf$/i.test(name || '') || (buffer && buffer.slice(0, 4).toString() === '%PDF')) {
    throw Object.assign(new Error('PDF uploads aren’t supported yet. Export the report as Excel or CSV from the accounting system.'), {status: 415});
  }
  if (isXlsx(name, buffer)) return parseXlsx(buffer);
  return {sheet: null, rows: parseCsv(buffer.toString('utf8'))};
}

module.exports = {parseCsv, sniffDelimiter, readGrid, cellValue};
