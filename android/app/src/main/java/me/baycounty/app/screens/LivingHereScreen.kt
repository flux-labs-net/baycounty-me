package me.baycounty.app.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import me.baycounty.app.Route
import me.baycounty.app.ui.*
import me.baycounty.kit.Outdoors

private data class Tile(val title: String, val symbol: String, val tone: Tone, val route: Route)

/** The Living here tab: the site's "Living here" menu as a grid of tiles, today's beach flag, then the rest of
 *  what's going on around town. */
@Composable
fun LivingHereScreen() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val home = store.home
    LaunchedEffect(Unit) { store.load("beach-conditions") }
    val tiles = listOf(
        Tile("Things to do", "calendar", Tone.SALMON, Route.Events),
        Tile("Beaches", "beach.umbrella", Tone.BLUE, Route.Beaches),
        Tile("Parks and trails", "tree", Tone.TEAL, Route.Parks),
        Tile("Schools", "graduationcap", Tone.AMBER, Route.Schools),
        Tile("Trash and utilities", "trash", Tone.TEAL, Route.Utilities(home)),
        Tile("Restaurants", "fork.knife", Tone.SALMON, Route.Dataset("restaurants")),
        Tile("New businesses", "storefront", Tone.BLUE, Route.Dataset("new-businesses")),
        Tile("Jobs", "briefcase", Tone.AMBER, Route.Dataset("job-openings")),
        Tile("Storms and alerts", "exclamationmark.triangle", Tone.SALMON, Route.Emergency),
    )
    Screen("Living here", spacing = 24) {
        item {
            Text(home?.let { "What to do and what you need, near ${it.display}." } ?: "What to do and what you need, around Bay County.",
                style = T.subhead, color = Brand.secondary)
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                for (line in tiles.chunked(3)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        for (t in line) {
                            Column(
                                Modifier.weight(1f).heightIn(min = 96.dp).card(16.dp).clickable { nav.push(t.route) }
                                    .padding(horizontal = 6.dp, vertical = 12.dp).semantics(mergeDescendants = true) {},
                                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterVertically),
                            ) {
                                ToneIcon(t.symbol, t.tone, 42.dp)
                                Text(t.title, style = T.caption.copy(fontWeight = FontWeight.SemiBold), color = Brand.text, textAlign = TextAlign.Center, maxLines = 2)
                            }
                        }
                    }
                }
            }
        }
        item { BeachCard() }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                SectionHeader("More around town")
                CardList {
                    if (home != null) RouteRow(Route.Address(home), "My address", home.display, symbol = "house")
                    else RouteRow(Route.MyAddress, "My address", "Tax bill, districts and meetings for one address", symbol = "house")
                    RowDivider(50.dp)
                    RouteRow(Route.HurricanePrep, "Hurricane prep", "Sandbags, generators, disaster help", symbol = "hurricane")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("development-projects"), "Building and development", "New homes and projects in review", symbol = "building.2")
                    RowDivider(50.dp)
                    RouteRow(Route.Dataset("road-contracts"), "Road projects", "State road work and costs", symbol = "road.lanes")
                    RowDivider(50.dp)
                    RouteRow(Route.Chambers, "Business community", "Chamber boards, events and public money", symbol = "storefront")
                    RowDivider(50.dp)
                    RouteRow(Route.Military, "Military and the bases", "Base news and federal contracts", symbol = "shield")
                    RowDivider(50.dp)
                    RouteRow(Route.Volunteer, "Volunteer", "Open needs from local nonprofits", symbol = "heart")
                }
            }
        }
    }
}

/** Today's beach flag on navy, like the site's beach card. Hidden until the conditions load. */
@Composable
private fun BeachCard() {
    val store = LocalStore.current
    val nav = LocalNav.current
    val now = Outdoors.forecast(store.rows["beach-conditions"] ?: emptyList()).firstOrNull() ?: return
    val flag = now.string("flag_color") ?: return
    val dark = flag == "Yellow" || flag == "Green"
    Column(
        Modifier.fillMaxWidth().background(Brand.navyFill, RoundedCornerShape(18.dp)).clickable { nav.push(Route.Beaches) }.padding(18.dp)
            .semantics(mergeDescendants = true) {},
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("BEACHES TODAY", style = T.caption.copy(fontWeight = FontWeight.SemiBold, letterSpacing = 0.6.sp), color = Color.White.copy(alpha = 0.85f))
            Spacer(Modifier.weight(1f))
            Text(
                "$flag flag", style = T.caption.copy(fontWeight = FontWeight.Bold), color = if (dark) Color(0xFF161B24) else Color.White,
                modifier = Modifier.background(Color(0xFF000000 or Outdoors.flagHex(flag)), CircleShape).padding(horizontal = 10.dp, vertical = 4.dp),
            )
        }
        Text(listOfNotNull(now.string("rip_current_risk")?.let { "$it rip current risk." }, now.string("surf_height")?.let { "Surf $it." }).joinToString(" "),
            style = T.headline, color = Color.White)
        Text("From the National Weather Service. Tap for water quality and beach access.", style = T.caption, color = Color.White.copy(alpha = 0.85f))
    }
}
