"""Make long ingested text readable: paragraphs, and the key facts pulled out.

Legal notices and similar bodies come off PDFs and newspaper sites as one run-on line. paragraphs() puts blank lines
between paragraphs (a leading all-caps heading, WHEREAS clauses, "WHEN:" style labels, and about three sentences each),
so the dataset, the API and the apps all get readable text. facts() pulls out the reference number, emails, phone
numbers and web links. Pages render the result with BC.longText (ui.js) or html() below.
"""
import html as H
import re

# words that end in a period without ending a sentence
ABBR = {'fla', 'st', 'no', 'nos', 'inc', 'co', 'corp', 'llc', 'jr', 'sr', 'mr', 'mrs', 'ms', 'dr', 'sec', 'ste', 'ave', 'blvd',
        'rd', 'hwy', 'dept', 'approx', 'etc', 'vs', 'a.m', 'p.m', 'u.s', 'f.s', 'e.g', 'i.e', 'ft', 'sq', 'vol', 'pg', 'pp', 'ord',
        'res', 'p', 'fl', 'ext', 'est', 'prof', 'gov', 'atty', 'mt', 'ct', 'ln', 'pkwy', 'hon', 'c.s.t', 'c.d.t'}
CAPS_WORD = re.compile(r"^[^a-z]*[A-Z][^a-z]*$")
LABEL = re.compile(r"(?<![\w'’])((?:[A-Z][A-Z&/'’-]*\s){0,2}[A-Z][A-Z&/'’-]+):(?=\s)")
HARD = re.compile(r"\s(?=(?:WHEREAS\b|NOW,? THEREFORE\b|BE IT (?:FURTHER )?RESOLVED\b|(?:SECTION|Section|ITEM|Item) \d+[.:](?=\s)))")
LIST_ITEM = re.compile(r"(?<!ITEM)(?<!Item)\s(?=(\d{1,2})\.\s[A-Z])")
# field labels a site-plan or meeting notice lists inline ("Location: ... Size: ... Owner: ...")
FIELD = re.compile(r"(?<!Meeting)\s(?=(?:Meeting Date|Meeting Time|Location|Size|Parcel(?: ID| No\.?| Number| #)?|Number of lots|Owner|Applicant|Agent|Proposed Development|"
                   r"Request|Zoning|Future Land Use|Acreage|Date|Time|Place|Purpose|Contact|Meeting ID|Passcode):\s)")
SENT_END = re.compile(r"[.!?][\"”’)]?\s+(?=[\"“(]?[A-Z0-9])")
TARGET = 300   # paragraph length to aim for, in characters


def _sentences(t):
    out, i = [], 0
    for m in SENT_END.finditer(t):
        word = re.split(r'[\s(]', t[i:m.start() + 1])[-1].rstrip('.').lower().strip('"“”’')
        if word in ABBR or len(word) == 1 or re.fullmatch(r'\d+', word) and t[m.end():m.end() + 1].isdigit():
            continue
        out.append(t[i:m.end()].strip()); i = m.end()
    if t[i:].strip():
        out.append(t[i:].strip())
    return out


def _clauses(s):
    """A very long sentence that is a list of clauses ('; PROVIDING FOR ...') gets one clause per line."""
    if len(s) > 500 and s.count('; ') >= 3:
        return s.replace('; ', ';\n')
    return s


