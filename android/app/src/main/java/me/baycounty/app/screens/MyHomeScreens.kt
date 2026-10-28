package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import me.baycounty.app.Account
import me.baycounty.app.Push
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.AccountMe
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.NearbyFeed
import java.time.LocalTime

/** My home (/account): sign in with an emailed code, save a home address, then see what's happening near it. Reads
 *  /api/account, the same answers the website's My home page shows. Same sections as the iOS MyHomeView. */
@Composable
fun MyHomeScreen() {
    val context = LocalContext.current
    val nav = LocalNav.current
    LaunchedEffect(Unit) { Account.load(context); if (Account.me == null) Account.refresh(context) }
    val me = Account.me
    Screen(
        "My home",
        actions = { if (Account.signedIn && me != null) ToolbarIcon("gearshape", "Settings") { nav.push(Route.AccountSettings) } },
        onRefresh = { Account.refresh(context) },
        spacing = 20,
    ) {
        val home = me?.home
        when {
            !Account.signedIn -> item { SignInCard() }
            me != null && home != null -> {
                item { HomeHeader(me, home) }
                val f = Account.feed
                if (f != null) feedContent(f) else if (Account.error == null) item { Loading() }
            }
            me != null -> {
                item {
                    PageHero("My home", "Where do you live?",
                        "Save your address to see meetings, events, road work, alerts and trash day for your street.", symbol = "house", tone = Tone.BLUE)
                }
                item { HomeSearch() }
            }
            else -> item { Loading() }
        }
        Account.error?.let { e -> if (Account.signedIn) item { Text(e, style = T.footnote, color = Brand.salmon) } }
    }
}

@Composable
private fun HomeHeader(me: AccountMe, home: AccountMe.Home) {
    val h = LocalTime.now().hour
    val part = if (h < 12) "Good morning" else if (h < 17) "Good afternoon" else "Good evening"
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        PageHero(listOfNotNull(part, me.user.firstName?.ifBlank { null }).joinToString(", "), home.address, home.subtitle.ifEmpty { null },
            badge = { ToneIcon("house.fill", Tone.BLUE, 48.dp) })
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            home.city?.let { HomeChip(it) }
            home.zone?.let { HomeChip("Evacuation zone $it") }
        }
    }
}

@Composable
private fun HomeChip(text: String) {
    Text(text, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy,
        modifier = Modifier.background(Brand.sunken, CircleShape).padding(horizontal = 10.dp, vertical = 5.dp))
}

@Composable
private fun PrimaryButton(text: String, enabled: Boolean, onClick: () -> Unit) {
    Button(onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp), shape = RoundedCornerShape(12.dp),
        colors = ButtonDefaults.buttonColors(containerColor = Brand.navyFill)) { Text(text, style = T.subheadBold) }
}

@Composable
private fun field() = OutlinedTextFieldDefaults.colors(focusedContainerColor = Brand.surface, unfocusedContainerColor = Brand.surface,
    focusedBorderColor = Brand.navy, unfocusedBorderColor = Brand.hairline, focusedTextColor = Brand.text, unfocusedTextColor = Brand.text)

// Sign in

