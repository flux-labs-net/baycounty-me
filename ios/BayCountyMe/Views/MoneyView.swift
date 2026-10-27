import SwiftUI
import BayCountyKit

/// The Money tab: the website's Public Money menu, with native screens where the app has them.
struct MoneyView: View {
    @Environment(AppStore.self) private var store

    private struct Item: Identifiable {
        let title: String
        let symbol: String
        let detail: String
        /// A native screen, or nil for a site page opened in the in-app browser.
        var route: Route? = nil
        var site: String? = nil
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
        .init(title: "Budget compare", symbol: "arrow.left.arrow.right", detail: "One government's budget, two years side by side", route: .budgetCompare()),
        .init(title: "Cost per resident", symbol: "person.2", detail: "Each service, per resident", route: .dataset("budget-per-resident")),
        .init(title: "CRA spending", symbol: "building.2", detail: "What redevelopment agencies paid for", route: .cra),
        .init(title: "CRA tax increment", symbol: "percent", detail: "Property tax that goes to the CRAs instead", route: .craIncrement),
        .init(title: "Sales tax projects", symbol: "road.lanes", detail: "Half-cent projects: promised vs built", route: .dataset("sales-tax-projects")),
        .init(title: "Hurricane Michael", symbol: "hurricane", detail: "Every FEMA rebuilding project", route: .dataset("fema-michael-projects")),
    ]
    private let accountability: [Item] = [
        .init(title: "Accountability console", symbol: "checklist", detail: "Projects from budget to close-out, with open questions", route: .accountability),
        .init(title: "Savings finder", symbol: "dollarsign.arrow.circlepath", detail: "Where governments could spend less", route: .dataset("savings-opportunities")),
        .init(title: "Contracts", symbol: "signature", detail: "Who wins contracts, and how", route: .dataset("contracts")),
        .init(title: "Companies", symbol: "building", detail: "Every company paid, with its contracts and votes", route: .vendors),
        .init(title: "How they voted", symbol: "hand.raised", detail: "Every recorded vote on money decisions", route: .dataset("votes")),
        .init(title: "Tourism payments", symbol: "dollarsign.circle", detail: "Who the tourism agencies paid", route: .dataset("vendor-payments")),
        .init(title: "Change orders", symbol: "arrow.triangle.2.circlepath", detail: "How much contracts grew", route: .dataset("change-orders")),
        .init(title: "Emergency purchases", symbol: "exclamationmark.triangle", detail: "Bought without bidding", route: .dataset("emergency-purchases")),
        .init(title: "Debt", symbol: "creditcard", detail: "What each government owes", route: .dataset("debt")),
        .init(title: "Bonds and loans", symbol: "banknote", detail: "Every bond, note and loan", route: .dataset("bonds")),
        .init(title: "Audit findings", symbol: "magnifyingglass", detail: "What outside auditors flagged", route: .dataset("audit-findings")),
    ]
    /// The site's Connections menu.
    private let connections: [Item] = [
        .init(title: "Network", symbol: "point.3.filled.connected.trianglepath.dotted", detail: "Who every government paid, and who gave to officials", site: "/connections"),
        .init(title: "Campaign gifts", symbol: "chart.bar", detail: "What each official raised, and from whom", route: .dataset("campaign-finance")),
        .init(title: "Donors with contracts", symbol: "link", detail: "Businesses that gave and also hold contracts", route: .donorContracts),
        .init(title: "Money map", symbol: "point.3.connected.trianglepath.dotted", detail: "Donors, officials and votes on their contracts", route: .moneyMap),
        .init(title: "Shared owners", symbol: "person.2", detail: "Businesses with a shared owner that gave to the same candidate", site: "/connections/shared-owners"),
        .init(title: "Nonprofits", symbol: "heart.text.square", detail: "Every local nonprofit, its public money, and its board", route: .dataset("nonprofits")),
        .init(title: "Nonprofit boards", symbol: "person.3", detail: "Who sits on each nonprofit's board", route: .dataset("nonprofit-board-members")),
        .init(title: "Chambers of commerce", symbol: "storefront", detail: "Boards, events and public money", route: .chambers),
        .init(title: "Business ties", symbol: "briefcase", detail: "Officials' and candidates' businesses", site: "/connections/business-ties"),
    ]
    private let elections: [Item] = [
        .init(title: "2026 candidates", symbol: "checkmark.seal", detail: "Who's running, and what they raised", route: .dataset("candidates-2026")),
        .init(title: "Gifts from organizations", symbol: "envelope", detail: "2026 contributions from businesses and groups", route: .dataset("campaign-contributions-2026")),
        .init(title: "Past elections", symbol: "clock.arrow.circlepath", detail: "Every local race from 2016 to 2025, with what each raised", route: .dataset("campaign-history")),
        .init(title: "Gifts in past races", symbol: "tray.full", detail: "Business and group gifts to 2016 to 2025 campaigns", route: .dataset("campaign-contributions-history")),
        .init(title: "Business owners who gave", symbol: "person.text.rectangle", detail: "Gifts from people who run a registered business", route: .dataset("owner-gifts")),
    ]

