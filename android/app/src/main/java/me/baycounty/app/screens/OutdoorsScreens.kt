package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.Outdoors
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.ZoneId

private fun hex(v: Long) = Color(0xFF000000 or v)

private fun ratingColor(r: String?): Color = when (r) {
    "Good" -> hex(0x2E9E5B)
    "Moderate" -> hex(0xE0A526)
    "Poor" -> hex(0xD84315)
    else -> Color.Gray
}

@Composable
private fun riskColor(r: String?): Color = when (r) {
    "High" -> hex(0xD84315)
    "Moderate" -> Brand.amber
    "Low" -> Brand.good
    else -> Brand.text
}

private fun dot(r: DataRow, id: String, title: String, color: Color): MapDot? {
    val lat = r.number("latitude") ?: return null
    val lng = r.number("longitude") ?: return null
    return MapDot(id, title, lat, lng, color, r)
}

@Composable
private fun Tags(tags: List<String>) {
    Flow(4.dp) {
        for (t in tags) Text(t, style = T.caption2, color = Brand.text, maxLines = 1,
            modifier = Modifier.background(Brand.sunken, RoundedCornerShape(50)).padding(horizontal = 7.dp, vertical = 2.dp))
    }
}

/** A tappable list row that opens directions: name, detail line, tags. */
@Composable
private fun PlaceRow(title: String, detail: String, tags: List<String>, url: String?) {
    val opener = rememberOpener()
    Row(
        Modifier.fillMaxWidth().clickable { opener.open(url) }.padding(horizontal = 14.dp, vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(title, style = T.subheadBold, color = Brand.text)
            if (detail.isNotEmpty()) Text(detail, style = T.caption, color = Brand.secondary)
            if (tags.isNotEmpty()) Tags(tags)
        }
        Icon(icon("arrow.triangle.turn.up.right.diamond"), "Directions", tint = Brand.navy)
    }
}

@Composable
private fun ShowAllButton(n: Int, onClick: () -> Unit) {
    Box(Modifier.fillMaxWidth().heightIn(min = 44.dp).card(14.dp).clickable(onClick = onClick), contentAlignment = Alignment.Center) {
        Text("Show all $n", style = T.subheadBold, color = Brand.navy)
    }
}

// Beaches

/** Beaches (/beaches): today's flag and rip current risk, the forecast, what the flags mean, water quality at each
 *  state sampling site, and every public beach access on a map. Same sections as the iOS BeachesView. */
@Composable
fun BeachesScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Outdoors.beachDatasets) }
    val conditions = store.rows["beach-conditions"] ?: emptyList()
    val sites = store.rows["beach-water-sites"] ?: emptyList()
    val access = store.rows["beach-access"] ?: emptyList()
    val parking = store.rows["beach-parking"] ?: emptyList()
    val today = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    var filter by rememberSaveable { mutableStateOf(Outdoors.AccessFilter.ALL) }
    var query by rememberSaveable { mutableStateOf("") }
    var showAll by rememberSaveable { mutableStateOf(false) }

    Screen("Beaches", onRefresh = { Outdoors.beachDatasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero("Outdoors · Beaches", "Beaches",
                "Today's flag and rip current risk, water quality at each state sampling site, and every public beach access.",
                symbol = "beach.umbrella", tone = Tone.TEAL)
        }
        if (conditions.isEmpty() && access.isEmpty()) {
            item {
                val e = Outdoors.beachDatasets.firstNotNullOfOrNull { store.errors[it] }
                if (e != null) Unavailable("Couldn't load the beaches", e) else Loading()
            }
            return@Screen
        }
        item { TodaySection(conditions) }
        item { FlagsSection(conditions) }
        item { WaterSection(sites, today) }
        item {
            AccessSection(access, sites, parking, filter, query, showAll,
                onFilter = { filter = it; showAll = false }, onQuery = { query = it }, onShowAll = { showAll = true })
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.Parks, "Parks, boat ramps and trails", symbol = "tree")
                    RowDivider(50.dp)
                    WebRow("Beaches on BayCounty.me", "${BayCountyClient.SITE}/beaches", "Map, flag meanings and sources", symbol = "safari")
                }
                FreshnessNote("beach-conditions")
            }
        }
    }
}

