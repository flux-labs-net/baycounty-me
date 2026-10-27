import Foundation

/// Emergencies and alerts (/emergency) and Hurricane prep (/hurricane-prep). The live list comes from
/// `/api/v1/emergency` (checked every 5 minutes on the server); the datasets hold the zones, shelters, numbers,
/// the notices archive, prep steps, disaster declarations and FEMA rebuild money by ZIP code. Mirrors
/// site/emergency_page.py, site/hurricane_prep_page.py and api/_emergency_feed.js.
public enum Emergency {
    public static let datasets = ["evacuation-zones", "emergency-shelters", "emergency-resources", "emergency-notices"]
    public static let prepDatasets = ["hurricane-prep", "disaster-declarations", "rebuild-money"]
    public static let feedPath = "/api/v1/emergency"

    // MARK: - Kinds

    public static let kinds = ["evacuation", "weather", "shelter", "boil-water", "road", "utility", "storm"]

    public static func label(_ kind: String) -> String {
        switch kind {
        case "evacuation": "Evacuation order"
        case "weather": "Weather"
        case "shelter": "Shelter open"
        case "boil-water": "Boil-water notice"
        case "road": "Road closure"
        case "utility": "Water or utility"
        case "storm": "Storm update"
        default: "Notice"
        }
    }

    public static func symbol(_ kind: String) -> String {
        switch kind {
        case "evacuation": "car.side.arrowtriangle.up.fill"
        case "weather": "cloud.bolt.rain"
        case "shelter": "house.lodge"
        case "boil-water": "drop.triangle"
        case "road": "road.lanes"
        case "utility": "drop"
        default: "megaphone"
        }
    }

    static let severityRank = ["extreme": 0, "severe": 1, "moderate": 2, "minor": 3, "info": 4]

    /// Most serious first, then newest.
    public static func sorted(_ notices: [Row]) -> [Row] {
        notices.sorted { a, b in
            let ra = severityRank[a.string("severity") ?? ""] ?? 5, rb = severityRank[b.string("severity") ?? ""] ?? 5
            if ra != rb { return ra < rb }
            return (a.first(["updated", "issued"]) ?? "") > (b.first(["updated", "issued"]) ?? "")
        }
    }

    /// The headline line, the same wording as the site and the API.
    public static func headline(_ notices: [Row]) -> String {
        let evac = notices.filter { $0.string("kind") == "evacuation" }
        if let e = evac.first {
            let z = e.string("zones").map { $0.contains(",") ? " for Zones \($0)" : " for Zone \($0)" } ?? ""
            return "Evacuation order in effect\(z)."
        }
        let weather = notices.filter { $0.string("kind") == "weather" }
        if let w = weather.first(where: { ($0.string("event") ?? "").range(of: "Warning|Emergency", options: .regularExpression) != nil }) {
            return "\(w.string("event") ?? "A warning") in effect."
        }
        if !weather.isEmpty { return "\(weather.count) weather \(weather.count == 1 ? "advisory or watch" : "advisories and watches") in effect." }
        return "No weather warnings or evacuation orders right now."
    }

    // MARK: - The live feed

    public struct Feed: Sendable {
        public let headline: String
        public let checkedAt: Date?
        public let notices: [Row]
        public let shelters: [Row]
        public let zones: [Row]
        public let counts: [String: Int]
        public var sheltersOpen: Int { shelters.filter { $0.string("status") == "open" }.count }

        public func count(_ kind: String) -> Int { counts[kind] ?? notices.filter { $0.string("kind") == kind }.count }
    }

    public static func parseFeed(_ data: Data) throws -> Feed {
        let o = try JSONDecoder().decode([String: JSONValue].self, from: data)
        let rows: (String) -> [Row] = { key in
            (o[key]?.arrayValue ?? []).enumerated().compactMap { i, v in v.objectValue.map { Row(id: i, values: $0) } }
        }
        var counts: [String: Int] = [:]
        for (k, v) in o["counts"]?.objectValue ?? [:] { counts[k] = v.doubleValue.map { Int($0) } }
        let notices = rows("notices")
        return Feed(headline: o["headline"]?.stringValue ?? headline(notices), checkedAt: o["checked_at"]?.stringValue.flatMap(parseISO),
                    notices: notices, shelters: rows("shelters"), zones: rows("zones"), counts: counts)
    }

