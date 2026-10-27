package me.baycounty.app.screens

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.Looper
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.AddressMatch
import me.baycounty.kit.AddressModel
import me.baycounty.kit.AddressParser
import me.baycounty.kit.AddressReport
import me.baycounty.kit.FloodText
import me.baycounty.kit.Format
import me.baycounty.kit.GISClient
import me.baycounty.kit.GeoPoint
import me.baycounty.kit.Governments
import me.baycounty.kit.NearbyMoney
import java.net.URLEncoder
import kotlin.coroutines.resume

/** Text with **bold** parts, as the iOS app writes them in Markdown. */
private fun md(s: String): AnnotatedString = buildAnnotatedString {
    s.split("**").forEachIndexed { i, part -> if (i % 2 == 1) withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(part) } else append(part) }
}

/** One fix of where the phone is, or null when it can't get one in 15 seconds. */
@SuppressLint("MissingPermission")
private suspend fun currentLocation(context: Context): Location? = withTimeoutOrNull(15_000) {
    val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    val provider = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER).firstOrNull { runCatching { lm.isProviderEnabled(it) }.getOrDefault(false) }
        ?: return@withTimeoutOrNull null
    suspendCancellableCoroutine { cont ->
        if (Build.VERSION.SDK_INT >= 30) {
            lm.getCurrentLocation(provider, null, context.mainExecutor) { if (cont.isActive) cont.resume(it) }
        } else {
            val l = object : LocationListener {
                override fun onLocationChanged(loc: Location) { if (cont.isActive) cont.resume(loc) }
                @Deprecated("old API") override fun onStatusChanged(p: String?, s: Int, b: android.os.Bundle?) {}
                override fun onProviderDisabled(p: String) { if (cont.isActive) cont.resume(null) }
            }
            @Suppress("DEPRECATION") lm.requestSingleUpdate(provider, l, Looper.getMainLooper())
            cont.invokeOnCancellation { lm.removeUpdates(l) }
        }
    }
}

/** Finds a Bay County address: type it, or use where you are. */
@Composable
fun MyAddressScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var query by rememberSaveable { mutableStateOf("") }
    var results by remember { mutableStateOf<List<AddressMatch>>(emptyList()) }
    var relaxed by remember { mutableStateOf(false) }
    var searching by remember { mutableStateOf(false) }
    var locating by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }

    suspend fun findNearby() {
        locating = true
        try {
            val loc = currentLocation(context)
            if (loc == null) { message = "Couldn't find your location. Try typing the address."; return }
            val near = store.gis.addressesNear(GeoPoint(loc.longitude, loc.latitude))
            results = near; relaxed = false
            message = if (near.isEmpty()) "No Bay County address found within 150 feet of where you are. Try typing it." else null
        } catch (e: Exception) {
            message = "Bay County's map server didn't answer. Try again in a moment."
        } finally { locating = false }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { granted ->
        if (granted.values.any { it }) scope.launch { findNearby() }
        else message = "Location is off for BayCounty.me. You can turn it on in Settings, or type the address."
    }

    LaunchedEffect(query) {
        val q = query.trim()
        if (q.length < 3) { results = emptyList(); message = null; return@LaunchedEffect }
        delay(300)
        if (AddressParser.parse(q)?.tokens?.isNotEmpty() != true) {
            results = emptyList(); message = "Start with the house number, then the street (for example \"1614 Ohio\")."
            return@LaunchedEffect
        }
        searching = true
        try {
            val r = store.gis.search(q)
            results = r.matches; relaxed = r.relaxed
            message = if (r.matches.isEmpty()) "No matching address. Check the house number, or try just the number and street name (for example \"1614 Ohio\")." else null
        } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) {
            message = "Bay County's map server didn't answer. Try again in a moment."
        } finally { searching = false }
    }

    Screen("My Address", spacing = 18) {
        item { FilterField(query, "e.g. 825 Ohio Ave") { query = it } }
        item {
            FormSection(null, "Lookups go straight to Bay County's public map server. BayCounty.me doesn't store what you search, and your location is only used once, to find the nearest address.") {
                CardList {
                    Text(
                        "Type a Bay County street address to see your property tax estimate, who represents you, your schools, your flood and evacuation zones, and whether you're inside a redevelopment district.",
                        style = T.subhead, color = Brand.text, modifier = Modifier.padding(14.dp),
                    )
                    RowDivider()
                    Row(
                        Modifier.fillMaxWidth().heightIn(min = 50.dp).clickable(enabled = !locating, role = Role.Button) {
                            val ok = listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
                                .any { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }
                            if (ok) scope.launch { findNearby() }
                            else permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                        }.padding(horizontal = 14.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Icon(icon("location"), null, tint = Brand.navy, modifier = Modifier.size(22.dp))
                        Text(if (locating) "Finding you…" else "Use my location", style = T.body, color = Brand.navy)
                    }
                }
            }
        }
        message?.let { item { Text(it, style = T.subhead, color = Brand.secondary, modifier = Modifier.fillMaxWidth().card(14.dp).padding(14.dp)) } }
        if (searching && results.isEmpty()) item { Loading() }
        if (results.isNotEmpty()) item {
            FormSection(if (relaxed) "Closest matches" else "Addresses") {
                CardList {
                    results.forEachIndexed { i, m ->
                        RouteRow(Route.Address(m), m.display, m.subtitle.ifEmpty { null })
                        if (i < results.lastIndex) RowDivider()
                    }
                }
            }
        }
        val home = store.home
        if (home != null && query.isEmpty() && results.isEmpty()) item {
            FormSection("Saved") { CardList { RouteRow(Route.Address(home), home.display, symbol = "house.fill") } }
        }
    }
}

