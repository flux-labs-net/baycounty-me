package me.baycounty.staff

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Flag
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import me.baycounty.kit.AlertArea
import me.baycounty.kit.Staff
import me.baycounty.kit.StaffAlert
import me.baycounty.kit.StaffFlag
import me.baycounty.kit.StaffOverview
import me.baycounty.kit.StaffPost
import me.baycounty.kit.StaffReach

/** A screen opened over the tabs. */
sealed interface Page {
    data object SendAlert : Page
    data class Alert(val alert: StaffAlert) : Page
    data class Notice(val post: StaffPost?) : Page
    data class Flag(val flag: StaffFlag) : Page
    data object Records : Page
    data object SendFile : Page
}

@Composable
fun StaffApp(model: StaffModel, screen: String?, locked: Boolean, onUnlock: () -> Unit) {
    LaunchedEffect(Unit) { model.refresh() }
    when {
        !model.signedIn || screen == "signin" -> SignInScreen(model)
        screen == "signin-code" -> SignInScreen(model, codeSentTo = "clerk@example.gov")
        model.me == null -> Loading(model)
        locked || screen == "locked" -> LockScreen(onUnlock)
        else -> StaffRoot(model, screen)
    }
}

@Composable
private fun Loading(model: StaffModel) {
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxSize().background(Brand.canvas).padding(32.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        val e = model.error
        if (e == null) CircularProgressIndicator(color = Brand.navy) else {
            Text(e, style = T.subhead, color = Brand.secondary)
            Spacer(Modifier.height(14.dp))
            PrimaryButton("Try again") { scope.launch { model.refresh() } }
            TextButton({ scope.launch { model.signOut() } }) { Text("Sign out", color = Brand.salmon) }
        }
    }
}

@Composable
private fun LockScreen(onUnlock: () -> Unit) {
    Column(Modifier.fillMaxSize().background(Brand.canvas).padding(32.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(Icons.Filled.Fingerprint, null, tint = Brand.navy, modifier = Modifier.size(56.dp))
        Spacer(Modifier.height(16.dp))
        Text("BayCounty.me Staff is locked", style = androidx.compose.material3.MaterialTheme.typography.titleLarge, color = Brand.text)
        Spacer(Modifier.height(8.dp))
        Text("Unlock with your fingerprint, face or screen lock. The app locks after 5 minutes away.", style = T.subhead, color = Brand.secondary)
        Spacer(Modifier.height(20.dp))
        PrimaryButton("Unlock", onClick = onUnlock)
        Spacer(Modifier.weight(1f, fill = false))
        FluxFooter()
    }
}

@Composable
fun SignInScreen(model: StaffModel, codeSentTo: String? = null) {
    val scope = rememberCoroutineScope()
    var email by remember { mutableStateOf(codeSentTo ?: "") }
    var code by remember { mutableStateOf("") }
    var sent by remember { mutableStateOf(codeSentTo != null) }
    var busy by remember { mutableStateOf(false) }
    var resent by remember { mutableStateOf(false) }
    // The Flux footer stays pinned to the bottom; everything above it scrolls.
    Column(Modifier.fillMaxSize().background(Brand.canvas).imePadding()) {
    Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(20.dp).padding(top = 40.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Image(painterResource(R.drawable.app_mark), null, Modifier.size(48.dp).clip(RoundedCornerShape(12.dp)).border(1.dp, Brand.hairline, RoundedCornerShape(12.dp)))
            Spacer(Modifier.width(14.dp))
            Text("BayCounty.me Staff", style = androidx.compose.material3.MaterialTheme.typography.headlineMedium, color = Brand.text)
        }
        Spacer(Modifier.height(12.dp))
        Text("For city and county staff. Send alerts, post notices and flag data for your government.", style = T.subhead, color = Brand.secondary)
        Spacer(Modifier.height(18.dp))
        Card {
            Column(Modifier.padding(16.dp)) {
                if (!sent) {
                    Eyebrow("Work email")
                    OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth(), placeholder = { Text("you@city.gov") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Send))
                    Spacer(Modifier.height(12.dp))
                    PrimaryButton(if (busy) "Sending…" else "Email me a code", enabled = !busy && "@" in email) {
                        busy = true; scope.launch { sent = model.login(email.trim()); busy = false }
                    }
                } else {
                    Text("If $email has access, a 6-digit code is on its way. It expires in 10 minutes.", style = T.subhead, color = Brand.text)
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(code, { code = it.filter(Char::isDigit).take(6) }, Modifier.fillMaxWidth(), placeholder = { Text("123456") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done))
                    Spacer(Modifier.height(12.dp))
                    PrimaryButton(if (busy) "Checking…" else "Sign in", enabled = !busy && code.length == 6) {
                        busy = true; scope.launch { model.verify(email.trim(), code); busy = false }
                    }
                    if (resent) Text("New code sent. Use the newest email; older codes stop working.", style = T.footnote, color = Brand.secondary,
                        modifier = Modifier.padding(top = 8.dp))
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        TextButton({ busy = true; code = ""; model.error = null; scope.launch { resent = model.login(email.trim()); busy = false } }, enabled = !busy) {
                            Text("Send a new code")
                        }
                        TextButton({ sent = false; resent = false; code = ""; model.error = null }) { Text("Use a different email") }
                    }
                }
                ErrorLine(model.error)
            }
        }
    }
        FluxFooter()
    }
}

