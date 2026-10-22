"""Spanish pages (/es, /es/mi-direccion, /es/glosario, /es/solicitar-registros, /es/impuestos,
/es/tarifas-y-facturas, /es/exenciones, /es/elecciones, /es/reuniones).

Translations live in i18n/: es_glossary.json (term-for-term), es_address.json (ordered English→Spanish
phrase pairs applied to the My Address page and its script), es_common.json (strings shared by every /es
page, incl. window.BCM_I18N labels for site.js and report.js) and one es_<page>.json per translated page.
Each page reuses its English renderer: label dicts in the English module are swapped for Spanish ones
while it renders (patched()), then the leftover English is replaced phrase by phrase (unmatched pairs are
printed at build time, so a change to the English page shows up). The rest of the site is English;
Spanish pages link to it and say so.
"""
import contextlib, html, json, os, re, tempfile
from glossary import GROUPS, TERMS

HERE = os.path.dirname(os.path.abspath(__file__))
I18N = os.path.join(HERE, 'i18n')
e = html.escape

ES_MENU = [
    {'label': 'Inicio', 'href': '/es'},
    {'label': 'Mi dirección', 'href': '/es/mi-direccion'},
    {'label': 'Dinero público', 'groups': [
        {'group': 'Impuestos y tarifas', 'items': [
            {'label': 'Sus impuestos', 'href': '/es/impuestos', 'desc': 'A dónde va cada dólar de su factura'},
            {'label': 'Tarifas y facturas', 'href': '/es/tarifas-y-facturas', 'desc': 'Cargos fijos, agua, alcantarillado y basura'},
            {'label': 'Exenciones', 'href': '/es/exenciones', 'desc': 'Quién paga menos impuesto a la propiedad'},
        ]},
    ]},
    {'label': 'Participe', 'groups': [
        {'group': 'Su voz', 'items': [
            {'label': 'Elecciones 2026', 'href': '/es/elecciones', 'desc': 'Candidatos y dinero de campaña'},
            {'label': 'Reuniones públicas', 'href': '/es/reuniones', 'desc': 'Cuándo y dónde se reúne cada junta'},
            {'label': 'Solicitar registros', 'href': '/es/solicitar-registros', 'desc': 'Pida un registro público'},
        ]},
    ]},
    {'label': 'Glosario', 'href': '/es/glosario'},
]

# Spanish page -> its English twin (hreflang alternates and the language switch link)
ES_ALT = {'/es': '/', '/es/mi-direccion': '/my-address', '/es/glosario': '/glossary', '/es/solicitar-registros': '/records-request',
          '/es/impuestos': '/public-money/tax-dollars', '/es/tarifas-y-facturas': '/public-money/fees-and-bills',
          '/es/exenciones': '/public-money/exemptions', '/es/elecciones': '/elections', '/es/reuniones': '/meetings'}

ES_FOOTER = [
    ('puts Bay County, Florida public records in plain view: maps, money, and the documents behind them.', 'reúne los registros públicos del condado de Bay, Florida, en un solo lugar: mapas, dinero y los documentos que los respaldan.'),
    ('Found an error or have a record to add?', '¿Encontró un error o tiene un registro que agregar?'),
    ('Send a correction</a> or email', 'Envíe una corrección</a> (en inglés) o escriba a'),
    ("What's new", 'Novedades'),
    ('Sources and method', 'Fuentes y método'),
    ('Powered by', 'Desarrollado por'),
    ('Skip to content', 'Saltar al contenido'),
    ('<span class="sr">Menu</span>', '<span class="sr">Menú</span>'),
    ('aria-label="Main"', 'aria-label="Principal"'),
    ('aria-label="Theme: match system"', 'aria-label="Tema: igual que el sistema"'),
    ('<span class="theme-lbl">System</span>', '<span class="theme-lbl">Sistema</span>'),
]
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def prune(built):
    """Drop menu items and alternates for Spanish pages not in this build (e.g. /es/elecciones before the data exists)."""
    for k in [k for k in ES_ALT if k not in built or ES_ALT[k] not in built]:
        del ES_ALT[k]
    for m in ES_MENU:
        for g in m.get('groups', []):
            g['items'] = [i for i in g['items'] if i['href'] in built]
    ES_MENU[:] = [m for m in ES_MENU if 'href' in m or any(g['items'] for g in m['groups'])]


def es_date(m):
    """'Oct 20, 2026' (or an re match of it) -> '20 de octubre de 2026'."""
    if isinstance(m, str):
        m = re.match(r'([A-Z][a-z]{2})[a-z]*\.? (\d{1,2}),? (\d{4})', m)
    return f'{int(m.group(2))} de {MONTHS[EN_MONTHS.index(m.group(1)[:3])]} de {m.group(3)}'


def common():
    return json.load(open(os.path.join(I18N, 'es_common.json')))


