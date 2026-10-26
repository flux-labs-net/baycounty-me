import Foundation

/// How much property tax goes to the redevelopment agencies (CRAs), from the cra-agencies, cra-tax-increment and
/// cra-increment-checks datasets. The same figures as /public-money/cra-tax-increment (site/cra_increment.js).
public enum CRAIncrement {
    public enum Scenario: String, Sendable, CaseIterable {
        case low, mid, high
        public var label: String { switch self { case .low: "Low 3%"; case .mid: "Middle 6%"; case .high: "High 9%" } }
    }

    /// Who pays: every payer, only Bay County, or only the cities.
    public enum Payer: String, Sendable, CaseIterable {
        case all, county, cities
        public var label: String { switch self { case .all: "All payers"; case .county: "Bay County"; case .cities: "Cities" } }
        func amount(_ r: Row) -> Double {
            switch self {
            case .all: r.number("increment") ?? 0
            case .county: r.number("county_amount") ?? 0
            case .cities: r.number("city_amount") ?? 0
            }
        }
    }

    public struct Headline: Sendable {
        public let lastYear: Int
        public let firstYear: Int
        public let total: Double
        public let county: Double
        public let frontBeachRoad: Double
        public let agencies: Int
        public let paidOnRecord: Double
        public let countyOnRecord: Double
        public let toComeLow: Double
        public let toComeHigh: Double
    }

    public struct YearTotal: Sendable, Hashable, Identifiable {
        public let fiscalYear: Int
        public let amount: Double
        public let projected: Bool
        public var id: Int { fiscalYear }
    }

    public static let shortNames = ["pcb-fbr": "Front Beach Road", "pcb-pier": "Pier Park", "pc": "Panama City", "lh": "Lynn Haven",
                                    "callaway": "Callaway", "springfield": "Springfield", "parker": "Parker"]

    static func fy(_ r: Row) -> Int { r.number("fiscal_year").map(Int.init) ?? 0 }
    static func sum(_ rows: [Row], _ key: String) -> Double { rows.compactMap { $0.number(key) }.reduce(0, +) }

    public static func headline(agencies: [Row], years: [Row]) -> Headline? {
        let h = years.filter { $0.string("scenario") == "history" }
        guard let last = h.map(fy).max(), let first = h.map(fy).min() else { return nil }
        let y = h.filter { fy($0) == last }
        return Headline(lastYear: last, firstYear: first, total: sum(y, "increment"), county: sum(y, "county_amount"),
                        frontBeachRoad: sum(y.filter { $0.string("cra_id") == "pcb-fbr" }, "increment"), agencies: agencies.count,
                        paidOnRecord: sum(h, "increment"), countyOnRecord: sum(h, "county_amount"),
                        toComeLow: sum(agencies, "to_come_low"), toComeHigh: sum(agencies, "to_come_high"))
    }

    /// Yearly totals: reported years, then the chosen growth scenario until each CRA's sunset.
    public static func byYear(_ years: [Row], scenario: Scenario = .mid, payer: Payer = .all) -> [YearTotal] {
        let h = years.filter { $0.string("scenario") == "history" }
        let lastH = h.map(fy).max() ?? 0
        let rows = h + years.filter { $0.string("scenario") == scenario.rawValue }
        var by: [Int: Double] = [:]
        for r in rows { by[fy(r), default: 0] += payer.amount(r) }
        return by.keys.sorted().map { YearTotal(fiscalYear: $0, amount: by[$0]!, projected: $0 > lastH) }
    }

    /// What is still to come for one CRA under a scenario.
    public static func toCome(_ agency: Row, _ scenario: Scenario) -> Double? { agency.number("to_come_\(scenario.rawValue)") }
}
