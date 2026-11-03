package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Format
import me.baycounty.kit.SchoolDetails
import me.baycounty.kit.Schools
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Public schools (/schools): the district calendar, every public school, enrollment since 2016, closed schools and the
 *  School Board. Zoned schools for an address are on My Address. Same sections as the iOS SchoolsView. */
@Composable
fun SchoolsScreen() {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.load(Schools.datasets); store.load(SchoolDetails.ZONES) }
    val schools = store.rows["schools"] ?: emptyList()
    val calendar = store.rows["school-calendar"] ?: emptyList()
    val enrollment = store.rows["school-enrollment"] ?: emptyList()
    val grades = store.rows["school-grades"] ?: emptyList()
    val state = store.rows["school-grade-state"] ?: emptyList()
    val spend = store.rows["school-spending"] ?: emptyList()
    val bell = store.rows["school-bell-times"] ?: emptyList()
    val zoneRows = store.rows[SchoolDetails.ZONES] ?: emptyList()
    var zoneLevel by rememberSaveable { mutableStateOf("None") }
    var showAllSpending by rememberSaveable { mutableStateOf(false) }
    val today = LocalDate.now(ZoneId.of("America/Chicago")).toString()
    var kind by rememberSaveable { mutableStateOf(Schools.Kind.ALL) }
    var filter by rememberSaveable { mutableStateOf(Schools.Filter.ALL) }
    var query by rememberSaveable { mutableStateOf("") }
    var showAll by rememberSaveable { mutableStateOf(false) }
    var open by rememberSaveable { mutableStateOf<String?>(null) }

    Screen("Schools", onRefresh = { Schools.datasets.forEach { store.load(it, force = true) } }, spacing = 22) {
        item {
            PageHero(
                "Governments · Bay District Schools", "Public schools",
                "Find the schools zoned for your address, see what's coming up on the school calendar, and compare every public school in Bay County: grades, students, spending and how each has changed since 2016.",
                symbol = "graduationcap", tone = Tone.BLUE,
            )
        }
        if (schools.isEmpty()) {
            item { val e = store.errors["schools"]; if (e != null) Unavailable("Couldn't load the schools", e) else Loading() }
            return@Screen
        }
        item { Kpis(schools, calendar, enrollment, grades, today) }
        item {
            CardList {
                val home = store.home
                if (home != null) {
                    RouteRow(Route.Address(home), "Schools zoned for your home", home.display, symbol = "house")
                    RowDivider(50.dp)
                    RouteRow(Route.MyAddress, "Another address", "Zoned schools for any Bay County address", symbol = "magnifyingglass")
                } else RouteRow(Route.MyAddress, "Which schools serve your address", "Your zoned elementary, middle and high school", symbol = "mappin.and.ellipse")
            }
        }
        item { MapSection(schools, zoneRows, zoneLevel, onLevel = { zoneLevel = it }) { id -> open = id; filter = Schools.Filter.ALL; query = "" } }
        item { CalendarSection(calendar, bell, today, kind, showAll, onKind = { kind = it; showAll = false }, onMore = { showAll = !showAll }) }
        item {
            SchoolsSection(schools, enrollment, grades, Extras(state, spend, bell), filter, query, open,
                onFilter = { filter = it }, onQuery = { query = it }, onOpen = { open = if (open == it) null else it })
        }
        item { GradesSection(grades, state) }
        item { SpendingSection(spend, schools, showAllSpending) { showAllSpending = true } }
        item { EnrollmentSection(enrollment) }
        item { ClosedSection(schools) }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                PageSection("Who runs the schools", "person.3", Tone.BLUE, "An elected five-member School Board and an elected superintendent") {
                    CardList {
                        RouteRow(Route.Gov("schools"), "Bay District Schools", "Budget, debt, audits, board members and meetings", symbol = "building.columns")
                        RowDivider(50.dp)
                        RouteRow(Route.Dataset("votes", mapOf("board" to "Bay District School Board")), "How the board voted", symbol = "hand.raised")
                    }
                }
                FreshnessNote("school-calendar")
            }
        }
    }
}