def localize_chrome(page_html):
    """Translate the shared header/footer of an /es page, and give site.js and report.js their Spanish labels."""
    for a, b in ES_FOOTER:
        page_html = page_html.replace(a, b)
    page_html = re.sub(r'Page updated ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})', lambda m: 'Página actualizada el ' + es_date(m), page_html)
    labels = json.dumps(common()['bcm'], ensure_ascii=False)
    page_html = page_html.replace('<script src="/assets/site.js" defer></script>', f'<script>window.BCM_I18N={labels}</script>\n<script src="/assets/site.js" defer></script>', 1)
    page_html = page_html.replace('<script src="/assets/report.js" defer></script>', '<script src="/assets/report.es.js" defer></script>', 1)
    return page_html.replace('<meta property="og:locale" content="en_US">', '<meta property="og:locale" content="es_US">')


def updated_key(path):
    """Changelog path that dates an /es page: a translated data page is as fresh as its English twin."""
    return ES_ALT[path] if path in ES_ALT and path not in ('/es', '/es/mi-direccion', '/es/glosario', '/es/solicitar-registros') else path


REPORT_ES = [
    ("toLocaleDateString('en-US'", "toLocaleDateString('es-US'"),
    ("'Report exported '", "'Informe exportado el '"),
    ("{text: 'POWERED BY'", "{text: 'DESARROLLADO POR'"),
    ("'Powered by Flux Labs'", "'Desarrollado por Flux Labs'"),
    ("'Public records · sources linked in the report · corrections: hello@fluxlabs.net'", "'Registros públicos · fuentes enlazadas en el informe · correcciones: hello@fluxlabs.net'"),
    ("`Page ${page} of ${pages}`", "`Página ${page} de ${pages}`"),
    ("'Building PDF…'", "'Creando el PDF…'"),
    ("alert('Sorry, the PDF could not be built. Your browser\\'s Print > Save as PDF still works.')", "alert('No se pudo crear el PDF. Todavía puede usar Imprimir > Guardar como PDF en su navegador.')"),
]


def write_report_es(out_dir):
    """assets/report.es.js: the PDF export with Spanish cover and footer text."""
    js, miss = apply_pairs(open(os.path.join(HERE, 'report.js')).read(), REPORT_ES)
    if miss:
        print('es report.js: unmatched pairs', miss)
    open(os.path.join(out_dir, 'assets', 'report.es.js'), 'w').write(js)


