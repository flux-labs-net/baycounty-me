import XCTest
@testable import BayCountyKit

/// The volunteer board reads the published volunteer-needs and volunteer-orgs datasets the same way the site does.
final class VolunteerTests: XCTestCase {
    func rows(_ id: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json")))
    }

    func testNeedsAndOrgsRead() throws {
        let needs = try rows("volunteer-needs"), orgs = try rows("volunteer-orgs")
        XCTAssertFalse(needs.isEmpty)
        XCTAssertGreaterThan(orgs.count, 20)
        XCTAssertTrue(needs.allSatisfy { Volunteer.causes.contains($0.string("cause") ?? "") })
        XCTAssertTrue(orgs.allSatisfy { Volunteer.causes.contains($0.string("cause") ?? "") })
        let dated = Volunteer.open(needs, today: "2000-01-01").prefix { $0.string("starts") != nil }.compactMap { $0.string("starts") }
        XCTAssertEqual(dated, dated.sorted())
        let c = Volunteer.causes(in: needs, orgs)
        XCTAssertEqual(c, Volunteer.causes.filter { c.contains($0) })
    }

    func testLabels() throws {
        let r = try Row.decodeList(Data(#"[{"starts":"2026-12-03","ends":"2026-12-03","schedule":"One day"},{"schedule":"Ongoing","remote":true},{"schedule":"Shifts"}]"#.utf8))
        XCTAssertEqual(Volunteer.when(r[0]), "Thu, Dec 3")
        XCTAssertEqual(Volunteer.when(r[1]), "Ongoing")
        XCTAssertEqual(Volunteer.whereLabel(r[1]), "Remote or from home")
        XCTAssertEqual(Volunteer.when(r[2]), "Multiple shifts")
    }
}
