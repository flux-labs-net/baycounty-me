import Foundation

/// The top of the app's Today tab: a greeting, four "right now" cards (beach flag, active notices, next meeting,
/// trash day) and this weekend's events. The cards use the same rules and wording as the site's home page
/// (site/home.py `_today`). Mirrored in android/kit TodayBrief.kt.
public enum TodayBrief {
    public enum Target: Hashable, Sendable { case beaches, emergency, meetings, utilities }

    public struct Card: Hashable, Sendable, Identifiable {
        public let id: String
        public let symbol: String
        /// blue, teal, amber or salmon, like the site's icon tones.
        public let tone: String
        public let title: String
        public let detail: String
        public let target: Target
    }

    /// "Good morning" before noon, "Good afternoon" until 5 p.m., then "Good evening".
    public static func greeting(hour: Int) -> String {
        hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
    }

    /// The hour in Bay County (Central time).
    public static func hour(_ now: Date = Date()) -> Int {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "America/Chicago")!
        return c.component(.hour, from: now)
    }

    /// "Wednesday, Oct 28" for a yyyy-MM-dd day.
    public static func dateLine(_ day: String) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: day) else { return day }
        f.dateFormat = "EEEE, MMM d"
        return f.string(from: d)
    }

    /// The four cards. `beach` is the beach-conditions dataset, `notices` emergency-notices, `trashDays` the garbage
    /// pickup days at the saved home when they were looked up.
    public static func cards(beach: [Row], notices: [Row], meetings: [Meeting], trashDays: String?, now: Date = Date()) -> [Card] {
        [beachCard(beach), noticesCard(notices), meetingCard(meetings, now: now), trashCard(trashDays)]
    }

    static func beachCard(_ rows: [Row]) -> Card {
        let now = Outdoors.forecast(rows).first
        let flag = now?.string("flag_color")
        let risk = now?.string("rip_current_risk")
        return Card(id: "beach", symbol: "flag", tone: "amber",
                    title: flag.map { "\($0) beach flag" } ?? "Beach flags",
                    detail: risk.map { "\($0) rip current risk" } ?? "Today's flag at each beach", target: .beaches)
    }

    static func noticesCard(_ rows: [Row]) -> Card {
        let active = rows.filter { $0.string("status") == "active" }
        guard !active.isEmpty else {
            return Card(id: "notices", symbol: "exclamationmark.triangle", tone: "salmon", title: "No active alerts",
                        detail: "Weather, boil-water and road notices", target: .emergency)
        }
        let known: Set<String> = ["weather", "boil-water", "evacuation", "road", "utility"]
        var counts: [String: Int] = [:], order: [String] = []
        for n in active {
            let k = known.contains(n.string("kind") ?? "") ? n.string("kind")! : "other"
            if counts[k] == nil { order.append(k) }
            counts[k, default: 0] += 1
        }
        // Most first; ties keep the order they first appeared in, like Python's stable sort on the site.
        let parts = order.enumerated().sorted { a, b in
            counts[a.element]! != counts[b.element]! ? counts[a.element]! > counts[b.element]! : a.offset < b.offset
        }.map { "\(counts[$0.element]!) \($0.element)" }
        return Card(id: "notices", symbol: "exclamationmark.triangle", tone: "salmon",
                    title: "\(active.count) active notice\(active.count == 1 ? "" : "s")", detail: parts.joined(separator: ", "), target: .emergency)
    }

    static func meetingCard(_ meetings: [Meeting], now: Date) -> Card {
        guard let m = Meeting.upcoming(meetings, now: now).first, let s = m.start else {
            return Card(id: "meeting", symbol: "calendar", tone: "blue", title: "Meetings",
                        detail: "When every board meets, with agendas", target: .meetings)
        }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "EEE MMM d"
        return Card(id: "meeting", symbol: "calendar", tone: "blue", title: "Next meeting · \(f.string(from: s))",
                    detail: m.boardName, target: .meetings)
    }

    static func trashCard(_ days: String?) -> Card {
        if let d = days, !d.isEmpty {
            return Card(id: "trash", symbol: "trash", tone: "teal", title: "Trash day: \(d)", detail: "At your home", target: .utilities)
        }
        return Card(id: "trash", symbol: "trash", tone: "teal", title: "Trash day",
                    detail: "Your pickup day and who provides water and power", target: .utilities)
    }

    /// Garbage pickup days from a utilities lookup ("Friday"), or nil.
    public static func trashDays(_ lookup: UtilityLookup?) -> String? {
        lookup?.pickup.first { $0.service == "garbage" }?.days
    }

    /// The weekend the Today tab shows: today through Sunday on Friday, Saturday and Sunday, else the coming
    /// Friday through Sunday. Both yyyy-MM-dd.
    public static func weekend(today: String) -> (from: String, to: String)? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd"
        guard let t = f.date(from: today) else { return nil }
        var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "UTC")!
        let wd = c.component(.weekday, from: t)   // 1 = Sunday ... 7 = Saturday
        let toSunday = (8 - wd) % 7
        let sunday = c.date(byAdding: .day, value: toSunday, to: t)!
        let from = (wd == 6 || wd == 7 || wd == 1) ? t : c.date(byAdding: .day, value: -2, to: sunday)!
        return (f.string(from: from), f.string(from: sunday))
    }

    /// One-off events this weekend (not public meetings or repeating programs), community and chamber events first,
    /// one per title, then in date order.
    public static func weekendEvents(_ rows: [Row], today: String, limit: Int = 4) -> [Row] {
        guard let w = weekend(today: today) else { return [] }
        let pool = Events.upcoming(rows, today: today).filter { r in
            let d = max(String((r.string("starts") ?? "").prefix(10)), today)
            return d >= w.from && d <= w.to && r.bool("recurring") != true && r.string("category") != "Public meeting"
        }
        var seen = Set<String>(), picks: [Row] = []
        for r in pool.filter({ $0.string("category") != "Library" }) + pool.filter({ $0.string("category") == "Library" }) {
            if seen.insert(r.string("title") ?? "").inserted { picks.append(r) }
            if picks.count == limit { break }
        }
        return picks.sorted { ($0.string("starts") ?? "") < ($1.string("starts") ?? "") }
    }
}
