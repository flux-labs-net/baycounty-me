import SwiftUI
import BayCountyKit

struct GovernmentsView: View {
    @Environment(AppStore.self) private var store
    @State private var metric: GovMetric = .perResident

    var body: some View {
        NavigationStack {
            List {
                if store.governments.isEmpty {
                    if let e = store.errors["government-profiles"] {
                        ContentUnavailableView("Couldn't load governments", systemImage: "wifi.slash", description: Text(e))
                    } else {
                        ProgressView().frame(maxWidth: .infinity)
                    }
                } else {
                    Section {
                        Picker("Compare", selection: $metric) {
                            ForEach(GovMetric.allCases) { Text($0.short).tag($0) }
                        }
                        .pickerStyle(.segmented)
                        CompareBars(title: metric.title, caption: metric.caption,
                                    items: metric.items(store.governments), format: metric.format)
                    }
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                    .listRowSeparator(.hidden)
                }
                let maxBudget = store.governments.compactMap(\.budgetTotal).max() ?? 0
                Section("Every government") {
                    ForEach(store.governments) { g in
                        NavigationLink(value: Route.government(g.govID)) {
                            VStack(alignment: .leading, spacing: 5) {
                                HStack(alignment: .firstTextBaseline) {
                                    Text(g.name).font(.body.weight(.semibold))
                                    Spacer()
                                    if let b = g.budgetTotal {
                                        Text(Format.compactMoney(b)).font(.subheadline.weight(.semibold).monospacedDigit())
                                            + Text(" budget").font(.caption).foregroundColor(.secondary)
                                    }
                                }
                                if let b = g.budgetTotal, maxBudget > 0 { MagnitudeBar(fraction: b / maxBudget, height: 5) }
                                HStack(spacing: 6) {
                                    if let p = g.population { Text("\(Format.number(p)) residents") }
                                    if let m = g.millage { Text("· \(Format.number(m)) mills") }
                                }
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 3)
                        }
                    }
                }
                Section {
                    NavigationLink(value: Route.people) { Label("People: officials, leaders and candidates", systemImage: "person.3") }
                    NavigationLink(value: Route.dataset("officials-pay")) { Label("What officials are paid", systemImage: "person.text.rectangle") }
                    WebLink(title: "Compare governments side by side", symbol: "chart.bar.xaxis",
                            url: URL(string: "https://baycounty.me/compare"))
                    WebLink(title: "Who runs Bay County", symbol: "building.columns", url: URL(string: "https://baycounty.me/who-runs-bay-county"))
                }
            }
            .navigationTitle("Places")
            .refreshable { await store.loadGovernments() }
            .withRoutes()
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

struct GovernmentDetailView: View {
    @Environment(AppStore.self) private var store
    let govID: String

    /// Datasets that carry a gov_id column, so they can be filtered to this government.
    private var related: [DatasetInfo] {
        (store.catalog?.datasets ?? []).filter {
            !DatasetSpec.ownScreens.contains($0.id) && $0.column("gov_id") != nil
        }
    }

    var body: some View {
        if let g = store.government(govID) {
            List {
                Section {
                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 10) {
                        if let v = g.budgetTotal { StatTile(title: "Total budget", value: Format.compactMoney(v), caption: g.budgetStatus) }
                        if let v = g.budgetPerResident { StatTile(title: "Budget per resident", value: Format.money(v.rounded())) }
                        if let v = g.generalFund { StatTile(title: "General fund", value: Format.compactMoney(v)) }
                        if let v = g.propertyTaxLevy { StatTile(title: "Property tax levied", value: Format.compactMoney(v)) }
                        if let v = g.millage { StatTile(title: "Tax rate (mills)", value: Format.number(v), caption: "Per $1,000 of taxable value") }
                        if let v = g.debtTotal { StatTile(title: "Debt", value: Format.compactMoney(v), caption: g.debtPerResident.map { "\(Format.money($0.rounded())) per resident" }) }
                        if let v = g.auditFindings { StatTile(title: "Audit findings", value: "\(v)", caption: [g.auditYear, g.repeatFindings.map { "\($0) repeat" }].compactMap { $0 }.joined(separator: " · ")) }
                        if let v = g.votesRecorded { StatTile(title: "Votes recorded", value: "\(v)", caption: g.splitVotes.map { "\($0) split" }) }
                        if let v = g.typicalUtilityBill { StatTile(title: "Typical utility bill", value: Format.money(v), caption: "Per month") }
                        if let v = g.femaMichael { StatTile(title: "FEMA, Hurricane Michael", value: Format.compactMoney(v)) }
                    }
                    .listRowInsets(EdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12))
                    if let p = g.population {
                        Text("\(Format.number(p)) residents (2025 estimate)").font(.footnote).foregroundStyle(.secondary)
                    }
                }

                Section {
                    ForEach([GovMetric.perResident, .millage, .debt], id: \.self) { m in
                        let items = m.items(store.governments)
                        if items.contains(where: { $0.id == govID }) {
                            CompareBars(title: m.title, caption: m.caption, items: items, highlight: govID, format: m.format)
                        }
                    }
                    if let v = g.votesRecorded, let sv = g.splitVotes, v > 0 {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Recorded votes").font(.subheadline.weight(.semibold))
                            ShareBar(parts: [.init(label: "Unanimous", value: Double(v - sv), color: Brand.good),
                                             .init(label: "Split", value: Double(sv), color: Brand.amber)])
                        }
                        .padding(14)
                        .background(Brand.surface, in: RoundedRectangle(cornerRadius: 12))
                    }
                } header: {
                    Text("Compared with the others")
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 6, leading: 0, bottom: 6, trailing: 0))
                .listRowSeparator(.hidden)

                let upcoming = Array(Meeting.upcoming(store.meetings).filter { $0.govID == govID }.prefix(3))
                if !upcoming.isEmpty {
                    Section("Coming up") {
                        ForEach(upcoming) { m in NavigationLink(value: Route.meeting(m.id)) { MeetingRow(meeting: m) } }
                    }
                }

                Section("Records") {
                    ForEach(related) { d in
                        NavigationLink(value: Route.dataset(d.id, filters: ["gov_id": govID])) {
                            Label(d.title, systemImage: DatasetSpec.for(d.id).symbol)
                        }
                    }
                }

                Section {
                    NavigationLink(value: Route.taxCalculator()) { Label("Budget and where the money comes from", systemImage: "chart.pie") }
                    WebLink(title: "Full profile on BayCounty.me", url: g.pageURL)
                }
            }
            .navigationTitle(g.name)
            .navigationBarTitleDisplayMode(.inline)
        } else {
            ContentUnavailableView("Not found", systemImage: "building.columns")
        }
    }
}
