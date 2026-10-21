"""Spanish pages (/es, /es/mi-direccion, /es/glosario, /es/solicitar-registros).

Translations live in i18n/: es_glossary.json (term-for-term) and es_address.json
(ordered English→Spanish phrase pairs applied to the My Address page and its script).
The rest of the site is English; /es links to it and says so.
"""
import html, json, os
from glossary import GROUPS, TERMS

HERE = os.path.dirname(os.path.abspath(__file__))
I18N = os.path.join(HERE, 'i18n')
e = html.escape

ES_MENU = [
    {'label': 'Inicio', 'href': '/es'},
    {'label': 'Mi dirección', 'href': '/es/mi-direccion'},
    {'label': 'Solicitar registros', 'href': '/es/solicitar-registros'},
    {'label': 'Glosario', 'href': '/es/glosario'},
]

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
]
MONTHS = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
EN_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def localize_chrome(page_html):
    """Translate the shared header/footer of an /es page."""
    import re
    for a, b in ES_FOOTER:
        page_html = page_html.replace(a, b)
    page_html = re.sub(r'Page updated ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})',
                       lambda m: f'Página actualizada el {int(m.group(2))} de {MONTHS[EN_MONTHS.index(m.group(1))]} de {m.group(3)}', page_html)
    return page_html.replace('<meta property="og:locale" content="en_US">', '<meta property="og:locale" content="es_US">')


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
    return {t['id']: {'term': g['terms'].get(t['id'], {}).get('term') or t['term'], 'simple': g['terms'].get(t['id'], {}).get('simple') or t['simple']} for t in TERMS}


def es_glossary_page():
    g = glossary_es()
    gl = g['groups']
    jump = ''.join(f'<a href="#g-{k}">{e(gl.get(k, label))}</a>' for k, label in GROUPS)
    out = [f'''<div class="page prose glossary">
  <span class="eyebrow">Glosario</span>
  <h1>Guía en lenguaje sencillo</h1>
  <p class="lede">El dinero público viene con mucha jerga. Aquí está cada término de este sitio, explicado primero de forma sencilla y luego con más detalle. En todo el sitio, una palabra con subrayado punteado se puede tocar para ver su explicación corta.</p>
  <nav class="g-jump" aria-label="Secciones del glosario">{jump}</nav>''']
    for k, label in GROUPS:
        out.append(f'<section class="g-group" id="g-{k}"><h2>{e(gl.get(k, label))}</h2>')
        for t in [t for t in TERMS if t['group'] == k]:
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
    ('/public-money/tax-dollars', 'Sus impuestos', 'A dónde va cada dólar de su factura de impuestos a la propiedad.'),
    ('/public-money/cra-spending', 'Gastos de las CRA', 'Qué pagaron las agencias de reurbanización con el dinero de impuestos.'),
    ('/public-money/votes', 'Votos', 'Cómo votó cada funcionario en las decisiones de dinero, según las actas.'),
    ('/meetings', 'Reuniones públicas', 'Cuándo y dónde se reúne cada junta, con enlaces a las agendas.'),
    ('/public-money/campaign-money', 'Dinero de campaña', 'Quién financió las campañas de los funcionarios y qué donantes tienen contratos.'),
    ('/open-data', 'Datos abiertos', 'Descargue los datos de este sitio en CSV y JSON.'),
]


def es_home():
    cards = [('/es/mi-direccion', 'Mi dirección', 'Escriba una dirección del condado de Bay y vea su estimado de impuestos a la propiedad, quién lo representa, sus escuelas, sus zonas de inundación y evacuación, y si está dentro de un distrito de reurbanización.'),
             ('/es/solicitar-registros', 'Solicitar registros públicos', 'Elija un gobierno y un registro, y le escribimos la solicitud bajo la ley de registros públicos de Florida.'),
             ('/es/glosario', 'Glosario', 'Cada término de dinero público explicado en lenguaje sencillo: CRA, millaje, exención de vivienda principal y más.')]
    c = ''.join(f'<a class="gv-card" href="{h}"><span class="eyebrow">En español</span><b>{e(t)}</b><span class="small">{e(d)}</span></a>' for h, t, d in cards)
    s = ''.join(f'<li><a href="{h}" hreflang="en">{e(t)}</a> <span class="muted small">(en inglés)</span><br><span class="small">{e(d)}</span></li>' for h, t, d in ES_SECTIONS)
    return f'''<div class="page prose es-home">
  <span class="eyebrow">BayCounty.me en español</span>
  <h1>Los registros públicos del condado de Bay, en lenguaje sencillo</h1>
  <p class="lede">BayCounty.me reúne los presupuestos, impuestos, contratos, votos y mapas de los gobiernos locales del condado de Bay, Florida, con enlaces a cada documento original. Es un sitio independiente y neutral.</p>
  <div class="es-cards">{c}</div>
  <h2>El resto del sitio (en inglés)</h2>
  <p>Estas secciones están en inglés por ahora. Su navegador puede traducirlas.</p>
  <ul class="plain es-list">{s}</ul>
</div>'''
