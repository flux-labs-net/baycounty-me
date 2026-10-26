package me.baycounty.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.kit.Browse
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Dates
import me.baycounty.kit.DonorContracts
import me.baycounty.kit.Format
import me.baycounty.kit.PeopleDirectory
import me.baycounty.kit.Period
import me.baycounty.kit.VoteSummary
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate

/** A thin bar showing how big one amount is next to the largest in view. */
@Composable
fun MagnitudeBar(fraction: Double, height: Dp = 4.dp, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(height).clip(CircleShape).background(Brand.sunken).clearAndSetSemantics {}) {
        Box(Modifier.fillMaxWidth(fraction.coerceIn(0.0, 1.0).toFloat().coerceAtLeast(0.03f)).fillMaxHeight().background(Brand.blue, CircleShape))
    }
}

/** One vote as a mark: filled for yes, a ring for no, grey for absent or abstained. */
@Composable
fun VoteDot(choice: VoteSummary.Choice, size: Dp = 12.dp) {
    when (choice) {
        VoteSummary.Choice.YES -> Box(Modifier.size(size).background(Brand.good, CircleShape))
        VoteSummary.Choice.NO -> Box(Modifier.size(size).border(2.5.dp, Brand.salmon, CircleShape))
        VoteSummary.Choice.OTHER -> Box(Modifier.size(size).background(Brand.secondary.copy(alpha = 0.3f), CircleShape))
    }
}

/** One mark per member. */
@Composable
fun VoteDots(summary: VoteSummary, size: Dp = 12.dp) {
    val order = { c: VoteSummary.Choice -> c.ordinal }
    val choices = if (summary.members.isNotEmpty()) summary.members.map { it.choice }.sortedBy(order)
        else List(summary.yes) { VoteSummary.Choice.YES } + List(summary.no) { VoteSummary.Choice.NO }
    Row(Modifier.clearAndSetSemantics { contentDescription = "${summary.yes} yes, ${summary.no} no" + if (summary.other > 0) ", ${summary.other} absent" else "" },
        horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        for (c in choices.take(11)) VoteDot(c, size)
    }
}

/** One member's vote with the word beside it. */
@Composable
fun VoteMark(choice: VoteSummary.Choice) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
        VoteDot(choice)
        Text(when (choice) { VoteSummary.Choice.YES -> "Yes"; VoteSummary.Choice.NO -> "No"; else -> "Absent" }, style = T.caption.copy(fontWeight = FontWeight.Medium), color = Brand.secondary)
    }
}

fun voteChoice(v: String?): VoteSummary.Choice = when ((v ?: "").lowercase()) { "yes" -> VoteSummary.Choice.YES; "no" -> VoteSummary.Choice.NO; else -> VoteSummary.Choice.OTHER }

@Composable
fun VoteLegend() {
    Row(Modifier.clearAndSetSemantics {}, horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
        for (c in VoteSummary.Choice.entries) Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
            VoteDot(c, 10.dp)
            Text(when (c) { VoteSummary.Choice.YES -> "Yes"; VoteSummary.Choice.NO -> "No"; else -> "Absent" }, style = T.caption, color = Brand.secondary)
        }
    }
}

/** A recorded vote: headline and amount, the roll call as dots, and the outcome. */
@Composable
fun VoteRow(row: DataRow, summary: VoteSummary) {
    val outcome = when (summary.passed) {
        true -> "Passed"; false -> "Failed"
        null -> (row.string("outcome") ?: "Outcome not published").replaceFirstChar { it.uppercase() }
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(row.string("headline") ?: "Vote", style = T.subheadBold, color = Brand.text, maxLines = 3, modifier = Modifier.weight(1f))
            row.number("amount")?.let { Text(Format.compactMoney(it), style = T.subheadBold, color = Brand.text) }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (summary.hasTally) VoteDots(summary)
            Text(
                if (summary.hasTally && summary.passed != null) "$outcome ${summary.tallyText}" else outcome,
                style = T.caption.copy(fontWeight = if (summary.passed == false) FontWeight.Bold else FontWeight.Normal),
                color = if (summary.passed == false) Brand.text else Brand.secondary, maxLines = 1, modifier = Modifier.weight(1f),
            )
            if (summary.split) Badge("Split", Brand.amber)
        }
    }
}

/** Initials on a circle tinted by name, like the site's people cards. */
@Composable
fun PersonInitials(name: String, size: Dp = 38.dp) {
    val initials = name.split(" ").filter { it.firstOrNull()?.isLetter() == true }.take(2).joinToString("") { it.take(1) }
    var h = 0
    for (c in name) h = (h * 31 + c.code) % 9973
    val tone = listOf(Tone.BLUE, Tone.TEAL, Tone.AMBER, Tone.SALMON)[Math.abs(h) % 4]
    Box(Modifier.size(size).background(tone.color().copy(alpha = 0.13f), CircleShape).clearAndSetSemantics {}, contentAlignment = Alignment.Center) {
        Text(initials, style = T.body.copy(fontSize = (size.value * 0.38f).sp, fontWeight = FontWeight.SemiBold), color = tone.color())
    }
}

