import SwiftUI
import BayCountyKit

/// The Home tab's tax bill tile, opened: one short screen with the yearly estimate, who gets it, how it changed from
/// last year, and where to go deeper (every line, fees, exemptions, rates). Same estimate as the tax calculator.
struct TaxBillView: View {
    @Environment(AppStore.self) private var store
    @AppStorage("taxDistrict") private var savedDistrict = ""
    var districtID: String?

    var body: some View {
        ScrollView {
            if let m = store.taxModel, let d = m.districts.first(where: { $0.id == (districtID ?? savedDistrict) }) ?? m.districts.first {
                content(m, d)
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 80)
            }
        }
        .background(Brand.canvas)
        .navigationTitle("Your tax bill")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadTax() }
    }

    private func content(_ m: TaxModel, _ d: TaxModel.District) -> some View {
        let value = HomeTiles.sampleValue
        let e = TaxCalculator.estimate(model: m, district: d, value: value, homestead: true)
        let name: (String) -> String = { g in g == "city" ? TaxCalculator.cityName(model: m, district: d) : m.groupName(g) }
        let change: Double? = e.trend.count >= 2 ? e.trend[e.trend.count - 1].total - e.trend[e.trend.count - 2].total : nil
        return VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Your tax bill · \(e.trend.last?.fy ?? "")".uppercased())
                    .font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(.secondary)
                Text(Format.money(e.total)).font(.system(size: 40, weight: .semibold)).monospacedDigit()
                Text("Estimate for a \(Format.compactMoney(value)) home with homestead in \(d.label).")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            .accessibilityElement(children: .combine)

            VStack(alignment: .leading, spacing: 14) {
                StackBar(parts: e.byGroup.map { (name($0.group), $0.amount, TaxColors.color($0.group)) })
                ForEach(e.byGroup) { g in
                    HStack(spacing: 10) {
                        RoundedRectangle(cornerRadius: 3).fill(TaxColors.color(g.group)).frame(width: 10, height: 10)
                        Text(name(g.group)).font(.body)
                        Spacer()
                        Text(Format.money(g.amount)).font(.body.weight(.semibold)).monospacedDigit()
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(16)
            .card(16)

            if let change, abs(change) >= 1 {
                Label {
                    Text("\(change > 0 ? "Up" : "Down") \(Format.money(abs(change))) from last year for the same home.")
                } icon: {
                    Image(systemName: change > 0 ? "arrow.up.right" : "arrow.down.right")
                }
                .font(.subheadline)
                .foregroundStyle(.primary)
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Brand.good.opacity(0.12), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }

            VStack(alignment: .leading, spacing: 10) {
                EyebrowHeader(text: "Go deeper")
                CardList {
                    if let home = store.home {
                        RouteRow(route: .address(home), title: "Exact estimate for your home", detail: home.display, symbol: "house")
                        RowDivider(inset: 50)
                    }
                    RouteRow(route: .taxCalculator(districtID: d.id, value: value, homestead: true), title: "Every line, any home value", symbol: "percent")
                    RowDivider(inset: 50)
                    RouteRow(route: .dataset("fees-assessments"), title: "Fees on your bill", symbol: "doc.plaintext")
                    RowDivider(inset: 50)
                    RouteRow(route: .dataset("property-tax-exemptions"), title: "Exemptions you may qualify for", symbol: "checkmark.shield")
                    RowDivider(inset: 50)
                    RouteRow(route: .dataset("property-tax-rates"), title: "Who set these rates", detail: "Every taxing authority, by year", symbol: "chart.line.uptrend.xyaxis")
                }
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}
