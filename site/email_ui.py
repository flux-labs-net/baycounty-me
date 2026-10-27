"""Python twin of api/_email_ui.js: the shared BayCounty.me email layout, for the senders written in Python
(the agenda watcher and the workflow alerts). Only the pieces those notices use. Keep it in step with the JS file:
api/__tests__/email-ui.test.js renders the same notice with both and fails if the HTML differs."""
import html as _html

SITE = 'https://baycounty.me'
F = "Poppins,'Segoe UI',Arial,Helvetica,sans-serif"
MONO = "'IBM Plex Mono',Consolas,'Courier New',monospace"
C = {'bg': '#EEF3FA', 'card': '#FFFFFF', 'sunken': '#F4F8FC', 'ink': '#161B24', 'muted': '#5A6372', 'faint': '#8A93A1',
     'line': '#DCE4EE', 'link': '#1E3A76', 'btn': '#1E3A76', 'btnTx': '#FFFFFF', 'salmon': '#E5564A', 'accent': '#B23A2F'}
TONES = {'blue': ('#E6EEF8', '#1E3A76'), 'teal': ('#E9F5F2', '#1F8A7A'), 'amber': ('#FDF5E6', '#9A6512'), 'salmon': ('#FFF1EE', '#B23A2F')}
TONES_DARK = {'blue': ('#1C2A40', '#9DB8EA'), 'teal': ('#132723', '#4CC2B2'), 'amber': ('#2A2215', '#FFC36B'), 'salmon': ('#2A1B1D', '#FF8C82')}
ICONS = ['alert', 'bell', 'calendar', 'chat', 'check', 'dollar', 'file', 'key', 'lock', 'mail', 'megaphone', 'reply', 'search', 'spark', 'vote']
DARK = [
    ('bc-bg', 'background-color', '#0E131B'), ('bc-card', 'background-color', '#151C27'), ('bc-sk', 'background-color', '#1B2431'),
    ('bc-btn', 'background-color', '#9DB8EA'), ('bc-ln', 'border-color', '#263142'),
    ('bc-ink', 'color', '#E7ECF3'), ('bc-mu', 'color', '#A1AABA'), ('bc-fa', 'color', '#768092'), ('bc-lk', 'color', '#9DB8EA'),
    ('bc-btx', 'color', '#0E131B'), ('bc-sal', 'color', '#FF8C82'), ('bc-acc', 'color', '#FF8C82'),
] + [x for t, (bg, fg) in TONES_DARK.items() for x in (('bc-tb-' + t, 'background-color', bg), ('bc-tf-' + t, 'color', fg))]
ABOUT = 'BayCounty.me puts Bay County, Florida public records in plain view. Built by Flux Labs in Panama City.'


def esc(s):
    return _html.escape('' if s is None else str(s), quote=True).replace('&#x27;', '&#39;')


def dark_css():
    rules = ''.join('.%s{%s:%s!important}' % r for r in DARK)
    ogs = ''.join('[data-%s] .%s{%s:%s!important}' % ('ogsc' if p == 'color' else 'ogsb', c, p, v) for c, p, v in DARK)
    return ('@media (prefers-color-scheme:dark){%s.bc-l{display:none!important}.bc-d{display:block!important;max-height:none!important;'
            'overflow:visible!important}}%s') % (rules, ogs)


HEAD_CSS = ('body{margin:0;padding:0;-webkit-text-size-adjust:100%}a{text-decoration:none}table{border-collapse:separate}'
            '@media (max-width:620px){.bc-px{padding-left:20px!important;padding-right:20px!important}.bc-h1{font-size:21px!important;'
            'line-height:28px!important}.bc-out{padding-left:8px!important;padding-right:8px!important}}') + dark_css()


def _tone(t):
    return t if t in TONES else 'blue'


def icon(name, tone, size):
    if name not in ICONS:
        name = 'spark'

    def img(dark, cls, style):
        return ('<img class="%s" src="%s/assets/email/%s-%s%s.png" width="%d" height="%d" alt="" style="%sborder:0;outline:none;width:%dpx;height:%dpx">'
                % (cls, SITE, name, tone, '-d' if dark else '', size, size, style, size, size))
    return img(False, 'bc-l', 'display:block;') + '<!--[if !mso]><!-->' + img(True, 'bc-d', 'display:none;max-height:0;overflow:hidden;') + '<!--<![endif]-->'


