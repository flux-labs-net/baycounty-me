import Foundation

/// Police, fire and the Sheriff (/public-safety), from the safety-agencies, crime-counts and police-staffing datasets.
/// The same numbers and rules as site/safety_page.py and site/safety_charts.py: who covers each town, what each
/// department costs per resident, the crimes each police agency reported to the FBI (full years only in the charts),
/// the share solved, and officers. Counts only: no incident names a person.
public enum PublicSafety {
    public static let datasets = ["safety-agencies", "crime-counts", "police-staffing"]
    /// Florida agencies switched from yearly summaries to monthly incident reports (NIBRS) in 2025.
    public static let newSystem = 2025

    public enum Offense: String, CaseIterable, Sendable {
        case violent = "V", property = "P"
        public var label: String { self == .violent ? "Violent crime" : "Property crime" }
        public var noun: String { self == .violent ? "violent" : "property" }
    }

    /// One government's police and fire rows.
    public struct Town: Identifiable, Sendable {
        public let id: String
        public let name: String
        public let police: Row?
        public let fire: Row?
    }

    /// Governments in the dataset's order, each with its police and fire department.
    public static func towns(_ agencies: [Row]) -> [Town] {
        var order: [String] = []
        var by: [String: [String: Row]] = [:]
        for r in agencies {
            guard let g = r.string("gov_id"), let s = r.string("service") else { continue }
            if by[g] == nil { order.append(g); by[g] = [:] }
            by[g]![s] = r
        }
        return order.map { g in
            let p = by[g]?["police"], f = by[g]?["fire"]
            return Town(id: g, name: (p ?? f)?.string("government") ?? g, police: p, fire: f)
        }
    }

    public static func fiscalYear(_ agencies: [Row]) -> String { agencies.lazy.compactMap { $0.string("budget_fiscal_year") }.first ?? "FY2026" }

    /// Police and fire budgets, what cities pay the Sheriff by contract, fire departments, and sworn officers.
    public static func totals(_ agencies: [Row]) -> (police: Double, fire: Double, contracts: Double, fireDepartments: Int, officers: Int) {
        let pol = agencies.filter { $0.string("service") == "police" }, fire = agencies.filter { $0.string("service") == "fire" }
        let contracts = pol.filter { $0.string("agency_gov_id") != $0.string("gov_id") && $0.string("gov_id") != "county" }
        return (pol.compactMap { $0.number("budget_amount") }.reduce(0, +), fire.compactMap { $0.number("budget_amount") }.reduce(0, +),
                contracts.compactMap { $0.number("budget_amount") }.reduce(0, +), fire.count, Int(pol.compactMap { $0.number("officers") }.reduce(0, +)))
    }

    /// Reporting agencies in the order they appear.
    public static func agencies(_ crimes: [Row]) -> [(id: String, name: String)] {
        var seen = Set<String>(), out: [(String, String)] = []
        for r in crimes { if let a = r.string("agency_id"), seen.insert(a).inserted { out.append((a, r.string("agency") ?? a)) } }
        return out
    }

    /// Years where some agency reported fewer than 12 months ("so far").
    static func partialYears(_ crimes: [Row]) -> Set<Int> {
        Set(crimes.filter { ($0.number("months_reported") ?? 12) < 12 }.compactMap { $0.number("year").map(Int.init) })
    }

    /// Violent and property crimes in the latest full year before 2025, and the change since the first full year
    /// (same agencies).
    public static func headline(_ crimes: [Row]) -> (year: Int, firstYear: Int, violent: Int, property: Int, violentChange: Int?)? {
        let years = Set(crimes.compactMap { $0.number("year").map(Int.init) }).sorted()
        guard !years.isEmpty else { return nil }
        let partial = partialYears(crimes)
        let full = years.filter { !partial.contains($0) && $0 < 2025 }
        let ky = full.last ?? years.last!, first = full.first ?? years.first!
        func cell(_ a: String, _ y: Int, _ c: String) -> Row? {
            crimes.first { $0.string("agency_id") == a && Int($0.number("year") ?? 0) == y && $0.string("offense_code") == c }
        }
        let ids = agencies(crimes).map(\.id)
        let v = ids.compactMap { cell($0, ky, "V")?.number("count") }.reduce(0, +)
        let p = ids.compactMap { cell($0, ky, "P")?.number("count") }.reduce(0, +)
        let vFirst = ids.filter { cell($0, ky, "V") != nil }.compactMap { cell($0, first, "V")?.number("count") }.reduce(0, +)
        return (ky, first, Int(v), Int(p), vFirst > 0 ? Int(((v - vFirst) / vFirst * 100).rounded()) : nil)
    }

    /// Full reported years of one offense for one agency: year -> row.
    public static func fullYears(_ crimes: [Row], agency: String, offense: Offense) -> [Int: Row] {
        var out: [Int: Row] = [:]
        for r in crimes where r.string("agency_id") == agency && r.string("offense_code") == offense.rawValue
            && r.number("count") != nil && r.number("months_reported") == 12 && r.number("per_1000") != nil {
            if let y = r.number("year") { out[Int(y)] = r }
        }
        return out
    }

    /// One point of a crime-rate line: the agency's rate per 1,000 people and Florida's.
    public struct RatePoint: Identifiable, Sendable {
        public var id: Int { year }
        public let year: Int
        public let rate: Double
        public let florida: Double?
        public let count: Int
    }