@Composable
private fun TodaySection(conditions: List<DataRow>) {
    val opener = rememberOpener()
    val fc = Outdoors.forecast(conditions)
    val now = fc.firstOrNull()
    val flag = Outdoors.flag(conditions)
    PageSection("Today at the beach", "sun.max", Tone.AMBER,
        "From the National Weather Service surf zone forecast. Flags can change during the day: check the pole at the beach.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Row {
                    Box(Modifier.width(3.dp).height(64.dp).background(Brand.secondary))
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Box(Modifier.size(40.dp, 26.dp).background(hex(Outdoors.flagHex(flag?.first ?: "")), RoundedCornerShape(3.dp)))
                        if (flag?.first == "Double red") Box(Modifier.size(40.dp, 26.dp).background(hex(Outdoors.flagHex("Double red")), RoundedCornerShape(3.dp)))
                    }
                }
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text("BEACH FLAG", style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Brand.salmon)
                    Text(flag?.let { "${it.first} flag" } ?: "Not reported", style = T.title2, color = Brand.text)
                    if (!flag?.second.isNullOrEmpty()) Text(flag!!.second, style = T.subheadBold, color = Brand.text)
                }
            }
            Grid2(listOf(0, 1, 2, 3)) { i, m ->
                when (i) {
                    0 -> KPICard("Rip current risk", now?.string("rip_current_risk") ?: "—", m, symbol = "water.waves", tone = Tone.SALMON)
                    1 -> KPICard("Surf", now?.string("surf_height") ?: "—", m, symbol = "wind", tone = Tone.BLUE)
                    2 -> KPICard("Water", (now?.string("water_temperature") ?: "—").replace(" degrees", "°F"), m, symbol = "thermometer.medium", tone = Tone.TEAL)
                    else -> KPICard("UV index", now?.string("uv_index") ?: "—", m, symbol = "sun.max", tone = Tone.AMBER)
                }
            }
            for (a in Outdoors.alerts(conditions)) {
                Box(Modifier.fillMaxWidth().card(14.dp).clickable { opener.open(a.url("source_url")) }) {
                    TextRow(a.string("period") ?: "Alert", a.string("summary"), badge = "Alert" to Brand.salmon)
                }
            }
            if (fc.size > 1) {
                CardList {
                    val rest = fc.drop(1)
                    rest.forEachIndexed { i, r ->
                        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text(r.string("period") ?: "", style = T.subheadBold, color = Brand.text)
                                val w = r.string("weather")?.let { listOfNotNull(it, r.string("winds")).joinToString(", ") }
                                    ?: (r.string("summary") ?: "").replace("*", "")
                                Text(w, style = T.caption, color = Brand.secondary)
                            }
                            Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(r.string("rip_current_risk") ?: "—", style = T.subheadBold, color = riskColor(r.string("rip_current_risk")))
                                Text("rip currents", style = T.caption2, color = Brand.secondary)
                            }
                        }
                        if (i < rest.lastIndex) RowDivider()
                    }
                }
            }
            Text("If you're caught in a rip current, swim parallel to shore, then back in. For a text when Panama City Beach's flags change, text PCBFLAGS to 888777.",
                style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun FlagsSection(conditions: List<DataRow>) {
    val legend = Outdoors.legend(conditions)
    PageSection("What the flags mean", "flag", Tone.SALMON, "Double red flags close the water. No flag flying doesn't mean the water is safe.") {
        CardList {
            legend.forEachIndexed { i, l ->
                Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Box(Modifier.padding(top = 2.dp).size(26.dp, 18.dp).background(hex(Outdoors.flagHex(l.string("flag_color") ?: "")), RoundedCornerShape(3.dp)))
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("${l.string("flag_color") ?: ""}: ${l.string("meaning") ?: ""}", style = T.subheadBold, color = Brand.text)
                        Text(l.string("summary") ?: "", style = T.caption, color = Brand.secondary)
                    }
                }
                if (i < legend.lastIndex) RowDivider(52.dp)
            }
        }
    }
}

@Composable
private fun WaterSection(sites: List<DataRow>, today: String) {
    val list = Outdoors.waterSites(sites)
    val poor = Outdoors.poorNow(sites, today)
    PageSection("Water quality", "drop", Tone.BLUE,
        "Florida Healthy Beaches Program: enterococci per 100 mL. Good 0 to 35, moderate 36 to 70, poor 71 or more.") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(
                if (poor.isEmpty()) "No site was rated poor in the past six weeks."
                else "${poor.size} site${if (poor.size == 1) " was" else "s were"} rated poor at a test in the past six weeks.",
                style = T.subhead, color = Brand.text,
            )
            CardList {
                list.forEachIndexed { i, s ->
                    val rating = s.string("latest_rating")
                    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Text(s.string("name") ?: "", style = T.subheadBold, color = Brand.text)
                            Text(listOfNotNull("Latest ${s.string("latest_date") ?: "none"}", s.number("latest_enterococcus")?.let { "${it.toInt()} per 100 mL" },
                                if (s.bool("latest_advisory") == true) "health advisory" else null).joinToString(" · "), style = T.caption, color = Brand.secondary)
                            Text("${(s.number("good") ?: 0.0).toInt()} good, ${(s.number("moderate") ?: 0.0).toInt()} moderate, ${(s.number("poor") ?: 0.0).toInt()} poor since ${s.string("first_date") ?: ""}",
                                style = T.caption2, color = Brand.secondary)
                        }
                        if (rating != null) Badge(rating, ratingColor(rating))
                    }
                    if (i < list.lastIndex) RowDivider()
                }
            }
        }
    }
}

