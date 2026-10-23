import SwiftUI
import BayCountyKit

struct HomeView: View {
    @Environment(AppStore.self) private var store

    private let topics: [(title: String, symbol: String, route: Route)] = [
        ("CRA Spending", "building.2", .cra),
        ("Contracts", "signature", .dataset("contracts")),
        ("How They Voted", "hand.raised", .dataset("votes")),
        ("Salaries", "person.crop.circle.badge.checkmark", .dataset("salary-leaders")),
        ("Campaign Money", "chart.bar", .dataset("campaign-finance")),
        ("Hurricane Michael", "hurricane", .dataset("fema-michael-projects")),
        ("Sales Tax Projects", "road.lanes", .dataset("sales-tax-projects")),
        ("Audit Findings", "magnifyingglass", .dataset("audit-findings")),
    ]

    private let tools: [(title: String, symbol: String, path: String)] = [
        ("My Address", "mappin.and.ellipse", "my-address"),
        ("Tax Dollars calculator", "percent", "public-money/tax-dollars"),
        ("Compare governments", "chart.bar.xaxis", "compare"),
        ("Amendment 3", "checklist", "public-money/amendment-3"),
        ("Request a record", "doc.text", "records-request"),
        ("Send a correction", "exclamationmark.bubble", "about#contact"),
    ]

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Bay County public records in plain view.")
                            .font(.title2.weight(.semibold))
                        Text("Budgets, taxes, contracts, votes and meetings, each linked to the record it came from.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Button { store.tab = .search } label: {
                            Label("Search the records", systemImage: "magnifyingglass")
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(12)
                                .background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                        FreshnessNote()
                    }
                    .padding(.vertical, 6)
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
                        ForEach(topics, id: \.title) { t in
                            NavigationLink(value: t.route) {
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
                    Button("Every dataset") { store.tab = .explore }
                }

                Section {
                    ForEach(tools, id: \.title) { t in
                        WebLink(title: t.title, symbol: t.symbol, url: URL(string: "https://baycounty.me/\(t.path)"))
                    }
                } header: {
                    Text("On the website")
                } footer: {
                    Text("Interactive tools open the BayCounty.me page.")
                }

                Section { PoweredByFlux() }
                    .listRowBackground(Color.clear)
            }
            .navigationTitle("BayCounty.me")
            .refreshable { await store.refreshAll() }
            .withRoutes()
        }
    }
}
