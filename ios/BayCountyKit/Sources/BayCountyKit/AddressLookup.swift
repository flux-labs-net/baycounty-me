import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// My Address (site/address.js): find a Bay County address on the county's public GIS server and look up
/// everything that applies to it. Lookups go straight to Bay County's and FEMA's map servers; nothing is sent to BayCounty.me.
public enum AddressParser {
    static let types: [String: [String]] = {
        var t: [String: [String]] = [:]
        let pairs: [(String, String)] = [("DRIVE", "DR"), ("DRV", "DR"), ("DR", "DR"), ("STREET", "ST"), ("STR", "ST"), ("ST", "ST"), ("AVENUE", "AVE"), ("AV", "AVE"), ("AVN", "AVE"), ("AVE", "AVE"),
            ("ROAD", "RD"), ("RD", "RD"), ("BOULEVARD", "BLVD"), ("BLV", "BLVD"), ("BLVD", "BLVD"), ("LANE", "LN"), ("LN", "LN"), ("COURT", "CT"), ("CRT", "CT"), ("CT", "CT"), ("COURTS", "CTS"),
            ("CIRCLE", "CIR"), ("CIRC", "CIR"), ("CIR", "CIR"), ("PLACE", "PL"), ("PL", "PL"), ("TERRACE", "TER"), ("TERR", "TER"), ("TER", "TER"), ("TRAIL", "TRL"), ("TR", "TRL"), ("TRL", "TRL"),
            ("PARKWAY", "PKWY"), ("PKY", "PKWY"), ("PKWY", "PKWY"), ("PLAZA", "PLZ"), ("PLZ", "PLZ"), ("POINT", "PT"), ("PT", "PT"), ("CROSSING", "XING"), ("XING", "XING"),
            ("LANDING", "LNDG"), ("LNDG", "LNDG"), ("MANOR", "MNR"), ("MNR", "MNR"), ("SQUARE", "SQ"), ("SQ", "SQ"), ("ALLEY", "ALY"), ("ALY", "ALY"), ("BEND", "BND"), ("BND", "BND"),
            ("GARDENS", "GDNS"), ("GDNS", "GDNS"), ("KNOLL", "KNL"), ("KNL", "KNL"), ("TRACE", "TRCE"), ("TRCE", "TRCE"), ("CORNER", "COR"), ("COR", "COR"),
            ("LOOP", "LOOP"), ("RUN", "RUN"), ("PATH", "PATH"), ("PASS", "PASS"), ("WAY", "WAY"), ("TURN", "TURN"), ("ISLE", "ISLE")]
        for (k, v) in pairs { t[k] = [v] }
        t["COVE"] = ["COVE", "CV"]; t["CV"] = ["COVE", "CV"]
        return t
    }()
    static let dirs = ["NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHWEST": "NW", "N": "N", "S": "S", "E": "E", "W": "W", "NW": "NW"]
    static let ordinals = ["FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH", "SEVENTH": "7TH", "EIGHTH": "8TH", "NINTH": "9TH", "TENTH": "10TH",
        "ELEVENTH": "11TH", "TWELFTH": "12TH", "THIRTEENTH": "13TH", "FOURTEENTH": "14TH", "FIFTEENTH": "15TH", "SIXTEENTH": "16TH", "SEVENTEENTH": "17TH", "EIGHTEENTH": "18TH", "NINETEENTH": "19TH", "TWENTIETH": "20TH"]
    static let places = ["PANAMA CITY BEACH", "PANAMA CITY", "LYNN HAVEN", "CALLAWAY", "SPRINGFIELD", "PARKER", "MEXICO BEACH", "SOUTHPORT", "FOUNTAIN", "YOUNGSTOWN", "TYNDALL AFB", "BAYOU GEORGE", "BAY COUNTY"]

    public struct Token: Equatable, Sendable {
        public enum Kind: String, Sendable { case name, type, dir }
        public let alts: [String]
        public let kind: Kind
        public var word = false
        public var partial = false
    }

    public struct Parsed: Equatable, Sendable {
        public let house: String
        public let unit: String
        public let place: String
        public let tokens: [Token]
    }

    static func re(_ pattern: String, _ s: String, _ template: String) -> String {
        s.replacingOccurrences(of: pattern, with: template, options: .regularExpression)
    }