@contextlib.contextmanager
def patched(mod, **attrs):
    """Swap module-level names (label dicts, small helpers) while an English renderer runs."""
    old = {k: getattr(mod, k) for k in attrs}
    for k, v in attrs.items():
        setattr(mod, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(mod, k, v)


def page_pairs(name):
    return json.load(open(os.path.join(I18N, f'es_{name}.json')))


def translate(text, pairs, label, quiet=()):
    """Apply ordered phrase pairs, then the shared ones; report pairs that no longer match the English page."""
    text, miss = apply_pairs(text, pairs)
    miss = [m for m in miss if not any(m.startswith(q[:60]) for q in quiet)]
    if miss:
        print(f'es {label}: {len(miss)} unmatched pairs', miss[:4])
    for a, b in common()['html']:
        text = text.replace(a, b)
    return text


def money_es(n, short=False):
    """$ amount in Spanish words: 1.2e9 -> '$1.20 mil millones', 4.5e6 -> '$4.5 millones', 413000 -> '$413 mil'."""
    if n is None:
        return '—'
    a = abs(n)
    if a >= 1e9:
        return f'${n/1e9:,.2f} mil millones'
    if a >= 1e6:
        return f'${n/1e6:,.1f} millones'
    if a >= 1e4:
        return f'${n/1e3:,.0f} mil'
    return f'${n:,.0f}'


def data_stamp(page, twin):
    """'Data updated Oct 20, 2026' -> Spanish, dated like the English twin."""
    from updates import last_updated, nice
    return re.sub(r'Data updated [A-Z][a-z]{2} \d{1,2}, \d{4}', 'Datos actualizados el ' + es_date(nice(last_updated(twin))), page)


def _pairs(kind):
    return json.load(open(os.path.join(I18N, 'es_address.json')))[kind]


def apply_pairs(text, pairs):
    missed = []
    for a, b in pairs:
        if a in text:
            text = text.replace(a, b)
        else:
            missed.append(a[:60])
    return text, missed


# Data-level fee labels shown on the tax card
NAV_ES = {
    'Bay County stormwater fee': 'Tarifa de aguas pluviales del condado de Bay',
    'Bay County stormwater fee (commercial)': 'Tarifa de aguas pluviales del condado de Bay (comercial)',
    'Street lighting assessment': 'Contribución especial de alumbrado público',
    'Road improvement assessment': 'Contribución especial para mejoras de calles',
    'Pier Park area assessment': 'Contribución especial del área de Pier Park',
    'Panama City fire assessment': 'Contribución especial de bomberos de Panama City',
    'Panama City Beach fire assessment': 'Contribución especial de bomberos de Panama City Beach',
    'Panama City Beach stormwater assessment': 'Contribución especial de aguas pluviales de Panama City Beach',
    'Front Beach Road CRA assessment': 'Contribución especial de la CRA de Front Beach Road',
    'Lynn Haven stormwater assessment': 'Contribución especial de aguas pluviales de Lynn Haven',
    'Springfield fire assessment': 'Contribución especial de bomberos de Springfield',
    'Community development district assessment': 'Contribución del distrito de desarrollo comunitario',
    'Special district assessment': 'Contribución de distrito especial',
    'Lighting district assessment': 'Contribución del distrito de alumbrado',
    # tax groups in the bill breakdown
    'Schools': 'Escuelas', 'Your city': 'Su ciudad', 'County fire & mosquito': 'Bomberos y mosquitos del condado', 'Special districts': 'Distritos especiales',
}


EXTRA_JS = [
    (' for school taxes${t.nonOther', ' para impuestos escolares${t.nonOther'), ('for city and district taxes', 'para impuestos de la ciudad y de distritos'),
    ('No property tax is owed on this home.', 'Esta vivienda no paga impuesto a la propiedad.'), ('About exemptions →', 'Sobre las exenciones (en inglés) →'),
    ("['Homestead', t.h1]", "['Exención de vivienda principal (homestead)', t.h1]"),
    ("['Additional homestead', t.second]", "['Exención adicional de vivienda principal', t.second]"),
    ("['Other exemptions', t.other]", "['Otras exenciones', t.other]"),
    ("The kinds of other exemptions aren't shown, to protect owners' privacy. Owners can see theirs on the <a href=\"${PA_URL}\" target=\"_blank\" rel=\"noopener\">Property Appraiser's site</a>.",
     "No mostramos de qué tipo son las otras exenciones, para proteger la privacidad de los dueños. Cada dueño puede ver las suyas en el <a href=\"${PA_URL}\" target=\"_blank\" rel=\"noopener\">sitio del Tasador de Propiedades (Property Appraiser)</a>."),
    ("' <span class=\"muted small\">(includes homestead)</span>'", "' <span class=\"muted small\">(incluye homestead)</span>'"),
]


def es_addr_page(out_dir):
    from addr_page import addr_page
    page = addr_page(out_dir)  # writes the English assets/address.js
    page, miss_h = apply_pairs(page, _pairs('html'))
    js = open(os.path.join(out_dir, 'assets', 'address.js')).read()
    from addr_page import ADDR_TXT
    es_txt = json.load(open(os.path.join(I18N, 'es_address.json')))['txt']
    en_txt = json.dumps(ADDR_TXT, ensure_ascii=False, separators=(',', ':'))
    if en_txt not in js or set(es_txt) != set(ADDR_TXT):
        print('es address: UI text block out of sync with addr_page.ADDR_TXT', sorted(set(ADDR_TXT) ^ set(es_txt)))
    js = js.replace(en_txt, json.dumps({**ADDR_TXT, **es_txt}, ensure_ascii=False, separators=(',', ':')))
    pairs =[x for x in _pairs('js') if x[0] != '(${usd(t.school)} for school taxes)']
    js, miss_j = apply_pairs(js, pairs + EXTRA_JS)
    for a, b in NAV_ES.items():
        js = js.replace(json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False))
    # in-site links from the script point at English pages; keep them, but send glossary/records to Spanish
    js = js.replace("'/glossary#", "'/es/glosario#").replace('"/glossary#', '"/es/glosario#')
    open(os.path.join(out_dir, 'assets', 'address.es.js'), 'w').write(js)
    if miss_h or miss_j:
        print('es address: unmatched pairs', len(miss_h), len(miss_j), (miss_h + miss_j)[:5])
    page = page.replace('/assets/address.js', '/assets/address.es.js')
    note = '<p class="note small">Los nombres de agencias, distritos y escuelas aparecen como los publica el condado, en inglés. Los enlaces a otras secciones llevan al sitio en inglés.</p>'
    return page.replace('<section class="tx-sec method"', note + '\n  <section class="tx-sec method"', 1)


def glossary_es():
    return json.load(open(os.path.join(I18N, 'es_glossary.json')))


def glossary_es_terms():
    g = glossary_es()
    out = {t['id']: {'term': g['terms'].get(t['id'], {}).get('term') or t['term'], 'simple': g['terms'].get(t['id'], {}).get('simple') or t['simple']} for t in TERMS}
    out.update({t['id']: {'term': t['term'], 'simple': t['simple']} for t in g.get('extra', [])})  # Spanish-only terms used by /es pages
    return out


