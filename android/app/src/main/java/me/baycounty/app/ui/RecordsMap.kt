package me.baycounty.app.ui

import android.graphics.drawable.GradientDrawable
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.viewinterop.AndroidView
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Row as DataRow
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker

/** Records with a location as dots on an OpenStreetMap map of the county (the iOS app's MapKit map). */
@Composable
fun RecordsMap(datasetID: String, rows: List<DataRow>, modifier: Modifier = Modifier, onSelect: ((DataRow) -> Unit)? = null) {
    val located = rows.filter { it.number("lat") != null && it.number("lng") != null }.take(600)
    if (LocalInspectionMode.current) {
        Box(modifier.clip(RoundedCornerShape(14.dp)).background(Brand.sunken), contentAlignment = Alignment.Center) { Text("Map", style = T.caption, color = Brand.secondary) }
        return
    }
    val context = LocalContext.current
    val spec = DatasetSpec.forId(datasetID)
    val colors = located.associate { it.id to statusColor(it.string("status") ?: "").toArgb() }
    val map = remember {
        Configuration.getInstance().userAgentValue = context.packageName
        MapView(context).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            zoomController.setVisibility(org.osmdroid.views.CustomZoomButtonsController.Visibility.NEVER)
            controller.setZoom(if (located.size == 1) 15.0 else 10.5)
            controller.setCenter(located.singleOrNull()?.let { GeoPoint(it.number("lat")!!, it.number("lng")!!) } ?: GeoPoint(30.22, -85.68))
        }
    }
    DisposableEffect(map) { map.onResume(); onDispose { map.onPause(); map.onDetach() } }
    AndroidView({ map }, modifier.clip(RoundedCornerShape(14.dp))) { m ->
        m.overlays.clear()
        for (r in located) {
            m.overlays.add(Marker(m).apply {
                position = GeoPoint(r.number("lat")!!, r.number("lng")!!)
                title = spec.title(r)
                icon = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL; setSize(40, 40); setColor(colors[r.id] ?: 0xFF1E3A76.toInt()); setStroke(4, 0xFFFFFFFF.toInt())
                }
                setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_CENTER)
                setOnMarkerClickListener { _, _ -> onSelect?.invoke(r); onSelect != null }
            })
        }
        m.invalidate()
    }
}

