package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SchoolsTest {
    @Test fun schoolsAndCalendarRead() {
        val schools = Repo.rows("schools")
        val open = Schools.open(schools)
        assertTrue("dozens of open schools", open.size > 40)
        assertEquals("elementary schools come first", "Elementary", open.first().string("level"))
        assertTrue("every charter filter row is a charter", Schools.open(schools, Schools.Filter.CHARTER).all { it.bool("charter") == true })
        assertTrue("search finds Bay High", Schools.open(schools, query = "bay high").any { it.string("name") == "Bay High School" })
        assertTrue("closed schools are listed", Schools.closed(schools).isNotEmpty())
        val years = Schools.districtEnrollment(Repo.rows("school-enrollment"))
        assertEquals("2015-16", years.first().first)
        assertTrue(years.all { it.second > 20_000 })
        val cal = Repo.rows("school-calendar")
        assertTrue(Schools.upcoming(cal, "2000-01-01").isNotEmpty())
        assertTrue(Schools.upcoming(cal, "2000-01-01", Schools.Kind.OFF).all { it.string("kind") in setOf("no-school", "break") })
    }

    @Test fun whenLabels() {
        val r = Row.decodeList("""[{"starts":"2026-10-27T15:00","ends":"2026-10-27T17:00","all_day":false},
            {"starts":"2026-10-28","ends":"2026-10-28","all_day":true},{"starts":"2026-11-23","ends":"2026-11-27","all_day":true}]""")
        assertEquals("Tue, Oct 27 · 3 p.m.", Schools.whenLabel(r[0]))
        assertEquals("Wednesday, October 28", Schools.whenLabel(r[1]))
        assertEquals("Mon, Nov 23 to Fri, Nov 27", Schools.whenLabel(r[2]))
    }
}
