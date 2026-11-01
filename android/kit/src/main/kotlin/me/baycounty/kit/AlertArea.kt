package me.baycounty.kit

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.doubleOrNull
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.cos

/** Where an alert or notice applies, as government staff drew it in the /staff workspace (site/area_map.js): pins
 *  (with a circle radius in meters), street or pipe lines, and areas. Stored as a GeoJSON FeatureCollection in the
 *  `geometry` text of a live notice (/api/v1/emergency). Mirrors the Swift `AlertArea`. */
data class AlertArea(val shapes: List<Shape>, val placed: String? = null) {
    data class Coord(val lat: Double, val lng: Double)

    /** The line under the map when it was placed rather than drawn: a road post placed from the streets it names
     *  ("street-names", api/_road_map.js) or FL511's start and end points ("fl511"). null for a staff drawing. */
    val note: String?
        get() = when (placed) {
            "street-names" -> "Placed on the map from the streets the notice names. Check the notice for the exact spot."
            "fl511" -> "Start and end points from FL511."
            else -> null
        }

    sealed interface Shape {
        /** A pin; radius in meters when staff drew a circle around it. */
        data class Pin(val at: Coord, val radius: Double?) : Shape
        data class Line(val coords: List<Coord>) : Shape
        /** An area: the outer ring first, then any holes. */
        data class Area(val rings: List<List<Coord>>) : Shape
    }

    data class Bounds(val south: Double, val west: Double, val north: Double, val east: Double)

    /** Every point the map has to show, circles included (their edge, roughly), for fitting the map around them. */
    val bounds: Bounds?
        get() {
            val pts = mutableListOf<Coord>()
            for (s in shapes) when (s) {
                is Shape.Pin -> {
                    pts += s.at
                    val r = s.radius
                    if (r != null && r > 0) {
                        val dLat = r / 111_320.0
                        val dLng = r / (111_320.0 * cos(s.at.lat * PI / 180))
                        pts += Coord(s.at.lat - dLat, s.at.lng - dLng); pts += Coord(s.at.lat + dLat, s.at.lng + dLng)
                    }
                }
                is Shape.Line -> pts += s.coords
                is Shape.Area -> pts += s.rings.firstOrNull().orEmpty()
            }
            if (pts.isEmpty()) return null
            return Bounds(pts.minOf { it.lat }, pts.minOf { it.lng }, pts.maxOf { it.lat }, pts.maxOf { it.lng })
        }

    companion object {
        /** null when there's no drawing (empty, not GeoJSON, or nothing drawable in it). */
        fun parse(text: String?): AlertArea? {
            if (text.isNullOrBlank()) return null
            val obj = runCatching { Json.parseToJsonElement(text) }.getOrNull() as? JsonObject ?: return null
            if ((obj["type"] as? JsonPrimitive)?.content != "FeatureCollection") return null
            val features = obj["features"] as? JsonArray ?: return null
            // GeoJSON positions are [lng, lat].
            fun coord(v: JsonElement?): Coord? {
                val a = v as? JsonArray ?: return null
                if (a.size < 2) return null
                val lng = (a[0] as? JsonPrimitive)?.doubleOrNull ?: return null
                val lat = (a[1] as? JsonPrimitive)?.doubleOrNull ?: return null
                return if (abs(lat) <= 90 && abs(lng) <= 180) Coord(lat, lng) else null
            }
            fun line(v: JsonElement?): List<Coord> = (v as? JsonArray).orEmpty().mapNotNull(::coord)
            fun rings(v: JsonElement?): List<List<Coord>> = (v as? JsonArray).orEmpty().map(::line).filter { it.size >= 3 }
            val shapes = mutableListOf<Shape>()
            var placed: String? = null
            for (f in features) {
                val fo = f as? JsonObject ?: continue
                val g = fo["geometry"] as? JsonObject ?: continue
                if (placed == null) placed = ((fo["properties"] as? JsonObject)?.get("placed") as? JsonPrimitive)?.content
                val c = g["coordinates"]
                when ((g["type"] as? JsonPrimitive)?.content) {
                    "Point" -> coord(c)?.let { p ->
                        val r = ((fo["properties"] as? JsonObject)?.get("radius_m") as? JsonPrimitive)?.doubleOrNull
                        shapes += Shape.Pin(p, r?.takeIf { it > 0 })
                    }
                    "LineString" -> line(c).takeIf { it.size >= 2 }?.let { shapes += Shape.Line(it) }
                    "MultiLineString" -> (c as? JsonArray).orEmpty().forEach { part -> line(part).takeIf { it.size >= 2 }?.let { shapes += Shape.Line(it) } }
                    "Polygon" -> rings(c).takeIf { it.isNotEmpty() }?.let { shapes += Shape.Area(it) }
                    "MultiPolygon" -> (c as? JsonArray).orEmpty().forEach { poly -> rings(poly).takeIf { it.isNotEmpty() }?.let { shapes += Shape.Area(it) } }
                }
            }
            return if (shapes.isEmpty()) null else AlertArea(shapes, placed)
        }

        /** Pins dropped in the staff app, each with the same circle (meters; null or 0 = no circle), as the GeoJSON
         *  FeatureCollection the workspace stores (api/_gov.js areaShape). null when there are no pins. */
        fun pinsGeoJSON(pins: List<Coord>, radius: Double?): String? {
            if (pins.isEmpty()) return null
            val r = radius?.takeIf { it > 0 }
            val f = pins.joinToString(",") { p ->
                val props = if (r != null) "{\"radius_m\":${r.toInt()}}" else "{}"
                "{\"type\":\"Feature\",\"properties\":$props,\"geometry\":{\"type\":\"Point\",\"coordinates\":[${"%.6f".format(java.util.Locale.US, p.lng)},${"%.6f".format(java.util.Locale.US, p.lat)}]}}"
            }
            return "{\"type\":\"FeatureCollection\",\"features\":[$f]}"
        }

        /** The first live notice with a drawn map, for the map under the home screen's alert strip. */
        fun firstMapped(notices: List<Row>): Pair<Row, AlertArea>? =
            notices.firstNotNullOfOrNull { n -> parse(n.string("geometry"))?.let { n to it } }
    }
}
