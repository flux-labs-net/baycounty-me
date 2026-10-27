import SwiftUI
import Charts
import BayCountyKit

/// Hurricane prep (/hurricane-prep): what to do before the season, sandbags, generator safety, when a storm is coming
/// and after it; FEMA housing aid and flood insurance money by ZIP code after past storms; every disaster declaration
/// since 2016. Reads the hurricane-prep, rebuild-money and disaster-declarations datasets.
struct HurricanePrepView: View {
    @Environment(AppStore.self) private var store
    @State private var storm: Emergency.Storm = .all
    @State private var openTopic: String? = "Before the season"
    @State private var showAllZips = false

    private var steps: [Row] { store.rows["hurricane-prep"] ?? [] }
    private var money: [Row] { store.rows["rebuild-money"] ?? [] }
    private var declarations: [Row] { Emergency.declarations(store.rows["disaster-declarations"] ?? []) }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Take part · Stay safe", title: "Hurricane prep",
                     subtitle: "A plan and a kit, sandbags, generator safety, what to do when a storm is coming and after it, and the FEMA money past storms brought each part of the county.",
                     symbol: "hurricane", tone: .blue)
            if steps.isEmpty {
                if Emergency.prepDatasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load hurricane prep", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                CardList {
                    RouteRow(route: .emergency, title: "Find my evacuation zone", detail: "And what's happening now", symbol: "map")
                }
                stepsSection
                rebuildSection
                declarationsSection
            }
            FreshnessNote(key: "rebuild-money")
        }
        .navigationTitle("Hurricane prep")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Emergency.prepDatasets) }
        .refreshable { for i in Emergency.prepDatasets { await store.load(i, force: true) } }
    }

    private var stepsSection: some View {
        PageSection(title: "What to do", symbol: "checklist", tone: .teal, caption: "From Bay County, Ready.gov, the CDC, the Weather Service and FEMA. Each step links its source.") {
            VStack(spacing: 10) {
                ForEach(Emergency.prepTopics(steps), id: \.topic) { t in
                    DisclosureGroup(isExpanded: Binding(get: { openTopic == t.topic }, set: { openTopic = $0 ? t.topic : nil })) {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(t.rows) { s in
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(s.string("step") ?? "").font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                                    Text(s.string("text") ?? "").font(.subheadline).fixedSize(horizontal: false, vertical: true)
                                    if let u = s.url("source_url") {
                                        Button("Source: \(s.string("source") ?? "link")") { store.open(u) }.font(.caption)
                                    }
                                }
                            }
                        }
                        .padding(.top, 8)
                    } label: {
                        Label(t.topic, systemImage: Emergency.prepSymbol(t.topic)).font(.headline)
                    }
                    .padding(14).card(14)
                }
            }
        }
    }

    private var rebuildSection: some View {
        let zips = Emergency.rebuild(money, storm: storm)
        let shown = showAllZips ? zips : Array(zips.prefix(8))
        let fema = zips.map(\.femaAid).reduce(0, +), flood = zips.map(\.floodPaid).reduce(0, +)
        return PageSection(title: "Rebuild money by neighborhood", symbol: "house.and.flag", tone: .amber,
                           caption: "FEMA housing aid (repairs and rent) and flood insurance claims paid, by ZIP code. Totals only; no household is named.") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: Emergency.Storm.allCases.map { (id: $0, label: $0.label) }, selected: storm) { storm = $0 }
                StatGrid {
                    KPICard(title: "FEMA housing aid", value: Format.compactMoney(fema), caption: "\(zips.map(\.households).reduce(0, +).formatted()) households applied", symbol: "house", tone: .blue)
                    KPICard(title: "Flood insurance paid", value: Format.compactMoney(flood), caption: "\(zips.map(\.claims).reduce(0, +).formatted()) claims", symbol: "drop", tone: .amber)
                }
                Chart {
                    ForEach(shown) { z in
                        BarMark(x: .value("Dollars", z.femaAid), y: .value("ZIP", z.label))
                            .foregroundStyle(by: .value("Program", "FEMA housing aid"))
                        BarMark(x: .value("Dollars", z.floodPaid), y: .value("ZIP", z.label))
                            .foregroundStyle(by: .value("Program", "Flood insurance"))
                    }
                }
                .chartForegroundStyleScale(["FEMA housing aid": Color(red: 0.25, green: 0.44, blue: 0.69), "Flood insurance": Color(red: 0.85, green: 0.56, blue: 0.16)])
                .chartXAxis { AxisMarks { v in AxisGridLine(); AxisValueLabel { if let d = v.as(Double.self) { Text(Format.compactMoney(d)) } } } }
                .chartLegend(position: .top, alignment: .leading)
                .frame(height: CGFloat(max(shown.count, 1)) * 34 + 50)
                .padding(14).card(14)
                .accessibilityLabel("Rebuild money by ZIP code; the list below has every figure")
                CardList {
                    ForEach(shown) { z in
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(z.label).font(.subheadline.weight(.semibold).monospacedDigit())
                                Text(z.name).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer()
                            VStack(alignment: .trailing, spacing: 2) {
                                Text(Format.compactMoney(z.total)).font(.subheadline.weight(.semibold).monospacedDigit())
                                Text("\(z.households) applied · \(z.claims) claims").font(.caption2).foregroundStyle(.secondary)
                            }
                        }
                        .padding(.horizontal, 14).padding(.vertical, 9)
                        if z.id != shown.last?.id { RowDivider() }
                    }
                }
                if zips.count > 8 {
                    Button(showAllZips ? "Show fewer" : "Show all \(zips.count) ZIP codes") { showAllZips.toggle() }.font(.subheadline)
                }
            }
        }
    }

    private var declarationsSection: some View {
        PageSection(title: "Disaster declarations", symbol: "doc.text", tone: .salmon,
                    caption: "\(declarations.count) since 2016. A major disaster opens FEMA aid; an emergency pays for evacuations and shelters.") {
            CardList {
                ForEach(declarations) { d in
                    Button { store.open(d.url("source_url")) } label: {
                        HStack(alignment: .top, spacing: 12) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(d.string("title") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                Text([d.string("kind"), d.string("declared"), d.bool("individual_aid") == true ? "aid to households" : nil].compactMap { $0 }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                            Image(systemName: "arrow.up.right").font(.caption).foregroundStyle(.tertiary)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if d.id != declarations.last?.id { RowDivider() }
                }
            }
        }
    }
}
