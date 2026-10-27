"""Business names that are probably one company: the shared rules for donors, vendors and Sunbiz.

Three levels, from safest to loosest:
  1. same key: ids.vkey() ignores case, spacing, punctuation, '&'/'and', a leading 'The', legal suffixes and suffixes
     cut short by the elections office ('T K Vandy LLC' = 'TKVandy, LLC' = 'tkvandy'). Always one company.
  2. same Sunbiz filing: two spellings that data/sunbiz matched to the same Florida corporation document number by an
     exact or vendor-alias name match, or a name cut at the 30-character limit (not by a plural or short-prefix guess). Joined automatically, with the document number
     as evidence (sunbiz_groups).
  3. look-alike ("like"): one letter off, a plural, or one name is the start of the other (like_reason). Never joined
     automatically: build_entities.py lists them in vendor_review.json look_alike_names, an admin confirms or keeps them
     apart on /admin (Name matches), and export_name_decisions.py brings those calls back into the next build
     (name_decisions.json).
"""
import collections, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..')

# Sunbiz match methods that rest on the name itself, not on a guess. 'truncated_name' (only one Bay County filing starts
# with the name) counts only when the elections office cut the name at its 30-character limit; a short name like
# "Phoenix Construction" could be a company with no Bay County filing.
STRONG_SUNBIZ = {'exact', 'vendor_alias'}
_ROMAN = re.compile(r'(?:^|[^a-z])(i|ii|iii|iv|v|vi)$')


def lev(a, b, cap=3):
    """Edit distance (insert, delete, change one letter), stopping early once it passes cap."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def _digits(k):
    return re.findall(r'\d+', k)


def like_reason(ka, kb):
    """Why two different keys look like one company, or None. Keys are ids.vkey() values."""
    if ka == kb:
        return None
    a, b = sorted((ka, kb), key=len)
    if len(a) < 6 or _digits(a) != _digits(b):
        return None
    if b in (a + 's', a + 'es'):
        return 'plural'
    if b.startswith(a):
        rest = b[len(a):]
        # 'Blairstone I' / 'Blairstone II', 'Phase 1' / 'Phase 2': numbered siblings, not variants
        if re.fullmatch(r'i{1,3}|iv|v', rest) or _ROMAN.search(a) and re.fullmatch(r'i+', rest):
            return None
        if len(a) >= 12:  # 'Centennial' / 'Centennial Bank' is too short to call a cut-off name
            return 'shortened'
        return None
    d = lev(a, b)
    if d == 1 and len(a) >= 6 or d == 2 and len(a) >= 12:
        # one letter apart only in a trailing number word ('i' vs 'ii') is a sibling, not a typo
        if _ROMAN.search(a) and _ROMAN.search(b) and a.rstrip('iv') == b.rstrip('iv'):
            return None
        return 'spelling'
    return None


def like_pairs(keys):
    """[(key_a, key_b, reason)] for every look-alike pair among keys (an iterable of vkeys). Keys are compared within
    blocks that share their first three letters, so a spelling slip in the first letters is not caught."""
    block = collections.defaultdict(list)
    for k in sorted(set(keys)):
        if len(k) >= 6:
            block[k[:3]].append(k)
    out = []
    for ks in block.values():
        for i, a in enumerate(ks):
            for b in ks[i + 1:]:
                r = like_reason(a, b)
                if r:
                    out.append((a, b, r))
    return out


def sunbiz_groups(key):
    """{document number: (entity name, {key: [spellings]})} for every Sunbiz filing that two or more spellings with
    different keys were matched to by name. key is ids.vkey."""
    out = {}
    import glob
    for fp in sorted(glob.glob(os.path.join(DATA, 'sunbiz', '*', 'business_donor_sunbiz.json'))):
        for r in json.load(open(fp)).get('rows') or []:
            doc = r.get('sunbiz_doc_number')
            m = r.get('match_method')
            if not doc or not (m in STRONG_SUNBIZ or m == 'truncated_name' and len(r['contributor'].strip()) >= 28):
                continue
            ent, ks = out.setdefault(doc, (r.get('sunbiz_entity_name'), collections.defaultdict(set)))
            ks[key(r['contributor'])].add(r['contributor'].strip())
    return {d: (e, {k: sorted(v) for k, v in ks.items()}) for d, (e, ks) in out.items() if len(ks) > 1}


def decisions():
    """Admin calls on look-alike pairs ({'confirmed': [...], 'rejected': [...]}, each {a_key, b_key, ...}), written by
    export_name_decisions.py. Missing file: no calls yet."""
    try:
        d = json.load(open(os.path.join(HERE, 'name_decisions.json')))
    except FileNotFoundError:
        return {'confirmed': [], 'rejected': []}
    return {'confirmed': d.get('confirmed') or [], 'rejected': d.get('rejected') or []}


class Joins:
    """Union-find over keys. find(k) is the group's key; the first key added to a group stays its key."""

    def __init__(self):
        self.up = {}

    def find(self, k):
        while self.up.get(k, k) != k:
            self.up[k] = self.up.get(self.up[k], self.up[k])
            k = self.up[k]
        return k

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra not in self.up and rb in self.up:  # an existing group keeps its key when a new key joins it
            ra, rb = rb, ra
        if ra != rb:
            self.up[rb] = ra
        self.up.setdefault(ra, ra)
        return ra

    def groups(self):
        g = collections.defaultdict(set)
        for k in self.up:
            g[self.find(k)].add(k)
        return {r: ks for r, ks in g.items() if len(ks) > 1}
