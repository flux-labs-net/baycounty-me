"""One name per company across every BayCounty.me record (contracts, change orders, emergency purchases,
check registers, campaign donors).

Agendas, registers and campaign reports spell the same company many ways ("C.W. Roberts Contracting, Inc.",
"CW ROBERTS CONT", "CW Roberts"). resolve(raw) returns (id, display name, type) for any spelling:
  1. names are reduced to a key (lowercase, punctuation and suffixes such as Inc/LLC dropped, see key());
  2. the key is looked up in VENDORS below, where each company lists the keys of all its spellings;
  3. a key not listed becomes its own company, so new records still work before anyone reviews them.
Merges below were reviewed by hand. Only merge spellings that are clearly the same company; firms that share
a word (Anderson Columbia vs Anderson Construction, RJ Gorman Marine vs RJ Gorman Contracting) stay apart.

type: 'business' (default), 'public' (another government, or a public risk pool owned by governments),
'unnamed' (the record doesn't say who got the work).
"""
import os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'entities'))
import ids  # noqa: E402

SUFFIX = r'\b(inc|llc|co|corp|corporation|company|the|of|lp|llp|pa|pllc|ltd|dba|d b a)\b'


def key(name):
    v = (name or '').lower().replace('&', ' and ')
    v = re.sub(r'\(.*?\)', ' ', v)
    v = re.sub(r"[.,'/;]", ' ', v)
    v = re.sub(SUFFIX, ' ', v)
    v = re.sub(r'\band\b', ' ', v)
    return re.sub(r'\s+', ' ', v).strip()


# id: (display name, [keys of every spelling], type)
VENDORS = {
    '850-construction': ('850 Construction Services', ['850 constructio', '850 construction services'], 'business'),
    'american-sand': ('American Sand & Asphalt Paving', ['american sand', 'american sand asphalt', 'american sand asphalt paving',
                                                         'american sand asphalt pavi'], 'business'),
    'anderson-columbia': ('Anderson Columbia Co.', ['anderson columbia'], 'business'),
    'anderson-construction': ('Anderson Construction Co. of North Florida', ['anderson construction', 'anderson construction north florida'], 'business'),
    'arris': ('ARRIS General Contractors', ['arris general', 'arris general contractors'], 'business'),
    'barge': ('Barge Design Solutions', ['barge design solutions'], 'business'),
    'bayou-builders': ('Bayou Builders of Bay County', ['bayou builders bay', 'bayou builders bay county'], 'business'),
    'bcl': ('BCL Civil Contractors', ['bcl civil contr', 'bcl civil contractors'], 'business'),
    'behar-peteranecz': ('Behar Peteranecz', ['behar peteranecz'], 'business'),
    'bgn': ('BGN Contractors (Gage Golden Construction)', ['bgn contractors', 'gage golden construction', 'gage golden construction bgn contractors'], 'business'),
    'black-veatch': ('Black & Veatch', ['black veatch'], 'business'),
    'cbc': ('CBC Construction', ['cbc constructio', 'cbc construction'], 'business'),
    'cdr-maguire': ('CDR Maguire', ['cdr maguire', 'cdr maguire cdr emergency management'], 'business'),
    'charles-white': ('Charles N. White Construction', ['charles n white construction'], 'business'),
    'coastal-parasail': ('Coastal Parasail', ['coastal parasail'], 'business'),
    'core-main': ('Core & Main', ['core main'], 'business'),
    'culpepper': ('Culpepper Construction', ['culpepper', 'culpepper const', 'culpepper construction'], 'business'),
    'cw-roberts': ('C.W. Roberts Contracting', ['c w roberts', 'c w roberts contracting', 'cw roberts', 'cw roberts cont'], 'business'),
    'davison': ('Davison Fuels & Oil', ['davison fuels i', 'davison fuels oil'], 'business'),
    'dewberry': ('Dewberry Engineers', ['dewberry', 'dewberry engineering', 'dewberry engineers'], 'business'),
    'ecsc': ('ECSC (Emerald Coast Site Construction)', ['ecsc', 'emerald coast site construction'], 'business'),
    'empire-pipe': ('Empire Pipe and Supply', ['empire pipe supply'], 'business'),
    'emr': ('EMR', ['emr'], 'business'),
    'fpl': ('Florida Power & Light', ['florida power light', 'fpl - florida p', 'fpl'], 'business'),
    'gcuc': ('Gulf Coast Utility Contractors', ['gulf coast util', 'gulf coast utility construction', 'gulf coast utility contractor',
                                                'gulf coast utility contractors', 'gulf coast utility contractors staline waterworks'], 'business'),
    'gortemoller': ('Gortemoller Engineering', ['gortemoller engineering'], 'business'),
    'halff': ('Halff Associates', ['halff', 'halff associates'], 'business'),
    'hall-contracting': ('Hall Contracting & Construction', ['hall contracting construction'], 'business'),
    'harders': ('H.G. Harders & Sons', ['h g harders sons', 'hg harder s son'], 'business'),
    'hydra': ('Hydra Services', ['hydra service', 'hydra services'], 'business'),
    'imageworks': ('Imageworks Commercial Interiors', ['imageworks c317', 'imageworks commercial interiors'], 'business'),
    'inland': ('Inland Construction and Engineering', ['inland construction', 'inland construction engineering'], 'business'),
    'mainline': ('Mainline Construction', ['mainline construction'], 'business'),
    'marshall-brothers': ('Marshall Brothers Construction & Engineering', ['marshall brothers', 'marshall bothers', 'marshall brothers construction',
                                                                         'marshall brothers construction engineering'], 'business'),
    'metric': ('Metric Engineering', ['metric engineering'], 'business'),
    'mott-macdonald': ('Mott MacDonald', ['mott macdonald', 'mott macdonald florida'], 'business'),
    'mr-fence': ('Mr. Fence of Florida', ['mr fence', 'mr fence florida'], 'business'),
    'ovivo': ('Ovivo USA', ['ovivo usa'], 'business'),
    'panhandle-engineering': ('Panhandle Engineering', ['panhandle engin', 'panhandle engineering'], 'business'),
    'phoenix': ('Phoenix Construction Services', ['phoenix constru', 'phoenix construction services'], 'business'),
    'reeves-shaw': ('Reeves & Shaw Construction', ['reeves shaw construction'], 'business'),
    'rj-gorman-marine': ('RJ Gorman Marine Construction', ['r j gorman marine construction', 'rj gorman marine construction', 'rj gorman marine'], 'business'),
    'roberts-and-roberts': ('Roberts and Roberts', ['roberts roberts', 'roberts rober'], 'business'),
    'royal-american': ('Royal American Construction', ['royal american construction'], 'business'),
    'sj-electro': ('S.J. Electro Systems (Primax)', ['s j electro systems primax', 'sj electro systems primex'], 'business'),
    'southeastern-outdoor': ('Southeastern Outdoor Management', ['southeastern outdoor management', 'southeastern outdoor mgmt'], 'business'),
    'southern-construction': ('Southern Construction Services', ['southern construction', 'southern construction service', 'southern construction services'], 'business'),
    'tb-landmark': ('TB Landmark Construction', ['t b landmark construction', 'tb landmark construction'], 'business'),
    'telemetry': ('Telemetry and Process Control', ['telemetry process con', 'telemetry process control'], 'business'),
    'ten-8': ('Ten-8 Fire & Safety', ['ten-8', 'ten-8 fire safety', 'leasing 2 ten-8 fire safety'], 'business'),
    'tk-vandy': ('TK Vandy', ['t k vandy', 'tk vandy', 'tkvandy'], 'business'),
    'weeks-marine': ('Weeks Marine', ['weeks marine'], 'business'),
    'williams-communications': ('Williams Communications', ['williams communications'], 'business'),
    'florida-architects': ('Florida Architects', ['florida architects'], 'business'),
    # public bodies and government-owned risk pools: not contractor wins
    'fdot': ('Florida Department of Transportation', ['florida department transportation'], 'public'),
    'volusia-sheriff': ("Volusia County Sheriff's Office", ['volusia county sheriff s office'], 'public'),
    'flc': ('Florida League of Cities', ['florida league cities'], 'public'),
    'pgit': ('Preferred Governmental Insurance Trust', ['preferred governmental insurance trust'], 'public'),
}