@Composable
private fun Kpis(schools: List<DataRow>, calendar: List<DataRow>, enrollment: List<DataRow>, grades: List<DataRow>, today: String) {
    val open = Schools.open(schools)
    val charter = open.count { it.bool("charter") == true }
    val total = Schools.districtEnrollment(enrollment).lastOrNull()
    val off = Schools.nextDayOff(calendar, today)
    val counts = SchoolDetails.gradeCounts(schools, grades)
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Public schools", "${open.size}", m, "${open.size - charter} run by the district, $charter charter schools", "graduationcap", Tone.AMBER)
            1 -> KPICard("Students" + (total?.let { ", ${it.first}" } ?: ""), total?.let { Format.number(it.second) } ?: "—", m,
                "Enrolled in the fall, from the federal school directory", "person.3", Tone.BLUE)
            2 -> if (counts != null) KPICard("A schools, ${SchoolDetails.yearLabel(counts.year)}", "${counts.a}", m,
                "of ${counts.graded} graded. ${counts.b} B, ${counts.c} C, ${counts.df} D or F", "star", Tone.TEAL)
            else KPICard("State school grades", "—", m, "Being added from the Florida Department of Education", "star", Tone.TEAL)
            else -> KPICard("Next day off", off?.let(Schools::date)?.format(DateTimeFormatter.ofPattern("MMM d", Locale.US)) ?: "—", m,
                off?.string("title"), "calendar", Tone.SALMON)
        }
    }
}

@Composable
private fun CalendarSection(calendar: List<DataRow>, bell: List<DataRow>, today: String, kind: Schools.Kind, showAll: Boolean, onKind: (Schools.Kind) -> Unit, onMore: () -> Unit) {
    val list = Schools.upcoming(calendar, today, kind)
    val shown = if (showAll) list else list.take(6)
    PageSection("School calendar", "calendar", Tone.SALMON, "From the district's calendar, checked daily") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(Schools.Kind.entries.map { it to it.label }, kind) { onKind(it) }
            if (list.isEmpty()) {
                Text("Nothing coming up in this group.", style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp))
            } else {
                CardList {
                    shown.forEachIndexed { i, ev ->
                        EventRow(ev)
                        if (i < shown.lastIndex) RowDivider(72.dp)
                    }
                    if (list.size > 6) {
                        RowDivider(0.dp)
                        ShowMoreRow(showAll, "Show ${list.size - shown.size} more", onMore)
                    }
                }
            }
            SchoolDetails.earlyRelease(bell)?.let {
                Text("Early release days (${SchoolDetails.bellYear(bell) ?: ""}): $it. Each school's start and end times are under Every public school.", style = T.footnote, color = Brand.secondary)
            }
            CardList { WebRow("The district's full calendar", "https://www.bay.k12.fl.us/o/bds/page/academic-calendar", symbol = "safari") }
        }
    }
}

private val month = DateTimeFormatter.ofPattern("MMM", Locale.US)
private val dayNum = DateTimeFormatter.ofPattern("d", Locale.US)
private val weekday = DateTimeFormatter.ofPattern("EEE", Locale.US)

@Composable
private fun EventRow(ev: DataRow) {
    val d = Schools.date(ev)
    val k = ev.string("kind") ?: ""
    val color = when (k) { "no-school", "break" -> Brand.salmon; "board-meeting" -> Brand.navy; else -> Brand.good }
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(
            Modifier.width(48.dp).background(Brand.surface, RoundedCornerShape(10.dp)).border(1.dp, Brand.hairline, RoundedCornerShape(10.dp)),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                d?.format(month)?.uppercase() ?: "", style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Color.White, textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().background(Brand.salmonFill, RoundedCornerShape(topStart = 10.dp, topEnd = 10.dp)).padding(vertical = 2.dp),
            )
            Text(d?.format(dayNum) ?: "", style = T.number, color = Brand.text)
            Text(d?.format(weekday) ?: "", style = T.caption2, color = Brand.secondary, modifier = Modifier.padding(bottom = 4.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(ev.string("title") ?: "", style = T.subheadBold, color = Brand.text)
            Text(Schools.whenLabel(ev), style = T.caption, color = Brand.secondary)
            ev.string("venue")?.let { Text(it, style = T.caption, color = Brand.secondary) }
            Badge(Schools.kindLabel(k), color)
        }
    }
}

