import XCTest
@testable import BayCountyKit

/// Emergencies and Hurricane prep: the live feed, the zone lookup answer, and the sums behind the rebuild chart,
/// checked against the files the site publishes.
final class EmergencyTests: XCTestCase {
    func load(_ name: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent(name)))
    }

    func testFeedParsesNoticesSheltersAndCounts() throws {
        let json = #"{"headline":"Hurricane Warning in effect.","checked_at":"2026-10-27T21:00:00.000Z","counts":{"weather":1,"boil-water":2},"#
            + #""notices":[{"notice_id":"nws:1","kind":"weather","event":"Hurricane Warning","severity":"extreme","title":"Hurricane Warning"}],"#
            + #""shelters":[{"shelter_id":"a","name":"A","status":"open","type":"general"},{"shelter_id":"b","name":"B","status":"closed","type":"general"}],"#
            + #""zones":[{"zone":"A","ordered":true}]}"#
        let f = try Emergency.parseFeed(Data(json.utf8))
        XCTAssertEqual(f.headline, "Hurricane Warning in effect.")
        XCTAssertNotNil(f.checkedAt)
        XCTAssertEqual(f.notices.count, 1)
        XCTAssertEqual(f.count("boil-water"), 2)
        XCTAssertEqual(f.sheltersOpen, 1)
        XCTAssertEqual(f.zones.first?.bool("ordered"), true)
    }

    func testHeadlineMatchesTheSite() {
        let row = { (v: [String: JSONValue]) in Row(id: 0, values: v) }
        XCTAssertEqual(Emergency.headline([]), "No weather warnings or evacuation orders right now.")
        XCTAssertEqual(Emergency.headline([row(["kind": .string("evacuation"), "zones": .string("A, B")])]), "Evacuation order in effect for Zones A, B.")
        XCTAssertEqual(Emergency.headline([row(["kind": .string("weather"), "event": .string("Tornado Watch")])]), "1 weather advisory or watch in effect.")
    }

    func testSortedPutsTheMostSeriousFirst() {
        let a = Row(id: 0, values: ["severity": .string("minor"), "issued": .string("2026-10-27T10:00")])
        let b = Row(id: 1, values: ["severity": .string("extreme"), "issued": .string("2026-10-26T10:00")])
        XCTAssertEqual(Emergency.sorted([a, b]).map(\.id), [1, 0])
    }

    func testZoneAnswer() throws {
        let json = #"{"found":true,"zone":"D","address":{"address":"825 OHIO AVE","community":"LYNN HAVEN"},"point":{"lat":30.24,"lng":-85.64},"#
            + #""what_to_do":"You're in evacuation Zone D.","orders_now":[{"title":"Order for Zone A","includes_you":false}],"#
            + #""nearest_shelters":[{"name":"Deane Bozeman","miles":4.2}]}"#
        let z = try Emergency.parseZone(Data(json.utf8))
        XCTAssertEqual(z.zone, "D")
        XCTAssertEqual(z.address, "825 OHIO AVE, LYNN HAVEN")
        XCTAssertEqual(z.orders.first?.includesYou, false)
        XCTAssertEqual(z.nearestShelters.count, 1)
        XCTAssertEqual(z.lat, 30.24)
        XCTAssertTrue(Emergency.zoneURL(address: "825 Ohio Ave").absoluteString.hasSuffix("evacuation-zone?address=825%20Ohio%20Ave"))
    }

    func testRebuildMoneyAddsUpLikeTheSite() throws {
        let rows = try load("rebuild-money.json")
        let all = Emergency.rebuild(rows)
        XCTAssertFalse(all.isEmpty)
        XCTAssertEqual(all.last?.zip, "other", "other ZIP codes go last")
        let total = rows.compactMap { $0.number("amount_paid") }.reduce(0, +)
        XCTAssertEqual(all.map(\.total).reduce(0, +), total, accuracy: 1)
        let michael = Emergency.rebuild(rows, storm: .michael)
        let byZip = Dictionary(uniqueKeysWithValues: all.map { ($0.zip, $0.total) })
        XCTAssertTrue(michael.allSatisfy { m in m.total <= (byZip[m.zip] ?? 0) + 0.01 })
        XCTAssertGreaterThan(michael.first?.total ?? 0, 1_000_000)
    }

    func testPrepTopicsKeepTheSiteOrder() throws {
        let topics = Emergency.prepTopics(try load("hurricane-prep.json"))
        XCTAssertEqual(topics.first?.topic, "Before the season")
        XCTAssertTrue(topics.contains { $0.topic == "Generator safety" })
        XCTAssertTrue(topics.allSatisfy { !$0.rows.isEmpty })
    }

    func testSheltersAreGroupedByType() throws {
        let groups = Emergency.sheltersByType(try load("emergency-shelters.json"))
        XCTAssertFalse(groups.isEmpty)
        XCTAssertEqual(groups.map(\.rows.count).reduce(0, +), try load("emergency-shelters.json").count)
    }

    func testPushBodyHasNoAddress() throws {
        let d = Emergency.pushBody(token: "ab", platform: "ios", topics: ["water", "agenda"], govs: ["pcb"], lat: 30.1, lng: -85.6, radius: 1, appVersion: "1.0")
        let o = try JSONSerialization.jsonObject(with: d) as! [String: Any]
        XCTAssertEqual(o["topics"] as? [String], ["agenda", "water"])
        XCTAssertEqual(o["lat"] as? Double, 30.1)
        XCTAssertNil(o["address"])
        XCTAssertEqual(Emergency.hexToken(Data([0x0a, 0xff])), "0aff")
    }
}