def es_glossary_page():
    g = glossary_es()
    gl = {**g['groups'], **dict(g.get('extra_groups', []))}
    groups = list(GROUPS) + [(k, v) for k, v in g.get('extra_groups', [])]
    terms = list(TERMS) + g.get('extra', [])
    jump = ''.join(f'<a href="#g-{k}">{e(gl.get(k, label))}</a>' for k, label in groups)
    out = [f'''<div class="page prose glossary">
  <span class="eyebrow">Glosario</span>
  <h1>Guía en lenguaje sencillo</h1>
  <p class="lede">El dinero público viene con mucha jerga. Aquí está cada término de este sitio, explicado primero de forma sencilla y luego con más detalle. En todo el sitio, una palabra con subrayado punteado se puede tocar para ver su explicación corta.</p>
  <nav class="g-jump" aria-label="Secciones del glosario">{jump}</nav>''']
    for k, label in groups:
        out.append(f'<section class="g-group" id="g-{k}"><h2>{e(gl.get(k, label))}</h2>')
        for t in [t for t in terms if t['group'] == k]:
            s = g['terms'].get(t['id'], {})
            term, simple, more, ex = (s.get(f) if s.get(f) is not None else t[f] for f in ('term', 'simple', 'more', 'example'))
            out.append(f'<article class="g-term" id="{t["id"]}"><h3>{e(term)}</h3><p class="g-simple">{e(simple)}</p>'
                       + (f'<p class="g-more">{e(more)}</p>' if more else '')
                       + (f'<p class="g-ex"><b>Ejemplo:</b> {e(ex)}</p>' if ex else '') + '</article>')
        out.append('</section>')
    out.append('</div>')
    return '\n'.join(out)


ES_SUGGEST_T = {
    'Check registers, FY2023': 'Registros de cheques, año fiscal 2023',
    'County manager contract': 'Contrato del administrador del condado',
    'FY2026 and FY2027 budget hearing minutes': 'Actas de las audiencias de presupuesto 2026 y 2027',
    'Tourist Development Plan': 'Plan de Desarrollo Turístico',
    'AshBritt debris contract': 'Contrato de escombros con AshBritt',
    'Front Beach Road CRA agreement': 'Acuerdo de la CRA de Front Beach Road',
    'Board meeting minutes': 'Actas de las reuniones de la Junta Escolar',
    'Final FY2025-26 budget': 'Presupuesto final 2025-26',
    'Half-cent project list': 'Lista de proyectos del medio centavo',
    'Contracts over $100,000': 'Contratos de más de $100,000',
    'Check registers': 'Registros de cheques',
    'City manager pay': 'Salario del administrador de la ciudad',
    'CRA payments to vendors': 'Pagos de la CRA a proveedores',
    '$150M Series 2023 note': 'Préstamo de $150 millones, Serie 2023',
    'Martin Theatre contracts': 'Contratos del Teatro Martin',
    'Council minutes, 2024': 'Actas del Concejo, 2024',
    'Front Beach Road Segment 3 contract': 'Contrato del Segmento 3 de Front Beach Road',
    'Residential garbage rate': 'Tarifa residencial de basura',
    'CRA bond documents': 'Documentos de bonos de la CRA',
    'Check registers, FY2026': 'Registros de cheques, año fiscal 2026',
    'FY2026-27 budget': 'Presupuesto 2026-27',
    'Commission seat terms': 'Períodos de los comisionados',
    'CRA budget, FY2025-26': 'Presupuesto de la CRA, 2025-26',
    'Adopted budget': 'Presupuesto aprobado',
    'Contracts over $50,000': 'Contratos de más de $50,000',
    'CRA annual reports': 'Informes anuales de la CRA',
    'Budget hearing minutes': 'Actas de las audiencias de presupuesto',
    'Contracts and purchases': 'Contratos y compras',
    'Employee count': 'Número de empleados',
    'Utility rates': 'Tarifas de servicios públicos',
    'Council minutes since April 2024': 'Actas del Concejo desde abril de 2024',
    'CRA records': 'Registros de la CRA',
    'Debris contracts': 'Contratos de escombros',
    'Employee count and administrator pay': 'Empleados y salario del administrador',
}

L_ES = {'sendTo': 'Enviar a:', 'email': 'Correo:', 'phone': 'Teléfono:', 'mail': 'Correo postal:', 'online': 'En línea:', 'portal': 'portal de solicitudes de registros',
        'noEmail': 'No tenemos un correo de registros.', 'contact': 'Página de contacto', 'site': 'Sitio web', 'askClerk': 'pida hablar con el secretario municipal o el encargado de registros.',
        'policy': 'Su política de registros', 'other': 'Otra cosa', 'otherD': 'Escriba su propia descripción abajo (en inglés, si puede).',
        'copied': 'Copiada. Péguela en un correo o una carta.', 'selectAll': 'Seleccione todo y copie.',
        'namePh': '[Your name]', 'emailPh': '[Your email]', 'need': 'Primero escriba su nombre y su correo. La oficina los necesita para enviarle un estimado de costos y los registros.'}


