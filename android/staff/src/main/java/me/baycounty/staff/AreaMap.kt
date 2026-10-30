package me.baycounty.staff

import android.graphics.drawable.GradientDrawable
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
import androidx.compose.ui.viewinterop.AndroidView
import me.baycounty.kit.AlertArea
import org.osmdroid.config.Configuration
import org.osmdroid.events.MapEventsReceiver
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.MapEventsOverlay
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polygon
import org.osmdroid.views.overlay.Polyline

private const val RED = 0xFFD14343.toInt()
private const val RED_FILL = 0x2ED14343

/** An alert's map in the staff app. With onTap it's the pin dropper on Send an alert (tap the map to drop a pin, tap a
 *  pin to take it off); without, it shows a saved alert's map read-only. Drawn the same way as the public apps. */
@Composable
fun AreaMap(area: AlertArea?, modifier: Modifier = Modifier, onTap: ((AlertArea.Coord) -> Unit)? = null, onPinTap: ((Int) -> Unit)? = null) {
    if (LocalInspectionMode.current) {
        Box(modifier.clip(RoundedCornerShape(12.dp)).background(Brand.sunken), contentAlignment = Alignment.Center) { Text("Map", style = T.caption, color = Brand.secondary) }
        return
    }
    val context = LocalContext.current
    val map = remember {
        Configuration.getInstance().userAgentValue = context.packageName
        MapView(context).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            zoomController.setVisibility(org.osmdroid.views.CustomZoomButtonsController.Visibility.NEVER)
            val b = area?.bounds
            controller.setZoom(if (b == null) 12.0 else 15.0)
            controller.setCenter(if (b != null) GeoPoint((b.south + b.north) / 2, (b.west + b.east) / 2) else GeoPoint(30.2, -85.66))
            if (b != null && onTap == null) addOnFirstLayoutListener { _, _, _, _, _ ->
                val pad = 0.003
                zoomToBoundingBox(BoundingBox(b.north + pad, b.east + pad, b.south - pad, b.west - pad), false, 24)
            }
        }
    }
    DisposableEffect(map) { map.onResume(); onDispose { map.onPause(); map.onDetach() } }
    AndroidView({ map }, modifier.clip(RoundedCornerShape(12.dp)).semantics { contentDescription = if (onTap != null) "Map. Tap where the alert applies to drop a pin." else "Map of where this applies" }) { m ->
        m.overlays.clear()
        if (onTap != null) m.overlays.add(MapEventsOverlay(object : MapEventsReceiver {
            override fun singleTapConfirmedHelper(p: GeoPoint): Boolean { onTap(AlertArea.Coord(p.latitude, p.longitude)); return true }
            override fun longPressHelper(p: GeoPoint): Boolean = false
        }))
        fun gp(c: AlertArea.Coord) = GeoPoint(c.lat, c.lng)
        var pin = 0
        for (s in area?.shapes.orEmpty()) when (s) {
            is AlertArea.Shape.Pin -> {
                val i = pin++
                s.radius?.let { r ->
                    m.overlays.add(Polygon(m).apply {
                        points = Polygon.pointsAsCircle(gp(s.at), r)
                        fillPaint.color = RED_FILL; outlinePaint.color = RED; outlinePaint.strokeWidth = 4f
                        setOnClickListener { _, _, _ -> false }
                    })
                }
                m.overlays.add(Marker(m).apply {
                    position = gp(s.at)
                    icon = GradientDrawable().apply { shape = GradientDrawable.OVAL; setSize(40, 40); setColor(RED); setStroke(4, 0xFFFFFFFF.toInt()) }
                    setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                    setOnMarkerClickListener { _, _ -> onPinTap?.invoke(i); true }
                })
            }
            is AlertArea.Shape.Line -> m.overlays.add(Polyline(m).apply {
                setPoints(s.coords.map(::gp)); outlinePaint.color = RED; outlinePaint.strokeWidth = 9f
                setOnClickListener { _, _, _ -> false }
            })
            is AlertArea.Shape.Area -> m.overlays.add(Polygon(m).apply {
                points = s.rings.first().map(::gp)
                fillPaint.color = RED_FILL; outlinePaint.color = RED; outlinePaint.strokeWidth = 4f
                setOnClickListener { _, _, _ -> false }
            })
        }
        m.invalidate()
    }
}