/** Email, then the 6-digit code from the email. No password. */
@Composable
private fun SignInCard() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var email by rememberSaveable { mutableStateOf("") }
    var code by rememberSaveable { mutableStateOf("") }
    var sent by rememberSaveable { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    fun send() = scope.launch { busy = true; if (Account.start(email.trim())) sent = true; busy = false }
    fun verify() = scope.launch { if (busy) return@launch; busy = true; if (!Account.verify(context, email.trim(), code)) code = ""; busy = false }

    Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
        PageHero("My home", "Your corner of Bay County",
            "Sign in to save your home and see what's happening around it: meetings, events, road work, alerts and your trash day.", symbol = "house", tone = Tone.BLUE)
        Column(Modifier.fillMaxWidth().card(16.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (!sent) {
                Text("Sign in or create an account", style = T.headline, color = Brand.text)
                OutlinedTextField(email, { email = it }, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(12.dp), colors = field(),
                    placeholder = { Text("you@example.com", style = T.body) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { send() }))
                PrimaryButton(if (busy) "Sending…" else "Email me a code", !busy && "@" in email) { send() }
                Text("We'll email you a 6-digit code. No password to remember.", style = T.footnote, color = Brand.secondary)
            } else {
                Text("Check your email", style = T.headline, color = Brand.text)
                Text("We sent a 6-digit code to $email. It works for 15 minutes.", style = T.subhead, color = Brand.secondary)
                OutlinedTextField(code, { v -> code = v.filter { it.isDigit() }.take(6); if (code.length == 6) verify() }, Modifier.fillMaxWidth(),
                    singleLine = true, shape = RoundedCornerShape(12.dp), colors = field(), textStyle = T.number,
                    placeholder = { Text("123456", style = T.number) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword, imeAction = ImeAction.Done))
                PrimaryButton(if (busy) "Checking…" else "Sign in", !busy && code.length == 6) { verify() }
                TextButton({ sent = false; code = ""; Account.error = null }) { Text("Use a different email", color = Brand.navy) }
            }
            Account.error?.let { Text(it, style = T.footnote, color = Brand.salmon) }
        }
        PageSection("What you get", "sparkles", Tone.TEAL) {
            CardList {
                RowLabel("Near my home", "Meetings, events, road work and notices within the distance you pick", "mappin.and.ellipse", chevron = false)
                RowDivider(50.dp)
                RowLabel("Your trash day and evacuation zone", "Pickup days and the zone for your street", "trash", chevron = false)
                RowDivider(50.dp)
                RowLabel("A Monday email", "Your week near home, if you want it", "envelope", chevron = false)
                RowDivider(50.dp)
                RowLabel("Alerts for your street", "Evacuation orders for your zone and boil-water notices for your city", "bell", chevron = false)
            }
        }
        Text("Your email and home address are kept private and never shown on the site. Delete your account any time in Settings.",
            style = T.footnote, color = Brand.secondary)
    }
}

// Home search

/** Finds a Bay County address on the county's map server and saves it as the account's home. */
@Composable
private fun HomeSearch(onSaved: () -> Unit = {}) {
    val store = LocalStore.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var query by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<AddressMatch>>(emptyList()) }
    var message by remember { mutableStateOf<String?>(null) }
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
    fun save(m: AddressMatch) = scope.launch {
        Account.saveHome(context, m)
        if (Account.me?.home != null) { query = ""; results = emptyList(); onSaved() }
    }
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        FilterField(query, "e.g. 825 Ohio Ave") { query = it }
        message?.let { Text(it, style = T.footnote, color = Brand.secondary) }
        if (results.isNotEmpty()) CardList {
            results.forEachIndexed { i, m ->
                Box(Modifier.clickable(role = Role.Button) { save(m) }) { RowLabel(m.display, m.subtitle.ifEmpty { null }, "house") }
                if (i < results.lastIndex) RowDivider(50.dp)
            }
        }
        val saved = store.home
        if (saved != null && query.isEmpty() && results.isEmpty()) CardList {
            Box(Modifier.clickable(role = Role.Button) { save(saved) }) { RowLabel("Use ${saved.display}", "The address saved on this phone", "location") }
        }
    }
}

// Feed

private val SECTION_SYMBOL = mapOf("alerts" to "exclamationmark.triangle", "meetings" to "person.3", "events" to "calendar", "projects" to "hammer",
    "notices" to "doc.plaintext", "food" to "fork.knife", "business" to "storefront")
private val SECTION_TONE = mapOf("alerts" to Tone.SALMON, "meetings" to Tone.BLUE, "events" to Tone.TEAL, "projects" to Tone.AMBER,
    "notices" to Tone.BLUE, "food" to Tone.TEAL, "business" to Tone.AMBER)

