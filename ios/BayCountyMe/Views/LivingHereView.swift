import SwiftUI
import BayCountyKit

/// The Living here tab: the day-to-day pages (the site's "Living here" menu): your address, trash day, schools,
/// beaches, storms and what's going on around town.
struct LivingHereView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    section("Home and family") {
                        RouteRow(route: .myHome, title: "My home", detail: "Sign in to see meetings, events, road work and alerts near your home", symbol: "person.crop.circle")
                        RowDivider(inset: 50)
                        if let home = store.home {
                            RouteRow(route: .address(home), title: "My address", detail: home.display, symbol: "house")
                        } else {
                            RouteRow(route: .myAddress, title: "My address", detail: "Tax bill, districts and meetings for one address", symbol: "house")
                        }
                        RowDivider(inset: 50)
                        RouteRow(route: .utilities(store.home), title: "Utilities and trash day", detail: "Who provides what, and your pickup day", symbol: "trash")
                        RowDivider(inset: 50)
                        RouteRow(route: .schools, title: "Public schools", detail: "Your zoned schools, calendar and grades", symbol: "graduationcap")
                        RowDivider(inset: 50)
                        RouteRow(route: .dataset("restaurants"), title: "Restaurant inspections", detail: "Every inspection, warning and closure", symbol: "fork.knife")
                        RowDivider(inset: 50)
                        RouteRow(route: .dataset("job-openings"), title: "Government jobs", detail: "Open jobs at every local government", symbol: "briefcase")
                    }
                    section("Outdoors and storms") {
                        RouteRow(route: .beaches, title: "Beaches", detail: "Today's flag, rip currents and water quality", symbol: "flag")
                        RowDivider(inset: 50)
                        RouteRow(route: .parks, title: "Parks", detail: "Parks, boat ramps and trails", symbol: "tree")
                        RowDivider(inset: 50)
                        RouteRow(route: .emergency, title: "Emergencies and alerts", detail: "Warnings, evacuation zones, shelters", symbol: "exclamationmark.triangle")
                        RowDivider(inset: 50)
                        RouteRow(route: .hurricanePrep, title: "Hurricane prep", detail: "Sandbags, generators, disaster help", symbol: "hurricane")
                    }
                    section("Around town") {
                        RouteRow(route: .events, title: "Events", detail: "What's happening around the county", symbol: "calendar")
                        RowDivider(inset: 50)
                        RouteRow(route: .dataset("new-businesses"), title: "New businesses", detail: "Companies filed, month by month", symbol: "storefront")
                        RowDivider(inset: 50)
                        RouteRow(route: .dataset("development-projects"), title: "Building and development", detail: "New homes and projects in review", symbol: "building.2")
                        RowDivider(inset: 50)
                        RouteRow(route: .dataset("road-contracts"), title: "Road projects", detail: "State road work and costs", symbol: "road.lanes")
                        RowDivider(inset: 50)
                        RouteRow(route: .military, title: "Military and the bases", detail: "Base news and federal contracts", symbol: "shield")
                        RowDivider(inset: 50)
                        RouteRow(route: .volunteer, title: "Volunteer", detail: "Open needs from local nonprofits", symbol: "heart")
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle("Living here")
            .withRoutes()
        }
    }

    private func section<C: View>(_ title: String, @ViewBuilder _ rows: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: title)
            CardList { rows() }
        }
    }
}
