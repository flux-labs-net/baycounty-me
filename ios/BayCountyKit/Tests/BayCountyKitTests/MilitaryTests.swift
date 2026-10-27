import XCTest
@testable import BayCountyKit

/// The Military screen's totals against the published datasets (same numbers as site/military_page.py).
final class MilitaryTests: XCTestCase {
    private func rows(_ id: String) throws -> [Row] {
        let url = DataTests.downloads.appendingPathComponent("\(id).json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        return try Row.decodeList(Data(contentsOf: url))
    }

    func testBasesNewsAndContracts() throws {
        let bases = try rows("military-installations"), news = try rows("military-news"), years = try rows("federal-contract-years")
        XCTAssertEqual(Set(bases.compactMap { $0.string("installation_id") }), ["tyndall-afb", "nsa-panama-city"])
        let s = Military.stories(news)
        XCTAssertEqual(s.map { $0.string("published") ?? "" }, s.map { $0.string("published") ?? "" }.sorted(by: >))
        XCTAssertTrue(Military.stories(news, base: "tyndall-afb").allSatisfy { $0.string("installation_id") == "tyndall-afb" })
        let c = Military.companies(years)
        XCTAssertFalse(c.isEmpty)
        XCTAssertEqual(c.map(\.total), c.map(\.total).sorted(by: >))
        XCTAssertTrue(years.allSatisfy { ($0.number("year") ?? 0) >= 2016 })
        XCTAssertEqual(Military.byYear(years).map { $0.defense + $0.other }.reduce(0, +), Military.total(years), accuracy: 1)
    }

    func testDateLabel() {
        XCTAssertEqual(Military.dateLabel("2026-09-17T11:56"), "Sep 17, 2026")
        XCTAssertEqual(Military.dateLabel(nil), "")
    }
}