    /// Small multiples: each agency with a full year of this offense, its rate per 1,000 people by year.
    public static func trends(_ crimes: [Row], offense: Offense) -> [(id: String, name: String, points: [RatePoint])] {
        agencies(crimes).compactMap { a in
            let fy = fullYears(crimes, agency: a.id, offense: offense)
            guard !fy.isEmpty else { return nil }
            let pts = fy.keys.sorted().map { y in
                let r = fy[y]!
                return RatePoint(year: y, rate: r.number("per_1000") ?? 0, florida: r.number("florida_per_1000"), count: Int(r.number("count") ?? 0))
            }
            return (a.id, shortName(a.name), pts)
        }
        // Mexico Beach's old department last, like the site
        .sorted { ($0.id == "mb-police" ? 1 : 0) < ($1.id == "mb-police" ? 1 : 0) }
    }

    /// The highest rate in any panel (agency or Florida), so every panel shares one scale.
    public static func trendMax(_ t: [(id: String, name: String, points: [RatePoint])]) -> Double {
        t.flatMap { $0.points.flatMap { [$0.rate, $0.florida ?? 0] } }.max() ?? 1
    }

    /// Share cleared over each agency's latest three full yearly reports (before 2025), highest first; agencies with
    /// fewer than 20 crimes in those years are left out.
    public static func solved(_ crimes: [Row], offense: Offense) -> [(name: String, share: Double, cleared: Int, count: Int, span: String)] {
        agencies(crimes).compactMap { a in
            let fy = fullYears(crimes, agency: a.id, offense: offense)
            let ys = Array(fy.keys.filter { $0 < newSystem }.sorted().suffix(3))
            let n = ys.compactMap { fy[$0]?.number("count") }.reduce(0, +)
            let c = ys.compactMap { fy[$0]?.number("cleared") }.reduce(0, +)
            guard n >= 20, let f = ys.first, let l = ys.last else { return nil }
            return (shortName(a.name), c / n, Int(c), Int(n), f == l ? "\(f)" : "\(f)–\(l)")
        }
        .sorted { $0.share > $1.share }
    }

    /// Police and fire budget per resident for each government that has one.
    public static func perResident(_ agencies: [Row]) -> [(name: String, police: Double?, fire: Double?)] {
        towns(agencies).compactMap { t in
            let p = t.police?.number("cost_per_resident"), f = t.fire?.number("cost_per_resident")
            return p == nil && f == nil ? nil : (t.name, p, f)
        }
    }

    /// What a town card says about crime: whose numbers cover it, the latest full year, and the rates against Florida.
    public struct TownCrime: Sendable {
        public let agencyName: String
        public let year: Int?
        public let violent: Row?
        public let property: Row?
        /// The Sheriff's numbers stand in for a town it polices.
        public let sheriffCovers: Bool
    }

    public static func townCrime(_ town: Town, crimes: [Row]) -> TownCrime {
        let pol = town.police
        let own = pol.flatMap { p in p.string("fbi_ori") != nil && p.string("agency_gov_id") == p.string("gov_id") ? p.string("agency_id") : nil }
        let aid = own ?? "bcso"
        let name = own != nil ? (pol?.string("agency") ?? "") : "the Sheriff's Office"
        let v = fullYears(crimes, agency: aid, offense: .violent), p = fullYears(crimes, agency: aid, offense: .property)
        var ly = v.keys.max()
        if ly == newSystem, v[newSystem - 1] != nil { ly = newSystem - 1 }  // the switch year dips; show the last yearly summary
        return TownCrime(agencyName: name, year: ly, violent: ly.flatMap { v[$0] }, property: ly.flatMap { p[$0] }, sheriffCovers: aid == "bcso" && town.id != "county")
    }

    /// "about the same as Florida", "1.4 times Florida's rate" or "30% below Florida's rate".
    public static func versusFlorida(_ r: Row) -> String? {
        guard let rate = r.number("per_1000"), let fl = r.number("florida_per_1000"), fl > 0 else { return nil }
        let ratio = rate / fl
        if ratio >= 0.9 && ratio <= 1.1 { return "about the same as Florida" }
        if ratio > 1.1 { return String(format: "%.1f times Florida's rate", ratio) }
        return "\(Int((100 * (1 - ratio)).rounded()))% below Florida's rate"
    }

    /// The latest staffing row for an agency.
    public static func staffing(_ staff: [Row], agency: String) -> Row? {
        staff.filter { $0.string("agency_id") == agency }.max { ($0.number("year") ?? 0) < ($1.number("year") ?? 0) }
    }

    /// Each agency's latest officers and civilian staff, and the first year on file for comparison.
    public static func staffingSummary(_ staff: [Row]) -> [(id: String, name: String, year: Int, officers: Int, civilians: Int, firstYear: Int, firstOfficers: Int)] {
        var seen = Set<String>(), out: [(String, String, Int, Int, Int, Int, Int)] = []
        for r in staff {
            guard let a = r.string("agency_id"), seen.insert(a).inserted else { continue }
            let rows = staff.filter { $0.string("agency_id") == a }.sorted { ($0.number("year") ?? 0) < ($1.number("year") ?? 0) }
            guard let f = rows.first, let l = rows.last else { continue }
            out.append((a, r.string("agency") ?? a, Int(l.number("year") ?? 0), Int(l.number("officers") ?? 0), Int(l.number("civilians") ?? 0),
                        Int(f.number("year") ?? 0), Int(f.number("officers") ?? 0)))
        }
        return out
    }

    /// 'Panama City Police Department' -> 'Panama City police'.
    public static func shortName(_ name: String) -> String {
        name.replacingOccurrences(of: " Police Department (reported until 2019)", with: " police (until 2019)")
            .replacingOccurrences(of: " Police Department", with: " police")
            .replacingOccurrences(of: "Bay County Sheriff's Office", with: "Sheriff's Office")
    }

    /// $74.4M / $812K, like the site.
    public static func money(_ n: Double?) -> String {
        guard let n else { return "—" }
        return n >= 1e6 ? String(format: "$%.1fM", n / 1e6) : "$\(Format.number((n / 1e3).rounded()))K"
    }
}
