import Foundation

/// The app's Home tab ("My home dashboard"): a line about the home, an alert strip when notices are active, and tiles
/// that each give one answer. Owners lead with their tax bill, renters with their utilities, and a resident who hasn't
/// said leads with setting up their home. Tapping a tile opens one short screen. Mirrored in android/kit HomeTiles.kt.
public enum HomeTiles {
    /// Own or rent, asked once at setup and changeable in My home. `unset` is "visiting or rather not say".
    public enum Tenure: String, CaseIterable, Sendable {
        case own, rent, unset

        public var label: String {
            switch self {
            case .own: "I own it"
            case .rent: "I rent"
            case .unset: "Visiting or rather not say"
            }
        }

        public var detail: String {
            switch self {
            case .own: "Your tax bill, homestead and exemptions up front"
            case .rent: "Utilities, services and where public money goes up front"
            case .unset: "A county-wide view"
            }
        }
    }

    public enum Target: Hashable, Sendable { case setup, taxBill, utilities, beaches, meetings, election, representatives, schools }

    public struct Tile: Hashable, Sendable, Identifiable {
        public let id: String
        public let symbol: String
        /// blue, teal, amber or salmon, like the site's icon tones.
        public let tone: String
        public let eyebrow: String
        public let value: String
        public let detail: String
        public let target: Target
        /// The first tile, drawn on navy.
        public let featured: Bool
    }

    public struct Alert: Hashable, Sendable {
        public let title: String
        public let detail: String
    }

    /// The home value the tax tile estimates for until the resident enters their own, like the site's calculator.
    public static let sampleValue = 250_000.0

    /// The tiles, in order: the lead tile, trash (only on pickup day or the evening before), beach, election day
    /// (in the 45 days before it), next meeting, who represents you, schools. With an odd count the app lets the lead
    /// tile span the row.
    public static func tiles(tenure: Tenure, hasHome: Bool, utilities: UtilityLookup?, taxTotal: Double?, beach: [Row],
                             meetings: [Meeting], electionDay: String?, now: Date = Date()) -> [Tile] {
        var out = [lead(tenure: tenure, utilities: utilities, taxTotal: taxTotal)]
        if let t = trash(utilities, now: now) { out.append(t) }
        out.append(beachTile(beach))
        if let e = election(electionDay, now: now) { out.append(e) }
        out.append(meeting(meetings, now: now))
        out.append(Tile(id: "reps", symbol: "person.2", tone: "blue", eyebrow: "Who represents you",
                        value: hasHome ? "Your officials" : "Officials", detail: "City, county and school board",
                        target: .representatives, featured: false))
        out.append(Tile(id: "schools", symbol: "graduationcap", tone: "blue", eyebrow: "Schools",
                        value: hasHome ? "Your zoned schools" : "Public schools", detail: "Grades, calendar and buses",
                        target: .schools, featured: false))
        return out
    }

    static func lead(tenure: Tenure, utilities: UtilityLookup?, taxTotal: Double?) -> Tile {
        switch tenure {
        case .own:
            return Tile(id: "tax", symbol: "dollarsign.circle", tone: "blue", eyebrow: "Your tax bill",
                        value: taxTotal.map { Format.money($0) } ?? "Estimate", detail: "a year · \(Format.compactMoney(sampleValue)) home, homestead",
                        target: .taxBill, featured: true)
        case .rent:
            let n = utilities?.services.count ?? 0
            return Tile(id: "utilities", symbol: "bolt", tone: "teal", eyebrow: "Your utilities", value: "Water, power, trash",
                        detail: n > 0 ? "Who provides each of \(n) services" : "Who to call to set up or report",
                        target: .utilities, featured: true)
        case .unset:
            return Tile(id: "setup", symbol: "house", tone: "blue", eyebrow: "Make it yours", value: "Set up your home",
                        detail: "Own or rent? Get answers for your address", target: .setup, featured: true)
        }
    }

    /// The trash tile from the Today trash card's rules: only on pickup day, or from 4 p.m. the day before.
    static func trash(_ lookup: UtilityLookup?, now: Date) -> Tile? {
        guard let c = TodayBrief.trashCard(lookup, now: now) else { return nil }
        let word = c.title.hasSuffix("today") ? "Today" : "Tomorrow"
        let none = c.title.hasPrefix("No ")
        return Tile(id: "trash", symbol: "trash", tone: "teal", eyebrow: "Trash day", value: none ? "No pickup" : word,
                    detail: none ? "\(word) · \(c.detail)" : c.detail, target: .utilities, featured: false)
    }