@Composable
private fun SchoolsSection(
    schools: List<DataRow>, enrollment: List<DataRow>, grades: List<DataRow>, extras: Extras, filter: Schools.Filter, query: String, open: String?,
    onFilter: (Schools.Filter) -> Unit, onQuery: (String) -> Unit, onOpen: (String) -> Unit,
) {
    val list = Schools.open(schools, filter, query)
    PageSection("Every public school", "graduationcap", Tone.AMBER, "${list.size} schools · tap one for its details") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(Schools.Filter.entries.map { it to it.label }, filter) { onFilter(it) }
            FilterField(query, "Find a school or city", onQuery)
            CardList {
                list.forEachIndexed { i, s ->
                    SchoolRow(s, enrollment, grades, extras, open == s.string("school_id")) { onOpen(s.string("school_id") ?: "") }
                    if (i < list.lastIndex) RowDivider(64.dp)
                }
            }
            Text("The letter is the school's latest Florida school grade. Students are from the federal school directory.", style = T.footnote, color = Brand.secondary)
        }
    }
}

/** The datasets a school's details read beyond the list itself. */
private class Extras(val state: List<DataRow>, val spend: List<DataRow>, val bell: List<DataRow>)

@Composable
private fun gradeColor(g: String?): Color = when (g) { "A" -> Brand.good; "B" -> Brand.blue; "C" -> Brand.amber; "D", "F" -> Brand.salmon; else -> Brand.secondary }

/** A school's letter grade in its grade color (A teal, B blue, C amber, D or F salmon). */
@Composable
private fun GradeBadge(grade: String?, size: Int = 36) {
    val c = gradeColor(grade)
    Box(Modifier.size(size.dp).background((if (grade == null) Brand.hairline else c).copy(alpha = 0.2f), RoundedCornerShape((size / 4).dp))
        .semantics { contentDescription = grade?.let { "Grade $it" } ?: "No grade" }, contentAlignment = Alignment.Center) {
        Text(grade ?: "–", style = if (size > 30) T.headline else T.caption.copy(fontWeight = FontWeight.Bold), color = c)
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun SchoolRow(s: DataRow, enrollment: List<DataRow>, grades: List<DataRow>, x: Extras, expanded: Boolean, onTap: () -> Unit) {
    val opener = rememberOpener()
    val id = s.string("school_id") ?: ""
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth().clickable(onClick = onTap), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            GradeBadge(s.string("latest_grade"))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(s.string("name") ?: "", style = T.subheadBold, color = Brand.text)
                Text(Schools.subtitle(s), style = T.caption, color = Brand.secondary)
            }
            Text(if (expanded) "▴" else "▾", style = T.caption, color = Brand.tertiary)
        }
        if (expanded) {
            val sp = SchoolDetails.spending(x.spend, id)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Fact("Students" + (s.string("enrollment_year")?.let { ", $it" } ?: ""), s.number("enrollment")?.let { Format.number(it) } ?: "—", Modifier.weight(1f))
                Fact("Per teacher", s.number("students_per_teacher")?.let { Format.number(it) } ?: "—", Modifier.weight(1f))
                Fact("Spent per student" + (sp?.let { ", ${SchoolDetails.yearLabel(it.first)}" } ?: ""), sp?.let { Format.money(Math.round(it.second).toDouble()) } ?: "—", Modifier.weight(1f))
            }
            val g = Schools.grades(grades, id)
            if (g.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.semantics { contentDescription = "State grades: " + g.joinToString(", ") { "${(it.number("year") ?: 0.0).toInt()} ${it.string("grade") ?: ""}" } }) {
                    Text("State grades", style = T.caption, color = Brand.secondary)
                    androidx.compose.foundation.layout.FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        g.reversed().forEach { r ->
                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                GradeBadge(r.string("grade"), 26)
                                Text("${(r.number("year") ?: 0.0).toInt()}", fontSize = 10.sp, color = Brand.secondary)
                            }
                        }
                    }
                }
            }
            SchoolDetails.scores(grades, x.state, id)?.let { ScoreBars(it) }
            val ys = Schools.enrollment(enrollment, id)
            if (ys.size > 1) Text("Students: ${Format.number(ys.first().second)} in ${ys.first().first}, ${Format.number(ys.last().second)} in ${ys.last().first}", style = T.caption, color = Brand.secondary)
            SchoolDetails.hours(x.bell, id)?.let { h ->
                Text(androidx.compose.ui.text.buildAnnotatedString {
                    pushStyle(androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.SemiBold)); append("School day ${SchoolDetails.bellYear(x.bell) ?: ""}: "); pop(); append(h)
                }, style = T.caption, color = Brand.text)
            }
            s.number("free_reduced_lunch_pct")?.let { Text("${Format.number(Math.round(it).toDouble())}% of students qualify for free or reduced-price lunch.", style = T.caption, color = Brand.secondary) }
            CardList {
                SchoolDetails.mapsURL(s)?.let { u ->
                    Box(Modifier.clickable { opener.open(u) }) { RowLabel(listOfNotNull(s.string("address"), s.string("city")).joinToString(", "), "Open in Maps", "map") }
                    RowDivider(50.dp)
                }
                SchoolDetails.phone(s)?.let { (label, tel) ->
                    Box(Modifier.clickable { opener.open(tel) }) { RowLabel(label, "Call the school", "phone") }
                    RowDivider(50.dp)
                }
                Box(Modifier.clickable { opener.openSite(Schools.pagePath(s)) }) { RowLabel("On BayCounty.me", symbol = "safari") }
            }
        }
    }
}

