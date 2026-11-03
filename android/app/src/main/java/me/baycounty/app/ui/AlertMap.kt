package me.baycounty.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import android.graphics.drawable.GradientDrawable
import me.baycounty.kit.AlertArea
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polygon
import org.osmdroid.views.overlay.Polyline

private const val RED = 0xFFD14343.toInt()
private const val RED_FILL = 0x2ED14343

/** The map government staff drew on an alert (where a boil-water notice or a closure applies): circles around pins,
 *  street or pipe lines and areas, in red, fitted to the drawing. Read-only; the iOS AlertMapView. */
@Composable
fun AlertMap(area: AlertArea, modifier: Modifier = Modifier) {
    if (LocalInspectionMode.current) {
        Box(modifier.clip(RoundedCornerShape(12.dp)).background(Brand.sunken), contentAlignment = Alignment.Center) { Text("Map", style = T.caption, color = Brand.secondary) }
        return
    }
    val context = LocalContext.current
    val map = remember(area) {
        Configuration.getInstance().userAgentValue = context.packageName
        MapView(context).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            zoomController.setVisibility(org.osmdroid.views.CustomZoomButtonsController.Visibility.NEVER)
            controller.setZoom(14.0)
            val b = area.bounds
            controller.setCenter(if (b != null) GeoPoint((b.south + b.north) / 2, (b.west + b.east) / 2) else GeoPoint(30.2, -85.66))
            fun gp(c: AlertArea.Coord) = GeoPoint(c.lat, c.lng)
            for (s in area.shapes) when (s) {
                is AlertArea.Shape.Pin -> {
                    s.radius?.let { r ->
                        overlays.add(Polygon(this).apply {
                            points = Polygon.pointsAsCircle(gp(s.at), r)
                            fillPaint.color = RED_FILL; outlinePaint.color = RED; outlinePaint.strokeWidth = 4f
                            setOnClickListener { _, _, _ -> false }
                        })
                    }
                    overlays.add(Marker(this).apply {
                        position = gp(s.at)
                        icon = GradientDrawable().apply { shape = GradientDrawable.OVAL; setSize(34, 34); setColor(RED); setStroke(4, 0xFFFFFFFF.toInt()) }
                        setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                        setOnMarkerClickListener { _, _ -> true }
                    })
                }
                is AlertArea.Shape.Line -> overlays.add(Polyline(this).apply {
                    setPoints(s.coords.map(::gp)); outlinePaint.color = RED; outlinePaint.strokeWidth = 9f
                    setOnClickListener { _, _, _ -> false }
                })
                is AlertArea.Shape.Area -> overlays.add(Polygon(this).apply {
                    points = s.rings.first().map(::gp)
                    if (s.rings.size > 1) holes = s.rings.drop(1).map { r -> r.map(::gp) }
                    fillPaint.color = RED_FILL; outlinePaint.color = RED; outlinePaint.strokeWidth = 4f
                    setOnClickListener { _, _, _ -> false }
                })
            }
            // Fit the drawing once the view has a size (never closer than a few blocks).
            if (b != null) addOnFirstLayoutListener { _, _, _, _, _ ->
                val pad = 0.003
                zoomToBoundingBox(BoundingBox(b.north + pad, b.east + pad, b.south - pad, b.west - pad), false, 24)
            }
        }
    }
    DisposableEffect(map) { map.onResume(); onDispose { map.onPause(); map.onDetach() } }
    androidx.compose.ui.viewinterop.AndroidView({ map }, modifier.clip(RoundedCornerShape(12.dp)).semantics { contentDescription = "Map of where this applies" })
}
