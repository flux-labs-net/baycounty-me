package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.AccountabilityConsole
import me.baycounty.kit.AccountabilityConsole.Phase
import me.baycounty.kit.BayCountyClient
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Governments

private enum class ASort(val label: String) { RECENT("Most recent"), GROWTH("Most cost growth"), MONEY("Largest") }

@Composable private fun severityColor(s: String?): Color = when (s) { "high" -> Brand.salmon; "warn" -> Brand.amber; else -> Brand.blue }
private fun severityLabel(s: String?): String = when (s) { "high" -> "High"; "warn" -> "Question"; else -> "Note" }

@Composable private fun stageColor(s: String?): Color = when (Phase.of(s)) {
    Phase.DONE -> Brand.good
    Phase.STOPPED -> Brand.secondary
    Phase.ACTIVE -> if (s == "delayed") Brand.amber else Brand.blue
}

@Composable private fun kindColor(k: String): Color = when (k) {
    "budget", "estimate" -> Brand.secondary
    "award", "approval", "vote" -> Brand.navy
    "change" -> Brand.amber
    "payment", "spent", "complete" -> Brand.good
    else -> Brand.blue
}

private val months = listOf("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

/** "2021-03-15" → Mar 15, 2021; "2021-03" → Mar 2021; anything else stays. */
private fun accDate(s: String?): String {
    if (s.isNullOrEmpty()) return ""
    if (s.length >= 10) Dates.parse(s.take(10))?.let { return Dates.display(it, false) }
    if (s.length == 7) s.takeLast(2).toIntOrNull()?.takeIf { it in 1..12 }?.let { return months[it - 1] + " " + s.take(4) }
    return s
}

private val AccountabilityConsole.Project.stageLabel: String get() = AccountabilityConsole.stage(status)

/** The Accountability console: public projects followed from first budget to close-out (/public-money/accountability). */
@Composable
fun AccountabilityScreen() {
    val store = LocalStore.current
    val o = rememberOpener()
    LaunchedEffect(Unit) { store.loadAccountability() }
    var phase by rememberSaveable { mutableStateOf<Phase?>(null) }
    var onlyQuestions by rememberSaveable { mutableStateOf(false) }
    var rule by rememberSaveable { mutableStateOf<String?>(null) }
    var gov by rememberSaveable { mutableStateOf<String?>(null) }
    var sort by rememberSaveable { mutableStateOf(ASort.RECENT) }
    var query by rememberSaveable { mutableStateOf("") }
    var showOptions by remember { mutableStateOf(false) }
    val c = store.accountability
    val filtered = rule != null || gov != null || onlyQuestions

    Screen(
        "Accountability", onRefresh = { store.loadAccountability(force = true) }, spacing = 0,
        actions = { ToolbarIcon(if (filtered) "line.3.horizontal.decrease.circle.fill" else "line.3.horizontal.decrease.circle", "Sort and filter") { showOptions = true } },
    ) {
        if (c == null) {
            item { AppDataPending("accountability.json", "Couldn't load the console") { store.loadAccountability(force = true) } }
            return@Screen
        }
        val q = query.trim().lowercase()
        val rows = c.projects.filter { p ->
            (phase == null || Phase.of(p.status) == phase) && (!onlyQuestions || p.flags.isNotEmpty()) &&
                (rule == null || p.flags.any { it.r == rule }) && (gov == null || p.gk == gov) &&
                (q.isEmpty() || p.n.lowercase().contains(q) || (p.agency ?: "").lowercase().contains(q) || (p.vendor ?: "").lowercase().contains(q))
        }.let { r ->
            when (sort) {
                ASort.RECENT -> r.sortedByDescending { it.last ?: "" }
                ASort.GROWTH -> r.sortedByDescending { it.growth ?: Double.NEGATIVE_INFINITY }
                ASort.MONEY -> r.sortedByDescending { it.money ?: 0.0 }
            }
        }
        val maxMoney = rows.mapNotNull { it.money }.maxOrNull() ?: 0.0
        item {
            Column(Modifier.padding(bottom = 14.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                PageIntro("/public-money/accountability")
                FilterField(query, "Find a project") { query = it }
                if (query.isEmpty()) {
                    StatStrip(listOf(
                        "Projects" to "${c.stats?.projects ?: c.projects.size}",
                        "With questions" to "${c.stats?.flagged ?: 0}",
                        "Records missing" to "${c.stats?.gaps ?: 0}",
                    ))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(icon("questionmark.bubble"), null, tint = Brand.secondary, modifier = Modifier.size(18.dp))
                        Text("A flag is a question for the agency, not a finding of wrongdoing. Each one names the published rule that raised it.", style = T.footnote, color = Brand.secondary)
                    }
                    val counts = c.rules.mapNotNull { r ->
                        val n = c.projects.count { p -> p.flags.any { it.r == r.id } }
                        if (n > 0) BarItem(r.id, r.title, n.toDouble()) else null
                    }.sortedByDescending { it.value }
                    if (counts.isNotEmpty()) CompareBars(
                        "Questions by rule", counts, { "${it.toInt()}" }, "Projects flagged by each rule. Tap one to see them.", rule, labelsAbove = true,
                    ) { id -> rule = if (rule == id) null else id }
                }
                ChipRow(listOf<Pair<Phase?, String>>(null to "All") + Phase.entries.map { it to it.label }, phase) { phase = it }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Flow(6.dp) {
                        rule?.let { r -> FilterChip(c.rule(r)?.title ?: r) { rule = null } }
                        gov?.let { g -> FilterChip(Governments.names[g] ?: g) { gov = null } }
                        if (onlyQuestions) FilterChip("With questions") { onlyQuestions = false }
                    }
                    Fill()
                    Text("${rows.size} of ${c.projects.size}", style = T.footnote, color = Brand.secondary, softWrap = false)
                }
            }
        }
        if (rows.isEmpty()) item { Unavailable("No projects match", "Try fewer filters or a shorter search.", symbol = "magnifyingglass") }
        cardItems(rows, key = { it.id }) { p ->
            val nav = LocalNav.current
            Box(Modifier.clickable(role = Role.Button) { nav.push(Route.AccountabilityProject(p.id)) }) { ProjectRow(p, maxMoney) }
        }
        c.about?.let { about -> item { Text(about, style = T.caption, color = Brand.secondary, modifier = Modifier.padding(top = 14.dp, start = 4.dp, end = 4.dp)) } }
    }

    if (showOptions) {
        ModalBottomSheet(onDismissRequest = { showOptions = false }, containerColor = Brand.canvas) {
            Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("Sort and filter", style = T.title3, color = Brand.text)
                EyebrowHeader("Sort")
                ChipRow(ASort.entries.map { it to it.label }, sort) { sort = it }
                ToggleRow("Only projects with questions", onlyQuestions) { onlyQuestions = it }
                EyebrowHeader("Government")
                MenuPicker(
                    gov?.let { Governments.names[it] ?: it } ?: "Every government",
                    listOf<Pair<String?, String>>(null to "Every government") + Governments.order.map { it to (Governments.names[it] ?: it) }, "Government",
                ) { gov = it }
                LinkLine("Open on BayCounty.me", "safari") { showOptions = false; o.openSite("/public-money/accountability") }
            }
        }
    }
}