@Composable
private fun AccessSection(
    access: List<DataRow>, sites: List<DataRow>, parking: List<DataRow>, filter: Outdoors.AccessFilter, query: String, showAll: Boolean,
    onFilter: (Outdoors.AccessFilter) -> Unit, onQuery: (String) -> Unit, onShowAll: () -> Unit,
) {
    val opener = rememberOpener()
    val list = Outdoors.accesses(access, filter, query)
    val shown = if (showAll || query.isNotEmpty()) list else list.take(12)
    val blue = Brand.blue
    val pts = access.mapNotNull { dot(it, "a${it.id}", it.string("name") ?: "Beach access", blue) } +
        Outdoors.waterSites(sites).mapNotNull { dot(it, "w${it.id}", it.string("name") ?: "", ratingColor(it.string("latest_rating"))) } +
        parking.mapNotNull { dot(it, "p${it.id}", "County beach parking", Color.Gray) }
    PageSection("Beach access and parking", "beach.umbrella", Tone.TEAL,
        "${access.size} public accesses. Blue: access. Green to red: water sample site. Gray: county beach parking.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            PointsMap(pts, Modifier.fillMaxWidth().height(280.dp)) { p -> p.row?.let { opener.open(Outdoors.directions(it)) } }
            FilterField(query, "Search by name, number or street", onQuery)
            ChipRow(Outdoors.AccessFilter.entries.map { it to it.label }, filter) { onFilter(it) }
            CardList {
                shown.forEachIndexed { i, a ->
                    PlaceRow(a.string("name") ?: "", listOfNotNull(a.string("address"), a.string("area")).joinToString(" · "), Outdoors.accessTags(a), Outdoors.directions(a))
                    if (i < shown.lastIndex) RowDivider()
                }
            }
            if (shown.size < list.size) ShowAllButton(list.size, onShowAll)
        }
    }
}

// Parks

/** Parks (/parks): every public park with its amenities, boat ramps, trails and each government's recreation pages.
 *  Same sections as the iOS ParksView. */
@Composable
fun ParksScreen() {
    val store = LocalStore.current
    val opener = rememberOpener()
    LaunchedEffect(Unit) { store.load(Outdoors.parkDatasets) }
    val parks = store.rows["parks"] ?: emptyList()
    val ramps = store.rows["boat-ramps"] ?: emptyList()
    val trails = store.rows["trails"] ?: emptyList()
    val rec = store.rows["recreation-departments"] ?: emptyList()
    var filter by rememberSaveable { mutableStateOf(Outdoors.ParkFilter.ALL) }
    var gov by rememberSaveable { mutableStateOf("") }
    var query by rememberSaveable { mutableStateOf("") }
    var showAll by rememberSaveable { mutableStateOf(false) }

    Screen("Parks", onRefresh = { Outdoors.parkDatasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero("Outdoors · Parks", "Parks, boat ramps and trails",
                "Every public park, boat ramp and trail, what each has, who runs it, and where to sign up for programs.",
                symbol = "tree", tone = Tone.TEAL)
        }
        if (parks.isEmpty()) {
            item {
                val e = Outdoors.parkDatasets.firstNotNullOfOrNull { store.errors[it] }
                if (e != null) Unavailable("Couldn't load the parks", e) else Loading()
            }
            return@Screen
        }
        item { ParkKpis(parks, ramps, trails) }
        item {
            val good = Brand.good; val blue = Brand.blue; val amber = Brand.amber
            val pts = parks.mapNotNull { dot(it, "k${it.id}", it.string("name") ?: "", good) } +
                ramps.mapNotNull { dot(it, "r${it.id}", it.string("name") ?: "", blue) } +
                trails.mapNotNull { dot(it, "t${it.id}", it.string("name") ?: "", amber) }
            PointsMap(pts, Modifier.fillMaxWidth().height(280.dp)) { p -> p.row?.let { opener.open(Outdoors.directions(it)) } }
        }
        item {
            ParksSection(parks, filter, gov, query, showAll,
                onFilter = { filter = it; showAll = false }, onGov = { gov = it; showAll = false }, onQuery = { query = it }, onShowAll = { showAll = true })
        }
        item { SignUpSection(rec) }
        item { RampsSection(ramps) }
        item { TrailsSection(trails) }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.Beaches, "Beaches", symbol = "beach.umbrella")
                    RowDivider(50.dp)
                    WebRow("Parks on BayCounty.me", "${BayCountyClient.SITE}/parks", "Map and sources", symbol = "safari")
                }
                FreshnessNote("parks")
            }
        }
    }
}

