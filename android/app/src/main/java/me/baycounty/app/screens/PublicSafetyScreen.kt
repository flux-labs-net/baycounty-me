package me.baycounty.app.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Format
import me.baycounty.kit.PublicSafety
import me.baycounty.kit.Row as DataRow
import java.util.Locale
import kotlin.math.roundToInt

/** Police, fire and the Sheriff (/public-safety): who covers each town and what it costs, crimes each police agency
 *  reported to the FBI since 2016 (rates against Florida), the share solved, cost per resident and officers. Same
 *  sections as the iOS PublicSafetyView. Counts only: nothing here names a person. */
@Composable
fun PublicSafetyScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(PublicSafety.datasets) }
    val agencies = store.rows["safety-agencies"] ?: emptyList()
    val crimes = store.rows["crime-counts"] ?: emptyList()
    val staff = store.rows["police-staffing"] ?: emptyList()
    var town by rememberSaveable { mutableStateOf<String?>(null) }
    var offense by rememberSaveable { mutableStateOf(PublicSafety.Offense.VIOLENT) }

    Screen("Public safety", onRefresh = { PublicSafety.datasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "Living here · Police, fire and the Sheriff", "Police, fire and the Sheriff",
                "Who answers when you call 911 in each part of Bay County, what each police and fire department costs, how many crimes each police agency has reported since 2016, and how many officers they have.",
                symbol = "shield.lefthalf.filled", tone = Tone.BLUE,
            )
        }
        if (agencies.isEmpty()) {
            item { val e = PublicSafety.datasets.firstNotNullOfOrNull { store.errors[it] }; if (e != null) Unavailable("Couldn't load public safety", e) else Loading() }
            return@Screen
        }
        item { Kpis(agencies, crimes) }
        item { Explainer() }
        item { TownSection(agencies, crimes, staff, town) { town = it } }
        item { TrendSection(crimes, offense) { offense = it } }
        item { SolvedSection(crimes, offense) }
        item { CostSection(agencies) }
        item { StaffSection(staff) }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                CardList {
                    WebRow("Ask for police and fire records", "${BayCountyClient.SITE}/records", "Each agency's records contact", "doc.text")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("crime-counts"), "Every crime count", "What each agency reported to the FBI, by year", "tablecells")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("safety-agencies"), "Every department", "Budgets and who covers each town", "building.columns")
                }
                Text("Crime counts and staffing come from the FBI Crime Data Explorer, checked every week. Offenses known to police, not arrests or convictions. No Florida agency reported for 2021, Panama City Beach has not reported since 2020, and from 2025 agencies send monthly incident reports, so 2025 and later are not directly comparable.",
                    style = T.footnote, color = Brand.secondary)
                FreshnessNote("crime-counts")
            }
        }
    }
}

@Composable
private fun Kpis(agencies: List<DataRow>, crimes: List<DataRow>) {
    val t = PublicSafety.totals(agencies)
    val fy = PublicSafety.fiscalYear(agencies)
    val h = PublicSafety.headline(crimes)
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Police budgets, $fy", PublicSafety.money(t.police), m, "Including ${PublicSafety.money(t.contracts)} cities pay the Sheriff by contract", "shield", Tone.BLUE)
            1 -> KPICard("Fire budgets, $fy", PublicSafety.money(t.fire), m, "${t.fireDepartments} fire departments", "flame", Tone.SALMON)
            2 -> KPICard("Sworn officers", Format.number(t.officers), m, "Latest count each agency gave the FBI", "person.3", Tone.TEAL)
            else -> KPICard("Violent crimes, ${h?.year ?: ""}", h?.let { Format.number(it.violent) } ?: "—", m,
                h?.let { x -> listOfNotNull(x.violentChange?.let { "${if (it > 0) "+" else ""}$it% since ${x.firstYear}, same agencies" }, "${Format.number(x.property)} property crimes").joinToString("; ") },
                "chart.bar", Tone.AMBER)
        }
    }
}

