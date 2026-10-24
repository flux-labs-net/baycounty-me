"""Pull a county's charitable solicitation registrations from Florida FDACS (Division of Consumer Services).

Sources (both ASP.NET WebForms pages, fetched with plain HTTP postbacks):
  - Business License Lookup (BusinessSearch.aspx): county + program "CH: Charitable Organization", every status.
    Gives each registration number, name, DBA, city/state/zip, phone, issued and expiration dates and status.
  - Check-A-Charity (CheckACharity.aspx): searched by registration number, then the record is expanded.
    Gives the latest financial report (period end, revenue, program / administrative / fundraising expenses),
    and when present the professional solicitors / fundraising consultants, branches and uploaded documents.

The public pages do not show FEIN, website, contributions, government grants or officers. Officers and directors
are only inside the uploaded application PDFs. A second step, --officers, downloads each registration's latest
application PDF (cached in --work, never committed), reads the officers' names and titles and the FEIN, and rewrites
fdacs_officers.csv.gz and the fein column of fdacs_registrations.csv.gz. Its counts go to fdacs_pdf_log.json.

Street addresses and email addresses are read from the listing but never written.

Usage: python data/nonprofits/fetch_fdacs.py --county bay [--work DIR] [--limit N] [--officers]
Raw HTML is cached in --work (default: a fixed folder under the system temp dir) so a rerun resumes.
Writes data/nonprofits/<county>/{fdacs_registrations,fdacs_officers}.csv.gz and fdacs_fetch_log.json.
"""
import argparse, csv, datetime as dt, gzip, html, http.cookiejar, io, json, os, random, re, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request

try:
    import pdfplumber  # only needed for --officers
except ImportError:
    pdfplumber = None
try:
    import pypdf  # form fields of the fillable application
except ImportError:
    pypdf = None

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = 'https://csapp.fdacs.gov/CSPublicApp'
LISTING_URL = f'{BASE}/BusinessSearch/BusinessSearch.aspx'
CAC_URL = f'{BASE}/CheckACharity/CheckACharity.aspx'
UA = 'BayCounty.me public-records fetch (jeremy@fluxlabs.net)'
P = 'ctl00$cpMainContent$'
DELAY = 3.0
COUNTY_CODES = {'bay': '3'}  # value of the County dropdown on BusinessSearch.aspx

REG_COLS = ['registration_number', 'name', 'dba', 'fein', 'status', 'status_detail', 'registration_date',
            'expiration_date', 'city', 'state', 'zip', 'county', 'phone', 'website', 'fiscal_year_end',
            'total_revenue', 'contributions', 'government_grants', 'program_expenses', 'fundraising_expenses',
            'management_expenses', 'total_expenses', 'program_percent', 'fundraising_consultants', 'detail_url',
            'fetched_at']
OFF_COLS = ['registration_number', 'name', 'title', 'fetched_at']


class Stop(Exception):
    pass


class Client:
    """One request at a time, at least DELAY seconds apart, with backoff and a hard stop on repeated failures."""

    def __init__(self, delay=DELAY, max_errors=5):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [('User-Agent', UA), ('Accept', 'text/html')]
        self.delay, self.max_errors = delay, max_errors
        self.last = 0.0
        self.requests = 0
        self.errors = []

    def fetch(self, url, form=None):
        return self.fetch_raw(url, form)[1].decode('utf-8', 'replace')

    def fetch_raw(self, url, form=None):
        """(content type, body bytes)."""
        tries = 0
        while True:
            wait = self.delay + random.uniform(0.2, 1.2) - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.requests += 1
            try:
                data = urllib.parse.urlencode(form).encode() if form is not None else None
                with self.op.open(url, data, timeout=90) as r:
                    return r.headers.get('Content-Type', ''), r.read()
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                code = getattr(e, 'code', None)
                tries += 1
                self.errors.append(f'{url} {code or e}')
                if code is not None and code < 500 and code != 429:
                    raise Stop(f'HTTP {code} from {url}')
                if tries >= self.max_errors:
                    raise Stop(f'giving up after {tries} errors; last: {code or e}')
                back = min(300, 15 * 2 ** tries)
                print(f'  error {code or e}; backing off {back}s', file=sys.stderr)
                time.sleep(back)


def hidden(page):
    return {m.group(1): html.unescape(m.group(2)) for m in
            re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}


