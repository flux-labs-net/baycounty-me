import SwiftUI
import BayCountyKit

struct GovernmentsView: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if store.governments.isEmpty {
                    if let e = store.errors["government-profiles"] {
                        ContentUnavailableView("Couldn't load governments", systemImage: "wifi.slash", description: Text(e))
                    } else {
                        ProgressView().frame(maxWidth: .infinity)
                    }
                }
                ForEach(store.governments) { g in
                    NavigationLink(value: Route.government(g.govID)) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(g.name).font(.body.weight(.medium))
                            HStack(spacing: 6) {
                                if let p = g.population { Text("\(Format.number(p)) residents") }
                                if let b = g.budgetTotal { Text("· \(Format.compactMoney(b)) budget") }
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 2)
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
            .navigationTitle("Governments")
            .refreshable { await store.loadGovernments() }
            .withRoutes()
        }
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