/** The parts of a school's grade: a bar per score with a mark for the Florida average, and the change from the year before. */
@Composable
private fun ScoreBars(sc: SchoolDetails.Scores) {
    Column(Modifier.fillMaxWidth().background(Brand.hairline.copy(alpha = 0.2f), RoundedCornerShape(12.dp)).padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(sc.title, style = T.caption, color = Brand.secondary)
        sc.items.forEach { it ->
            Row(Modifier.fillMaxWidth().semantics(mergeDescendants = true) {
                contentDescription = "${it.label}: ${Math.round(it.value)} percent" + (it.state?.let { s -> ", Florida ${Math.round(s)}" } ?: "")
            }, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(it.label, style = T.caption2, color = Brand.text, modifier = Modifier.width(104.dp), maxLines = 2)
                androidx.compose.foundation.layout.BoxWithConstraints(Modifier.weight(1f).height(8.dp)) {
                    val w = maxWidth
                    Box(Modifier.fillMaxWidth().height(8.dp).background(Brand.hairline.copy(alpha = 0.5f), RoundedCornerShape(4.dp)))
                    Box(Modifier.width(w * (it.value.coerceAtMost(100.0) / 100).toFloat()).height(8.dp).background(Brand.navy, RoundedCornerShape(4.dp)))
                    it.state?.let { st ->
                        Box(Modifier.padding(start = (w * (st.coerceAtMost(100.0) / 100).toFloat() - 1.dp).coerceAtLeast(0.dp)).width(2.dp).height(8.dp).background(Brand.salmon))
                    }
                }
                Text("${Math.round(it.value)}%", style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, modifier = Modifier.width(34.dp), textAlign = TextAlign.End)
                val ch = it.change
                Text(when { ch == null -> ""; ch > 0 -> "+$ch"; ch == 0 -> "±0"; else -> "$ch" }, style = T.caption2,
                    color = when { (ch ?: 0) > 0 -> Brand.good; (ch ?: 0) < 0 -> Brand.salmon; else -> Brand.secondary },
                    modifier = Modifier.width(26.dp), textAlign = TextAlign.End)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(14.dp).height(6.dp).background(Brand.navy, RoundedCornerShape(3.dp)))
            Text("This school", style = T.caption2, color = Brand.secondary)
            Box(Modifier.width(2.dp).height(10.dp).background(Brand.salmon))
            Text(sc.stateLabel, style = T.caption2, color = Brand.secondary)
        }
    }
}