    public static func parse(_ raw: String) -> Parsed? {
        var s = raw.uppercased()
        s = re(#"[.,'"%_\\]"#, s, " ")
        s = re(#"\s+"#, s, " ").trimmingCharacters(in: .whitespaces)
        s = re(#"\b(FL|FLORIDA)\b"#, s, " ")
        s = re(#"\b\d{5}(-\d{4})?\s*$"#, s, " ")
        s = re(#"\s+"#, s, " ").trimmingCharacters(in: .whitespaces)
        var place = ""
        for p in places where s.hasSuffix(" " + p) {
            place = p
            s = String(s.dropLast(p.count + 1)).trimmingCharacters(in: .whitespaces)
            break
        }
        var unit = ""
        if let m = s.range(of: #"\s(?:#\s*|(?:APT|APARTMENT|UNIT|STE|SUITE|BLDG|LOT|RM|SPC|TRLR)\s+#?\s*)([A-Z0-9-]+)\s*$"#, options: .regularExpression) {
            let tail = String(s[m]).replacingOccurrences(of: "#", with: " ")
            unit = tail.split(separator: " ").last.map(String.init) ?? ""
            s = String(s[..<m.lowerBound]).trimmingCharacters(in: .whitespaces)
        }
        guard let hm = s.range(of: #"^\d+"#, options: .regularExpression) else { return nil }
        let house = String(s[hm])
        var rest = String(s[hm.upperBound...]).trimmingCharacters(in: .whitespaces)
        // "123 A MAIN ST": a letter right after the house number is part of the number, not the street
        if rest.count >= 2, let first = rest.first, first.isLetter, rest.dropFirst().first == " " { rest = String(rest.dropFirst(2)) }
        var joined = rest
        joined = re(#"\b(?:US|U S|SR|S R|STATE ROAD|STATE RD|CR|C R|COUNTY ROAD|COUNTY RD)\s*(?:HWY|HIGHWAY)?\s*(\d+[A-Z]?)\b"#, joined, "HIGHWAY $1")
        joined = re(#"\bHWY\b"#, joined, "HIGHWAY")
        joined = re(#"\bMLK\b"#, joined, "MARTIN LUTHER KING JR")
        joined = re(#"\bJUNIOR\b"#, joined, "JR")
        joined = re(#"\bMOUNT\b"#, joined, "MT")
        let w = joined.split(separator: " ").map(String.init)
        var toks = [Token]()
        for (i, t) in w.enumerated() {
            let last = i == w.count - 1
            if let o = ordinals[t] { toks.append(Token(alts: [o], kind: .name)); continue }
            if let d = dirs[t], i == 0 || last { toks.append(Token(alts: [d], kind: .dir)); continue }
            if (t == "ST" || t == "SAINT") && !last { toks.append(Token(alts: ["ST", "SAINT"], kind: .name, word: true)); continue }
            if let ty = types[t], last, i > 0 { toks.append(Token(alts: ty, kind: .type)); continue }
            toks.append(Token(alts: [t], kind: .name, partial: last))
        }
        return Parsed(house: house, unit: unit, place: place, tokens: toks)
    }

    static func sq(_ s: String) -> String { s.replacingOccurrences(of: "'", with: "''") }

    /// SQL where clause for Bay County's address point layer, keeping only some token kinds.
    public static func whereClause(_ a: Parsed, keep: [Token.Kind], unit: Bool = true) -> String {
        var parts = ["ADDRESS LIKE '\(a.house) %'"]
        for t in a.tokens where keep.contains(t.kind) {
            let ors = t.alts.map { x -> String in
                if t.kind == .name && !t.word {
                    return t.partial ? "ADDRESS LIKE '% \(sq(x))%'" : "(ADDRESS LIKE '% \(sq(x)) %' OR ADDRESS LIKE '% \(sq(x))')"
                }
                return "(ADDRESS LIKE '% \(sq(x)) %' OR ADDRESS LIKE '% \(sq(x))')"
            }
            parts.append("(" + ors.joined(separator: " OR ") + ")")
        }
        if unit && !a.unit.isEmpty { parts.append("(UNIT = '\(sq(a.unit))' OR UNIT LIKE '\(sq(a.unit))%')") }
        return parts.joined(separator: " AND ")
    }

    /// "1614 OHIO AVE" -> "1614 Ohio Ave"; keeps NE/NW/US/CR/SR in capitals.
    public static func titleCase(_ s: String) -> String {
        let words = s.lowercased().split(separator: " ", omittingEmptySubsequences: false).map { w -> String in
            let up = w.uppercased()
            if ["NE", "NW", "SE", "SW", "US", "CR", "SR"].contains(up) { return up }
            return w.prefix(1).uppercased() + w.dropFirst()
        }
        return words.joined(separator: " ")
    }
}

/// 32-bit FNV-1a, the same hash the site uses to split per-parcel files (addr_page.shard_key).
public func parcelShard(_ pid: String, count n: Int) -> String {
    var h: UInt32 = 0x811c9dc5
    for c in pid.utf8 { h = (h ^ UInt32(c)) &* 0x01000193 }
    return "h\(h % UInt32(n))"
}

public struct GeoPoint: Codable, Hashable, Sendable {
    public let x: Double   // longitude
    public let y: Double   // latitude
    public init(x: Double, y: Double) { self.x = x; self.y = y }

    /// Great-circle distance in miles.
    public func miles(to b: GeoPoint) -> Double {
        let R = 3958.8, t = Double.pi / 180
        let dLat = (b.y - y) * t, dLon = (b.x - x) * t
        let h = pow(sin(dLat / 2), 2) + cos(y * t) * cos(b.y * t) * pow(sin(dLon / 2), 2)
        return 2 * R * asin(sqrt(h))
    }
}

/// One address point from Bay County's address layer.
public struct AddressMatch: Codable, Hashable, Identifiable, Sendable {
    public let address: String
    public let unit: String?
    public let community: String?
    public let zip: String?
    public let renum: String?
    public let point: GeoPoint
    public var id: String { address + (unit ?? "") + (zip ?? "") }
    public var display: String { AddressParser.titleCase(address) + ((unit ?? "").trimmingCharacters(in: .whitespaces).isEmpty ? "" : " #\(unit!)") }
    public var subtitle: String { [community, zip].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ") }
}

/// Bay County GIS and FEMA flood map queries (ArcGIS REST).
public final class GISClient: @unchecked Sendable {
    public static let county = URL(string: "https://gis.baycountyfl.gov/arcgis/rest/services")!
    public static let fema = URL(string: "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer")!
    public static let panamaCity = URL(string: "https://services3.arcgis.com/RfAh242jlP6Nb5vP/arcgis/rest/services")!
    public static let agol = URL(string: "https://services1.arcgis.com/QB0VWfqR9MD4lF0F/arcgis/rest/services")!

    public struct Feature: Sendable {
        public let attributes: [String: JSONValue]
        public let geometry: GeoPoint?
        public func s(_ k: String) -> String? {
            guard let v = attributes[k], !v.isEmpty else { return nil }
            return v.stringValue?.trimmingCharacters(in: .whitespaces)
        }
        public func n(_ k: String) -> Double? { attributes[k]?.doubleValue }
    }

    struct Response: Decodable {
        struct F: Decodable {
            let attributes: [String: JSONValue]?
            let geometry: [String: JSONValue]?
        }
        struct Err: Decodable { let message: String? }
        let features: [F]?
        let error: Err?
    }

    public enum GISError: LocalizedError {
        case server(String)
        public var errorDescription: String? {
            switch self { case .server(let m): "Bay County's map server didn't answer (\(m))." }
        }
    }

    let session: URLSession
    public init(session: URLSession = .shared) { self.session = session }

    public func query(_ base: URL, _ path: String, _ params: [String: String], timeout: TimeInterval = 15) async throws -> [Feature] {
        var c = URLComponents(url: base.appendingPathComponent(path).appendingPathComponent("query"), resolvingAgainstBaseURL: false)!
        var p = ["f": "json", "returnGeometry": "false", "outFields": "*"]
        p.merge(params) { _, new in new }
        c.queryItems = p.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) }
        // ArcGIS reads '+' in a query as a space; keep literal pluses (none expected) safe.
        c.percentEncodedQuery = c.percentEncodedQuery?.replacingOccurrences(of: "+", with: "%2B")
        var req = URLRequest(url: c.url!, timeoutInterval: timeout)
        req.setValue("BayCounty.me iOS", forHTTPHeaderField: "User-Agent")
        let (data, resp) = try await session.data(for: req)
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else { throw GISError.server("HTTP \(code)") }
        let r = try JSONDecoder().decode(Response.self, from: data)
        if let e = r.error { throw GISError.server(e.message ?? "error") }
        return (r.features ?? []).map { f in
            var pt: GeoPoint? = nil
            if let g = f.geometry, let x = g["x"]?.doubleValue, let y = g["y"]?.doubleValue { pt = GeoPoint(x: x, y: y) }
            return Feature(attributes: f.attributes ?? [:], geometry: pt)
        }
    }

    static func pointJSON(_ pt: GeoPoint) -> String { #"{"x":\#(pt.x),"y":\#(pt.y),"spatialReference":{"wkid":4326}}"# }

    func atPoint(_ path: String, _ pt: GeoPoint, base: URL = GISClient.county, extra: [String: String] = [:]) async -> [Feature]? {
        var p = ["geometry": Self.pointJSON(pt), "geometryType": "esriGeometryPoint", "inSR": "4326", "spatialRel": "esriSpatialRelIntersects"]
        p.merge(extra) { _, n in n }
        return try? await query(base, path, p)
    }

    func nearest(_ layer: Int, _ pt: GeoPoint) async -> (Feature, Double)? {
        let p = ["geometry": Self.pointJSON(pt), "geometryType": "esriGeometryPoint", "inSR": "4326", "distance": "10",
                 "units": "esriSRUnit_StatuteMile", "returnGeometry": "true", "outSR": "4326"]
        guard let fs = try? await query(Self.county, "Admin_A12/MapServer/\(layer)", p) else { return nil }
        return fs.compactMap { f in f.geometry.map { (f, pt.miles(to: $0)) } }.min { $0.1 < $1.1 }
    }

    // MARK: Finding an address

    public func search(_ text: String) async throws -> (matches: [AddressMatch], relaxed: Bool) {
        guard let a = AddressParser.parse(text), !a.tokens.isEmpty else { return ([], false) }
        let opts = ["outFields": "ADDRESS,UNIT,CMNTY,ZIP,RENUM", "returnGeometry": "true", "outSR": "4326", "resultRecordCount": "25", "orderByFields": "ADDRESS"]
        var found: [Feature] = [], relaxed = false
        for keep in [[AddressParser.Token.Kind.name, .type, .dir], [.name]] {
            var p = opts; p["where"] = AddressParser.whereClause(a, keep: keep)
            found = try await query(Self.county, "Admin_A12/MapServer/3", p)
            if !found.isEmpty { relaxed = keep.count == 1 && a.tokens.contains { $0.kind != .name }; break }
        }
        if found.isEmpty && !a.unit.isEmpty {
            var p = opts; p["where"] = AddressParser.whereClause(a, keep: [.name], unit: false)
            found = try await query(Self.county, "Admin_A12/MapServer/3", p)
            relaxed = !found.isEmpty
        }
        var matches = found.compactMap(Self.match)
        if !a.place.isEmpty {
            matches.sort { ($0.community ?? "").uppercased() == a.place && ($1.community ?? "").uppercased() != a.place }
        }
        return (Array(matches.prefix(10)), relaxed)
    }

    /// The address points nearest a location (for "Use my location").
    public func addresses(near pt: GeoPoint) async throws -> [AddressMatch] {
        let p = ["geometry": Self.pointJSON(pt), "geometryType": "esriGeometryPoint", "inSR": "4326", "distance": "150", "units": "esriSRUnit_Foot",
                 "outFields": "ADDRESS,UNIT,CMNTY,ZIP,RENUM", "returnGeometry": "true", "outSR": "4326", "resultRecordCount": "40"]
        let fs = try await query(Self.county, "Admin_A12/MapServer/3", p)
        var seen = Set<String>()
        return fs.compactMap(Self.match)
            .sorted { pt.miles(to: $0.point) < pt.miles(to: $1.point) }
            .filter { seen.insert($0.address).inserted }
            .prefix(8).map { $0 }
    }

    static func match(_ f: Feature) -> AddressMatch? {
        guard let addr = f.s("ADDRESS"), let g = f.geometry else { return nil }
        return AddressMatch(address: addr, unit: f.s("UNIT"), community: f.s("CMNTY"), zip: f.s("ZIP"), renum: f.s("RENUM"), point: g)
    }

    // MARK: Flood map

    func femaAt(_ layer: Int, _ pt: GeoPoint, fields: String) async throws -> [Feature] {
        try await query(Self.fema, "\(layer)", ["geometry": Self.pointJSON(pt), "geometryType": "esriGeometryPoint", "inSR": "4326",
                                                 "spatialRel": "esriSpatialRelIntersects", "outFields": fields])
    }

    public struct Flood: Sendable {
        public enum Source: Sendable { case fema, county }
        public let source: Source
        public let zone: Feature?
        public let panel: Feature?
        public let lomr: Feature?
    }

    public func flood(at pt: GeoPoint) async -> Flood? {
        do {
            // FEMA's server drops some requests; like the website, try the flood zones twice before falling back.
            let fields = "FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,V_DATUM,DEPTH"
            async let zonesQ: [Feature] = { do { return try await femaAt(28, pt, fields: fields) } catch { return try await femaAt(28, pt, fields: fields) } }()
            async let panelsQ = try? femaAt(3, pt, fields: "FIRM_PAN,EFF_DATE")
            async let lomrQ = try? femaAt(1, pt, fields: "CASE_NO,EFF_DATE")
            var zones = try await zonesQ
            let rank: (Feature) -> Double = { z in
                (z.s("SFHA_TF") == "T" ? 1000 : 0) + ((z.s("FLD_ZONE") ?? "").hasPrefix("V") ? 500 : 0)
                    + max(0, z.n("STATIC_BFE") ?? 0) + ((z.s("ZONE_SUBTY") ?? "").contains("0.2") ? 100 : 0)
            }
            zones.sort { rank($0) > rank($1) }
            return Flood(source: .fema, zone: zones.first, panel: await panelsQ?.first, lomr: await lomrQ?.first)
        } catch {
            guard let c = await atPoint("Admin_A12/MapServer/51", pt) else { return nil }
            return Flood(source: .county, zone: c.first, panel: nil, lomr: nil)
        }
    }
}