/** Today tiles, then one card per section, then the home's governments. */
private fun androidx.compose.foundation.lazy.LazyListScope.feedContent(f: NearbyFeed) {
    item {
        val c = f.todayCard
        val trash = c.trash.orEmpty()
        data class Tile(val title: String, val value: String, val caption: String?, val symbol: String, val tone: Tone)
        val tiles = listOf(
            Tile("Alerts", if (c.alerts == 0) "None" else "${c.alerts}", if (c.alerts == 0) "Nothing for your street right now" else "For your street",
                "bell", if (c.alerts == 0) Tone.TEAL else Tone.SALMON),
            Tile("Pickup", trash.firstOrNull()?.days ?: "—", trash.drop(1).firstOrNull()?.let { "${it.service}: ${it.days}" } ?: trash.firstOrNull()?.service ?: "No pickup days found",
                "trash", Tone.TEAL),
            Tile("Evacuation zone", f.zone ?: "None", f.zone?.let { "Leave when zone $it is called" } ?: "Not in a zone", "wind", Tone.AMBER),
            c.beach?.let { b -> Tile("Beach flag", b.flag.replaceFirstChar { it.uppercase() }, b.ripCurrentRisk?.let { "Rip current risk: $it" }, "flag", Tone.BLUE) }
                ?: Tile("Your government", f.city ?: "Bay County", if (f.city == null) "Unincorporated Bay County" else f.localGovernment, "building.columns", Tone.BLUE),
        )
        Grid2(tiles) { t, m -> KPICard(t.title, t.value, m, t.caption, t.symbol, t.tone) }
    }
    f.sections.filter { it.items.isNotEmpty() || it.id == "alerts" }.forEach { s ->
        item(key = "sec-${s.id}") {
            PageSection(s.title, SECTION_SYMBOL[s.id], SECTION_TONE[s.id] ?: Tone.BLUE) {
                if (s.items.isEmpty()) {
                    Text(s.empty, style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(16.dp).padding(14.dp))
                } else CardList {
                    val shown = s.items.take(6)
                    shown.forEachIndexed { i, item ->
                        FeedRow(item)
                        if (i < shown.lastIndex) RowDivider(70.dp)
                    }
                }
            }
        }
    }
    item {
        PageSection("Your governments", "building.columns", Tone.BLUE) {
            CardList {
                f.governments.forEach { g ->
                    RouteRow(Route.Gov(g.govId), g.name, symbol = "building.columns")
                    RowDivider(50.dp)
                }
                RouteRow(Route.MyAddress, "Full address report", "Taxes, flood zone, schools and who represents you", "doc.text.magnifyingglass")
            }
        }
    }
    f.note?.let { item { Text(it, style = T.footnote, color = Brand.secondary) } }
}

