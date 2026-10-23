import SwiftUI
import BayCountyKit

struct HomeView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []

    private let topics: [(title: String, symbol: String, route: Route)] = [
        ("Tax calculator", "percent", .taxCalculator()),
        ("CRA Spending", "building.2", .cra),
        ("Contracts", "signature", .dataset("contracts")),
        ("How They Voted", "hand.raised", .dataset("votes")),
        ("Companies", "building", .vendors),
        ("Campaign Money", "chart.bar", .dataset("campaign-finance")),
        ("Amendment 3", "checklist", .amendment3()),
        ("Glossary", "character.book.closed", .glossary),
    ]

    var body: some View {
        NavigationStack(path: $path) {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Bay County public records in plain view.")
                            .font(.title2.weight(.semibold))
                        Text("Budgets, taxes, contracts, votes and meetings, each linked to the record it came from.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        FreshnessNote()
                    }
                    .padding(.vertical, 6)
                }

                if !store.governments.isEmpty {
                    let g = store.governments
                    Section {
                        StatStrip(tiles: [
                            .init(title: "Property tax levied", value: Format.compactMoney(g.compactMap(\.propertyTaxLevy).reduce(0, +))),
                            .init(title: "FEMA after Michael", value: Format.compactMoney(g.compactMap(\.femaMichael).reduce(0, +))),
                            .init(title: "Owed by governments", value: Format.compactMoney(g.compactMap(\.debtTotal).reduce(0, +))),
                        ])
                        .listRowBackground(Color.clear)
                        .listRowInsets(EdgeInsets(top: 4, leading: 16, bottom: 4, trailing: 16))
                    } header: {
                        Text("Bay County by the numbers")
                    } footer: {
                        Text("Totals for the county, the school district and the seven cities.")
                    }
                }

                Section {
                    if let home = store.home {
                        NavigationLink(value: Route.address(home)) {
                            HStack(spacing: 12) {
                                Image(systemName: "house.fill").font(.title3).foregroundStyle(Brand.navy)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("My Address").font(.caption).foregroundStyle(.secondary)
                                    Text(home.display).font(.headline)
                                    Text("Tax estimate, representatives, schools, flood zone").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        NavigationLink(value: Route.myAddress) { Label("Look up another address", systemImage: "magnifyingglass") }
                    } else {
                        NavigationLink(value: Route.myAddress) {
                            HStack(spacing: 12) {
                                Image(systemName: "mappin.and.ellipse").font(.title3).foregroundStyle(Brand.navy)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text("What applies to your address?").font(.headline)
                                    Text("Property tax estimate, who represents you, schools, flood and evacuation zones").font(.caption).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                } header: {
                    Text("My Address")
                }

                let next = Array(Meeting.upcoming(store.meetings).prefix(3))
                if !next.isEmpty {
                    Section {
                        ForEach(next) { m in
                            NavigationLink(value: Route.meeting(m.id)) { MeetingRow(meeting: m) }
                        }
                        Button("All meetings") { store.tab = .meetings }
                    } header: {
                        Text("Coming up")
                    }
                }

                Section("Follow the money") {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        // Buttons, not NavigationLinks: several links in one list row all fire the last one.
                        ForEach(topics, id: \.title) { t in
                            Button { path.append(t.route) } label: {
                                VStack(alignment: .leading, spacing: 8) {
                                    Image(systemName: t.symbol).font(.title3).foregroundStyle(Brand.navy)
                                    Text(t.title).font(.subheadline.weight(.medium)).foregroundStyle(.primary)
                                        .lineLimit(2).multilineTextAlignment(.leading)
                                }
                                .frame(maxWidth: .infinity, minHeight: 74, alignment: .topLeading)
                                .padding(12)
                                .background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .listRowInsets(EdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12))
                    Button("All public money") { store.tab = .money }
                }

                if !store.updates.isEmpty {
                    Section {
                        ForEach(store.updates.prefix(3)) { u in
                            NavigationLink(value: Route.updates) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(u.title).font(.subheadline.weight(.medium))
                                    Text(Dates.parse(u.date).map { Dates.display($0, hasTime: false) } ?? u.date)
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    } header: {
                        Text("What's new")
                    }
                }

                Section {
                    WebLink(title: "Compare governments", symbol: "chart.bar.xaxis", url: URL(string: "https://baycounty.me/compare"))
                    WebLink(title: "Request a public record", symbol: "doc.text", url: URL(string: "https://baycounty.me/records-request"))
                    WebLink(title: "Email alerts", symbol: "envelope", url: URL(string: "https://baycounty.me/alerts"))
                    WebLink(title: "Send a correction", symbol: "exclamationmark.bubble", url: URL(string: "https://baycounty.me/about#contact"))
                } header: {
                    Text("On the website")
                }

                Section { PoweredByFlux() }
                    .listRowBackground(Color.clear)
            }
            .navigationTitle("BayCounty.me")
            .refreshable { await store.refreshAll() }
            .withRoutes()
            .task { await openScreenshotRoute() }
        }
    }

    /// For automated screenshots: `-screen <name>` opens one screen at launch (see .github/workflows/ios-screenshots.yml).
    private func openScreenshotRoute() async {
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screen"), i + 1 < args.count, path.isEmpty else { return }
        let arg = args[i + 1]
        let simple: [String: Route] = [
            "tax": .taxCalculator(districtID: "Lynn Haven", value: 250_000, homestead: true), "amendment3": .amendment3(districtID: "Panama City", value: 300_000, homestead: true),
            "glossary": .glossary, "vendors": .vendors, "people": .people, "moneymap": .moneyMap, "donors": .donorContracts,
            "updates": .updates, "about": .about, "cra": .cra, "myaddress": .myAddress, "contracts": .dataset("contracts"),
            "vendor": .vendor("roberts-and-roberts"), "person": .person("clair-pease"), "explore": .explore,
            "votes": .dataset("votes"), "salaries": .dataset("salary-positions"),
        ]
        if let r = simple[arg] { path = [r]; return }
        let tabs: [String: AppStore.Tab] = ["tab:governments": .governments, "tab:money": .money, "tab:meetings": .meetings, "tab:search": .search]
        if let t = tabs[arg] { store.tab = t; return }
        if arg.hasPrefix("gov:") { path = [.government(String(arg.dropFirst(4)))]; return }
        if arg == "record:contract" || arg == "record:vote" {
            let ds = arg == "record:contract" ? "contracts" : "votes"
            await store.load(ds)
            let rows = store.rows[ds] ?? []
            let pick = ds == "contracts" ? rows.first { $0.string("vendor") == "Ten-8 Fire & Safety, LLC" }
                                         : rows.first { $0.string("headline") == "Approved $62.45 million FY2027 general fund budget" }
            if let r = pick ?? rows.first { path = [.record(ds, rowID: r.id)] }
            return
        }
        if arg.hasPrefix("address:") {
            let q = String(arg.dropFirst("address:".count))
            if let m = try? await store.gis.search(q).matches.first { path = [.address(m)] }
        }
    }
}
