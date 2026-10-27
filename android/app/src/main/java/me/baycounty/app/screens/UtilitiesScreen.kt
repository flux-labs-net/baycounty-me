package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.GeoPoint
import me.baycounty.kit.PickupDays
import me.baycounty.kit.UtilityLookup
import java.time.format.DateTimeFormatter
import java.util.Locale

/** The address the screenshot route opens (the same one as the saved test answer). */
val UTILITIES_SAMPLE = AddressMatch("825 OHIO AVE", null, "Lynn Haven", "32444", null, GeoPoint(-85.647793, 30.245649))

private val dayFormat = DateTimeFormatter.ofPattern("EEEE, MMMM d", Locale.US)

/** Utilities and trash day (/utilities): who provides water, sewer, power, gas and garbage at an address, its pickup
 *  days, holiday changes and the typical water bill. Reads /api/v1/utilities, the same answer the site's page shows.
 *  Same sections as the iOS UtilitiesView. Opens on the given address, else the saved home, else a search. */
@Composable
fun UtilitiesScreen(match: AddressMatch?) {
    val store = LocalStore.current
    var query by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<AddressMatch>>(emptyList()) }
    var message by remember { mutableStateOf<String?>(null) }
    var picked by remember { mutableStateOf<AddressMatch?>(null) }
    val current = picked ?: match ?: store.home
    var lookup by remember(current?.id) { mutableStateOf(current?.let { store.utilities[it.id] }) }
    var failed by remember(current?.id) { mutableStateOf(false) }

    LaunchedEffect(query) {
        val q = query.trim()
        if (q.length < 3) { results = emptyList(); message = null; return@LaunchedEffect }
        delay(300)
        try {
            val r = store.gis.search(q)
            results = r.matches
            message = if (r.matches.isEmpty()) "No matching address. Try just the house number and street name." else null
        } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) {
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }
    suspend fun load(force: Boolean = false) {
        val m = current ?: return
        failed = false
        try { lookup = store.loadUtilities(m, force) } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) { failed = true }
    }
    LaunchedEffect(current?.id) { if (lookup == null) load() }

    Screen("Utilities", onRefresh = { load(force = true) }, spacing = 20) {
        item {
            PageHero("What you pay", "Utilities and trash day",
                "Who provides your water, sewer, power, gas and garbage pickup, your trash day, holiday changes and what your city charges.",
                symbol = "trash", tone = Tone.TEAL)
        }
        item { FilterField(query, "e.g. 825 Ohio Ave") { query = it } }
        message?.let { item { Text(it, style = T.subhead, color = Brand.secondary) } }
        if (results.isNotEmpty()) item {
            CardList {
                results.forEachIndexed { i, m ->
                    Row(Modifier.clickable(role = Role.Button) { picked = m; query = ""; results = emptyList() }) { RowLabel(m.display, m.subtitle.ifEmpty { null }) }
                    if (i < results.lastIndex) RowDivider()
                }
            }
        }
        if (current == null && results.isEmpty()) item {
            Text("Search for a Bay County address to see who provides each utility and your trash day.", style = T.subhead, color = Brand.secondary)
        }
        if (current != null) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(current.display, style = T.title3, color = Brand.text)
                    Text(lookup?.let { if (it.area == "county") "Unincorporated Bay County" else "City of ${it.areaName}" } ?: current.subtitle, style = T.subhead, color = Brand.secondary)
                }
            }
            val l = lookup
            when {
                l != null -> utilitiesReport(l)
                failed -> item { Unavailable("Couldn't look up this address", "The map servers didn't answer. Pull to try again.") }
                else -> item { Loading() }
            }
        }
        item {
            CardList {
                RouteRow(Route.Dataset("utility-rates"), "Every utility charge", "Base fees, tiers, garbage and stormwater by city", symbol = "drop")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("utility-providers"), "Every provider", "By city and service", symbol = "bolt")
                RowDivider(50.dp)
                WebRow("Utilities on BayCounty.me", "https://baycounty.me/utilities", "Every city at a glance, outages and holiday schedules")
            }
        }
        item {
            Text("The address you look up isn't kept. Pickup days come from each city's route map; your bill names your electric provider.",
                style = T.footnote, color = Brand.secondary)
        }
    }
}