@Composable
private fun ParkKpis(parks: List<DataRow>, ramps: List<DataRow>, trails: List<DataRow>) {
    val miles = trails.sumOf { it.number("miles") ?: 0.0 }
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Public parks", "${parks.size}", m, "Run by the cities, the county and the state", "tree", Tone.TEAL)
            1 -> KPICard("With a playground", "${parks.count { it.bool("playground") == true }}", m,
                "${parks.count { it.bool("restroom") == true }} have restrooms", "figure.play", Tone.AMBER)
            2 -> KPICard("Boat ramps", "${ramps.size}", m,
                "${ramps.count { (it.string("water") ?: "").lowercase().startsWith("salt") }} on salt water", "sailboat", Tone.BLUE)
            else -> KPICard("Trail miles", "${Math.round(miles)}", m, "${trails.size} named trails", "figure.hiking", Tone.SALMON)
        }
    }
}

@Composable
private fun ParksSection(
    parks: List<DataRow>, filter: Outdoors.ParkFilter, gov: String, query: String, showAll: Boolean,
    onFilter: (Outdoors.ParkFilter) -> Unit, onGov: (String) -> Unit, onQuery: (String) -> Unit, onShowAll: () -> Unit,
) {
    val govs = listOf("" to "All") + parks.mapNotNull { r -> r.string("gov_id")?.let { it to (r.string("run_by") ?: it) } }.distinctBy { it.first }
    val list = Outdoors.parks(parks, filter, gov, query)
    val shown = if (showAll || query.isNotEmpty()) list else list.take(12)
    PageSection("Parks", "tree", Tone.TEAL, "${list.size} of ${parks.size} parks. Tap one for directions.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            FilterField(query, "Search parks by name or street", onQuery)
            ChipRow(govs, gov) { onGov(it) }
            ChipRow(Outdoors.ParkFilter.entries.map { it to it.label }, filter) { onFilter(it) }
            CardList {
                shown.forEachIndexed { i, p ->
                    val detail = listOfNotNull(p.string("address"), p.string("run_by")?.let { "Run by $it" }, p.number("acres")?.let { "${Format.number(it)} acres" }).joinToString(" · ")
                    PlaceRow(p.string("name") ?: "", detail, Outdoors.parkTags(p), Outdoors.directions(p))
                    if (i < shown.lastIndex) RowDivider()
                }
            }
            if (shown.size < list.size) ShowAllButton(list.size, onShowAll)
        }
    }
}

@Composable
private fun SignUpSection(rec: List<DataRow>) {
    PageSection("Programs, leagues and rentals", "figure.run", Tone.AMBER, "Each government runs its own sign-ups") {
        CardList {
            rec.forEachIndexed { i, d ->
                WebRow(d.string("name") ?: "", d.url("programs_url") ?: d.url("parks_url"), d.string("programs_label") ?: "Parks and facilities", symbol = "arrow.up.right.square")
                if (i < rec.lastIndex) RowDivider(50.dp)
            }
        }
    }
}

@Composable
private fun RampsSection(ramps: List<DataRow>) {
    val opener = rememberOpener()
    PageSection("Boat ramps and launches", "sailboat", Tone.BLUE, "${ramps.size} public ramps") {
        CardList {
            ramps.forEachIndexed { i, r ->
                TextRow(r.string("name") ?: "", listOfNotNull(r.string("waterbody"), r.string("water")?.let { "$it water" }, r.string("run_by")).joinToString(" · "),
                    modifier = Modifier.clickable { opener.open(Outdoors.directions(r)) })
                if (i < ramps.lastIndex) RowDivider()
            }
        }
    }
}

@Composable
private fun TrailsSection(trails: List<DataRow>) {
    val opener = rememberOpener()
    val list = trails.sortedByDescending { it.number("miles") ?: 0.0 }
    PageSection("Trails", "figure.hiking", Tone.SALMON, "Longest first. Miles add up each trail's mapped segments.") {
        CardList {
            list.forEachIndexed { i, t ->
                TextRow(t.string("name") ?: "", listOfNotNull(t.string("area"), t.string("surface"), t.string("uses")).joinToString(" · "),
                    value = t.number("miles")?.let { String.format(java.util.Locale.US, "%.1f mi", it) },
                    modifier = Modifier.clickable { opener.open(Outdoors.directions(t)) })
                if (i < list.lastIndex) RowDivider()
            }
        }
    }
}
