import XCTest
@testable import BayCountyKit

/// The watch apps' brief and complication lines (WatchBrief). Same cases as android/kit WatchBriefTest.kt.
final class WatchBriefTests: XCTestCase {
    private let feedJSON = #"""
    {"headline":"No weather warnings or evacuation orders right now.","checked_at":"2026-10-29T14:00:00Z","counts":{},
     "notices":[
      {"notice_id":"a","kind":"road","gov_id":"pc","title":"Harrison Ave closed","summary":"Closed  between\n4th and 5th.","source":"City of Panama City","severity":"minor","issued":"2026-10-29T14:00:00Z","status":"active"},
      {"notice_id":"b","kind":"boil-water","gov_id":"lh","title":"Boil-water notice on Ohio Ave","summary":"Boil water before drinking.","source":"City of Lynn Haven","severity":"moderate","issued":"2026-10-29T13:00:00Z","status":"active"},
      {"notice_id":"c","kind":"road","gov_id":"pc","title":"Old closure","status":"ended"},
      {"notice_id":"d","kind":"road","gov_id":"pc","title":"Same post again","status":"active","same_as":"a"}
     ],"shelters":[],"zones":[]}
    """#

    private let utilitiesJSON = #"""
    {"data":{"area":"lh","area_name":"Lynn Haven","services":[],"rates":[],"holidays":[],
     "pickup":[{"service":"garbage","service_label":"Garbage","provider":"City of Lynn Haven","days":"Thursday"}]}}
    """#

    private func at(_ m: Int, _ d: Int, _ h: Int) -> Date {
        var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!
        return c.date(from: DateComponents(year: 2026, month: m, day: d, hour: h))!
    }

    private func meeting(_ board: String, _ start: String) -> Meeting {
        Meeting(row: Row(id: 0, values: ["board": .string(board), "gov_id": .string(String(board.prefix { $0 != "-" })), "start": .string(start)]))
    }

    func testAlertsAreActiveOnlyAndMostSeriousFirst() throws {
        let feed = try Emergency.parseFeed(Data(feedJSON.utf8))
        let u = try UtilityLookup.decode(Data(utilitiesJSON.utf8))
        let b = WatchBrief.make(feed: feed, utilities: u, beach: [], meetings: [], now: at(10, 30, 9))
        XCTAssertEqual(b.alerts.map(\.id), ["b", "a"])          // moderate before minor; ended and repeated posts left out
        XCTAssertEqual(b.alertTitle, "2 active alerts")
        XCTAssertEqual(b.alerts[0].label, "Boil-water notice")
        XCTAssertTrue(b.alerts[0].nearHome)                      // Lynn Haven notice, Lynn Haven home
        XCTAssertFalse(b.alerts[1].nearHome)
        XCTAssertEqual(b.alerts[1].summary, "Closed between 4th and 5th.")
        XCTAssertEqual(b.place, "Lynn Haven")
        XCTAssertEqual(b.inline, "2 active alerts")
        XCTAssertEqual(b.circular, "2")
    }

    func testTrashReminderOnlyAroundPickupDay() throws {
        let u = try UtilityLookup.decode(Data(utilitiesJSON.utf8))
        let thursday = WatchBrief.make(feed: nil, utilities: u, beach: [], meetings: [], now: at(10, 29, 8))
        XCTAssertEqual(thursday.trash?.title, "Trash pickup today")
        XCTAssertNil(thursday.nextPickup)
        XCTAssertEqual(thursday.inline, "Trash pickup today")     // the feed didn't load, so the trash line leads
        XCTAssertEqual(thursday.circular, "–")
        XCTAssertEqual(thursday.alertTitle, "Alerts didn't load")
        let friday = WatchBrief.make(feed: nil, utilities: u, beach: [], meetings: [], now: at(10, 30, 8))
        XCTAssertNil(friday.trash)
        XCTAssertEqual(friday.nextPickup, "Next pickup Thursday")
        let wednesdayEvening = WatchBrief.make(feed: nil, utilities: u, beach: [], meetings: [], now: at(11, 4, 18))
        XCTAssertEqual(wednesdayEvening.trash?.title, "Trash pickup tomorrow")
        XCTAssertEqual(wednesdayEvening.rectangularDetail, "Trash pickup tomorrow")
    }

    func testNoHomeIsCountyWide() throws {
        let feed = try Emergency.parseFeed(Data(#"{"headline":"No weather warnings or evacuation orders right now.","notices":[]}"#.utf8))
        let b = WatchBrief.make(feed: feed, utilities: nil, beach: [], meetings: [], now: at(10, 30, 9))
        XCTAssertEqual(b.place, "Bay County")
        XCTAssertFalse(b.hasHome)
        XCTAssertNil(b.trash); XCTAssertNil(b.nextPickup)
        XCTAssertEqual(b.inline, "No active alerts")
        XCTAssertEqual(b.circular, "0")
        XCTAssertEqual(b.rectangularDetail, "Beach flags")
    }

    func testNextMeetingPrefersTheHomeGovernment() throws {
        let u = try UtilityLookup.decode(Data(utilitiesJSON.utf8))
        let ms = [meeting("county-commission", "2026-11-03T09:00:00-06:00"), meeting("lh-commission", "2026-11-10T17:00:00-06:00")]
        XCTAssertTrue(WatchBrief.make(feed: nil, utilities: u, beach: [], meetings: ms, now: at(10, 30, 9)).meeting.title.hasSuffix("Nov 10"))
        XCTAssertTrue(WatchBrief.make(feed: nil, utilities: nil, beach: [], meetings: ms, now: at(10, 30, 9)).meeting.title.hasSuffix("Nov 3"))
    }

    func testHomeMessageRoundTrip() {
        let h = WatchBrief.Home(lat: 30.2449, lon: -85.6483)
        XCTAssertEqual(WatchBrief.Home.from(message: WatchBrief.Home.message(h)), .some(h))
        XCTAssertEqual(WatchBrief.Home.from(message: WatchBrief.Home.message(nil)), .some(nil))
        XCTAssertNil(WatchBrief.Home.from(message: ["other": 1]))
    }
}