private data class Tab(val key: String, val label: String, val icon: ImageVector)

@Composable
fun StaffRoot(model: StaffModel, screen: String?) {
    var tab by remember {
        mutableStateOf(when (screen) { "alerts", "send", "alert" -> "alerts"; "notices", "notice" -> "notices"; "flags", "flag" -> "flags"; "more" -> "more"; else -> "home" })
    }
    var page by remember {
        mutableStateOf<Page?>(when (screen) {
            "send" -> Page.SendAlert
            "alert" -> model.alerts.firstOrNull()?.let { Page.Alert(it) }
            "notice" -> Page.Notice(null)
            "flag" -> model.flags.firstOrNull { it.status == "open" }?.let { Page.Flag(it) }
            "records" -> Page.Records
            "send-file", "send-file-preview" -> Page.SendFile
            else -> null
        })
    }
    BackHandler(enabled = page != null) { page = if (page == Page.SendFile) Page.Records else null }
    page?.let { p ->
        when (p) {
            Page.SendAlert -> SendAlertScreen(model, demoFill = screen == "send") { page = null }
            is Page.Alert -> AlertDetail(model, p.alert) { page = null }
            is Page.Notice -> NoticeEditor(model, p.post, demoFill = screen == "notice") { page = null }
            is Page.Flag -> FlagDetail(model, p.flag, answering = model.isOwner && model.workspaceId == null) { page = null }
            Page.Records -> RecordsScreen(model, onSend = { page = Page.SendFile }) { page = null }
            Page.SendFile -> SendFileScreen(model, demoPreview = screen == "send-file-preview") { page = Page.Records }
        }
        return
    }
    val all = model.isOwner && model.workspaceId == null
    val tabs = listOf(
        Tab("home", if (all) "Overview" else "Home", Icons.Filled.GridView), Tab("alerts", "Alerts", Icons.Filled.Warning),
        Tab("notices", "Notices", Icons.Filled.Description), Tab("flags", "Flags", Icons.Filled.Flag), Tab("more", "More", Icons.Filled.MoreHoriz),
    )
    val title = when (tab) {
        "home" -> if (all) "All governments" else model.workspace?.name ?: "Home"
        "alerts" -> "Alerts"; "notices" -> "Notices"; "flags" -> if (all) "Flags to answer" else "Data flags"; else -> "More"
    }
    Scaffold(
        containerColor = Brand.canvas,
        topBar = {
            TopAppBar(title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) }, actions = { WorkspaceMenu(model) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Brand.canvas, titleContentColor = Brand.text))
        },
        bottomBar = {
            NavigationBar(containerColor = Brand.surface) {
                tabs.forEach { t ->
                    val badge = when (t.key) { "alerts" -> model.alerts.count { it.isWaiting }; "flags" -> model.flags.count { it.status == "open" }; else -> 0 }
                    NavigationBarItem(selected = tab == t.key, onClick = { tab = t.key },
                        icon = { BadgedBox(badge = { if (badge > 0) Badge { Text("$badge") } }) { Icon(t.icon, null) } },
                        label = { Text(t.label) },
                        colors = NavigationBarItemDefaults.colors(selectedIconColor = Brand.navy, selectedTextColor = Brand.navy, indicatorColor = Brand.sunken))
                }
            }
        },
    ) { pad ->
        Box(Modifier.padding(pad).fillMaxSize()) {
            when (tab) {
                "home" -> if (all) OverviewScreen(model) else WorkspaceHome(model, onRecords = { page = Page.Records }) { page = Page.SendAlert }
                "alerts" -> if (model.workspaceId == null) PickGovernment(model, "alerts") else AlertsScreen(model, { page = Page.SendAlert }) { page = Page.Alert(it) }
                "notices" -> if (model.workspaceId == null) PickGovernment(model, "notices") else NoticesScreen(model) { page = Page.Notice(it) }
                "flags" -> FlagsScreen(model, all) { page = Page.Flag(it) }
                else -> MoreScreen(model) { page = Page.Records }
            }
        }
    }
}

