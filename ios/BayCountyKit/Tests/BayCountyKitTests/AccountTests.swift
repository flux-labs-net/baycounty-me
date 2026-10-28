import XCTest
@testable import BayCountyKit

/// The resident account answers decode, and item dates show in Bay County time like the site's My home page.
final class AccountTests: XCTestCase {
    func feed() throws -> NearbyFeed {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "nearby-sample", withExtension: "json", subdirectory: "Fixtures"))
        return try NearbyFeed.decode(Data(contentsOf: url))
    }

    func testDecodesTheNearbyAnswer() throws {
        let f = try feed()
        XCTAssertEqual(f.govId, "lh")
        XCTAssertEqual(f.zone, "D")
        XCTAssertEqual(f.home?.address, "825 Ohio Ave")
        XCTAssertEqual(f.todayCard.trash?.first?.days, "Friday")
        XCTAssertEqual(f.sections.map(\.id), ["alerts", "meetings", "events", "projects", "notices", "food", "business"])
        XCTAssertEqual(f.governments.map(\.govId), ["county", "schools", "lh"])
        XCTAssertFalse(f.sections.first { $0.id == "meetings" }!.items.isEmpty)
    }

    func testDatesWithoutAnOffsetShowAsWritten() throws {
        let w = try XCTUnwrap(NearbyFeed.when("2026-10-29T08:00:00"))
        XCTAssertEqual(w.month, "OCT"); XCTAssertEqual(w.day, "29"); XCTAssertEqual(w.time, "Thu 8 AM")
        // 13:30 UTC is 8:30 AM in Bay County (CDT).
        XCTAssertEqual(NearbyFeed.when("2026-10-29T13:30:00Z")?.time, "Thu 8:30 AM")
        let d = try XCTUnwrap(NearbyFeed.when("2026-11-03"))
        XCTAssertEqual(d.day, "3"); XCTAssertNil(d.time)
        XCTAssertNil(NearbyFeed.when(nil))
    }

    func testItemLinksAndTags() throws {
        let j = #"{"kind":"business","title":"Gulf Coast Bakery LLC","entity_id":"business:L26000012345"}"#
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase
        let item = try d.decode(NearbyFeed.Item.self, from: Data(j.utf8))
        XCTAssertEqual(item.link?.absoluteString, "https://baycounty.me/profile/business/L26000012345")
        let road = try d.decode(NearbyFeed.Item.self, from: Data(#"{"kind":"road","title":"Resurfacing","miles":0.4,"date":"2026-11-01"}"#.utf8))
        XCTAssertTrue(road.leadsWithDistance)
        XCTAssertEqual(road.tag, "Road")
    }

    func testDecodesTheAccount() throws {
        let j = #"""
        {"user":{"email":"a@example.com","first_name":"Sam"},
         "home":{"label":"Home","address":"825 Ohio Ave","city":"Lynn Haven","zip":"32444","lat":30.24,"lon":-85.65,"gov_id":"lh","zone":"D"},
         "prefs":{"weekly_email":true,"alert_email":["evacuation","water"],"push_topics":["weather"],"radius_mi":1,"topics":["meetings","events"]},
         "devices":0,"choices":{"topics":{"meetings":"Public meetings"},"radius_mi":[0.25,0.5,1,2,5],"push_topics":{"weather":"Weather"},"alert_email":{"water":"Boil water"}},
         "token":"abc"}
        """#
        let me = try AccountMe.decode(Data(j.utf8))
        XCTAssertEqual(me.user.firstName, "Sam")
        XCTAssertEqual(me.home?.subtitle, "Lynn Haven 32444")
        XCTAssertEqual(me.prefs?.radiusMi, 1)
        XCTAssertEqual(me.token, "abc")
        XCTAssertEqual(AccountMe.radiusLabel(0.5), "Half a mile")
        XCTAssertEqual(AccountMe.radiusLabel(5), "5 miles")
    }

    func testRequestsCarryTheTokenAndAction() throws {
        let r = AccountClient.request(base: URL(string: "https://baycounty.me")!, action: "prefs", token: "t1", body: ["radius_mi": 2])
        XCTAssertEqual(r.url?.absoluteString, "https://baycounty.me/api/account?action=prefs")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Authorization"), "Bearer t1")
        XCTAssertEqual(r.httpMethod, "POST")
        XCTAssertNil(AccountClient.request(action: "me", token: nil, body: nil).value(forHTTPHeaderField: "Authorization"))
    }
}
