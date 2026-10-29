// Link-preview images (1200x630 PNG) for pages the static build doesn't draw a card for.
//   GET /api/og?p=/restaurants/<slug>-<license>   a restaurant: name, address, latest result and inspection
//   GET /api/og?p=/profile/<kind>/<id>            a profile: name, kind, what it received or gave, connections
// Anything else redirects to the site-wide card. Names and figures come from the published datasets (never from the
// link), so a link can't make a card say something the records don't. Cards are cached a day at the edge.
const {rest, loadFile, SITE_URL} = require('./_data');
const {card, fonts, restaurantCard, entityCard, W, H} = require('./_og/card');

const REST = /^\/restaurants\/[a-z0-9-]{1,120}-(\d{5,9})$/;
const PROF = /^\/profile\/(vendor|nonprofit|member|owner|business|committee|gov)\/([A-Za-z0-9_.-]{1,100})$/;

async function cardFor(p) {
  let m = REST.exec(p);
  if (m) {
    const lic = m[1];
    const [r] = (await rest(`restaurants?select=business_name,kind,address,city,last_inspection,last_result,page_url&license_number=eq.${lic}&limit=1`, {timeout: 6000})).rows;
    if (!r || r.page_url !== p) return null;
    const [last] = (await rest(`restaurant_inspections?select=date,inspection_type,total_violations,high_priority&license_number=eq.${lic}&order=date.desc,visit_number.desc&limit=1`, {timeout: 6000}).catch(() => ({rows: []}))).rows;
    return restaurantCard(r, last);
  }
  m = PROF.exec(p);
  if (m) {
    const id = `${m[1]}:${m[2]}`;
    const {getEntity, KIND_LABEL} = require('./_entities');
    const catalog = await loadFile(null, '/downloads/index.json');
    const {entity} = await getEntity(null, catalog, id);
    return entityCard(entity, entity.kind_label || KIND_LABEL[entity.kind]);
  }
  return null;
}

let ImageResponse;
async function png(c) {
  if (!ImageResponse) ({ImageResponse} = await import('@vercel/og'));
  const img = new ImageResponse(card(c), {width: W, height: H, fonts: fonts()});
  return Buffer.from(await img.arrayBuffer());
}

module.exports = async (req, res) => {
  const p = String((req.query && req.query.p) || '').split('?')[0].replace(/\/+$/, '');
  let c = null;
  try { c = await cardFor(p); }
  catch (e) { if (e.status !== 404) console.error('og', p, e.message); }
  if (!c) {
    res.setHeader('Cache-Control', 'public, max-age=300, s-maxage=3600');
    res.writeHead(302, {Location: `${SITE_URL}/og/home.png`}); return res.end();
  }
  try {
    const buf = await png(c);
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Cache-Control', 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800');
    return res.status(200).send(buf);
  } catch (e) {
    console.error('og render', p, e.message);
    res.setHeader('Cache-Control', 'no-store');
    res.writeHead(302, {Location: `${SITE_URL}/og/home.png`}); return res.end();
  }
};
module.exports.cardFor = cardFor;
module.exports.png = png;
