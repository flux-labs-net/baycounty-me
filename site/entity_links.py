"""Link any name on the site to its profile, the same way everywhere.

Build time (Python pages):
    from entity_links import href, a, person, vendor, gov
    a('person:doug-moore')                  -> <a href="/people/doug-moore">Doug Moore</a>
    person('Douglas Moore')                 -> the same link, from any spelling people.json knows
    vendor('MARSHALL BROTHERS', 'Marshall') -> a link to the company's vendor page or profile
    gov('pc')                               -> <a href="/governments/panama-city">Panama City</a>

Every built page also goes through link_names(): a known official's, company's or nonprofit's name in the page text
becomes a link to its profile. Page scripts get the same in the browser: BC.href(entity_id) and BC.a(entity_id, text)
in site.js, and names in text the scripts fill in are linked from /data/entity-names.json (ENTITY_JS).

Not linked by name: government names (they are on every page), board members (common names; their links come from
their ids), and officials on the nonprofit and profile pages, where a board member who shares an official's name must
not read as that official until an admin confirms the match.
"""
import html as H
import json, os, re

from entity_graph import page_url, build, KIND_LABEL

e = lambda s: H.escape(str(s if s is not None else ''))


def href(eid):
    return page_url(eid)


def name_of(eid):
    x = build().ents.get(eid)
    return x['name'] if x else eid.split(':', 1)[-1]


def a(eid, text=None, cls=None):
    t = name_of(eid) if text is None else text
    if not eid or eid not in build().ents:
        return e(t)
    c = f' class="{cls}"' if cls else ''
    return f'<a{c} href="{e(href(eid))}">{e(t)}</a>'


def person(name, text=None):
    import ids
    pid = ids.person_id(name) if isinstance(name, str) else None
    t = (ids.split_district(name)[0] if isinstance(name, str) else name) if text is None else text
    return a('person:' + pid, t) if pid else e(t)


def vendor(name, text=None):
    import ids
    vid = ids.vendor_id(name)
    t = ids.biz_case(text if text is not None else name)
    return a('vendor:' + vid, t) if vid and 'vendor:' + vid in build().ents else e(t)


def gov(gid, text=None):
    return a('gov:' + gid, text) if gid and 'gov:' + gid in build().ents else e(text or gid or '')


# ---------- names in page text ----------
WORD = re.compile(r"[A-Za-z0-9&][A-Za-z0-9&'’.-]*")
GENERIC = {'city', 'county', 'state', 'florida', 'bay', 'school', 'schools', 'board', 'church', 'foundation', 'association', 'inc',
           'the', 'united way', 'habitat', 'american legion', 'rotary club',
           # company names that are also places or plain phrases in page text
           'pier park', 'key data', 'bag tags', 'stow away', 'leasing 2', 'who dey', '814 sand', 'port engr', 'mr fence', 'boo media',
           # plain phrases that match a short company or nonprofit name ("For Bay County items...", "direct deposit")
           'for bay county', 'construction services', 'blue shield', 'direct deposit', 'university of florida', 'energy systems',
           'disposal services', 'hope project', 'print source'}
SMALL = {'of', 'and', 'the', 'for', 'in', 'on', 'at', 'to', 'by', 'a', 'an', 'or', 'de', '&'}


def proper(seg):
    """Text matches a name only when it is written as one: every word capitalized (or a number), small words aside."""
    ws = WORD.findall(seg)
    return bool(ws) and (ws[0][0].isupper() or ws[0][0].isdigit()) and all(w[0].isupper() or w[0].isdigit() or w.lower() in SMALL for w in ws)
SUFFIX = re.compile(r',?\s+(inc\.?|incorporated|llc|l\.l\.c\.|corp\.?|corporation|co\.?|company|ltd\.?|pa|p\.a\.)$', re.I)


def norm(s):
    return ' '.join(w.lower().replace('’', "'").strip(".'-") for w in WORD.findall(s or '') if w.strip(".'-"))


def _forms(name):
    out = {name}
    s = SUFFIX.sub('', name.strip())
    if s != name:
        out.add(s)
    return out


