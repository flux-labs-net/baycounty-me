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
    LaunchedEffect(Unit) { store.load(Schools.datasets) }
    val schools = store.rows["schools"] ?: emptyList()
    val calendar = store.rows["school-calendar"] ?: emptyList()
    val enrollment = store.rows["school-enrollment"] ?: emptyList()
    val grades = store.rows["school-grades"] ?: emptyList()
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
                "What's coming up on the school calendar, and every public school in Bay County: grades, students and how each has changed since 2016.",
                symbol = "graduationcap", tone = Tone.BLUE,
            )
        }
        if (schools.isEmpty()) {
            item { val e = store.errors["schools"]; if (e != null) Unavailable("Couldn't load the schools", e) else Loading() }
            return@Screen
        }
        item { Kpis(schools, calendar, enrollment, grades, today) }
        item {
            CardList { RouteRow(Route.MyAddress, "Which schools serve your address", "Your zoned elementary, middle and high school", symbol = "mappin.and.ellipse") }
        }
        item { CalendarSection(calendar, today, kind, showAll, onKind = { kind = it; showAll = false }, onMore = { showAll = !showAll }) }
        item { SchoolsSection(schools, enrollment, grades, filter, query, open, onFilter = { filter = it }, onQuery = { query = it }, onOpen = { open = if (open == it) null else it }) }
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
    val gradeYears = grades.mapNotNull { it.number("year") }.toSet().size
    Grid2(listOf(0, 1, 2, 3)) { i, m ->
        when (i) {
            0 -> KPICard("Public schools", "${open.size}", m, "${open.size - charter} run by the district, $charter charter schools", "graduationcap", Tone.AMBER)
            1 -> KPICard("Students" + (total?.let { ", ${it.first}" } ?: ""), total?.let { Format.number(it.second) } ?: "—", m,
                "Enrolled in the fall, from the federal school directory", "person.3", Tone.BLUE)
            2 -> KPICard("School grades", if (grades.isEmpty()) "—" else "$gradeYears years", m,
                if (grades.isEmpty()) "Being added from the Florida Department of Education" else "Florida Department of Education", "star", Tone.TEAL)
            else -> KPICard("Next day off", off?.let(Schools::date)?.format(DateTimeFormatter.ofPattern("MMM d", Locale.US)) ?: "—", m,
                off?.string("title"), "calendar", Tone.SALMON)
        }
    }
}

@Composable
private fun CalendarSection(calendar: List<DataRow>, today: String, kind: Schools.Kind, showAll: Boolean, onKind: (Schools.Kind) -> Unit, onMore: () -> Unit) {
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
    schools: List<DataRow>, enrollment: List<DataRow>, grades: List<DataRow>, filter: Schools.Filter, query: String, open: String?,
    onFilter: (Schools.Filter) -> Unit, onQuery: (String) -> Unit, onOpen: (String) -> Unit,
) {
    val list = Schools.open(schools, filter, query)
    PageSection("Every public school", "graduationcap", Tone.AMBER, "${list.size} schools · tap one for its details") {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            ChipRow(Schools.Filter.entries.map { it to it.label }, filter) { onFilter(it) }
            FilterField(query, "Find a school or city", onQuery)
            CardList {
                list.forEachIndexed { i, s ->
                    SchoolRow(s, enrollment, grades, open == s.string("school_id")) { onOpen(s.string("school_id") ?: "") }
                    if (i < list.lastIndex) RowDivider(64.dp)
                }
            }
            Text("The letter is the school's latest Florida school grade. Students are from the federal school directory.", style = T.footnote, color = Brand.secondary)
        }
    }
}

@Composable
private fun SchoolRow(s: DataRow, enrollment: List<DataRow>, grades: List<DataRow>, expanded: Boolean, onTap: () -> Unit) {
    val opener = rememberOpener()
    val id = s.string("school_id") ?: ""
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(Modifier.fillMaxWidth().clickable(onClick = onTap), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(36.dp).background(Brand.hairline.copy(alpha = 0.4f), RoundedCornerShape(9.dp)), contentAlignment = Alignment.Center) {
                Text(s.string("latest_grade") ?: "–", style = T.headline, color = Brand.text)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(s.string("name") ?: "", style = T.subheadBold, color = Brand.text)
                Text(Schools.subtitle(s), style = T.caption, color = Brand.secondary)
            }
            Text(if (expanded) "▴" else "▾", style = T.caption, color = Brand.tertiary)
        }
        if (expanded) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Fact("Students" + (s.string("enrollment_year")?.let { ", $it" } ?: ""), s.number("enrollment")?.let { Format.number(it) } ?: "—", Modifier.weight(1f))
                Fact("Per teacher", s.number("students_per_teacher")?.let { Format.number(it) } ?: "—", Modifier.weight(1f))
                Fact("Free or reduced lunch", s.number("free_reduced_lunch_pct")?.let { "${Format.number(it)}%" } ?: "—", Modifier.weight(1f))
            }
            s.string("address")?.let { a ->
                Text(listOfNotNull(a, s.string("city"), s.string("phone")).joinToString(" · "), style = T.caption, color = Brand.secondary)
            }
            val g = Schools.grades(grades, id)
            if (g.isNotEmpty()) Text("Grades: " + g.take(6).joinToString(" · ") { "${(it.number("year") ?: 0.0).toInt()} ${it.string("grade") ?: ""}" }, style = T.caption, color = Brand.secondary)
            val ys = Schools.enrollment(enrollment, id)
            if (ys.size > 1) Text("Students: ${Format.number(ys.first().second)} in ${ys.first().first}, ${Format.number(ys.last().second)} in ${ys.last().first}", style = T.caption, color = Brand.secondary)
            Text("On BayCounty.me →", style = T.subheadBold, color = Brand.navy, modifier = Modifier.clickable { opener.openSite(Schools.pagePath(s)) })
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
