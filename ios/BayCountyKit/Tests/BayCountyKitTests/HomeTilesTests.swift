import XCTest
@testable import BayCountyKit

/// The Home tab's tiles: owners lead with the tax bill, renters with utilities, everyone else with setup.
/// Same cases as android/kit HomeTilesTest.kt.
final class HomeTilesTests: XCTestCase {
    private func row(_ v: [String: JSONValue]) -> Row { Row(id: 0, values: v) }
    private var cal: Calendar { var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!; return c }
    private func at(_ m: Int, _ d: Int, _ h: Int) -> Date { cal.date(from: DateComponents(year: 2026, month: m, day: d, hour: h))! }
    private func lynnHaven() throws -> UtilityLookup {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "utilities-lynn-haven", withExtension: "json", subdirectory: "Fixtures"))
        return try UtilityLookup.decode(Data(contentsOf: url))   // garbage on Friday
    }

    func testLeadTileFollowsOwnOrRent() throws {
        let home = try lynnHaven()
        let wed = at(10, 28, 8)
        let own = HomeTiles.tiles(tenure: .own, hasHome: true, utilities: home, taxTotal: 3284.6, beach: [], meetings: [], electionDay: nil, now: wed)
        XCTAssertEqual(own.first?.id, "tax")
        XCTAssertEqual(own.first?.value, "$3,285")
        XCTAssertEqual(own.first?.detail, "a year · $250K home, homestead")
        XCTAssertTrue(own.first?.featured ?? false)
        let rent = HomeTiles.tiles(tenure: .rent, hasHome: true, utilities: home, taxTotal: 3284.6, beach: [], meetings: [], electionDay: nil, now: wed)
        XCTAssertEqual(rent.first?.id, "utilities")
        XCTAssertFalse(rent.contains { $0.id == "tax" })
        let unset = HomeTiles.tiles(tenure: .unset, hasHome: false, utilities: nil, taxTotal: nil, beach: [], meetings: [], electionDay: nil, now: wed)
        XCTAssertEqual(unset.map(\.id), ["setup", "beach", "meeting", "reps", "schools"])
        XCTAssertEqual(unset.last?.value, "Public schools")
    }

    func testTrashTileOnlyAroundPickupDay() throws {
        let home = try lynnHaven()
        let tiles = { (d: Date) in HomeTiles.tiles(tenure: .own, hasHome: true, utilities: home, taxTotal: nil, beach: [], meetings: [], electionDay: nil, now: d) }
        let fri = tiles(at(10, 30, 8))
        XCTAssertEqual(fri.map(\.id), ["tax", "trash", "beach", "meeting", "reps", "schools"])
        XCTAssertEqual(fri[1].value, "Today")
        XCTAssertEqual(tiles(at(10, 29, 17))[1].value, "Tomorrow")
        XCTAssertFalse(tiles(at(10, 28, 8)).contains { $0.id == "trash" })
    }

    func testElectionTileInTheWeeksBefore() {
        let t = { (d: Date) in HomeTiles.tiles(tenure: .rent, hasHome: false, utilities: nil, taxTotal: nil, beach: [], meetings: [], electionDay: "2026-11-03", now: d) }
        XCTAssertEqual(t(at(10, 30, 9)).first { $0.id == "election" }?.value, "Tue, Nov 3")
        XCTAssertEqual(t(at(11, 3, 9)).first { $0.id == "election" }?.value, "Today")
        XCTAssertNil(t(at(11, 4, 9)).first { $0.id == "election" })
        XCTAssertNil(t(at(9, 1, 9)).first { $0.id == "election" })
    }

    func testBeachAndMeetingTiles() {
        let beach = [row(["kind": .string("forecast"), "sort_order": .number(0), "flag_color": .string("Yellow"), "rip_current_risk": .string("Moderate")])]
        let m = Meeting(row: row(["id": .string("m1"), "board": .string("mb-council"), "start": .string("2026-11-05T18:00:00-06:00")]))
        let tiles = HomeTiles.tiles(tenure: .own, hasHome: false, utilities: nil, taxTotal: nil, beach: beach, meetings: [m], electionDay: nil, now: at(10, 30, 9))
        XCTAssertEqual(tiles.first { $0.id == "beach" }?.value, "Yellow flag")
        XCTAssertEqual(tiles.first { $0.id == "beach" }?.detail, "Moderate rip current risk")
        XCTAssertEqual(tiles.first { $0.id == "meeting" }?.value, "Thu, Nov 5")
        XCTAssertEqual(tiles.first { $0.id == "tax" }?.value, "Estimate")
    }

    func testAlertLeadsWithTheMostUrgentKind() {
        let n = { (k: String, s: String) in self.row(["kind": .string(k), "status": .string(s)]) }
        let a = HomeTiles.alert([n("road", "active"), n("boil-water", "active"), n("boil-water", "active"), n("weather", "ended")])
        XCTAssertEqual(a?.title, "2 boil-water notices in effect")
        XCTAssertEqual(a?.detail, "1 more active. See the map and what to do.")
        XCTAssertEqual(HomeTiles.alert([n("shelter", "active")])?.title, "1 notice in effect")
        XCTAssertNil(HomeTiles.alert([n("road", "ended")]))
    }

    func testEyebrow() {
        XCTAssertEqual(HomeTiles.eyebrow(place: "Panama City", tenure: .rent), "Your home · Panama City · Renting")
        XCTAssertEqual(HomeTiles.eyebrow(place: "Panama City", tenure: .own), "Your home · Panama City")
        XCTAssertEqual(HomeTiles.eyebrow(place: nil, tenure: .own), "Bay County")
    }
}
