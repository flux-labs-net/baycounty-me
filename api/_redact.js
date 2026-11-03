// Hides residents' personal details in public mail (/correspondence, /api/v1/mail). Officials and government staff stay
// named: their mail about public business is a public record (Chapter 119, Florida Statutes). Hidden here:
//  * email addresses that aren't on a government domain (or baycounty.me)
//  * phone numbers and street addresses (we can't tell a home from an office reliably, so all are hidden)
//  * Social Security and card-like numbers
//  * any word or phrase the admin added to corr.redactions (a resident's name, for example)
const EMAIL = /\b[A-Z0-9._%+'-]+@([A-Z0-9-]+(?:\.[A-Z0-9-]+)*\.[A-Z]{2,})\b/gi;
const PHONE = /(?<![\w$])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}(?:\s*(?:x|ext\.?)\s*\d{1,5})?(?!\w)/gi;
const SSN = /\b\d{3}-\d{2}-\d{4}\b/g;
const CARD = /\b(?:\d[ -]?){13,16}\b/g;
const SUFFIX = 'St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Ct|Court|Cir|Circle|Way|Pl|Place|Pkwy|Parkway|Hwy|Highway|Trl|Trail|Ter|Terrace|Loop|Cv|Cove|Pt|Point';
const STREET = new RegExp(`\\b\\d{1,6}\\s+(?:[NSEW]\\.?\\s+)?(?:[A-Z0-9][A-Za-z0-9'.-]*\\s+){1,4}(?:${SUFFIX})\\b\\.?(?:\\s*(?:Apt|Unit|Suite|Ste|#)\\s*[\\w-]+)?`, 'g');

const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// govDomains: Set of lowercase domains whose addresses stay (city.gov, bay.k12.fl.us ...); phrases: strings to hide.
function redact(text, {govDomains = new Set(), phrases = []} = {}) {
  if (!text) return text || '';
  const isGov = d => { d = d.toLowerCase(); for (const g of govDomains) if (d === g || d.endsWith('.' + g)) return true; return false; };
  let s = String(text);
  for (const p of phrases.filter(Boolean).sort((a, b) => b.length - a.length)) s = s.replace(new RegExp(esc(p), 'gi'), '[name hidden]');
  s = s.replace(EMAIL, (m, d) => (isGov(d) ? m : '[email hidden]'));
  s = s.replace(SSN, '[number hidden]').replace(CARD, m => (m.replace(/\D/g, '').length >= 13 ? '[number hidden]' : m));
  s = s.replace(PHONE, '[phone hidden]');
  s = s.replace(STREET, '[address hidden]');
  return s;
}

// A sender or recipient address as shown publicly: government addresses as they are, anyone else hidden.
function shownAddress(addr, govDomains) {
  const a = String(addr || '').toLowerCase().trim();
  const d = a.split('@')[1] || '';
  for (const g of govDomains) if (d === g || d.endsWith('.' + g)) return a;
  return null;
}

module.exports = {redact, shownAddress};