def p(html, muted=False, mb=14, size=15, lh=24):
    return '<p class="%s" style="margin:0 0 %dpx 0;font-family:%s;font-size:%dpx;line-height:%dpx;color:%s">%s</p>' % (
        'bc-mu' if muted else 'bc-ink', mb, F, size, lh, C['muted'] if muted else C['ink'], html)


def small(html, mb=0):
    return p(html, muted=True, mb=mb, size=13, lh=20)


def badge(t, ic, size=48):
    t = _tone(t)
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td class="bc-tb-%s" width="%d" height="%d" align="center" '
            'valign="middle" bgcolor="%s" style="width:%dpx;height:%dpx;background-color:%s;border-radius:%dpx">%s</td></tr></table>'
            % (t, size, size, TONES[t][0], size, size, TONES[t][0], round(size * 0.3), icon(ic, t, round(size * 0.46))))


def hero(tone, ic, eyebrow, title):
    eb = ('<div class="bc-mu" style="font-family:%s;font-size:11px;line-height:16px;letter-spacing:1px;text-transform:uppercase;font-weight:600;color:%s">%s</div>'
          % (F, C['muted'], eyebrow)) if eyebrow else ''
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td width="48" valign="top" style="padding:2px 16px 0 0">%s</td>'
            '<td valign="middle">%s<div class="bc-h1 bc-ink" style="font-family:%s;font-size:24px;line-height:31px;font-weight:600;color:%s;margin-top:3px">%s</div></td></tr></table>'
            % (badge(tone, ic), eb, F, C['ink'], title))


def a(href, label, style=''):
    return '<a class="bc-lk" href="%s" style="color:%s;text-decoration:none;%s">%s</a>' % (esc(href), C['link'], style, label)


def foot_link(href, label):
    return '<a class="bc-mu" href="%s" style="color:%s;text-decoration:underline">%s</a>' % (esc(href), C['muted'], label)


def pill(t, text):
    t = _tone(t)
    return ('<span class="bc-tb-%s bc-tf-%s" style="display:inline-block;font-family:%s;font-size:12px;line-height:16px;font-weight:600;padding:4px 10px;'
            'border-radius:999px;background-color:%s;color:%s;white-space:nowrap">%s</span>' % (t, t, F, TONES[t][0], TONES[t][1], text))


def button(href, label, mt=8, mb=18):
    return ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:%dpx 0 %dpx 0"><tr><td class="bc-btn" bgcolor="%s" '
            'style="background-color:%s;border-radius:12px;padding:14px 24px"><a class="bc-btx" href="%s" style="font-family:%s;font-size:15px;line-height:18px;'
            'font-weight:600;color:%s;text-decoration:none;display:inline-block">%s</a></td></tr></table>'
            % (mt, mb, C['btn'], C['btn'], esc(href), F, C['btnTx'], esc(label)))


def _box(inner, m, cls, s, r=12):
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="margin:%s"><tr><td class="bc-sk %s" bgcolor="%s" '
            'style="background-color:%s;border-radius:%dpx;%s">%s</td></tr></table>' % (m, cls, C['sunken'], C['sunken'], r, s, inner))


def note(html):
    return _box(html, '6px 0 16px 0', 'bc-mu', 'padding:13px 16px;font-family:%s;font-size:13px;line-height:20px;color:%s' % (F, C['muted']))


def quote(text):
    return _box(esc(text).replace('\r\n', '<br>').replace('\n', '<br>'), '2px 0 18px 0', 'bc-ink',
                'padding:16px 18px;font-family:%s;font-size:14px;line-height:22px;color:%s' % (F, C['ink']))