/** A person with initials, name, the site's one line about them, and a tag when they're a 2026 candidate. */
@Composable
fun PersonRow(person: PeopleDirectory.Person, onClick: (() -> Unit)? = null) {
    val candidate = (person.kinds ?: emptyList()).contains("candidate") || person.mainRoles.any { (it.role ?: "").startsWith("2026 candidate") }
    Row(
        (if (onClick != null) Modifier.clickable(role = Role.Button, onClick = onClick) else Modifier).fillMaxWidth().padding(horizontal = 14.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        PersonInitials(person.name)
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(person.name, style = T.subheadBold, color = Brand.text)
                if (candidate) Badge("Candidate", Brand.amber)
            }
            Text(person.headline.replace("2026 candidate: ", "Running for "), style = T.caption, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        if (onClick != null) Chevron()
    }
}

/** A business gift to a campaign, matched to the business's contracts. */
@Composable
fun DonorMatchRow(match: DonorContracts.Match, showCandidate: Boolean = true) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            val pid = match.person_id; val vid = match.vendor_id
            when {
                showCandidate && pid != null -> Text(match.candidate ?: pid, style = T.subheadBold, color = Brand.navy, modifier = Modifier.weight(1f).clickable { nav.push(Route.Person(pid)) })
                !showCandidate && vid != null -> Text(match.vendor ?: match.contributor ?: vid, style = T.subheadBold, color = Brand.navy, modifier = Modifier.weight(1f).clickable { nav.push(Route.Vendor(vid)) })
                else -> Text((if (showCandidate) match.candidate else match.contributor) ?: "", style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
            }
            match.contribution_amount?.let { Text(Format.money(it), style = T.subhead, color = Brand.text) }
        }
        Text(listOfNotNull(match.office, match.election).joinToString(" · "), style = T.caption, color = Brand.secondary)
        match.contract_ids_or_descriptions?.takeIf { it.isNotEmpty() }?.let { Text(it.take(2).joinToString("\n"), style = T.caption2, color = Brand.text) }
        if (match.same_government_as_office == true) Badge("Contract with the same government", Brand.salmon)
    }
}

/** A filter in force, tapped to remove it. */
@Composable
fun FilterChip(text: String, remove: () -> Unit) {
    Row(
        Modifier.heightIn(min = 36.dp).clip(CircleShape).background(Brand.navy.copy(alpha = 0.12f)).clickable(role = Role.Button, onClick = remove)
            .padding(horizontal = 12.dp).semantics { contentDescription = "Remove filter $text" },
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(text, style = T.footnote.copy(fontWeight = FontWeight.Medium), color = Brand.navy, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.widthIn(max = 260.dp))
        Icon(icon("xmark"), null, tint = Brand.navy, modifier = Modifier.size(14.dp))
    }
}

/** A group's title on the left, its count and total on the right. */
@Composable
fun GroupHeader(title: String, count: Int, total: Double?, noun: String = "record", subtitle: String? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Column(Modifier.weight(1f)) {
            Text(title, style = T.headline, color = Brand.text, maxLines = 2)
            if (subtitle != null) Text(subtitle, style = T.caption, color = Brand.secondary)
        }
        Text(listOfNotNull("${Format.number(count.toDouble())} ${if (count == 1) noun else noun + "s"}", total?.let(Format::compactMoney)).joinToString(" · "),
            style = T.caption, color = Brand.secondary)
    }
}

/** One record in a line or two: name and amount, then a size bar and where and when. */
@Composable
fun CompactRecordRow(spec: DatasetSpec, row: DataRow, maxAmount: Double, hide: String? = null, onClick: () -> Unit) {
    val amount = spec.amount(row)
    val meta = spec.subtitleKeys.filter { it != spec.titleKeys.firstOrNull() && it != hide }.mapNotNull { key ->
        val v = row[key] ?: return@mapNotNull null
        val s = Format.value(v, key).takeIf { it.isNotEmpty() } ?: return@mapNotNull null
        if (key in listOf("government", "gov", "employer", "gov_id", "board")) Browse.shortGovernment(s) else s
    }.joinToString(" · ")
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(spec.title(row), style = T.subheadBold, color = Brand.text, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            amount?.let { Text(Format.compactMoney(it), style = T.subheadBold, color = Brand.text) }
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (amount != null && maxAmount > 0) MagnitudeBar(amount / maxAmount, modifier = Modifier.weight(1f))
            if (meta.isNotEmpty()) Text(meta, style = T.caption, color = Brand.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = if (amount != null && maxAmount > 0) Modifier.widthIn(max = 220.dp) else Modifier.weight(1f))
            else if (amount == null) Spacer(Modifier.weight(1f))
            spec.badge(row)?.let { Badge(it, statusColor(it)) }
        }
    }
}

