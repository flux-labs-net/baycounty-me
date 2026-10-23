import Foundation

/// The Tax Dollars calculator (site/tax.js), line for line.
public enum TaxCalculator {
    public struct Taxable: Equatable, Sendable {
        public let school: Double
        public let other: Double
    }

    public struct Line: Identifiable, Sendable {
        public let id: String
        public let name: String
        public let group: String
        public let mills: Double
        public let base: Double
        public let amount: Double
    }

    /// Taxable values for a home worth `value` (assessed). Homestead: $25,000 off everything, plus up to the second
    /// exemption amount for that year on value above $50,000, which doesn't apply to school taxes.
    public static func taxable(value v: Double, homestead: Bool, second: Double) -> Taxable {
        guard homestead else { return Taxable(school: v, other: v) }
        let first = min(v, 25_000), secondEx = max(0, min(v - 50_000, second))
        return Taxable(school: max(0, v - first), other: max(0, v - first - secondEx))
    }

    public static func bill(model: TaxModel, district: TaxModel.District, year: Int, taxable tv: Taxable) -> [Line] {
        district.stack.compactMap { id in
            guard let a = model.auth[id] else { return nil }
            let m = a.m.indices.contains(year) ? (a.m[year] ?? 0) : 0
            let base = a.school ? tv.school : tv.other
            return Line(id: id, name: a.n, group: a.g, mills: m, base: base, amount: base / 1000 * m)
        }
    }

    public struct GroupAmount: Identifiable, Hashable, Sendable {
        public let group: String
        public let amount: Double
        public var id: String { group }
    }

    public struct YearTotal: Identifiable, Hashable, Sendable {
        public let fy: String
        public let total: Double
        public var id: String { fy }
    }

    public struct Estimate: Sendable {
        public let lines: [Line]
        public let total: Double
        public let byGroup: [GroupAmount]
        /// Same home at each year's rates, oldest first.
        public let trend: [YearTotal]
    }

    public static func estimate(model: TaxModel, district: TaxModel.District, value: Double, homestead: Bool) -> Estimate {
        let L = model.latest
        let tv = taxable(value: value, homestead: homestead, second: model.second[L])
        let lines = bill(model: model, district: district, year: L, taxable: tv)
        let shown = lines.filter { $0.mills > 0 }
        let total = shown.reduce(0) { $0 + $1.amount }
        let byGroup = model.groupIDs.map { g in GroupAmount(group: g, amount: shown.filter { $0.group == g }.reduce(0) { $0 + $1.amount }) }
            .filter { $0.amount > 0 }
        let trend = model.years.indices.map { i -> YearTotal in
            let t = bill(model: model, district: district, year: i, taxable: taxable(value: value, homestead: homestead, second: model.second[i]))
            return YearTotal(fy: model.fy[i], total: t.reduce(0) { $0 + $1.amount })
        }
        return Estimate(lines: lines, total: total, byGroup: byGroup, trend: trend)
    }

    /// "Your city" -> the city's own name for this district.
    public static func cityName(model: TaxModel, district: TaxModel.District) -> String {
        district.stack.compactMap { model.auth[$0] }.first { $0.g == "city" }?.n ?? "Your city"
    }
}

/// The Amendment 3 calculator (site/amend.js).
public enum Amendment3Calculator {
    public enum Kind: String, CaseIterable, Identifiable, Sendable {
        case home, new, non
        public var id: String { rawValue }
        public var label: String {
            switch self {
            case .home: "My homestead (Florida resident before 2027)"
            case .new: "A newer homestead"
            case .non: "Not a homestead (rental, second home, business)"
            }
        }
    }

    public struct Scenario: Sendable {
        public let label: String
        public let schoolTaxable: Double
        public let otherTaxable: Double
        public let lines: [TaxCalculator.Line]
        public var total: Double { lines.reduce(0) { $0 + $1.amount } }
        public var schoolTotal: Double { lines.filter { $0.group == "school" }.reduce(0) { $0 + $1.amount } }
    }

    public static func scenarios(model: Amendment3Model, district: TaxModel.District, value v: Double, kind k: Kind) -> [Scenario] {
        let today: (Double, Double) = k == .non ? (v, v)
            : (max(0, v - 25_000), max(0, v - min(v, 25_000) - max(0, min(v - 50_000, model.second))))
        var rows: [(String, Double, Double)]
        if k == .non {
            rows = [("Today", today.0, today.1), ("2027 bill", today.0, today.1), ("2028 bill and after", today.0, today.1)]
        } else {
            let sch = max(0, v - 25_000)
            let e27: Double = k == .new ? 50_000 : 150_000, e28: Double = k == .new ? 51_220 : 250_000
            rows = [("Today", today.0, today.1), ("2027 bill", sch, max(0, v - e27)), ("2028 bill and after", sch, max(0, v - e28))]
        }
        let L = (district.total.count) - 1
        return rows.map { label, sch, oth in
            let lines = district.stack.compactMap { id -> TaxCalculator.Line? in
                guard let a = model.auth[id] else { return nil }
                let m = a.m.indices.contains(L) ? (a.m[L] ?? 0) : 0
                let base = a.school ? sch : oth
                return TaxCalculator.Line(id: id, name: a.n, group: a.school ? "school" : a.g, mills: m, base: base, amount: base / 1000 * m)
            }.filter { $0.mills > 0 }
            return Scenario(label: label, schoolTaxable: sch, otherTaxable: oth, lines: lines)
        }
    }

    public static func note(kind: Kind, scenarios: [Scenario]) -> String {
        switch kind {
        case .non:
            return "Amendment 3 doesn't lower this property's taxes directly. It slows how fast the taxed value can rise: at most 5% a year instead of 10% for non-school taxes. That only matters if the market value is rising faster than 5%."
        case .new:
            return "Newer residents get $50,000 off non-school taxes for their first four years with a homestead, then the larger exemption in year five."
        case .home:
            return scenarios.count > 2 && scenarios[2].otherTaxable == 0
                ? "At this value the home would owe no county, city or special-district property tax, only school tax."
                : "The savings top out once the exemption reaches $250,000. Above that, every extra dollar of value is taxed as it is today."
        }
    }
}
