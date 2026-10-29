import Foundation

/// The parts of /schools added in PR #191 and #194: the scores behind each grade next to the Florida average, spending
/// per student, school-day times, the grade mix against Florida, map and phone links, and the attendance zones for the
/// map. Same rules as site/schools_page.py (`_scores`, `_hours`, `_where`, `_mix`, the spending bars).
extension Schools {
    /// The school-zones dataset (attendance zone shapes) is big, so only the map loads it.
    public static let zonesDataset = "school-zones"

    /// The pieces of a Florida school grade, in the site's order: (column, label).
    public static let components: [(key: String, label: String)] = [
        ("grade3_ela_achievement", "3rd-grade reading"), ("ela_achievement", "Reading"), ("ela_gains", "Reading gains"),
        ("ela_gains_low25", "Reading, lowest 25%"), ("math_achievement", "Math"), ("math_gains", "Math gains"),
        ("math_gains_low25", "Math, lowest 25%"), ("science_achievement", "Science"), ("social_studies_achievement", "Social studies"),
        ("middle_acceleration", "Advanced courses"), ("graduation_rate", "Graduation rate"), ("college_career_acceleration", "College credit"),
    ]

    /// 2026 -> "2025-26"
    public static func yearLabel(_ y: Int) -> String { "\(y - 1)-\(String(String(y).suffix(2)))" }

    /// The newest year any school has a grade.
    public static func latestGradeYear(_ grades: [Row]) -> Int? { grades.compactMap { $0.number("year").map(Int.init) }.max() }

    /// The latest-year grades of the open schools: "A" count, everything graded, B, C, and D or F.
    public static func gradeCounts(_ schools: [Row], grades: [Row]) -> (year: Int, a: Int, graded: Int, b: Int, c: Int, df: Int)? {
        guard let y = latestGradeYear(grades) else { return nil }
        let open = Set(schools.filter { $0.string("status") == "Open" }.compactMap { $0.string("school_id") })
        let g = grades.filter { Int($0.number("year") ?? 0) == y && open.contains($0.string("school_id") ?? "") }.compactMap { $0.string("grade") }
        return (y, g.filter { $0 == "A" }.count, g.count, g.filter { $0 == "B" }.count, g.filter { $0 == "C" }.count, g.filter { $0 == "D" || $0 == "F" }.count)
    }

    public struct Score: Sendable, Hashable {
        public let label: String
        public let value: Double
        /// The Florida average for the same school type that year.
        public let state: Double?
        /// Points up or down from the school's year before, rounded.
        public let change: Int?
    }

    /// The scores behind one school's grade in the newest grade year, with the Florida average for its school type.
    public static func scores(grades: [Row], state: [Row], school: String) -> (title: String, stateLabel: String, items: [Score])? {
        guard let y = latestGradeYear(grades),
              let g = grades.first(where: { $0.string("school_id") == school && Int($0.number("year") ?? 0) == y }) else { return nil }
        let prev = grades.first { $0.string("school_id") == school && Int($0.number("year") ?? 0) == y - 1 }
        let type = g.string("school_type") ?? "All"
        let st = state.first { Int($0.number("year") ?? 0) == y && $0.string("school_type") == type }
            ?? state.first { Int($0.number("year") ?? 0) == y && $0.string("school_type") == "All" }
        let items: [Score] = components.compactMap { c in
            guard let v = g.number(c.key) else { return nil }
            let change = prev?.number(c.key).map { Int((v - $0).rounded()) }
            return Score(label: c.label, value: v, state: st?.number(c.key), change: change)
        }
        guard !items.isEmpty else { return nil }
        let pts = g.number("percent_of_points").map { ": \(Int($0.rounded()))% of possible points" } ?? ""
        let stType = st?.string("school_type").flatMap { $0 == "All" ? nil : $0.lowercased() + " school" } ?? "school"
        return ("Scores behind the \(g.string("school_year") ?? yearLabel(y)) grade\(pts)", "Florida \(stType) average", items)
    }

    /// '13:50' -> '1:50 p.m.'
    public static func time(_ hhmm: String?) -> String {
        let p = (hhmm ?? "").split(separator: ":")
        guard p.count >= 2, let h = Int(p[0]), let m = Int(p[1]) else { return "" }
        return String(format: "%d:%02d %@", (h + 11) % 12 + 1, m, h < 12 ? "a.m." : "p.m.")
    }

    /// One school's day: "7:30 a.m. to 2:00 p.m.", or one part per grade band.
    public static func hours(_ bell: [Row], school: String) -> String? {
        let rows = bell.filter { $0.string("kind") == "school day" && $0.string("school_id") == school }
        guard !rows.isEmpty else { return nil }
        let note = { (r: Row) in r.string("note").map { " (\($0))" } ?? "" }
        if rows.count == 1, rows[0].string("part") == nil {
            return "\(time(rows[0].string("start_time"))) to \(time(rows[0].string("end_time")))\(note(rows[0]))"
        }
        return rows.map { "\($0.string("part") ?? ""): \(time($0.string("start_time"))) to \(time($0.string("end_time")))\(note($0))" }.joined(separator: "; ")
    }

    /// "2026-27" for the bell times on file.
    public static func bellYear(_ bell: [Row]) -> String? { bell.lazy.compactMap { $0.string("school_year") }.first }

