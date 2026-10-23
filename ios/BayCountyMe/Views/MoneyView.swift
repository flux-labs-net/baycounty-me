import SwiftUI
import BayCountyKit

/// The Money tab: the website's Public Money menu, with native screens where the app has them.
struct MoneyView: View {
    @Environment(AppStore.self) private var store

    private struct Item: Identifiable {
        let title: String
        let symbol: String
        let detail: String
        let route: Route
        var id: String { title }
    }

    private let pay: [Item] = [
        .init(title: "Tax calculator", symbol: "percent", detail: "Your property tax bill, slice by slice", route: .taxCalculator()),
        .init(title: "Fees on your tax bill", symbol: "doc.plaintext", detail: "Fire, stormwater and other flat fees", route: .dataset("fees-assessments")),
        .init(title: "Exemptions", symbol: "house", detail: "Homestead, veterans, seniors and more", route: .dataset("property-tax-exemptions")),
        .init(title: "Amendment 3", symbol: "checklist", detail: "What the ballot amendment would change", route: .amendment3()),
        .init(title: "Tourist tax", symbol: "bed.double", detail: "The 5% bed tax visitors pay", route: .dataset("bed-tax-collections")),
        .init(title: "Tax rates by year", symbol: "chart.line.uptrend.xyaxis", detail: "Every taxing authority, 2020 to 2025", route: .dataset("property-tax-rates")),
    ]
    private let goes: [Item] = [
        .init(title: "Budgets", symbol: "chart.pie", detail: "Each budget by fund and department", route: .dataset("budget-detail")),
        .init(title: "Cost per resident", symbol: "person.2", detail: "Each service, per resident", route: .dataset("budget-per-resident")),
        .init(title: "CRA spending", symbol: "building.2", detail: "What redevelopment agencies paid for", route: .cra),
        .init(title: "Sales tax projects", symbol: "road.lanes", detail: "Half-cent projects: promised vs built", route: .dataset("sales-tax-projects")),
        .init(title: "Hurricane Michael", symbol: "hurricane", detail: "Every FEMA rebuilding project", route: .dataset("fema-michael-projects")),
    ]
    private let accountability: [Item] = [
        .init(title: "Contracts", symbol: "signature", detail: "Who wins contracts, and how", route: .dataset("contracts")),
        .init(title: "Companies", symbol: "building", detail: "Every company paid, with its contracts and votes", route: .vendors),
        .init(title: "How they voted", symbol: "hand.raised", detail: "Every recorded vote on money decisions", route: .dataset("votes")),
        .init(title: "Campaign money", symbol: "chart.bar", detail: "What each official raised", route: .dataset("campaign-finance")),
        .init(title: "Donors with contracts", symbol: "link", detail: "Businesses that gave and also hold contracts", route: .donorContracts),
        .init(title: "Money map", symbol: "point.3.connected.trianglepath.dotted", detail: "Donors, officials and contracts", route: .moneyMap),
        .init(title: "Who gets paid", symbol: "dollarsign.circle", detail: "Payments by the tourism agencies", route: .dataset("vendor-payments")),
        .init(title: "Change orders", symbol: "arrow.triangle.2.circlepath", detail: "How much contracts grew", route: .dataset("change-orders")),
        .init(title: "Emergency purchases", symbol: "exclamationmark.triangle", detail: "Bought without bidding", route: .dataset("emergency-purchases")),
        .init(title: "Debt", symbol: "creditcard", detail: "What each government owes", route: .dataset("debt")),
        .init(title: "Bonds and loans", symbol: "banknote", detail: "Every bond, note and loan", route: .dataset("bonds")),
        .init(title: "Audit findings", symbol: "magnifyingglass", detail: "What outside auditors flagged", route: .dataset("audit-findings")),
    ]
    private let elections: [Item] = [
        .init(title: "2026 candidates", symbol: "checkmark.seal", detail: "Who's running, and what they raised", route: .dataset("candidates-2026")),
        .init(title: "Gifts from organizations", symbol: "envelope", detail: "2026 contributions from businesses and groups", route: .dataset("campaign-contributions-2026")),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    section("What you pay", pay)
                    section("Where it goes", goes)
                    section("Accountability", accountability)
                    section("Elections", elections)
                    VStack(spacing: 0) {
                        NavigationLink(value: Route.explore) {
                            Label("Every dataset", systemImage: "square.grid.2x2").frame(maxWidth: .infinity, alignment: .leading).padding(14)
                        }
                        Divider().padding(.leading, 14)
                        WebLink(title: "Public money map", symbol: "map", url: URL(string: "https://baycounty.me/public-money/map"))
                            .frame(maxWidth: .infinity, alignment: .leading).padding(14)
                    }
                    .background(Brand.surface, in: RoundedRectangle(cornerRadius: 14))
                }
                .padding(16)
            }
            .background(Brand.canvas)
            .navigationTitle("Public Money")
            .withRoutes()
        }
    }

    private func section(_ title: String, _ items: [Item]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.title3.weight(.bold))
            TopicGrid(topics: items.map { TopicGrid.Topic(title: $0.title, symbol: $0.symbol, detail: $0.detail, route: $0.route) })
        }
    }
}