/** "Oct 22" this year, "Oct '25" in earlier years, or the fiscal year for records without a date. */
fun tableShortDate(row: DataRow): String {
    val s = row.first(Period.eventKeys + "date_end")
    val d = s?.let { Dates.parse(it) }
    if (d != null) {
        val thisYear = LocalDate.now(Dates.chicago).year
        return if (Dates.format(d, "yyyy").toInt() == thisYear) Dates.format(d, "MMM d") else Dates.format(d, "MMM ''yy")
    }
    return Period.of(row)?.label ?: ""
}

/** The biggest names in a list, as bars. Tapping one filters the list to it. */
@Composable
fun TopBars(title: String, items: List<Browse.Bucket>, byAmount: Boolean, onTap: (String) -> Unit) {
    val maxV = items.maxOfOrNull { if (byAmount) it.amount else it.count.toDouble() } ?: 1.0
    Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, style = T.subheadBold, color = Brand.text)
        for (item in items) {
            val v = if (byAmount) item.amount else item.count.toDouble()
            Column(Modifier.fillMaxWidth().clickable { onTap(item.key) }, verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row {
                    Text(item.label, style = T.subhead, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Spacer(Modifier.width(8.dp))
                    Text(if (byAmount) Format.compactMoney(v) else "${item.count}", style = T.subheadBold, color = Brand.text)
                }
                MagnitudeBar(if (maxV > 0) v / maxV else 0.0, 6.dp)
            }
        }
    }
}

/** Small headline numbers in a row. */
@Composable
fun StatStrip(tiles: List<Pair<String, String>>) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for ((t, v) in tiles) Column(Modifier.weight(1f).card(12.dp).padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(t, style = T.caption, color = Brand.secondary, maxLines = 1)
            Text(v, style = T.number, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** A labelled bar ("Raised  ▇▇▇▇  $42K"). */
@Composable
fun MoneyBar(label: String, value: Double, fraction: Double) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, style = T.caption, color = Brand.text, modifier = Modifier.width(48.dp))
        MagnitudeBar(fraction, 8.dp, Modifier.weight(1f))
        Text(Format.compactMoney(value), style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, modifier = Modifier.width(60.dp), textAlign = androidx.compose.ui.text.style.TextAlign.End)
    }
}

@Suppress("unused") private val unusedColor = Color.Unspecified

/** A search box for filtering a list on the screen (the iOS .searchable field). */
@Composable
fun FilterField(query: String, prompt: String, onChange: (String) -> Unit) {
    androidx.compose.material3.OutlinedTextField(
        query, onChange, Modifier.fillMaxWidth(),
        placeholder = { Text(prompt, style = T.body) },
        leadingIcon = { Icon(icon("magnifyingglass"), null, tint = Brand.secondary) },
        trailingIcon = { if (query.isNotEmpty()) androidx.compose.material3.IconButton(onClick = { onChange("") }) { Icon(icon("xmark"), "Clear", tint = Brand.tertiary) } },
        singleLine = true, shape = androidx.compose.foundation.shape.RoundedCornerShape(14.dp), textStyle = T.body,
        colors = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
            focusedContainerColor = Brand.surface, unfocusedContainerColor = Brand.surface,
            focusedBorderColor = Brand.navy, unfocusedBorderColor = Brand.hairline, cursorColor = Brand.navy,
            focusedTextColor = Brand.text, unfocusedTextColor = Brand.text,
        ),
    )
}

/** One row of a long card list inside a LazyColumn: rounded top on the first, rounded bottom on the last, a divider between. */
@Composable
fun Modifier.cardSegment(first: Boolean, last: Boolean): Modifier {
    val r = 16.dp
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(if (first) r else 0.dp, if (first) r else 0.dp, if (last) r else 0.dp, if (last) r else 0.dp)
    return this.fillMaxWidth().clip(shape).background(Brand.surface, shape)
}

/** Long lists (hundreds of rows) as lazily built card rows. Use on a Screen with spacing = 0. */
fun <T> androidx.compose.foundation.lazy.LazyListScope.cardItems(list: List<T>, key: ((T) -> Any)? = null, inset: Dp = 14.dp, row: @Composable (T) -> Unit) {
    items(list.size, key = key?.let { k -> { i: Int -> k(list[i]) } }) { i ->
        Column(Modifier.cardSegment(i == 0, i == list.lastIndex)) {
            row(list[i])
            if (i < list.lastIndex) RowDivider(inset)
        }
    }
}