/** The government switcher: the owner picks any government or All governments; staff with several pick theirs. */
@Composable
private fun WorkspaceMenu(model: StaffModel) {
    val me = model.me ?: return
    if (!me.admin && me.workspaces.size < 2) return
    val scope = rememberCoroutineScope()
    var open by remember { mutableStateOf(false) }
    Box {
        TextButton({ open = true }) {
            Text(model.workspace?.name?.removePrefix("City of ") ?: "All", style = T.subhead.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, maxLines = 1)
            Icon(Icons.Filled.ArrowDropDown, null, tint = Brand.navy)
        }
        DropdownMenu(open, { open = false }) {
            if (me.admin) DropdownMenuItem({ Text("All governments") }, { open = false; scope.launch { model.open(null) } })
            me.workspaces.forEach { w -> DropdownMenuItem({ Text(w.name) }, { open = false; scope.launch { model.open(w.id) } }) }
        }
    }
}

@Composable
internal fun Screen(content: @Composable () -> Unit) {
    Column(Modifier.fillMaxSize().background(Brand.canvas).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) { content() }
}

@Composable
internal fun PickGovernment(model: StaffModel, what: String) {
    val scope = rememberCoroutineScope()
    Screen {
        Text("Pick a government to see its $what.", style = T.subhead, color = Brand.secondary)
        val ws = model.me?.workspaces.orEmpty()
        Divided(ws.size) { i -> RowLink({ scope.launch { model.open(ws[i].id) } }, { Text(ws[i].name, style = T.bodyBold, color = Brand.text) }) }
    }
}

@Composable
fun OverviewScreen(model: StaffModel) {
    val scope = rememberCoroutineScope()
    val o = model.overview ?: return Screen { if (model.loading) CircularProgressIndicator(color = Brand.navy); ErrorLine(model.error) }
    Screen {
        TileGrid(listOf(
            { m -> StatTile(o.totals.waitingAlerts, "Alerts waiting for a second person", Icons.Filled.Groups, m, alert = o.totals.waitingAlerts > 0) },
            { m -> StatTile(o.totals.openFlags, "Data flags to answer", Icons.Filled.Flag, m, alert = o.totals.openFlags > 0) },
            { m -> StatTile(o.totals.liveAlerts, "Live alerts", Icons.Filled.Sensors, m, tint = Brand.good) },
            { m -> StatTile(o.totals.members, "Staff in ${o.totals.workspaces} governments", Icons.Filled.People, m) },
        ))
        Column {
            Eyebrow("Governments")
            val rows = o.workspaces.filter { it.needsAttention } + o.workspaces.filter { !it.needsAttention }
            Divided(rows.size) { i -> GovRow(rows[i]) { scope.launch { model.open(rows[i].id) } } }
        }
        Activity("Latest everywhere", o.activity.map { it.sentence to listOfNotNull(it.govName, Staff.whenOf(it.at)).joinToString(" · ") })
        ErrorLine(model.error)
    }
}

@Composable
private fun GovRow(w: StaffOverview.Row, onClick: () -> Unit) {
    val staff = if (w.members == 0) "No staff yet" else "${w.members} staff"
    RowLink(onClick, {
        Text(w.name, style = T.bodyBold, color = Brand.text)
        Text(w.lastActivity?.let { "$staff · active ${Staff.whenOf(it)}" } ?: staff, style = T.footnote, color = Brand.secondary, maxLines = 1)
    }) {
        when {
            w.waitingAlerts > 0 -> Chip("${w.waitingAlerts} waiting", Brand.amber)
            w.openFlags > 0 -> Chip("${w.openFlags} flag${if (w.openFlags == 1) "" else "s"}", Brand.amber)
            w.liveAlerts > 0 -> Chip("Live alert", Brand.salmon)
        }
    }
}

