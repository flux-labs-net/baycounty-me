import XCTest
@testable import BayCountyKit

final class AppUsageTests: XCTestCase {
    private func fresh() -> (AppUsage, UserDefaults) {
        let name = "usage-test-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return (AppUsage(defaults: d, version: "1.4 (12)"), d)
    }
    private var cal: Calendar { var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!; return c }
    private func day(_ y: Int, _ m: Int, _ d: Int) -> Date { cal.date(from: DateComponents(year: y, month: m, day: d, hour: 10))! }

    func testFirstCheckInIsNewAndCarriesCounts() throws {
        let (u, _) = fresh()
        u.opened(); u.opened()
        u.viewed("Restaurants"); u.viewed("restaurants"); u.viewed("dataset/votes")
        u.viewed("person/John Smith")  // spaces and capitals aren't a screen name
        let b = try XCTUnwrap(u.checkIn(now: day(2026, 10, 29), calendar: cal))
        XCTAssertEqual(b["platform"] as? String, "ios")
        XCTAssertEqual(b["version"] as? String, "1.4 (12)")
        XCTAssertEqual(b["new"] as? Bool, true)
        XCTAssertEqual(b["month"] as? Bool, true)
        XCTAssertEqual(b["week"] as? Bool, true)
        XCTAssertEqual(b["opens"] as? Int, 2)
        XCTAssertEqual(b["screens"] as? [String: Int], ["restaurants": 2, "dataset/votes": 1])
        XCTAssertNil(b["device"]); XCTAssertEqual(b.count, 7)
    }

    func testOncePerDayThenWeekAndMonthFlags() throws {
        let (u, _) = fresh()
        _ = u.checkIn(now: day(2026, 10, 27), calendar: cal); u.sent(now: day(2026, 10, 27), calendar: cal)  // a Tuesday
        XCTAssertNil(u.checkIn(now: day(2026, 10, 27), calendar: cal))
        let thu = try XCTUnwrap(u.checkIn(now: day(2026, 10, 29), calendar: cal))
        XCTAssertEqual(thu["new"] as? Bool, false)
        XCTAssertEqual(thu["week"] as? Bool, false)
        XCTAssertEqual(thu["month"] as? Bool, false)
        XCTAssertEqual(thu["opens"] as? Int, 1)
        XCTAssertEqual(thu["screens"] as? [String: Int], [:])
        u.sent(now: day(2026, 10, 29), calendar: cal)
        let nov = try XCTUnwrap(u.checkIn(now: day(2026, 11, 2), calendar: cal))  // next Monday, next month
        XCTAssertEqual(nov["week"] as? Bool, true)
        XCTAssertEqual(nov["month"] as? Bool, true)
    }

    func testTurnedOffCountsAndSendsNothing() {
        let (u, d) = fresh()
        u.viewed("today")
        u.enabled = false
        u.opened(); u.viewed("money")
        XCTAssertNil(u.checkIn(now: day(2026, 10, 29), calendar: cal))
        XCTAssertNil(d.dictionary(forKey: "usage.screens"))
        u.enabled = true
        XCTAssertNotNil(u.checkIn(now: day(2026, 10, 29), calendar: cal))
    }

    func testSiteLinksAreTagged() {
        XCTAssertEqual(AppLinks.tagged(URL(string: "https://baycounty.me/parks")!).absoluteString,
                       "https://baycounty.me/parks?utm_source=ios-app&utm_medium=app")
        XCTAssertEqual(AppLinks.tagged(URL(string: "https://baycounty.me/about#contact")!, source: "android-app").absoluteString,
                       "https://baycounty.me/about?utm_source=android-app&utm_medium=app#contact")
        XCTAssertEqual(AppLinks.tagged(URL(string: "https://baycounty.me/x?utm_source=email")!).absoluteString, "https://baycounty.me/x?utm_source=email")
        XCTAssertEqual(AppLinks.tagged(URL(string: "https://fluxlabs.net/")!).absoluteString, "https://fluxlabs.net/")
    }
}