/** One item: a date or distance tile, its title and a two-line detail, and a tag. */
@Composable
private fun FeedRow(item: NearbyFeed.Item) {
    val o = rememberOpener()
    val link = item.link
    val w = NearbyFeed.whenOf(item.date)
    Row(
        Modifier.fillMaxWidth().then(if (link != null) Modifier.clickable(role = Role.Button) { o.open(link) } else Modifier)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(Modifier.size(44.dp, 46.dp).background(Brand.sunken, RoundedCornerShape(10.dp)), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center) {
            val mi = item.miles
            when {
                item.leadsWithDistance && mi != null -> {
                    Text(if (mi < 0.1) "<0.1" else "%.1f".format(java.util.Locale.US, mi), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                    Text("MI", style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Brand.secondary)
                }
                w != null -> {
                    Text(w.month, style = T.caption2.copy(fontWeight = FontWeight.Bold), color = Brand.salmon)
                    Text(w.day, style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                }
                else -> Icon(icon("mappin"), null, tint = Brand.navy, modifier = Modifier.size(20.dp))
            }
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            item.tag?.let { tag ->
                Text(tag.uppercase(), style = T.caption2.copy(fontWeight = FontWeight.Bold),
                    color = if (item.level == "closed" || item.kind == "evacuation") Brand.salmon else Brand.navy)
            }
            Text(item.title, style = T.subheadBold, color = Brand.text, maxLines = 2, overflow = TextOverflow.Ellipsis)
            val time = w?.time
            if (!item.leadsWithDistance && item.allDay != true && time != null) {
                Text(time, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy)
            }
            item.detail?.takeIf { it.isNotEmpty() }?.let { Text(it, style = T.footnote, color = Brand.secondary, maxLines = 2, overflow = TextOverflow.Ellipsis) }
        }
        if (link != null) Box(Modifier.padding(top = 4.dp)) { Chevron() }
    }
}

// Settings

/** Name, home, distance, emails, topics and phone alerts; sign out and delete the account. */
@Composable
fun AccountSettingsScreen() {
    val context = LocalContext.current
    val nav = LocalNav.current
    val scope = rememberCoroutineScope()
    val me = Account.me
    var prefs by remember(me) { mutableStateOf(me?.prefs) }
    var name by remember(me) { mutableStateOf(me?.user?.firstName ?: "") }
    var changingHome by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    val c = me?.choices
    fun toggle(list: List<String>, k: String, on: Boolean) = if (on) (list + k).distinct() else list - k

    Screen("Settings", actions = {
        TextButton({
            scope.launch {
                if (name != (me?.user?.firstName ?: "")) Account.saveFirstName(context, name)
                prefs?.let { p -> if (p != me?.prefs) Account.save(context, p) }
                if (Account.error == null) nav.pop()
            }
        }) { Text("Save", style = T.subheadBold, color = Brand.navy) }
    }, spacing = 22) {
        if (me != null) {
            item {
                PageSection("You", "person", Tone.BLUE) {
                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        CardList { FactRow("Email", me.user.email) }
                        OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(12.dp), colors = field(),
                            label = { Text("First name") })
                    }
                }
            }
            item {
                PageSection("Home", "house", Tone.BLUE, "Kept private. Used only to pick what's near you.") {
                    val h = me.home
                    if (h != null && !changingHome) CardList {
                        FactRow(h.address, h.subtitle)
                        RowDivider()
                        Box(Modifier.clickable(role = Role.Button) { changingHome = true }) { RowLabel("Change address") }
                        RowDivider()
                        Box(Modifier.clickable(role = Role.Button) { scope.launch { Account.removeHome(context) } }) {
                            Text("Remove home", style = T.body, color = Brand.salmon, modifier = Modifier.fillMaxWidth().padding(14.dp))
                        }
                    } else HomeSearch { changingHome = false }
                }
            }
        }
        val p = prefs
        if (p != null && c != null) {
            item {
                PageSection("Near my home", "mappin.and.ellipse", Tone.TEAL) {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        FieldMenu("Distance", AccountMe.radiusLabel(p.radiusMi), AccountMe.radii.map { it to AccountMe.radiusLabel(it) }, Modifier.fillMaxWidth(), p.radiusMi) {
                            prefs = p.copy(radiusMi = it)
                        }
                        AccountMe.topicOrder.filter { c.topics[it] != null }.forEach { k ->
                            ToggleRow(c.topics.getValue(k), k in p.topics) { on -> prefs = p.copy(topics = toggle(p.topics, k, on)) }
                        }
                    }
                }
            }
            item {
                PageSection("Email", "envelope", Tone.AMBER, "Emergency emails go out only when a notice reaches your home.") {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        ToggleRow("Monday email: your week near home", p.weeklyEmail) { prefs = p.copy(weeklyEmail = it) }
                        AccountMe.alertEmailOrder.filter { c.alertEmail[it] != null }.forEach { k ->
                            ToggleRow(c.alertEmail.getValue(k), k in p.alertEmail) { on -> prefs = p.copy(alertEmail = toggle(p.alertEmail, k, on)) }
                        }
                    }
                }
            }
            item {
                PageSection("Phone alerts", "bell", Tone.SALMON,
                    if (Push.enabled) "These follow your home on every phone you're signed in on." else "Turn on alerts under Emergencies to get these on this phone.") {
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        AccountMe.pushOrder.filter { c.pushTopics[it] != null }.forEach { k ->
                            ToggleRow(c.pushTopics.getValue(k), k in p.pushTopics) { on -> prefs = p.copy(pushTopics = toggle(p.pushTopics, k, on)) }
                        }
                    }
                }
            }
        }
        item {
            CardList {
                Box(Modifier.clickable(role = Role.Button) { scope.launch { Account.signOut(context); nav.pop() } }) { RowLabel("Sign out", symbol = "person.crop.circle") }
                RowDivider()
                Box(Modifier.clickable(role = Role.Button) { confirmDelete = true }) {
                    Text("Delete account", style = T.body, color = Brand.salmon, modifier = Modifier.fillMaxWidth().padding(14.dp))
                }
            }
        }
        item { Text("Deleting removes your email, home and choices for good.", style = T.footnote, color = Brand.secondary) }
        Account.error?.let { e -> item { Text(e, style = T.footnote, color = Brand.salmon) } }
    }
    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Delete your account?") },
        text = { Text("Your email, home and choices are removed. This can't be undone.") },
        confirmButton = { TextButton({ confirmDelete = false; scope.launch { Account.deleteAccount(context); nav.pop(); nav.pop() } }) { Text("Delete account", color = Brand.salmon) } },
        dismissButton = { TextButton({ confirmDelete = false }) { Text("Cancel") } },
    )
}
