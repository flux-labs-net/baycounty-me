package me.baycounty.kit

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The Home tab's tiles: owners lead with the tax bill, renters with utilities, everyone else with setup.
 *  Same cases as the Swift HomeTilesTests. */
class HomeTilesTest {
    private fun row(vararg kv: Pair<String, Any>) = Row(0, kv.associate { (k, v) ->
        k to when (v) { is Boolean -> JsonPrimitive(v); is Number -> JsonPrimitive(v); else -> JsonPrimitive(v.toString()) } as JsonElement
    })
    private fun at(m: Int, d: Int, h: Int) = java.time.ZonedDateTime.of(2026, m, d, h, 0, 0, 0, java.time.ZoneId.of("America/Chicago")).toInstant()
    private val home = UtilityLookup.decode(java.io.File(Repo.fixtures, "utilities-lynn-haven.json").readText())   // garbage on Friday

    @Test fun leadTileFollowsOwnOrRent() {
        val wed = at(10, 28, 8)
        val own = HomeTiles.tiles(HomeTiles.Tenure.OWN, true, home, 3284.6, emptyList(), emptyList(), null, wed)
        assertEquals("tax", own.first().id)
        assertEquals("$3,285", own.first().value)
        assertEquals("a year · $250K home, homestead", own.first().detail)
        assertTrue(own.first().featured)
        val rent = HomeTiles.tiles(HomeTiles.Tenure.RENT, true, home, 3284.6, emptyList(), emptyList(), null, wed)
        assertEquals("utilities", rent.first().id)
        assertFalse(rent.any { it.id == "tax" })
        val unset = HomeTiles.tiles(HomeTiles.Tenure.UNSET, false, null, null, emptyList(), emptyList(), null, wed)
        assertEquals(listOf("setup", "beach", "meeting", "reps", "schools"), unset.map { it.id })
        assertEquals("Public schools", unset.last().value)
    }

    @Test fun trashTileOnlyAroundPickupDay() {
        fun tiles(i: java.time.Instant) = HomeTiles.tiles(HomeTiles.Tenure.OWN, true, home, null, emptyList(), emptyList(), null, i)
        val fri = tiles(at(10, 30, 8))
        assertEquals(listOf("tax", "trash", "beach", "meeting", "reps", "schools"), fri.map { it.id })
        assertEquals("Today", fri[1].value)
        assertEquals("Tomorrow", tiles(at(10, 29, 17))[1].value)
        assertFalse(tiles(at(10, 28, 8)).any { it.id == "trash" })
    }

    @Test fun electionTileInTheWeeksBefore() {
        fun t(i: java.time.Instant) = HomeTiles.tiles(HomeTiles.Tenure.RENT, false, null, null, emptyList(), emptyList(), "2026-11-03", i)
        assertEquals("Tue, Nov 3", t(at(10, 30, 9)).first { it.id == "election" }.value)
        assertEquals("Today", t(at(11, 3, 9)).first { it.id == "election" }.value)
        assertNull(t(at(11, 4, 9)).firstOrNull { it.id == "election" })
        assertNull(t(at(9, 1, 9)).firstOrNull { it.id == "election" })
    }

    @Test fun beachAndMeetingTiles() {
        val beach = listOf(row("kind" to "forecast", "sort_order" to 0, "flag_color" to "Yellow", "rip_current_risk" to "Moderate"))
        val m = Meeting(row("id" to "m1", "board" to "mb-council", "start" to "2026-11-05T18:00:00-06:00"))
        val tiles = HomeTiles.tiles(HomeTiles.Tenure.OWN, false, null, null, beach, listOf(m), null, at(10, 30, 9))
        assertEquals("Yellow flag", tiles.first { it.id == "beach" }.value)
        assertEquals("Moderate rip current risk", tiles.first { it.id == "beach" }.detail)
        assertEquals("Thu, Nov 5", tiles.first { it.id == "meeting" }.value)
        assertEquals("Estimate", tiles.first { it.id == "tax" }.value)
    }

    @Test fun alertLeadsWithTheMostUrgentKind() {
        fun n(k: String, s: String) = row("kind" to k, "status" to s)
        val a = HomeTiles.alert(listOf(n("road", "active"), n("boil-water", "active"), n("boil-water", "active"), n("weather", "ended")))
        assertEquals("2 boil-water notices in effect", a?.title)
        assertEquals("1 more active. See the map and what to do.", a?.detail)
        assertEquals("1 notice in effect", HomeTiles.alert(listOf(n("shelter", "active")))?.title)
        assertNull(HomeTiles.alert(listOf(n("road", "ended"))))
    }

    @Test fun eyebrow() {
        assertEquals("Your home · Panama City · Renting", HomeTiles.eyebrow("Panama City", HomeTiles.Tenure.RENT))
        assertEquals("Your home · Panama City", HomeTiles.eyebrow("Panama City", HomeTiles.Tenure.OWN))
        assertEquals("Bay County", HomeTiles.eyebrow(null, HomeTiles.Tenure.OWN))
    }
}