/** Every open school as a dot colored by its latest grade, with one level's attendance zones drawn under them. */
@Composable
private fun MapSection(schools: List<DataRow>, zoneRows: List<DataRow>, level: String, onLevel: (String) -> Unit, onPick: (String) -> Unit) {
    val dots = Schools.open(schools).mapNotNull { s ->
        val lat = s.number("latitude") ?: return@mapNotNull null
        val lon = s.number("longitude") ?: return@mapNotNull null
        MapDot(s.string("school_id") ?: "${s.id}", (s.string("name") ?: "") + (s.string("latest_grade")?.let { ", grade $it" } ?: ""), lat, lon, gradeColor(s.string("latest_grade")), s)
    }
    val zones = if (level == "None") emptyList() else SchoolDetails.zones(zoneRows, level)
    PageSection("Map of every school", "map", Tone.BLUE, "Colored by the latest state grade") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            ChipRow(listOf("None" to "No zones", "Elementary" to "Elementary zones", "Middle" to "Middle", "High" to "High"), level) { onLevel(it) }
            PointsMap(dots, Modifier.fillMaxWidth().height(280.dp), zones) { d -> d.row?.string("school_id")?.let(onPick) }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                listOf("A" to "A", "B" to "B", "C" to "C", "D" to "D or F", "" to "No grade").forEach { (g, label) ->
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(9.dp).background(gradeColor(g.ifEmpty { null }), RoundedCornerShape(5.dp)))
                        Text(label, style = T.caption, color = Brand.secondary)
                    }
                }
            }
            Text("Tap a school to open it below. Zones are the county's attendance zones; your own zoned schools are on My Address.", style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun GradesSection(grades: List<DataRow>, state: List<DataRow>) {
    val y = SchoolDetails.latestGradeYear(grades) ?: return
    val (local, fl) = SchoolDetails.gradeMix(grades, state, y)
    PageSection("School grades", "star", Tone.TEAL, "Florida Department of Education") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (fl != null) {
                Text(androidx.compose.ui.text.buildAnnotatedString {
                    append("In ${SchoolDetails.yearLabel(y)}, ")
                    pushStyle(androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold)); append("${Math.round(SchoolDetails.aShare(local))}%"); pop()
                    append(" of Bay County's graded public schools earned an A, compared with ")
                    pushStyle(androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold)); append("${Math.round(SchoolDetails.aShare(fl))}%"); pop()
                    append(" of schools statewide. Open a school above to see the test scores behind its grade next to the Florida average.")
                }, style = T.subhead, color = Brand.text)
                Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    GradeMixBar("Bay County", local)
                    GradeMixBar("Florida", fl)
                }
            }
            Text("No school grades were given for 2019-20, when state testing was canceled. For 2020-21, only schools that asked got a grade. 2022-23 grades were an informational baseline after the state changed its tests.",
                style = T.footnote, color = Brand.secondary)
        }
    }
}