/** One project: name and stage, its money, the growth between first and latest cost, and its questions. */
@Composable
private fun ProjectRow(p: AccountabilityConsole.Project, maxMoney: Double) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(p.n, style = T.subheadBold, color = Brand.text, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            p.money?.let { Text(Format.compactMoney(it), style = T.subheadBold, color = Brand.text) }
        }
        p.money?.let { if (maxMoney > 0) MagnitudeBar(it / maxMoney) }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Badge(p.stageLabel, stageColor(p.status))
            Text(p.g ?: "", style = T.caption, color = Brand.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            p.growth?.let { GrowthPill(it) }
            if (p.flags.isNotEmpty()) FlagCount(p.flags)
        }
    }
}

/** Cost growth, colored when it passes the 10% and 25% rule lines. */
@Composable
private fun GrowthPill(growth: Double) {
    val color = if (growth > 25) Brand.salmon else if (growth > 10) Brand.amber else Brand.secondary
    Text(
        (if (growth >= 0) "+" else "") + Format.number(Math.rint(growth * 10) / 10) + "%",
        style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = color,
        modifier = Modifier.background(color.copy(alpha = 0.12f), CircleShape).padding(horizontal = 7.dp, vertical = 2.dp)
            .clearAndSetSemantics { contentDescription = "Cost changed ${Format.number(growth)} percent" },
    )
}

