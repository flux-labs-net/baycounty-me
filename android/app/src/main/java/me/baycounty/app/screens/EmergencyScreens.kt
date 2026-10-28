package me.baycounty.app.screens

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import me.baycounty.app.Push
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Emergency
import me.baycounty.kit.Format
import me.baycounty.kit.Row as DataRow

private val zoneColors = mapOf("A" to Color(0xFFD1495B), "B" to Color(0xFFED8B3A), "C" to Color(0xFFBF9E21), "D" to Color(0xFF4F9D69))
private val femaColor = Color(0xFF3F6FB0)
private val floodColor = Color(0xFFD9902A)

/** Emergencies and alerts (/emergency). Same sections as the iOS EmergencyView: the live feed from /api/v1/emergency
 *  (the last daily archive until it loads or when offline), the zone lookup, shelters, phone alerts and numbers. */
@Composable
fun EmergencyScreen() {
    val store = LocalStore.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var feed by remember { mutableStateOf<Emergency.Feed?>(null) }
    var kind by rememberSaveable { mutableStateOf("") }
    var address by rememberSaveable { mutableStateOf("") }
    var zone by remember { mutableStateOf<Emergency.ZoneResult?>(null) }
    var zoneError by remember { mutableStateOf<String?>(null) }
    var looking by remember { mutableStateOf(false) }

    suspend fun loadFeed() {
        feed = runCatching { Emergency.parseFeed(store.client.get(Emergency.FEED_PATH).data) }.getOrNull()
    }
    suspend fun lookup(path: String) {
        looking = true; zoneError = null
        zone = runCatching { Emergency.parseZone(store.client.get(path).data) }.onFailure { zoneError = "Couldn't look that up. Check your connection and try again." }.getOrNull()
        looking = false
    }
    LaunchedEffect(Unit) {
        Push.load(context)
        store.load(Emergency.datasets)
        loadFeed()
        store.home?.let { h -> if (address.isEmpty()) { address = h.display; lookup(Emergency.zonePath(h.point.y, h.point.x)) } }
    }
    val shown = feed ?: store.rows["emergency-notices"]?.let {
        Emergency.offlineFeed(it, store.rows["emergency-shelters"] ?: emptyList(), store.rows["evacuation-zones"] ?: emptyList())
    }

    Screen("Emergencies", onRefresh = { loadFeed() }, spacing = 22) {
        item {
            PageHero("Take part · Stay safe", "Emergencies and alerts",
                "Weather warnings, evacuation orders, shelters, boil-water notices and road closures in Bay County, checked every few minutes.",
                symbol = "exclamationmark.triangle", tone = Tone.SALMON)
        }
        if (shown == null) {
            item { val e = Emergency.datasets.firstNotNullOfOrNull { store.errors[it] }; if (e != null) Unavailable("Couldn't load emergencies", e) else Loading() }
            return@Screen
        }
        item { Status(shown) }
        item {
            Grid2(listOf(0, 1, 2, 3)) { i, m ->
                when (i) {
                    0 -> KPICard("Weather alerts", "${shown.count("weather")}", m, symbol = "cloud.bolt.rain", tone = Tone.BLUE)
                    1 -> KPICard("Evacuation orders", "${shown.count("evacuation")}", m, symbol = "car.side.arrowtriangle.up.fill", tone = Tone.SALMON)
                    2 -> KPICard("Shelters open", "${shown.sheltersOpen}", m, symbol = "house.lodge", tone = Tone.TEAL)
                    else -> KPICard("Boil-water notices", "${shown.count("boil-water")}", m, symbol = "drop.triangle", tone = Tone.AMBER)
                }
            }
        }
        item {
            PageSection("Your evacuation zone", "map", Tone.BLUE, "From Bay County's evacuation zone map. Zone A leaves first.") {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            address, { address = it }, Modifier.weight(1f), singleLine = true, textStyle = T.body,
                            placeholder = { Text("Street address, like 825 Ohio Ave", style = T.body) },
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                            keyboardActions = KeyboardActions(onSearch = { scope.launch { lookup(Emergency.zonePath(address)) } }),
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(focusedContainerColor = Brand.surface, unfocusedContainerColor = Brand.surface,
                                focusedBorderColor = Brand.navy, unfocusedBorderColor = Brand.hairline, focusedTextColor = Brand.text, unfocusedTextColor = Brand.text),
                        )
                        Button({ scope.launch { lookup(Emergency.zonePath(address)) } }, enabled = address.trim().length >= 4 && !looking,
                            colors = ButtonDefaults.buttonColors(containerColor = Brand.navy)) { Text("Look up") }
                    }
                    if (looking) Loading()
                    zoneError?.let { Text(it, style = T.subhead, color = Brand.secondary) }
                    zone?.let { ZoneCard(it) }
                }
            }
        }
        item { Now(shown, kind) { kind = it } }
        item { Shelters(shown) }
        item { Alerts() }
        item { Numbers(store.rows["emergency-resources"] ?: emptyList()) }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.HurricanePrep, "Hurricane prep", "Sandbags, generators, rebuild money by ZIP code", symbol = "hurricane")
                    RowDivider(50.dp)
                    WebRow("Zone map and every notice", "${BayCountyClient.SITE}/emergency", "On BayCounty.me", symbol = "safari")
                }
                Text("In an emergency, call 911. BayCounty.me is an independent site: follow instructions from emergency officials.", style = T.footnote, color = Brand.secondary)
            }
        }
    }
}