def _reflow(t):
    t = re.sub(r'\s+', ' ', re.sub(r'([*=_~#-])\1{4,}', ' ', t)).strip()
    if not t:
        return []
    paras = []
    words = t.split(' ')
    # a leading heading in capitals ("CITY OF PANAMA CITY BEACH NOTICE TO PROPOSERS The City ...")
    n = 0
    while n < len(words) and CAPS_WORD.match(words[n]):
        n += 1
    if 2 <= n < len(words) and words[n][:1].isupper() and len(' '.join(words[:n])) <= 160:
        paras.append(' '.join(words[:n])); t = ' '.join(words[n:])
    # hard breaks: WHEREAS / labels like "WHEN:" start their own paragraph
    t = HARD.sub('\n', t)
    if all(re.search(rf'(?:^|\s){i}\.\s[A-Z]', t) for i in (1, 2, 3)):     # a numbered agenda: one item per line
        t = LIST_ITEM.sub('\n', t)
    if len(FIELD.findall(t)) >= 3:
        t = FIELD.sub('\n', t)
    t = LABEL.sub(lambda m: '\n' + m.group(0) if sum(c.isalpha() for c in m.group(1)) >= 3 and not m.group(1).startswith('FL ') else m.group(0), t)
    blocks = []
    for b in t.split('\n'):          # a bare label ("ITEM", "REGULAR MEETING:") joins what follows it
        b = b.strip()
        if blocks and (blocks[-1].endswith(':') or re.fullmatch(r'(?:ITEM|Item)', blocks[-1])) and len(blocks[-1]) < 40:
            blocks[-1] = f'{blocks[-1]} {b}'.strip()
        elif b:
            blocks.append(b)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        cur = ''
        for s in _sentences(block):
            if cur and len(cur) + len(s) > TARGET:
                paras.append(_clauses(cur)); cur = s
            else:
                cur = f'{cur} {s}'.strip()
        if cur:
            paras.append(_clauses(cur))
    return paras


FIELD_LINE = re.compile(r"^[A-Z][\w #/.()-]{0,28}:\s\S.{0,90}$")


def _fields(paras):
    """Runs of short "Label: value" paragraphs become one paragraph, a line each."""
    out = []
    for p in paras:
        if out and FIELD_LINE.match(p) and all(FIELD_LINE.match(x) for x in out[-1].split('\n')):
            out[-1] += '\n' + p
        else:
            out.append(p)
    return out


def paragraphs(text):
    """The text with blank lines between paragraphs. Text that already has paragraphs keeps them; only long ones reflow."""
    if not text:
        return text
    t = str(text).replace('\r\n', '\n').replace('\r', '\n')
    if '\n\n' in t.strip():
        out = []
        for p in re.split(r'\n\s*\n', t):
            out += _fields(_reflow(p)) if len(p) > 600 else [p.strip()] if p.strip() else []
        return '\n\n'.join(out)
    if '\n' in t.strip() and len(t) < 600:
        return t.strip()        # short text with line breaks (a weather alert) stays as written
    return '\n\n'.join(_fields(_reflow(t)))


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URLISH = re.compile(r"(?<![@\w.])(?:https?://[^\s<>\"']+|www\.[^\s<>\"']+|[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov|com|org|net|us|edu)(?:/[^\s<>\"']*)?)(?![\w@])", re.I)
PHONE = re.compile(r"(?<![\d-])\(?(\d{3})\)?[\s.-]{0,2}(\d{3})[\s.-](\d{4})(?![\d-])")
REF = [
    re.compile(r"\b(bid|rfq|rfp|itb|ifb|rfi|solicitation|project|contract)\s*(?:#|no\.?|number)\s*:?\s*([A-Z]{0,8}\d[\w.-]*\d|[A-Z]{0,8}\d+)", re.I),
    re.compile(r"\b(ordinance|resolution|emergency order)\s+(?:no\.?\s*|number\s*|#\s*)?(\d[\w-]*)", re.I),
]
TRAIL = '.,;:!?)]}\'"”’'


def _trim(u):
    while u and u[-1] in TRAIL and not (u[-1] == ')' and u.count('(') > u.count(')') - 1):
        u = u[:-1]
    return u


