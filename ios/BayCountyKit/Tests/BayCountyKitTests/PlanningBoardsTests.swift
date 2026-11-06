import XCTest
@testable import BayCountyKit

final class PlanningBoardsTests: XCTestCase {
    private func rows(_ json: String) throws -> [Row] { try Row.decodeList(Data(json.utf8)) }

    func testMembersInOrderWithLines() throws {
        let ms = try rows("""
        [{"board_id":"mb-planning","name":"Jeff Bacon","role":"Member","seat":"Post 4","term_end":"2028-01-08","sort_order":2},
         {"board_id":"mb-planning","name":"Jack Kerigan","role":"Chair","seat":"Post 3","term_end":"2027-01-08","sort_order":1},
         {"board_id":"pc-planning","name":"Aaron Rich","role":"Member","sort_order":2}]
        """)
        let mb = PlanningBoards.members(ms, board: "mb-planning")
        XCTAssertEqual(mb.map { $0.string("name") }, ["Jack Kerigan", "Jeff Bacon"])
        XCTAssertEqual(PlanningBoards.memberLine(mb[0]), "Chair · Post 3 · term ends Jan 8, 2027")
        XCTAssertEqual(PlanningBoards.memberLine(PlanningBoards.members(ms, board: "pc-planning")[0]), "Member")
    }

    func testMeetingLinesAndSummary() throws {
        XCTAssertEqual(PlanningBoards.meetingLine("2026-11-09T16:00:00-06:00"), "Mon, Nov 9, 2026 at 4 PM")
        XCTAssertEqual(PlanningBoards.meetingLine("2026-11-17T13:30:00-06:00"), "Tue, Nov 17, 2026 at 1:30 PM")
        XCTAssertEqual(PlanningBoards.meetingLine("2026-11-03"), "Tue, Nov 3, 2026")
        let bs = try rows(#"[{"gov_id":"lh","members_listed":5},{"gov_id":"lh","members_listed":4},{"gov_id":"pc","members_listed":5}]"#)
        XCTAssertEqual(PlanningBoards.summary(PlanningBoards.boards(bs, gov: "lh")), "9 members listed")
        XCTAssertEqual(PlanningBoards.summary(try rows(#"[{"gov_id":"county","members_listed":0}]"#)), "Members not published online")
    }
}
