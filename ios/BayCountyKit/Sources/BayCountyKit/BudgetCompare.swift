import Foundation

/// One government's budget in two fiscal years, line by line, from the budget-years dataset.
/// A Swift port of api/_budget.js `compare`, so the app shows the same comparison as /public-money/budget-compare.
public enum BudgetCompare {
    public enum Basis: String, Sendable, CaseIterable { case adopted, actual }

    public struct Line: Sendable, Hashable, Identifiable {
        public let key: String
        public var name: String
        public var from: Double?
        public var to: Double?
        public let inTotal: Bool
        public var id: String { key }
        public var change: Double { (to ?? 0) - (from ?? 0) }
        /// Percent change, one decimal, when both years have the line.
        public var pct: Double? {
            guard let f = from, let t = to, f != 0 else { return nil }
            return ((t - f) / abs(f) * 1000).rounded() / 10
        }
        /// added, removed or both.
        public var status: String { from == nil ? "added" : to == nil ? "removed" : "both" }
    }

    public struct Section: Sendable, Hashable, Identifiable {
        public let key: String
        public let title: String
        public let lines: [Line]
        public var id: String { key }
    }

    public struct Result: Sendable {
        public let government: String
        public let govID: String
        public let basis: Basis
        public let from: Int
        public let to: Int
        public let years: [Int]
        public let detailYears: [Int]
        public let totals: [Line]
        public let sections: [Section]
        public let biggestIncrease: Line?
        public let biggestDecrease: Line?
        public let notes: [String]
        public let sources: (from: [URL], to: [URL])
        /// Total budget by year, for the trend chart.
        public let history: [(fiscalYear: Int, total: Double)]
    }

    static let sectionsFor: [Basis: [String]] = [.adopted: ["department", "fund"], .actual: ["spending", "revenue"]]
    static let sectionTitles = ["department": "General Fund, by department", "fund": "By fund", "service": "By service",
                                "spending": "Spending", "revenue": "Revenue"]

    /// Governments with at least two years on record for a basis, in the site's order.
    public static func governments(_ rows: [Row], basis: Basis = .adopted) -> [String] {
        var years: [String: Set<Int>] = [:]
        for r in rows where r.string("basis") == basis.rawValue {
            if let g = r.string("gov_id"), let y = r.number("fiscal_year") { years[g, default: []].insert(Int(y)) }
        }
        let have = years.filter { $0.value.count >= 2 }.map(\.key)
        let order = ["county", "schools", "pc", "pcb", "lh", "cw", "sp", "parker", "mb"]
        return have.sorted { (order.firstIndex(of: $0) ?? 99, $0) < (order.firstIndex(of: $1) ?? 99, $1) }
    }

    static func lines(_ rows: [Row], from: Int, to: Int, key: (Row) -> String = { $0.string("line_key") ?? "" },
                      name: (Row) -> String = { $0.string("name") ?? "" }) -> [Line] {
        var order: [String] = []
        var m: [String: Line] = [:]
        for r in rows {
            guard let y = r.number("fiscal_year").map(Int.init), y == from || y == to else { continue }
            let k = key(r)
            if m[k] == nil { order.append(k); m[k] = Line(key: k, name: "", from: nil, to: nil, inTotal: r.bool("in_total") != false) }
            let amount = r.number("amount") ?? 0
            if y == to {
                m[k]!.to = (m[k]!.to ?? 0) + amount
                m[k]!.name = name(r)
            } else {
                m[k]!.from = (m[k]!.from ?? 0) + amount
                if m[k]!.name.isEmpty { m[k]!.name = name(r) }
            }
        }
        return order.compactMap { m[$0] }.enumerated()
            .sorted { a, b in
                let (x, y) = (a.element, b.element)
                if abs(x.change) != abs(y.change) { return abs(x.change) > abs(y.change) }
                if (x.to ?? 0) != (y.to ?? 0) { return (x.to ?? 0) > (y.to ?? 0) }
                return a.offset < b.offset
            }
            .map(\.element)
    }