    /// When the live feed can't be reached: the active notices from the last daily archive, and the dataset shelters.
    public static func offlineFeed(notices: [Row], shelters: [Row], zones: [Row]) -> Feed {
        let active = sorted(notices.filter { $0.string("status") == "active" })
        let sh = shelters.map { r -> Row in
            var v = r.values
            if v["type"] == nil { v["type"] = r["shelter_type"] }
            return Row(id: r.id, values: v)
        }
        return Feed(headline: headline(active), checkedAt: nil, notices: active, shelters: sh, zones: zones, counts: [:])
    }

    // MARK: - Evacuation zone lookup

    public struct ZoneResult: Sendable {
        public let found: Bool
        public let zone: String?
        public let address: String?
        public let whatToDo: String
        public let orders: [(title: String, includesYou: Bool)]
        public let nearestShelters: [Row]
        public let lat: Double?
        public let lng: Double?
    }

    public static func zoneURL(address: String, site: URL = BayCountyClient.site) -> URL {
        var c = URLComponents(url: site.appendingPathComponent("api/v1/evacuation-zone"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "address", value: address)]
        return c.url!
    }

    public static func zoneURL(lat: Double, lng: Double, site: URL = BayCountyClient.site) -> URL {
        var c = URLComponents(url: site.appendingPathComponent("api/v1/evacuation-zone"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "lat", value: String(format: "%.5f", lat)), URLQueryItem(name: "lng", value: String(format: "%.5f", lng))]
        return c.url!
    }

    public static func parseZone(_ data: Data) throws -> ZoneResult {
        let o = try JSONDecoder().decode([String: JSONValue].self, from: data)
        let found = o["found"]?.boolValue ?? false
        let addr = o["address"]?.objectValue
        let place = [addr?["address"]?.stringValue, addr?["community"]?.stringValue].compactMap { $0 }.joined(separator: ", ")
        let pt = o["point"]?.objectValue
        let orders = (o["orders_now"]?.arrayValue ?? []).compactMap { $0.objectValue }.map { (title: $0["title"]?.stringValue ?? "", includesYou: $0["includes_you"]?.boolValue ?? false) }
        let shelters = (o["nearest_shelters"]?.arrayValue ?? []).enumerated().compactMap { i, v in v.objectValue.map { Row(id: i, values: $0) } }
        return ZoneResult(found: found, zone: o["zone"]?.stringValue, address: place.isEmpty ? o["query"]?.stringValue : place,
                          whatToDo: o["what_to_do"]?.stringValue ?? o["message"]?.stringValue ?? "",
                          orders: orders, nearestShelters: shelters, lat: pt?["lat"]?.doubleValue, lng: pt?["lng"]?.doubleValue)
    }

    // MARK: - Shelters

    public static let shelterTypes = ["general", "special-needs", "pet-friendly", "extreme-weather", "mass-care", "recovery", "other"]

    public static func shelterTypeLabel(_ t: String) -> String {
        switch t {
        case "special-needs": "Special needs"
        case "general": "General population"
        case "mass-care": "Mass care support"
        case "recovery": "After the storm"
        case "extreme-weather": "Overflow and extreme weather"
        case "pet-friendly": "Pet friendly"
        default: "Shelter"
        }
    }

    /// Shelters grouped by type, in the order above, open ones first within a group.
    public static func sheltersByType(_ rows: [Row]) -> [(type: String, rows: [Row])] {
        let typeOf: (Row) -> String = { $0.first(["type", "shelter_type"]) ?? "other" }
        return shelterTypes.compactMap { t in
            let r = rows.filter { typeOf($0) == t }.sorted { ($0.string("status") == "open" ? 0 : 1, $0.string("name") ?? "") < ($1.string("status") == "open" ? 0 : 1, $1.string("name") ?? "") }
            return r.isEmpty ? nil : (t, r)
        }
    }

    // MARK: - Hurricane prep

    /// Prep steps grouped by topic, in the dataset's order.
    public static func prepTopics(_ rows: [Row]) -> [(topic: String, rows: [Row])] {
        let ordered = rows.sorted { ($0.number("sort_order") ?? 0) < ($1.number("sort_order") ?? 0) }
        var seen: [String] = []
        for r in ordered { if let t = r.string("topic"), !seen.contains(t) { seen.append(t) } }
        return seen.map { t in (t, ordered.filter { $0.string("topic") == t }) }
    }

    public static func prepSymbol(_ topic: String) -> String {
        switch topic {
        case "Before the season": "calendar"
        case "Sandbags": "shield.lefthalf.filled"
        case "Generator safety": "bolt.trianglebadge.exclamationmark"
        case "When a storm is coming": "hurricane"
        case "After the storm": "hammer"
        default: "info.circle"
        }
    }