    private enum MoneySection: String, CaseIterable { case pay, goes, accountability, connections, elections }

    private func title(_ s: MoneySection) -> String {
        switch s { case .pay: "What you pay"; case .goes: "Where it goes"; case .accountability: "Accountability"; case .connections: "Connections"; case .elections: "Elections" }
    }
    private func items(_ s: MoneySection) -> [Item] {
        switch s { case .pay: pay; case .goes: goes; case .accountability: accountability; case .connections: connections; case .elections: elections }
    }

    @State private var picked: MoneySection = .pay

    /// Running totals shown beside a row, from the government profiles and the Amendment 3 model.
    private func value(_ item: Item) -> String? {
        let g = store.governments
        switch item.title {
        case "Amendment 3":
            guard let a3 = store.amendment3 else { return nil }
            let v = a3.localImpact(1)
            return v > 0 ? "−" + Format.compactMoney(v) : nil
        case "Hurricane Michael": return total(g.compactMap(\.femaMichael))
        case "Debt": return total(g.compactMap(\.debtTotal))
        case "Audit findings":
            let n = g.compactMap(\.auditFindings).reduce(0, +)
            return n > 0 ? "\(n)" : nil
        default: return nil
        }
    }

    private func total(_ v: [Double]) -> String? {
        let t = v.reduce(0, +)
        return t > 0 ? Format.compactMoney(t) : nil
    }

    var body: some View {
        NavigationStack {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        levyCard
                        ChipRow(chips: MoneySection.allCases.map { (id: $0, label: title($0)) }, selected: picked) { s in
                            picked = s
                            withAnimation { proxy.scrollTo(s, anchor: .top) }
                        }
                        ForEach(MoneySection.allCases, id: \.self) { s in
                            section(title(s), items(s)).id(s)
                        }
                        CardList {
                            RouteRow(route: .explore, title: "Every dataset", symbol: "square.grid.2x2")
                            RowDivider(inset: 50)
                            WebRow(title: "Sales tax projects map", symbol: "map", url: URL(string: "https://baycounty.me/public-money/sales-tax-projects"))
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
                }
            }
            .background(Brand.canvas)
            .navigationTitle("Money")
            .refreshable { await store.loadGovernments() }
            .task { await store.loadAmendment3() }
            .withRoutes()
        }
    }

    /// Property tax levied this year across every government, split by who levies it.
    @ViewBuilder private var levyCard: some View {
        let g = store.governments
        let county = g.filter { $0.kind == "county" }.compactMap(\.propertyTaxLevy).reduce(0, +)
        let schools = g.filter { $0.kind == "schools" }.compactMap(\.propertyTaxLevy).reduce(0, +)
        let cities = g.filter { $0.kind == "city" }.compactMap(\.propertyTaxLevy).reduce(0, +)
        let total = county + schools + cities
        if total > 0 {
            let parts: [(label: String, value: Double, color: Color)] = [
                ("Schools", schools, Color(red: 0.56, green: 0.70, blue: 0.89)),
                ("County", county, Color(red: 1.0, green: 0.55, blue: 0.51)),
                ("Cities", cities, Brand.amber),
            ]
            NavigationLink(value: Route.taxCalculator()) {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Property tax levied this year").font(.footnote).foregroundStyle(.white.opacity(0.8))
                    Text(Format.compactMoney(total)).font(.largeTitle.weight(.heavy).monospacedDigit()).foregroundStyle(.white)
                    StackBar(parts: parts)
                    HStack(spacing: 14) {
                        ForEach(parts, id: \.label) { p in
                            HStack(spacing: 5) {
                                RoundedRectangle(cornerRadius: 2).fill(p.color).frame(width: 8, height: 8)
                                Text("\(p.label) \(Int((p.value / total * 100).rounded()))%")
                            }
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.8))
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(18)
                .background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .combine)
            .accessibilityHint("Opens the tax calculator")
        }
    }

    private func section(_ title: String, _ items: [Item]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: title)
            CardList {
                ForEach(items) { i in
                    if let route = i.route {
                        RouteRow(route: route, title: i.title, detail: i.detail, symbol: i.symbol, value: value(i))
                    } else if let site = i.site {
                        WebRow(title: i.title, detail: i.detail, symbol: i.symbol, url: URL(string: "https://baycounty.me" + site))
                    }
                    if i.id != items.last?.id { RowDivider(inset: 50) }
                }
            }
        }
    }
}