/** Everything that applies to one address (the website's My Address results). */
@Composable
fun AddressReportScreen(match: AddressMatch) {
    val store = LocalStore.current
    var report by remember(match.id) { mutableStateOf<AddressReport?>(null) }
    var nearby by remember(match.id) { mutableStateOf<NearbyMoney?>(null) }
    var nearbyFailed by remember(match.id) { mutableStateOf(false) }
    suspend fun load(force: Boolean = false) {
        store.loadAddressModel()
        val m = store.addressModel ?: return
        if (report == null || force) report = AddressReport.load(match, store.gis, store.client, m)
        if (nearby == null) try { nearby = NearbyMoney.load(match.point, store.client) } catch (e: kotlinx.coroutines.CancellationException) { throw e } catch (e: Exception) { nearbyFailed = true }
    }
    LaunchedEffect(match.id) { load(); store.loadPeople() }
    val r = report
    val m = store.addressModel
    Screen("My Address", onRefresh = { load(force = true) }, spacing = 22) {
        item {
            Column(Modifier.fillMaxWidth().card(16.dp).padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(match.display, style = T.title3, color = Brand.text)
                    val sub = if (r == null) match.subtitle + " · Loading…" else listOfNotNull(
                        r.cityName?.let { "City of $it" } ?: "Unincorporated Bay County", match.zip?.let { "ZIP $it" }, r.parcel?.s("A1RENUM")?.let { "Parcel $it" },
                    ).joinToString(" · ")
                    Text(sub, style = T.subhead, color = Brand.secondary)
                }
                val saved = store.home == match
                Row(
                    Modifier.clickable(role = Role.Button) { store.saveHome(if (saved) null else match) }.padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(icon(if (saved) "house.slash" else "house"), null, tint = if (saved) Brand.salmon else Brand.navy, modifier = Modifier.size(20.dp))
                    Text(if (saved) "Remove as my home" else "Save as my home", style = T.subheadBold, color = if (saved) Brand.salmon else Brand.navy)
                }
            }
        }
        if (r != null && m != null) {
            item { TaxSection(r, m) }
            r.parcel?.let { p -> item { PropertySection(r, m, p) } }
            if (r.parcel != null && r.taxEstimate(m) != null) item { AmendmentSection(r, m) }
            item { RepsSection(r, m) }
            item {
                FormSection("Zoned public schools", "Attendance zones from Bay District Schools via county GIS. Choice and magnet options differ.") {
                    CardList {
                        FactRow("Elementary", r.elementary ?: "—"); RowDivider()
                        FactRow("Middle", r.middle ?: "—"); RowDivider()
                        FactRow("High", r.high ?: "—")
                    }
                }
            }
            item { CRASection(r, m) }
            item { AddressUtilitiesSection(match) }
            item { SafetySection(r, match) }
            r.development?.let { d -> item { DevelopmentSection(d) } }
            item { NearbySection(nearby, nearbyFailed) }
            item {
                FormSection("Your government's records") {
                    val keys = setOf(r.govKey, "county", "schools").sortedBy { Governments.order.indexOf(it).let { i -> if (i < 0) 9 else i } }
                    CardList {
                        keys.forEachIndexed { i, k -> RouteRow(Route.Gov(k), Governments.names[k] ?: k, symbol = "building.columns"); if (i < keys.lastIndex) RowDivider(50.dp) }
                    }
                }
            }
            item {
                FormSection(null, "Owner names are not shown here. They're public at the Property Appraiser's site. Representative names come from Bay County's GIS and may lag an election.") {
                    r.parcel?.s("PLINK")?.let { CardList { WebRow("Property Appraiser record", it, symbol = "doc.text.magnifyingglass") } }
                }
            }
        } else if (m == null && store.appError("address.json") != null) {
            item { AppDataPending("address.json", "Couldn't load the address report") { load() } }
        } else {
            item {
                Row(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(Modifier.size(20.dp), color = Brand.navy, strokeWidth = 2.dp)
                    Text("Looking up this address…", style = T.subhead, color = Brand.secondary)
                }
            }
        }
    }
}