_BY_KEY = {k: vid for vid, (_, ks, _) in VENDORS.items() for k in ks}
_PUBLIC = re.compile(r'department of|^city of|^bay county\b|county (board|commission)|^state of|authority$|sheriff|school board', re.I)
_UNNAMED = re.compile(r'^(not named|various|multiple)', re.I)


_ENT = {}


def _entities():
    """Every spelling in data/entities/vendors.json -> (id, name, type). That file is built from this module's VENDORS
    (its ids defer to these), so the two resolvers agree; this fallback covers spellings only the entity build joined."""
    if not _ENT:
        import json, os
        try:
            d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'entities', 'vendors.json')))
        except (FileNotFoundError, ValueError):
            d = {'vendors': []}
        for v in d['vendors']:
            t = VENDORS[v['id']][2] if v['id'] in VENDORS else 'business'
            for a in v['aliases']:
                _ENT.setdefault(a.strip().lower(), (v['id'], v['name'], t))
        _ENT.setdefault('', None)
    return _ENT


def resolve(raw):
    """(id, display name, type) for any spelling of a vendor name."""
    raw = (raw or '').strip()
    if not raw or _UNNAMED.match(raw):
        return ('unnamed', 'Not named in the record', 'unnamed')
    k = key(raw)
    vid = _BY_KEY.get(k)
    if vid:
        n, _, t = VENDORS[vid]
        return (vid, n, t)
    ent = _entities().get(raw.lower())  # data/entities/vendors.json: spellings joined there (truncations, OCR errors, typos)
    if ent:
        return ent
    clean = re.sub(r'\s*\(.*?\)\s*', ' ', raw).strip()
    return (re.sub(r'[^a-z0-9]+', '-', k).strip('-') or 'unknown', ids.biz_case(clean), 'public' if _PUBLIC.search(raw) else 'business')