def names():
    """normalized name -> entity id, for officials, candidates, companies and nonprofits. A name two entities share is
    dropped, except that a company beats a nonprofit or business of the same name (the same organization)."""
    import ids
    G = build()
    cand = {}
    rank = {'person': 0, 'vendor': 1, 'nonprofit': 2}

    def add(n, eid, min_words=2, min_len=8):
        k = norm(n)
        if not k or k in GENERIC or len(k) < min_len or len(k.split()) < min_words:
            return
        cand.setdefault(k, set()).add(eid)
    for eid, x in G.ents.items():
        kind = x['kind']
        if kind == 'person':
            for n in [x['name']] + x['aliases']:
                add(ids.split_district(re.sub(r'\([^)]*\)', ' ', n))[0], eid, 2, 6)
                add(ids.split_district(n)[0], eid, 2, 6)  # William (Chuck) Perdue, William "Chuck" Perdue
        elif kind == 'vendor':
            for n in [re.sub(r'\s*\([^)]*\)', '', y).strip() for y in [x['name']] + x['aliases']]:
                for f in _forms(n):
                    add(f, eid, 1 if len(norm(f)) >= 10 and not norm(f).isdigit() else 2, 6)
        elif kind == 'nonprofit':
            for f in _forms(x['name']):
                add(f, eid, 2, 12)
    out = {}
    from entity_graph import _vendor_pages
    same = {(l['from_id'], l['to_id']) for l in G.links.values() if l['relation'] == 'same'}
    for k, s in cand.items():
        if len(s) > 1:
            # a vendor with no vendor page that is the same organization as a nonprofit: the nonprofit profile is fuller
            for v in [i for i in s if i.startswith('vendor:') and i[7:] not in _vendor_pages()]:
                if any((v, n) in same or (n, v) in same for n in s if n.startswith('nonprofit:')):
                    s = s - {v}
            if len(s) == 1:
                out[k] = next(iter(s))
                continue
            best = sorted(s, key=lambda i: rank[i.split(':')[0]])
            if rank[best[0].split(':')[0]] == rank[best[1].split(':')[0]]:
                continue
            s = {best[0]}
        out[k] = s.pop()
    return out


_IDX = {}


def _index():
    if not _IDX:
        n = names()
        _IDX['n'] = n
        _IDX['max'] = max(len(k.split()) for k in n) if n else 1
    return _IDX['n'], _IDX['max']


SKIP = {'a', 'script', 'style', 'textarea', 'title', 'head', 'option', 'svg', 'code', 'pre', 'button', 'label', 'select', 'h1', 'nav',
        'summary', 'input'}
VOID = {'br', 'img', 'input', 'meta', 'link', 'hr', 'wbr', 'source', 'col', 'area', 'base', 'embed', 'param', 'track'}
NO_PEOPLE = ('/connections/nonprofits', '/profile/', '/chambers', '/volunteer')


def _link_text(html_text, path, people_ok):
    n, mx = _index()
    t = H.unescape(html_text)  # match names as written ("Sam's Club", "Roberts & Roberts"), not as escaped HTML
    words = [(m.start(), m.end(), m.group(0)) for m in WORD.finditer(t)]
    if not words:
        return html_text
    out, i, last = [], 0, 0
    while i < len(words):
        hit = None
        for L in range(min(mx, len(words) - i), 0, -1):
            seg = t[words[i][0]:words[i + L - 1][1]]
            if '\n' in seg:
                continue
            eid = n.get(norm(seg))
            if eid and proper(seg) and (people_ok or not eid.startswith('person:')):
                hit = (L, eid)
                break
        if hit and page_url(hit[1]) == path:  # this page's own name: leave it, and don't link a shorter name inside it
            i += hit[0]
        elif hit:
            L, eid = hit
            s, en = words[i][0], words[i + L - 1][1]
            while en > s and t[en - 1] in ".'’-":  # keep sentence punctuation outside the link
                en -= 1
            out.append(e(t[last:s]))
            out.append(f'<a class="ent" href="{e(page_url(eid))}">{e(t[s:en])}</a>')
            last = en
            i += L
        else:
            i += 1
    if not out:
        return html_text
    out.append(e(t[last:]))
    return ''.join(out)