@Composable
private fun TaxSection(r: AddressReport, m: AddressModel) {
    FormSection("Property tax estimate", "Property tax: 2026 values × ${m.fy} rates. Fees: the FY2026 tax roll. Your official bill comes from the Tax Collector.") {
        val e = r.taxEstimate(m)
        CardList {
            if (e != null) {
                val groups = e.byGroup(m.groups.mapNotNull { it.firstOrNull() })
                val gname = { g: String -> if (g == "city") e.cityName ?: "City" else m.groups.firstOrNull { it.firstOrNull() == g }?.lastOrNull() ?: g }
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(Format.money(e.total), style = T.bigNumber, color = Brand.text)
                        Text("/ year", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(bottom = 4.dp))
                    }
                    Text("${e.districtLabel} · ${Format.number(e.mills)} mills${if (e.exact) "" else " (area inferred from the map)"}", style = T.caption, color = Brand.secondary)
                    StackBar(groups.map { Triple(gname(it.group), it.amount, taxColor(it.group)) })
                    for (g in groups) LegendRow(taxColor(g.group), gname(g.group), Format.money(g.amount))
                }
                r.fees?.let { fees ->
                    RowDivider()
                    if (fees.isEmpty()) {
                        Text("No flat fees (non-ad valorem assessments) were on this parcel's FY2026 tax bill.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(14.dp))
                    } else {
                        for ((code, amount) in fees) { FactRow(m.navLabel[code] ?: "Other charge ($code)", Format.money(amount)); RowDivider() }
                        Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp)) {
                            Text("Estimated total bill", style = T.subheadBold, color = Brand.text, modifier = Modifier.weight(1f))
                            Text(Format.money(e.total + fees.sumOf { it.second }), style = T.subheadBold.copy(fontWeight = FontWeight.Bold), color = Brand.text)
                        }
                    }
                }
                RowDivider()
                RouteRow(Route.TaxCalculator(e.districtID, e.parts.assessed, e.parts.homestead), "Try what-if numbers in the calculator")
            } else {
                Text("No parcel record came back for this address, so there's no value to estimate from.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp))
                RowDivider()
                RouteRow(Route.TaxCalculator(), "Use the calculator")
            }
        }
    }
}

