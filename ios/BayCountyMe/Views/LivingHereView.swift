import SwiftUI
import BayCountyKit

/// The Living here tab: the day-to-day pages (the site's "Living here" menu) as a grid of tiles, today's beach
/// flag, then the rest of what's going on around town.
struct LivingHereView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []

    /// The nine tiles, three by three.
    private var tiles: [(title: String, symbol: String, tone: Tone, route: Route)] {
        [
            ("Things to do", "calendar", .salmon, .events),
            ("Beaches", "beach.umbrella", .blue, .beaches),
            ("Parks and trails", "tree", .teal, .parks),
            ("Schools", "graduationcap", .amber, .schools),
            ("Trash and utilities", "trash", .teal, .utilities(store.home)),
            ("Restaurants", "fork.knife", .salmon, .restaurants),
            ("New businesses", "storefront", .blue, .dataset("new-businesses")),
            ("Jobs", "briefcase", .amber, .dataset("job-openings")),
            ("Storms and alerts", "exclamationmark.triangle", .salmon, .emergency),
        ]
    }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    Text(store.home.map { "What to do and what you need, near \($0.display)." } ?? "What to do and what you need, around Bay County.")
                        .font(.subheadline).foregroundStyle(.secondary)
                        .padding(.top, -12)
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 3), spacing: 10) {
                        ForEach(tiles, id: \.title) { t in
                            NavigationLink(value: t.route) {
                                VStack(spacing: 8) {
                                    ToneIcon(symbol: t.symbol, tone: t.tone, size: 42)
                                    Text(t.title).font(.caption.weight(.semibold)).foregroundStyle(.primary)
                                        .multilineTextAlignment(.center).lineLimit(2).minimumScaleFactor(0.85)
                                }
                                .frame(maxWidth: .infinity, minHeight: 96)
                                .padding(.horizontal, 6)
                                .card(16)
                            }
                            .buttonStyle(PressScale())
                        }
                    }
                    beachCard
                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeader(title: "More around town")
                        CardList {
                            RouteRow(route: .myHome, title: "My home", detail: "Sign in to see meetings, events, road work and alerts near your home", symbol: "person.crop.circle")
                            RowDivider(inset: 50)
                            if let home = store.home {
                                RouteRow(route: .address(home), title: "My address", detail: home.display, symbol: "house")
                            } else {
                                RouteRow(route: .myAddress, title: "My address", detail: "Tax bill, districts and meetings for one address", symbol: "house")
                            }
                            RowDivider(inset: 50)
                            RouteRow(route: .hurricanePrep, title: "Hurricane prep", detail: "Sandbags, generators, disaster help", symbol: "hurricane")
                            RowDivider(inset: 50)
                            RouteRow(route: .publicSafety, title: "Police, fire & Sheriff", detail: "Who covers your town, crimes reported, budgets", symbol: "shield.lefthalf.filled")
                            RowDivider(inset: 50)
                            RouteRow(route: .dataset("development-projects"), title: "Building and development", detail: "New homes and projects in review", symbol: "building.2")
                            RowDivider(inset: 50)
                            RouteRow(route: .dataset("road-contracts"), title: "Road projects", detail: "State road work and costs", symbol: "road.lanes")
                            RowDivider(inset: 50)
                            RouteRow(route: .chambers, title: "Business community", detail: "Chamber boards, events and public money", symbol: "person.3")
                            RowDivider(inset: 50)
                            RouteRow(route: .military, title: "Military and the bases", detail: "Base news and federal contracts", symbol: "shield")
                            RowDivider(inset: 50)
                            RouteRow(route: .volunteer, title: "Volunteer", detail: "Open needs from local nonprofits", symbol: "heart")
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle("Living here")
            .withRoutes()
            .task { await store.load("beach-conditions") }
        }
    }

    /// Today's beach flag on navy, like the site's beach card. Hidden until the conditions load.
    @ViewBuilder private var beachCard: some View {
        let rows = store.rows["beach-conditions"] ?? []
        if let now = Outdoors.forecast(rows).first, let flag = now.string("flag_color") {
            NavigationLink(value: Route.beaches) {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text("BEACHES TODAY").font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(.white.opacity(0.85))
                        Spacer()
                        Text("\(flag) flag").font(.caption.weight(.bold))
                            .foregroundStyle(Self.darkText(flag) ? Color(hex: 0x161B24) : .white)
                            .padding(.horizontal, 10).padding(.vertical, 4)
                            .background(Color(hex: Outdoors.flagHex(flag)), in: Capsule())
                    }
                    Text([now.string("rip_current_risk").map { "\($0) rip current risk." }, now.string("surf_height").map { "Surf \($0)." }]
                            .compactMap { $0 }.joined(separator: " "))
                        .font(.headline).foregroundStyle(.white).multilineTextAlignment(.leading)
                    Text("From the National Weather Service. Tap for water quality and beach access.")
                        .font(.caption).foregroundStyle(.white.opacity(0.85)).multilineTextAlignment(.leading)
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .buttonStyle(PressScale())
            .accessibilityElement(children: .combine)
        }
    }

    private static func darkText(_ flag: String) -> Bool { flag == "Yellow" || flag == "Green" }
}