def text(s):
    s = re.sub(r'<br\s*/?>', '\n', s or '')
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s).replace('\xa0', ' ')
    return re.sub(r'[ \t\r\f\v]+', ' ', s).strip()


def iso(d):
    d = (d or '').strip()
    for f in ('%m/%d/%Y', '%m/%d/%y'):
        try:
            return dt.datetime.strptime(d, f).date().isoformat()
        except ValueError:
            pass
    return ''


def money(s):
    s = (s or '').replace('$', '').replace(',', '').strip()
    neg = s.startswith('(') or s.startswith('-')
    s = s.strip('()-')
    if not re.fullmatch(r'\d*\.?\d+', s):
        return ''
    v = float(s)
    v = -v if neg else v
    return str(int(v)) if v == int(v) else f'{v:.2f}'


# ---------- listing ----------

def listing_pages(cl, county_code, work):
    """Every result page of the listing, following the grid's pager postbacks (cached per page)."""
    ldir = os.path.join(work, 'listing')
    os.makedirs(ldir, exist_ok=True)
    done = os.path.join(ldir, 'complete')
    if os.path.exists(done):
        return [open(os.path.join(ldir, f), encoding='utf-8').read()
                for f in sorted(os.listdir(ldir)) if f.endswith('.html')]
    page = cl.fetch(LISTING_URL)
    search = {P + 'BusinessNameTb': '', P + 'LicenseTb': '', P + 'txtPhone': '', P + 'txtCity': '',
              P + 'CountyDl': county_code, P + 'LicenseTypeDl': 'CH'}  # chkActive unchecked: every status
    form = hidden(page)
    form.update(search)
    form[P + 'SingleSearchBt'] = 'Search'
    page = cl.fetch(LISTING_URL, form)
    pages, n = [page], 1
    while True:
        with open(os.path.join(ldir, f'page{n:03d}.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        pager = re.search(r'<tr align="right">\s*<td>(.*?)</td>\s*</tr>', page, re.S)
        ptxt = pager.group(1) if pager else ''
        after = ptxt[ptxt.find(f'<span>{n}</span>'):] if f'<span>{n}</span>' in ptxt else ''
        links = re.findall(r"__doPostBack\(&#39;([^&]+)&#39;,&#39;&#39;\)\"><font[^>]*>([^<]+)</font>", after)
        # The next page is the first link after the current page number: "n+1", or "..." at a block's end.
        nxt = [t for t, label in links[:1] if label.strip() in (str(n + 1), '...')]
        if not nxt:
            break
        form = hidden(page)
        form.update(search)
        form.update({P + 'SortDl': 'NAME_1', P + 'FilterDl': '00', P + 'PagesizeDl': '20',
                     '__EVENTTARGET': nxt[0], '__EVENTARGUMENT': ''})
        page = cl.fetch(LISTING_URL, form)
        n += 1
        pages.append(page)
        if n > 500:
            raise Stop('listing pager did not end')
    open(done, 'w').close()
    return pages


def parse_listing(pages):
    m = re.search(r'id="cpMainContent_lblAmount">(\d+)<', pages[0])
    found = int(m.group(1)) if m else None
    out = []
    blocks = [b for page in pages for b in re.split(r'<div id="cpMainContent_MasterGv_maindiv_\d+">', page)[1:]]
    for b in blocks:
        name = text(re.search(r'<strong>(.*?)</strong>', b, re.S).group(1))
        addr_m = re.search(r'font-size: 14px;">\s*(.*?)<br\s*/?>\s*<b>Phone', b, re.S) or \
            re.search(r'dataTab_\d+".*?<tr>.*?</tr>\s*<tr>\s*<td[^>]*>(.*?)</td>', b, re.S)
        addr = text(addr_m.group(1)) if addr_m else ''
        city = state = zipc = ''
        am = re.search(r'([^,]+),\s*([A-Z]{2})\s+(\d{5})(?:-\d{0,4})?\s*$', addr)
        if am:
            city, state, zipc = am.group(1).strip(), am.group(2), am.group(3)
        pm = re.search(r'<b>Phone:</b>\s*([^<&]*)', b)
        phone = pm.group(1).strip() if pm else ''
        dm = re.search(r'<strong>DBA/Other Names</strong><br/>(.*?)</td>', b, re.S)
        dba = '; '.join(x.strip() for x in text(dm.group(1)).split('\n') if x.strip()) if dm else ''
        for row in re.findall(r'<tr><td style="font-size: 14px;">(.*?)</tr>', b, re.S):
            cells = [text(c) for c in re.findall(r'<td[^>]*>(.*?)</td>', '<td>' + row, re.S)]
            if len(cells) >= 5 and re.fullmatch(r'CH\d+', cells[1]):
                out.append({'registration_number': cells[1], 'name': name, 'dba': dba, 'license_type': cells[0],
                            'issued': iso(cells[2]), 'expires': iso(cells[3]), 'status_detail': cells[4],
                            'city': city, 'state': state, 'zip': zipc, 'phone': phone})
    return found, out


def status_of(detail):
    d = detail.lower()
    for key, label in (('not soliciting', 'Not Soliciting'), ('law na', 'Law NA'), ('active', 'Active'), ('expired', 'Expired'),
                       ('pending', 'Pending'), ('revoked', 'Revoked'), ('suspend', 'Suspended'),
                       ('inactive', 'Inactive'), ('denied', 'Denied'), ('withdrawn', 'Withdrawn'),
                       ('cancel', 'Cancelled'), ('exempt', 'Exempt'), ('closed', 'Closed')):
        if key in d:
            return label
    return detail


# ---------- Check-A-Charity ----------

class Charity:
    def __init__(self, cl, work):
        self.cl, self.dir = cl, os.path.join(work, 'detail')
        os.makedirs(self.dir, exist_ok=True)
        self.page = None

    def get(self, reg):
        path = os.path.join(self.dir, f'{reg}.html')
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return open(path, encoding='utf-8').read()
        if self.page is None:
            self.page = self.cl.fetch(CAC_URL)
        form = hidden(self.page)
        form.update({P + 'BusinessNameTb': '', P + 'LicenseTb': reg, P + 'SingleSearchBt': 'Search'})
        page = self.cl.fetch(CAC_URL, form)
        self.page = page
        btn = re.search(r'name="(ctl00\$cpMainContent\$MasterGv\$ctl\d+\$DetailIb)"', page)
        if btn and f'Registration Number :{reg}' in page:
            form = hidden(page)
            form.update({P + 'BusinessNameTb': '', P + 'LicenseTb': reg, P + 'SortDl': 'HONEST_SERVICE_REG_2',
                         P + 'PagesizeDl': '20', btn.group(1) + '.x': '5', btn.group(1) + '.y': '5'})
            page = self.cl.fetch(CAC_URL, form)
            self.page = page
        with open(path, 'w', encoding='utf-8') as f:
            f.write(page)
        return page


def parse_detail(page, reg):
    i = page.find('id="cpMainContent_MasterGv"')
    if i < 0 or f'Registration Number :{reg}' not in page:
        return None
    body = page[i:page.find('<div id="Expand">', i)]
    d = {'captions': []}
    m = re.search(r'Expiration Date :\s*([\d/]+)', body)
    d['expiration_date'] = iso(m.group(1)) if m else ''
    m = re.search(r'Revenue Source :\s*([^<]*?)\s*\((\d{1,2}/\d{1,2}/\d{4})\)', body)
    d['revenue_source'] = m.group(1).strip() if m else ''
    d['fiscal_year_end'] = iso(m.group(2)) if m else ''
    flat = text(body)

    def amt(label):
        mm = re.search(re.escape(label) + r'\s*:\s*(\(?-?\$[\d,]*\.?\d*\)?)\s*(\d+%)?', flat)
        return (money(mm.group(1)), (mm.group(2) or '').rstrip('%')) if mm else ('', '')

    d['total_revenue'] = amt('Total Revenue')[0]
    d['total_expenses'] = amt('Total Expenses')[0]
    d['program_expenses'], d['program_percent'] = amt('Program Services Expenses')
    d['management_expenses'] = amt('Administrative Expenses')[0]
    d['fundraising_expenses'] = amt('Fundraising Expenses')[0]
    for lbl, key in (('Contributions', 'contributions'), ('Government Grants', 'government_grants')):
        d[key] = amt(lbl)[0]
    # Captioned sub-tables of the expanded record (solicitors, branches, fundraisers, purpose, documents, ...).
    sections = {}
    for cap, tbl in re.findall(r'<caption[^>]*>(.*?)</caption>(.*?)</table>', body, re.S):
        cap = text(cap)
        rows = [text(r) for r in re.findall(r'<tr[^>]*>(.*?)</tr>', tbl, re.S)]
        sections[cap] = [r for r in rows if r]
        d['captions'].append(cap)
    d['sections'] = sections
    firms = []
    for cap, rows in sections.items():
        if re.search(r'solicit|fund ?rais|consultant', cap, re.I):
            for r in rows:
                firm = r.split('\n')[0].split(' -- ')[0].strip()  # rows read "FIRM -- City, St"
                if firm and firm not in firms:
                    firms.append(firm)
    d['fundraising_consultants'] = '; '.join(firms)
    people = []
    for cap, rows in sections.items():
        if re.search(r'officer|director|trustee', cap, re.I):
            for r in rows:
                parts = [x.strip() for x in re.split(r'\n| {2,}', r) if x.strip()]
                if parts:
                    people.append((parts[0], ' '.join(parts[1:])))
    d['officers'] = people
    return d


# ---------- officers from uploaded application PDFs (--officers) ----------

DOC_RE = re.compile(r"__doPostBack\(&#39;([^&]+gvDocuments[^&]+lnkBtn)&#39;,&#39;&#39;\)\">\s*Document ([^<]*?), "
                    r"received on (\d{1,2}/\d{1,2}/\d{4}) for tracking number \(DTN\): (\d+)\s*</a>")
PHONE_RE = re.compile(r'^\(?\d{3}\)?[-. ]?\d{3}-\d{4}')
ADDRESSY_RE = re.compile(r'^\d|@|\bP\.?\s?O\.? Box\b|\b\d{5}(-\d{4})?$', re.I)  # never keep address lines
SECTION_ENDS = ('Branch offices', 'Professional Solicitors', 'Fundraising Consultants', 'Commercial Co-venturers',
                'Financial Statement', 'Attached Documents', 'Application Questionnaire', 'Signature')


def documents(page):
    """Uploaded documents on an expanded record: [{target, kind, received, dtn}]."""
    return [{'target': t, 'kind': k.strip(), 'received': iso(d), 'dtn': n} for t, k, d, n in DOC_RE.findall(page)]


def latest_application(docs):
    apps = [d for d in docs if re.search(r'application|renewal', d['kind'], re.I)]
    return max(apps, key=lambda d: (d['received'], d['dtn']), default=None)


def download_pdf(cl, ch, reg, doc, path):
    """Post back the document link on the record page. Retries once with a freshly fetched record."""
    for fresh in (False, True):
        if fresh:
            cached = os.path.join(ch.dir, f'{reg}.html')
            if os.path.exists(cached):
                os.remove(cached)
        page = ch.get(reg)
        target = next((d['target'] for d in documents(page) if d['dtn'] == doc['dtn'] and d['kind'] == doc['kind']
                       and d['received'] == doc['received']), None)
        if not target:
            continue
        form = hidden(page)
        form.update({P + 'BusinessNameTb': '', P + 'LicenseTb': reg, P + 'SortDl': 'HONEST_SERVICE_REG_2',
                     P + 'PagesizeDl': '20', '__EVENTTARGET': target, '__EVENTARGUMENT': ''})
        ctype, body = cl.fetch_raw(CAC_URL, form)
        if 'pdf' in ctype.lower() or body[:5] == b'%PDF-':
            with open(path, 'wb') as f:
                f.write(body)
            return True
    return False


def clean_name(name):
    """Name as filed, minus stray punctuation at either end."""
    return re.sub(r"^[^\w(]+|[^\w.)]+$", '', re.sub(r'\s+', ' ', name)).strip()


def parse_form_fields(path):
    """(fein, [(name, title)]) from the fillable "small charitable organizations" form. Only the officer name and
    title fields and the FEI number are read."""
    if pypdf is None:
        return '', []
    try:
        fields = pypdf.PdfReader(path).get_fields() or {}
    except Exception:
        return '', []
    val = lambda k: str((fields.get(k) or {}).get('/V') or '').strip()
    fein = val('FEI prefix') + val('FEI number')
    fein = fein if re.fullmatch(r'\d{9}', fein) else ''
    people = []
    for k in fields:
        m = re.fullmatch(r'Name of (\w+) individual or officer', k)
        name = re.sub(r'\s+', ' ', val(k)) if m else ''
        if name and re.search(r'[A-Za-z]', name):
            people.append((name, val(f'Title of {m.group(1)} individual or officer')))
    return fein, list(dict.fromkeys((clean_name(n), t) for n, t in people))


def pdf_text(path):
    with pdfplumber.open(path) as pdf:
        return '\n'.join(pg.extract_text() or '' for pg in pdf.pages)


def parse_application(txt):
    """(fein, [(name, title)], skipped counts) from an application's text. People marked "- Removed" and anyone exempt from public
    records are left out. Only names and titles are kept."""
    m = re.search(r'FEIN:\s*(\d{2})-?(\d{7})\b', txt)
    fein = m.group(1) + m.group(2) if m else ''
    # Small-organization forms say "Personnel Information", the full form "Owner/Management Information".
    starts = [j for j in (txt.find('Personnel Information'), txt.find('Owner/Management Information')) if j >= 0]
    lines = [l.strip() for l in txt[min(starts):].split('\n')] if starts else []
    people, removed, cur = [], False, None
    for line in lines:
        if line.startswith(SECTION_ENDS):
            break  # branches, solicitors, consultants and documents also use "Name:" lines
        if line.startswith('- Removed'):
            removed = True
        elif line.startswith('Name:'):
            cur = {'name': line[5:].strip(), 'title': [], 'removed': removed, 'open': True, 'exempt': False}
            removed = False
            people.append(cur)
        elif cur and cur['open']:
            if line.startswith(('Phone:', 'Address:', 'Additional Information')):
                cur['open'] = False
            elif not PHONE_RE.match(line) and not ADDRESSY_RE.search(line):
                t = line[6:].strip() if line.startswith('Title:') else line
                if t:
                    cur['title'].append(t)
        if cur and re.search(r'exempt from Public Records\?.*\bYes\s*$', line):
            cur['exempt'] = True
    out, skipped = [], {'removed': 0, 'exempt': 0, 'blank': 0}
    for p in people:
        name = re.sub(r'\s+', ' ', p['name']).strip()
        if p['removed'] or p['exempt'] or not name or not re.search(r'[A-Za-z]', name) or name.startswith('Name:'):
            skipped['removed' if p['removed'] else 'exempt' if p['exempt'] else 'blank'] += 1
            continue
        name = clean_name(name)
        title = '; '.join(dict.fromkeys(p['title']))
        if (name, title) not in out:
            out.append((name, title))
    return fein, out, skipped


def officers_pass(a, county, work, out, today):
    if pdfplumber is None:
        sys.exit('--officers needs pdfplumber (pip install pdfplumber)')
    reg_path = os.path.join(out, 'fdacs_registrations.csv.gz')
    with gzip.open(reg_path, 'rt', encoding='utf-8', newline='') as f:
        regs = list(csv.DictReader(f))
    pdir = os.path.join(work, 'pdf')
    os.makedirs(pdir, exist_ok=True)
    cl = Client()
    ch = Charity(cl, work)
    todo = [r for r in regs if r['detail_url']]  # only records with a Check-A-Charity page have documents
    if a.limit:
        todo = todo[:a.limit]
    c = {'registrations_checked': 0, 'pdfs_found': 0, 'pdfs_downloaded': 0, 'pdfs_cached': 0, 'text_extracted': 0,
         'ocr': 0, 'skipped_no_text_layer': 0, 'skipped_download_failed': 0, 'no_application_listed': 0,
         'no_officer_table': 0, 'form_fields_read': 0, 'people_skipped_removed': 0,
         'people_skipped_exempt': 0, 'people_skipped_blank': 0, 'officer_rows': 0, 'registrations_with_officers': 0, 'feins_found': 0}
    officers, feins, unparsed, stopped = [], {}, [], None
    for n, r in enumerate(todo, 1):
        reg = r['registration_number']
        try:
            doc = latest_application(documents(ch.get(reg)))
            c['registrations_checked'] += 1
            if not doc:
                c['no_application_listed'] += 1
                print(f'[{n}/{len(todo)}] {reg} no application document', file=sys.stderr)
                continue
            c['pdfs_found'] += 1
            path = os.path.join(pdir, f'{reg}_{doc["dtn"]}.pdf')
            if os.path.exists(path) and os.path.getsize(path) > 0:
                c['pdfs_cached'] += 1
            elif download_pdf(cl, ch, reg, doc, path):
                c['pdfs_downloaded'] += 1
            else:
                c['skipped_download_failed'] += 1
                unparsed.append(f'{reg}: application PDF did not download')
                print(f'[{n}/{len(todo)}] {reg} download failed', file=sys.stderr)
                continue
        except Stop as e:
            stopped = str(e)
            print(f'STOP: {e}', file=sys.stderr)
            break
        try:
            txt = pdf_text(path)
        except Exception as e:
            txt = ''
            unparsed.append(f'{reg}: unreadable PDF ({e.__class__.__name__})')
        if len(txt.strip()) < 50:
            c['skipped_no_text_layer'] += 1  # Tesseract is not installed here: scans are counted and skipped
            print(f'[{n}/{len(todo)}] {reg} no text layer', file=sys.stderr)
            continue
        c['text_extracted'] += 1
        fein, people, skipped = parse_application(txt)
        if not people and not any(skipped.values()):
            ffein, people = parse_form_fields(path)  # the fillable paper form keeps answers in form fields
            fein = fein or ffein
            if people:
                c['form_fields_read'] += 1
        for k, v in skipped.items():
            c[f'people_skipped_{k}'] += v
        if fein:
            feins[reg] = fein
        if not people:
            c['no_officer_table'] += 1
            why = ', '.join(f'{v} {k}' for k, v in skipped.items() if v) or 'no officer table found'
            unparsed.append(f'{reg} ({doc["kind"]}, {doc["received"]}): no officers kept ({why})')
        for name, title in people:
            officers.append({'registration_number': reg, 'name': name, 'title': title, 'fetched_at': today})
        print(f'[{n}/{len(todo)}] {reg} {doc["kind"]} {doc["received"]}: {len(people)} people, '
              f'FEIN {"yes" if fein else "no"}', file=sys.stderr)
    c['officer_rows'] = len(officers)
    c['registrations_with_officers'] = len({o['registration_number'] for o in officers})
    c['feins_found'] = len(feins)
    for r in regs:
        if r['registration_number'] in feins:
            r['fein'] = feins[r['registration_number']]
    write_gz(reg_path, REG_COLS, regs)
    write_gz(os.path.join(out, 'fdacs_officers.csv.gz'), OFF_COLS, officers)
    log = {'fetched_at': today, 'county': county.title(), 'counts': c, 'unparsed': unparsed,
           'errors': cl.errors, 'seconds_between_requests': DELAY,
           'notes': ['One PDF per registration: the most recent uploaded Application (or renewal) on Check-A-Charity.',
                     'Only names and titles as filed are kept. Addresses, phones, emails and answers are not stored.',
                     'People marked "- Removed" on the application and anyone marked exempt from public records '
                     'are left out.',
                     'Scanned PDFs with no text layer are skipped (no OCR).']}
    if stopped:
        log['stopped_early'] = stopped
    with open(os.path.join(out, 'fdacs_pdf_log.json'), 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)
        f.write('\n')
    print(json.dumps(c), file=sys.stderr)
    if stopped:
        sys.exit(1)


# ---------- main ----------

def write_gz(path, cols, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, '') for c in cols})
    with gzip.GzipFile(path, 'wb', mtime=0) as f:
        f.write(buf.getvalue().encode('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--county', default='bay')
    ap.add_argument('--work', default=os.path.join(tempfile.gettempdir(), 'fdacs_work'))
    ap.add_argument('--limit', type=int)
    ap.add_argument('--out', help='output folder (default data/nonprofits/<county>)')
    ap.add_argument('--officers', action='store_true',
                    help='read officers and FEIN from uploaded application PDFs into the existing outputs')
    a = ap.parse_args()
    county = a.county.lower()
    if county not in COUNTY_CODES:
        sys.exit(f'unknown county {county}; add its dropdown code to COUNTY_CODES')
    work = os.path.join(a.work, county)
    os.makedirs(work, exist_ok=True)
    out = a.out or os.path.join(HERE, county)
    os.makedirs(out, exist_ok=True)
    today = dt.date.today().isoformat()
    if a.officers:
        return officers_pass(a, county, work, out, today)
    t0 = time.time()
    cl = Client()
    notes = []

    found, regs = parse_listing(listing_pages(cl, COUNTY_CODES[county], work))
    uniq = {}
    for r in regs:
        uniq.setdefault(r['registration_number'], r)
    regs = sorted(uniq.values(), key=lambda r: (r['name'], r['registration_number']))
    print(f'listing: {found} records found, {len(regs)} CH registrations parsed', file=sys.stderr)
    if found is not None and found != len(regs):
        notes.append(f'listing said {found} records but {len(regs)} CH registrations were parsed')
    if a.limit:
        regs = regs[:a.limit]

    ch = Charity(cl, work)
    rows, officers, captions, stopped, fetched = [], [], {}, None, 0
    for n, r in enumerate(regs, 1):
        reg = r['registration_number']
        try:
            page = ch.get(reg)
        except Stop as e:
            stopped = str(e)
            print(f'STOP: {e}', file=sys.stderr)
            break
        fetched += 1
        d = parse_detail(page, reg)
        for c in (d or {}).get('captions', []):
            captions[c] = captions.get(c, 0) + 1
        print(f'[{n}/{len(regs)}] {reg} {r["name"][:50]} {"ok" if d else "no Check-A-Charity record"}',
              file=sys.stderr)
        d = d or {}
        rows.append({
            'registration_number': reg, 'name': r['name'], 'dba': r['dba'], 'fein': '',
            'status': status_of(r['status_detail']), 'status_detail': r['status_detail'],
            'registration_date': r['issued'], 'expiration_date': r['expires'] or d.get('expiration_date', ''),
            'city': r['city'].title() if r['city'].isupper() else r['city'], 'state': r['state'], 'zip': r['zip'],
            'county': county.title(), 'phone': r['phone'], 'website': '',
            'fiscal_year_end': d.get('fiscal_year_end', ''), 'total_revenue': d.get('total_revenue', ''),
            'contributions': d.get('contributions', ''), 'government_grants': d.get('government_grants', ''),
            'program_expenses': d.get('program_expenses', ''),
            'fundraising_expenses': d.get('fundraising_expenses', ''),
            'management_expenses': d.get('management_expenses', ''),
            'total_expenses': d.get('total_expenses', ''), 'program_percent': d.get('program_percent', ''),
            'fundraising_consultants': d.get('fundraising_consultants', ''),
            'detail_url': CAC_URL if d else '', 'fetched_at': today,
        })
        for name, title in d.get('officers', []):
            officers.append({'registration_number': reg, 'name': name, 'title': title, 'fetched_at': today})

    write_gz(os.path.join(out, 'fdacs_registrations.csv.gz'), REG_COLS, rows)
    write_gz(os.path.join(out, 'fdacs_officers.csv.gz'), OFF_COLS, officers)
    notes += [
        'Listing: Business License Lookup, program CH, all statuses. registration_date is the "Issued" date '
        'shown there (the current registration period start, not the first registration).',
        'Financials: Check-A-Charity latest report; management_expenses is its "Administrative Expenses"; '
        'fiscal_year_end is the period end shown after "Revenue Source". The page shows one year only.',
        'Not shown on the public pages: FEIN, website, contributions, government grants, officers. Officers '
        'and directors appear only inside uploaded application PDFs, which are not downloaded.',
        'detail_url is the Check-A-Charity search page (records have no direct link; search the registration '
        'number).',
        'Street and email addresses are read but never stored.',
        f'Check-A-Charity section captions seen: {captions}',
    ]
    if stopped:
        notes.append(f'stopped early: {stopped}')
    log = {'fetched_at': today, 'county': county.title(), 'listing_results': found, 'details_fetched': fetched,
           'errors': cl.errors, 'seconds_between_requests': DELAY, 'notes': notes}
    with open(os.path.join(out, 'fdacs_fetch_log.json'), 'w', encoding='utf-8') as f:
        json.dump(log, f, indent=2)
        f.write('\n')
    print(f'wrote {len(rows)} registrations, {len(officers)} officers in {time.time() - t0:.0f}s '
          f'({cl.requests} requests)', file=sys.stderr)
    if stopped:
        sys.exit(1)


if __name__ == '__main__':
    main()
