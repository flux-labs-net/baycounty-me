package me.baycounty.kit

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RestaurantsTest {
    @Test fun listLatestFirstAndLastInspectionIsNewest() {
        val r = Repo.rows("restaurants")
        val i = Repo.rows("restaurant-inspections")
        val list = Restaurants.list(r, today = "2026-10-28")
        assertTrue(list.isNotEmpty())
        assertTrue(list.all { it.bool("licensed_now") == true })
        val dates = list.map { it.string("last_inspection") ?: "" }
        assertEquals(dates.sortedDescending(), dates)
        // the dataset's last_inspection is the newest visit (it once read the oldest)
        val one = list.first { (it.number("inspections") ?: 0.0) > 5 }
        assertEquals(one.string("last_inspection"), Restaurants.inspections(i, one.string("license_number") ?: "").first().string("date"))
        assertEquals(6, Restaurants.strip(one.string("recent_results")).size)
        assertTrue(Restaurants.list(r, show = Restaurants.Show.GONE, today = "2026-10-28").all { it.bool("licensed_now") == false })
        assertTrue(Restaurants.list(r, show = Restaurants.Show.FOLLOW, today = "2026-10-28").all { it.string("last_result_level") in setOf("warning", "fine", "closed") })
        assertFalse(Restaurants.cities(r).contains("Panama City Bch"))
    }

    @Test fun wordsAndStrip() {
        assertEquals(listOf("", "", "", "closed", "warning", "ok"), Restaurants.strip("ok warning closed"))
        assertEquals("Closed by the state", Restaurants.shortResult("Ordered closed (emergency order)"))
        assertEquals(Restaurants.Tone.BAD, Restaurants.tone("fine"))
        assertEquals("Oct 27, 2026", Restaurants.dateLabel("2026-10-27"))
        assertEquals("2025-10-28", Restaurants.yearAgo("2026-10-28"))
        val row = Row(0, mapOf("business_name" to JsonPrimitive("Red Star"), "last_inspection" to JsonPrimitive("2026-10-27"),
            "last_result" to JsonPrimitive("Met inspection standards"), "closures" to JsonPrimitive(2), "last_closure" to JsonPrimitive("2026-08-26"),
            "inspections" to JsonPrimitive(27)))
        assertEquals("Last inspected Oct 27, 2026: met inspection standards. The state has closed it twice since 2016, most recently Aug 26, 2026. 27 inspections on file.",
            Restaurants.summary(row))
        assertEquals("/api/v1/datasets/restaurant-inspections?license_number=1305433&sort=-date&limit=1000", Restaurants.inspectionsPath("1305433"))
    }

    @Test fun decodesApiAndDownloadShapes() {
        assertEquals("1", Row.decodeRows("""{"data":[{"license_number":"1"}],"meta":{"total":1}}""".toByteArray()).first().string("license_number"))
        assertEquals("1", Row.decodeRows("""[{"license_number":"1"}]""".toByteArray()).first().string("license_number"))
    }
}