/** The government filter as a toolbar icon with a menu. */
@Composable
fun GovFilterAction(gov: String?, extra: Map<String, String> = emptyMap(), onPick: (String?) -> Unit) {
    var open by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    Box {
        ToolbarIcon(if (gov == null) "line.3.horizontal.decrease.circle" else "line.3.horizontal.decrease.circle.fill", "Filter by government") { open = true }
        androidx.compose.material3.DropdownMenu(open, { open = false }, containerColor = Brand.surface) {
            val opts = listOf<Pair<String?, String>>(null to "Every government") + me.baycounty.kit.Governments.order.map { it to (me.baycounty.kit.Governments.names[it] ?: it) } + extra.map { it.key to it.value }
            for ((k, t) in opts) androidx.compose.material3.DropdownMenuItem(
                text = { Text(t, style = if (k == gov) T.subheadBold else T.body, color = if (k == gov) Brand.navy else Brand.text) },
                onClick = { open = false; onPick(k) },
            )
        }
    }
}

/** A switch with its label, on a card. */
@Composable
fun ToggleRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().card(14.dp).clickable { onChange(!checked) }.padding(horizontal = 14.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
        androidx.compose.material3.Switch(checked, onChange, colors = androidx.compose.material3.SwitchDefaults.colors(checkedTrackColor = Brand.navyFill))
    }
}

/** A card with a small label over the current choice that opens a menu (the iOS form Picker). */
@Composable
fun <K> FieldMenu(label: String, value: String, options: List<Pair<K, String>>, modifier: Modifier = Modifier, selected: K? = null, onPick: (K) -> Unit) {
    var open by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
    Box(modifier) {
        Column(
            Modifier.fillMaxWidth().heightIn(min = 56.dp).card(14.dp).clickable(role = androidx.compose.ui.semantics.Role.Button) { open = true }
                .padding(horizontal = 14.dp, vertical = 8.dp)
                .clearAndSetSemantics { contentDescription = "$label, $value" },
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(label, style = T.caption, color = Brand.secondary)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(value, style = T.headline, color = Brand.text, modifier = Modifier.weight(1f, fill = false), maxLines = 2)
                Icon(icon("chevron.up.chevron.down"), null, tint = Brand.secondary, modifier = Modifier.size(14.dp))
            }
        }
        androidx.compose.material3.DropdownMenu(open, { open = false }, containerColor = Brand.surface) {
            for ((k, t) in options) androidx.compose.material3.DropdownMenuItem(
                text = { Text(t, style = if (k == selected) T.subheadBold else T.body, color = if (k == selected) Brand.navy else Brand.text) },
                onClick = { open = false; onPick(k) },
            )
        }
    }
}

/** A dollar amount typed with the number pad, shown with thousands commas as you type. */
@Composable
fun MoneyField(label: String, text: String, onChange: (String) -> Unit) {
    androidx.compose.material3.OutlinedTextField(
        text,
        { new -> val digits = new.filter { it.isDigit() }; onChange(if (digits.isEmpty()) "" else me.baycounty.kit.Format.number(minOf(digits.toDouble(), 1e9))) },
        Modifier.fillMaxWidth(),
        label = { Text(label) },
        prefix = { Text("$", style = T.body, color = Brand.secondary) },
        singleLine = true, shape = androidx.compose.foundation.shape.RoundedCornerShape(14.dp), textStyle = T.body,
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.Number),
        colors = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
            focusedContainerColor = Brand.surface, unfocusedContainerColor = Brand.surface,
            focusedBorderColor = Brand.navy, unfocusedBorderColor = Brand.hairline, cursorColor = Brand.navy,
            focusedTextColor = Brand.text, unfocusedTextColor = Brand.text, focusedLabelColor = Brand.navy, unfocusedLabelColor = Brand.secondary,
        ),
    )
}

/** Digits in a typed amount, capped at a billion. */
fun typedAmount(text: String): Double = minOf(text.filter { it.isDigit() }.toDoubleOrNull() ?: 0.0, 1e9)

/** One choice in a short list of long options, with a check on the picked one (the iOS inline Picker). */
@Composable
fun <K> RadioList(options: List<Pair<K, String>>, selected: K, onPick: (K) -> Unit) {
    CardList {
        options.forEachIndexed { i, (k, t) ->
            Row(
                Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = androidx.compose.ui.semantics.Role.RadioButton) { onPick(k) }
                    .padding(horizontal = 14.dp, vertical = 10.dp)
                    .semantics(mergeDescendants = true) { this.selected = k == selected },
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(t, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
                if (k == selected) Icon(icon("checkmark"), null, tint = Brand.navy, modifier = Modifier.size(20.dp))
            }
            if (i < options.lastIndex) RowDivider()
        }
    }
}
