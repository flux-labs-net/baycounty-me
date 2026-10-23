import SwiftUI
import Charts
import BayCountyKit

/// CRA Spending: what Bay County's six redevelopment agencies paid for, mapped.
struct CRAView: View {
    @Environment(AppStore.self) private var store
    @State private var selected: Route?
    private let id = "cra-payments"

    private var rows: [Row] { store.rows[id] ?? [] }

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 10) {
                    Text("Community Redevelopment Agencies keep a share of property tax growth in their districts. This is what they spent it on.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    HStack(spacing: 10) {
                        StatTile(title: "Paid out", value: Format.compactMoney(CRALedger.paidOut(rows)), caption: "Reported spent")
                        StatTile(title: "Committed or budgeted", value: Format.compactMoney(CRALedger.pending(rows)), caption: "Not proof of payment")
                    }
                    FreshnessNote(key: id)
                }
                .padding(.vertical, 4)
            }

            if !rows.isEmpty {
                Section {
                    RecordsMap(datasetID: id, rows: rows) { row in selected = .record(id, rowID: row.id) }
                        .frame(height: 260)
                        .listRowInsets(EdgeInsets())
                    HStack(spacing: 12) {
                        ForEach(["Spent", "Committed", "Budgeted", "Proposed"], id: \.self) { s in
                            HStack(spacing: 4) { Circle().fill(Brand.status(s)).frame(width: 8, height: 8); Text(s) }
                        }
                    }
                    .font(.caption2).foregroundStyle(.secondary)
                }

                let summaries = CRALedger.summaries(rows)
                Section("By agency") {
                    Chart(summaries) { s in
                        BarMark(x: .value("Amount", s.paidOut), y: .value("Agency", s.agency.replacingOccurrences(of: " CRA", with: "")))
                            .foregroundStyle(by: .value("Kind", "Paid out"))
                        BarMark(x: .value("Amount", s.pending), y: .value("Agency", s.agency.replacingOccurrences(of: " CRA", with: "")))
                            .foregroundStyle(by: .value("Kind", "Committed or budgeted"))
                    }
                    .chartForegroundStyleScale(["Paid out": Brand.navy, "Committed or budgeted": Brand.navy.opacity(0.35)])
                    .chartXAxis {
                        AxisMarks { v in
                            AxisGridLine()
                            AxisValueLabel { if let d = v.as(Double.self) { Text(Format.compactMoney(d)) } }
                        }
                    }
                    .chartLegend(position: .bottom)
                    .frame(height: CGFloat(summaries.count) * 40 + 60)
                    .padding(.vertical, 6)

                    ForEach(summaries) { s in
                        NavigationLink(value: Route.dataset(id, filters: ["cra": s.agency])) {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(s.agency).font(.body.weight(.medium))
                                    Text("\(s.records) records").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text(Format.compactMoney(s.paidOut)).monospacedDigit()
                                    if s.pending > 0 { Text("+\(Format.compactMoney(s.pending)) planned").font(.caption).foregroundStyle(.secondary) }
                                }
                            }
                        }
                    }
                }

                Section {
                    NavigationLink(value: Route.dataset(id)) { Label("All \(rows.count) records", systemImage: "list.bullet") }
                    WebLink(title: "CRA Spending on BayCounty.me", url: URL(string: "https://baycounty.me/public-money/cra-spending"))
                } footer: {
                    Text("Totals count each dollar once. Records that are parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out of totals.")
                }
            } else if store.errors[id] == nil {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .navigationTitle("CRA Spending")
        .task { await store.load(id) }
        .refreshable { await store.load(id, force: true) }
        .navigationDestination(item: $selected) { route in
            if case .record(let d, let r) = route { RecordDetailView(datasetID: d, rowID: r) }
        }
    }
}
