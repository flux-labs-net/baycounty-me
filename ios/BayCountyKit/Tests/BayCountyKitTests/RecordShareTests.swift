import XCTest
@testable import BayCountyKit

/// Copy and Share text for a record: the same shape on the site (site/share.js), iOS and Android (RecordShareTest.kt).
final class RecordShareTests: XCTestCase {
    func rows(_ id: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json")))
    }

    func testContractTextHasItsFieldsSourceAndLink() throws {
        let cat = try JSONDecoder().decode(Catalog.self, from: Data(contentsOf: DataTests.downloads.appendingPathComponent("index.json")))
        let info = try XCTUnwrap(cat.dataset("contracts"))
        let row = try XCTUnwrap(try rows("contracts").first { DatasetSpec.sourceURL($0) != nil })
        let lines = RecordShare.text("contracts", row, columns: info.columns, listTitle: info.title).components(separatedBy: "\n")
        XCTAssertEqual(lines.first, DatasetSpec.for("contracts").title(row))
        XCTAssertTrue(lines.dropFirst().contains { $0.contains(": ") })
        XCTAssertLessThanOrEqual(lines.count, RecordShare.maxFields + 4)
        XCTAssertEqual(lines[lines.count - 2], "From “\(info.title)” on BayCounty.me")
        XCTAssertEqual(lines.last, "https://baycounty.me/public-money/contracts")
        XCTAssertTrue(lines.contains { $0.hasPrefix("Source: http") })
    }

    func testOwnPageWinsOverTheListPage() throws {
        let r = try XCTUnwrap(try rows("restaurants").first { $0.string("page_url") != nil })
        XCTAssertEqual(RecordShare.url("restaurants", r)?.absoluteString, "https://baycounty.me" + (r.string("page_url") ?? ""))
    }

    func testPageText() {
        XCTAssertEqual(RecordShare.page(title: "Mosey's Downtown", summary: ["Restaurant · Panama City", ""], path: "/restaurants/moseys-downtown-1304089"),
                       "Mosey's Downtown\nRestaurant · Panama City\nhttps://baycounty.me/restaurants/moseys-downtown-1304089")
    }
}
