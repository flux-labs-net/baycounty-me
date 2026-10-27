// Which public schools serve a place (GET /api/v1/schools and the MCP tool zoned_schools).
// Reads the school-zones dataset (attendance zone shapes from the county GIS server, as GeoJSON) and the schools
// dataset (site/page_datasets.py _school_rows()). Pure functions apart from geocode(), so the tests, the API, the MCP
// tool and the /schools page give the same answer.
const bad = (msg, status = 400) => Object.assign(new Error(msg), {status, expose: true});
const LEVELS = ['Elementary', 'Middle', 'High'];
const GIS = 'https://gis.baycountyfl.gov/arcgis/rest/services/Admin_A12/MapServer/3';  // the county's address points

// Even-odd ray casting over every ring, so holes (Esri inner rings) come out right.
function inRings(rings, x, y) {
  let inside = false;
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
  }
  return inside;
}

function ringsOf(geometry) {
  const g = typeof geometry === 'string' ? JSON.parse(geometry) : geometry;
  if (!g) return [];
  return g.type === 'Polygon' ? g.coordinates : g.type === 'MultiPolygon' ? g.coordinates.flat() : [];
}

const pick = s => s && ({school_id: s.school_id, name: s.name, level: s.level, grades: s.grades, charter: s.charter, address: s.address, city: s.city,
  phone: s.phone, enrollment: s.enrollment, enrollment_year: s.enrollment_year, latest_grade: s.latest_grade, latest_grade_year: s.latest_grade_year,
  latest_per_student: s.latest_per_student, latest_spending_year: s.latest_spending_year, page_url: s.page_url});

// The zoned school for each level at a point. A point in an ordinary zone and an MOU zone gets the ordinary one.
function zonedAt(zones, schools, lat, lon) {
  lat = Number(lat); lon = Number(lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) throw bad('Give lat and lon as decimal degrees, e.g. lat=30.17&lon=-85.66.');
  const byId = new Map(schools.map(s => [s.school_id, s]));
  const out = {};
  for (const level of LEVELS) {
    const hits = zones.filter(z => z.level === level && inRings(ringsOf(z.geometry), lon, lat)).sort((a, b) => (a.mou_area ? 1 : 0) - (b.mou_area ? 1 : 0));
    const z = hits[0];
    out[level.toLowerCase()] = z ? {zone: z.zone_name, zone_id: z.zone_id, mou_area: !!z.mou_area, zone_last_edited: z.last_edited, school: pick(byId.get(z.school_id)) || {school_id: z.school_id, name: z.school}} : null;
  }
  return {lat, lon, inside_district: LEVELS.some(l => out[l.toLowerCase()]), ...out,
    note: 'Attendance zones from the school district via the county GIS server. Choice, magnet, charter and virtual schools take students from outside their zone. Confirm with the district before enrolling.'};
}

// A short list of every open school, for the endpoint without a location.
function summary(schools) {
  return schools.filter(s => s.status === 'Open').map(pick);
}

// Find an address in the county's address points (house number and street words). Returns [{address, city, zip, lat, lon}].
async function geocode(text, fetchImpl = fetch) {
  const s = String(text || '').toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b(FL|FLORIDA|\d{5})\b/g, ' ').replace(/\s+/g, ' ').trim();
  const m = /^(\d+)\s+(.+)$/.exec(s);
  if (!m) throw bad('Give a street address with a house number, e.g. 1200 Harrison Ave.');
  const SKIP = new Set(['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'BLVD', 'LN', 'LANE', 'CT', 'CIR', 'PL', 'WAY', 'PANAMA', 'CITY', 'BEACH', 'LYNN', 'HAVEN', 'CALLAWAY', 'SPRINGFIELD', 'PARKER', 'MEXICO', 'SOUTHPORT', 'YOUNGSTOWN', 'FOUNTAIN']);
  const words = m[2].split(' ').filter(w => w.length > 1 && !SKIP.has(w)).slice(0, 3);
  if (!words.length) throw bad('Add the street name.');
  const where = [`ADDRESS LIKE '${m[1]} %'`, ...words.map(w => `ADDRESS LIKE '% ${w.replace(/'/g, "''")}%'`)].join(' AND ');
  const u = `${GIS}/query?` + new URLSearchParams({where, outFields: 'ADDRESS,CMNTY,ZIP', returnGeometry: 'true', outSR: '4326', resultRecordCount: '5', f: 'json'});
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 8000);
  try {
    const r = await fetchImpl(u, {signal: ctl.signal});
    const j = await r.json();
    if (j.error) throw new Error(j.error.message);
    return (j.features || []).map(f => ({address: f.attributes.ADDRESS, city: f.attributes.CMNTY, zip: f.attributes.ZIP, lat: f.geometry.y, lon: f.geometry.x}));
  } catch (e) {
    if (e.expose) throw e;
    throw bad("The county's address service didn't answer. Try again, or pass lat and lon.", 502);
  } finally { clearTimeout(t); }
}

module.exports = {inRings, ringsOf, zonedAt, summary, geocode, LEVELS};
