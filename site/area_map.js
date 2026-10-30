/* Maps of where an alert or notice applies (a boil-water area, a main break, a closed street).
   BCMap.editor(box, input) lets government staff draw on a map in /staff: pins with a radius, street or pipe lines,
   and areas. The drawing is kept in `input` (a hidden form field) as a GeoJSON FeatureCollection.
   BCMap.view(box, geojson) draws a saved map read-only on public pages (/emergency, /notices).
   Leaflet is loaded from cdnjs the first time a map is needed. */
(() => {
  const CSS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
  const JS = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
  const CENTER = [30.2, -85.66], ZOOM = 10;
  const COLOR = '#d14343';
  let loading = null;
  function leaflet() {
    if (window.L) return Promise.resolve(window.L);
    if (loading) return loading;
    loading = new Promise((ok, no) => {
      const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = CSS; document.head.appendChild(l);
      const s = document.createElement('script'); s.src = JS; s.onload = () => ok(window.L); s.onerror = () => { loading = null; no(new Error('The map could not load.')); };
      document.head.appendChild(s);
    });
    return loading;
  }
  // Map styles, once per page. Dark mode darkens the street tiles the same way the outdoors map does.
  function styles() {
    if (document.getElementById('bcmap-css')) return;
    const st = document.createElement('style'); st.id = 'bcmap-css';
    st.textContent = `.bcmap{height:300px;border-radius:12px;border:1px solid var(--line);overflow:hidden;background:var(--sunken);z-index:0}
.bcmap.small{height:220px}
.bcmap.drawing{cursor:crosshair}
:root[data-theme="dark"] .bcmap .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .bcmap .leaflet-tile-pane{filter:invert(1) hue-rotate(180deg) brightness(.9) contrast(.9)}}
.bcmap-ed{display:flex;flex-direction:column;gap:8px}
.bcmap-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.bcmap-bar .seg{display:inline-flex;border:1px solid var(--line);border-radius:999px;overflow:hidden}
.bcmap-bar .seg button{border:0;background:var(--surface);color:var(--ink);font:inherit;font-size:.84rem;padding:7px 12px;cursor:pointer;min-height:36px}
.bcmap-bar .seg button+button{border-left:1px solid var(--line)}
.bcmap-bar .seg button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
.bcmap-bar select,.bcmap-bar input{font:inherit;font-size:.84rem;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);min-height:36px;box-sizing:border-box}
.bcmap-bar input{flex:1 1 200px;min-width:0}
.bcmap-tip{font-size:.82rem;color:var(--muted);margin:0}
.bcmap-tip b{color:var(--ink)}
.bcmap-legend{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.8rem;color:var(--muted);margin:6px 0 0}`;
    document.head.appendChild(st);
  }
  function base(L, el, opts) {
    const map = L.map(el, {zoomControl: true, attributionControl: true, scrollWheelZoom: false, ...opts}).setView(CENTER, ZOOM);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap contributors'}).addTo(map);
    return map;
  }
  const parse = v => {
    if (!v) return null;
    try { const g = typeof v === 'string' ? JSON.parse(v) : v; return g && g.type === 'FeatureCollection' && g.features && g.features.length ? g : null; } catch (e) { return null; }
  };
  // Leaflet uses [lat, lng]; GeoJSON uses [lng, lat].
  const ll = c => [c[1], c[0]];
  function draw(L, layer, g) {
    for (const f of g.features) {
      const t = f.geometry.type, c = f.geometry.coordinates;
      if (t === 'Point') {
        const r = f.properties && f.properties.radius_m;
        if (r) L.circle(ll(c), {radius: r, color: COLOR, weight: 2, fillOpacity: .18}).addTo(layer);
        L.circleMarker(ll(c), {radius: 6, color: '#fff', weight: 2, fillColor: COLOR, fillOpacity: 1}).addTo(layer);
      } else if (t === 'LineString') L.polyline(c.map(ll), {color: COLOR, weight: 6, opacity: .85}).addTo(layer);
      else if (t === 'Polygon') L.polygon(c[0].map(ll), {color: COLOR, weight: 2, fillOpacity: .18}).addTo(layer);
    }
  }
  const fit = (map, layer) => { const b = layer.getBounds && layer.getBounds(); if (b && b.isValid()) map.fitBounds(b.pad(.25), {maxZoom: 16}); };
  const describe = g => {
    const n = {Point: 0, LineString: 0, Polygon: 0};
    g.features.forEach(f => { n[f.geometry.type]++; });
    return [n.Point && `${n.Point} pin${n.Point > 1 ? 's' : ''}`, n.LineString && `${n.LineString} line${n.LineString > 1 ? 's' : ''}`, n.Polygon && `${n.Polygon} area${n.Polygon > 1 ? 's' : ''}`].filter(Boolean).join(', ');
  };

  // Read-only map on a public page.
  async function view(box, value) {
    const g = parse(value);
    if (!g || !box) return false;
    styles();
    const L = await leaflet();
    box.classList.add('bcmap', 'small');
    const map = base(L, box, {dragging: !L.Browser.mobile, tap: false});
    const layer = L.featureGroup().addTo(map);
    draw(L, layer, g);
    fit(map, layer);
    return true;
  }

  // Staff drawing tool. Fills `input.value` with the FeatureCollection (or '' when empty).
  async function editor(box, input) {
    styles();
    box.innerHTML = `<div class="bcmap-ed">
      <div class="bcmap-bar"><input type="search" placeholder="Jump to an address, like 825 Ohio Ave" aria-label="Jump to an address" data-addr><button class="btn" type="button" data-find>Find</button></div>
      <div class="bcmap-bar">
        <span class="seg" role="group" aria-label="What to draw"><button type="button" data-tool="pin" aria-pressed="true">Pin</button><button type="button" data-tool="line" aria-pressed="false">Street or pipe</button><button type="button" data-tool="area" aria-pressed="false">Area</button></span>
        <select data-radius aria-label="Circle around the pin"><option value="0">No circle</option><option value="100">100 ft circle</option><option value="250" selected>¼ block (250 ft)</option><option value="500">500 ft circle</option><option value="1320">¼ mile circle</option><option value="2640">½ mile circle</option><option value="5280">1 mile circle</option></select>
        <button class="btn primary" type="button" data-finish hidden>Finish</button>
        <button class="btn quiet" type="button" data-undo>Undo</button><button class="btn quiet" type="button" data-clear>Clear map</button>
      </div>
      <div class="bcmap" data-map></div>
      <p class="bcmap-tip" data-tip aria-live="polite"></p></div>`;
    const $ = s => box.querySelector(s);
    let L;
    try { L = await leaflet(); } catch (e) { $('[data-tip]').textContent = e.message; return null; }
    const map = base(L, $('[data-map]'));
    $('[data-map]').classList.add('drawing');
    const layer = L.featureGroup().addTo(map), sketch = L.featureGroup().addTo(map);
    let tool = 'pin', pts = [];
    let shapes = (parse(input.value) || {features: []}).features.slice();
    const FT = 0.3048;
    const save = () => { input.value = shapes.length ? JSON.stringify({type: 'FeatureCollection', features: shapes}) : ''; input.dispatchEvent(new Event('change', {bubbles: true})); };
    const tips = {pin: 'Tap the map where it is. The circle shows the area around it.', line: 'Tap along the street or pipe, point by point, then press <b>Finish</b>.', area: 'Tap each corner of the area, then press <b>Finish</b>.'};
    function redraw() {
      layer.clearLayers(); sketch.clearLayers();
      if (shapes.length) draw(L, layer, {features: shapes});
      if (pts.length) {
        (tool === 'area' && pts.length > 2 ? L.polygon(pts, {color: COLOR, dashArray: '6 6', weight: 2, fillOpacity: .1}) : L.polyline(pts, {color: COLOR, dashArray: '6 6', weight: tool === 'line' ? 5 : 2})).addTo(sketch);
        pts.forEach(p => L.circleMarker(p, {radius: 5, color: '#fff', weight: 2, fillColor: COLOR, fillOpacity: 1}).addTo(sketch));
      }
      const need = tool === 'line' ? 2 : 3;
      $('[data-finish]').hidden = tool === 'pin' || !pts.length;
      $('[data-finish]').disabled = pts.length < need;
      $('[data-radius]').hidden = tool !== 'pin';
      $('[data-tip]').innerHTML = (pts.length ? `${pts.length} point${pts.length > 1 ? 's' : ''} so far. ` : '') + tips[tool] +
        (shapes.length ? ` On the map: ${describe({features: shapes})}.` : ' Nothing on the map yet; the map is optional.');
    }
    function finish() {
      if (tool === 'line' && pts.length >= 2) shapes.push({type: 'Feature', properties: {}, geometry: {type: 'LineString', coordinates: pts.map(p => [p[1], p[0]])}});
      if (tool === 'area' && pts.length >= 3) { const r = pts.map(p => [p[1], p[0]]); r.push(r[0]); shapes.push({type: 'Feature', properties: {}, geometry: {type: 'Polygon', coordinates: [r]}}); }
      pts = []; save(); redraw();
    }
    map.on('click', e => {
      const p = [Math.round(e.latlng.lat * 1e6) / 1e6, Math.round(e.latlng.lng * 1e6) / 1e6];
      if (tool === 'pin') {
        const ft = Number($('[data-radius]').value);
        shapes.push({type: 'Feature', properties: ft ? {radius_m: Math.round(ft * FT)} : {}, geometry: {type: 'Point', coordinates: [p[1], p[0]]}});
        save();
      } else pts.push(p);
      redraw();
    });
    box.addEventListener('click', e => {
      const t = e.target.closest('[data-tool]');
      if (t) {
        if (pts.length) finish();
        tool = t.dataset.tool; box.querySelectorAll('[data-tool]').forEach(b => b.setAttribute('aria-pressed', b === t ? 'true' : 'false')); redraw();
      }
      if (e.target.closest('[data-finish]')) finish();
      if (e.target.closest('[data-undo]')) { if (pts.length) pts.pop(); else { shapes.pop(); save(); } redraw(); }
      if (e.target.closest('[data-clear]')) { pts = []; shapes = []; save(); redraw(); }
      if (e.target.closest('[data-find]')) find();
    });
    async function find() {
      const q = $('[data-addr]').value.trim(); if (!q) return;
      $('[data-tip]').textContent = 'Looking up the address…';
      try {
        const r = await fetch('/api/v1/evacuation-zone?address=' + encodeURIComponent(q)).then(x => x.json());
        const pt = r && (r.point || (r.data && r.data.point));
        if (!pt) { $('[data-tip]').textContent = (r && r.message) || 'No Bay County address matched. Try the house number and street.'; return; }
        map.setView([pt.lat, pt.lng], 17); redraw();
      } catch (err) { $('[data-tip]').textContent = 'The address lookup is not answering. Move the map by hand.'; }
    }
    $('[data-addr]').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); find(); } });
    redraw();
    if (shapes.length) fit(map, layer);
    setTimeout(() => map.invalidateSize(), 50);
    // The form calls this after reset or when it loads a saved post.
    return {set(v) { pts = []; shapes = (parse(v) || {features: []}).features.slice(); input.value = shapes.length ? JSON.stringify({type: 'FeatureCollection', features: shapes}) : ''; redraw(); if (shapes.length) fit(map, layer); else map.setView(CENTER, ZOOM); },
      refresh() { map.invalidateSize(); }};
  }

  window.BCMap = {view, editor, parse, describe};
})();