    /// Fiscal years on record for a government and basis.
    public static func years(_ rows: [Row], gov: String, basis: Basis = .adopted) -> [Int] {
        Array(Set(rows.filter { $0.string("gov_id") == gov && $0.string("basis") == basis.rawValue }
            .compactMap { $0.number("fiscal_year").map(Int.init) })).sorted()
    }

    /// Compares two years. With no years given: the latest year with line-by-line detail against the detail year before it.
    public static func compare(_ all: [Row], gov: String, basis: Basis = .adopted, from: Int? = nil, to: Int? = nil) -> Result? {
        let rows = all.filter { $0.string("gov_id")?.lowercased() == gov.lowercased() }
        guard let first = rows.first else { return nil }
        let mine = rows.filter { $0.string("basis") == basis.rawValue }
        let fy = { (r: Row) in r.number("fiscal_year").map(Int.init) ?? 0 }
        let years = Array(Set(mine.map(fy))).sorted()
        let detail = Array(Set(mine.filter { $0.string("section") != "total" }.map(fy))).sorted()
        guard years.count >= 2 else { return nil }
        let pool = detail.count >= 2 ? detail : years
        let toY = to ?? pool.last!
        guard let fromY = from ?? (pool.reversed().first { $0 < toY } ?? years.filter { $0 < toY }.last),
              years.contains(fromY), years.contains(toY), fromY != toY else { return nil }
        let yr = mine.filter { fy($0) == fromY || fy($0) == toY }
        let sec = { (s: String) in yr.filter { $0.string("section") == s } }
        var sections: [Section] = []
        for s in sectionsFor[basis]! { sections.append(Section(key: s, title: sectionTitles[s]!, lines: lines(sec(s), from: fromY, to: toY))) }
        if basis == .adopted {
            let svc = { (r: Row) in r.string("service") ?? "Other services" }
            sections.append(Section(key: "service", title: sectionTitles["service"]!, lines: lines(sec("department"), from: fromY, to: toY, key: svc, name: svc)))
        }
        let totalOrder = ["total", "general_fund", "revenue_total", "spending_total"]
        let totals = lines(sec("total"), from: fromY, to: toY).sorted {
            (totalOrder.firstIndex(of: $0.key) ?? -1) < (totalOrder.firstIndex(of: $1.key) ?? -1)
        }
        var history: [(fiscalYear: Int, total: Double)] = []
        var status: [Int: String] = [:]
        for y in years {
            let t = mine.filter { fy($0) == y && $0.string("section") == "total" }
            status[y] = t.first?.string("status")
            if let v = t.first(where: { $0.string("line_key") == "total" || $0.string("line_key") == "spending_total" })?.number("amount") {
                history.append((y, v))
            }
        }
        var notes: [String] = []
        let main = sections[0].lines
        let has = { (y: Int) in main.contains { (y == fromY ? $0.from : $0.to) != nil } }
        for y in [fromY, toY] where !has(y) {
            notes.append("FY\(y) has only a total on record, no \(basis == .actual ? "breakdown" : "fund or department lines").")
        }
        if has(fromY), has(toY) {
            let both = main.filter { $0.status == "both" }.count
            if Double(both) < Double(main.count) / 2 {
                notes.append("Most \(basis == .actual ? "lines" : "department names") differ between the two documents, so compare by service or total.")
            }
        }
        if let a = status[fromY], let b = status[toY], a != b {
            notes.append("FY\(fromY) is \(a) and FY\(toY) is \(b), so they aren't measured the same way.")
        }
        func src(_ y: Int) -> [URL] {
            var seen = Set<String>()
            return yr.filter { fy($0) == y }.compactMap { $0.string("source_url") }.filter { seen.insert($0).inserted }.compactMap(URL.init(string:))
        }
        let moved = main.filter { $0.status == "both" && $0.inTotal && ($0.from ?? 0) > 0 && ($0.to ?? 0) > 0 }
        return Result(government: first.string("government") ?? "", govID: first.string("gov_id") ?? gov, basis: basis,
                      from: fromY, to: toY, years: years, detailYears: detail, totals: totals, sections: sections,
                      biggestIncrease: moved.first { $0.change > 0 }, biggestDecrease: moved.first { $0.change < 0 },
                      notes: notes, sources: (src(fromY), src(toY)), history: history)
    }
}
