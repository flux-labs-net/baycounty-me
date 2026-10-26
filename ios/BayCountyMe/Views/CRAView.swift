import SwiftUI
import Charts
import BayCountyKit

/// CRA Spending: what Bay County's redevelopment agencies paid for, mapped.
struct CRAView: View {
    @Environment(AppStore.self) private var store
    @State private var selected: Route?
    private let id = "cra-payments"

    private var rows: [Row] { store.rows[id] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Where it goes", title: "CRA spending",
                     subtitle: "Community Redevelopment Agencies keep a share of property tax growth in their districts. This is what they spent it on.",
                     symbol: "building.2", tone: .teal)
            StatGrid {
                KPICard(title: "Paid out", value: Format.compactMoney(CRALedger.paidOut(rows)), caption: "Reported spent", symbol: "checkmark.circle", tone: .teal)
                KPICard(title: "Committed or budgeted", value: Format.compactMoney(CRALedger.pending(rows)), caption: "Not proof of payment", symbol: "clock", tone: .amber)
            }
            FreshnessNote(key: id)

            if !rows.isEmpty {
                PageSection(title: "On the map", symbol: "map", tone: .blue) {
                    VStack(alignment: .leading, spacing: 10) {
                        RecordsMap(datasetID: id, rows: rows) { row in selected = .record(id, rowID: row.id) }
                            .frame(height: 280)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                        FlowLayout(spacing: 12) {
                            ForEach(["Spent", "Committed", "Budgeted", "Proposed"], id: \.self) { s in
                                HStack(spacing: 4) { Circle().fill(Brand.status(s)).frame(width: 8, height: 8); Text(s) }
                            }
                        }
                        .font(.caption).foregroundStyle(.secondary)
                    }
                }

                let summaries = CRALedger.summaries(rows)
                PageSection(title: "By agency", symbol: "chart.bar", tone: .amber) {
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
                    .padding(14)
                    .card(14)

                    CardList {
                        ForEach(summaries) { s in
                            NavigationLink(value: Route.dataset(id, filters: ["cra": s.agency])) {
                                HStack(spacing: 8) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(s.agency).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                        Text("\(s.records) records").font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    VStack(alignment: .trailing, spacing: 2) {
                                        Text(Format.compactMoney(s.paidOut)).font(.subheadline.weight(.bold).monospacedDigit()).foregroundStyle(.primary)
                                        if s.pending > 0 { Text("+\(Format.compactMoney(s.pending)) planned").font(.caption).foregroundStyle(.secondary) }
                                    }
                                    Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                                }
                                .padding(.horizontal, 14).padding(.vertical, 10)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            if s.id != summaries.last?.id { RowDivider() }
                        }
                    }
                }

                VStack(alignment: .leading, spacing: 10) {
                    CardList {
                        RouteRow(route: .dataset(id), title: "All \(rows.count) records", symbol: "list.bullet")
                        RowDivider(inset: 50)
                        RouteRow(route: .craIncrement, title: "How much tax goes to the CRAs", symbol: "percent")
                    }
                    Text("Totals count each dollar once. Records that are parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out of totals.")
                        .font(.caption).foregroundStyle(.secondary)
                    WebLink(title: "CRA Spending on BayCounty.me", url: URL(string: "https://baycounty.me/public-money/cra-spending")).font(.subheadline)
                }
            } else if store.errors[id] == nil {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .navigationTitle("CRA Spending")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(id) }
        .refreshable { await store.load(id, force: true) }
        .navigationDestination(item: $selected) { route in
            if case .record(let d, let r) = route { RecordDetailView(datasetID: d, rowID: r) }
        }
    }
}
