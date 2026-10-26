import SwiftUI
import Charts
import BayCountyKit

/// CRA tax increment: how much property tax goes to the redevelopment agencies (/public-money/cra-tax-increment).
/// Reads the cra-agencies, cra-tax-increment and cra-increment-checks datasets.
struct CRAIncrementView: View {
    @Environment(AppStore.self) private var store
    @State private var scenario: CRAIncrement.Scenario = .mid
    @State private var payer: CRAIncrement.Payer = .all
    private let ids = ["cra-agencies", "cra-tax-increment", "cra-increment-checks"]

    private var agencies: [Row] { store.rows["cra-agencies"] ?? [] }
    private var years: [Row] { store.rows["cra-tax-increment"] ?? [] }
    private var checks: [Row] { store.rows["cra-increment-checks"] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Where it goes", title: "CRA tax increment",
                     subtitle: "Property tax on growth inside each redevelopment district goes to its CRA instead of the county or city budget.",
                     symbol: "percent", tone: .amber)
            if let h = CRAIncrement.headline(agencies: agencies, years: years) {
                StatGrid {
                    KPICard(title: "Tax increment, FY\(String(h.lastYear))", value: Format.compactMoney(h.total),
                            caption: "All \(h.agencies) CRAs. \(pct(h.frontBeachRoad, h.total))% is Front Beach Road", symbol: "percent", tone: .amber)
                    KPICard(title: "Paid by Bay County, FY\(String(h.lastYear))", value: Format.compactMoney(h.county),
                            caption: "\(pct(h.county, h.total))% of the total; the cities paid \(Format.compactMoney(h.total - h.county))", symbol: "building.columns", tone: .blue)
                    KPICard(title: "Paid on record, FY\(String(h.firstYear)) to FY\(String(h.lastYear))", value: Format.compactMoney(h.paidOnRecord),
                            caption: "\(Format.compactMoney(h.countyOnRecord)) from the county. Early years are missing for several CRAs", symbol: "clock", tone: .teal)
                    KPICard(title: "Still to come, to each sunset", value: "\(Format.compactMoney(h.toComeLow)) to \(Format.compactMoney(h.toComeHigh))",
                            caption: "Low to high growth", symbol: "chart.line.uptrend.xyaxis", tone: .salmon)
                }
                simpleVersion
                chart(h)
                agencyList
                if !checks.isEmpty { checksSection }
            } else if ids.contains(where: { store.errors[$0] != nil }) {
                ContentUnavailableView("Couldn't load the CRA figures", systemImage: "wifi.slash")
            } else {
                ProgressView().frame(maxWidth: .infinity, minHeight: 160)
            }
            VStack(alignment: .leading, spacing: 8) {
                RouteRowLink(route: .cra, title: "What the CRAs spent it on", symbol: "building.2")
                WebLink(title: "CRA tax increment on BayCounty.me", url: URL(string: "https://baycounty.me/public-money/cra-tax-increment"))
                    .font(.subheadline)
            }
            FreshnessNote(key: "cra-tax-increment")
        }
        .navigationTitle("CRA tax increment")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(ids) }
        .refreshable { for i in ids { await store.load(i, force: true) } }
    }

    private func pct(_ a: Double, _ b: Double) -> Int { b > 0 ? Int((a / b * 100).rounded()) : 0 }

    private var simpleVersion: some View {
        PageSection(title: "The simple version", symbol: "lightbulb", tone: .amber) {
            VStack(alignment: .leading, spacing: 10) {
                Text("**A CRA starts with a base value.** The county and the city keep collecting tax on the value the district had in its base year.")
                Text("**Growth above the base is the increment.** Each year they pay 95% of what their tax rate raises on that growth into the CRA's trust fund. The CRA can spend it only inside the district.")
                Text("**So the money isn't gone, it's set aside.** Without a CRA the county and city could spend it anywhere. Schools and the water management district pay nothing.")
            }
            .font(.subheadline)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card(14)
        }
    }

    private func chart(_ h: CRAIncrement.Headline) -> some View {
        let series = CRAIncrement.byYear(years, scenario: scenario, payer: payer)
        return PageSection(title: "Tax increment by year", symbol: "chart.bar", tone: .blue,
                           caption: "Reported through FY\(String(h.lastYear)), then projected to each CRA's sunset. Front Beach Road is held to its $30M yearly cap.") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: CRAIncrement.Scenario.allCases.map { (id: $0, label: $0.label) }, selected: scenario) { scenario = $0 }
                ChipRow(chips: CRAIncrement.Payer.allCases.map { (id: $0, label: $0.label) }, selected: payer) { payer = $0 }
                // Years are categories so each bar gets an even slot (a number axis started at year 0
                // and squeezed every bar into one sliver). Only round years are labelled.
                let ticks = Set(ChartTicks.yearTicks(series.map(\.fiscalYear)).map(String.init))
                Chart(series) { y in
                    BarMark(x: .value("Year", String(y.fiscalYear)), y: .value("Amount", y.amount), width: .ratio(0.72))
                        .foregroundStyle(y.projected ? Brand.amber : Brand.navy)
                        .cornerRadius(2)
                }
                .chartXAxis {
                    AxisMarks(values: series.map { String($0.fiscalYear) }.filter { ticks.contains($0) }) { v in
                        AxisValueLabel(collisionResolution: .disabled) { if let s = v.as(String.self) { Text(s).font(.caption2) } }
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .trailing, values: .automatic(desiredCount: 4)) { v in
                        AxisGridLine().foregroundStyle(Brand.hairline)
                        AxisValueLabel { if let d = v.as(Double.self) { Text(Format.compactMoney(d)).font(.caption2) } }
                    }
                }
                .frame(height: 200)
                .accessibilityLabel("Tax increment by year")
                .accessibilityValue(series.filter { $0.fiscalYear % 5 == 0 }.map { "FY\($0.fiscalYear) \(Format.compactMoney($0.amount))" }.joined(separator: ", "))
                HStack(spacing: 14) {
                    HStack(spacing: 5) { RoundedRectangle(cornerRadius: 2).fill(Brand.navy).frame(width: 10, height: 10); Text("Reported") }
                    HStack(spacing: 5) { RoundedRectangle(cornerRadius: 2).fill(Brand.amber).frame(width: 10, height: 10); Text("Projected") }
                }
                .font(.caption).foregroundStyle(.secondary)
            }
            .padding(14)
            .card(14)
        }
        .id("chart")
    }

    private var agencyList: some View {
        let sorted = agencies.sorted { ($0.number("increment_fy2025") ?? 0) > ($1.number("increment_fy2025") ?? 0) }
        return PageSection(title: "Each CRA at a glance", symbol: "building.2", tone: .teal, caption: "FY2025, the last year reported for all seven") {
            CardList {
                ForEach(sorted) { a in
                    let share = Int(((a.number("county_share_fy2025") ?? 0) * 100).rounded())
                    VStack(alignment: .leading, spacing: 6) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(a.string("cra") ?? "CRA").font(.subheadline.weight(.semibold))
                            Spacer(minLength: 6)
                            Text(shortMoney(a.number("increment_fy2025"))).font(.subheadline.weight(.bold).monospacedDigit())
                        }
                        Text([a.string("city"), a.string("base_year").map { "base year \($0)" }, "\(share)% paid by the county"]
                            .compactMap { $0 }.joined(separator: " · "))
                            .font(.caption).foregroundStyle(.secondary)
                        Text("Paid on record \(shortMoney(a.number("paid_on_record"))) · still to come \(shortMoney(CRAIncrement.toCome(a, scenario))) by FY\(a.number("sunset_fy").map { String(Int($0)) } ?? "?")\(a.bool("sunset_assumed") == true ? " (assumed)" : "")")
                            .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.horizontal, 14).padding(.vertical, 11)
                    .accessibilityElement(children: .combine)
                    if a.id != sorted.last?.id { RowDivider() }
                }
            }
        }
    }

    private var checksSection: some View {
        PageSection(title: "Checked against official figures", symbol: "checkmark.seal", tone: .teal) {
            CardList {
                ForEach(checks) { c in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(c.string("figure") ?? "").font(.subheadline).fixedSize(horizontal: false, vertical: true)
                        Text("Official \(shortMoney(c.number("official_figure"))) · our estimate \(shortMoney(c.number("estimate")))\(c.number("difference_pct").map { " · \(Format.number($0))% apart" } ?? "")")
                            .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        SourceLink(url: c.url("source_url"))
                    }
                    .padding(.horizontal, 14).padding(.vertical, 11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if c.id != checks.last?.id { RowDivider() }
                }
            }
        }
    }
}

/// A RouteRow on its own card.
struct RouteRowLink: View {
    let route: Route
    let title: String
    var symbol: String? = nil
    var body: some View { CardList { RouteRow(route: route, title: title, symbol: symbol) } }
}