@Composable
private fun FlagCount(flags: List<AccountabilityConsole.Flag>) {
    val worst = if (flags.any { it.sev == "high" }) "high" else if (flags.any { it.sev == "warn" }) "warn" else "info"
    val c = severityColor(worst)
    Row(
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(3.dp),
        modifier = Modifier.clearAndSetSemantics { contentDescription = "${flags.size} ${if (flags.size == 1) "question" else "questions"}" },
    ) {
        Icon(icon("questionmark.circle.fill"), null, tint = c, modifier = Modifier.size(15.dp))
        Text("${flags.size}", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = c)
    }
}

/** One project's cost, questions, missing records, agency reply and timeline. */
@Composable
fun AccountabilityProjectScreen(id: String) {
    val store = LocalStore.current
    LaunchedEffect(Unit) { store.loadAccountability() }
    val c = store.accountability
    val p = c?.projects?.firstOrNull { it.id == id }
    Screen(p?.n ?: "Project", spacing = 22) {
        if (c == null) { item { AppDataPending("accountability.json", "Couldn't load the console") { store.loadAccountability(force = true) } }; return@Screen }
        if (p == null) { item { Unavailable("Project not found", symbol = "checklist") }; return@Screen }
        item {
            Column(Modifier.fillMaxWidth().card(16.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(p.n, style = T.title3, color = Brand.text)
                Text(listOfNotNull(p.g, p.agency).joinToString(" · "), style = T.subhead, color = Brand.secondary)
                Flow(6.dp) {
                    Badge(p.stageLabel, stageColor(p.status))
                    Badge(AccountabilityConsole.source(p.src), Brand.secondary)
                    p.late_days?.takeIf { it > 0 }?.let { Badge("About ${it.toInt()} days late", Brand.amber) }
                }
                p.what?.let { Text(it, style = T.subhead, color = Brand.text) }
            }
        }
        if (p.where != null || p.funding != null) item {
            CardList {
                p.where?.let { FactRow("Where", it) }
                if (p.where != null && p.funding != null) RowDivider()
                p.funding?.let { FactRow("Paid for by", it) }
            }
        }
        if (p.base?.a != null || p.latest?.a != null) item { FormSection("Cost") { CostCard(p) } }
        if (p.flags.isNotEmpty()) item {
            FormSection("Questions raised", "Raised by the published rules. A question, not a finding of wrongdoing.") {
                CardList { p.flags.forEachIndexed { i, f -> FlagRow(f, c.rule(f.r)); if (i < p.flags.lastIndex) RowDivider() } }
            }
        }
        if (p.gaps.isNotEmpty()) item {
            FormSection("Records still missing") {
                CardList {
                    for (g in p.gaps) {
                        Row(Modifier.fillMaxWidth().padding(14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Icon(icon("doc.questionmark"), null, tint = Brand.secondary, modifier = Modifier.size(18.dp))
                            Text(g.q, style = T.subhead, color = Brand.text)
                        }
                        RowDivider()
                    }
                    WebRow("Request a public record", "${BayCountyClient.SITE}/records-request", symbol = "envelope")
                }
            }
        }
        item {
            FormSection("Agency reply") {
                CardList {
                    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Icon(icon(if (p.reply?.status == "replied") "checkmark.bubble" else "bubble.left"), null, tint = Brand.navy, modifier = Modifier.size(20.dp))
                        Text(AccountabilityConsole.reply(p.reply?.status), style = T.subhead, color = Brand.text)
                    }
                    p.reply?.text?.let { RowDivider(); Text(it, style = T.subhead, color = Brand.text, modifier = Modifier.padding(14.dp)) }
                    p.reply?.u?.let { RowDivider(); WebRow("The agency's reply", it, symbol = "doc.text") }
                }
            }
        }
        item {
            FormSection("Timeline") {
                Column(Modifier.fillMaxWidth().card(14.dp).padding(start = 14.dp, end = 14.dp, top = 14.dp, bottom = 4.dp)) {
                    p.timeline.forEachIndexed { i, e -> TimelineRow(e, i == p.timeline.lastIndex) }
                }
            }
        }
        item { CardList { WebRow("This project on BayCounty.me", "${BayCountyClient.SITE}/public-money/accountability#${p.id}") } }
    }
}

@Composable
private fun CostCard(p: AccountabilityConsole.Project) {
    val first = p.base?.a ?: 0.0
    val latest = p.latest?.a ?: 0.0
    val maxV = maxOf(first, latest, 1.0)
    Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        p.base?.a?.let { CostLine("First", it, p.base?.t, it / maxV, Brand.blue) }
        p.latest?.a?.let { CostLine("Latest", it, p.latest?.t, it / maxV, Brand.navy) }
        val g = p.growth ?: if (first > 0 && latest > 0) (latest - first) / first * 100 else null
        if (g != null) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            GrowthPill(g)
            Text(if (p.flags.any { it.r == "growth" }) "Past the 10% that raises a question" else "Change from the first figure", style = T.caption, color = Brand.secondary)
        }
        p.money?.takeIf { it != latest && it != first }?.let { Text("Money followed on this project: ${Format.money(it)}", style = T.caption, color = Brand.secondary) }
    }
}

