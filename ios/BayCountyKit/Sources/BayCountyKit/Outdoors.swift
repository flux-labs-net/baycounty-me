import Foundation

/// Beaches (/beaches) and parks (/parks), from the beach-conditions, beach-water-sites, beach-access, beach-parking,
/// parks, boat-ramps, trails and recreation-departments datasets. Same rules as site/outdoors_page.py.
public enum Outdoors {
    public static let beachDatasets = ["beach-conditions", "beach-water-sites", "beach-access", "beach-parking"]
    public static let parkDatasets = ["parks", "boat-ramps", "trails", "recreation-departments"]

    /// The latest forecast periods, in order. The first carries the flag color reported that day.
    public static func forecast(_ rows: [Row]) -> [Row] {
        rows.filter { $0.string("kind") == "forecast" }.sorted { ($0.number("sort_order") ?? 0) < ($1.number("sort_order") ?? 0) }
    }

    public static func alerts(_ rows: [Row]) -> [Row] { rows.filter { $0.string("kind") == "alert" } }

    /// What each flag color means, in the order the site lists them (double red first).
    public static func legend(_ rows: [Row]) -> [Row] {
        rows.filter { $0.string("kind") == "legend" }.sorted { ($0.number("sort_order") ?? 0) < ($1.number("sort_order") ?? 0) }
    }

    /// Today's flag color ("Yellow", "Double red", ...) and what it means, or nil when none was reported.
    public static func flag(_ rows: [Row]) -> (color: String, meaning: String)? {
        guard let c = forecast(rows).first?.string("flag_color") else { return nil }
        return (c, legend(rows).first { $0.string("flag_color") == c }?.string("meaning") ?? "")
    }

    /// The flag's color as hex RGB, matching the site.
    public static func flagHex(_ color: String) -> UInt32 {
        switch color {
        case "Double red": 0xC62828
        case "Red": 0xE53935
        case "Yellow": 0xF2C230
        case "Green": 0x2E9E5B
        case "Purple": 0x7E57C2
        default: 0x9AA3AF
        }
    }

    /// Active sampling sites, west to east.
    public static func waterSites(_ rows: [Row]) -> [Row] {
        rows.filter { $0.bool("active") == true }.sorted { ($0.number("longitude") ?? 0) < ($1.number("longitude") ?? 0) }
    }

    /// Sites whose latest rated sample was Poor within `days` of `today` (yyyy-MM-dd).
    public static func poorNow(_ rows: [Row], today: String, days: Int = 45) -> [Row] {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
        guard let t = f.date(from: today), let from = Calendar(identifier: .gregorian).date(byAdding: .day, value: -days, to: t) else { return [] }
        let cut = f.string(from: from)
        return waterSites(rows).filter { $0.string("latest_rating") == "Poor" && ($0.string("latest_date") ?? "") >= cut }
    }

    public enum AccessFilter: String, Sendable, CaseIterable {
        case all, wheelchair, driveOn, parking
        public var label: String { switch self { case .all: "All"; case .wheelchair: "Wheelchair"; case .driveOn: "Drive-on"; case .parking: "Parking" } }
    }

    /// Beach accesses west to east, filtered and searched by name, number or street.
    public static func accesses(_ rows: [Row], filter: AccessFilter = .all, query: String = "") -> [Row] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return rows.filter { r in
            let ok: Bool = switch filter {
            case .all: true
            case .wheelchair: r.bool("wheelchair_access") == true
            case .driveOn: r.bool("vehicle_access") == true
            case .parking: r.bool("parking") == true
            }
            let text = [r.string("name"), r.string("address"), r.string("area")].compactMap { $0 }.joined(separator: " ").lowercased()
            return ok && (q.isEmpty || text.contains(q))
        }
        .sorted { ($0.number("longitude") ?? 0) < ($1.number("longitude") ?? 0) }
    }

    /// The short tags for what's at an access ("Wheelchair", "Drive-on", "Parking (40)", ...).
    public static func accessTags(_ r: Row) -> [String] {
        var t: [String] = []
        if r.bool("wheelchair_access") == true { t.append("Wheelchair") }
        if r.bool("vehicle_access") == true { t.append("Drive-on") }
        if r.bool("parking") == true { t.append("Parking" + (r.number("parking_spaces").map { " (\(Int($0)))" } ?? "")) }
        if r.bool("restroom") == true { t.append("Restrooms") }
        if r.bool("shower") == true { t.append("Showers") }
        if r.bool("lifeguard") == true { t.append("Lifeguard") }
        return t
    }

    public static let amenities: [(key: String, label: String)] = [
        ("playground", "Playground"), ("restroom", "Restrooms"), ("pavilion", "Pavilion"), ("picnic_tables", "Picnic tables"), ("trail", "Trail"),
        ("boat_ramp", "Boat ramp"), ("boat_dock", "Dock"), ("fishing_pier", "Fishing pier"), ("beach_access", "Beach access"), ("baseball", "Baseball"),
        ("basketball", "Basketball"), ("football", "Football"), ("soccer", "Soccer"), ("tennis", "Tennis"), ("volleyball", "Volleyball"),
        ("community_building", "Community building"),
    ]

    public enum ParkFilter: String, Sendable, CaseIterable {
        case all, playground, restroom, sports, water, trail, beach
        public var label: String {
            switch self {
            case .all: "Any park"; case .playground: "Playground"; case .restroom: "Restrooms"; case .sports: "Sports"
            case .water: "Ramp, dock or pier"; case .trail: "Trail"; case .beach: "Beach access"
            }
        }
    }

    public static func has(_ p: Row, _ f: ParkFilter) -> Bool {
        switch f {
        case .all: true
        case .playground: p.bool("playground") == true
        case .restroom: p.bool("restroom") == true
        case .sports: ["baseball", "basketball", "football", "soccer", "tennis", "volleyball"].contains { p.bool($0) == true }
        case .water: ["boat_ramp", "boat_dock", "fishing_pier"].contains { p.bool($0) == true }
        case .trail: p.bool("trail") == true
        case .beach: p.bool("beach_access") == true
        }
    }

    /// Parks by name, filtered by amenity, government (gov_id, or "other" for state land) and search text.
    public static func parks(_ rows: [Row], filter: ParkFilter = .all, gov: String = "", query: String = "") -> [Row] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return rows.filter { p in
            let g = p.string("gov_id") ?? "other"
            let text = [p.string("name"), p.string("address")].compactMap { $0 }.joined(separator: " ").lowercased()
            return has(p, filter) && (gov.isEmpty || g == gov) && (q.isEmpty || text.contains(q))
        }
        .sorted { ($0.string("name") ?? "") < ($1.string("name") ?? "") }
    }

    public static func parkTags(_ p: Row) -> [String] { amenities.filter { p.bool($0.key) == true }.map(\.label) }

    /// Driving directions to a row's map point (Apple Maps).
    public static func directions(_ r: Row) -> URL? {
        guard let lat = r.number("latitude"), let lon = r.number("longitude") else { return nil }
        return URL(string: "https://maps.apple.com/?daddr=\(lat),\(lon)")
    }
}