@Composable
private fun PropertySection(r: AddressReport, m: AddressModel, p: GISClient.Feature) {
    val store = LocalStore.current
    val t = AddressReport.taxParts(p, r.exemptions, m.second2026)
    FormSection("The property") {
        CardList {
            p.s("DORAPPDESC")?.let { FactRow("Use", AddressParser.titleCase(it)); RowDivider() }
            p.s("S1YRBLTACT")?.let { b -> FactRow("Built", b + (p.n("S1AREAHEAT")?.let { " · ${Format.number(Math.rint(it))} heated sq ft" } ?: "")); RowDivider() }
            FactRow("Market (just) value", Format.money(t.just)); RowDivider()
            FactRow("Assessed value", Format.money(t.assessed), if (t.assessed < t.just) "Capped ${Format.money(t.just - t.assessed)} below market." else null); RowDivider()
            if (t.exempt > 0) {
                FactRow("Exemptions", Format.money(t.exempt)); RowDivider()
                if (t.homesteadAmount > 0) { FactRow("    Homestead", Format.money(t.homesteadAmount)); RowDivider() }
                if (t.additionalHomestead > 0) { FactRow("    Additional homestead", Format.money(t.additionalHomestead)); RowDivider() }
                if (t.otherExemptions > 0) {
                    FactRow("    Other exemptions", Format.money(t.otherExemptions), "The kinds of other exemptions aren't shown, to protect owners' privacy."); RowDivider()
                }
            } else { FactRow("Exemptions", "None"); RowDivider() }
            FactRow("Taxable value", Format.money(t.otherTaxable), if (t.schoolTaxable != t.otherTaxable) "${Format.money(t.schoolTaxable)} for school taxes" else null)
            if (t.fullyExempt) { RowDivider(); Text("No property tax is owed on this home.", style = T.subheadBold, color = Brand.text, modifier = Modifier.padding(14.dp)) }
            if (!t.homestead && r.isResidential) {
                RowDivider()
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("No homestead exemption", style = T.subheadBold, color = Brand.text)
                    Text(
                        "This home has no homestead exemption on the 2026 tax roll. That's normal for a rental or a second home. If you own it and it was your permanent home on January 1, you can apply with the Bay County Property Appraiser. Applications are due March 1 for that year's taxes.",
                        style = T.footnote, color = Brand.text,
                    )
                }
            }
            RowDivider()
            Flow(16.dp) {
                for ((label, id) in listOf("Assessed value" to "assessed-value", "Taxable value" to "taxable-value", "Homestead" to "homestead")) {
                    Text(label, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable(role = Role.Button) { store.explain(id) }.padding(horizontal = 14.dp, vertical = 12.dp))
                }
            }
        }
    }
}

@Composable
private fun AmendmentSection(r: AddressReport, m: AddressModel) {
    val p = r.parcel ?: return
    val e = r.taxEstimate(m) ?: return
    val t = AddressReport.taxParts(p, r.exemptions, m.second2026)
    FormSection("If Amendment 3 passes") {
        CardList {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                val s = r.amendment3Savings(m)
                if (s != null) {
                    Text(
                        md("With the full \$250,000 homestead exemption on today's value and rates, this home's county, city and district taxes would drop by about **${Format.money(s.first)} a year**${if (s.second) ", to zero; it would still pay school tax" else ""}."),
                        style = T.subhead, color = Brand.text,
                    )
                    Text("Assumes rates stay the same and the owner was a Florida resident before 2027.", style = T.caption, color = Brand.secondary)
                } else {
                    Text(
                        md("This property has no homestead exemption, so Amendment 3 wouldn't lower its tax bill directly. It would limit how fast its taxed value can rise to **5% a year instead of 10%** for non-school taxes.${if (t.assessed < t.just) " Its value is already capped ${Format.money(t.just - t.assessed)} below market." else ""}"),
                        style = T.subhead, color = Brand.text,
                    )
                }
            }
            RowDivider()
            RouteRow(Route.Amendment3(e.districtID, t.assessed, t.homestead), "Try your own numbers")
        }
    }
}

@Composable
private fun RepLine(title: String, f: GISClient.Feature?, gov: String?, m: AddressModel) {
    val store = LocalStore.current
    val nav = LocalNav.current
    val o = rememberOpener()
    val name = f?.s("REPNAME")
    val member = if (name != null && gov != null) AddressReport.matchMember(name, gov, m) else null
    val person = name?.let { n -> store.people?.people?.firstOrNull { p -> p.name.equals(n, ignoreCase = true) || (member != null && p.name == member.name) } }
    Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(title, style = T.caption, color = Brand.secondary)
        if (person != null) {
            Row(Modifier.clickable(role = Role.Button) { nav.push(Route.Person(person.id)) }, verticalAlignment = Alignment.CenterVertically) {
                Text(name, style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.navy, modifier = Modifier.weight(1f))
                Chevron()
            }
        } else Text(name ?: "—", style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.text)
        val detail = listOfNotNull(f?.s("NAME"), member?.let { "${it.yes} yes · ${it.no} no in recorded money votes" })
        if (detail.isNotEmpty()) Text(detail.joinToString(" · "), style = T.caption, color = Brand.secondary)
        f?.s("DISTRICTURL")?.let { u -> Text("Website", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable { o.open(u) }.padding(vertical = 4.dp)) }
    }
}