@Composable
private fun CostLine(label: String, amount: Double, what: String?, fraction: Double, color: Color) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row {
            Text(label, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
            Text(Format.money(amount), style = T.subheadBold, color = Brand.text)
        }
        Box(Modifier.fillMaxWidth().height(10.dp)) {
            Box(Modifier.fillMaxWidth(fraction.toFloat().coerceIn(0.02f, 1f)).fillMaxHeight().background(color, CircleShape))
        }
        what?.let { Text(it.replaceFirstChar { ch -> ch.uppercase() }, style = T.caption, color = Brand.secondary) }
    }
}

@Composable
private fun FlagRow(flag: AccountabilityConsole.Flag, rule: AccountabilityConsole.Rule?) {
    var open by rememberSaveable(flag.id) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(Modifier.size(9.dp).background(severityColor(flag.sev), CircleShape))
            Text(rule?.title ?: flag.r, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
            Text(severityLabel(flag.sev), style = T.caption.copy(fontWeight = FontWeight.Medium), color = Brand.secondary)
        }
        Text(flag.note, style = T.subhead, color = Brand.text)
        if (rule != null) {
            Row(
                Modifier.clickable(role = Role.Button) { open = !open }.padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text("How this rule works", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy)
                Icon(icon(if (open) "chevron.up" else "chevron.down"), null, tint = Brand.navy, modifier = Modifier.size(16.dp))
            }
            if (open) Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                for ((t, b) in listOfNotNull(rule.`when`?.let { "When it's raised" to it }, rule.means?.let { "What it means" to it }, rule.not?.let { "What it doesn't mean" to it })) {
                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text(t, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text)
                        Text(b, style = T.caption, color = Brand.secondary)
                    }
                }
            }
        }
    }
}

/** A timeline step: a colored dot on a line, the date and kind, the amount, what happened and who was paid. */
@Composable
private fun TimelineRow(e: AccountabilityConsole.Event, isLast: Boolean) {
    val nav = LocalNav.current
    val o = rememberOpener()
    Row(Modifier.fillMaxWidth().height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.width(12.dp).fillMaxHeight().clearAndSetSemantics {}, horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.padding(top = 3.dp).size(12.dp).background(kindColor(e.k), CircleShape))
            if (!isLast) Box(Modifier.width(2.dp).weight(1f).background(Brand.sunken))
        }
        Column(Modifier.weight(1f).padding(bottom = 12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(AccountabilityConsole.kind(e.k), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = kindColor(e.k))
                Text(accDate(e.d), style = T.caption, color = Brand.secondary, modifier = Modifier.weight(1f))
                e.a?.let { Text((if (e.approx == true) "about " else "") + Format.money(it), style = T.subheadBold, color = Brand.text) }
            }
            Text(e.t, style = T.subhead, color = Brand.text)
            e.payee?.let { payee ->
                val vid = e.vid
                Row(
                    (if (vid != null) Modifier.clickable(role = Role.Button) { nav.push(Route.Vendor(vid)) } else Modifier).padding(vertical = 2.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp),
                ) {
                    Icon(icon("building"), null, tint = if (vid != null) Brand.navy else Brand.secondary, modifier = Modifier.size(14.dp))
                    Text(payee, style = T.caption, color = if (vid != null) Brand.navy else Brand.secondary)
                }
            }
            e.url?.let { u ->
                Row(Modifier.clickable { o.open(u) }.padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                    Icon(icon("doc.text.magnifyingglass"), null, tint = Brand.navy, modifier = Modifier.size(14.dp))
                    Text("Source", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy)
                }
            }
        }
    }
}
