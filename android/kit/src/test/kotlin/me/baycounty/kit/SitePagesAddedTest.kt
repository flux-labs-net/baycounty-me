package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.roundToInt

/** The school, public safety and overlap screens against the site's published datasets (iOS: SitePagesAddedTests). */
class SitePagesAddedTest {
    @Test fun schoolGradesScoresSpendingAndHours() {
        val schools = Repo.rows("schools"); val grades = Repo.rows("school-grades"); val state = Repo.rows("school-grade-state")
        val spend = Repo.rows("school-spending"); val bell = Repo.rows("school-bell-times"); val zones = Repo.rows("school-zones")
        val c = SchoolDetails.gradeCounts(schools, grades)!!
        assertEquals(2026, c.year)
        assertTrue(c.a > 10)
        val s = SchoolDetails.scores(grades, state, "03-0491")!!
        assertTrue(s.title.startsWith("Scores behind the 2025-26 grade"))
        assertTrue(s.items.any { it.label == "Graduation rate" })
        assertTrue(s.items.all { it.state != null })
        assertEquals("8:15 a.m. to 3:00 p.m.", SchoolDetails.hours(bell, "03-0491"))
        assertEquals("Elementary (K-5): 7:30 a.m. to 2:00 p.m.; Middle (6-8): 7:30 a.m. to 2:05 p.m.", SchoolDetails.hours(bell, "03-0571"))
        assertEquals("1:50 p.m.", SchoolDetails.time("13:50"))
        assertEquals("12:05 a.m.", SchoolDetails.time("00:05"))
        val r = SchoolDetails.spendingRanking(spend, schools)!!
        assertEquals(2025, r.year)
        assertEquals("St. Andrew School at Oakland Terrace", r.rows.first().name)
        assertEquals(10764.0, r.average, 1.0)
        assertNotNull(SchoolDetails.gradeMix(grades, state, 2026).second)
        val row = schools.first { it.string("school_id") == "03-0491" }
        assertEquals("(850) 767-4400" to "tel:+18507674400", SchoolDetails.phone(row))
        assertTrue(SchoolDetails.mapsURL(row)!!.contains("501%20Mosley%20Dr"))
        assertFalse(SchoolDetails.zones(zones, "High").isEmpty())
        assertTrue(SchoolDetails.zones(zones, "Elementary").all { it.rings.isNotEmpty() && it.rings[0].size > 3 })
    }

    @Test fun publicSafety() {
        val a = Repo.rows("safety-agencies"); val c = Repo.rows("crime-counts"); val s = Repo.rows("police-staffing")
        val t = PublicSafety.totals(a)
        assertEquals(130_393_108.0, t.police, 1.0)
        assertEquals(492, t.officers)
        val h = PublicSafety.headline(c)!!
        assertEquals(2024, h.year); assertEquals(2016, h.firstYear); assertEquals(598, h.violent); assertEquals(-23, h.violentChange)
        val solved = PublicSafety.solved(c, PublicSafety.Offense.VIOLENT)
        assertEquals("Panama City Beach police", solved.first().name)
        assertEquals(75, (solved.first().share * 100).roundToInt())
        val towns = PublicSafety.towns(a)
        assertEquals("county", towns.first().id)
        assertTrue(PublicSafety.townCrime(towns.first { it.id == "cw" }, c).sheriffCovers)
        assertTrue(PublicSafety.trends(c, PublicSafety.Offense.VIOLENT).all { tr -> tr.points.none { it.year == 2021 } })
        assertFalse(PublicSafety.staffingSummary(s).isEmpty())
        assertEquals("$74.4M", PublicSafety.money(74_437_440.0))
    }

    @Test fun overlaps() {
        val all = Overlaps.datasets.associateWith { Repo.rows(it) }
        val h = Overlaps.headline(all)
        assertEquals(318, h.donorVotes); assertEquals(116, h.pairs); assertEquals(68, h.contested); assertEquals(51, h.topWon)
        assertEquals(6, h.emergencyFromDonors); assertEquals(12, h.emergency)
        val cards = Overlaps.cards(all)
        assertEquals(8, cards.size)
        val live = Overlaps.decodeLive("""{"data":{"split_purchases":{"rows":[{"payee":"Acme","payments":2,"threshold":5000,"total":9800,"government":"Lynn Haven"}],"error":null}}}""".toByteArray())
        val line = Overlaps.liveLine("split_purchases", live.getValue("split_purchases").first())
        assertEquals("Acme", line.title)
        assertTrue(line.detail.startsWith("2 payments just under $5,000"))
    }
}