@Composable
private fun RepsSection(r: AddressReport, m: AddressModel) {
    FormSection("Who represents you") {
        CardList {
            RepLine("County Commission", r.commission, "county", m); RowDivider()
            val city = r.cityName
            if (city != null) {
                if (r.cityCouncil != null) RepLine("City of $city", r.cityCouncil, r.govKey.takeIf { it != "county" }, m)
                else FactRow("City", "City of $city")
            } else {
                Text("No city (unincorporated). The County Commission is your local government.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(14.dp))
            }
            RowDivider()
            RepLine("School Board", r.schoolBoard, "schools", m); RowDivider()
            RepLine("Florida House", r.floridaHouse, null, m); RowDivider()
            RepLine("Florida Senate", r.floridaSenate, null, m); RowDivider()
            RepLine("U.S. House", r.usHouse, null, m); RowDivider()
            RouteRow(Route.Dataset("candidates-2026", mapOf("gov_id" to r.govKey)), "2026 races for your area")
        }
    }
}

@Composable
private fun CRASection(r: AddressReport, m: AddressModel) {
    val store = LocalStore.current
    FormSection("Redevelopment district (CRA)") {
        CardList {
            val c = r.cra
            val name = c?.s("CRA")
            if (!r.craChecked) {
                Text("Couldn't check right now.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp))
            } else if (c != null && name != null) {
                val agency = m.craAgency[name]
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        md("This address is inside the **$name** district${c.s("EST_YEAR")?.let { " (created $it)" } ?: ""}. The city and county taxes on growth in this area since then go to the ${agency ?: "CRA"}'s fund and must be spent inside its districts."),
                        style = T.subhead, color = Brand.text,
                    )
                    val s = agency?.let { m.cra[it] }
                    if (s != null) Text("$agency: ${Format.compactMoney(s.spent)} in documented spending and awards across ${s.n} records.", style = T.footnote, color = Brand.text)
                    Text("What's a CRA?", style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.navy, modifier = Modifier.clickable(role = Role.Button) { store.explain("cra") }.padding(vertical = 4.dp))
                }
                if (agency != null && m.cra[agency] != null) { RowDivider(); RouteRow(Route.Dataset("cra-payments", mapOf("cra" to agency)), "See what it pays for") }
            } else {
                Text(
                    md("This address is **not inside a CRA district**, so all of its city and county property tax goes to those governments' regular budgets."),
                    style = T.subhead, color = Brand.text, modifier = Modifier.padding(14.dp),
                )
                RowDivider()
                RouteRow(Route.CRA, "See Bay County's CRAs")
            }
        }
    }
}

@Composable
private fun NearestRow(title: String, x: Pair<GISClient.Feature, Double>?) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(title, style = T.subhead, color = Brand.text, modifier = Modifier.weight(1f))
        if (x != null) Column(horizontalAlignment = Alignment.End) {
            Text(x.first.s("NAME") ?: "—", style = T.subhead, color = Brand.text, textAlign = TextAlign.End)
            Text(String.format(java.util.Locale.US, "%.1f mi", x.second), style = T.caption, color = Brand.secondary)
        } else Text("None within 10 miles", style = T.subhead, color = Brand.secondary)
    }
}

@Composable
private fun SafetySection(r: AddressReport, match: AddressMatch) {
    val (headline, detail) = FloodText.describe(r.flood)
    val place = r.cityName?.let { "$it, FL" } ?: "Bay County, FL"
    val fema = "https://msc.fema.gov/portal/search?AddressQuery=" + URLEncoder.encode("${match.display}, $place", "UTF-8").replace("+", "%20")
    FormSection(
        "Flood, storms and services",
        "Flood zone is checked live against FEMA's National Flood Hazard Layer at the address point. A building's official zone comes from the flood map, your lender's flood determination or an elevation certificate.",
    ) {
        CardList {
            Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text("Flood zone", style = T.caption, color = Brand.secondary)
                Text(headline, style = T.body.copy(fontWeight = FontWeight.Medium), color = Brand.text)
                detail?.let { Text(it, style = T.caption, color = Brand.secondary) }
            }
            RowDivider()
            FactRow("Evacuation zone", r.evacuationZone?.let { "Zone $it" } ?: "Not in a mapped zone"); RowDivider()
            NearestRow("Nearest fire station", r.fireStation); RowDivider()
            NearestRow("Nearest library", r.library); RowDivider()
            NearestRow("Nearest park", r.park); RowDivider()
            r.mosquito?.s("DISTRICT")?.let { FactRow("Mosquito control", it); RowDivider() }
            r.touristTaxArea?.let { FactRow("Tourist tax area", it); RowDivider() }
            WebRow("Check this address on FEMA's map", fema, symbol = "map")
        }
    }
}

