package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Browse
import me.baycounty.kit.DatasetSpec
import me.baycounty.kit.Dates
import me.baycounty.kit.Format
import me.baycounty.kit.Governments
import me.baycounty.kit.Period
import me.baycounty.kit.RecordShare
import me.baycounty.kit.VoteSummary
import me.baycounty.kit.newestKey
import me.baycounty.kit.Row as DataRow
import java.time.LocalDate

private enum class DSort(val label: String) { STANDARD("Site order"), AMOUNT("Largest first"), NEWEST("Newest first"), NAME("A to Z") }
private enum class DMode(val label: String, val symbol: String) { LIST("List", "list.bullet"), TABLE("Table", "tablecells"), MAP("Map", "map") }
private enum class VoteFilter(val label: String) { ALL("All"), SPLIT("Split"), FAILED("Failed") }
private enum class TCol(val label: String) { DATE("Date"), TITLE("Name"), GOV("Gov"), AMOUNT("Amount") }

/**
 * Any dataset on the site. Opens on the current year, newest first, with a summary (headline numbers, a chart by
 * month or year, the biggest names), then the records grouped by month (or government, company…) in compact rows.
 * Table mode lines records up in sortable columns; Map mode plots them. Votes are grouped by meeting with a dot per member.
 */
@Composable
fun DatasetScreen(datasetID: String, preset: Map<String, String>) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val context = LocalContext.current
    LaunchedEffect(datasetID) { store.load(datasetID) }
    val spec = DatasetSpec.forId(datasetID)
    val info = store.info(datasetID)
    val all = store.rows[datasetID] ?: emptyList()
    val isVotes = datasetID == "votes"

    var query by rememberSaveable { mutableStateOf("") }
    var filterList by rememberSaveable { mutableStateOf(preset.map { "${it.key}=${it.value}" }) }
    val filters = filterList.associate { it.substringBefore("=") to it.substringAfter("=") }
    fun setFilter(k: String, v: String?) { filterList = (filters - k + (if (v != null) mapOf(k to v) else emptyMap())).map { "${it.key}=${it.value}" } }
    var sortName by rememberSaveable { mutableStateOf<String?>(null) }
    var periodLabel by rememberSaveable { mutableStateOf<String?>(null) } // null = not chosen yet, "" = every year
    var modeName by rememberSaveable { mutableStateOf(DMode.LIST.name) }
    var groupID by rememberSaveable { mutableStateOf<String?>(null) }
    var collapsed by rememberSaveable { mutableStateOf(listOf<String>()) }
    var shareFor by remember { mutableStateOf<Int?>(null) }  // the record whose Copy / Share menu is open
    var bucket by rememberSaveable { mutableStateOf<String?>(null) }
    var tableSort by rememberSaveable { mutableStateOf("DATE:false") }
    var voteFilter by rememberSaveable { mutableStateOf(VoteFilter.ALL) }
    var showOptions by remember { mutableStateOf(false) }
    val mode = DMode.valueOf(modeName)

    val idx = remember(all) { Period.Index(all) }
    val byRow = remember(all) { all.mapNotNull { r -> idx.period(r)?.let { r.id to it } }.toMap() }
    val periods = idx.periods
    val period: Period? = when (periodLabel) { null -> idx.defaultPeriod(); "" -> null; else -> periods.firstOrNull { it.label == periodLabel } }
    val sort = sortName?.let { DSort.valueOf(it) } ?: if (periods.isEmpty()) DSort.STANDARD else DSort.NEWEST
    val govColumn = Browse.governmentColumn(spec, all)
    val totalInfo = Browse.totals[datasetID]

    val q = query.trim()
    val inPeriod = all.filter { row ->
        (period == null || byRow[row.id] == period) &&
            filters.all { (k, v) -> row.string(k) == v || row[k]?.let { Format.value(it, k) } == v } && store.matches(row, q)
    }
    fun sorted(rows: List<DataRow>) = when (sort) {
        DSort.STANDARD -> rows
        DSort.AMOUNT -> rows.sortedByDescending { spec.amount(it) ?: Double.NEGATIVE_INFINITY }
        DSort.NEWEST -> rows.sortedByDescending { spec.newestKey(it) }
        DSort.NAME -> rows.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { spec.title(it) })
    }
    val b = bucket
    val inBucket = if (b == null) inPeriod else if (b.length == 7 && b[4] == '-') inPeriod.filter { Browse.monthKey(it) == b } else inPeriod.filter { byRow[it.id]?.label == b }
    val rows = sorted(inBucket)

    val groupOptions = Browse.groupOptions(all, spec, byRow, period)
    val group: Browse.GroupKey = groupID?.let { id -> (groupOptions + Browse.GroupKey.None).firstOrNull { it.id == id } } ?: run {
        if (sort != DSort.NEWEST) Browse.GroupKey.None
        else groupOptions.firstOrNull()?.takeIf { it == Browse.GroupKey.Month || it == Browse.GroupKey.Year } ?: Browse.GroupKey.None
    }
    val title = info?.title ?: Format.label(datasetID)

    // Controls shared by every mode: year and group menus, the count, filters in force.
    val controls: @Composable () -> Unit = {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (periods.size > 1) MenuPicker(period?.label ?: "All years", listOf("" to "All years") + periods.reversed().map { it.label to it.label }, "Year: ${period?.label ?: "All years"}", filled = true) {
                    periodLabel = it; bucket = null; groupID = null; collapsed = emptyList()
                }
                if (mode == DMode.LIST && !isVotes && groupOptions.size > 1) {
                    MenuPicker(if (group == Browse.GroupKey.None) "Group" else "By ${group.label.lowercase()}",
                        listOf("none" to "No groups") + groupOptions.map { it.id to it.label }, "Group records by ${group.label}") { groupID = it; collapsed = emptyList() }
                }
                Spacer(Modifier.weight(1f))
                Text("${Format.number(rows.size.toDouble())} of ${Format.number(all.size.toDouble())}", style = T.footnote, color = Brand.secondary)
            }
            if (filters.isNotEmpty() || bucket != null) Flow {
                bucket?.let { bk -> FilterChip(if (bk.length == 7) Browse.monthName(bk) else bk) { bucket = null } }
                for ((k, v) in filters.toSortedMap()) FilterChip(if (k == "gov_id") Governments.names[v] ?: v else v) { setFilter(k, null) }
            }
            FreshnessNote(datasetID)
        }
    }

    Screen(
        title,
        actions = {
            ToolbarIcon(mode.symbol, "View as ${mode.label}") {
                val modes = DMode.entries.filter { it != DMode.MAP || all.any { r -> r.number("lat") != null } }
                modeName = modes[(modes.indexOf(mode) + 1) % modes.size].name
            }
            ToolbarIcon(if (filters.isEmpty()) "line.3.horizontal.decrease.circle" else "line.3.horizontal.decrease.circle.fill", "Sort and filter") { showOptions = true }
        },
        onRefresh = { store.load(datasetID, force = true) },
        spacing = 0,
    ) {
        item { FilterField(query, "Search ${title.lowercase()}") { query = it }; Spacer(Modifier.height(12.dp)) }
        if (all.isEmpty()) {
            item {
                val e = store.errors[datasetID]
                if (e != null) Unavailable("Couldn't load this data", e) else Loading()
            }
            return@Screen
        }
        item { controls(); Spacer(Modifier.height(12.dp)) }
        when {
            mode == DMode.MAP -> item {
                RecordsMap(datasetID, rows, Modifier.fillMaxWidth().height(460.dp).card(18.dp)) { nav.push(Route.Record(datasetID, it.id)) }
            }
            mode == DMode.TABLE -> tableContent(spec, rows, govColumn, periods.isNotEmpty(), tableSort, { tableSort = it }) { nav.push(Route.Record(datasetID, it.id)) }
            isVotes -> {
                val summaries = rows.associate { it.id to VoteSummary(it) }
                val shown = rows.filter { r ->
                    when (voteFilter) { VoteFilter.ALL -> true; VoteFilter.SPLIT -> summaries[r.id]?.split == true; VoteFilter.FAILED -> summaries[r.id]?.passed == false }
                }
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        ChipRow(VoteFilter.entries.map { it to it.label }, voteFilter,
                            mapOf(VoteFilter.ALL to rows.size, VoteFilter.SPLIT to summaries.values.count { it.split }, VoteFilter.FAILED to summaries.values.count { it.passed == false })) { voteFilter = it }
                        VoteLegend()
                        if (q.isEmpty() && voteFilter == VoteFilter.ALL) SummaryCard(datasetID, spec, inPeriod, byRow, period, periods, govColumn, bucket, { bucket = if (bucket == it) null else it }) { k, v -> setFilter(k, v) }
                        Spacer(Modifier.height(8.dp))
                    }
                }
                for (m in Browse.meetings(shown)) {
                    val key = "${m.date}|${m.board}"
                    val open = key !in collapsed
                    item(key = "h$key") {
                        Box(Modifier.clickable { collapsed = if (open) collapsed + key else collapsed - key }.padding(top = 14.dp, bottom = 8.dp)) {
                            GroupHeader(m.board, m.votes.size, null, "vote", Dates.parse(m.date)?.let { Dates.display(it, false) } ?: m.date)
                        }
                    }
                    if (open) cardItems(m.votes, key = { "v${it.id}" }) { v ->
                        Box {
                            Box(Modifier.combinedClickable(onLongClick = { shareFor = v.id }) { nav.push(Route.Record(datasetID, v.id)) }.padding(horizontal = 14.dp, vertical = 10.dp)) { VoteRow(v, summaries[v.id] ?: VoteSummary(v)) }
                            ShareDropdown(shareFor == v.id, { shareFor = null }, spec.title(v), { RecordShare.text(datasetID, v, info?.columns.orEmpty(), info?.title) }, RecordShare.url(datasetID, v))
                        }
                    }
                }
                if (shown.isEmpty()) item { EmptyState(q, period) { periodLabel = "" } }
            }
            else -> {
                if (q.isEmpty()) item {
                    SummaryCard(datasetID, spec, inPeriod, byRow, period, periods, govColumn, bucket, { bucket = if (bucket == it) null else it }) { k, v -> setFilter(k, v) }
                    Spacer(Modifier.height(8.dp))
                }
                val groups = Browse.groups(rows, group, spec, byRow)
                val maxAmount = rows.mapNotNull { spec.amount(it) }.maxOrNull() ?: 0.0
                val hide = (group as? Browse.GroupKey.Column)?.column
                for (g in groups) {
                    val open = g.key !in collapsed
                    if (group != Browse.GroupKey.None) item(key = "h${g.key}") {
                        Box(Modifier.clickable { collapsed = if (open) collapsed + g.key else collapsed - g.key }.padding(top = 14.dp, bottom = 8.dp)) {
                            GroupHeader(g.title, g.rows.size, if (totalInfo != null) g.total else null)
                        }
                    } else item { Spacer(Modifier.height(8.dp)) }
                    if (open) cardItems(g.rows, key = { "r${it.id}" }) { r ->
                        // long-press a record for Copy text, Copy link and Share
                        Box {
                            CompactRecordRow(spec, r, maxAmount, hide, onLongClick = { shareFor = r.id }) { nav.push(Route.Record(datasetID, r.id)) }
                            ShareDropdown(shareFor == r.id, { shareFor = null }, spec.title(r), { RecordShare.text(datasetID, r, info?.columns.orEmpty(), info?.title) }, RecordShare.url(datasetID, r))
                        }
                    }
                }
                if (rows.isEmpty()) item { EmptyState(q, period) { periodLabel = "" } }
                info?.description?.let { d ->
                    item { Text("$d Every record links to its source; check the original before relying on one figure.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 18.dp)) }
                }
            }
        }
    }

    if (showOptions) {
        ModalBottomSheet(onDismissRequest = { showOptions = false }, containerColor = Brand.canvas) {
            Column(Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, bottom = 32.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("Sort and filter", style = T.title3, color = Brand.text)
                EyebrowHeader("Sort")
                val sorts = DSort.entries.filter { when (it) { DSort.AMOUNT -> spec.amountKeys.isNotEmpty(); DSort.NEWEST -> periods.isNotEmpty(); else -> true } }
                ChipRow(sorts.map { it to it.label }, sort) { sortName = it.name }
                val cols = filterColumns(spec, info, all)
                if (cols.isNotEmpty()) {
                    EyebrowHeader("Filter")
                    Flow(spacing = 8.dp) {
                        for ((key, choices) in cols) {
                            val cur = filters[key]
                            MenuPicker(cur ?: "Any ${Format.label(key).lowercase()}", listOf<Pair<String?, String>>(null to "Any ${Format.label(key).lowercase()}") + choices.map { it to it }, Format.label(key)) { setFilter(key, it) }
                        }
                    }
                }
                if (filters.isNotEmpty()) LinkLine("Clear filters", "xmark") { filterList = emptyList() }
                LinkLine("Open on BayCounty.me", "safari") { showOptions = false; o.open(info?.pageURL) }
                info?.csvURL?.let { csv ->
                    LinkLine("Share CSV link", "square.and.arrow.up") {
                        showOptions = false
                        val send = android.content.Intent(android.content.Intent.ACTION_SEND).setType("text/plain").putExtra(android.content.Intent.EXTRA_TEXT, csv)
                        context.startActivity(android.content.Intent.createChooser(send, null).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                }
            }
        }
    }
}

/** Filter choices: the spec's preferred columns, then any column the catalog lists a short set of values for. */
private fun filterColumns(spec: DatasetSpec, info: me.baycounty.kit.DatasetInfo?, all: List<DataRow>): List<Pair<String, List<String>>> {
    info ?: return emptyList()
    val keys = spec.filterKeys.toMutableList()
    for (c in info.columns) if (c.name !in keys && c.name !in DatasetSpec.hiddenColumns && c.choices.size in 2..12) keys += c.name
    return keys.take(6).mapNotNull { key ->
        var choices = info.column(key)?.choices ?: emptyList()
        if (choices.isEmpty()) choices = all.mapNotNull { r -> r[key]?.let { Format.value(it, key) } }.filter { it.isNotEmpty() }.toSet().sorted()
        if (choices.size in 2..80) key to choices else null
    }
}

@Composable
private fun EmptyState(query: String, period: Period?, showAll: () -> Unit) {
    if (query.isEmpty() && period != null) Unavailable("Nothing from ${period.label}", "No records match for this year.", "Show all years", "calendar", showAll)
    else Unavailable("No results", if (query.isEmpty()) null else "Nothing matches “$query”.", symbol = "magnifyingglass")
}

/** Headline numbers, a bar chart by month or year (tap a bar to see its records), and the biggest names. */
@Composable
private fun SummaryCard(
    datasetID: String, spec: DatasetSpec, base: List<DataRow>, byRow: Map<Int, Period>, period: Period?, periods: List<Period>,
    govColumn: String?, bucket: String?, onBucket: (String) -> Unit, onTop: (String, String) -> Unit,
) {
    val totalInfo = Browse.totals[datasetID]
    val byAmount = totalInfo != null
    val tiles = buildList {
        add(Browse.noun(datasetID) to Format.number(base.size.toDouble()))
        val amounts = base.mapNotNull { spec.amount(it) }
        if (totalInfo != null) add(totalInfo.label to Format.compactMoney(amounts.sum()))
        else amounts.maxOrNull()?.let { add("Largest" to Format.compactMoney(it)) }
        govColumn?.let { g -> val n = base.mapNotNull { it.string(g) }.toSet().size; if (n > 1) add((if (g == "board") "Boards" else "Governments") to "$n") }
    }
    val buckets: List<Browse.Bucket> = if (period != null) {
        if (period.fiscal) emptyList() else {
            val now = Period.currentYear()
            val last = if (period.year == now) LocalDate.now(Dates.chicago).monthValue else 12
            Browse.months(base, spec, period.year, last).let { bs -> if (bs.count { it.count > 0 } >= 2) bs else emptyList() }
        }
    } else Browse.years(base, spec, byRow).let { if (it.size >= 2) it.takeLast(12) else emptyList() }
    val what = totalInfo?.let { "${it.label} each" } ?: "${Browse.noun(datasetID)} each"
    val chartTitle = if (period != null) "$what month" else if (periods.firstOrNull()?.fiscal == true) "$what fiscal year" else "$what year"
    val t = spec.titleKeys.firstOrNull() ?: ""
    val topKey = if (t in listOf("vendor", "payee", "contributor", "member", "candidate", "applicant")) t else govColumn
    val top = topKey?.let { Browse.top(base, it, spec, byAmount) } ?: emptyList()
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        if (tiles.isNotEmpty()) StatStrip(tiles)
        if (buckets.isNotEmpty()) {
            val fmt: (Double) -> String = { if (byAmount) Format.compactMoney(it) else Format.number(it) }
            Column(Modifier.fillMaxWidth().card(12.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(chartTitle, style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                    if (bucket != null) Text("Show all", style = T.caption.copy(fontWeight = FontWeight.Medium), color = Brand.navy, modifier = Modifier.clickable { onBucket(bucket) }.padding(4.dp))
                    else Text("Tap a bar", style = T.caption, color = Brand.secondary)
                }
                val selectedLabel = buckets.firstOrNull { it.key == bucket }?.label
                BarChart(buckets.map { ChartPoint(it.label, if (byAmount) it.amount else it.count.toDouble()) }, format = fmt, selectedLabel = selectedLabel) { label ->
                    buckets.firstOrNull { it.label == label }?.let { onBucket(it.key) }
                }
                buckets.firstOrNull { it.key == bucket }?.let { bk ->
                    Text("${if (bk.key.length == 7) Browse.monthName(bk.key, false) else bk.label}: ${if (byAmount) Format.compactMoney(bk.amount) + " across " else ""}${bk.count} ${if (bk.count == 1) "record" else "records"}",
                        style = T.footnote, color = Brand.secondary)
                }
            }
        }
        if (topKey != null && top.size >= 2) TopBars((if (datasetID in Browse.giftLists) "Total given by " else "Biggest by ") + Browse.GroupKey.Column(topKey).label.lowercase(), top, byAmount,
            countUnit = if (datasetID in Browse.giftLists) "gift" else null) { onTop(topKey, it) }
        totalInfo?.note?.let { Text(it, style = T.caption2, color = Brand.secondary) }
    }
}

private fun LazyListScope.tableContent(
    spec: DatasetSpec, rows: List<DataRow>, govColumn: String?, hasDates: Boolean, sortState: String, setSort: (String) -> Unit, open: (DataRow) -> Unit,
) {
    val cols = buildList { if (hasDates) add(TCol.DATE); add(TCol.TITLE); if (govColumn != null) add(TCol.GOV); if (spec.amountKeys.isNotEmpty()) add(TCol.AMOUNT) }
    val col = runCatching { TCol.valueOf(sortState.substringBefore(":")) }.getOrDefault(TCol.DATE).let { if (it in cols) it else TCol.TITLE }
    val asc = sortState.substringAfter(":") == "true"
    val sorted = when (col) {
        TCol.DATE -> rows.sortedBy { spec.newestKey(it) }
        TCol.TITLE -> rows.sortedWith(compareBy(String.CASE_INSENSITIVE_ORDER) { spec.title(it) })
        TCol.GOV -> rows.sortedBy { it.string(govColumn ?: "") ?: "~" }
        TCol.AMOUNT -> rows.sortedBy { spec.amount(it) ?: Double.NEGATIVE_INFINITY }
    }.let { if (asc) it else it.reversed() }
    fun width(c: TCol) = when (c) { TCol.DATE -> 58.dp; TCol.GOV -> 74.dp; TCol.AMOUNT -> 70.dp; TCol.TITLE -> 0.dp }
    @Suppress("OPT_IN_USAGE")
    stickyHeader {
        Row(Modifier.fillMaxWidth().background(Brand.sunken).padding(horizontal = 12.dp, vertical = 9.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (c in cols) {
                val label = if (c == TCol.TITLE) Browse.GroupKey.Column(spec.titleKeys.firstOrNull() ?: "name").label else c.label
                val m = (if (c == TCol.TITLE) Modifier.weight(1f) else Modifier.width(width(c)))
                Row(m.clickable(role = Role.Button) { setSort(if (col == c) "${c.name}:${!asc}" else "${c.name}:${c == TCol.TITLE || c == TCol.GOV}") }
                    .semantics { contentDescription = "Sort by ${c.label}" },
                    horizontalArrangement = if (c == TCol.AMOUNT) Arrangement.End else Arrangement.Start, verticalAlignment = Alignment.CenterVertically) {
                    Text(label, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = if (col == c) Brand.navy else Brand.secondary, maxLines = 1)
                    if (col == c) Icon(icon(if (asc) "chevron.up" else "chevron.down"), null, tint = Brand.navy, modifier = Modifier.size(14.dp))
                }
            }
        }
    }
    items(sorted.size, key = { "t${sorted[it].id}" }) { i ->
        val r = sorted[i]
        Row(Modifier.fillMaxWidth().background(if (i % 2 == 0) Brand.surface else Brand.canvas).clickable { open(r) }.heightIn(min = 44.dp).padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (c in cols) when (c) {
                TCol.DATE -> Text(tableShortDate(r), style = T.subhead, color = Brand.secondary, maxLines = 1, modifier = Modifier.width(width(c)))
                TCol.TITLE -> Text(spec.title(r), style = T.subhead, color = Brand.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                TCol.GOV -> Text(govColumn?.let { r.string(it) }?.let(Browse::shortGovernment) ?: "", style = T.caption, color = Brand.secondary, maxLines = 1, modifier = Modifier.width(width(c)))
                TCol.AMOUNT -> Text(spec.amount(r)?.let(Format::compactMoney) ?: "", style = T.subheadBold, color = Brand.text, textAlign = TextAlign.End, maxLines = 1, modifier = Modifier.width(width(c)))
            }
        }
    }
    if (rows.isEmpty()) item { Unavailable("No results", symbol = "magnifyingglass") }
}

@Suppress("unused") private val keepFill = Modifier.fillMaxSize()