@Composable
private fun Activity(title: String, items: List<Pair<String, String>>) {
    Column {
        Eyebrow(title)
        if (items.isEmpty()) Card { Text("Nothing yet.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
        else Divided(items.size) { i ->
            Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp)) {
                Text(items[i].first, style = T.subhead, color = Brand.text)
                Text(items[i].second, style = T.caption, color = Brand.secondary)
            }
        }
    }
}

@Composable
fun WorkspaceHome(model: StaffModel, onRecords: () -> Unit = {}, onSend: () -> Unit) {
    val h = model.home ?: return Screen { if (model.loading) CircularProgressIndicator(color = Brand.navy); ErrorLine(model.error) }
    Screen {
        if (model.can("alert_sender")) PrimaryButton("Send an alert", color = Brand.salmonFill, icon = Icons.Filled.Warning, onClick = onSend)
        model.submissions?.takeIf { model.can("submit") }?.let { RecordsDueCard(it, onRecords) }
        TileGrid(listOf(
            { m -> StatTile(h.counts.liveAlerts, "Live alerts", Icons.Filled.Sensors, m, alert = h.counts.liveAlerts > 0) },
            { m -> StatTile(h.counts.waitingAlerts, "Waiting for a second person", Icons.Filled.Groups, m, alert = h.counts.waitingAlerts > 0) },
            { m -> StatTile(h.counts.notices, "Notices you posted", Icons.Filled.Description, m) },
            { m -> StatTile(h.counts.openFlags, "Open data flags", Icons.Filled.Flag, m, tint = Brand.amber) },
        ))
        Activity("Latest", h.activity.map { it.sentence to Staff.whenOf(it.at) })
        val r = Staff.roleLabel[model.role]?.lowercase() ?: model.role
        Text("You're signed in as ${if (model.role == "alert_sender") "an" else "a"} $r. Numbers from public records can't be changed here, only flagged.",
            style = T.footnote, color = Brand.secondary)
    }
}