def link_names(doc, path):
    """Link known names in the text inside <main> (never inside links, buttons, headings h1, scripts, or any element
    marked data-nolink)."""
    if path.startswith('/es') or path in ('/404',):
        return doc
    a0 = doc.find('<main id="main">')
    a1 = doc.rfind('</main>')
    if a0 < 0 or a1 < 0:
        return doc
    people_ok = not path.startswith(NO_PEOPLE)
    head, body, tail = doc[:a0], doc[a0:a1], doc[a1:]
    out, stack = [], []  # (tag, blocks linking)
    for part in re.split(r'(<[^>]+>)', body):
        if part.startswith('<'):
            m = re.match(r'<\s*(/?)\s*([a-zA-Z0-9]+)', part)
            if m and not part.startswith('<!'):
                tag = m.group(2).lower()
                if m.group(1):
                    if any(t == tag for t, _ in stack):
                        while stack:
                            t, _ = stack.pop()
                            if t == tag:
                                break
                elif tag not in VOID and not part.endswith('/>'):
                    stack.append((tag, tag in SKIP or 'data-nolink' in part))
            out.append(part)
        elif part.strip() and not any(b for _, b in stack):
            out.append(_link_text(part, path, people_ok))
        else:
            out.append(part)
    return head + ''.join(out) + tail


