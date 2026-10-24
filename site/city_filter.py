"""The city filter every page shares.

One control, at the top of a page, picks a government (Bay County, the school district or a city). Its value is
always a GOVS key (county, schools, pc, pcb, lh, cw, sp, parker, mb) and it is written to the link as ?gov=<key>.
The choice is remembered, so moving to another page keeps the same city. site_helpers.js (BCM.city) does the
work in the browser; this module writes the markup and the alias table it reads.

    city_bar(keys)                  the bar itself, with only the governments that have data on the page
    gkey('Panama City, City of')    -> 'pc'   (any spelling a dataset uses, CRA codes too)
    data_g('pc', 'pcb')             -> ' data-g="pc pcb"'   (for rows the browser should hide by city)
    link_attrs(key)                 data-alias for a page's own <option>, so ?gov=pc selects it

Rows of a page that has no script of its own carry data-g="<key> ..."; with city_bar(..., hide=True) the
browser hides the ones that don't match. Rows without data-g (countywide items) always show.
"""
import html, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'data', 'entities'))
from govs import GOVS, BY_KEY, CRA_NAME  # noqa: E402

KEYS = [g['key'] for g in GOVS]
# the CRA dashboards use their own two-letter codes
CRA_CODE = {g['key']: g['cra'] for g in GOVS if g.get('cra')}
LABEL = {g['key']: g['short'] for g in GOVS}


def _loose(s):
    s = str(s or '').lower().replace('&', ' and ')
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'^city of |, city of$|\bbocc\b', ' ', s.strip())
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def _aliases():
    out = {k: set() for k in KEYS}
    for g in GOVS:
        k = g['key']
        for f in ('key', 'slug', 'short', 'name', 'tax', 'auth', 'debt', 'audit', 'contracts', 'fees', 'surtax', 'util'):
            if g.get(f):
                out[k].add(g[f])
        out[k].update(g.get('fema') or [])
        if g.get('cra'):
            out[k].update([g['cra'], g['cra'].upper(), CRA_NAME[g['cra']], f'{g["short"]} CRA'])
    try:
        import ids
        for e in ids.governments():
            k = e['id'] if e['id'] in out else (e.get('parent') if e.get('parent') in out else None)
            if k:
                out[k].update([e['id'], e['name'], e['short']] + e.get('aliases', []))
    except Exception:  # the entity table is optional at build time
        pass
    return out


ALIASES = _aliases()
_IDX = {}
for _k in KEYS:
    for _a in ALIASES[_k]:
        _IDX.setdefault(_loose(_a), _k)
for _k in KEYS:  # the plain short name always wins ("Panama City" is never Panama City Beach)
    _IDX[_loose(LABEL[_k])] = _k


def gkey(name):
    """A GOVS key for any name or code a dataset uses, or None."""
    if not name:
        return None
    if name in BY_KEY:
        return name
    n = _loose(name)
    if n in _IDX:
        return _IDX[n]
    n2 = re.sub(r'\s+(cra|community redevelopment agency|commission|council|board)$', '', n)
    return _IDX.get(n2)


def data_g(*keys):
    ks = [k for k in dict.fromkeys(gkey(k) for k in keys if k) if k]
    return f' data-g="{" ".join(ks)}"' if ks else ''


def by_city(values):
    """data-by for a figure that changes with the city: values = {'': countywide html, 'pc': ..., ...}.
    The first value shows before the script runs; a missing city keeps the countywide value."""
    v = {k: ('' if x is None else str(x)) for k, x in values.items() if x is not None}
    return f" data-by='{html.escape(json.dumps(v, separators=(',', ':')), quote=True)}'"


def link_attrs(key):
    """data-alias for an <option> whose value isn't a GOVS key, so BCM can match ?gov=<key> to it."""
    return f' data-alias="{key}"' if key else ''


def js_table():
    """The alias table site.js carries (window.BCM_CITIES)."""
    rows = []
    for g in GOVS:
        k = g['key']
        al = sorted({_loose(a) for a in ALIASES[k]} - {''})
        rows.append({'k': k, 's': g['short'], 'slug': g['slug'], 'kind': g['kind'], 'cra': g.get('cra') or '', 'al': al})
    return 'window.BCM_CITIES=' + json.dumps(rows, separators=(',', ':')) + ';\n'


def city_bar(keys=None, legacy='', hide=False, label='Government', note='', all_label='All governments', es=False, fixed=None, extra=''):
    """The filter bar at the top of a page. keys: the governments that have data here (in GOVS order).
    legacy: older link params this page used for the same thing ("g", "cra"), read once and turned into ?gov=.
    hide: hide [data-g] rows on the page that don't match. A page's other controls are moved into the bar
    when they carry data-scope (year first), so every page's filters sit in one place."""
    ks = [k for k in KEYS if keys is None or k in keys]
    if es:
        label, all_label = ('Gobierno' if label == 'Government' else label), ('Todos los gobiernos' if all_label == 'All governments' else all_label)
    opts = f'<option value="">{html.escape(all_label)}</option>' + ''.join(
        f'<option value="{k}">{html.escape(LABEL[k])}</option>' for k in ks)
    attrs = (f' data-legacy="{html.escape(legacy)}"' if legacy else '') + (' data-city-hide' if hide else '') + (f' data-city-fixed="{fixed}"' if fixed else '')
    if fixed:
        opts = f'<option value="">{html.escape(all_label)}</option>' + ''.join(
            f'<option value="{k}"{" selected" if k == fixed else ""}>{html.escape(LABEL[k])}</option>' for k in ks)
    nt = f'<span class="sc-note muted">{note}</span>' if note else ''
    return f'''<div class="scope" data-scope role="group" aria-label="{'Filtros' if es else 'Filter this page'}">
  <label class="sc-f sc-city"><span>{html.escape(label)}</span><select id="scCity" data-city{attrs} aria-label="{html.escape(label)}">{opts}</select></label>
  <div class="sc-slot" data-scope-slot></div>{nt}{extra}
</div>'''


def scope(html_str, label='Year'):
    """Mark a page control for the bar: wraps it in a labelled field and data-scope so BCM moves it in."""
    return f'<label class="sc-f" data-scope><span>{html.escape(label)}</span>{html_str}</label>'
