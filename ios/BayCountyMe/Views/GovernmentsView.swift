import SwiftUI
import BayCountyKit

struct GovernmentsView: View {
    @Environment(AppStore.self) private var store
    @State private var metric: GovMetric = .perResident
    @State private var path: [Route] = []

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    if store.governments.isEmpty {
                        if let e = store.errors["government-profiles"] {
                            ContentUnavailableView("Couldn't load governments", systemImage: "wifi.slash", description: Text(e))
                        } else {
                            ProgressView().frame(maxWidth: .infinity, minHeight: 200)
                        }
                    } else {
                        compareCard
                        governmentsSection
                    }
                    peopleSection
                    FreshnessNote(key: "government-profiles")
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle("Places")
            .refreshable { await store.loadGovernments() }
            .withRoutes()
        }
    }

    /// Pick a measure, see every government ranked on it. Tapping a bar opens that government.
    private var compareCard: some View {
        let items = metric.items(store.governments)
        return VStack(alignment: .leading, spacing: 12) {
            ChipRow(chips: GovMetric.allCases.map { (id: $0, label: $0.short) }, selected: metric) { m in
                withAnimation(.snappy) { metric = m }
            }
            CompareBars(title: metric.title, caption: metric.caption, items: items,
                        highlight: items.first?.id, format: metric.format) { path.append(.government($0)) }
        }
    }

    private var governmentsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Every government")
            CardList {
                ForEach(store.governments) { g in
                    NavigationLink(value: Route.government(g.govID)) {
                        HStack(spacing: 12) {
                            GovBadge(govID: g.govID)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(g.name).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                Text(subtitle(g)).font(.caption.monospacedDigit()).foregroundStyle(.secondary).lineLimit(1)
                            }
                            Spacer(minLength: 4)
                            if let b = g.budgetTotal {
                                Text(Format.compactMoney(b)).font(.subheadline.weight(.bold).monospacedDigit())
                                    .foregroundStyle(.primary)
                                    .accessibilityLabel("\(Format.compactMoney(b)) budget")
                            }
                            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                        .padding(.horizontal, 14)
                        .frame(minHeight: 64)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if g.id != store.governments.last?.id { RowDivider(inset: 66) }
                }
            }
        }
    }

    private func subtitle(_ g: Government) -> String {
        [g.kind == "schools" ? "School district" : Format.label(g.kind),
         g.population.map { "\(Format.number($0)) residents" },
         g.millage.flatMap { $0 > 0 ? "\(Format.number($0)) mills" : nil }]
            .compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private var peopleSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "People")
            CardList {
                RouteRow(route: .people, title: "Officials, leaders and candidates", symbol: "person.3")
                RowDivider(inset: 50)
                RouteRow(route: .schools, title: "Public schools", detail: "Calendar, grades and students for every school", symbol: "graduationcap")
                RowDivider(inset: 50)
                RouteRow(route: .dataset("officials-pay"), title: "What officials are paid", symbol: "person.text.rectangle")
                RowDivider(inset: 50)
                RouteRow(route: .budgetCompare(), title: "Budget compare", symbol: "arrow.left.arrow.right")
                RowDivider(inset: 50)
                WebRow(title: "Compare side by side", symbol: "chart.bar.xaxis", url: URL(string: "https://baycounty.me/compare"))
            }
        }
    }
}

/// Ways to compare the governments side by side.
enum GovMetric: String, CaseIterable, Identifiable {
    case perResident, budget, millage, debt
    var id: String { rawValue }

    var short: String {
        switch self { case .perResident: "Per resident"; case .budget: "Budget"; case .millage: "Tax rate"; case .debt: "Debt" }
    }
    var title: String {
        switch self {
        case .perResident: "Budget per resident"
        case .budget: "Total budget"
        case .millage: "Property tax rate"
        case .debt: "Debt per resident"
        }
    }
    var caption: String? {
        switch self {
        case .millage: "Mills: dollars per $1,000 of taxable value"
        case .perResident: "Total budget divided by 2025 population"
        default: nil
        }
    }

    func value(_ g: Government) -> Double? {
        switch self {
        case .perResident: g.budgetPerResident
        case .budget: g.budgetTotal
        case .millage: g.millage
        case .debt: g.debtPerResident
        }
    }

    func format(_ v: Double) -> String {
        switch self {
        case .perResident, .debt: Format.money(v.rounded())
        case .budget: Format.compactMoney(v)
        case .millage: Format.number(v)
        }
    }

    func items(_ govs: [Government]) -> [CompareBars.Item] {
        govs.compactMap { g in value(g).map { CompareBars.Item(id: g.govID, label: g.name, value: $0) } }
            .sorted { $0.value > $1.value }
    }
}

