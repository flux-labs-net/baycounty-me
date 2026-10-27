package me.baycounty.app.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.Volunteer
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.ZoneId

/** Volunteer (/volunteer): open volunteer needs from local nonprofits and the nonprofits that rely on volunteers, filtered
 *  by one plain cause. Same sections as the iOS VolunteerView. */
@Composable
fun VolunteerScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Volunteer.datasets) }
    val needs = store.rows["volunteer-needs"] ?: emptyList()
    val orgs = store.rows["volunteer-orgs"] ?: emptyList()
    val today = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    var cause by rememberSaveable { mutableStateOf("") }
    var allNeeds by rememberSaveable { mutableStateOf(false) }
    var allOrgs by rememberSaveable { mutableStateOf(false) }

    Screen("Volunteer", onRefresh = { Volunteer.datasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "Take part · Volunteer", "Volunteer in Bay County",
                "Local nonprofits looking for help right now, and the groups that rely on volunteers year-round.",
                symbol = "hand.raised", tone = Tone.TEAL,
            )
        }
        if (needs.isEmpty() && orgs.isEmpty()) {
            item {
                val e = Volunteer.datasets.firstNotNullOfOrNull { store.errors[it] }
                if (e != null) Unavailable("Couldn't load volunteer needs", e) else Loading()
            }
            return@Screen
        }
        val c = cause.ifEmpty { null }
        val open = Volunteer.open(needs, today, c)
        val list = Volunteer.orgs(orgs, c)
        item { Kpis(Volunteer.open(needs, today), orgs) }
        item {
            ChipRow(listOf("" to "All causes") + Volunteer.causesIn(needs, orgs).map { it to it }, cause) {
                cause = it; allNeeds = false; allOrgs = false
            }
        }
        item {
            PageSection("Open needs right now", "hand.raised", Tone.TEAL, "Sign up on the organization's board. Check the details there before you go.") {
                if (open.isEmpty()) {
                    Text("No open needs for this cause. Try another, or reach out to one of the nonprofits below.", style = T.subhead,
                         color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
                } else {
                    val shown = if (allNeeds) open else open.take(6)
                    CardList {
                        shown.forEachIndexed { i, r ->
                            NeedRow(r)
                            if (i < shown.lastIndex) RowDivider(14.dp)
                        }
                        if (open.size > 6) {
                            RowDivider(0.dp)
                            ShowMoreRow(allNeeds, "Show ${open.size - shown.size} more") { allNeeds = !allNeeds }
                        }
                    }
                }
            }
        }
        item {
            PageSection("Nonprofits that rely on volunteers", "heart.text.square", Tone.BLUE,
                        "Volunteer counts are each group's own estimate on its latest IRS Form 990.") {
                val shown = if (allOrgs) list else list.take(8)
                CardList {
                    shown.forEachIndexed { i, o ->
                        OrgRow(o)
                        if (i < shown.lastIndex) RowDivider(64.dp)
                    }
                    if (list.size > 8) {
                        RowDivider(0.dp)
                        ShowMoreRow(allOrgs, "Show ${list.size - shown.size} more") { allOrgs = !allOrgs }
                    }
                }
            }
        }
        item { HowToHelp() }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    RouteRow(Route.Dataset("nonprofits"), "All nonprofits", symbol = "heart.text.square")
                    RowDivider(50.dp)
                    WebRow("Volunteer on BayCounty.me", "${BayCountyClient.SITE}/volunteer", "Search every need and nonprofit", symbol = "safari")
                }
                FreshnessNote("volunteer-needs")
            }
        }
    }
}

@Composable
private fun Kpis(open: List<DataRow>, orgs: List<DataRow>) {
    val posting = open.mapNotNull { it.string("organization") }.toSet().size
    val local = open.count { it.string("nonprofit_id") != null }
    val reported = orgs.sumOf { it.number("volunteers_reported") ?: 0.0 }
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Open needs", "${open.size}", m, "From $posting organizations", "hand.raised", Tone.TEAL)
            1 -> KPICard("Posted by local nonprofits", "$local", m, "The rest are regional groups serving the county", "heart.text.square", Tone.SALMON)
            2 -> KPICard("Nonprofits that use volunteers", "${orgs.size}", m, "On their IRS filing, or posting a need now", "person.3", Tone.BLUE)
            else -> KPICard("Volunteers reported", Format.number(reported), m, "Latest Form 990s", "chart.bar", Tone.AMBER)
        }
    }
}

@Composable
private fun NeedRow(r: DataRow) {
    val opener = rememberOpener()
    Column(
        Modifier.fillMaxWidth().clickable { opener.open(r.url("url")) }.padding(horizontal = 14.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Badge(r.string("cause") ?: "", Brand.good)
            Badge(Volunteer.whenLabel(r), Brand.secondary)
        }
        Text(r.string("title") ?: "", style = T.subheadBold, color = Brand.text)
        Text(listOf(r.string("organization") ?: "", Volunteer.whereLabel(r)).joinToString(" · "), style = T.caption, color = Brand.secondary)
        r.string("description")?.let { Text(it, style = T.caption, color = Brand.text, maxLines = 3, overflow = TextOverflow.Ellipsis) }
        Text("Sign up via ${r.string("board") ?: "the board"}", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy)
    }
}

@Composable
private fun OrgRow(o: DataRow) {
    val opener = rememberOpener()
    val path = Volunteer.profilePath(o, "page_url")
    val nums = listOfNotNull(
        o.number("open_needs")?.takeIf { it > 0 }?.let { "${it.toInt()} open need" + if (it > 1) "s" else "" },
        o.number("volunteers_reported")?.let { "${Format.number(it)} volunteers" },
        o.string("city"),
    ).joinToString(" · ")
    Row(
        Modifier.fillMaxWidth().clickable { if (path != null) opener.openSite(path) else opener.open(o.url("website")) }
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        PersonInitials(o.string("name") ?: "", 38.dp)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(o.string("name") ?: "", style = T.subheadBold, color = Brand.text)
            Text(o.string("cause") ?: "", style = T.caption, color = Brand.good)
            if (nums.isNotEmpty()) Text(nums, style = T.caption, color = Brand.secondary)
        }
        Chevron()
    }
}

@Composable
private fun HowToHelp() {
    PageSection("How to help", "lightbulb", Tone.AMBER) {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            for ((b, rest) in listOf(
                "Pick a cause and a schedule." to " Ongoing roles like mentoring ask for a few hours a month; one-day events need no long commitment.",
                "Sign up with the organization." to " Roles with children or patients often ask for a background check and a short training first.",
                "No need listed?" to " Most nonprofits here take volunteers year-round. Visit their website and ask what they need.",
            )) {
                Text(buildAnnotatedString { withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(b) }; append(rest) }, style = T.subhead, color = Brand.text)
            }
        }
    }
}
