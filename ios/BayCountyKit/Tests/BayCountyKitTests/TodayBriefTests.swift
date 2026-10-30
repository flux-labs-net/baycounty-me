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

    /// The trash card shows only on pickup day, or from 4 p.m. the day before. Same cases as the site's BCTrashCard.
    func testTrashCardOnlyAroundPickupDay() {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let at = { (m: Int, d: Int, h: Int) in cal.date(from: DateComponents(year: 2026, month: m, day: d, hour: h))! }
        let holidays = [UtilityLookup.Holiday(provider: nil, holiday: "Thanksgiving Day", whenObserved: "4th Thursday in November", garbage: "Moved to the Saturday after", yardWaste: nil),
                        UtilityLookup.Holiday(provider: nil, holiday: "Memorial Day", whenObserved: "Last Monday in May", garbage: "No pickup", yardWaste: nil),
                        UtilityLookup.Holiday(provider: nil, holiday: "Labor Day", whenObserved: "1st Monday in September", garbage: "Normal", yardWaste: nil),
                        UtilityLookup.Holiday(provider: nil, holiday: "Christmas Day", whenObserved: "December 25", garbage: "No pickup; in 2025 Thursday's route moved to Saturday, December 27", yardWaste: nil),
                        UtilityLookup.Holiday(provider: nil, holiday: "New Year's Day", whenObserved: "January 1", garbage: "No pickup; in 2026 Thursday's route moved to Saturday, January 3", yardWaste: nil)]
        let card = { (m: Int, d: Int, h: Int) in TodayBrief.trashCard(days: "Monday, Thursday", holidays: holidays, now: at(m, d, h)) }
        XCTAssertEqual(card(10, 29, 9)?.title, "Trash pickup today")        // Thursday
        XCTAssertEqual(card(10, 29, 9)?.detail, "At your home")
        XCTAssertNil(card(10, 30, 9))                                       // Friday
        XCTAssertNil(card(11, 1, 14))                                       // Sunday afternoon
        XCTAssertEqual(card(11, 1, 17)?.title, "Trash pickup tomorrow")     // Sunday evening
        XCTAssertEqual(card(11, 1, 17)?.detail, "Put it out tonight")
        XCTAssertEqual(card(11, 26, 8)?.title, "No trash pickup today")     // Thanksgiving
        XCTAssertEqual(card(11, 26, 8)?.detail, "Thanksgiving Day · Moved to the Saturday after")
        XCTAssertEqual(card(11, 25, 18)?.title, "No trash pickup tomorrow")
        XCTAssertEqual(card(5, 25, 8)?.detail, "Memorial Day")              // last Monday in May
        XCTAssertEqual(card(5, 18, 8)?.title, "Trash pickup today")         // not the last Monday
        XCTAssertEqual(card(9, 7, 8)?.title, "Trash pickup today")          // Labor Day pickup is normal
        XCTAssertEqual(TodayBrief.trashCard(days: "Friday", holidays: holidays, now: at(12, 25, 8))?.detail, "Christmas Day")   // the 2025 note is left off
        XCTAssertEqual(TodayBrief.trashCard(days: "Thursday", holidays: holidays, now: cal.date(from: DateComponents(year: 2026, month: 1, day: 1, hour: 8))!)?.detail,
                       "New Year's Day · In 2026 Thursday's route moved to Saturday, January 3")
        XCTAssertNil(TodayBrief.trashCard(days: nil, holidays: [], now: at(10, 29, 9)))
        XCTAssertNil(TodayBrief.trashCard(nil))
    }

    func testCardsLeadWithTrashOnlyOnPickupDay() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "utilities-lynn-haven", withExtension: "json", subdirectory: "Fixtures"))
        let home = try UtilityLookup.decode(Data(contentsOf: url))   // garbage on Friday
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let fri = cal.date(from: DateComponents(year: 2026, month: 10, day: 30, hour: 8))!
        let wed = cal.date(from: DateComponents(year: 2026, month: 10, day: 28, hour: 8))!
        XCTAssertEqual(TodayBrief.cards(beach: [], notices: [], meetings: [], utilities: home, now: fri).map(\.id), ["trash", "beach", "notices", "meeting"])
        XCTAssertEqual(TodayBrief.cards(beach: [], notices: [], meetings: [], utilities: home, now: wed).map(\.id), ["beach", "notices", "meeting"])
        XCTAssertEqual(TodayBrief.cards(beach: [], notices: [], meetings: [], utilities: nil, now: fri).count, 3)
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
