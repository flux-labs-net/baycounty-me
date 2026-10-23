import XCTest
@testable import BayCountyKit

final class PeriodTests: XCTestCase {
    private func row(_ d: [String: String]) -> Row {
        Row(id: 0, values: d.mapValues { JSONValue.string($0) })
    }

    func testRecordYears() {
        XCTAssertEqual(Period.of(row(["date": "2026-03-10"])), Period(year: 2026, fiscal: false))
        XCTAssertEqual(Period.of(row(["date_start": "2025-10-01", "date_end": "2026-09-30", "fy": "FY2026"])), Period(year: 2026, fiscal: true))
        XCTAssertEqual(Period.of(row(["date_start": "2026-10-21", "date_end": "2026-10-21"])), Period(year: 2026, fiscal: false))
        XCTAssertEqual(Period.of(row(["date_or_fy": "FY2014"])), Period(year: 2014, fiscal: true))
        XCTAssertEqual(Period.of(row(["fiscal_year": "FY2025-26"])), Period(year: 2026, fiscal: true))
        XCTAssertEqual(Period.of(row(["tax_year": "2025"])), Period(year: 2025, fiscal: false))
        XCTAssertEqual(Period.of(row(["election": "2024 primary/general"])), Period(year: 2024, fiscal: false))
        XCTAssertNil(Period.of(row(["name": "No date"])))
        XCTAssertEqual(Period.of(row(["as_of": "FY2026-27"])), Period(year: 2027, fiscal: true))
        // A payment dated Nov 2025 falls in FY2026 when its list is kept by fiscal year.
        let mixed = [row(["date_end": "2026-09-30", "date_start": "2025-10-01"]), row(["date_end": "2025-09-30", "date_start": "2024-10-01"]),
                     row(["date": "2025-11-04"])]
        let idx = Period.Index(mixed)
        XCTAssertTrue(idx.fiscal)
        XCTAssertEqual(idx.periods.map(\.label), ["FY2026", "FY2025"])
        XCTAssertEqual(Period(year: 2026, fiscal: true).label, "FY2026")
    }

    func testDefaultPeriod() {
        let oct22 = ISO8601DateFormatter().date(from: "2026-10-22T12:00:00Z")!
        let cal = [2026, 2025, 2024].map { Period(year: $0, fiscal: false) }
        XCTAssertEqual(Period.defaultPeriod(in: cal, now: oct22)?.year, 2026)
        // No records yet this year: the newest past year.
        XCTAssertEqual(Period.defaultPeriod(in: [2025, 2024].map { Period(year: $0, fiscal: false) }, now: oct22)?.year, 2025)
        // Fiscal lists open on the fiscal year that began Oct 1.
        let fy = [2027, 2026, 2025].map { Period(year: $0, fiscal: true) }
        XCTAssertEqual(Period.defaultPeriod(in: fy, now: oct22)?.label, "FY2027")
        // Planned future years don't win over the current one.
        let planned = [2030, 2026, 2025].map { Period(year: $0, fiscal: false) }
        XCTAssertEqual(Period.defaultPeriod(in: planned, now: oct22)?.year, 2026)
    }

    /// Every published dataset either has periods for its rows or has no dates at all.
    func testPublishedDatasets() throws {
        let dir = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
            .appendingPathComponent("../../../../site/public/downloads").standardized
        guard FileManager.default.fileExists(atPath: dir.path) else { throw XCTSkip("site build not present") }
        func rows(_ id: String) throws -> [Row] { try Row.decodeList(Data(contentsOf: dir.appendingPathComponent("\(id).json"))) }
        let oct22 = ISO8601DateFormatter().date(from: "2026-10-22T12:00:00Z")!
        for id in ["contracts", "votes", "member-votes", "change-orders"] {
            XCTAssertEqual(Period.defaultPeriod(for: try rows(id), now: oct22), Period(year: 2026, fiscal: false), id)
        }
        for id in ["cra-payments", "audit-findings", "salary-positions", "officials-pay"] {
            XCTAssertTrue(Period.all(in: try rows(id)).allSatisfy(\.fiscal), id)
            let p = Period.defaultPeriod(for: try rows(id), now: oct22)
            XCTAssertEqual(p?.fiscal, true, id)
            XCTAssertGreaterThan(Period.all(in: try rows(id)).count, 1, id)
        }
        // Pay snapshots "as of" a date are kept by calendar year.
        XCTAssertEqual(Period.defaultPeriod(for: try rows("salary-leaders"), now: oct22), Period(year: 2026, fiscal: false))
        // Most sales tax projects have no date, so that list opens on every year.
        XCTAssertNil(Period.defaultPeriod(for: try rows("sales-tax-projects"), now: oct22))
        // One fiscal year only: no year picker.
        XCTAssertNil(Period.defaultPeriod(for: try rows("budget-detail"), now: oct22))
    }
}
