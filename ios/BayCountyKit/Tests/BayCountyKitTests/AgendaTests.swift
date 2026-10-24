import XCTest
@testable import BayCountyKit

/// The Today tab's meeting agenda (amounts, kinds, short titles) and the Amendment 3 reminder.
final class AgendaTests: XCTestCase {
    func meeting(_ json: String) throws -> Meeting {
        Meeting(row: try Row.decodeList(Data(json.utf8))[0])
    }

    func testAgendaJoinsAmountsAndDropsHeadings() throws {
        let m = try meeting(#"""
        [{"board":"pc","title":"City Commission","start":"2026-10-27T16:30:00-05:00",
          "items":[{"title":"Consideration to purchase a Kaiser S8 Walking Telescopic Excavator for a cost of $693,834.87.","amount":"$693,834.87"},
                   {"title":"Consideration of approval of eleven firms for Bid PC25-052.","amount":null}],
          "agenda_items":["Agenda - 10/27/2026 AGENDA CITY COMMISSION","Opening Prayer with Rev. Matt Thompson, Lead Pastor.","Consent Agenda",
                          "Consideration to purchase a Kaiser S8 Walking Telescopic Excavator for a cost of $693,834.87.",
                          "Second and final of two public hearings on Ordinance 3315, an ordinance amending sec. 104-39.B.",
                          "Consideration and approval of a Right-of-Way Use Agreement with the Port Authority."]}]
        """#)
        let a = m.agenda
        XCTAssertEqual(a.count, 3, a.map(\.title).joined(separator: " | "))
        XCTAssertEqual(a[0].amount ?? 0, 693_834.87, accuracy: 0.01)
        XCTAssertEqual(a[0].kind, .spending)
        XCTAssertEqual(a[1].kind, .hearing)
        XCTAssertEqual(a[2].kind, .other)
        XCTAssertEqual(a[2].shortTitle, "A Right-of-Way Use Agreement with the Port Authority")
        XCTAssertEqual(m.moneyTotal, 693_834.87, accuracy: 0.01)
    }

    func testAgendaFallsBackToMoneyItems() throws {
        let m = try meeting(#"[{"board":"lh","start":"2026-10-27","items":[{"title":"Award of bid to Mainline Construction in the amount of $6,173,449.43.","amount":"$6,173,449.43"}]}]"#)
        XCTAssertEqual(m.agenda.count, 1)
        XCTAssertEqual(m.agenda[0].shortTitle, "Award of bid to Mainline Construction in the amount of $6,173,449.43")
    }

    func testParseAmount() {
        XCTAssertEqual(AgendaItem.parseAmount("$8,020.66"), 8020.66)
        XCTAssertEqual(AgendaItem.parseAmount("$1.2 million"), 1_200_000)
        XCTAssertNil(AgendaItem.parseAmount("TBD"))
    }

    func testAmendment3ReminderEndsAfterElectionDay() throws {
        let json = #"{"districts":[],"auth":{},"groups":[],"second":0,"govs":[{"n":"A","levy":1,"imp":[1,30]},{"n":"B","levy":1,"imp":[2,13.7]}],"state":[],"vote":"2026-11-03"}"#
        let m = try JSONDecoder().decode(Amendment3Model.self, from: Data(json.utf8))
        XCTAssertEqual(m.localImpact(1), 43.7, accuracy: 0.001)
        XCTAssertTrue(m.isBeforeVote(now: Dates.parse("2026-11-03T20:00:00-06:00")!))
        XCTAssertFalse(m.isBeforeVote(now: Dates.parse("2026-11-04T08:00:00-06:00")!))
    }
}