def facts(rows):
    out = []
    for i, (k, v) in enumerate(rows):
        top = 'border-top:1px solid %s;' % C['line'] if i else ''
        out.append('<tr><td class="bc-mu bc-ln" width="110" valign="top" style="padding:9px 12px 9px 0;%sfont-family:%s;font-size:13px;line-height:20px;color:%s">%s</td>'
                   '<td class="bc-ink bc-ln" valign="top" style="padding:9px 0;%sfont-family:%s;font-size:14px;line-height:20px;color:%s;word-break:break-word">%s</td></tr>'
                   % (top, F, C['muted'], k, top, F, C['ink'], v))
    return '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:4px 0 16px 0">' + ''.join(out) + '</table>'


def list_rows(rows):
    """Rows with a status pill: [(tone, label, html), ...]."""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px 0">' + ''.join(
        '<tr><td class="bc-ln" style="padding:10px 0;border-bottom:1px solid %s"><table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td valign="top" style="padding:1px 10px 0 0;white-space:nowrap">%s</td>'
        '<td class="bc-ink" valign="top" style="font-family:%s;font-size:14px;line-height:21px;color:%s;word-break:break-word">%s</td></tr></table></td></tr>'
        % (C['line'], pill(t, label), F, C['ink'], html) for t, label, html in rows) + '</table>')


def preheader(text):
    if not text:
        return ''
    return ('<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;opacity:0">%s%s</div>'
            % (esc(text), '&#8199;&#65279;&#847; ' * 40))


def admin_footer(why='Admin notice. Sent to BayCounty.me admins only.'):
    return '%s %s' % (why, foot_link(SITE + '/admin', 'Open admin'))


def layout(title, body, preheader_text='', kicker='', hero_args=None, footer=ABOUT):
    """hero_args: (tone, icon, eyebrow, title) or None."""
    pad = 'padding-left:32px;padding-right:32px'
    hero_row = ('<tr><td class="bc-px" style="padding-top:30px;padding-bottom:18px;%s">%s</td></tr>\n' % (pad, hero(*hero_args))) if hero_args else ''
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="X-UA-Compatible" content="IE=edge">'
            '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark"><title>' + esc(title) + '</title>'
            '<!--[if !mso]><!--><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@600&amp;display=swap"><!--<![endif]-->'
            "<!--[if mso]><style>*{font-family:'Segoe UI',Arial,sans-serif!important}</style><![endif]-->"
            '<style>' + HEAD_CSS + '</style></head>\n'
            '<body class="bc-bg" style="margin:0;padding:0;background-color:' + C['bg'] + '">' + preheader(preheader_text) + '\n'
            '<table class="bc-bg" role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="' + C['bg'] + '" style="background-color:' + C['bg'] + '"><tr><td class="bc-out" align="center" style="padding:28px 16px 32px 16px">\n'
            '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px">\n'
            '<tr><td style="padding:0 6px 14px 6px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td class="bc-ink" style="font-family:' + F + ';font-size:21px;line-height:26px;font-weight:700;color:' + C['ink'] + ';letter-spacing:-0.2px"><a class="bc-ink" href="' + SITE + '" style="color:' + C['ink'] + ';text-decoration:none">BayCounty<span class="bc-sal" style="color:' + C['salmon'] + '">.me</span></a></td>'
            '<td class="bc-mu" align="right" style="font-family:' + F + ';font-size:12px;line-height:16px;font-weight:500;color:' + C['muted'] + '">' + kicker + '</td></tr></table></td></tr>\n'
            '<tr><td class="bc-card bc-ln" bgcolor="' + C['card'] + '" style="background-color:' + C['card'] + ';border:1px solid ' + C['line'] + ';border-radius:20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">\n'
            + hero_row +
            '<tr><td class="bc-px" style="padding-top:' + ('0' if hero_args else '30') + 'px;padding-bottom:18px;' + pad + '">' + body + '</td></tr>\n'
            '</table></td></tr>\n'
            '<tr><td class="bc-mu" style="padding:18px 6px 0 6px;font-family:' + F + ';font-size:12px;line-height:19px;color:' + C['muted'] + '">' + footer + '</td></tr>\n'
            '</table></td></tr></table></body></html>')


def admin_notice(subject, body, preheader_text='', kicker='', tone='blue', ic='bell', eyebrow='', title='', footer=None):
    """Full HTML for an admin notice (the plain-text part is the caller's)."""
    return layout(subject, body, preheader_text, kicker, (tone, ic, eyebrow, title), footer or admin_footer())
