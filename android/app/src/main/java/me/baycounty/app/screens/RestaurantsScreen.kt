package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.Restaurants
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.ZoneId

/** Restaurant inspections (/restaurants): search first, then every place latest inspected first with its latest result
 *  and a strip of its last six inspections. Reads the restaurants dataset; rules in the kit's Restaurants. Same screen as
 *  the iOS RestaurantsView. */
@Composable
fun RestaurantsScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    LaunchedEffect(Unit) { store.load(Restaurants.datasets) }
    val rows = store.rows["restaurants"] ?: emptyList()
    val today = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    var query by rememberSaveable { mutableStateOf("") }
    var city by rememberSaveable { mutableStateOf("") }
    var show by rememberSaveable { mutableStateOf(Restaurants.Show.LATEST) }
    var limit by rememberSaveable { mutableIntStateOf(40) }

    Screen("Restaurants", onRefresh = { store.load("restaurants", force = true) }, spacing = 16) {
        item {
            PageHero("Living here · Restaurants", "Restaurant inspections",
                     "Look up any restaurant, food truck or caterer and see what state inspectors found on every visit since 2016.",
                     symbol = "fork.knife", tone = Tone.SALMON)
        }
        if (rows.isEmpty()) {
            item { store.errors["restaurants"]?.let { Unavailable("Couldn't load restaurants", it) } ?: Loading() }
            return@Screen
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                FilterField(query, "Restaurant, owner or street") { query = it; limit = 40 }
                FieldMenu("City", city.ifEmpty { "All cities" }, listOf("" to "All cities") + Restaurants.cities(rows).map { it to it }, selected = city) { city = it; limit = 40 }
                ChipRow(Restaurants.Show.entries.map { it to it.label }, show) { show = it; limit = 40 }
                val (start, places) = Restaurants.week(rows)
                if (places > 0) Text(buildAnnotatedString {
                    withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = Brand.text)) { append("$places") }
                    append(" places inspected in the week of ${Restaurants.dateLabel(start)}.")
                }, style = T.subhead, color = Brand.secondary)
            }
        }
        val all = Restaurants.list(rows, query, city, show, today)
        val shown = all.take(limit)
        item { Text("${Format.number(all.size)} place${if (all.size == 1) "" else "s"}, latest inspected first", style = T.footnote, color = Brand.secondary) }
        item {
            if (shown.isEmpty()) {
                Text("Nothing matches. Try another name or street.", style = T.subhead, color = Brand.secondary,
                     modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
            } else {
                CardList {
                    shown.forEachIndexed { i, r ->
                        RestaurantRow(r) { nav.push(Route.Restaurant(r.string("license_number") ?: "")) }
                        if (i < shown.lastIndex) RowDivider(14.dp)
                    }
                    if (all.size > shown.size) {
                        RowDivider(0.dp)
                        ShowMoreRow(false, "Show more") { limit += 60 }
                    }
                }
            }
        }
        item {
            Text("The squares are the last six inspections, oldest to newest: green met standards, amber warning, red closed or fine recommended.",
                 style = T.caption, color = Brand.secondary)
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList { WebRow("Closures, common problems and new places", "${BayCountyClient.SITE}/restaurants", "On BayCounty.me", symbol = "safari") }
                FreshnessNote("restaurants")
            }
        }
    }
}

@Composable
private fun RestaurantRow(r: DataRow, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(r.string("business_name") ?: "", style = T.subheadBold, color = Brand.text)
            Text(listOfNotNull(r.string("kind"), r.string("city"), if (r.bool("licensed_now") == true) null else "No longer licensed").joinToString(" · "),
                 style = T.caption, color = Brand.secondary)
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            ResultPill(Restaurants.shortResult(r.string("last_result")) ?: "Not inspected yet", r.string("last_result_level"))
            Text(Restaurants.dateLabel(r.string("last_inspection")), style = T.caption2, color = Brand.secondary)
            if (r.string("recent_results") != null) InspectionStrip(r.string("recent_results"))
        }
    }
}

@Composable
private fun levelColor(level: String?): Color = when (Restaurants.tone(level)) {
    Restaurants.Tone.GOOD -> Brand.good
    Restaurants.Tone.WARNING -> Brand.amber
    Restaurants.Tone.BAD -> Brand.salmon
    Restaurants.Tone.NONE -> Brand.secondary
}

/** A result in its color: green met standards, amber warning, red closed or fine recommended. */
@Composable
private fun ResultPill(text: String, level: String?) {
    val c = levelColor(level)
    val warn = Restaurants.tone(level) == Restaurants.Tone.WARNING
    Text(text, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = if (warn) Brand.text else c,
         modifier = Modifier.background(c.copy(alpha = if (warn) 0.28f else 0.14f), RoundedCornerShape(50)).padding(horizontal = 9.dp, vertical = 3.dp))
}