    public enum Storm: String, CaseIterable, Sendable {
        case all, michael, sally, other
        public var label: String {
            switch self { case .all: "Every storm"; case .michael: "Michael (2018)"; case .sally: "Sally (2020)"; case .other: "Other flooding" }
        }
        func includes(_ event: String?) -> Bool {
            switch self {
            case .all: true
            case .michael: event == "Hurricane Michael"
            case .sally: event == "Hurricane Sally"
            case .other: event != "Hurricane Michael" && event != "Hurricane Sally"
            }
        }
    }

    public struct ZipTotal: Identifiable, Sendable, Equatable {
        public let zip: String
        public let name: String
        public var femaAid: Double = 0
        public var households: Int = 0
        public var floodPaid: Double = 0
        public var claims: Int = 0
        public var total: Double { femaAid + floodPaid }
        public var id: String { zip }
        public var label: String { zip == "other" ? "Other" : zip }
    }

    /// FEMA housing aid and flood insurance paid per ZIP code for one storm (or all), largest first, "other" last.
    /// The same sums as the chart on /hurricane-prep.
    public static func rebuild(_ rows: [Row], storm: Storm = .all) -> [ZipTotal] {
        var byZip: [String: ZipTotal] = [:]
        for r in rows where storm.includes(r.string("event")) {
            guard let z = r.string("zip") else { continue }
            var t = byZip[z] ?? ZipTotal(zip: z, name: r.string("area_name") ?? "")
            let paid = r.number("amount_paid") ?? 0, n = Int(r.number("count") ?? 0)
            if (r.string("program") ?? "").hasPrefix("FEMA") { t.femaAid += paid; t.households += n } else { t.floodPaid += paid; t.claims += n }
            byZip[z] = t
        }
        return byZip.values.filter { $0.total > 0 }.sorted {
            if ($0.zip == "other") != ($1.zip == "other") { return $1.zip == "other" }
            return $0.total > $1.total
        }
    }

    public static func declarations(_ rows: [Row]) -> [Row] {
        rows.sorted { ($0.string("declared") ?? "") > ($1.string("declared") ?? "") }
    }

    // MARK: - Phone notifications (POST /api/push)

    public static let pushTopics: [(id: String, label: String, detail: String)] = [
        ("weather", "Weather warnings", "Hurricane, tropical storm, tornado, flood and surge warnings"),
        ("evacuation", "Evacuation orders", "When an order names a zone"),
        ("shelters", "Shelter openings", "When the county opens shelters"),
        ("water", "Boil-water notices", "For the cities you pick, or all"),
        ("roads", "Full road closures", "State roads and city closures"),
        ("agenda", "Agenda items near me", "Items on a meeting agenda near the place you save"),
    ]
    public static let defaultTopics: Set<String> = ["weather", "evacuation", "shelters", "water"]
    /// Governments whose boil-water notices and closures a phone can follow (none picked = all).
    public static let pushGovs: [(id: String, label: String)] = [
        ("county", "Unincorporated Bay County"), ("pc", "Panama City"), ("pcb", "Panama City Beach"), ("lh", "Lynn Haven"),
        ("cw", "Callaway"), ("sp", "Springfield"), ("parker", "Parker"), ("mb", "Mexico Beach"),
    ]
    public static let radiusChoices: [Double] = [0.25, 0.5, 1, 2, 5]

    /// The sign-up body. The saved place is a point only (the server rounds it to about 100 m); no address is sent.
    public static func pushBody(token: String, platform: String, topics: Set<String>, govs: [String], lat: Double?, lng: Double?,
                                radius: Double, appVersion: String?) -> Data {
        var o: [String: Any] = ["token": token, "platform": platform, "topics": topics.sorted(), "govs": govs, "radius_mi": radius, "place": "fl-bay"]
        if let lat, let lng { o["lat"] = lat; o["lng"] = lng }
        if let appVersion { o["app_version"] = appVersion }
        return (try? JSONSerialization.data(withJSONObject: o, options: [.sortedKeys])) ?? Data()
    }

    public static func hexToken(_ data: Data) -> String { data.map { String(format: "%02x", $0) }.joined() }

    // MARK: - Dates

    static func parseISO(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime]
        if let d = f.date(from: s) { return d }
        let l = DateFormatter(); l.locale = Locale(identifier: "en_US_POSIX"); l.timeZone = TimeZone(identifier: "America/Chicago")
        l.dateFormat = "yyyy-MM-dd'T'HH:mm"
        return l.date(from: String(s.prefix(16)))
    }

    /// "Oct 27, 2:05 PM" in Central time.
    public static func when(_ s: String?) -> String {
        guard let s, let d = parseISO(s) else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "MMM d, h:mm a"
        return f.string(from: d)
    }
}
