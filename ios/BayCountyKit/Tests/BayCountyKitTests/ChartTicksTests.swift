import XCTest
@testable import BayCountyKit

final class ChartTicksTests: XCTestCase {
    func testLabelsThinOutAndKeepTheLast() {
        XCTAssertEqual(ChartTicks.labelIndices(count: 4), [0, 1, 2, 3])
        XCTAssertEqual(ChartTicks.labelIndices(count: 12), [1, 3, 5, 7, 9, 11])
        XCTAssertEqual(ChartTicks.labelIndices(count: 34).count, 6)
        XCTAssertEqual(ChartTicks.labelIndices(count: 34).last, 33)
        XCTAssertEqual(ChartTicks.labelIndices(count: 0), [])
        for n in 1...40 { XCTAssertLessThanOrEqual(ChartTicks.labelIndices(count: n).count, ChartTicks.phoneLabels) }
    }

    func testYearTicksAreRound() {
        XCTAssertEqual(ChartTicks.yearTicks(Array(2016...2049)), [2020, 2025, 2030, 2035, 2040, 2045])
        XCTAssertEqual(ChartTicks.yearTicks(Array(2021...2026)), Array(2021...2026))
        XCTAssertEqual(ChartTicks.yearTicks(Array(2016...2026)), [2016, 2018, 2020, 2022, 2024, 2026])
    }

    func testCutoff() {
        XCTAssertEqual(ChartTicks.sinceCutoff([2003, 2015, 2016, 2025]) { $0 }, [2016, 2025])
        XCTAssertEqual(ChartTicks.year(of: "FY2024"), 2024)
        XCTAssertEqual(ChartTicks.year(of: "'19"), 2019)
        XCTAssertNil(ChartTicks.year(of: "Jan"))
    }

    func testCRASeriesStartsAt2016() {
        func row(_ fy: Int, _ scenario: String, _ v: Double) -> Row {
            Row(id: fy, values: ["fiscal_year": .number(Double(fy)), "scenario": .string(scenario), "increment": .number(v),
                                 "county_amount": .number(v / 2), "cra_id": .string("pc")])
        }
        let rows = [row(2003, "history", 1), row(2016, "history", 2), row(2025, "history", 3), row(2026, "mid", 4)]
        let s = CRAIncrement.byYear(rows)
        XCTAssertEqual(s.map(\.fiscalYear), [2016, 2025, 2026])
        XCTAssertEqual(s.last?.projected, true)
        XCTAssertEqual(CRAIncrement.headline(agencies: [], years: rows)?.firstYear, 2016)
    }
}