def facts(text):
    """{'reference', 'emails', 'phones', 'links'} found in the text; lists are '; '-joined strings, '' when none."""
    t = re.sub(r'\s+', ' ', text or '')
    ref = ''
    for rx in REF:
        m = rx.search(t)
        if m:
            kind = m.group(1).strip()
            kind = kind.upper() if kind.lower() in ('rfq', 'rfp', 'itb', 'ifb', 'rfi') else kind.capitalize()
            ref = f'{kind} {m.group(2).rstrip(".-")}'
            break
    emails = list(dict.fromkeys(e.lower().rstrip('.') for e in EMAIL.findall(t)))
    phones = []
    for m in PHONE.finditer(t):
        before = t[max(0, m.start() - 6):m.start()].lower()
        if re.search(r'\bf(ax)?\s*:?\s*$', before) or re.search(r'(id|#|no\.?)\s*:?\s*$', before):
            continue
        p = f'({m.group(1)}) {m.group(2)}-{m.group(3)}'
        if p.startswith('(800) 955-877'):     # Florida Relay (TDD), in every notice's accessibility line
            continue
        if p not in phones:
            phones.append(p)
    links = []
    for m in URLISH.finditer(t):
        u = _trim(m.group(0))
        if '@' in t[max(0, m.start() - 1):m.start()] or any(u.lower() in e for e in emails):
            continue
        key = re.sub(r'^https?://', '', u.lower()).rstrip('/')
        if key not in [re.sub(r'^https?://', '', x.lower()).rstrip('/') for x in links]:
            links.append(u)
    return {'reference': ref, 'emails': '; '.join(emails), 'phones': '; '.join(phones), 'links': '; '.join(links)}


def href(u):
    return u if re.match(r'https?://', u, re.I) else 'https://' + u


def _inline(p):
    """Escape one paragraph and link its emails, phone numbers and web addresses."""
    marks = []
    for m in EMAIL.finditer(p):
        marks.append((m.start(), m.end(), f'<a href="mailto:{H.escape(m.group(0))}">{H.escape(m.group(0))}</a>'))
    for m in URLISH.finditer(p):
        u = _trim(m.group(0))
        if not any(s < m.start() + len(u) and m.start() < e for s, e, _ in marks):
            marks.append((m.start(), m.start() + len(u), f'<a href="{H.escape(href(u), quote=True)}" target="_blank" rel="noopener">{H.escape(u)}</a>'))
    for m in PHONE.finditer(p):
        if not any(s < m.end() and m.start() < e for s, e, _ in marks):
            marks.append((m.start(), m.end(), f'<a href="tel:+1{m.group(1)}{m.group(2)}{m.group(3)}">{H.escape(m.group(0))}</a>'))
    out, i = '', 0
    for s, e, a in sorted(marks):
        if s < i:
            continue
        out += H.escape(p[i:s]) + a; i = e
    out += H.escape(p[i:])
    lab = re.match(r'((?:[A-Z][A-Z&/\'’-]*\s){0,2}[A-Z][A-Z&/\'’-]+):\s', p)
    if lab and sum(c.isalpha() for c in lab.group(1)) >= 3:
        n = len(H.escape(lab.group(0)))
        out = f'<b class="lt-lab">{out[:n].rstrip()}</b> {out[n:]}'
    return out.replace('\n', '<br>')


def is_heading(p):
    return len(p) <= 160 and not re.search('[a-z]', p) and len(p.split()) >= 2 and not p.rstrip().endswith((':', ','))


def html(text):
    """Paragraphs as <p> tags, the same markup BC.longText makes in the browser."""
    paras = [p.strip() for p in re.split(r'\n\s*\n', paragraphs(text) or '') if p.strip()]
    def one(p):
        if is_heading(p):
            return f'<p class="lt-h">{H.escape(p)}</p>'
        lines = p.split('\n')
        if len(lines) > 1 and all(FIELD_LINE.match(x) for x in lines):
            return '<dl class="lt-f">' + ''.join(f'<div><dt>{H.escape(x.split(":", 1)[0])}</dt><dd>{_inline(x.split(":", 1)[1].strip())}</dd></div>' for x in lines) + '</dl>'
        return f'<p>{_inline(p)}</p>'
    return ''.join(one(p) for p in paras)
