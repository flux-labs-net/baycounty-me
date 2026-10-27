import XCTest
@testable import BayCountyKit

/// The /api/v1/utilities answer decodes, and pickup-day math matches the site's page script.
final class UtilitiesTests: XCTestCase {
    func lookup() throws -> UtilityLookup {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "utilities-lynn-haven", withExtension: "json", subdirectory: "Fixtures"))
        return try UtilityLookup.decode(Data(contentsOf: url))
    }

    func testDecodesTheApiAnswer() throws {
        let l = try lookup()
        XCTAssertEqual(l.area, "lh")
        XCTAssertEqual(l.areaName, "Lynn Haven")
        let garbage = try XCTUnwrap(l.pickup.first { $0.service == "garbage" })
        XCTAssertEqual(garbage.days, "Friday")
        XCTAssertEqual(garbage.zoneText, "ROUTE-E")
        XCTAssertNotNil(l.provider(for: garbage)?.phone)
        XCTAssertNotNil(l.typicalBill)
        XCTAssertTrue(l.otherServices.contains { $0.service == "water" })
        XCTAssertFalse(l.otherServices.contains { s in l.pickup.contains { $0.service == s.service } })
    }

    func testNextPickupDay() {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let tue = cal.date(from: DateComponents(year: 2026, month: 10, day: 27, hour: 9))!
        let thu = cal.date(from: DateComponents(year: 2026, month: 10, day: 29))!
        XCTAssertEqual(PickupDays.next("Monday, Thursday", from: tue, calendar: cal), thu)
        XCTAssertEqual(PickupDays.next("Tuesday", from: tue, calendar: cal), cal.startOfDay(for: tue))
        XCTAssertNil(PickupDays.next(nil, from: tue, calendar: cal))
    }
}