@Composable
private fun DevelopmentSection(d: AddressReport.Development) {
    FormSection(
        "Zoning and development nearby",
        "Projects and rezonings within half a mile, last 5 years, from Bay County, Panama City, Lynn Haven and Panama City Beach planning maps. Building permits aren't published as open data.",
    ) {
        CardList {
            if (d.failed) {
                Text("Bay County's planning maps didn't answer. Try again in a moment.", style = T.subhead, color = Brand.secondary, modifier = Modifier.padding(14.dp))
                return@CardList
            }
            FactRow("Zoning", d.zoning ?: "Not mapped"); RowDivider()
            FactRow("Future land use", d.futureLandUse ?: "Not mapped")
            if (d.projects.isEmpty()) { RowDivider(); Text("No development projects on file within half a mile in the last 5 years.", style = T.footnote, color = Brand.secondary, modifier = Modifier.padding(14.dp)) }
            for (p in d.projects) {
                RowDivider()
                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(p.name + (p.detail?.takeIf { it.isNotEmpty() }?.let { " · $it" } ?: ""), style = T.subheadBold, color = Brand.text)
                    Text(
                        listOfNotNull(p.status, p.`when`, p.address, p.miles?.let { String.format(java.util.Locale.US, "%.1f mi away", it) }, p.source).filter { it.isNotEmpty() }.joinToString(" · "),
                        style = T.caption, color = Brand.secondary,
                    )
                }
            }
            for (z in d.rezonings) {
                RowDivider()
                Column(Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text("Rezoning, ordinance ${z.ordinance}", style = T.subheadBold, color = Brand.text)
                    Text(z.changes.take(4).joinToString("; ") + (if (z.changes.size > 4) " and ${z.changes.size - 4} more" else ""), style = T.caption, color = Brand.text)
                }
            }
            for (c in d.conditionalUses) { RowDivider(); Text("Conditional use: $c", style = T.caption, color = Brand.text, modifier = Modifier.padding(14.dp)) }
        }
    }
}

@Composable
private fun NearbySection(n: NearbyMoney?, failed: Boolean) {
    FormSection(
        "Public money near you",
        "Distances are from the address point. CRA records placed only somewhere in a district, and rows left out of CRA totals, aren't shown; the dollar total counts spent and committed money.",
    ) {
        Column(Modifier.fillMaxWidth().card(14.dp).padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            when {
                n != null -> {
                    Text("CRA spending within half a mile", style = T.subheadBold, color = Brand.text)
                    if (n.cra.isEmpty()) Text("None on file nearby.", style = T.footnote, color = Brand.secondary)
                    else {
                        Text("${n.cra.size} records · ${Format.compactMoney(n.craTotal)} spent or committed", style = T.caption, color = Brand.secondary)
                        for (c in n.cra.take(5)) NearbyLine(
                            "${c.amount?.let { Format.money(it) } ?: "—"} · ${c.purpose}",
                            listOfNotNull(c.status, c.`when`, String.format(java.util.Locale.US, "%.1f mi", c.miles)).joinToString(" · "),
                        )
                    }
                    Text("Sales tax projects within a mile", style = T.subheadBold, color = Brand.text, modifier = Modifier.padding(top = 6.dp))
                    if (n.projects.isEmpty()) Text("None on file nearby.", style = T.footnote, color = Brand.secondary)
                    else {
                        Text("${n.projects.size} projects", style = T.caption, color = Brand.secondary)
                        for (p in n.projects.take(5)) NearbyLine(
                            p.name + (p.cost?.let { " · ${Format.compactMoney(it)}" } ?: ""),
                            listOfNotNull(
                                NearbyMoney.statusLabel(p.status), if (p.status == "in_progress") p.percent?.let { "${it.toInt()}%" } else null,
                                p.government, String.format(java.util.Locale.US, "%.1f mi", p.miles),
                            ).joinToString(" · "),
                        )
                    }
                }
                failed -> Text("Couldn't load right now.", style = T.subhead, color = Brand.secondary)
                else -> Loading()
            }
        }
    }
}

@Composable
private fun NearbyLine(title: String, detail: String) {
    Column(Modifier.semantics(mergeDescendants = true) {}.padding(vertical = 2.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(title, style = T.subhead, color = Brand.text, maxLines = 2)
        Text(detail, style = T.caption, color = Brand.secondary)
    }
}
