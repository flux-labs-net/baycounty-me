import XCTest
@testable import BayCountyKit

/// The Restaurants screen against the published datasets (same order and wording as site/restaurants_page.py).
final class RestaurantsTests: XCTestCase {
    private func rows(_ id: String) throws -> [Row] {
        let url = DataTests.downloads.appendingPathComponent("\(id).json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        return try Row.decodeList(Data(contentsOf: url))
    }

    func testListLatestFirstAndLastInspectionIsNewest() throws {
        let r = try rows("restaurants"), i = try rows("restaurant-inspections")
        let list = Restaurants.list(r, today: "2026-10-28")
        XCTAssertFalse(list.isEmpty)
        XCTAssertTrue(list.allSatisfy { $0.bool("licensed_now") == true })
        let dates = list.map { $0.string("last_inspection") ?? "" }
        XCTAssertEqual(dates, dates.sorted(by: >))
        // the dataset's last_inspection is the newest visit (it once read the oldest)
        let one = try XCTUnwrap(list.first { ($0.number("inspections") ?? 0) > 5 })
        let visits = Restaurants.inspections(i, license: one.string("license_number") ?? "")
        XCTAssertEqual(visits.first?.string("date"), one.string("last_inspection"))
        XCTAssertEqual(Restaurants.strip(one.string("recent_results")).count, 6)
        XCTAssertTrue(Restaurants.list(r, show: .gone, today: "2026-10-28").allSatisfy { $0.bool("licensed_now") == false })
        XCTAssertTrue(Restaurants.list(r, show: .follow, today: "2026-10-28").allSatisfy { ["warning", "fine", "closed"].contains($0.string("last_result_level") ?? "") })
        XCTAssertFalse(Restaurants.cities(r).contains("Panama City Bch"))
    }

    func testWordsAndStrip() {
        XCTAssertEqual(Restaurants.strip("ok warning closed"), ["", "", "", "closed", "warning", "ok"])
        XCTAssertEqual(Restaurants.shortResult("Ordered closed (emergency order)"), "Closed by the state")
        XCTAssertEqual(Restaurants.tone("fine"), .bad)
        XCTAssertEqual(Restaurants.dateLabel("2026-10-27"), "Oct 27, 2026")
        XCTAssertEqual(Restaurants.yearAgo("2026-10-28"), "2025-10-28")
        let row = Row(id: 0, values: ["business_name": .string("Red Star"), "last_inspection": .string("2026-10-27"), "last_result": .string("Met inspection standards"),
                                      "closures": .number(2), "last_closure": .string("2026-08-26"), "inspections": .number(27)])
        XCTAssertEqual(Restaurants.summary(row), "Last inspected Oct 27, 2026: met inspection standards. The state has closed it twice since 2016, most recently Aug 26, 2026. 27 inspections on file.")
        XCTAssertEqual(Restaurants.inspectionsPath("1305433"), "/api/v1/datasets/restaurant-inspections?license_number=1305433&sort=-date&limit=1000")
    }

    func testDecodesApiAndDownloadShapes() throws {
        let api = Data(#"{"data":[{"license_number":"1"}],"meta":{"total":1}}"#.utf8), plain = Data(#"[{"license_number":"1"}]"#.utf8)
        XCTAssertEqual(try Row.decodeRows(api).first?.string("license_number"), "1")
        XCTAssertEqual(try Row.decodeRows(plain).first?.string("license_number"), "1")
    }
}