def write_names(out_dir):
    """/data/entity-names.json for ENTITY_JS: {"n": {normalized name: index}, "u": [profile URL], "k": [kind], "max": words}."""
    n, mx = _index()
    # page scripts mostly print officials and companies; nonprofits only when they have money ties (keeps the file small)
    G = build()
    money = {x[k] for x in G.links.values() if x['relation'] in ('paid', 'grant', 'same', 'gift') for k in ('from_id', 'to_id')}
    n = {k: v for k, v in n.items() if not v.startswith('nonprofit:') or v in money}
    mx = max(len(k.split()) for k in n) if n else 1
    eids = sorted(set(n.values()))
    pos = {x: i for i, x in enumerate(eids)}
    json.dump({'n': {k: pos[v] for k, v in sorted(n.items())}, 'u': [page_url(x) for x in eids], 'k': [x.split(':')[0] for x in eids], 'max': mx},
              open(os.path.join(out_dir, 'data', 'entity-names.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    return len(n)


def js_rules():
    """What BC.href needs to turn an entity id into its URL without loading the whole registry."""
    from entity_graph import _main_govs, _vendor_pages
    return {'gov': _main_govs(), 'vp': sorted(_vendor_pages())}


ENTITY_JS = r"""
(() => {
  const R = __ENTITY_RULES__, VP = new Set(R.vp);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  // the profile URL for an entity id: same rule as site/entity_graph.py page_url()
  function href(id) {
    const i = String(id || '').indexOf(':'); if (i < 0) return null;
    const k = id.slice(0, i), v = id.slice(i + 1);
    if (k === 'gov' && R.gov[v]) return '/governments/' + R.gov[v];
    if (k === 'vendor' && VP.has(v)) return '/public-money/vendors/' + v;
    if (k === 'person') return '/people/' + encodeURIComponent(v);
    return '/profile/' + k + '/' + encodeURIComponent(v);
  }
  const a = (id, text, cls) => {  // names filed in all caps read as names (api/_names.js), as entity_links.a() does at build
    const u = href(id), t = window.BCNames ? BCNames.nameCase(text, id) : text;
    return u ? `<a${cls ? ` class="${cls}"` : ''} href="${esc(u)}">${esc(t)}</a>` : esc(t);
  };
  window.BC = Object.assign(window.BC || {}, {href, a});
  // names in text that page scripts fill in: same rules as entity_links.link_names()
  const main = document.getElementById('main'); if (!main || document.documentElement.lang.startsWith('es')) return;
  const noPeople = /^\/(connections\/nonprofits|profile\/)/.test(location.pathname);
  const SKIP = new Set(['A', 'SCRIPT', 'STYLE', 'TEXTAREA', 'TITLE', 'OPTION', 'INPUT', 'SELECT', 'CODE', 'PRE', 'BUTTON', 'LABEL', 'H1', 'NAV', 'SUMMARY', 'svg']);
  const SMALL = new Set(['of', 'and', 'the', 'for', 'in', 'on', 'at', 'to', 'by', 'a', 'an', 'or', 'de', '&']);
  const proper = s => { const ws = s.match(/[A-Za-z0-9&][A-Za-z0-9&'’.-]*/g) || []; return ws.length > 0 && /^[A-Z0-9]/.test(ws[0]) && ws.every(w => /^[A-Z0-9]/.test(w) || SMALL.has(w.toLowerCase())); };
  const WORD = /[A-Za-z0-9&][A-Za-z0-9&'’.-]*/g, norm = s => (s.match(WORD) || []).map(w => w.toLowerCase().replace(/’/g, "'").replace(/^[.'-]+|[.'-]+$/g, '')).filter(Boolean).join(' ');
  let N = null, busy = false; const done = new WeakSet();
  function fix(node) {
    const t = node.nodeValue; if (!t || t.length < 6) return;
    const ws = []; let m; WORD.lastIndex = 0; while ((m = WORD.exec(t))) ws.push([m.index, m.index + m[0].length]);
    const frag = []; let i = 0, last = 0;
    while (i < ws.length) {
      let hit = 0, id = -1;
      for (let L = Math.min(N.max, ws.length - i); L > 0; L--) {
        const seg = t.slice(ws[i][0], ws[i + L - 1][1]); if (!proper(seg)) continue; const x = N.n[norm(seg)];
        if (x !== undefined && !(noPeople && N.k[x] === 'person')) { hit = L; id = x; break; }
      }
      if (hit && N.u[id] === location.pathname) { i += hit; continue; }  // this page's own name: skip it whole
      if (hit) { let s = ws[i][0], e = ws[i + hit - 1][1]; while (e > s && ".'’-".includes(t[e - 1])) e--; frag.push([last, s, e, id]); last = e; i += hit; } else i++;
    }
    if (!frag.length) return;
    const f = document.createDocumentFragment(); let p = 0;
    frag.forEach(([l, s, e, id]) => { f.appendChild(document.createTextNode(t.slice(p, s))); const el = document.createElement('a'); el.className = 'ent'; el.href = N.u[id]; el.textContent = t.slice(s, e); f.appendChild(el); p = e; });
    f.appendChild(document.createTextNode(t.slice(p)));
    f.childNodes.forEach(c => done.add(c.nodeType === 3 ? c : c.firstChild));
    node.parentNode.replaceChild(f, node);
  }
  function walk() {
    if (!N || busy) return; busy = true;
    const w = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {acceptNode: n => {
      if (done.has(n)) return NodeFilter.FILTER_REJECT;
      for (let p = n.parentNode; p && p !== main.parentNode; p = p.parentNode) if (SKIP.has(p.nodeName) || (p.hasAttribute && p.hasAttribute('data-nolink'))) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT; }});
    const list = []; while (w.nextNode()) list.push(w.currentNode);
    list.forEach(n => { done.add(n); fix(n); });
    busy = false;
  }
  const start = () => fetch('/data/entity-names.json').then(r => r.ok ? r.json() : null).then(d => { N = d; walk(); let t; new MutationObserver(() => { clearTimeout(t); t = setTimeout(walk, 120); }).observe(main, {childList: true, subtree: true}); }).catch(() => {});
  if ('requestIdleCallback' in window) requestIdleCallback(start, {timeout: 2500}); else setTimeout(start, 400);
})();
"""


def entity_js():
    return ENTITY_JS.replace('__ENTITY_RULES__', json.dumps(js_rules(), separators=(',', ':')))
