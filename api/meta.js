// Link previews for profile pages. /profile/<kind>/<id> is one client-side shell (site/profile.js), so a link-preview
// crawler (iMessage, Facebook, X, Slack, LinkedIn, Discord, WhatsApp...) that doesn't run scripts would only see the
// shell's generic title. vercel.json sends those crawlers here instead (matched by user agent); people still get the
// static shell. This returns the same shell with the profile's own title, summary and preview image (api/og.js).
// Search engines get the same page, opened to search with structured data and a short text summary (every kind in
// INDEXED; Jeremy chose all profiles, 2026-11-04). Keep INDEXED in step
// with site/seo.py INDEXED_PROFILE_KINDS, which lists the same profiles in sitemap-profiles.xml.
//   GET /api/meta?p=/profile/<kind>/<id>
const {loadFile, SITE_URL} = require('./_data');

const PROF = /^\/profile\/(vendor|nonprofit|member|owner|business|committee|gov)\/([A-Za-z0-9_.-]{1,100})$/;
const esc = s => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
let SHELL = null;
const INDEXED = new Set(['gov', 'vendor', 'nonprofit', 'business', 'committee', 'member', 'owner']);
const LD_TYPE = {gov: 'GovernmentOrganization', nonprofit: 'NGO', vendor: 'Organization', business: 'Organization', committee: 'Organization', member: 'Person', owner: 'Person'};

async function shell() {
  if (SHELL && Date.now() - SHELL.t < 3600e3) return SHELL.html;
  const r = await fetch(`${SITE_URL}/profile`);
  if (!r.ok) throw new Error(`shell ${r.status}`);
  SHELL = {t: Date.now(), html: await r.text()};
  return SHELL.html;
}

// The shell's head with this profile's title, summary, address and image swapped in.
function withMeta(html, {title, desc, url, img, index, ld, summary}) {
  const T = esc(title), D = esc(desc), U = esc(url), I = esc(img);
  let out = html;
  if (index) out = out.replace(/<meta name="robots" content="[^"]*">/, '<meta name="robots" content="index, follow, max-image-preview:large">');
  if (ld) out = out.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/, () => `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, '\\u003c')}</script>`);
  if (summary) out = out.replace('<main id="main">', () => `<main id="main">\n<noscript><p class="pf-noscript">${esc(summary)}</p></noscript>`);
  return out
    .replace(/<title>[^<]*<\/title>/, `<title>${T} · BayCounty.me</title>`)
    .replace(/(<meta name="description" content=")[^"]*/, `$1${D}`)
    .replace(/(<link rel="canonical" href=")[^"]*/, `$1${U}`)
    .replace(/(<meta property="og:(?:title)" content=")[^"]*/, `$1${T}`)
    .replace(/(<meta name="twitter:title" content=")[^"]*/, `$1${T}`)
    .replace(/(<meta property="og:description" content=")[^"]*/, `$1${D}`)
    .replace(/(<meta name="twitter:description" content=")[^"]*/, `$1${D}`)
    .replace(/(<meta property="og:url" content=")[^"]*/, `$1${U}`)
    .replace(/(<meta (?:property="og:image"|name="twitter:image") content=")[^"]*/g, `$1${I}`)
    .replace(/(<meta (?:property="og:image:alt"|name="twitter:image:alt") content=")[^"]*/g, `$1${T}`);
}

function describe(e) {
  const bits = [e.subtitle, e.connections ? `${Number(e.connections).toLocaleString('en-US')} documented connections in Bay County public records` : 'Its record in Bay County public records'];
  return bits.filter(Boolean).join('. ') + ', each with its source.';
}

// ProfilePage about the organization or person, with a source link and breadcrumbs (same graph shape as site/seo.py jsonld()).
function structured(e, kind, url, title, desc) {
  const org = {'@type': LD_TYPE[kind] || 'Organization', '@id': url + '#entity', name: e.name, url,
    ...(e.subtitle ? {description: e.subtitle} : {}), ...(e.source_url ? {sameAs: e.source_url} : {}),
    areaServed: {'@type': 'AdministrativeArea', name: 'Bay County, Florida'}};
  return {'@context': 'https://schema.org', '@graph': [{'@type': 'ProfilePage', '@id': url + '#page', url, name: title, description: desc,
    inLanguage: 'en-US', isPartOf: {'@id': `${SITE_URL}/#site`}, about: {'@id': org['@id']}, mainEntity: {'@id': org['@id']},
    breadcrumb: {'@type': 'BreadcrumbList', itemListElement: [
      {'@type': 'ListItem', position: 1, name: 'BayCounty.me', item: `${SITE_URL}/`},
      {'@type': 'ListItem', position: 2, name: 'Connections', item: `${SITE_URL}/connections`},
      {'@type': 'ListItem', position: 3, name: e.name, item: url}]}}, org]};
}

module.exports = async (req, res) => {
  const p = String((req.query && req.query.p) || '').split('?')[0].replace(/\/+$/, '');
  const m = PROF.exec(p);
  let html;
  try {
    html = await shell();
    if (m) {
      const {getEntity, KIND_LABEL} = require('./_entities');
      const catalog = await loadFile(null, '/downloads/index.json');
      const {entity: e} = await getEntity(null, catalog, `${m[1]}:${m[2]}`);
      const url = `${SITE_URL}${p}`, title = `${e.name}: ${(e.kind_label || KIND_LABEL[e.kind] || 'profile').toLowerCase()}`, desc = describe(e);
      const index = INDEXED.has(m[1]);
      html = withMeta(html, {title, desc, url, img: `${SITE_URL}/api/og?p=${encodeURIComponent(p)}`, index,
        ld: index ? structured(e, m[1], url, title, desc) : null, summary: `${e.name}. ${desc}`});
    }
  } catch (e) {
    if (e.status !== 404) console.error('meta', p, e.message);
    if (!html) { res.setHeader('Cache-Control', 'no-store'); return res.status(503).send('Try again shortly.'); }
  }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'public, max-age=600, s-maxage=86400, stale-while-revalidate=604800');
  return res.status(200).send(html);
};
module.exports.withMeta = withMeta;
module.exports.structured = structured;
module.exports.INDEXED = INDEXED;
