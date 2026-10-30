package me.baycounty.kit

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Test
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue

/** The maps government staff draw on alerts (site/area_map.js): pins with a circle, street lines and areas. */
class AlertAreaTest {
    private val drawn = """{"type":"FeatureCollection","features":[""" +
        """{"type":"Feature","properties":{"radius_m":250},"geometry":{"type":"Point","coordinates":[-85.65,30.24]}},""" +
        """{"type":"Feature","properties":{},"geometry":{"type":"LineString","coordinates":[[-85.66,30.25],[-85.64,30.25]]}},""" +
        """{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[-85.7,30.2],[-85.6,30.2],[-85.6,30.3],[-85.7,30.2]]]}}]}"""

    @Test fun parsesPinsLinesAndAreas() {
        val a = AlertArea.parse(drawn)!!
        assertEquals(3, a.shapes.size)
        assertEquals(AlertArea.Shape.Pin(AlertArea.Coord(30.24, -85.65), 250.0), a.shapes[0])
        assertEquals(2, (a.shapes[1] as AlertArea.Shape.Line).coords.size)
        assertEquals(4, (a.shapes[2] as AlertArea.Shape.Area).rings.first().size)
        val b = a.bounds!!
        assertEquals(30.2, b.south, 1e-9); assertEquals(30.3, b.north, 1e-9); assertEquals(-85.7, b.west, 1e-9)
    }

    @Test fun nothingToDraw() {
        assertNull(AlertArea.parse(null)); assertNull(AlertArea.parse("")); assertNull(AlertArea.parse("not json"))
        assertNull(AlertArea.parse("""{"type":"FeatureCollection","features":[]}"""))
    }

    @Test fun firstMappedNotice() {
        val plain = Row(0, mapOf("title" to JsonPrimitive("Flood Advisory")))
        val mapped = Row(1, mapOf("title" to JsonPrimitive("Boil water"), "geometry" to JsonPrimitive(drawn)))
        assertEquals("Boil water", AlertArea.firstMapped(listOf(plain, mapped))?.first?.string("title"))
        assertTrue(AlertArea.firstMapped(listOf(plain)) == null)
    }

    @Test fun pinsFromTheStaffApp() {
        assertNull(AlertArea.pinsGeoJSON(emptyList(), 250.0))
        val g = AlertArea.pinsGeoJSON(listOf(AlertArea.Coord(30.24, -85.65)), 250.0)
        assertEquals(listOf(AlertArea.Shape.Pin(AlertArea.Coord(30.24, -85.65), 250.0)), AlertArea.parse(g)?.shapes)
        assertEquals(listOf(AlertArea.Shape.Pin(AlertArea.Coord(30.24, -85.65), null)), AlertArea.parse(AlertArea.pinsGeoJSON(listOf(AlertArea.Coord(30.24, -85.65)), null))?.shapes)
    }
}