@Composable
private fun Explainer() {
    PageSection("Who covers what", "info.circle", Tone.BLUE, "The simple version") {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Step(1, "The Sheriff covers the whole county.", "The Bay County Sheriff's Office patrols everywhere outside city limits, runs the county jail, and polices Callaway and Mexico Beach, which pay it by contract.")
            Step(2, "Five cities have their own police.", "Panama City, Panama City Beach, Lynn Haven, Springfield and Parker run police departments paid from their city budgets.")
            Step(3, "Every city has a fire department.", "Bay County Fire Rescue covers the unincorporated areas, paid by a fire fee on tax bills there.")
        }
    }
}

@Composable
private fun Step(n: Int, head: String, body: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Box(Modifier.size(22.dp).background(Brand.navyFill, CircleShape), contentAlignment = Alignment.Center) {
            Text("$n", style = T.caption.copy(fontWeight = FontWeight.Bold), color = Color.White)
        }
        Text(buildAnnotatedString { pushStyle(SpanStyle(fontWeight = FontWeight.SemiBold)); append(head); pop(); append(" $body") }, style = T.subhead, color = Brand.text)
    }
}

@Composable
private fun Eyebrow(text: String) = Text(text.uppercase(), style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = Brand.secondary)

@Composable
private fun TownSection(agencies: List<DataRow>, crimes: List<DataRow>, staff: List<DataRow>, picked: String?, onPick: (String) -> Unit) {
    val towns = PublicSafety.towns(agencies)
    val pick = towns.firstOrNull { it.id == (picked ?: towns.first().id) } ?: towns.first()
    val crime = PublicSafety.townCrime(pick, crimes)
    PageSection("Your town", "mappin.and.ellipse", Tone.TEAL, "Pick where you live") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(towns.map { it.id to it.name }, pick.id) { onPick(it) }
            TownCard("Police", pick.police, pick.police?.let { PublicSafety.staffing(staff, it.string("agency_id") ?: "") })
            TownCard("Fire", pick.fire, null)
            Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Eyebrow(if (crime.sheriffCovers) "Crimes reported by ${crime.agencyName}" else "Crimes reported")
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    CrimeStat(crime.violent, "violent", crime.year, Modifier.weight(1f))
                    CrimeStat(crime.property, "property", crime.year, Modifier.weight(1f))
                }
                crime.year?.takeIf { it < 2024 }?.let {
                    Text("${crime.agencyName.replaceFirstChar { c -> c.uppercase() }} has not sent the FBI a full year since $it.", style = T.caption, color = Brand.secondary)
                }
                if (crime.sheriffCovers) Text("${pick.name} is policed by the Sheriff, so its crimes are counted in the Sheriff's numbers for all the areas it patrols.", style = T.caption, color = Brand.secondary)
            }
            CardList { RouteRow(Route.Gov(pick.id), pick.name, "Budget, officials, meetings and votes", "building.columns") }
        }
    }
}

@Composable
private fun TownCard(label: String, r: DataRow?, officers: DataRow?) {
    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp).semantics(mergeDescendants = true) {}, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Eyebrow(label)
        Text(r?.string("agency") ?: "—", style = T.headline, color = Brand.text)
        r?.string("arrangement")?.let { Text(it, style = T.caption, color = Brand.secondary) }
        r?.number("cost_per_resident")?.let { c ->
            Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(Format.money(Math.round(c).toDouble()), style = T.number, color = Brand.text)
                Text("per resident, ${r.string("budget_fiscal_year") ?: ""}", style = T.caption, color = Brand.secondary, modifier = Modifier.padding(bottom = 3.dp))
            }
        }
        val y = officers?.number("year")
        val n = officers?.number("officers")
        if (y != null && y >= 2023 && n != null) {
            val per = officers.number("population")?.let { String.format(Locale.US, ", %.1f officers per 1,000 people", 1000 * n / it) } ?: ""
            Text("${Format.number(n)} sworn officers and ${Format.number(officers.number("civilians") ?: 0.0)} civilian staff in ${y.toInt()}$per.", style = T.caption, color = Brand.secondary)
        }
    }
}

