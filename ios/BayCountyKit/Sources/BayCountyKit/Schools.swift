import Foundation

/// Public schools (/schools), from the schools, school-calendar and school-enrollment datasets (plus school-grades and
/// school-spending once the state's files are in). The same order, filters and "coming up" rule as site/schools_page.py.
public enum Schools {
    public static let datasets = ["schools", "school-calendar", "school-enrollment", "school-grades", "school-spending"]
    public static let levelOrder = ["Elementary", "Middle", "High", "Combined", "Other"]

    public enum Filter: String, Sendable, CaseIterable {
        case all, elementary, middle, high, combined, charter
        public var label: String {
            switch self {
            case .all: "All"; case .elementary: "Elementary"; case .middle: "Middle"; case .high: "High"
            case .combined: "K-8 and K-12"; case .charter: "Charter"
            }
        }
    }

    /// Open schools, by level then name, optionally filtered and searched (name or city).
    public static func open(_ rows: [Row], filter: Filter = .all, query: String = "") -> [Row] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return rows.filter { r in
            guard r.string("status") == "Open" else { return false }
            let level = r.string("level") ?? ""
            let ok: Bool = switch filter {
            case .all: true
            case .charter: r.bool("charter") == true
            case .combined: level == "Combined"
            default: level == filter.label
            }
            let hay = "\(r.string("name") ?? "") \(r.string("city") ?? "")".lowercased()
            return ok && (q.isEmpty || hay.contains(q))
        }
        .sorted { a, b in
            let la = levelOrder.firstIndex(of: a.string("level") ?? "") ?? 9, lb = levelOrder.firstIndex(of: b.string("level") ?? "") ?? 9
            return la != lb ? la < lb : (a.string("name") ?? "") < (b.string("name") ?? "")
        }
    }

    /// Schools that have closed since 2016, most recently closed first.
    public static func closed(_ rows: [Row]) -> [Row] {
        rows.filter { $0.string("status") == "Closed" }
            .sorted { ($0.string("last_year_open") ?? "", $1.string("name") ?? "") > ($1.string("last_year_open") ?? "", $0.string("name") ?? "") }
    }

    /// "Elementary · grades PK-5 · Lynn Haven · Charter"
    public static func subtitle(_ s: Row) -> String {
        [s.string("level"), s.string("grades").map { "grades \($0)" }, s.string("city"), s.bool("charter") == true ? "Charter" : nil]
            .compactMap { $0 }.joined(separator: " · ")
    }

    // MARK: Calendar

    public enum Kind: String, Sendable, CaseIterable {
        case all, off, milestones, board
        public var label: String {
            switch self { case .all: "Everything"; case .off: "Days off"; case .milestones: "Grading and graduation"; case .board: "School Board" }
        }
        func matches(_ kind: String) -> Bool {
            switch self {
            case .all: true
            case .off: kind == "no-school" || kind == "break"
            case .milestones: ["grading", "graduation", "first-day", "last-day", "early-release"].contains(kind)
            case .board: kind == "board-meeting"
            }
        }
    }

    public static let kindLabels = ["no-school": "No school", "break": "Break", "board-meeting": "School Board", "early-release": "Early release",
                                    "grading": "Grading period", "graduation": "Graduation", "first-day": "First day", "last-day": "Last day"]
    public static func kindLabel(_ k: String?) -> String { kindLabels[k ?? ""] ?? "District event" }

    /// Calendar entries that haven't ended by `today` (yyyy-MM-dd, local), soonest first.
    public static func upcoming(_ rows: [Row], today: String, kind: Kind = .all) -> [Row] {
        rows.filter { r in
            guard let s = r.string("starts") else { return false }
            return String((r.string("ends") ?? s).prefix(10)) >= today && kind.matches(r.string("kind") ?? "")
        }
        .sorted { ($0.string("starts") ?? "") < ($1.string("starts") ?? "") }
    }

    /// The next day off (no school or a break) that starts on or after `today`.
    public static func nextDayOff(_ rows: [Row], today: String) -> Row? {
        upcoming(rows, today: today, kind: .off).first { String(($0.string("starts") ?? "").prefix(10)) >= today }
    }

    static let tz = TimeZone(identifier: "America/Chicago")!

    static func parse(_ s: String) -> Date? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = tz
        for (p, n) in [("yyyy-MM-dd'T'HH:mm:ss", 19), ("yyyy-MM-dd'T'HH:mm", 16), ("yyyy-MM-dd", 10)] where s.count >= n {
            f.dateFormat = p
            if let d = f.date(from: String(s.prefix(n))) { return d }
        }
        return nil
    }

    public static func date(_ row: Row) -> Date? { row.string("starts").flatMap(parse) }

    /// "Tue, Oct 27 · 3 p.m.", "Wednesday, October 28" or "Nov 23 to Nov 27".
    public static func when(_ row: Row) -> String {
        guard let s = row.string("starts"), let d = parse(s) else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = tz
        var c = Calendar(identifier: .gregorian); c.timeZone = tz
        let end = row.string("ends").flatMap(parse)
        if row.bool("all_day") == true || !s.contains("T") {
            f.dateFormat = "EEE, MMM d"
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

    // MARK: Enrollment, grades, spending

    /// Every public school's fall enrollment added up, by school year ("2015-16"), oldest first.
    public static func districtEnrollment(_ rows: [Row]) -> [(year: String, students: Double)] {
        var t: [String: Double] = [:]
        for r in rows { if let y = r.string("school_year") { t[y, default: 0] += r.number("enrollment") ?? 0 } }
        return t.keys.sorted().map { ($0, t[$0]!) }
    }

    /// One school's enrollment by school year, oldest first.
    public static func enrollment(_ rows: [Row], school: String) -> [(year: String, students: Double)] {
        rows.filter { $0.string("school_id") == school }
            .compactMap { r in r.string("school_year").map { ($0, r.number("enrollment") ?? 0) } }
            .sorted { $0.year < $1.year }
    }

    /// One school's grades, newest first.
    public static func grades(_ rows: [Row], school: String) -> [Row] {
        rows.filter { $0.string("school_id") == school }.sorted { ($0.number("year") ?? 0) > ($1.number("year") ?? 0) }
    }

    /// The site's anchor for a school on /schools.
    public static func pageURL(_ s: Row, site: String = "https://baycounty.me") -> URL? {
        URL(string: site + (s.string("page_url") ?? "/schools/"))
    }
}