def es_records_page(out_dir):
    from records_page import records_data
    data = records_data()
    for r in data:
        for s in r['s']:
            s['t'] = ES_SUGGEST_T.get(s['t'], s['t'])
    js = open(os.path.join(HERE, 'records.js')).read().replace('__REC__', json.dumps(data, ensure_ascii=False, separators=(',', ':'))).replace('__L__', json.dumps(L_ES, ensure_ascii=False))
    open(os.path.join(out_dir, 'assets', 'records.es.js'), 'w').write(js)
    return '''<div class="page tax">
  <header class="tx-top"><div class="tx-brand"><span class="eyebrow">Participe</span><h1>Solicite un registro público</h1>
    <p class="lede">La ley de registros públicos de Florida permite que cualquier persona vea los registros del gobierno. No tiene que explicar por qué. Elija un gobierno y un registro, o describa el suyo, y nosotros escribimos la solicitud.</p></div></header>
  <div class="callout"><b>La carta se escribe en inglés.</b> Así la oficina la puede atender sin demora. Abajo de la carta está lo que dice, en español. También puede pedir los registros en persona o por teléfono, en el idioma que prefiera.</div>
  <div class="rq">
    <div class="rq-form">
      <label class="vf"><span>1. Gobierno</span><select id="rqG"></select></label>
      <div class="vf"><span>2. ¿Qué registro quiere?</span><div id="rqS" class="rq-s" role="radiogroup" aria-label="Registros sugeridos"></div></div>
      <label class="vf"><span>Descripción de los registros <em>(va en la carta, en inglés)</em></span><textarea id="rqD" rows="5" placeholder="Sea específico: qué, de qué fechas, de qué departamento. Por ejemplo: the contract and change orders for the Martin Theatre project."></textarea></label>
      <div class="cf-row"><label class="vf"><span>Su nombre</span><input id="rqN" type="text" autocomplete="name" required></label>
        <label class="vf"><span>Su correo electrónico</span><input id="rqC" type="email" autocomplete="email" required></label></div>
      <label class="vf"><span>Teléfono <em>(opcional)</em></span><input id="rqP" type="tel" autocomplete="tel"></label>
      <p class="note small">Muchas solicitudes tienen un cargo por copias o por tiempo del personal. Su nombre y su correo le permiten a la oficina enviarle un estimado de costos y los registros.</p>
      <label class="chk"><input type="checkbox" id="rqE" checked> Pedir copias electrónicas</label>
    </div>
    <div class="rq-out">
      <div class="rq-to" id="rqTo"></div>
      <label class="vf"><span>Su solicitud (en inglés)</span><textarea id="rqL" rows="16" readonly></textarea></label>
      <div class="rq-btns"><button type="button" class="pill" id="rqCopy">Copiar</button><a class="pill" id="rqMail" href="#">Abrir en el correo</a><a class="pill" id="rqPortal" href="#" target="_blank" rel="noopener" hidden>Abrir el portal de registros</a><button type="button" class="pill" id="rqPrint">Imprimir</button></div>
      <p class="note small" id="rqMsg" role="status"></p>
      <details class="flds"><summary>Qué dice la carta, en español</summary><p class="small">Fecha. Para: el encargado de registros del gobierno elegido. Asunto: solicitud de registros públicos.</p>
        <p class="small">"Conforme a la Ley de Registros Públicos de Florida, Capítulo 119 de los Estatutos de Florida, solicito copias de los siguientes registros públicos: [su descripción]. Por favor, entréguelos en formato electrónico (PDF o el formato original, como Excel) por correo si es posible. Si alguna parte está exenta, cite la exención específica de cada parte retenida y entregue el resto, como exige la sección 119.07(1)(e) y (f). Si la solicitud implica un cargo por servicio especial o costos de copias de más de $25, envíeme un estimado antes de proceder. Preparé esta solicitud con la herramienta gratuita de BayCounty.me, un sitio independiente de registros públicos. BayCounty.me no hace esta solicitud y no necesita una copia. Envíe todas las respuestas, estimados y registros directamente a mí, a los datos de contacto de abajo. Gracias por su ayuda." Y su nombre, su correo y, si lo dio, su teléfono.</p></details>
    </div>
  </div>
  <section class="tx-sec method"><div class="sec-hd"><h2 id="tips">Bueno saber</h2></div><ul class="plain">
    <li><b>Cualquier persona puede pedir.</b> Según el Capítulo 119 de los Estatutos de Florida, puede pedir registros en persona, por teléfono, por correo electrónico o por carta, y no tiene que explicar por qué. La ley no exige su nombre, pero cuando hay un cargo la oficina necesita cómo enviarle el estimado, cobrar y entregarle los registros, así que este formulario lo incluye.</li>
    <li><b>Costos.</b> Las agencias pueden cobrar por las copias (normalmente 15 centavos por página) y, si la solicitud requiere mucho tiempo del personal, un cargo por servicio especial. La carta pide que le avisen antes de cobrar.</li>
    <li><b>Exenciones.</b> Si retienen algo, deben decirle qué ley lo exime y entregarle el resto.</li>
    <li><b>La oficina le responde a usted.</b> La carta dice que se preparó en BayCounty.me, pero pide que todas las respuestas, estimados y registros se le envíen directamente a usted. BayCounty.me no recibe nada.</li>
    <li>Esta página escribe la solicitud; no la envía ni guarda una copia. Nada de lo que escribe aquí se guarda.</li></ul></section>
</div>
<link rel="stylesheet" href="/assets/tax.css">
<script src="/assets/records.es.js" defer></script>'''