@Composable
private fun Status(f: Emergency.Feed) {
    val tone = if (f.count("evacuation") > 0) Tone.SALMON else if (f.notices.isEmpty()) Tone.TEAL else Tone.AMBER
    Row(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        ToneIcon(if (f.count("evacuation") > 0) "exclamationmark.octagon" else "bell", tone, 40.dp)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(f.headline, style = T.headline, color = Brand.text)
            Text(if (f.live) "Checked every 5 minutes. Pull to refresh." else "From the last saved check. Pull to refresh.", style = T.caption, color = Brand.secondary)
        }
    }
}

@Composable
private fun ZoneCard(z: Emergency.ZoneResult) {
    Column(Modifier.fillMaxWidth().card(18.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(52.dp).background(zoneColors[z.zone] ?: Brand.secondary, RoundedCornerShape(14.dp)), contentAlignment = Alignment.Center) {
                Text(z.zone ?: "–", style = T.title2.copy(fontWeight = FontWeight.Bold), color = Color.White)
            }
            Column {
                Text(if (!z.found) "No match" else z.zone?.let { "Evacuation Zone $it" } ?: "Not in an evacuation zone", style = T.headline, color = Brand.text)
                z.address?.let { Text(it, style = T.caption, color = Brand.secondary) }
            }
        }
        Text(z.whatToDo, style = T.subhead, color = Brand.text)
        if (z.orders.isEmpty()) Text("No evacuation order is in effect right now.", style = T.footnote, color = Brand.secondary)
        for (o in z.orders) Text((if (o.includesYou) "Includes your zone: " else "") + o.title, style = if (o.includesYou) T.subheadBold else T.subhead, color = Brand.text)
        if (z.nearestShelters.isNotEmpty()) {
            Text("Nearest county shelters (open only when the county opens them)", style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
            for (s in z.nearestShelters) {
                Text("${s.string("name") ?: ""} · ${s.number("miles")?.let { "%.1f mi".format(it) } ?: ""} · ${s.string("status") ?: ""}", style = T.footnote, color = Brand.secondary)
            }
        }
    }
}

@Composable
private fun Now(f: Emergency.Feed, kind: String, onKind: (String) -> Unit) {
    val present = Emergency.kinds.filter { k -> f.notices.any { it.string("kind") == k } }
    val list = if (kind.isEmpty()) f.notices else f.notices.filter { it.string("kind") == kind }
    PageSection("Happening now", "bell", Tone.SALMON, "Most serious first") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (present.size > 1) ChipRow(listOf("" to "Everything") + present.map { it to Emergency.label(it) }, kind) { onKind(it) }
            if (list.isEmpty()) Text("Nothing posted right now.", style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
            for (n in list) NoticeCard(n)
        }
    }
}

