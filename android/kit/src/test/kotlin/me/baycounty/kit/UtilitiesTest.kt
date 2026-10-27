package me.baycounty.kit

import java.io.File
import java.time.LocalDate
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** The /api/v1/utilities answer decodes, and pickup-day math matches the site's page script. */
class UtilitiesTest {
    private val lookup = UtilityLookup.decode(File(Repo.fixtures, "utilities-lynn-haven.json").readText())

    @Test fun decodesTheApiAnswer() {
        assertEquals("lh", lookup.area)
        assertEquals("Lynn Haven", lookup.areaName)
        val garbage = lookup.pickup.first { it.service == "garbage" }
        assertEquals("Friday", garbage.days)
        assertEquals("ROUTE-E", garbage.zoneText)
        assertNotNull(lookup.provider(garbage)?.phone)
        assertNotNull(lookup.typicalBill)
        assertTrue(lookup.otherServices.none { s -> lookup.pickup.any { it.service == s.service } })
        assertTrue(lookup.otherServices.any { it.service == "water" })
    }

    @Test fun zoneTextOnlyWhenItAddsSomething() {
        val p = UtilityLookup.Pickup("garbage", "Garbage", "City", zone = "15", zoneLabel = "route", days = "Monday, Thursday")
        assertEquals("route 15", p.zoneText)
        assertEquals(null, p.copy(zone = "Friday", days = "Friday").zoneText)
    }

    @Test fun nextPickupDay() {
        val tue = LocalDate.of(2026, 10, 27)
        assertEquals(LocalDate.of(2026, 10, 29), PickupDays.next("Monday, Thursday", tue))
        assertEquals(tue, PickupDays.next("Tuesday", tue))
        assertEquals(LocalDate.of(2026, 11, 2), PickupDays.next("MONDAY", tue) ?: PickupDays.next("Monday", tue))
        assertEquals(null, PickupDays.next(null, tue))
    }
}