ES_SECTIONS = [
    ('/governments', 'Gobiernos', 'Una página por cada gobierno local: quién lo dirige, su presupuesto, deuda, auditorías, votos y contratos.'),
    ('/compare', 'Comparar gobiernos', 'Presupuestos, impuestos y deuda por residente, lado a lado.'),
    ('/public-money/cra-spending', 'Gastos de las CRA', 'Qué pagaron las agencias de reurbanización con el dinero de impuestos.'),
    ('/public-money/votes', 'Votos', 'Cómo votó cada funcionario en las decisiones de dinero, según las actas.'),
    ('/meetings', 'Reuniones públicas', 'Cuándo y dónde se reúne cada junta, con enlaces a las agendas.'),
    ('/public-money/campaign-money', 'Dinero de campaña', 'Quién financió las campañas de los funcionarios y qué donantes tienen contratos.'),
    ('/open-data', 'Datos abiertos', 'Descargue los datos de este sitio en CSV y JSON.'),
]


def es_home():
    cards = [('/es/mi-direccion', 'Mi dirección', 'Escriba una dirección del condado de Bay y vea su estimado de impuestos a la propiedad, quién lo representa, sus escuelas, sus zonas de inundación y evacuación, y si está dentro de un distrito de reurbanización.'),
             ('/es/impuestos', 'Sus impuestos', 'Calcule su factura del impuesto a la propiedad y vea qué parte recibe el condado, las escuelas, su ciudad y cada distrito, y en qué gasta su dinero cada gobierno.'),
             ('/es/tarifas-y-facturas', 'Tarifas y facturas', 'Las tarifas fijas de su factura de impuestos (bomberos, aguas pluviales, alumbrado) y cuánto cuesta el agua, el alcantarillado y la basura en cada ciudad.'),
             ('/es/exenciones', 'Exenciones', 'Quién paga menos impuesto a la propiedad, desde el homestead hasta los veteranos con discapacidad, y cómo solicitar una exención.'),
             ('/es/elecciones', 'Elecciones 2026', 'Cada contienda local de 2026: los candidatos, lo que proponen, y de dónde viene el dinero de su campaña.'),
             ('/es/reuniones', 'Reuniones públicas', 'Cuándo y dónde se reúne cada junta, con enlaces a las agendas y los temas de dinero de cada reunión.'),
             ('/es/solicitar-registros', 'Solicitar registros públicos', 'Elija un gobierno y un registro, y le escribimos la solicitud bajo la ley de registros públicos de Florida.'),
             ('/es/glosario', 'Glosario', 'Cada término de dinero público explicado en lenguaje sencillo: CRA, millaje, exención de vivienda principal y más.')]
    c = ''.join(f'<a class="gv-card" href="{h}"><span class="eyebrow">En español</span><b>{e(t)}</b><span class="small">{e(d)}</span></a>' for h, t, d in cards if h in ES_ALT)
    s = ''.join(f'<li><a href="{h}" hreflang="en">{e(t)}</a> <span class="muted small">(en inglés)</span><br><span class="small">{e(d)}</span></li>' for h, t, d in ES_SECTIONS if h not in ES_ALT.values())
    return f'''<div class="page prose es-home">
  <span class="eyebrow">BayCounty.me en español</span>
  <h1>Los registros públicos del condado de Bay, en lenguaje sencillo</h1>
  <p class="lede">BayCounty.me reúne los presupuestos, impuestos, contratos, votos y mapas de los gobiernos locales del condado de Bay, Florida, con enlaces a cada documento original. Es un sitio independiente y neutral.</p>
  <div class="es-cards">{c}</div>
  <h2>El resto del sitio (en inglés)</h2>
  <p>Estas secciones están en inglés por ahora. Su navegador puede traducirlas.</p>
  <ul class="plain es-list">{s}</ul>
</div>'''


def _tr(d, k, label, miss):
    if k in d:
        return d[k]
    miss.add(f'{label}: {k[:50]}')
    return k


def es_tax_page(out_dir):
    """/es/impuestos: tax_page() rendered with Spanish data labels, then phrase pairs on the page and tax.js."""
    import tax_page as tp
    T, miss = page_pairs('tax'), set()
    d = tp.build_data()
    d['groups'] = [(g, _tr(T['groups'], n, 'group', miss)) for g, n in d['groups']]
    for a in d['auth'].values():
        a['n'] = _tr(T['auth'], a['n'], 'auth', miss)
    for b in d['bars']:
        b['n'] = _tr(T['auth'], b['n'], 'bar', miss)
    for x in d['districts']:
        x['label'] = T['districts'].get(x['label'], x['label'])
    K = T['keys']
    for g in d['govs']:
        g['short'] = T['short'].get(g['short'], g['short'])
        g['name'] = _tr(T['names'], g['name'], 'name', miss)
        g['status'] = [g['status'][0], _tr(T['status'], g['status'][1], 'status', miss)]
        for f in ('rev', 'exp', 'other'):
            if g.get(f):
                g[f] = {_tr(K, k, 'key', miss): v for k, v in g[f].items()}
        for y in g.get('act', []):
            y['rev'] = {_tr(K, k, 'key', miss): v for k, v in y['rev'].items()}
            y['exp'] = {_tr(K, k, 'key', miss): v for k, v in y['exp'].items()}
        g['ctx'] = [[_tr(T['ctx'], t, 'ctx', miss), u] for t, u in g['ctx']]
        g['notes'] = [_tr(T['notes'], n, 'note', miss) for n in g['notes']]
        g['src'] = [[t.replace('Related: ', 'Relacionado: '), u] for t, u in g['src']]
    d['gaps'] = [_tr(T['gaps'], x, 'gap', miss) for x in d['gaps']]
    if miss:
        print('es tax: untranslated data labels', len(miss), sorted(miss)[:6])
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, 'assets'))
        with patched(tp, build_data=lambda: d):
            page = tp.tax_page(tmp)
        js = open(os.path.join(tmp, 'assets', 'tax.js')).read()
    js, miss_j = apply_pairs(js, T['js'])
    if miss_j:
        print('es tax.js: unmatched pairs', len(miss_j), miss_j[:4])
    open(os.path.join(out_dir, 'assets', 'tax.es.js'), 'w').write(js)
    return data_stamp(translate(page, T['html'], 'tax'), '/public-money/tax-dollars')


