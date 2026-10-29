package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import me.baycounty.app.BuildConfig
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Dates
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Every term on the site, explained simply first. */
@Composable
fun GlossaryScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { if (store.glossary == null) store.loadGlossary() }
    var query by rememberSaveable { mutableStateOf("") }
    val g = store.glossary
    Screen("Glossary", onRefresh = { store.loadGlossary() }, spacing = 20) {
        if (g == null) {
            item { AppDataPending("glossary.json", "Couldn't load the glossary") { store.loadGlossary() } }
            return@Screen
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    "Government money comes with a lot of jargon. Here is every term on BayCounty.me, explained simply first, with more detail after.",
                    style = T.subhead, color = Brand.text,
                )
                FilterField(query, "Find a term") { query = it }
            }
        }
        val q = query.trim().lowercase()
        var any = false
        for (grp in g.groups) {
            val terms = g.terms.filter { it.group == grp.id && (q.isEmpty() || it.term.lowercase().contains(q) || it.simple.lowercase().contains(q)) }
            if (terms.isEmpty()) continue
            any = true
            item(key = grp.id) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    EyebrowHeader(grp.name)
                    CardList {
                        terms.forEachIndexed { i, t ->
                            Column(
                                Modifier.fillMaxWidth().clickable(role = Role.Button) { store.presentedTerm = t }.padding(horizontal = 14.dp, vertical = 10.dp),
                                verticalArrangement = Arrangement.spacedBy(3.dp),
                            ) {
                                Text(t.term, style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.text)
                                Text(t.simple, style = T.caption, color = Brand.secondary, maxLines = 3, overflow = TextOverflow.Ellipsis)
                            }
                            if (i < terms.lastIndex) RowDivider()
                        }
                    }
                }
            }
        }
        if (!any) item { Unavailable("No terms match", "Try a shorter word.", symbol = "magnifyingglass") }
    }
}

/** The site's change log. */
@Composable
fun UpdatesScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { if (store.updates.isEmpty()) store.loadUpdates() }
    Screen("What's new", onRefresh = { store.loadUpdates() }, spacing = 18) {
        if (store.updates.isEmpty()) item { AppDataPending("updates.json", "Couldn't load updates") { store.loadUpdates() } }
        for (u in store.updates) item(key = u.id) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader(Dates.parse(u.date)?.let { Dates.display(it, false) } ?: u.date)
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(u.title, style = T.headline, color = Brand.text)
                    Text(u.text, style = T.subhead, color = Brand.text)
                }
            }
        }
    }
}

/** What BayCounty.me is, where the information comes from, privacy and corrections. */
@Composable
fun AboutScreen() {
    val store = LocalStore.current
    val scope = rememberCoroutineScope()
    Screen("About", spacing = 20) {
        item {
            Text(
                "BayCounty.me is an independent, free website and app that puts Bay County, Florida public records in one place, in plain language: all nine local governments, their budgets, taxes, contracts, votes, campaign money and meetings, plus what's happening near your address. Every figure links to its public record, back to 2016. It is not run by any government.",
                style = T.subhead, color = Brand.text, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp),
            )
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("What the labels mean")
                val labels = listOf(
                    "Spent" to "Reported paid.",
                    "Committed" to "Awarded, not fully paid.",
                    "Budgeted / Proposed" to "Plans, not proof of payment.",
                    "Not in totals" to "Totals count each dollar once. Parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out.",
                )
                CardList {
                    labels.forEachIndexed { i, (t, d) ->
                        Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(t, style = T.subheadBold, color = Brand.text)
                            Text(d, style = T.footnote, color = Brand.secondary)
                        }
                        if (i < labels.lastIndex) RowDivider()
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("Who runs it")
                Text(
                    "Built and run by Flux Labs, a managed IT company in Panama City. We live and work here, and we built this so public records are easy to read without a records request. No ads, no tracking, and no money from any government, candidate or campaign.",
                    style = T.subhead, color = Brand.text, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp),
                )
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("Data")
                CardList {
                    store.catalog?.let { c ->
                        c.updated?.let { FactRow("Data updated", it); RowDivider() }
                        FactRow("Datasets", "${c.datasets.size}"); RowDivider()
                    }
                    store.lastRefresh?.let {
                        FactRow("Checked", DateTimeFormatter.ofPattern("MMM d, yyyy, h:mm a", Locale.US).withZone(ZoneId.systemDefault()).format(it)); RowDivider()
                    }
                    Row(
                        Modifier.fillMaxWidth().clickable(role = Role.Button) { scope.launch { store.refreshAll() } }.padding(horizontal = 14.dp, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Icon(icon("arrow.clockwise"), null, tint = Brand.navy, modifier = Modifier.size(22.dp))
                        Text("Check for new data", style = T.body, color = Brand.navy)
                    }
                }
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                EyebrowHeader("App")
                CardList { FactRow("Version", "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})") }
                ToggleRow("Share anonymous usage counts", store.shareUsage) { store.setShareUsage(it) }
                Text(
                    "Once a day the app sends how many times it was opened and which screens were viewed, with the app version. Nothing that identifies you or your phone is sent: no name, account, address or device id. It helps us see what residents use.",
                    style = T.caption, color = Brand.secondary, modifier = Modifier.padding(horizontal = 4.dp),
                )
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                CardList {
                    WebRow("Send a correction", "${BayCountyClient.SITE}/about#contact", symbol = "exclamationmark.bubble")
                    RowDivider(50.dp)
                    WebRow("Privacy", "${BayCountyClient.SITE}/privacy", symbol = "hand.raised")
                    RowDivider(50.dp)
                    WebRow("Sources and method", "${BayCountyClient.SITE}/about", symbol = "doc.text")
                    RowDivider(50.dp)
                    WebRow("baycounty.me", BayCountyClient.SITE, symbol = "safari")
                }
                Text(
                    "No ads and no tracking. The address saved on My Address stays on your phone. A My home account keeps only your email, home address and first name, to show what's near you, and you can delete it any time.",
                    style = T.caption, color = Brand.secondary, modifier = Modifier.padding(horizontal = 4.dp),
                )
            }
        }
        item { PoweredByFlux() }
    }
}