@Composable
fun AlertsScreen(model: StaffModel, onSend: () -> Unit, onOpen: (StaffAlert) -> Unit) {
    Screen {
        if (model.can("alert_sender")) PrimaryButton("Send an alert", color = Brand.salmonFill, icon = Icons.Filled.Warning, onClick = onSend)
        val now = model.alerts.filter { it.isLive || it.isWaiting }
        val past = model.alerts.filter { !it.isLive && !it.isWaiting }
        Column {
            Eyebrow("Now")
            if (now.isEmpty()) Card { Text("No live alerts.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            else Divided(now.size) { i -> AlertRow(model, now[i]) { onOpen(now[i]) } }
        }
        if (past.isNotEmpty()) Column { Eyebrow("Past"); Divided(past.size) { i -> AlertRow(model, past[i]) { onOpen(past[i]) } } }
    }
}

@Composable
private fun AlertRow(model: StaffModel, a: StaffAlert, onClick: () -> Unit) {
    RowLink(onClick, {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Chip(a.statusLabel, alertColor(a)); Spacer(Modifier.width(6.dp))
            Text((model.alertKinds[a.kind]?.substringBefore(" (") ?: a.kind) + if (a.countywide) " · Countywide" else "", style = T.caption, color = Brand.secondary)
        }
        Spacer(Modifier.height(4.dp))
        Text(a.title, style = T.bodyBold, color = Brand.text)
        Text(if (a.isLive) "Sent ${Staff.whenOf(a.sentAt)} · ends ${Staff.whenOf(a.endsAt)}" else "By ${a.createdBy} · ${Staff.whenOf(a.createdAt)}", style = T.caption, color = Brand.secondary)
    })
}

/** A screen over the tabs with a back arrow. */
@Composable
internal fun Sub(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
    Scaffold(containerColor = Brand.canvas, topBar = {
        TopAppBar(title = { Text(title) }, navigationIcon = { IconButton(onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = Brand.canvas, titleContentColor = Brand.text))
    }) { pad -> Box(Modifier.padding(pad).imePadding()) { Screen(content) } }
}

@Composable
fun AlertDetail(model: StaffModel, a: StaffAlert, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var sure by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    fun run(f: suspend () -> String?) { busy = true; scope.launch { err = f(); busy = false; if (err == null) onBack() } }
    Sub("Alert", onBack) {
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Chip(a.statusLabel, alertColor(a))
                Text(a.title, style = androidx.compose.material3.MaterialTheme.typography.titleLarge, color = Brand.text)
                Text(a.message, style = T.body, color = Brand.text)
                a.instruction?.takeIf { it.isNotEmpty() }?.let { Text(it, style = T.bodyBold, color = Brand.navy) }
            }
        }
        AlertArea.parse(a.geometry)?.let { area -> AreaMap(area, Modifier.fillMaxWidth().height(220.dp)) }
        Card {
            Detail("Kind", model.alertKinds[a.kind] ?: a.kind)
            Detail("Reaches", if (a.countywide) "All of Bay County" else model.workspace?.name ?: "")
            Detail("Severity", Staff.severities.firstOrNull { it.first == a.severity }?.second ?: "Severe")
            Detail("Written by", a.createdBy)
            a.confirmedBy?.let { Detail("Confirmed by", it) }
            a.sentAt?.let { Detail("Sent", Staff.whenOf(it)) }
            a.endsAt?.let { Detail(if (a.isLive) "Ends" else "Ended", Staff.whenOf(it)) }
            a.sentSentence?.let { Detail("Sent to", it) }
        }
        if (model.can("alert_sender") && (a.isLive || a.isWaiting)) Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (a.isWaiting) {
                if (a.canConfirm(model.me?.email ?: "")) PrimaryButton("Confirm and send to all of Bay County", color = Brand.salmonFill, enabled = !busy) { run { model.confirm(a) } }
                else Text("You wrote this alert, so another alert sender has to confirm it.", style = T.subhead, color = Brand.secondary)
            }
            val label = if (a.isWaiting) (if (sure) "Cancel it: are you sure?" else "Cancel this alert") else (if (sure) "End it now: are you sure?" else "End this alert")
            QuietButton(label, color = Brand.salmon, enabled = !busy) { if (sure) run { model.end(a) } else sure = true }
            ErrorLine(err)
        }
    }
}

@Composable
private fun Picker(label: String, value: String, options: List<Pair<String, String>>, onPick: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        Row(Modifier.fillMaxWidth().clickable { open = true }.heightIn(min = 52.dp).padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(label, style = T.body, color = Brand.text, modifier = Modifier.weight(1f))
            Text(options.firstOrNull { it.first == value }?.second ?: value, style = T.body, color = Brand.secondary, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1.4f, fill = false))
            Icon(Icons.Filled.ArrowDropDown, null, tint = Brand.secondary)
        }
        DropdownMenu(open, { open = false }) { options.forEach { (k, v) -> DropdownMenuItem({ Text(v) }, { onPick(k); open = false }) } }
    }
}

/** The circles the web workspace offers (site/area_map.js), in meters. */
private val RADII = listOf(0.0 to "No circle", 30.0 to "100 ft", 76.0 to "¼ block (250 ft)", 152.0 to "500 ft", 402.0 to "¼ mile", 805.0 to "½ mile", 1609.0 to "1 mile")