def es_fees_page():
    """/es/tarifas-y-facturas: fees_page() run on a Spanish copy of its data file, then phrase pairs."""
    import fees_page as fp
    T, miss = page_pairs('fees'), set()
    d = json.load(open(fp.SRC))
    tr = lambda s: _tr(T['data'], s, 'fees', miss) if s else s
    for x in d['assessments']:  # only what the table shows: rows with a 2025 levy, and the rate before how_charged
        r = x.get('roll_2025')
        r = r[0] if isinstance(r, list) and r else (r if isinstance(r, dict) else {})
        if not r.get('total_levied'):
            continue
        for k in ('name', 'government', 'rate' if x.get('rate') else 'how_charged'):
            if x.get(k):
                x[k] = tr(x[k])
    for u in d['utility_rates']:  # 'provider' stays English: fees_page matches it to its bill table; the page pairs translate it
        for k in ('area', 'calc', 'effective') if u.get('bill_5000gal') else ():
            if u.get(k):
                u[k] = tr(u[k])
    shown = [g for g in d['gaps'] if not re.search(r'salar|pay|roster|term|school board|manager', g, re.I)]
    d['gaps'] = [tr(g) for g in shown]
    assert not any(re.search(r'salar|pay|roster|term|school board|manager', g, re.I) for g in d['gaps']), 'a Spanish gap would be filtered out'
    if miss:
        print('es fees: untranslated data text', len(miss), sorted(miss)[:6])
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(d, f, ensure_ascii=False)
    try:
        with patched(fp, SRC=f.name, OTHER_NOTE={k: T['other_note'][k] for k in fp.OTHER_NOTE}):
            page = fp.fees_page()
    finally:
        os.unlink(f.name)
    return data_stamp(translate(page, T['html'], 'fees'), '/public-money/fees-and-bills')


def money_short_es(n):
    """exemptions_page.money in Spanish style: billions as millions ('$1,150M'; 'B' would read as 'billón')."""
    a = abs(n or 0)
    return f'${n/1e6:,.0f}M' if a >= 1e9 else f'${n/1e6:,.1f}M' if a >= 1e6 else f'${n/1e3:,.0f}K' if a >= 1e4 else f'${n:,.0f}'


def es_exemptions_page():
    """/es/exenciones: exemptions_page() with Spanish label tables (no shard rewrite), then phrase pairs."""
    import exemptions_page as xp
    T = page_pairs('exemptions')
    home = [(c, *T['home'][c], school) for c, _n, _a, _w, school in xp.HOME]
    other = {c: T['other'][c] for c in xp.OTHER_NAMES}
    with patched(xp, HOME=home, OTHER_NAMES=other, DIST_SHORT=T['dist'], money=money_short_es, write_shards=lambda out_dir: 0):
        page = xp.exemptions_page(None)
    return translate(page, T['html'], 'exemptions')  # the 'No' cells of the school-taxes column are already Spanish


ES_DAYS = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']