/** The last six inspections as small squares, oldest on the left. */
@Composable
private fun InspectionStrip(recent: String?) {
    val lv = Restaurants.strip(recent)
    val hairline = Brand.hairline
    val colors = lv.map { if (it.isEmpty()) hairline else levelColor(it) }
    Row(Modifier.semantics { contentDescription = "Last inspections, oldest to newest: ${lv.filter { it.isNotEmpty() }.joinToString(", ")}" },
        horizontalArrangement = Arrangement.spacedBy(3.dp)) {
        colors.forEach { Box(Modifier.size(10.dp).background(it, RoundedCornerShape(2.5.dp))) }
    }
}

/** One restaurant (/restaurants/<name>-<license>): the plain summary, its numbers and every inspection since 2016, read
 *  from /api/v1/datasets/restaurant-inspections by license number. Same as the iOS RestaurantDetailView. */
@Composable
fun RestaurantDetailScreen(license: String) {
    val store = LocalStore.current
    LaunchedEffect(license) { store.load(Restaurants.datasets); store.loadRestaurantVisits(license) }
    val r = store.rows["restaurants"]?.firstOrNull { it.string("license_number") == license }
    val visits = store.restaurantVisits[license]

    Screen(r?.string("business_name") ?: "Restaurant", onRefresh = { store.loadRestaurantVisits(license, force = true) }, spacing = 16) {
        if (r == null) {
            item { store.errors["restaurants"]?.let { Unavailable("Couldn't load this restaurant", it) } ?: Loading() }
            return@Screen
        }
        item {
            PageHero("Restaurant inspections", r.string("business_name") ?: "",
                     listOfNotNull(r.string("kind"), r.string("address"), r.string("city")).joinToString(" · "), symbol = "fork.knife", tone = Tone.SALMON)
        }
        item { Text(Restaurants.summary(r), style = T.body, color = Brand.text, modifier = Modifier.fillMaxWidth().card(16.dp).padding(16.dp)) }
        item {
            Grid2(listOf(0, 1, 2, 3)) { i, m ->
                when (i) {
                    0 -> KPICard("Latest result", Restaurants.shortResult(r.string("last_result")) ?: "None yet", m, Restaurants.dateLabel(r.string("last_inspection")), "checkmark.seal", Tone.TEAL)
                    1 -> KPICard("Inspections", Format.number(r.number("inspections") ?: 0.0), m, "${(r.number("inspections_last_year") ?: 0.0).toInt()} in the last 12 months", "checklist", Tone.BLUE)
                    2 -> KPICard("High-priority violations", Format.number(r.number("high_priority_last_year") ?: 0.0), m, "Cited in the last 12 months", "exclamationmark.triangle", Tone.AMBER)
                    else -> KPICard("Emergency closures", Format.number(r.number("closures") ?: 0.0), m, r.string("last_closure")?.let { "Last ${Restaurants.dateLabel(it)}" } ?: "Since 2016", "flag", Tone.SALMON)
                }
            }
        }
        r.string("licensee")?.let { who -> item { CardList { FactRow("License holder", who) } } }
        item {
            PageSection("Every inspection since 2016", "checklist", Tone.BLUE, "Newest first") {
                when {
                    visits == null && store.errors["visits:$license"] != null ->
                        Text("Couldn't load the inspections. Pull to try again, or open the page on BayCounty.me.", style = T.subhead, color = Brand.secondary)
                    visits == null -> Loading()
                    visits.isEmpty() -> Text("No inspections on file yet.", style = T.subhead, color = Brand.secondary)
                    else -> CardList {
                        visits.forEachIndexed { i, x ->
                            val closed = x.string("disposition") == "Emergency order recommended"
                            Column(
                                Modifier.fillMaxWidth().background(if (closed) Brand.salmon.copy(alpha = 0.08f) else Color.Transparent)
                                    .padding(horizontal = 14.dp, vertical = 11.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp),
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(Restaurants.dateLabel(x.string("date")), style = T.caption, color = Brand.secondary)
                                    Spacer(Modifier.weight(1f))
                                    ResultPill(x.string("result") ?: "", x.string("result_level"))
                                }
                                Text(Restaurants.visitLabel(x), style = T.subheadBold, color = Brand.text)
                                Text(Restaurants.counts(x), style = T.caption, color = Brand.secondary)
                                x.string("violation_items")?.let { Text(it, style = T.caption, color = Brand.secondary) }
                            }
                            if (i < visits.lastIndex) RowDivider(14.dp)
                        }
                    }
                }
            }
        }
        item {
            CardList { WebRow("Open on BayCounty.me", "${BayCountyClient.SITE}${Restaurants.pagePath(r)}", "With the violation names for every visit", symbol = "safari") }
        }
    }
}
