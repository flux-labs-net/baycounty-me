package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Test

class PlanningBoardsTest {
    private fun rows(json: String) = Row.decodeList(json)

    @Test
    fun membersInOrderWithLines() {
        val ms = rows("""[{"board_id":"mb-planning","name":"Jeff Bacon","role":"Member","seat":"Post 4","term_end":"2028-01-08","sort_order":2},
            {"board_id":"mb-planning","name":"Jack Kerigan","role":"Chair","seat":"Post 3","term_end":"2027-01-08","sort_order":1},
            {"board_id":"pc-planning","name":"Aaron Rich","role":"Member","sort_order":2}]""")
        val mb = PlanningBoards.members(ms, "mb-planning")
        assertEquals(listOf("Jack Kerigan", "Jeff Bacon"), mb.map { it.string("name") })
        assertEquals("Chair · Post 3 · term ends Jan 8, 2027", PlanningBoards.memberLine(mb[0]))
        assertEquals("Member", PlanningBoards.memberLine(PlanningBoards.members(ms, "pc-planning")[0]))
    }

    @Test
    fun meetingLinesAndSummary() {
        assertEquals("Mon, Nov 9, 2026 at 4 PM", PlanningBoards.meetingLine("2026-11-09T16:00:00-06:00"))
        assertEquals("Tue, Nov 17, 2026 at 1:30 PM", PlanningBoards.meetingLine("2026-11-17T13:30:00-06:00"))
        assertEquals("Tue, Nov 3, 2026", PlanningBoards.meetingLine("2026-11-03"))
        val bs = rows("""[{"gov_id":"lh","members_listed":5},{"gov_id":"lh","members_listed":4},{"gov_id":"pc","members_listed":5}]""")
        assertEquals("9 members listed", PlanningBoards.summary(PlanningBoards.boards(bs, "lh")))
        assertEquals("Members not published online", PlanningBoards.summary(rows("""[{"gov_id":"county","members_listed":0}]""")))
    }
}
