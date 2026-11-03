import Foundation

/// The top of the app's Today tab: a greeting, the "right now" cards (trash pickup only around pickup day, beach
/// flag, active notices, next meeting) and this weekend's events. The cards use the same rules and wording as the site's home page
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

    /// The "right now" cards. `beach` is the beach-conditions dataset, `notices` emergency-notices, `utilities` the
    /// saved home's utilities lookup. The trash card leads, and only on pickup day (or the evening before).
    public static func cards(beach: [Row], notices: [Row], meetings: [Meeting], utilities: UtilityLookup?, now: Date = Date()) -> [Card] {
        [trashCard(utilities, now: now), beachCard(beach), noticesCard(notices), meetingCard(meetings, now: now)].compactMap { $0 }
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

    /// The trash card for the saved home, or nil: shown on garbage pickup day, and from 4 p.m. the day before
    /// ("put it out tonight"). A holiday with no pickup says so instead. Same rules as the site's home.js `BCTrashCard`.
    public static func trashCard(_ lookup: UtilityLookup?, now: Date = Date()) -> Card? {
        guard let l = lookup else { return nil }
        return trashCard(days: trashDays(l), holidays: l.holidays, now: now)
    }

    static func trashCard(days: String?, holidays: [UtilityLookup.Holiday], now: Date) -> Card? {
        guard let days, !days.isEmpty else { return nil }
        var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!
        let today = c.startOfDay(for: now), tomorrow = c.date(byAdding: .day, value: 1, to: today)!
        func runs(_ d: Date) -> Bool { days.range(of: "\\b\(weekdays[c.component(.weekday, from: d) - 1])\\b", options: [.regularExpression, .caseInsensitive]) != nil }
        func card(_ d: Date, _ word: String, _ detail: String) -> Card {
            guard let h = holidays.first(where: { ($0.garbage ?? "").range(of: "^(no pickup|moved)", options: [.regularExpression, .caseInsensitive]) != nil
                                                  && isOn($0.whenObserved, d, c) }) else {
                return Card(id: "trash", symbol: "trash", tone: "teal", title: "Trash pickup \(word)", detail: detail, target: .utilities)
            }
            // "No pickup; in 2025 Thursday's route moved to Saturday, December 27": a note about another year is left off.
            var rest = (h.garbage ?? "").replacingOccurrences(of: "^no pickup[;,.]?\\s*", with: "", options: [.regularExpression, .caseInsensitive])
            let year = String(c.component(.year, from: d))
            if let years = try? NSRegularExpression(pattern: "\\b20\\d\\d\\b"),
               years.matches(in: rest, range: NSRange(rest.startIndex..., in: rest)).contains(where: { (rest as NSString).substring(with: $0.range) != year }) { rest = "" }
            return Card(id: "trash", symbol: "trash", tone: "teal", title: "No trash pickup \(word)",
                        detail: rest.isEmpty ? h.holiday : "\(h.holiday) · \(rest.prefix(1).uppercased())\(rest.dropFirst())", target: .utilities)
        }
        if runs(today) { return card(today, "today", "At your home") }
        if c.component(.hour, from: now) >= 16, runs(tomorrow) { return card(tomorrow, "tomorrow", "Put it out tonight") }
        return nil
    }

    private static let weekdays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    private static let months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    /// Whether a holiday's "when" falls on the day: "January 1", "4th Thursday in November", "Last Monday in May".
    static func isOn(_ when: String?, _ d: Date, _ c: Calendar) -> Bool {
        let parts = (when ?? "").split(separator: " ").map(String.init)
        let month = c.component(.month, from: d) - 1, day = c.component(.day, from: d), wd = c.component(.weekday, from: d) - 1
        if parts.count == 2, let n = Int(parts[1]) { return months.firstIndex(of: parts[0]) == month && n == day }
        guard parts.count == 4, parts[2].lowercased() == "in", months.firstIndex(of: parts[3]) == month, weekdays.firstIndex(of: parts[1]) == wd else { return false }
        if parts[0].lowercased() == "last" { return day + 7 > c.range(of: .day, in: .month, for: d)!.count }
        guard let n = Int(parts[0].prefix { $0.isNumber }) else { return false }
        return (day + 6) / 7 == n
    }

    /// Garbage pickup days from a utilities lookup ("Friday"), or nil.
    public static func trashDays(_ lookup: UtilityLookup?) -> String? {
        lookup?.pickup.first { $0.service == "garbage" && !($0.days ?? "").isEmpty }?.days
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
