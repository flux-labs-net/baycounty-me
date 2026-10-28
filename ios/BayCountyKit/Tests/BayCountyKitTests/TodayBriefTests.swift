import XCTest
@testable import BayCountyKit

/// The Today tab's greeting, "right now" cards and weekend picks. Wording matches site/home.py `_today`.
final class TodayBriefTests: XCTestCase {
    private func row(_ v: [String: JSONValue]) -> Row { Row(id: 0, values: v) }

    func testGreeting() {
        XCTAssertEqual(TodayBrief.greeting(hour: 7), "Good morning")
        XCTAssertEqual(TodayBrief.greeting(hour: 13), "Good afternoon")
        XCTAssertEqual(TodayBrief.greeting(hour: 20), "Good evening")
        XCTAssertEqual(TodayBrief.dateLine("2026-10-28"), "Wednesday, Oct 28")
    }

    func testBeachCard() {
        let rows = [row(["kind": .string("forecast"), "sort_order": .number(0), "flag_color": .string("Yellow"), "rip_current_risk": .string("Moderate")])]
        let c = TodayBrief.beachCard(rows)
        XCTAssertEqual(c.title, "Yellow beach flag")
        XCTAssertEqual(c.detail, "Moderate rip current risk")
        XCTAssertEqual(TodayBrief.beachCard([]).title, "Beach flags")
    }

    func testNoticesCardCountsActiveByKind() {
        let n = { (k: String, s: String) in self.row(["kind": .string(k), "status": .string(s)]) }
        let c = TodayBrief.noticesCard([n("boil-water", "active"), n("utility", "active"), n("boil-water", "active"),
                                        n("boil-water", "active"), n("utility", "active"), n("shelter", "active"), n("road", "ended")])
        XCTAssertEqual(c.title, "6 active notices")
        XCTAssertEqual(c.detail, "3 boil-water, 2 utility, 1 other")
        XCTAssertEqual(TodayBrief.noticesCard([]).title, "No active alerts")
    }

    func testTrashCard() {
        XCTAssertEqual(TodayBrief.trashCard("Friday").title, "Trash day: Friday")
        XCTAssertEqual(TodayBrief.trashCard(nil).title, "Trash day")
    }

    func testWeekendWindow() {
        // 2026-10-28 is a Wednesday: the coming Friday through Sunday.
        XCTAssertEqual(TodayBrief.weekend(today: "2026-10-28")?.from, "2026-10-30")
        XCTAssertEqual(TodayBrief.weekend(today: "2026-10-28")?.to, "2026-11-01")
        // Saturday: today through Sunday. Sunday: just today.
        XCTAssertEqual(TodayBrief.weekend(today: "2026-10-31")?.from, "2026-10-31")
        XCTAssertEqual(TodayBrief.weekend(today: "2026-10-31")?.to, "2026-11-01")
        XCTAssertEqual(TodayBrief.weekend(today: "2026-11-01")?.to, "2026-11-01")
    }

    func testWeekendEventsSkipsRepeatsAndMeetings() {
        let e = { (t: String, s: String, cat: String, rec: Bool) in
            self.row(["title": .string(t), "starts": .string(s), "category": .string(cat), "recurring": .bool(rec)])
        }
        let rows = [e("Fall Festival", "2026-10-31T08:00:00", "Community", false), e("Story time", "2026-10-31T10:00:00", "Library", true),
                    e("Commission", "2026-10-30T09:00:00", "Public meeting", false), e("ZooBoo", "2026-10-31T00:00:00", "Community", false),
                    e("Next week", "2026-11-05T09:00:00", "Community", false), e("Craft", "2026-10-31T00:00:00", "Library", false)]
        let picks = TodayBrief.weekendEvents(rows, today: "2026-10-28")
        XCTAssertEqual(picks.map { $0.string("title") }, ["ZooBoo", "Craft", "Fall Festival"])
    }
}
