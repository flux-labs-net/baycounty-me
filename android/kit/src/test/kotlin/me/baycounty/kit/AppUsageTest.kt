package me.baycounty.kit

import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate

class AppUsageTest {
    private class MapStore : AppUsage.Store {
        val m = mutableMapOf<String, String>()
        override fun getString(key: String) = m[key]
        override fun putString(key: String, value: String?) { if (value == null) m.remove(key) else m[key] = value }
    }

    @Test fun firstCheckInIsNewAndCarriesCounts() {
        val u = AppUsage(MapStore(), "1.4 (112)")
        u.opened(); u.opened()
        u.viewed("Restaurants"); u.viewed("restaurants"); u.viewed("dataset/votes"); u.viewed("person/John Smith")
        val b = u.checkIn(LocalDate.of(2026, 10, 29))!!
        assertEquals("android", b["platform"]!!.jsonPrimitive.content)
        assertEquals("1.4 (112)", b["version"]!!.jsonPrimitive.content)
        assertEquals(true, b["new"]!!.jsonPrimitive.boolean)
        assertEquals(true, b["month"]!!.jsonPrimitive.boolean)
        assertEquals(true, b["week"]!!.jsonPrimitive.boolean)
        assertEquals(2, b["opens"]!!.jsonPrimitive.int)
        assertEquals(mapOf("restaurants" to 2, "dataset/votes" to 1), b["screens"]!!.jsonObject.mapValues { it.value.jsonPrimitive.int })
        assertEquals(7, b.size)
    }

    @Test fun oncePerDayThenWeekAndMonthFlags() {
        val u = AppUsage(MapStore(), "1")
        u.sent(LocalDate.of(2026, 10, 27))  // a Tuesday
        assertNull(u.checkIn(LocalDate.of(2026, 10, 27)))
        val thu = u.checkIn(LocalDate.of(2026, 10, 29))!!
        assertEquals(false, thu["new"]!!.jsonPrimitive.boolean)
        assertEquals(false, thu["week"]!!.jsonPrimitive.boolean)
        assertEquals(false, thu["month"]!!.jsonPrimitive.boolean)
        assertEquals(1, thu["opens"]!!.jsonPrimitive.int)
        u.sent(LocalDate.of(2026, 10, 29))
        val nov = u.checkIn(LocalDate.of(2026, 11, 2))!!  // next Monday, next month
        assertEquals(true, nov["week"]!!.jsonPrimitive.boolean)
        assertEquals(true, nov["month"]!!.jsonPrimitive.boolean)
    }

    @Test fun turnedOffCountsAndSendsNothing() {
        val s = MapStore()
        val u = AppUsage(s, "1")
        u.viewed("today")
        u.enabled = false
        u.opened(); u.viewed("money")
        assertNull(u.checkIn(LocalDate.of(2026, 10, 29)))
        assertNull(s.m["usage.screens"])
        u.enabled = true
        assertNotNull(u.checkIn(LocalDate.of(2026, 10, 29)))
    }

    @Test fun siteLinksAreTagged() {
        assertEquals("https://baycounty.me/parks?utm_source=android-app&utm_medium=app", AppLinks.tagged("https://baycounty.me/parks"))
        assertEquals("https://baycounty.me/about?utm_source=android-app&utm_medium=app#contact", AppLinks.tagged("https://baycounty.me/about#contact"))
        assertEquals("https://baycounty.me/x?a=1&utm_source=android-app&utm_medium=app", AppLinks.tagged("https://baycounty.me/x?a=1"))
        assertEquals("https://baycounty.me/x?utm_source=email", AppLinks.tagged("https://baycounty.me/x?utm_source=email"))
        assertEquals("https://fluxlabs.net/", AppLinks.tagged("https://fluxlabs.net/"))
    }
}
