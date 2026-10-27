package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ChambersTest {
    @Test fun boardsAndEventsRead() {
        val chambers = Repo.rows("chambers")
        val leaders = Repo.rows("chamber-leaders")
        val events = Repo.rows("chamber-events")
        assertEquals(2, chambers.size)
        for (c in chambers) {
            val id = c.string("chamber_id")!!
            assertTrue("$id has a board", Chambers.boardSeats(leaders, id) > 5)
            assertEquals("Executive committee comes first", "Executive committee", Chambers.leaders(leaders, id).first().first)
            assertTrue("$id has programs", Chambers.programs(events, id).isNotEmpty())
        }
        val past = Chambers.pastChairs(leaders, "bay-chamber")
        assertTrue(past.all { (it.number("year") ?: 0.0) >= 2016 })
        val up = Chambers.upcoming(events, "2000-01-01")
        assertEquals(up.map { it.string("starts") }, up.map { it.string("starts") }.sortedBy { it })
        assertTrue(up.none { it.string("kind") == "program" })
    }

    @Test fun whenLabel() {
        val r = Row.decodeList("""[{"starts":"2026-10-27T08:00:00","ends":"2026-10-27T09:30:00"}]""")[0]
        assertEquals("Tue, Oct 27 · 8 a.m.", Chambers.whenLabel(r))
        val d = Row.decodeList("""[{"starts":"2026-11-06T00:00:00","ends":"2026-11-08T00:00:00","all_day":true}]""")[0]
        assertEquals("Nov 6 to Nov 8", Chambers.whenLabel(d))
    }
}

class EventsTest {
    private fun row(json: String) = Row.decodeList("[$json]")[0]

    @Test fun upcomingStartsAtTodayAndSorts() {
        val rows = Repo.rows(Events.DATASET)
        val up = Events.upcoming(rows, "2000-01-01")
        assertEquals(rows.size, up.size)
        assertEquals(up.map { it.string("starts") }, up.map { it.string("starts") }.sortedBy { it })
        assertTrue(Events.towns(rows).isNotEmpty())
    }

    @Test fun featuredSkipsMeetingsAndRepeats() {
        val rows = listOf(
            row("""{"title":"Fair","starts":"2026-11-02T10:00:00","category":"Community","recurring":false}"""),
            row("""{"title":"Commission Meeting","starts":"2026-11-02T17:00:00","category":"Public meeting","recurring":false}"""),
            row("""{"title":"Story Time","starts":"2026-11-03T10:00:00","category":"Library","recurring":true}"""),
        )
        assertEquals(listOf("Fair"), Events.featured(rows, "2026-11-01", "2026-11-30").map { it.string("title") })
    }

    @Test fun labels() {
        assertEquals("Today", Events.dayLabel("2026-10-27", "2026-10-27"))
        assertEquals("Tomorrow", Events.dayLabel("2026-10-28", "2026-10-27"))
        assertEquals("Thursday, Oct 29", Events.dayLabel("2026-10-29", "2026-10-27"))
        assertEquals("5:30 p.m.", Events.time(row("""{"starts":"2026-10-29T17:30:00"}""")))
        assertEquals("All day", Events.time(row("""{"starts":"2026-10-29T00:00:00"}""")))
    }
}
