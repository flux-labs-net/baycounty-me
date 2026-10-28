package me.baycounty.kit

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MilitaryTest {
    @Test fun basesNewsAndContracts() {
        val bases = Repo.rows("military-installations")
        val news = Repo.rows("military-news")
        val years = Repo.rows("federal-contract-years")
        assertEquals(setOf("tyndall-afb", "nsa-panama-city"), bases.mapNotNull { it.string("installation_id") }.toSet())
        val s = Military.stories(news)
        assertEquals(s.map { it.string("published") }, s.map { it.string("published") }.sortedByDescending { it })
        assertTrue(Military.stories(news, "tyndall-afb").all { it.string("installation_id") == "tyndall-afb" })
        val c = Military.companies(years)
        assertTrue(c.isNotEmpty())
        assertEquals(c.map { it.total }, c.map { it.total }.sortedDescending())
        assertTrue(years.all { (it.number("year") ?: 0.0) >= 2016 })
        assertEquals(Military.total(years), Military.byYear(years).sumOf { it.second + it.third }, 1.0)
    }

    @Test fun dateLabel() {
        assertEquals("Sep 17, 2026", Military.dateLabel("2026-09-17T11:56"))
        assertEquals("", Military.dateLabel(null))
    }
}