@Composable
fun SendAlertScreen(model: StaffModel, demoFill: Boolean, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var kind by remember { mutableStateOf("boil-water") }
    var severity by remember { mutableStateOf(if (demoFill) "moderate" else "severe") }
    var hours by remember { mutableStateOf(if (demoFill) 48 else 24) }
    var countywide by remember { mutableStateOf(false) }
    var title by remember { mutableStateOf(if (demoFill && model.demo != null) "Boil water: Ohio Ave, 5th to 9th St" else "") }
    var message by remember { mutableStateOf(if (demoFill && model.demo != null) "A water main broke on Ohio Ave. Crews are repairing it now. Pressure may be low." else "") }
    var instruction by remember { mutableStateOf(if (demoFill && model.demo != null) "Boil water for one minute before drinking or cooking until we lift this notice." else "") }
    var reach by remember { mutableStateOf<StaffReach?>(null) }
    var review by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    var done by remember { mutableStateOf<String?>(null) }
    var pins by remember { mutableStateOf(listOf<AlertArea.Coord>()) }
    var radius by remember { mutableStateOf(76.0) }
    LaunchedEffect(kind, countywide) { reach = model.reach(kind, countywide) }
    Sub("Send an alert", onBack) {
        done?.let { Card { Column(Modifier.padding(16.dp)) { Text(it, style = T.bodyBold, color = Brand.good); Spacer(Modifier.height(10.dp)); PrimaryButton("Close", onClick = onBack) } }; return@Sub }
        Column {
            Eyebrow("What kind")
            Card {
                Picker("Kind", kind, Staff.alertOrder.mapNotNull { k -> model.alertKinds[k]?.let { k to it } }) { kind = it }
                Picker("How serious", severity, Staff.severities) { severity = it }
                Picker("Ends after", hours.toString(), Staff.hourChoices.map { it.toString() to Staff.hoursLabel(it) }) { hours = it.toInt() }
                if (model.workspace?.countywide == true) Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("All of Bay County", style = T.body, color = Brand.text, modifier = Modifier.weight(1f)); Switch(countywide, { countywide = it })
                }
            }
        }
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Eyebrow("The alert")
            OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Headline") }, maxLines = 3)
            OutlinedTextField(message, { message = it }, Modifier.fillMaxWidth(), label = { Text("What is happening") }, minLines = 3)
            OutlinedTextField(instruction, { instruction = it }, Modifier.fillMaxWidth(), label = { Text("What people should do (optional)") }, minLines = 2)
            Text("Keep the headline short: it is what shows on a locked phone.", style = T.footnote, color = Brand.secondary)
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Eyebrow("Map (optional)")
            AreaMap(AlertArea(pins.map { AlertArea.Shape.Pin(it, radius.takeIf { r -> r > 0 }) }), Modifier.fillMaxWidth().height(260.dp),
                onTap = { pins = pins + it }, onPinTap = { i -> pins = pins.filterIndexed { j, _ -> j != i } })
            Card {
                Picker("Circle around each pin", radius.toInt().toString(), RADII.map { it.first.toInt().toString() to it.second }) { radius = it.toDouble() }
                if (pins.isNotEmpty()) QuietButton("Clear the map", color = Brand.salmon) { pins = emptyList() }
            }
            Text(if (pins.isEmpty()) "Tap the map where it applies, like a main break or the street that's closed. Residents see it with the alert. Lines and drawn areas are on the web workspace."
                 else "${pins.size} pin${if (pins.size == 1) "" else "s"}. Tap a pin to take it off.", style = T.footnote, color = Brand.secondary)
        }
        Column {
            Eyebrow("Who gets it")
            Card {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(reach?.sentence ?: "Checking who this reaches…", style = T.subhead, color = Brand.text)
                    if (countywide) Text("A countywide alert waits until a second alert sender confirms it.", style = T.subhead, color = Brand.amber)
                }
            }
        }
        PrimaryButton(if (countywide) "Review and save" else "Review and send", color = Brand.salmonFill, enabled = !busy && title.isNotBlank() && message.isNotBlank()) { review = true }
        ErrorLine(err)
    }
    if (review) AlertDialog(
        onDismissRequest = { review = false },
        title = { Text(if (countywide) "Save this countywide alert?" else "Send this alert now?") },
        text = { Text("$title\n\n${reach?.sentence ?: ""}" + if (pins.isEmpty()) "" else "\n\nThe map shows with it.") },
        confirmButton = {
            TextButton({
                review = false; busy = true
                scope.launch {
                    try { done = model.sendAlert(kind, title, message, instruction, severity, countywide, hours, AlertArea.pinsGeoJSON(pins, radius)) } catch (e: Exception) { err = e.message }
                    busy = false
                }
            }) { Text(if (countywide) "Save for a second person" else "Send to ${model.workspace?.name ?: "your city"}", color = Brand.salmon) }
        },
        dismissButton = { TextButton({ review = false }) { Text("Keep editing") } },
    )
}