/** Trash-day cards, providers, holiday changes and the typical bill for one lookup. */
private fun androidx.compose.foundation.lazy.LazyListScope.utilitiesReport(l: UtilityLookup) {
    if (l.pickup.isNotEmpty()) item {
        PageSection("Trash day", symbol = "trash", tone = Tone.TEAL) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) { l.pickup.forEach { PickupCard(l, it) } }
        }
    }
    item {
        PageSection("Who provides what", symbol = "bolt", tone = Tone.BLUE) {
            val rows = l.otherServices.flatMap { s -> s.providers.mapIndexed { i, p -> Triple(s, i, p) } }
            CardList {
                rows.forEachIndexed { i, (s, idx, p) ->
                    ProviderRow(s, idx, p)
                    if (i < rows.lastIndex) RowDivider()
                }
            }
        }
    }
    if (l.holidays.isNotEmpty()) item {
        PageSection("Holiday changes", symbol = "calendar", tone = Tone.AMBER) {
            CardList {
                l.holidays.forEachIndexed { i, h ->
                    TextRow(h.holiday, listOfNotNull(h.whenObserved, h.garbage?.let { "Garbage: $it" }, h.yardWaste?.let { "Yard waste: $it" }).joinToString("\n"))
                    if (i < l.holidays.lastIndex) RowDivider()
                }
            }
        }
    }
    l.typicalBill?.let { bill -> item { CardList { FactRow("Typical water and sewer bill", "$" + "%.2f".format(Locale.US, bill), "5,000 gallons a month") } } }
}

@Composable
private fun PickupCard(l: UtilityLookup, p: UtilityLookup.Pickup) {
    val prov = l.provider(p)
    Column(Modifier.fillMaxWidth().card(16.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        EyebrowHeader(p.serviceLabel)
        p.days?.let { days ->
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(days, style = T.title3.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                p.zoneText?.let { Text("($it)", style = T.subhead, color = Brand.secondary) }
            }
            PickupDays.next(days)?.let { Text("Next: ${it.format(dayFormat)}", style = T.subhead, color = Brand.secondary) }
        }
        p.zoneArea?.let { Text(listOfNotNull(if (p.days == null) p.zone else null, it).joinToString(": "), style = T.caption, color = Brand.secondary) }
        p.rule?.let { Text(it, style = T.subhead, color = Brand.text) }
        p.notes?.let { Text(it, style = T.caption, color = Brand.secondary) }
        if (prov != null) {
            Text(prov.provider, style = T.subheadBold, color = Brand.text)
            ProviderLinks(prov)
        } else Text(p.provider, style = T.caption, color = Brand.secondary)
    }
}

@Composable
private fun ProviderRow(s: UtilityLookup.Service, index: Int, p: UtilityLookup.Provider) {
    val opener = rememberOpener()
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text((s.serviceLabel + if (s.providers.size > 1) (if (index == 0) " · most likely" else " · or") else "").uppercase(),
            style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Brand.secondary)
        val id = p.entityId?.split(":", limit = 2)?.takeIf { it.size == 2 }
        Text(p.provider, style = T.subheadBold, color = if (id != null) Brand.navy else Brand.text,
            modifier = if (id != null) Modifier.clickable { opener.openSite("/profile/${id[0]}/${id[1]}") } else Modifier)
        p.notes?.let { Text(it, style = T.caption, color = Brand.secondary) }
        ProviderLinks(p)
    }
}

@Composable
private fun ProviderLinks(p: UtilityLookup.Provider) {
    val opener = rememberOpener()
    val context = LocalContext.current
    Row(horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
        p.phone?.let { phone ->
            LinkLine(phone, "phone") {
                runCatching { context.startActivity(android.content.Intent(android.content.Intent.ACTION_DIAL, android.net.Uri.parse("tel:" + phone.filter { it.isDigit() || it == '+' }))) }
            }
        }
        p.website?.let { w -> LinkLine("Website", "safari") { opener.open(w) } }
        p.outageUrl?.takeIf { it != p.website }?.let { o -> LinkLine("Outages", "bolt") { opener.open(o) } }
    }
}

/** The utilities section on an address report: trash day, with a link to the full screen. */
@Composable
fun AddressUtilitiesSection(match: AddressMatch) {
    val store = LocalStore.current
    var lookup by remember(match.id) { mutableStateOf(store.utilities[match.id]) }
    var failed by remember(match.id) { mutableStateOf(false) }
    LaunchedEffect(match.id) {
        if (lookup == null) try { lookup = store.loadUtilities(match) } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) { failed = true }
    }
    FormSection("Utilities and trash day") {
        CardList {
            val l = lookup
            when {
                l != null -> {
                    l.pickup.forEach { p -> FactRow(p.serviceLabel, p.days ?: "See details", p.zoneText); RowDivider() }
                    l.otherServices.filter { it.service == "water" || it.service == "electric" }.forEach { s ->
                        FactRow(s.serviceLabel, s.providers.joinToString(" or ") { it.provider }); RowDivider()
                    }
                    RouteRow(Route.Utilities(match), "All utilities, phone numbers and holidays")
                }
                failed -> RouteRow(Route.Utilities(match), "The utility lookup didn't answer", "Try the utilities screen")
                else -> Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(Modifier.size(20.dp), color = Brand.navy, strokeWidth = 2.dp)
                    Text("Looking up utilities…", style = T.subhead, color = Brand.secondary)
                }
            }
        }
    }
}