    static func beachTile(_ rows: [Row]) -> Tile {
        let f = Outdoors.forecast(rows).first
        return Tile(id: "beach", symbol: "flag", tone: "amber", eyebrow: "Beach",
                    value: f?.string("flag_color").map { "\($0) flag" } ?? "Beach flags",
                    detail: f?.string("rip_current_risk").map { "\($0) rip current risk" } ?? "Today's flag at each beach",
                    target: .beaches, featured: false)
    }

    /// Election day, in the 45 days before it (and on the day).
    static func election(_ day: String?, now: Date) -> Tile? {
        guard let day, let d = parseDay(day) else { return nil }
        let today = central.startOfDay(for: now)
        guard let days = central.dateComponents([.day], from: today, to: d).day, days >= 0, days <= 45 else { return nil }
        return Tile(id: "election", symbol: "checkmark.seal", tone: "salmon", eyebrow: "Election day",
                    value: days == 0 ? "Today" : format(d, "EEE, MMM d"), detail: "Your ballot and where to vote",
                    target: .election, featured: false)
    }

    static func meeting(_ meetings: [Meeting], now: Date) -> Tile {
        guard let m = Meeting.upcoming(meetings, now: now).first, let s = m.start else {
            return Tile(id: "meeting", symbol: "calendar", tone: "blue", eyebrow: "Meetings", value: "Public meetings",
                        detail: "When every board meets, with agendas", target: .meetings, featured: false)
        }
        return Tile(id: "meeting", symbol: "calendar", tone: "blue", eyebrow: "Next meeting", value: format(s, "EEE, MMM d"),
                    detail: m.boardName, target: .meetings, featured: false)
    }

    /// The strip above the tiles when notices are active: the most urgent kind first (evacuation, weather, boil water,
    /// road, utility), with the count of that kind.
    public static func alert(_ notices: [Row]) -> Alert? {
        let active = notices.filter { $0.string("status") == "active" }
        guard !active.isEmpty else { return nil }
        let order = ["evacuation", "weather", "boil-water", "road", "utility"]
        let kind = order.first { k in active.contains { $0.string("kind") == k } }
        let n = kind.map { k in active.filter { $0.string("kind") == k }.count } ?? active.count
        let words = ["evacuation": "evacuation", "weather": "weather", "boil-water": "boil-water", "road": "road", "utility": "utility"]
        let title = "\(n) \(kind.flatMap { words[$0] }.map { $0 + " " } ?? "")notice\(n == 1 ? "" : "s") in effect"
        let others = active.count - n
        // "the map" only when one of them has a map to show.
        let next = active.contains { AlertArea.parse($0.string("geometry")) != nil } ? "See the map and what to do." : "See what to do."
        return Alert(title: title, detail: others > 0 ? "\(others) more active. \(next)" : next)
    }

    /// "YOUR HOME · PANAMA CITY · RENTING" with a saved home, else "BAY COUNTY". The app shows it in capitals.
    public static func eyebrow(place: String?, tenure: Tenure) -> String {
        guard let place else { return "Bay County" }
        return "Your home · \(place)" + (tenure == .rent ? " · Renting" : "")
    }

    /// The tax district for the saved home: its city when the utilities lookup names one, the county's unincorporated
    /// district outside the cities, else the one picked in the tax calculator, else the first.
    public static func taxDistrict(model: TaxModel, utilities: UtilityLookup?, saved: String) -> TaxModel.District? {
        if let u = utilities {
            let id = u.area == "county" ? "unincorporated" : u.areaName
            if let d = model.districts.first(where: { $0.id == id }) { return d }
        }
        return model.districts.first { $0.id == saved } ?? model.districts.first
    }

    private static let central: Calendar = {
        var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!; return c
    }()

    private static func parseDay(_ s: String) -> Date? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = central.timeZone; f.dateFormat = "yyyy-MM-dd"
        return f.date(from: String(s.prefix(10)))
    }

    private static func format(_ d: Date, _ pattern: String) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = central.timeZone; f.dateFormat = pattern
        return f.string(from: d)
    }
}