@Composable
private fun NoticeCard(n: DataRow) {
    val opener = rememberOpener()
    var open by remember { mutableStateOf(false) }
    val k = n.string("kind") ?: "storm"
    val more = listOfNotNull(n.string("summary")?.takeIf { it != n.string("title") }, n.string("instruction")).joinToString("\n\n")
    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Icon(icon(Emergency.symbol(k)), null, tint = Brand.secondary, modifier = Modifier.size(16.dp))
            Text((if (k == "weather") n.string("event") ?: "Weather" else Emergency.label(k)).uppercase(), style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary)
        }
        Text(n.string("title") ?: "", style = T.subheadBold, color = Brand.text)
        n.string("area")?.let { Text(it, style = T.footnote, color = Brand.secondary, maxLines = 3) }
        if (more.isNotEmpty()) {
            Text(if (open) "Hide details" else "Details", style = T.footnote, color = Brand.navy, modifier = Modifier.clickable { open = !open })
            if (open) Text(more, style = T.footnote, color = Brand.text)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(listOfNotNull(n.string("source"), Emergency.posted(n).ifEmpty { null }).joinToString(" · "), style = T.caption, color = Brand.secondary, modifier = Modifier.weight(1f))
            n.url("url")?.let { u -> Text("Source", style = T.caption, color = Brand.navy, modifier = Modifier.clickable { opener.open(u) }) }
        }
    }
}

@Composable
private fun Shelters(f: Emergency.Feed) {
    PageSection("Shelters", "house.lodge", Tone.TEAL,
        "Not every shelter opens for every storm. Plan to stay with family or friends outside the zone if you can; special needs shelters need registration ahead of time.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            for ((type, rows) in Emergency.sheltersByType(f.shelters)) {
                Text(Emergency.shelterTypeLabel(type), style = T.subheadBold, color = Brand.text)
                CardList {
                    rows.forEachIndexed { i, s ->
                        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                                Text(s.string("name") ?: "", style = T.subhead, color = Brand.text)
                                Text(s.string("address") ?: "", style = T.caption, color = Brand.secondary)
                            }
                            Text((s.string("status") ?: "").replaceFirstChar { it.uppercase() }, style = T.caption.copy(fontWeight = FontWeight.Bold),
                                color = if (s.string("status") == "open") Brand.good else Brand.secondary)
                        }
                        if (i < rows.lastIndex) RowDivider()
                    }
                }
            }
        }
    }
}

@Composable
private fun Alerts() {
    val store = LocalStore.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val home = store.home
    val turnOn = { Push.enable(context, home?.point) { scope.launch { Push.sync(context, home?.point) } } }
    val ask = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) turnOn() else Push.status = "Notifications are off for BayCounty.me in Settings."
    }
    PageSection("Alerts on this phone", "bell.badge", Tone.AMBER,
        "BayCounty.me sends a notification when the county, a city or the Weather Service posts one of these. Only this phone's token and your choices are stored.") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Send me alerts", style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                Switch(Push.enabled, { on ->
                    if (!on) scope.launch { Push.disable(context) }
                    else if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) ask.launch(Manifest.permission.POST_NOTIFICATIONS)
                    else turnOn()
                }, colors = SwitchDefaults.colors(checkedTrackColor = Brand.navy))
            }
            if (Push.enabled) {
                CardList {
                    Emergency.pushTopics.forEachIndexed { i, t ->
                        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(t.label, style = T.subhead, color = Brand.text)
                                Text(t.detail, style = T.caption, color = Brand.secondary)
                            }
                            Switch(t.id in Push.topics, { on -> Push.setTopic(context, t.id, on); scope.launch { Push.sync(context, home?.point) } },
                                colors = SwitchDefaults.colors(checkedTrackColor = Brand.navy))
                        }
                        if (i < Emergency.pushTopics.lastIndex) RowDivider()
                    }
                }
                if ("agenda" in Push.topics) {
                    if (home != null) {
                        Text("Agenda items within ${radiusLabel(Push.radius)} of ${home.display}.", style = T.footnote, color = Brand.secondary)
                        ChipRow(Emergency.radiusChoices.map { it to radiusLabel(it) }, Push.radius) { r -> Push.setRadius(context, r); scope.launch { Push.sync(context, home.point) } }
                    } else {
                        Text("Save your address on Today to get agenda items near it.", style = T.footnote, color = Brand.secondary)
                    }
                }
                Text("Boil-water notices and closures from", style = T.footnote.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
                ChipLayout {
                    for ((id, label) in Emergency.pushGovs) {
                        val on = id in Push.govs
                        Text(label, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = if (on) Color.White else Brand.text,
                            modifier = Modifier.background(if (on) Brand.navy else Brand.hairline.copy(alpha = 0.35f), RoundedCornerShape(50))
                                .clickable { Push.toggleGov(context, id); scope.launch { Push.sync(context, home?.point) } }
                                .padding(horizontal = 10.dp, vertical = 6.dp))
                    }
                }
                Text(if (Push.govs.isEmpty()) "None picked: every government." else "Only the ones picked.", style = T.caption, color = Brand.secondary)
            }
            Push.status?.let { Text(it, style = T.caption, color = Brand.secondary) }
        }
    }
}