/** Grades A to F as one stacked bar, like the site's grade mix. */
@Composable
private fun GradeMixBar(label: String, mix: Map<String, Int>) {
    val n = mix.values.sum().coerceAtLeast(1)
    Column(verticalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.semantics(mergeDescendants = true) {
        contentDescription = "$label: " + listOf("A", "B", "C", "D", "F").joinToString(", ") { "$it ${mix[it] ?: 0}" }
    }) {
        Text("$label · ${Format.number(mix.values.sum())} schools", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
        Row(Modifier.fillMaxWidth().height(22.dp).background(Brand.sunken, RoundedCornerShape(6.dp)), horizontalArrangement = Arrangement.spacedBy(1.dp)) {
            listOf("A", "B", "C", "D", "F").forEach { g ->
                val c = mix[g] ?: 0
                if (c > 0) {
                    val share = c.toFloat() / n
                    Box(Modifier.weight(share).height(22.dp).background(gradeColor(g).copy(alpha = 0.3f)), contentAlignment = Alignment.Center) {
                        if (share >= 0.1f) Text("$g ${Math.round(share * 100)}%", style = T.caption2.copy(fontWeight = FontWeight.SemiBold), color = gradeColor(g), maxLines = 1)
                    }
                }
            }
        }
    }
}

@Composable
private fun SpendingSection(spend: List<DataRow>, schools: List<DataRow>, showAll: Boolean, onShowAll: () -> Unit) {
    val r = SchoolDetails.spendingRanking(spend, schools) ?: return
    val top = r.rows.firstOrNull()?.perStudent ?: return
    val shown = if (showAll) r.rows else r.rows.take(10)
    PageSection("Spending per school", "dollarsign.circle", Tone.AMBER, "Per-pupil expenditure reports") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(androidx.compose.ui.text.buildAnnotatedString {
                append("What each school spent per student in ${SchoolDetails.yearLabel(r.year)}, counting federal, state and local money. Across these schools the average was about ")
                pushStyle(androidx.compose.ui.text.SpanStyle(fontWeight = FontWeight.Bold)); append(Format.money(Math.round(r.average).toDouble())); pop()
                append(" per student. Schools for students with disabilities, alternative schools and small schools cost more per student.")
            }, style = T.subhead, color = Brand.text)
            CardList {
                shown.forEachIndexed { i, x ->
                    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(Modifier.fillMaxWidth()) {
                            Text(x.name, style = T.caption, color = Brand.text, maxLines = 1, modifier = Modifier.weight(1f))
                            Text(Format.money(Math.round(x.perStudent).toDouble()), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
                        }
                        Box(Modifier.fillMaxWidth((x.perStudent / top).toFloat().coerceAtLeast(0.02f)).height(6.dp).background(Brand.amber, RoundedCornerShape(3.dp)))
                    }
                    if (i < shown.lastIndex) RowDivider(14.dp)
                }
                if (r.rows.size > shown.size) {
                    RowDivider(0.dp)
                    ShowMoreRow(false, "Show all ${r.rows.size} schools", onShowAll)
                }
            }
            CardList { RouteRow(Route.Overlaps, "Where records overlap", "School spending next to grades, and more", symbol = "point.3.connected.trianglepath.dotted") }
        }
    }
}

@Composable
private fun Fact(label: String, value: String, modifier: Modifier) {
    Column(modifier.background(Brand.hairline.copy(alpha = 0.35f), RoundedCornerShape(12.dp)).padding(horizontal = 10.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = T.caption2, color = Brand.secondary, maxLines = 2)
        Text(value, style = T.subheadBold, color = Brand.text)
    }
}

@Composable
private fun EnrollmentSection(enrollment: List<DataRow>) {
    val ys = Schools.districtEnrollment(enrollment)
    val hi = ys.maxOfOrNull { it.second } ?: 1.0
    PageSection("Students by year", "chart.bar", Tone.BLUE, "Every public school, fall enrollment") {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                Modifier.fillMaxWidth().card(14.dp).padding(14.dp).semantics { contentDescription = ys.joinToString(", ") { "${it.first}: ${Format.number(it.second)}" } },
                horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Bottom,
            ) {
                for ((y, n) in ys) {
                    Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(String.format(Locale.US, "%.1fK", n / 1000), fontSize = 9.sp, fontWeight = FontWeight.SemiBold, color = Brand.text, maxLines = 1)
                        Box(Modifier.fillMaxWidth().height((110 * n / hi).coerceAtLeast(4.0).dp)
                            .background(if (y == "2019-20" || y == "2020-21") Brand.salmon else Brand.navy, RoundedCornerShape(4.dp)))
                        Text(y.takeLast(2), fontSize = 9.sp, color = Brand.secondary)
                    }
                }
            }
            Text("Red: the two school years after Hurricane Michael (October 2018), when enrollment fell and several schools closed or merged.", style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun ClosedSection(schools: List<DataRow>) {
    val list = Schools.closed(schools)
    PageSection("Schools closed since 2016", "xmark.circle", Tone.AMBER, "${list.size} schools") {
        CardList {
            list.forEachIndexed { i, s ->
                TextRow(s.string("name") ?: "", listOfNotNull("Last listed ${s.string("last_year_open") ?: ""}", s.string("city")).joinToString(" · "))
                if (i < list.lastIndex) RowDivider()
            }
        }
    }
}