def es_meetings_page():
    """/es/reuniones: meetings_page() with Spanish dates, generic titles and schedules (i18n/es_meetings.json),
    then phrase pairs. Board names, specific titles, agenda items and venues stay as each government posts them.
    The English page writes /meetings.ics; this one writes nothing outside its HTML."""
    import meetings_page as mp
    from govs import _load
    T = page_pairs('meetings')
    md = _load().get('meetings') or {'boards': [], 'meetings': []}
    md = json.loads(json.dumps(md))
    miss = set()
    for b in md.get('boards', []):
        if b.get('schedule'):
            b['schedule'] = _tr(T['schedule'], b['schedule'], 'schedule', miss)
    for x in md.get('boards', []) + md.get('meetings', []):
        for a, c in T['place'] if x.get('location') else ():
            x['location'] = x['location'].replace(a, c)
    for m in md.get('meetings', []):
        m['title'] = T['titles'].get(m.get('title'), m.get('title'))
    if miss:
        print('es meetings: untranslated schedules', sorted(miss))

    def when(s):
        d, timed = mp._dt(s)
        if not d:
            return s
        t = f'{ES_DAYS[d.weekday()]}, {d.day} de {MONTHS[d.month - 1][:3]}.'
        return t + (' · ' + d.strftime('%-I:%M').replace(':00', '') + (' a. m.' if d.hour < 12 else ' p. m.') if timed else '')
    real = _load()
    with tempfile.TemporaryDirectory() as tmp, patched(mp, _load=lambda: {**real, 'meetings': md}, _when=when):
        page = mp.meetings_page(tmp)
    page = translate(page, T['html'], 'meetings', quiet=('<li class="muted">No upcoming', '<span class="badge">Expected', '<span class="badge ok">Agenda posted', 'rel="noopener">Packet', 'rel="noopener">Minutes', 'rel="noopener">Agenda', "<p class=\"small muted\">From the regular", "<p class=\"small muted\">On the government"))
    page = page.replace('<option value="county">Bay County</option>', '<option value="county">Condado de Bay</option>').replace('<option value="schools">Bay District Schools</option>', '<option value="schools">Escuelas del Distrito de Bay</option>')
    page = re.sub(r'(<p class="small">)(CANCEL+ED\b)', r'\1<span class="badge warn">Cancelada</span> \2', page)
    page = re.sub(r'<summary>(\d+) money items? on the agenda</summary>', lambda m: f'<summary>{m.group(1)} tema{"s" if m.group(1) != "1" else ""} de dinero en la agenda</summary>', page)
    page = re.sub(r'<span>Revisado el (\d{4})-(\d{2})-(\d{2})</span>', lambda m: '<span>Revisado el ' + iso_es(m) + '</span>', page)
    return page


def iso_es(m):
    """re match of YYYY-MM-DD -> '2 de octubre de 2026'."""
    return f'{int(m.group(3))} de {MONTHS[int(m.group(2)) - 1]} de {m.group(1)}'


def es_elections_page():
    """/es/elecciones: elections_page() on Spanish copies of its data (notes, backgrounds, platform summaries, gaps)
    with Spanish label dicts, then phrase pairs. Office names stay English until after rendering because
    elections_page matches finance records by office. Individual donors are never named, as on the English page."""
    import elections_page as ep
    T, miss = page_pairs('elections'), set()
    C, F = ep.load()
    if not C:
        return ep.elections_page()
    tx = lambda s: _tr(T['text'], s, 'text', miss) if s else s
    for r in C['races']:
        if r.get('notes'):
            r['notes'] = tx(ep._clean(r['notes']))
        for c in r.get('candidates') or []:
            for k in ('background', 'platform_note'):
                if c.get(k):
                    c[k] = tx(c[k])
            c['platform'] = [tx(p) for p in c.get('platform') or []]
    C['gaps'] = [tx(g) for g in C.get('gaps') or []]
    F['gaps'] = [tx(g) for g in F.get('gaps') or []]
    notes = {}
    for r in F.get('candidates') or []:
        for n in ep._notes(r):
            notes[n] = tx(n)
    orig_notes = ep._notes
    with patched(ep, load=lambda: (C, F), GOVN=T['govn'], PARTY=T['party'], STATUS_LBL=T['status'], _clean=lambda t: t,
                 _notes=lambda r: [notes.get(n, n) for n in orig_notes(r)]):
        page = ep.elections_page()
    if miss:
        print('es elections: untranslated data text', len(miss), sorted(miss)[:6])
    page = translate(page, T['html'], 'elections', quiet=('<a href="#next">April 2027</a>', '<h2>Already running for April 2027</h2>', 'Filed with the Supervisor of Elections for the April 20', '<p class="muted">No local races', '<p class="muted">None.</p>', '<th scope="row">Refunds to individual', ' of the total is in-kind', '>No platform statement found.', 'No campaign finance report found', '<span class="badge">Withdrew</span>', '<small>Party</small>', '<small>Committee</small>', '<small>Business</small>', '<small>Political committee</small>', '<small>Other</small>', 'Decided earlier in 2026', 'Decided in the Aug. 18 primary', ' (appointed)', ' (not a candidate)', '<p class="small muted">None reported.</p>'))
    for a, b in T['re']:
        page = re.sub(a, b, page)
    page = re.sub(r'; and (\d+) other descriptions</small>', r'; y \1 descripciones más</small>', page)
    page = re.sub(r'(?<=<span class="muted small">hasta )(\d{4})-(\d{2})-(\d{2})', lambda m: 'el ' + iso_es(m), page)
    page = re.sub(r'<span>Campaign reports checked (\d{4})-(\d{2})-(\d{2})</span>', lambda m: '<span>Informes de campaña revisados el ' + iso_es(m) + '</span>', page)
    for en, es in sorted(T['office'].items(), key=lambda kv: -len(kv[0])):
        page = page.replace(f'<h3>{html.escape(en)}</h3>', f'<h3>{html.escape(es)}</h3>').replace(f'<b>{html.escape(en)}</b>', f'<b>{html.escape(es)}</b>')
    return page