private fun radiusLabel(r: Double): String = when (r) { 0.25 -> "¼ mile"; 0.5 -> "½ mile"; 1.0 -> "1 mile"; else -> "${r.toInt()} miles" }

@Composable
private fun Numbers(rows: List<DataRow>) {
    val opener = rememberOpener()
    PageSection("Phone numbers and links", "phone", Tone.BLUE) {
        CardList {
            rows.forEachIndexed { i, r ->
                val phone = r.string("phone")
                Row(
                    Modifier.fillMaxWidth().clickable { if (phone != null) opener.open("tel:" + phone.filter { it.isDigit() }) else opener.open(r.url("url")) }
                        .padding(horizontal = 14.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(r.string("name") ?: "", style = T.subheadBold, color = Brand.text)
                        r.string("about")?.let { Text(it, style = T.caption, color = Brand.secondary) }
                    }
                    if (phone != null) Text(phone, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy) else Chevron()
                }
                if (i < rows.lastIndex) RowDivider()
            }
        }
    }
}

/** Hurricane prep (/hurricane-prep). Same sections as the iOS HurricanePrepView. */
@Composable
fun HurricanePrepScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Emergency.prepDatasets) }
    val steps = store.rows["hurricane-prep"] ?: emptyList()
    val money = store.rows["rebuild-money"] ?: emptyList()
    val decl = Emergency.declarations(store.rows["disaster-declarations"] ?: emptyList())
    var storm by rememberSaveable { mutableStateOf(Emergency.Storm.ALL) }
    var openTopic by rememberSaveable { mutableStateOf<String?>("Before the season") }
    var showAll by rememberSaveable { mutableStateOf(false) }

    Screen("Hurricane prep", onRefresh = { Emergency.prepDatasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero("Take part · Stay safe", "Hurricane prep",
                "A plan and a kit, sandbags, generator safety, what to do when a storm is coming and after it, and the FEMA money past storms brought each part of the county.",
                symbol = "hurricane", tone = Tone.BLUE)
        }
        if (steps.isEmpty()) {
            item { val e = Emergency.prepDatasets.firstNotNullOfOrNull { store.errors[it] }; if (e != null) Unavailable("Couldn't load hurricane prep", e) else Loading() }
            return@Screen
        }
        item { CardList { RouteRow(Route.Emergency, "Find my evacuation zone", "And what's happening now", symbol = "map") } }
        item {
            PageSection("What to do", "checklist", Tone.TEAL, "From Bay County, Ready.gov, the CDC, the Weather Service and FEMA. Each step links its source.") {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    for ((topic, rows) in Emergency.prepTopics(steps)) PrepTopic(topic, rows, openTopic == topic) { openTopic = if (openTopic == topic) null else topic }
                }
            }
        }
        item { Rebuild(money, storm, showAll, { storm = it; showAll = false }, { showAll = !showAll }) }
        item {
            PageSection("Disaster declarations", "doc.text", Tone.SALMON, "${decl.size} since 2016. A major disaster opens FEMA aid; an emergency pays for evacuations and shelters.") {
                val opener = rememberOpener()
                CardList {
                    decl.forEachIndexed { i, d ->
                        TextRow(d.string("title") ?: "", listOfNotNull(d.string("kind"), d.string("declared"), if (d.bool("individual_aid") == true) "aid to households" else null).joinToString(" · "),
                            modifier = Modifier.clickable { opener.open(d.url("source_url")) })
                        if (i < decl.lastIndex) RowDivider()
                    }
                }
            }
        }
        item { FreshnessNote("rebuild-money") }
    }
}