@Composable
private fun CrimeStat(r: DataRow?, noun: String, year: Int?, modifier: Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(3.dp)) {
        val rate = r?.number("per_1000")
        if (r != null && rate != null && year != null) {
            Text(Format.number(rate), style = T.number, color = Brand.text)
            Text("$noun per 1,000 people, $year", style = T.caption, color = Brand.secondary)
            Text("${Format.number(r.number("count") ?: 0.0)} reported${PublicSafety.versusFlorida(r)?.let { "; $it" } ?: ""}.", style = T.caption, color = Brand.secondary)
        } else {
            Text("No full year of $noun crime reported to the FBI.", style = T.caption, color = Brand.secondary)
        }
    }
}

@Composable
private fun TrendSection(crimes: List<DataRow>, offense: PublicSafety.Offense, onOffense: (PublicSafety.Offense) -> Unit) {
    val t = PublicSafety.trends(crimes, offense)
    val top = PublicSafety.trendMax(t) * 1.1
    val years = t.flatMap { tr -> tr.points.map { it.year } }
    val lo = years.minOrNull() ?: 2016
    val hi = years.maxOrNull() ?: 2025
    PageSection("Crime over time", "chart.xyaxis.line", Tone.AMBER, "Crimes reported per 1,000 people, full years only") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(PublicSafety.Offense.entries.map { it to it.label }, offense) { onOffense(it) }
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.width(14.dp).height(3.dp).background(Brand.navy, RoundedCornerShape(2.dp)))
                Text("The agency", style = T.caption, color = Brand.secondary)
                Box(Modifier.width(14.dp).height(2.dp).background(Brand.secondary))
                Text("Florida (dashed)", style = T.caption, color = Brand.secondary)
            }
            Grid2(t) { a, m ->
                Column(m.card(12.dp).padding(10.dp).semantics(mergeDescendants = true) {
                    contentDescription = "${a.name}: " + a.points.joinToString(", ") { "${it.year} ${Format.number(it.rate)}" }
                }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(a.name, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, maxLines = 2)
                    Text("Latest ${a.points.lastOrNull()?.year ?: ""}: ${a.points.lastOrNull()?.let { Format.number(it.rate) } ?: "—"}", style = T.caption2, color = Brand.secondary)
                    RatePanel(a.points, lo, hi, top)
                    Row(Modifier.fillMaxWidth()) {
                        Text("$lo", style = T.caption2, color = Brand.secondary, modifier = Modifier.weight(1f))
                        Text("$hi", style = T.caption2, color = Brand.secondary)
                    }
                }
            }
            Text("Every panel uses the same scale. Gaps are years the agency sent the FBI nothing. Panama City Beach's rate counts only residents, not the visitors police there also serve.",
                style = T.footnote, color = Brand.secondary)
        }
    }
}

/** One agency's rate line (broken at missing years) over Florida's dashed line, on a shared scale. */
@Composable
private fun RatePanel(points: List<PublicSafety.RatePoint>, lo: Int, hi: Int, top: Double) {
    val navy = Brand.navy
    val ref = Brand.secondary
    val grid = Brand.hairline
    Canvas(Modifier.fillMaxWidth().height(80.dp).clearAndSetSemantics {}) {
        val x = { y: Int -> if (hi == lo) size.width / 2 else (y - lo) * size.width / (hi - lo) }
        val yv = { v: Double -> (size.height * (1 - v / top)).toFloat() }
        for (f in listOf(0.0, 0.5, 1.0)) drawLine(grid, Offset(0f, yv(top * f)), Offset(size.width, yv(top * f)), 1f)
        val dash = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))
        points.zipWithNext().forEach { (a, b) ->
            val fa = a.florida
            val fb = b.florida
            if (b.year == a.year + 1 && fa != null && fb != null) drawLine(ref, Offset(x(a.year), yv(fa)), Offset(x(b.year), yv(fb)), 2f, pathEffect = dash)
            if (b.year == a.year + 1) drawLine(navy, Offset(x(a.year), yv(a.rate)), Offset(x(b.year), yv(b.rate)), 4f)
        }
        points.forEach { drawCircle(navy, 5f, Offset(x(it.year), yv(it.rate))) }
    }
}

