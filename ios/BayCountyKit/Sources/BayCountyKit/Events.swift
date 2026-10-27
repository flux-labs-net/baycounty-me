import Foundation

/// Community events (/events and the home page), from the community-events dataset. The same rules as site/events.js:
/// everything is measured against today's local date, so a stale download still starts at today.
public enum Events {
    public static let dataset = "community-events"
    public static let kinds = ["Community", "Public meeting", "Library", "Chamber"]

    /// Events that haven't ended by `today` (yyyy-MM-dd), soonest first.
    public static func upcoming(_ rows: [Row], today: String, town: String? = nil, kind: String? = nil, oneOff: Bool = false, query: String = "") -> [Row] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return rows.filter { r in
            guard let s = r.string("starts") else { return false }
            let end = String((r.string("ends") ?? s).prefix(10))
            let text = [r.string("title"), r.string("venue"), r.string("source")].compactMap { $0 }.joined(separator: " ").lowercased()
            return end >= today && (town == nil || r.string("town") == town) && (kind == nil || r.string("category") == kind)
                && (!oneOff || r.bool("recurring") != true) && (q.isEmpty || text.contains(q))
        }
        .sorted { ($0.string("starts") ?? "") < ($1.string("starts") ?? "") }
    }

    /// What's on today (started today or earlier and not over).
    public static func today(_ rows: [Row], today: String, town: String? = nil) -> [Row] {
        upcoming(rows, today: today, town: town).filter { String(($0.string("starts") ?? "").prefix(10)) <= today }
    }

    /// One-off events (not public meetings, not repeating programs) after today and within `days`: community and chamber
    /// events first, one per title, then back in date order. The home page's "Coming soon".
    public static func featured(_ rows: [Row], today: String, until: String, town: String? = nil, limit: Int = 8) -> [Row] {
        let pool = upcoming(rows, today: today, town: town).filter { r in
            let d = String((r.string("starts") ?? "").prefix(10))
            return d > today && d <= until && r.bool("recurring") != true && r.string("category") != "Public meeting"
        }
        var seen = Set<String>(), picks: [Row] = []
        for r in pool.filter({ $0.string("category") != "Library" }) + pool.filter({ $0.string("category") == "Library" }) {
            let t = r.string("title") ?? ""
            if seen.insert(t).inserted { picks.append(r) }
            if picks.count == limit { break }
        }
        return picks.sorted { ($0.string("starts") ?? "") < ($1.string("starts") ?? "") }
    }

    /// Towns with events, busiest first, the county-wide calendar last.
    public static func towns(_ rows: [Row]) -> [String] {
        var n: [String: Int] = [:]
        for r in rows { if let t = r.string("town") { n[t, default: 0] += 1 } }
        return n.keys.filter { $0 != "Bay County" }.sorted { (n[$0]!, $1) > (n[$1]!, $0) } + (n["Bay County"] != nil ? ["Bay County"] : [])
    }

    /// Upcoming events grouped by day (an event already under way counts as today).
    public static func byDay(_ rows: [Row], today: String) -> [(day: String, rows: [Row])] {
        var order: [String] = [], groups: [String: [Row]] = [:]
        for r in rows {
            let d = max(String((r.string("starts") ?? "").prefix(10)), today)
            if groups[d] == nil { order.append(d) }
            groups[d, default: []].append(r)
        }
        return order.sorted().map { ($0, groups[$0]!) }
    }

    /// "Today", "Tomorrow" or "Thursday, Oct 29".
    public static func dayLabel(_ day: String, today: String) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: day), let t = f.date(from: today) else { return day }
        let diff = Int((d.timeIntervalSince(t) / 86_400).rounded())
        if diff == 0 { return "Today" }
        if diff == 1 { return "Tomorrow" }
        f.dateFormat = "EEEE, MMM d"
        return f.string(from: d)
    }

    /// "9:30 a.m." or "All day".
    public static func time(_ row: Row) -> String {
        guard row.bool("all_day") != true, let s = row.string("starts"), s.count >= 16 else { return "All day" }
        let h = Int(s.dropFirst(11).prefix(2)) ?? 0, m = String(s.dropFirst(14).prefix(2))
        if h == 0 && m == "00" { return "All day" }
        return "\(h % 12 == 0 ? 12 : h % 12)\(m == "00" ? "" : ":" + m) \(h < 12 ? "a.m." : "p.m.")"
    }

    public static func todayKey(_ now: Date = Date()) -> String {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: now)
    }

    public static func plusDays(_ n: Int, _ now: Date = Date()) -> String { todayKey(now.addingTimeInterval(Double(n) * 86_400)) }
}
