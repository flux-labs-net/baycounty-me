package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VolunteerTest {
    @Test fun needsAndOrgsRead() {
        val needs = Repo.rows("volunteer-needs")
        val orgs = Repo.rows("volunteer-orgs")
        assertTrue("needs on file", needs.isNotEmpty())
        assertTrue("orgs on file", orgs.size > 20)
        assertTrue(needs.all { it.string("cause") in Volunteer.causes })
        assertTrue(orgs.all { it.string("cause") in Volunteer.causes })
        val open = Volunteer.open(needs, "2000-01-01")
        val dated = open.takeWhile { it.string("starts") != null }.map { it.string("starts")!! }
        assertEquals(dated, dated.sorted())
        val ranked = Volunteer.orgs(orgs)
        assertTrue((ranked.first().number("open_needs") ?: 0.0) >= (ranked.last().number("open_needs") ?: 0.0))
        val c = Volunteer.causesIn(needs, orgs)
        assertEquals(c, Volunteer.causes.filter { it in c })
    }

    @Test fun labels() {
        val r = Row.decodeList("""[{"starts":"2026-12-03","ends":"2026-12-03","schedule":"One day"},{"schedule":"Ongoing","remote":true},{"schedule":"Shifts"}]""")
        assertEquals("Thu, Dec 3", Volunteer.whenLabel(r[0]))
        assertEquals("Ongoing", Volunteer.whenLabel(r[1]))
        assertEquals("Remote or from home", Volunteer.whereLabel(r[1]))
        assertEquals("Multiple shifts", Volunteer.whenLabel(r[2]))
    }
}
