"""Turn bare source URLs and internal data-file names in page text into real links.

Applied to every built page (server side) and, through LINKIFY_JS, to text that page scripts fill in later.
Only text outside tags is touched; nothing inside <a>, <script>, <style>, <textarea>, <title> or attributes changes.
"""
import html as H
import re

URL = re.compile(r'https?://[^\s<>"\']+')
TRAIL = '.,;:!?)]}\'"'
# internal file names researchers wrote into notes -> the page a reader can open
PATHS = [
    (r'data/contracts/contracts\.json', '/public-money/contracts', 'the Contracts page'),
    (r'data/tax/budgets\.json', '/public-money/tax-dollars', 'the Tax Dollars page'),
    (r'data/votes/votes\.json', '/public-money/votes', 'the How They Voted page'),
    (r'data/campaign/[a-z_]+\.json', '/public-money/campaign-money', 'the Campaign Money page'),
    (r'data/[a-z_]+/[a-z_0-9]+\.(?:json|csv)', '/open-data', "this site's open data"),
]
SKIP = {'a', 'script', 'style', 'textarea', 'title', 'head', 'option', 'svg'}


def label(u):
    host = re.sub(r'^https?://(www\.)?', '', u).split('/')[0].split('?')[0]
    return host or 'source'


def _text(t):
    def url_sub(m):
        u = m.group(0); tail = ''
        while u and u[-1] in TRAIL:
            if u[-1] == ')' and u.count('(') > u.count(')') - 1:
                break
            tail = u[-1] + tail; u = u[:-1]
        raw = H.unescape(u)
        return f'<a class="src" href="{H.escape(raw, quote=True)}" target="_blank" rel="noopener">{H.escape(label(raw))}</a>{tail}'
    t = URL.sub(url_sub, t)
    for pat, href, lbl in PATHS:
        t = re.sub(pat, f'<a href="{href}">{lbl}</a>', t)
    return t


def linkify_html(doc):
    out, depth = [], {k: 0 for k in SKIP}
    for part in re.split(r'(<[^>]+>)', doc):
        if part.startswith('<'):
            m = re.match(r'<\s*(/?)\s*([a-zA-Z0-9]+)', part)
            if m:
                tag = m.group(2).lower()
                if tag in SKIP and not part.endswith('/>'):
                    depth[tag] = max(0, depth[tag] + (-1 if m.group(1) else 1))
            out.append(part)
        elif part and not any(depth.values()) and ('http' in part or 'data/' in part):
            out.append(_text(part))
        else:
            out.append(part)
    return ''.join(out)


LINKIFY_JS = r"""
(() => {
  const URLRE = /https?:\/\/[^\s<>"']+/g, SKIP = new Set(['A','SCRIPT','STYLE','TEXTAREA','TITLE','OPTION','INPUT','SELECT']);
  const PATHS = [[/data\/contracts\/contracts\.json/g, '/public-money/contracts', 'the Contracts page'], [/data\/tax\/budgets\.json/g, '/public-money/tax-dollars', 'the Tax Dollars page'],
    [/data\/votes\/votes\.json/g, '/public-money/votes', 'the How They Voted page'], [/data\/campaign\/[a-z_]+\.json/g, '/public-money/campaign-money', 'the Campaign Money page'],
    [/data\/[a-z_]+\/[a-z_0-9]+\.(?:json|csv)/g, '/open-data', "this site's open data"]];
  const host = u => u.replace(/^https?:\/\/(www\.)?/, '').split(/[/?#]/)[0] || 'source';
  function fix(node) {
    const t = node.nodeValue; if (!t || (t.indexOf('http') < 0 && t.indexOf('data/') < 0)) return;
    const marks = [];
    let m; URLRE.lastIndex = 0;
    while ((m = URLRE.exec(t))) { let u = m[0]; while (/[.,;:!?)\]}'"]$/.test(u) && !(u.endsWith(')') && (u.match(/\(/g) || []).length > (u.match(/\)/g) || []).length - 1)) u = u.slice(0, -1); marks.push([m.index, m.index + u.length, u, host(u), true]); }
    PATHS.forEach(([re, href, lbl]) => { re.lastIndex = 0; let p; while ((p = re.exec(t))) if (!marks.some(k => p.index < k[1] && p.index + p[0].length > k[0])) marks.push([p.index, p.index + p[0].length, href, lbl, false]); });
    if (!marks.length) return;
    marks.sort((a, b) => a[0] - b[0]);
    const frag = document.createDocumentFragment(); let i = 0;
    marks.forEach(([s, e, href, lbl, ext]) => { if (s < i) return; frag.appendChild(document.createTextNode(t.slice(i, s))); const a = document.createElement('a'); a.href = href; a.textContent = lbl; if (ext) { a.className = 'src'; a.target = '_blank'; a.rel = 'noopener'; } frag.appendChild(a); i = e; });
    frag.appendChild(document.createTextNode(t.slice(i)));
    node.parentNode.replaceChild(frag, node);
  }
  function walk(root) {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: n => { for (let p = n.parentNode; p && p !== root.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || p.nodeName === 'svg') return NodeFilter.FILTER_REJECT; return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode); list.forEach(fix);
  }
  const main = document.getElementById('main'); if (!main) return;
  walk(main);
  let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(() => walk(main), 60); }).observe(main, {childList: true, subtree: true});
})();
"""