@Composable
fun NoticesScreen(model: StaffModel, onOpen: (StaffPost?) -> Unit) {
    Screen {
        if (model.can("publisher")) PrimaryButton("Post a notice", icon = Icons.Filled.Add) { onOpen(null) }
        val mine = model.notices?.posts.orEmpty()
        Column {
            Eyebrow("Posted here")
            if (mine.isEmpty()) Card { Text("Nothing posted from here yet.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            else Divided(mine.size) { i -> NoticeRow(mine[i], if (model.can("publisher")) ({ onOpen(mine[i]) }) else null) }
            Text("These show on BayCounty.me as soon as you post them.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
        }
        val read = model.notices?.fromRecords.orEmpty()
        if (read.isNotEmpty()) Column {
            Eyebrow("From your notice website")
            Divided(read.size) { i -> NoticeRow(read[i], null) }
            Text("Read from public records, so they can't be changed here. Flag one if it's wrong.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
        }
    }
}

@Composable
private fun NoticeRow(p: StaffPost, onClick: (() -> Unit)?) {
    RowLink(onClick, {
        Text(p.title, style = T.bodyBold, color = Brand.text)
        Text(listOfNotNull(p.kindLabel, p.eventDate?.let { "on " + Staff.whenOf(it) }, p.published?.let { "posted " + Staff.whenOf(it) }).joinToString(" · "),
            style = T.caption, color = Brand.secondary)
    })
}

@Composable
fun NoticeEditor(model: StaffModel, post: StaffPost?, demoFill: Boolean, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val fill = demoFill && post == null && model.demo != null
    var kind by remember { mutableStateOf(post?.kind ?: if (fill) "hearing" else "meeting") }
    var title by remember { mutableStateOf(post?.title ?: if (fill) "Public hearing on the 2027 budget" else "") }
    var text by remember { mutableStateOf(post?.text ?: if (fill) "The City Commission will hold a public hearing on the proposed 2027 budget at City Hall, 825 Ohio Ave, at 5:30 pm." else "") }
    var date by remember { mutableStateOf(post?.eventDate ?: if (fill) "2026-11-12" else "") }
    var busy by remember { mutableStateOf(false) }
    var sure by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    fun run(f: suspend () -> String?) { busy = true; scope.launch { err = f(); busy = false; if (err == null) onBack() } }
    Sub(if (post == null) "Post a notice" else "Edit notice", onBack) {
        Card { Picker("Kind", kind, Staff.noticeOrder.map { it to (model.noticeKinds[it] ?: it) }) { kind = it } }
        OutlinedTextField(title, { title = it }, Modifier.fillMaxWidth(), label = { Text("Title") }, maxLines = 3)
        OutlinedTextField(date, { date = it.filter { c -> c.isDigit() || c == '-' }.take(10) }, Modifier.fillMaxWidth(), label = { Text("Date, if it has one (YYYY-MM-DD)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done))
        OutlinedTextField(text, { text = it }, Modifier.fillMaxWidth(), label = { Text("Notice text") }, minLines = 6)
        Text(if (post?.geometry != null) "This notice has a map. To change the map, use the workspace on the web." else "To add a map (a pin, a street or an area), use the workspace on the web.",
            style = T.footnote, color = Brand.secondary)
        PrimaryButton(if (busy) "Saving…" else if (post == null) "Post notice" else "Save changes", enabled = !busy && title.isNotBlank() && text.isNotBlank()) {
            run { model.saveNotice(post?.id, kind, title, text, date.takeIf { it.length == 10 }) }
        }
        if (post != null) QuietButton(if (sure) "Withdraw: are you sure?" else "Withdraw this notice", color = Brand.salmon, enabled = !busy) {
            if (sure) run { model.withdraw(post) } else sure = true
        }
        ErrorLine(err)
    }
}

@Composable
fun FlagsScreen(model: StaffModel, answering: Boolean, onOpen: (StaffFlag) -> Unit) {
    var filter by remember { mutableStateOf("open") }
    val shown = if (filter == "all") model.flags else model.flags.filter { it.status == filter }
    Screen {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("open" to "Open", "fixed" to "Fixed", "all" to "All").forEach { (k, v) -> FilterChip(filter == k, { filter = k }, { Text(v) }) }
        }
        if (shown.isEmpty()) Card { Text(if (filter == "open") "No open flags." else "No flags.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
        else Divided(shown.size) { i ->
            val f = shown[i]
            RowLink({ onOpen(f) }, {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Chip(f.statusLabel, flagColor(f))
                    if (answering && f.govName != null) { Spacer(Modifier.width(6.dp)); Text(f.govName!!, style = T.caption, color = Brand.secondary) }
                }
                Spacer(Modifier.height(4.dp))
                Text(f.subject, style = T.bodyBold, color = Brand.text)
                val line = if (f.shownValue != null && f.correctValue != null) "Shows ${f.shownValue}, should be ${f.correctValue}" else f.note
                line?.let { Text(it, style = T.subhead, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis) }
            })
        }
        Text(if (answering) "Flags from every government. Check each one against its source, then answer."
             else "Numbers from public records can't be changed here. Flag what's wrong on the web workspace's Records tab; we check it against the source and answer here.",
            style = T.footnote, color = Brand.secondary)
    }
}

@Composable
fun FlagDetail(model: StaffModel, f: StaffFlag, answering: Boolean, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val uri = LocalUriHandler.current
    var reply by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var err by remember { mutableStateOf<String?>(null) }
    fun answer(status: String) { busy = true; scope.launch { err = model.answer(f, status, reply); busy = false; if (err == null) onBack() } }
    Sub("Flag", onBack) {
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Chip(f.statusLabel, flagColor(f))
                Text(f.subject, style = androidx.compose.material3.MaterialTheme.typography.titleLarge, color = Brand.text)
            }
            f.govName?.let { Detail("Government", it) }
            Detail("From", f.email)
            Detail("Sent", Staff.whenOf(f.createdAt))
            f.shownValue?.let { Detail("Site shows", it) }
            f.correctValue?.let { Detail("Should be", it) }
            f.evidenceUrl?.let { u -> Text("Where it comes from", style = T.bodyBold, color = Brand.navy, modifier = Modifier.clickable { uri.openUri(u) }.padding(14.dp)) }
            f.note?.let { Text(it, style = T.subhead, color = Brand.text, modifier = Modifier.padding(14.dp)) }
        }
        f.reply?.let { Column { Eyebrow("Our answer"); Card { Text(it, style = T.body, color = Brand.text, modifier = Modifier.padding(14.dp)) } } }
        if (answering && f.status == "open") Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Eyebrow("Answer")
            OutlinedTextField(reply, { reply = it }, Modifier.fillMaxWidth(), label = { Text("Reply to the staff member (optional)") }, minLines = 2)
            PrimaryButton("Fixed on the site", color = Brand.good, enabled = !busy) { answer("fixed") }
            QuietButton("Checked, not changed", enabled = !busy) { answer("not_changed") }
            Text("Check the value against the source first. A fix to record data is made in the data pipeline, not here.", style = T.footnote, color = Brand.secondary)
            ErrorLine(err)
        }
    }
}

@Composable
fun MoreScreen(model: StaffModel, onRecords: () -> Unit = {}) {
    val scope = rememberCoroutineScope()
    val uri = LocalUriHandler.current
    Screen {
        if (model.isOwner || model.can("submit")) Column {
            Card { RowLink(onRecords, { Text("Send records", style = T.bodyBold, color = Brand.text) }) }
            Text("Send your check register, budget report or contract list straight from your accounting system.",
                style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(top = 8.dp))
        }
        Column {
            Eyebrow("Signed in")
            Card {
                Detail("Email", model.me?.email ?: "")
                Detail("Access", if (model.isOwner) "Site owner (every government)" else model.workspace?.let { "${it.roleLabel}, ${it.name}" } ?: "")
            }
        }
        Column {
            Eyebrow("Safety")
            Card {
                listOf("Fingerprint, face or screen lock after 5 minutes away", "Countywide alerts need a second person to confirm", "Every action is logged for your workspace owner")
                    .forEach { Text(it, style = T.subhead, color = Brand.text, modifier = Modifier.padding(horizontal = 14.dp, vertical = 11.dp)) }
            }
        }
        Card {
            RowLink({ uri.openUri("https://baycounty.me/staff") }, { Text("Open the full workspace on the web", style = T.body, color = Brand.navy) })
            RowLink({ uri.openUri("mailto:hello@baycounty.me") }, { Text("Get help", style = T.body, color = Brand.navy) })
        }
        QuietButton("Sign out", color = Brand.salmon) { scope.launch { model.signOut() } }
        Text("BayCounty.me Staff ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}). Made by Flux Labs.", style = T.footnote, color = Brand.secondary)
    }
}
