"""Show dates the US way in page text: 2025-02-10 -> Feb 10, 2025; 2026-10-27 17:30 -> Oct 27, 2026, 5:30 PM;
9/30/2024 -> Sep 30, 2024. Spanish pages (/es/...) get 10 feb 2025.

Applied to every built page (server side) and, through DATES_JS, to text that page scripts fill in later. Only text
outside tags changes; attributes (data-d, href, datetime), code samples, inputs and scripts keep ISO dates, so sorting,
filters and links are unaffected. Two-digit years (10/20/26 in an agenda title) are left as written.
"""
import re

EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic']
SKIP = {'script', 'style', 'textarea', 'title', 'head', 'option', 'svg', 'code', 'pre'}
# not part of a longer token: a URL piece, a file name, a document number like 2020-01204
ISO = re.compile(r'(?<![\w/.-])((?:19|20)\d\d)-(\d\d)-(\d\d)(?:[ T](\d\d):(\d\d)(?::\d\d)?)?(?![\w/-])')
MDY = re.compile(r'(?<![\w/.-])(\d{1,2})/(\d{1,2})/((?:19|20)\d\d)(?![\w/-])')


def _fmt(y, m, d, hh=None, mm=None, es=False):
    y, m, d = int(y), int(m), int(d)
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    s = f'{d} {ES[m - 1]} {y}' if es else f'{EN[m - 1]} {d}, {y}'
    if hh is not None and not (int(hh) == 0 and int(mm) == 0):  # a bare midnight timestamp is just a date
        h, mi = int(hh), int(mm)
        if es:
            s += f', {h}:{mi:02d}'
        else:
            s += f', {(h % 12) or 12}:{mi:02d} {"AM" if h < 12 else "PM"}'
    return s


def us_dates(text, es=False):
    text = ISO.sub(lambda m: _fmt(m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), es) or m.group(0), text)
    return MDY.sub(lambda m: _fmt(m.group(3), m.group(1), m.group(2), es=es) or m.group(0), text)


def us_dates_html(doc, es=False):
    out, depth = [], {k: 0 for k in SKIP}
    for part in re.split(r'(<[^>]+>)', doc):
        if part.startswith('<'):
            m = re.match(r'<\s*(/?)\s*([a-zA-Z0-9]+)', part)
            if m:
                tag = m.group(2).lower()
                if tag in SKIP and not part.endswith('/>'):
                    depth[tag] = max(0, depth[tag] + (-1 if m.group(1) else 1))
            out.append(part)
        elif part and not any(depth.values()) and ('-' in part or '/' in part):
            out.append(us_dates(part, es))
        else:
            out.append(part)
    return ''.join(out)


DATES_JS = r"""
// A clear flag for a business the state lists as inactive (dissolved, revoked or no longer filing). Active returns ''.
window.BCM_bizOff = (status, lastYear) => {
  const s = String(status || '').trim();
  if (!s || /^(a|active)$/i.test(s)) return '';
  const tip = 'Inactive in Florida corporate records (Sunbiz): dissolved, revoked or no longer filing annual reports' + (lastYear ? `. Last filed ${lastYear}.` : '.');
  return `<span class="biz-off" title="${tip}">Inactive${lastYear ? ' since ' + lastYear : ''}</span>`;
};
(() => {
  const ES = (document.documentElement.lang || '').startsWith('es');
  const EN_M = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], ES_M = ['ene','feb','mar','abr','may','jun','jul','ago','sept','oct','nov','dic'];
  const SKIP = new Set(['SCRIPT','STYLE','TEXTAREA','TITLE','OPTION','INPUT','SELECT','CODE','PRE']);
  const ISO = /(^|[^\w\/.-])((?:19|20)\d\d)-(\d\d)-(\d\d)(?:[ T](\d\d):(\d\d)(?::\d\d)?)?(?![\w\/-])/g;
  const MDY = /(^|[^\w\/.-])(\d{1,2})\/(\d{1,2})\/((?:19|20)\d\d)(?![\w\/-])/g;
  function fmt(y, m, d, hh, mm) {
    y = +y; m = +m; d = +d;
    if (!(m >= 1 && m <= 12 && d >= 1 && d <= 31)) return null;
    let s = ES ? `${d} ${ES_M[m - 1]} ${y}` : `${EN_M[m - 1]} ${d}, ${y}`;
    if (hh != null && !(+hh === 0 && +mm === 0)) { const h = +hh; s += ES ? `, ${h}:${mm}` : `, ${(h % 12) || 12}:${mm} ${h < 12 ? 'AM' : 'PM'}`; }
    return s;
  }
  const usDate = window.BCM_usDate = t => String(t ?? '').replace(ISO, (all, pre, y, m, d, hh, mm) => { const f = fmt(y, m, d, hh, mm); return f ? pre + f : all; })
    .replace(MDY, (all, pre, m, d, y) => { const f = fmt(y, m, d); return f ? pre + f : all; });
  function walk(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: n => { for (let p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || p.nodeName === 'svg' || p.isContentEditable) return NodeFilter.FILTER_REJECT; return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode);
    list.forEach(n => { const t = n.nodeValue; if (t && /\d[-\/]\d/.test(t)) { const u = usDate(t); if (u !== t) n.nodeValue = u; } });
  }
  const main = document.getElementById('main'); if (!main) return;
  walk(main);
  let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => walk(main), 60); }).observe(main, {childList: true, subtree: true});
})();
"""
