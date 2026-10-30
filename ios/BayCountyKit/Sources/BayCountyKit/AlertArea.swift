import Foundation

/// Where an alert or notice applies, as government staff drew it in the /staff workspace (site/area_map.js): pins
/// (with a circle radius in meters), street or pipe lines, and areas. Stored as a GeoJSON FeatureCollection in the
/// `geometry` text of a live notice (/api/v1/emergency, /api/v1/emergency-timeline) or a staff notice.
public struct AlertArea: Equatable, Sendable {
    public struct Coord: Equatable, Sendable {
        public let lat: Double, lng: Double
        public init(lat: Double, lng: Double) { self.lat = lat; self.lng = lng }
    }
    public enum Shape: Equatable, Sendable {
        /// A pin; radius in meters when staff drew a circle around it.
        case pin(Coord, radius: Double?)
        case line([Coord])
        /// An area: the outer ring first, then any holes.
        case area([[Coord]])
    }

    public let shapes: [Shape]

    /// Every point the map has to show, circles included (their edge, roughly), for fitting the map around them.
    public var bounds: (south: Double, west: Double, north: Double, east: Double)? {
        var pts: [Coord] = []
        for s in shapes {
            switch s {
            case .pin(let c, let r):
                pts.append(c)
                if let r, r > 0 {
                    let dLat = r / 111_320, dLng = r / (111_320 * cos(c.lat * .pi / 180))
                    pts += [Coord(lat: c.lat - dLat, lng: c.lng - dLng), Coord(lat: c.lat + dLat, lng: c.lng + dLng)]
                }
            case .line(let cs): pts += cs
            case .area(let rings): pts += rings.first ?? []
            }
        }
        guard let f = pts.first else { return nil }
        return pts.reduce((f.lat, f.lng, f.lat, f.lng)) { b, p in (min(b.0, p.lat), min(b.1, p.lng), max(b.2, p.lat), max(b.3, p.lng)) }
    }

    /// nil when there's no drawing (empty, not GeoJSON, or nothing drawable in it).
    public static func parse(_ text: String?) -> AlertArea? {
        guard let text, let data = text.data(using: .utf8),
              case .object(let obj)? = try? JSONDecoder().decode(JSONValue.self, from: data),
              obj["type"]?.stringValue == "FeatureCollection", case .array(let features)? = obj["features"] else { return nil }
        func arr(_ v: JSONValue?) -> [JSONValue] { if case .array(let a)? = v { return a }; return [] }
        // GeoJSON positions are [lng, lat].
        func coord(_ v: JSONValue?) -> Coord? {
            let a = arr(v)
            guard a.count >= 2, case .number(let lng) = a[0], case .number(let lat) = a[1], abs(lat) <= 90, abs(lng) <= 180 else { return nil }
            return Coord(lat: lat, lng: lng)
        }
        func line(_ v: JSONValue?) -> [Coord] { arr(v).compactMap(coord) }
        func rings(_ v: JSONValue?) -> [[Coord]] { arr(v).map(line).filter { $0.count >= 3 } }
        var shapes: [Shape] = []
        for case .object(let f) in features {
            guard case .object(let g)? = f["geometry"], let type = g["type"]?.stringValue else { continue }
            let c = g["coordinates"]
            switch type {
            case "Point":
                if let p = coord(c) {
                    var r: Double?
                    if case .object(let props)? = f["properties"], case .number(let m)? = props["radius_m"], m > 0 { r = m }
                    shapes.append(.pin(p, radius: r))
                }
            case "LineString":
                let l = line(c); if l.count >= 2 { shapes.append(.line(l)) }
            case "MultiLineString":
                for part in arr(c) { let l = line(part); if l.count >= 2 { shapes.append(.line(l)) } }
            case "Polygon":
                let r = rings(c); if !r.isEmpty { shapes.append(.area(r)) }
            case "MultiPolygon":
                for poly in arr(c) { let r = rings(poly); if !r.isEmpty { shapes.append(.area(r)) } }
            default: continue
            }
        }
        return shapes.isEmpty ? nil : AlertArea(shapes: shapes)
    }

    /// Pins dropped in the staff app, each with the same circle (meters; nil or 0 = no circle), as the GeoJSON
    /// FeatureCollection the workspace stores (api/_gov.js areaShape). nil when there are no pins.
    public static func pinsGeoJSON(_ pins: [Coord], radius: Double?) -> String? {
        guard !pins.isEmpty else { return nil }
        let r = (radius ?? 0) > 0 ? radius! : 0
        let f = pins.map { p in
            let props = r > 0 ? #"{"radius_m":\#(Int(r))}"# : "{}"
            return #"{"type":"Feature","properties":\#(props),"geometry":{"type":"Point","coordinates":[\#(round6(p.lng)),\#(round6(p.lat))]}}"#
        }
        return #"{"type":"FeatureCollection","features":[\#(f.joined(separator: ","))]}"#
    }
    private static func round6(_ v: Double) -> String { String(format: "%.6f", v) }

    /// The first live notice with a drawn map, for the map under the home screen's alert strip.
    public static func firstMapped(_ notices: [Row]) -> (notice: Row, area: AlertArea)? {
        for n in notices { if let a = parse(n.string("geometry")) { return (n, a) } }
        return nil
    }
}
