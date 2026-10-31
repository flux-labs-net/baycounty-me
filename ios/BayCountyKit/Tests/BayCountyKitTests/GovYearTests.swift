import XCTest
@testable import BayCountyKit

/// A government's year: budget lines for the year picked, and the "no data" note naming the nearest years and why.
/// Same wording as site/gov.js and the Kotlin GovYearTest.
final class GovYearTests: XCTestCase {
    private func row(_ v: [String: JSONValue]) -> Row { Row(id: 0, values: v) }
    private var now: Date {
        var c = DateComponents(); c.year = 2026; c.month = 10; c.day = 31; c.hour = 9
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "America/Chicago")!
        return cal.date(from: c)!
    }

    func testBudgetForTheYearOnly() {
        let rows = [
            row(["gov_id": .string("lh"), "fiscal_year": .number(2022), "basis": .string("adopted"), "section": .string("total"), "line_key": .string("total"), "name": .string("Total budget"), "amount": .number(57_100_000), "status": .string("adopted")]),
            row(["gov_id": .string("lh"), "fiscal_year": .number(2022), "basis": .string("adopted"), "section": .string("department"), "line_key": .string("d:pd"), "name": .string("Police"), "amount": .number(4_000_000)]),
            row(["gov_id": .string("lh"), "fiscal_year": .number(2022), "basis": .string("actual"), "section": .string("revenue"), "line_key": .string("r:x"), "name": .string("Borrowing"), "amount": .number(9), "in_total": .bool(false)]),
            row(["gov_id": .string("lh"), "fiscal_year": .number(2023), "basis": .string("adopted"), "section": .string("department"), "line_key": .string("d:pd"), "name": .string("Police"), "amount": .number(5_000_000)]),
        ]
        let b = GovYear.budget(rows, gov: "lh", year: 2022)
        XCTAssertEqual(b.total, 57_100_000)
        XCTAssertEqual(b.departments, [GovYear.Line(name: "Police", amount: 4_000_000)])
        XCTAssertTrue(b.revenue.isEmpty)
        XCTAssertEqual(GovYear.budgetYears(rows, gov: "lh", basis: "adopted"), [2022, 2023])
    }

    func testGapNamesNearestYearAndWhy() {
        XCTAssertEqual(GovYear.gap("audit", year: 2019, have: [2023, 2024, 2025], kind: .audit, gov: "lh", short: "Lynn Haven", now: now),
                       "No FY2019 audit on file. Earliest we have: FY2023. The state Auditor General posts only the last five years of audits; older ones have to come from Lynn Haven.")
        XCTAssertEqual(GovYear.gap("audit", year: 2022, have: [2023, 2024, 2025], kind: .audit, gov: "lh", short: "Lynn Haven", now: now),
                       "No FY2022 audit on file. Earliest we have: FY2023. We haven't read it in yet; it is among the last five years of audits the state Auditor General posts online.")
        XCTAssertEqual(GovYear.gap("audit", year: 2027, have: [2025], kind: .audit, gov: "lh", short: "Lynn Haven", now: now),
                       "No FY2027 audit on file. Latest we have: FY2025. FY2027 runs to Sep 30, 2027; audited figures come only after the year ends.")
        XCTAssertEqual(GovYear.gap("adopted budget", year: 2019, have: [2020, 2021], kind: .budget, gov: "lh", short: "Lynn Haven", now: now),
                       "No FY2019 adopted budget on file. Earliest we have: FY2020. Not in Lynn Haven's budget documents online or the state audit reports we have.")
    }

    func testFiscalYearOfAuditLabel() {
        XCTAssertEqual(GovYear.fiscalYearOf("FY2024 (year ended 2024-09-30)"), 2024)
        XCTAssertEqual(GovYear.years(gov: "lh", now: now).first, 2027)
        XCTAssertEqual(GovYear.years(gov: "lh", now: now).last, 2016)
    }
}
