import Foundation

/// One government's figures for one fiscal year, for the government screen's Year picker. The same year rules and
/// "no data" wording as the government pages on the site (site/gov.js): a year with no record says so, names the
/// nearest years we have, and says why. Mirrors android/kit GovYear.kt.
public enum GovYear {
    public enum Kind: Sendable { case audit, budget }

    public struct Line: Sendable, Hashable, Identifiable {
        public let name: String
        public let amount: Double
        public var id: String { name }
        public init(name: String, amount: Double) { self.name = name; self.amount = amount }
    }

    /// One fiscal year of the budget-years dataset for one government.
    public struct Budget: Sendable {
        public let year: Int
        public let total: Double?
        public let generalFund: Double?
        public let status: String?
        public let funds: [Line]
        public let departments: [Line]
        public let revenue: [Line]
        public let spending: [Line]
        public var hasAdopted: Bool { total != nil || generalFund != nil }
    }

    /// Fiscal years to pick from, newest first: the site's first year (2016) to the current fiscal year.
    public static func years(gov: String, now: Date = Date()) -> [Int] {
        Array((Cutoff.firstYear...Officeholders.fiscalYear(gov: gov, date: now)).reversed())
    }

    static func fy(_ r: Row) -> Int? { r.number("fiscal_year").map(Int.init) }

    /// This government's government-years row for the year, if there is one.
    public static func row(_ rows: [Row], gov: String, year: Int) -> Row? {
        rows.first { $0.string("gov_id") == gov && fy($0) == year }
    }

    /// Fiscal years with a value in a government-years column.
    public static func yearsWith(_ rows: [Row], gov: String, column: String) -> [Int] {
        Array(Set(rows.filter { $0.string("gov_id") == gov && $0.number(column) != nil }.compactMap(fy))).sorted()
    }

    /// "FY2024 (year ended 2024-09-30)" -> 2024.
    public static func fiscalYearOf(_ s: String?) -> Int? {
        guard let s, let r = s.range(of: #"FY\s*\d{4}"#, options: .regularExpression) else { return nil }
        return Int(s[r].suffix(4))
    }

    public static func budget(_ rows: [Row], gov: String, year: Int) -> Budget {
        let rs = rows.filter { $0.string("gov_id") == gov && fy($0) == year }
        func lines(_ basis: String, _ section: String) -> [Line] {
            rs.filter { $0.string("basis") == basis && $0.string("section") == section && $0.bool("in_total") != false }
                .compactMap { r in r.number("amount").flatMap { $0 > 0 ? Line(name: r.string("name") ?? "", amount: $0) : nil } }
                .sorted { $0.amount > $1.amount }
        }
        let total = rs.first { $0.string("basis") == "adopted" && $0.string("line_key") == "total" }
        let gf = rs.first { $0.string("basis") == "adopted" && $0.string("line_key") == "general_fund" }
        return Budget(year: year, total: total?.number("amount"), generalFund: gf?.number("amount"), status: (total ?? gf)?.string("status"),
                      funds: lines("adopted", "fund"), departments: lines("adopted", "department"),
                      revenue: lines("actual", "revenue"), spending: lines("actual", "spending"))
    }

    /// Fiscal years with budget-years lines of a basis (and, optionally, one of the sections).
    public static func budgetYears(_ rows: [Row], gov: String, basis: String, sections: Set<String>? = nil) -> [Int] {
        Array(Set(rows.filter { $0.string("gov_id") == gov && $0.string("basis") == basis && (sections.map { s in s.contains($0.string("section") ?? "") } ?? true) }
            .compactMap(fy))).sorted()
    }

    /// "No FY2019 audit on file. Earliest we have: FY2023. The state Auditor General posts …"
    public static func gap(_ what: String, year: Int, have: [Int], kind: Kind, gov: String, short: String, now: Date = Date()) -> String {
        let h = Array(Set(have)).sorted()
        let before = h.last { $0 < year }, after = h.first { $0 > year }
        let near: String
        switch (before, after) {
        case let (b?, a?): near = "Nearest we have: FY\(b) and FY\(a)."
        case let (b?, nil): near = "Latest we have: FY\(b)."
        case let (nil, a?): near = "Earliest we have: FY\(a)."
        default: near = ""
        }
        let w = Officeholders.fyWindow(gov: gov, year: year), today = Dates.dayKey(now)
        let why: String
        if h.isEmpty {
            why = "We have no \(what) for \(short) in any year yet."
        } else if kind == .audit && w.to >= today {
            let end = Dates.parse(w.to).map { Dates.display($0, hasTime: false) } ?? w.to
            why = "FY\(year) runs to \(end); audited figures come only after the year ends."
        } else if kind == .audit && year > h.last! {
            why = "Florida gives governments nine months after the year ends to file the audit with the state, and the FY\(year) one isn't on file here yet."
        } else if kind == .audit && year < h.first! && year > h.last! - 5 {
            why = "We haven't read it in yet; it is among the last five years of audits the state Auditor General posts online."
        } else if kind == .audit && year < h.first! {
            why = "The state Auditor General posts only the last five years of audits; older ones have to come from \(short)."
        } else if kind == .budget && w.from > today {
            why = "FY\(year) hasn't started; \(short) adopts each budget in September."
        } else if kind == .budget && year < h.first! {
            why = "Not in \(short.hasSuffix("s") ? short + "'" : short + "'s") budget documents online or the state audit reports we have."
        } else {
            why = "Not in the records we have found yet."
        }
        return ["No FY\(year) \(what) on file.", near, why].filter { !$0.isEmpty }.joined(separator: " ")
    }
}