    /// "elementary let out at 12:30 p.m., middle let out at …" for early release days.
    public static func earlyRelease(_ bell: [Row]) -> String? {
        let rows = bell.filter { $0.string("kind") == "early release" }
        guard !rows.isEmpty else { return nil }
        return rows.map { "\(($0.string("part") ?? "").lowercased()) let out at \(time($0.string("end_time")))" }.joined(separator: ", ")
    }

    /// The newest year with spending per student.
    public static func spendingYear(_ spend: [Row]) -> Int? {
        spend.filter { $0.number("total_per_student") != nil }.compactMap { $0.number("year").map(Int.init) }.max()
    }

    /// What one school spent per student in the newest spending year.
    public static func spending(_ spend: [Row], school: String) -> (year: Int, perStudent: Double)? {
        guard let y = spendingYear(spend),
              let r = spend.first(where: { $0.string("school_id") == school && Int($0.number("year") ?? 0) == y }),
              let v = r.number("total_per_student") else { return nil }
        return (y, v)
    }

    /// Open schools by spending per student in the newest year, highest first, and the enrollment-weighted average.
    public static func spendingRanking(_ spend: [Row], schools: [Row]) -> (year: Int, rows: [(id: String, name: String, perStudent: Double)], average: Double)? {
        guard let y = spendingYear(spend) else { return nil }
        let open = Set(schools.filter { $0.string("status") == "Open" }.compactMap { $0.string("school_id") })
        let rs = spend.filter { Int($0.number("year") ?? 0) == y && $0.number("total_per_student") != nil && open.contains($0.string("school_id") ?? "") }
        let total = rs.compactMap { $0.number("estimated_total") }.reduce(0, +)
        let students = rs.filter { $0.number("estimated_total") != nil }.compactMap { $0.number("enrollment") }.reduce(0, +)
        let list = rs.map { (id: $0.string("school_id") ?? "", name: $0.string("school") ?? "", perStudent: $0.number("total_per_student")!) }
            .sorted { $0.perStudent > $1.perStudent }
        return (y, list, students > 0 ? total / students : 0)
    }

    /// Grades A to F in one year: every graded school here (closed ones too, like the site), and Florida's counts.
    public static func gradeMix(grades: [Row], state: [Row], year: Int) -> (local: [String: Int], florida: [String: Int]?) {
        var local: [String: Int] = [:]
        for g in grades where Int(g.number("year") ?? 0) == year {
            if let x = g.string("grade"), "ABCDF".contains(x), x.count == 1 { local[x, default: 0] += 1 }
        }
        let fl = state.first { Int($0.number("year") ?? 0) == year && $0.string("school_type") == "All" }
        let florida = fl.map { r in Dictionary(uniqueKeysWithValues: "ABCDF".map { (String($0), Int(r.number("grade_\(String($0).lowercased())") ?? 0)) }) }
        return (local, florida)
    }

    /// Share of A schools, 0-100.
    public static func aShare(_ mix: [String: Int]) -> Double {
        let n = mix.values.reduce(0, +)
        return n == 0 ? 0 : 100 * Double(mix["A"] ?? 0) / Double(n)
    }

    /// The school's address as a maps search (opens the Maps app).
    public static func mapsURL(_ s: Row) -> URL? {
        guard let a = s.string("address") else { return nil }
        let q = [s.string("name"), a, s.string("city"), "FL \(s.string("zip") ?? "")".trimmingCharacters(in: .whitespaces)].compactMap { $0 }.joined(separator: ", ")
        var c = URLComponents(string: "https://www.google.com/maps/search/")!
        c.queryItems = [URLQueryItem(name: "api", value: "1"), URLQueryItem(name: "query", value: q)]
        return c.url
    }

    /// "(850) 767-4400" and a tel: link, when the phone has ten digits.
    public static func phone(_ s: Row) -> (label: String, url: URL)? {
        let d = String((s.string("phone") ?? "").filter(\.isNumber).suffix(10))
        guard d.count == 10 else { return nil }
        let a = Array(d)
        return ("(\(String(a[0..<3]))) \(String(a[3..<6]))-\(String(a[6..<10]))", URL(string: "tel:+1\(d)")!)
    }

    /// One attendance zone's outline rings as (latitude, longitude) pairs, from the GeoJSON in school-zones.
    public struct Zone: Sendable, Identifiable {
        public let id: String
        public let level: String
        public let school: String
        public let rings: [[(lat: Double, lon: Double)]]
    }

    public static func zones(_ rows: [Row], level: String) -> [Zone] {
        rows.filter { $0.string("level") == level }.compactMap { r in
            guard let g = r.string("geometry"), let data = g.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let type = obj["type"] as? String, let coords = obj["coordinates"] as? [Any] else { return nil }
            let polys: [[Any]] = type == "MultiPolygon" ? coords.compactMap { $0 as? [Any] } : [coords]
            let rings: [[(lat: Double, lon: Double)]] = polys.compactMap { $0.first as? [[Double]] }
                .map { $0.compactMap { p in p.count >= 2 ? (lat: p[1], lon: p[0]) : nil } }
            return rings.isEmpty ? nil : Zone(id: r.string("zone_id") ?? "\(r.id)", level: level, school: r.string("school") ?? r.string("zone_name") ?? "", rings: rings)
        }
    }
}