@Composable
private fun Bar(label: String?, sub: String?, share: Double, value: String, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        if (label != null) Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
            Text(label, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
            if (sub != null) Text(sub, style = T.caption2, color = Brand.secondary)
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.weight(1f).height(12.dp).background(Brand.sunken, RoundedCornerShape(4.dp))) {
                Box(Modifier.fillMaxWidth(share.toFloat().coerceIn(0.01f, 1f)).height(12.dp).background(color, RoundedCornerShape(4.dp)))
            }
            Text(value, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, modifier = Modifier.width(52.dp), textAlign = TextAlign.End)
        }
    }
}

@Composable
private fun SolvedSection(crimes: List<DataRow>, offense: PublicSafety.Offense) {
    val list = PublicSafety.solved(crimes, offense)
    PageSection("Share of crimes solved", "checkmark.seal", Tone.TEAL, "${offense.label}: cleared by arrest or otherwise closed, each agency's latest three yearly reports") {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            list.forEach { b ->
                Box(Modifier.semantics(mergeDescendants = true) { contentDescription = "${b.name}: ${b.cleared} of ${b.count} cleared, ${b.span}" }) {
                    Bar(b.name, b.span, b.share, "${(b.share * 100).roundToInt()}%", Brand.navy)
                }
            }
            Text("Uses the switch above. Agencies with fewer than 20 crimes in those years are left out.", style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun CostSection(agencies: List<DataRow>) {
    val list = PublicSafety.perResident(agencies)
    val top = list.flatMap { listOf(it.police ?: 0.0, it.fire ?: 0.0) }.maxOrNull() ?: 1.0
    PageSection("What police and fire cost per resident", "dollarsign.circle", Tone.AMBER, "${PublicSafety.fiscalYear(agencies)} budgets") {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(Brand.navy, RoundedCornerShape(2.dp))); Text("Police", style = T.caption, color = Brand.secondary)
                Box(Modifier.size(10.dp).background(Brand.salmon, RoundedCornerShape(2.dp))); Text("Fire", style = T.caption, color = Brand.secondary)
            }
            list.forEach { r ->
                Column(verticalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.semantics(mergeDescendants = true) {
                    contentDescription = "${r.name}: police ${r.police?.let { Format.money(Math.round(it).toDouble()) } ?: "none"}, fire ${r.fire?.let { Format.money(Math.round(it).toDouble()) } ?: "none"} per resident"
                }) {
                    Text(r.name, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
                    r.police?.let { Bar(null, null, it / top, Format.money(Math.round(it).toDouble()), Brand.navy) }
                    r.fire?.let { Bar(null, null, it / top, Format.money(Math.round(it).toDouble()), Brand.salmon) }
                }
            }
            Text("The budget divided by the people it serves: each city's residents, the whole county for the Sheriff (it runs the jail for everyone), and the unincorporated county for Bay County Fire Rescue. Beach towns serve many visitors who are not counted as residents.",
                style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun StaffSection(staff: List<DataRow>) {
    val list = PublicSafety.staffingSummary(staff)
    PageSection("Police officers and staff", "person.3", Tone.BLUE, "Sworn officers on October 31 each year, with civilian staff") {
        CardList {
            list.forEachIndexed { i, s ->
                TextRow(s.name, "${Format.number(s.civilians)} civilian staff, ${s.year} · ${Format.number(s.firstOfficers)} officers in ${s.firstYear}", Format.number(s.officers))
                if (i < list.lastIndex) RowDivider()
            }
        }
    }
}
