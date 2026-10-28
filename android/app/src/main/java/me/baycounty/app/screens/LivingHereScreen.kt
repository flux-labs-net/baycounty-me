package me.baycounty.app.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import me.baycounty.app.Route
import me.baycounty.app.ui.*

/** The Living here tab: the site's "Living here" menu (your address, trash day, schools, beaches, storms, around town). */
@Composable
fun LivingHereScreen() {
    val store = LocalStore.current
    val home = store.home
    Screen("Living here", spacing = 24) {
        item {
            LivingGroup("Home and family") {
                RouteRow(Route.MyHome, "My home", "Sign in to see meetings, events, road work and alerts near your home", symbol = "person.crop.circle")
                RowDivider(50.dp)
                if (home != null) RouteRow(Route.Address(home), "My address", home.display, symbol = "house")
                else RouteRow(Route.MyAddress, "My address", "Tax bill, districts and meetings for one address", symbol = "house")
                RowDivider(50.dp)
                RouteRow(Route.Utilities(home), "Utilities and trash day", "Who provides what, and your pickup day", symbol = "trash")
                RowDivider(50.dp)
                RouteRow(Route.Schools, "Public schools", "Your zoned schools, calendar and grades", symbol = "graduationcap")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("restaurants"), "Restaurant inspections", "Every inspection, warning and closure", symbol = "fork.knife")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("job-openings"), "Government jobs", "Open jobs at every local government", symbol = "briefcase")
            }
        }
        item {
            LivingGroup("Outdoors and storms") {
                RouteRow(Route.Beaches, "Beaches", "Today's flag, rip currents and water quality", symbol = "flag")
                RowDivider(50.dp)
                RouteRow(Route.Parks, "Parks", "Parks, boat ramps and trails", symbol = "tree")
                RowDivider(50.dp)
                RouteRow(Route.Emergency, "Emergencies and alerts", "Warnings, evacuation zones, shelters", symbol = "exclamationmark.triangle")
                RowDivider(50.dp)
                RouteRow(Route.HurricanePrep, "Hurricane prep", "Sandbags, generators, disaster help", symbol = "hurricane")
            }
        }
        item {
            LivingGroup("Around town") {
                RouteRow(Route.Events, "Events", "What's happening around the county", symbol = "calendar")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("new-businesses"), "New businesses", "Companies filed, month by month", symbol = "storefront")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("development-projects"), "Building and development", "New homes and projects in review", symbol = "building.2")
                RowDivider(50.dp)
                RouteRow(Route.Dataset("road-contracts"), "Road projects", "State road work and costs", symbol = "road.lanes")
                RowDivider(50.dp)
                RouteRow(Route.Military, "Military and the bases", "Base news and federal contracts", symbol = "shield")
                RowDivider(50.dp)
                RouteRow(Route.Volunteer, "Volunteer", "Open needs from local nonprofits", symbol = "heart")
            }
        }
    }
}

@Composable
private fun LivingGroup(title: String, rows: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionHeader(title)
        CardList { rows() }
    }
}
