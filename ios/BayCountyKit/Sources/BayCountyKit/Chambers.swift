import Foundation

/// Chambers of commerce (/chambers), from the chambers, chamber-leaders and chamber-events datasets. The same groups,
/// order and "coming up" rule as site/chambers_page.py.
public enum Chambers {
    public static let datasets = ["chambers", "chamber-leaders", "chamber-events"]

    /// Board groups in the order the site shows them; staff last. Past chairs are listed separately.
    public static let groups = ["Executive committee", "Board", "Ex officio (non-voting)", "Honorary", "Staff"]

    public static func groupLabel(_ g: String) -> String {
        switch g {
        case "Board": "Directors"
        case "Honorary": "Honorary members"
        default: g
        }
    }

    /// Each group of one chamber's leaders that has anyone in it, in site order.
    public static func leaders(_ rows: [Row], chamber: String) -> [(group: String, rows: [Row])] {
        let mine = rows.filter { $0.string("chamber_id") == chamber }
            .sorted { ($0.number("sort_order") ?? 0) < ($1.number("sort_order") ?? 0) }
        return groups.compactMap { g in
            let r = mine.filter { $0.string("role_group") == g }
            return r.isEmpty ? nil : (g, r)
        }
    }

    /// Past chairs since 2016, newest first.
    public static func pastChairs(_ rows: [Row], chamber: String) -> [Row] {
        rows.filter { $0.string("chamber_id") == chamber && $0.string("role_group") == "Past chairs" }
            .sorted { ($0.number("year") ?? 0) > ($1.number("year") ?? 0) }
    }

    /// Board seats (everyone but staff and past chairs).
    public static func boardSeats(_ rows: [Row], chamber: String? = nil) -> Int {
        rows.filter { r in
            let g = r.string("role_group") ?? ""
            return g != "Staff" && g != "Past chairs" && (chamber == nil || r.string("chamber_id") == chamber)
        }.count
    }

    public enum Kind: String, Sendable, CaseIterable {
        case all, chamber, community
        public var label: String { switch self { case .all: "All events"; case .chamber: "Chamber events"; case .community: "Community events" } }
    }

    /// Events that haven't ended by `today` (yyyy-MM-dd, local), soonest first, optionally for one chamber and kind.
    public static func upcoming(_ rows: [Row], today: String, chamber: String? = nil, kind: Kind = .all) -> [Row] {
        rows.filter { r in
            guard r.string("kind") == "event", let s = r.string("starts") else { return false }
            let end = String((r.string("ends") ?? s).prefix(10))
            let isChamber = r.bool("chamber_event") == true
            return end >= today && (chamber == nil || r.string("chamber_id") == chamber)
                && (kind == .all || (kind == .chamber) == isChamber)
        }
        .sorted { ($0.string("starts") ?? "") < ($1.string("starts") ?? "") }
    }

    public static func programs(_ rows: [Row], chamber: String) -> [Row] {
        rows.filter { $0.string("kind") == "program" && $0.string("chamber_id") == chamber }
            .sorted { ($0.number("sort_order") ?? 0) < ($1.number("sort_order") ?? 0) }
    }

    /// The official's id when a leader is linked to an official's profile (opened natively), else nil.
    public static func personID(_ leader: Row) -> String? {
        guard let e = leader.string("person_entity_id"), e.hasPrefix("person:") else { return nil }
        return String(e.dropFirst(7))
    }

    /// The profile page on the site for a leader or their organization (`person_url` / `organization_url`).
    public static func profileURL(_ row: Row, _ key: String, site: String = "https://baycounty.me") -> URL? {
        guard let p = row.string(key), p.hasPrefix("/") else { return nil }
        return URL(string: site + p)
    }

    /// "Tue, Oct 27 · 8 a.m." style label for an event's start (all-day events show only the date).
    public static func when(_ row: Row) -> String {
        guard let s = row.string("starts"), let d = parse(s) else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        let end = row.string("ends").flatMap(parse)
        let cal = Calendar(identifier: .gregorian)
        var c = cal; c.timeZone = f.timeZone
        let allDay = row.bool("all_day") == true || (c.component(.hour, from: d) == 0 && c.component(.minute, from: d) == 0)
        if allDay {
            f.dateFormat = "MMM d"
            if let end, !c.isDate(end, inSameDayAs: d) { return "\(f.string(from: d)) to \(f.string(from: end))" }
            f.dateFormat = "EEEE, MMMM d"
            return f.string(from: d)
        }
        f.dateFormat = "EEE, MMM d"
        let day = f.string(from: d)
        f.dateFormat = c.component(.minute, from: d) == 0 ? "h a" : "h:mm a"
        let t = f.string(from: d).replacingOccurrences(of: "AM", with: "a.m.").replacingOccurrences(of: "PM", with: "p.m.")
        return "\(day) · \(t)"
    }

    static func parse(_ s: String) -> Date? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        return f.date(from: String(s.prefix(19)))
    }

    public static func date(_ row: Row) -> Date? { row.string("starts").flatMap(parse) }
}