@Composable
private fun PrepTopic(topic: String, rows: List<DataRow>, open: Boolean, onToggle: () -> Unit) {
    val opener = rememberOpener()
    Column(Modifier.fillMaxWidth().card(14.dp)) {
        Row(Modifier.fillMaxWidth().clickable { onToggle() }.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            ToneIcon(Emergency.prepSymbol(topic), Tone.TEAL)
            Text(topic, style = T.headline, color = Brand.text, modifier = Modifier.weight(1f))
            Icon(icon(if (open) "chevron.up" else "chevron.down"), null, tint = Brand.tertiary)
        }
        if (open) {
            Column(Modifier.padding(start = 14.dp, end = 14.dp, bottom = 14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                for (s in rows) {
                    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                        Text(s.string("step") ?: "", style = T.subheadBold, color = Brand.text)
                        Text(s.string("text") ?: "", style = T.subhead, color = Brand.text)
                        s.url("source_url")?.let { u -> Text("Source: ${s.string("source") ?: "link"}", style = T.caption, color = Brand.navy, modifier = Modifier.clickable { opener.open(u) }) }
                    }
                }
            }
        }
    }
}

@Composable
private fun Rebuild(money: List<DataRow>, storm: Emergency.Storm, showAll: Boolean, onStorm: (Emergency.Storm) -> Unit, onMore: () -> Unit) {
    val zips = Emergency.rebuild(money, storm)
    val shown = if (showAll) zips else zips.take(8)
    val max = zips.maxOfOrNull { it.total } ?: 1.0
    PageSection("Rebuild money by neighborhood", "house.and.flag", Tone.AMBER,
        "FEMA housing aid (repairs and rent) and flood insurance claims paid, by ZIP code. Totals only; no household is named.") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(Emergency.Storm.entries.map { it to it.label }, storm) { onStorm(it) }
            Grid2(listOf(0, 1)) { i, m ->
                if (i == 0) KPICard("FEMA housing aid", Format.compactMoney(zips.sumOf { it.femaAid }), m, "${zips.sumOf { it.households }} households applied", "house", Tone.BLUE)
                else KPICard("Flood insurance paid", Format.compactMoney(zips.sumOf { it.floodPaid }), m, "${zips.sumOf { it.claims }} claims", "drop", Tone.AMBER)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Legend(femaColor, "FEMA housing aid"); Legend(floodColor, "Flood insurance")
            }
            CardList {
                shown.forEachIndexed { i, z ->
                    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 9.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(z.label, style = T.subheadBold, color = Brand.text)
                                Text(z.name, style = T.caption, color = Brand.secondary)
                            }
                            Text(Format.compactMoney(z.total), style = T.subheadBold, color = Brand.text, textAlign = TextAlign.End)
                        }
                        Row(Modifier.fillMaxWidth().height(10.dp), horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                            if (z.femaAid > 0) Box(Modifier.fillMaxWidth((z.femaAid / max).toFloat().coerceIn(0.005f, 1f)).height(10.dp).background(femaColor, RoundedCornerShape(2.dp)))
                            if (z.floodPaid > 0) Box(Modifier.weight(1f, fill = false).fillMaxWidth((z.floodPaid / max / (1 - z.femaAid / max).coerceAtLeast(0.0001)).toFloat().coerceIn(0.005f, 1f)).height(10.dp).background(floodColor, RoundedCornerShape(topEnd = 4.dp, bottomEnd = 4.dp)))
                        }
                    }
                    if (i < shown.lastIndex) RowDivider()
                }
                if (zips.size > 8) { RowDivider(0.dp); ShowMoreRow(showAll, "Show all ${zips.size} ZIP codes", onMore) }
            }
        }
    }
}

@Composable
private fun Legend(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Box(Modifier.size(12.dp).background(color, RoundedCornerShape(3.dp)))
        Text(label, style = T.caption, color = Brand.secondary)
    }
}
