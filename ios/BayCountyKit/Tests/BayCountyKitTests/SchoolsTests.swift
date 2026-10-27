import XCTest
@testable import BayCountyKit

/// Schools against the site's published school datasets (the same checks as the Android SchoolsTest).
final class SchoolsTests: XCTestCase {
    func rows(_ id: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json")))
    }

    func testSchoolsAndCalendar() throws {
        let schools = try rows("schools")
        let open = Schools.open(schools)
        XCTAssertGreaterThan(open.count, 40)
        XCTAssertEqual(open.first?.string("level"), "Elementary")
        XCTAssertTrue(Schools.open(schools, filter: .charter).allSatisfy { $0.bool("charter") == true })
        XCTAssertTrue(Schools.open(schools, query: "bay high").contains { $0.string("name") == "Bay High School" })
        XCTAssertFalse(Schools.closed(schools).isEmpty)
        let years = Schools.districtEnrollment(try rows("school-enrollment"))
        XCTAssertEqual(years.first?.year, "2015-16")
        XCTAssertTrue(years.allSatisfy { $0.students > 20_000 })
        let cal = try rows("school-calendar")
        XCTAssertFalse(Schools.upcoming(cal, today: "2000-01-01").isEmpty)
        XCTAssertTrue(Schools.upcoming(cal, today: "2000-01-01", kind: .off).allSatisfy { ["no-school", "break"].contains($0.string("kind") ?? "") })
    }

    func testWhen() throws {
        let r = try Row.decodeList(Data("""
        [{"starts":"2026-10-27T15:00","ends":"2026-10-27T17:00","all_day":false},
         {"starts":"2026-10-28","ends":"2026-10-28","all_day":true},{"starts":"2026-11-23","ends":"2026-11-27","all_day":true}]
        """.utf8))
        XCTAssertEqual(Schools.when(r[0]), "Tue, Oct 27 · 3 p.m.")
        XCTAssertEqual(Schools.when(r[1]), "Wednesday, October 28")
        XCTAssertEqual(Schools.when(r[2]), "Mon, Nov 23 to Fri, Nov 27")
    }
}
