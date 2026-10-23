import SwiftUI
import Charts
import BayCountyKit

/// Tax Dollars: estimate a property tax bill, see where it goes, and open each government's budget.
struct TaxCalculatorView: View {
    @Environment(AppStore.self) private var store
    @State private var districtID: String
    @State private var valueText: String
    @State private var homestead: Bool
    @State private var govID: String?
    @AppStorage("taxDistrict") private var savedDistrict = ""

    init(districtID: String? = nil, value: Double? = nil, homestead: Bool? = nil) {
        _districtID = State(initialValue: districtID ?? "")
        _valueText = State(initialValue: value.map { Format.number($0.rounded()) } ?? "250,000")
        _homestead = State(initialValue: homestead ?? true)
    }

    private var value: Double { min(Double(valueText.filter(\.isNumber)) ?? 0, 1e9) }

    var body: some View {
        Group {
            if let m = store.taxModel {
                content(m)
            } else if let e = store.appError("tax.json") {
                ContentUnavailableView("Couldn't load the calculator", systemImage: "wifi.slash", description: Text(e))
            } else {
                ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .navigationTitle("Tax Dollars")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadTax()
            if districtID.isEmpty, let m = store.taxModel {
                districtID = m.districts.contains { $0.id == savedDistrict } ? savedDistrict : (m.districts.first?.id ?? "")
            }
        }
        .onChange(of: districtID) { _, new in if !new.isEmpty { savedDistrict = new } }
    }

    @ViewBuilder private func content(_ m: TaxModel) -> some View {
        let d = m.districts.first { $0.id == districtID } ?? m.districts[0]
        let e = TaxCalculator.estimate(model: m, district: d, value: value, homestead: homestead)
        let L = m.latest
        let gname: (String) -> String = { g in g == "city" ? TaxCalculator.cityName(model: m, district: d) : m.groupName(g) }
        List {
            Section { PageIntro(path: "/public-money/tax-dollars") }

            Section("Your bill") {
                Picker("Where the property is", selection: $districtID) {
                    ForEach(m.districts) { d in Text("\(d.label) · \(Format.number(d.total[L])) mills").tag(d.id) }
                }
                HStack {
                    Text("Assessed value")
                    Spacer()
                    TextField("Value", text: $valueText)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.trailing)
                        .frame(maxWidth: 160)
                        .onChange(of: valueText) { _, new in
                            let digits = new.filter(\.isNumber)
                            let f = digits.isEmpty ? "" : Format.number(min(Double(digits) ?? 0, 1e9))
                            if f != new { valueText = f }
                        }
                }
                Toggle("Homestead exemption", isOn: $homestead)
            }

            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text(Format.money(e.total)).font(.largeTitle.weight(.semibold).monospacedDigit())
                    Text(e.total > 0 ? "about \(Format.money(e.total / 12)) a month · \(Format.number(d.total[L])) mills in all" : "Enter a value to see your estimate")
                        .font(.caption).foregroundStyle(.secondary)
                    StackBar(parts: e.byGroup.map { (gname($0.group), $0.amount, TaxColors.color($0.group)) })
                }
                .padding(.vertical, 4)
                ForEach(e.byGroup) { g in
                    LegendRow(color: TaxColors.color(g.group), label: gname(g.group), value: Format.money(g.amount),
                              detail: e.total > 0 ? "\(Int((g.amount / e.total * 100).rounded()))%" : nil)
                }
            } header: { Text("Estimate, \(m.fy[L]) rates") }

            Section("Each taxing authority") {
                ForEach(e.lines, id: \.id) { l in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Circle().fill(TaxColors.color(l.group)).frame(width: 8, height: 8)
                            Text(l.name).font(.subheadline)
                            Spacer()
                            Text(Format.money(l.amount)).monospacedDigit()
                        }
                        Text("\(Format.number(l.mills)) mills on \(Format.money(l.base))").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if d.id == "Panama City Beach" { Text("Panama City Beach has no city property tax.").font(.footnote).foregroundStyle(.secondary) }
                if d.id.hasPrefix("unincorporated") { Text("No city. The county provides fire service.").font(.footnote).foregroundStyle(.secondary) }
            }

            Section {
                Chart(e.trend) { y in
                    BarMark(x: .value("Year", y.fy), y: .value("Bill", y.total)).foregroundStyle(Brand.navy)
                }
                .chartYAxis { AxisMarks { v in AxisGridLine(); AxisValueLabel { if let d = v.as(Double.self) { Text(Format.compactMoney(d)) } } } }
                .frame(height: 180)
            } header: { Text("The same home at each year's rates") }

            Section {
                let total = m.bars.reduce(0) { $0 + $1.v }
                ForEach(m.bars, id: \.n) { b in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(b.n).font(.subheadline)
                            Spacer()
                            Text(Format.compactMoney(b.v)).monospacedDigit()
                        }
                        GeometryReader { g in
                            RoundedRectangle(cornerRadius: 3).fill(TaxColors.color(b.g))
                                .frame(width: max(3, g.size.width * b.v / (m.bars.first?.v ?? 1)))
                        }
                        .frame(height: 8)
                        Text("\(Int((b.v / max(total, 1) * 100).rounded()))% of all property tax").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            } header: { Text("Where all of Bay County's property tax goes, \(m.fy[L])") }

            Section("Each government's money") {
                ForEach(m.govs) { g in
                    NavigationLink {
                        GovBudgetView(gov: g)
                    } label: {
                        HStack {
                            Text(g.short)
                            Spacer()
                            if let t = g.total { Text(Format.compactMoney(t)).foregroundStyle(.secondary) }
                        }
                    }
                }
            }

            if let gaps = m.gaps, !gaps.isEmpty {
                Section("Gaps") { ForEach(gaps, id: \.self) { Text($0).font(.footnote) } }
            }
        }
        .scrollDismissesKeyboard(.interactively)
    }
}

/// One government's budget: general fund sources and spending, actual money in and out, and context.
struct GovBudgetView: View {
    @Environment(AppStore.self) private var store
    let gov: TaxModel.GovBudget
    @State private var year: String?

    var body: some View {
        List {
            Section {
                LabeledContent("Total budget, FY2026", value: gov.total.map { Format.compactMoney($0) } ?? "Not published online")
                LabeledContent("General fund", value: gov.gf.map { Format.compactMoney($0) } ?? "—")
                LabeledContent("Property tax levied", value: gov.id == "panama_city_beach" ? "$0" : gov.levy.map { Format.compactMoney($0) } ?? "—")
                LabeledContent("Tax rate", value: gov.mills.map { $0 == 0 ? "None" : "\(Format.number($0)) mills" } ?? "—")
                Label(gov.statusText, systemImage: gov.statusOK ? "checkmark.circle" : "exclamationmark.circle")
                    .font(.footnote).foregroundStyle(gov.statusOK ? Brand.good : Brand.amber)
            }
            if let n = gov.next {
                Section("New budget, \(n.fy)") {
                    if let t = n.total { LabeledContent("Total", value: Format.compactMoney(t)) }
                    if let g = n.gf { LabeledContent("General fund", value: Format.compactMoney(g)) }
                    if let mm = n.mills { LabeledContent("Tax rate", value: mm == 0 ? "No city property tax" : "\(Format.number(mm)) mills") }
                    Text(n.adopted == true ? "Adopted." : "Final hearing held; adoption not yet confirmed in posted minutes.").font(.footnote)
                    if let src = n.src, src.count > 1, let u = URL(string: src[1]) { WebLink(title: src[0], symbol: "doc.text", url: u) }
                }
            }
            if let mix = gov.mix {
                Section { Text("Across all funds, the schools expect \(Format.compactMoney(mix["Local"] ?? 0)) from local sources (mostly property tax), \(Format.compactMoney(mix["State"] ?? 0)) from the state and \(Format.compactMoney(mix["Federal"] ?? 0)) from the federal government.").font(.footnote) }
            }
            barSection("Where the general fund money comes from", gov.rev)
            barSection("What the general fund pays for", gov.exp)
            if let o = gov.other, !o.isEmpty { barSection("School construction, debt and other funds", o) }
            if let act = gov.act, !act.isEmpty {
                let years = act.map(\.fy)
                let cur = year.flatMap { y in years.contains(y) ? y : nil } ?? years.last { y in !(act.first { $0.fy == y }?.rev.isEmpty ?? true) } ?? years.last!
                let a = act.first { $0.fy == cur }!
                Section {
                    Picker("Year", selection: Binding(get: { cur }, set: { year = $0 })) {
                        ForEach(years, id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    if let rt = a.rt { LabeledContent("Money in", value: Format.compactMoney(rt)) }
                    if let et = a.et { LabeledContent("Money out", value: Format.compactMoney(et)) }
                    if let p = a.pop { LabeledContent("Residents", value: Format.number(p)) }
                } header: { Text("What actually came in and went out") } footer: {
                    Text("From the audited annual report, all operating funds including utilities.")
                }
                barSection("Money in, by source, \(cur)", a.rev)
                barSection("Money out, by service, \(cur)", a.exp)
            }
            if let notes = gov.notes, !notes.isEmpty { Section { ForEach(notes, id: \.self) { Text($0).font(.footnote) } } }
            if let ctx = gov.ctx, !ctx.isEmpty {
                Section("Worth knowing") {
                    ForEach(ctx, id: \.self) { c in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(c.first ?? "").font(.footnote)
                            if c.count > 1, let u = URL(string: c[1]) { Button("Source") { store.open(u) }.font(.caption).buttonStyle(.borderless) }
                        }
                    }
                }
            }
            if let src = gov.src {
                Section("Sources") {
                    ForEach(Array(src.enumerated()), id: \.offset) { _, s in
                        if s.count > 1, let t = s[0], let u = s[1].flatMap(URL.init(string:)) { WebLink(title: t, symbol: "doc.text", url: u) }
                    }
                }
            }
        }
        .navigationTitle(gov.short)
        .navigationBarTitleDisplayMode(.inline)
    }

    private static let savings = try! NSRegularExpression(pattern: "fund balance|reserve|carr(y|ied)|cash carry", options: .caseInsensitive)
    private func isSavings(_ k: String) -> Bool { Self.savings.firstMatch(in: k, range: NSRange(k.startIndex..., in: k)) != nil }

    @ViewBuilder private func barSection(_ title: String, _ obj: [String: Double]?) -> some View {
        let ent = (obj ?? [:]).filter { $0.value > 0 }
            .sorted { (isSavings($0.key) ? 1 : 0, -$0.value) < (isSavings($1.key) ? 1 : 0, -$1.value) }
        Section(title) {
            if ent.isEmpty {
                Text("This government does not post a budget online with this detail.").font(.footnote).foregroundStyle(.secondary)
            } else {
                let max = ent.map(\.value).max() ?? 1
                let total = ent.filter { !isSavings($0.key) }.reduce(0) { $0 + $1.value }
                ForEach(ent, id: \.key) { k, v in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(k).font(.subheadline)
                            Spacer()
                            Text(Format.compactMoney(v)).monospacedDigit()
                        }
                        GeometryReader { g in
                            RoundedRectangle(cornerRadius: 3).fill(isSavings(k) ? Brand.amber : Brand.blue)
                                .frame(width: Swift.max(3, g.size.width * v / max))
                        }
                        .frame(height: 7)
                        Text(isSavings(k) ? "Savings, not new money or spending" : "\(Int((v / Swift.max(total, 1) * 100).rounded()))%")
                            .font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

/// Amendment 3: the bill before and after, and what local governments would collect.
struct Amendment3View: View {
    @Environment(AppStore.self) private var store
    @State private var districtID: String
    @State private var valueText: String
    @State private var kind: Amendment3Calculator.Kind
    @AppStorage("taxDistrict") private var savedDistrict = ""

    init(districtID: String? = nil, value: Double? = nil, homestead: Bool? = nil) {
        _districtID = State(initialValue: districtID ?? "")
        _valueText = State(initialValue: value.map { Format.number($0.rounded()) } ?? "300,000")
        _kind = State(initialValue: homestead == false ? .non : .home)
    }

    private var value: Double { min(Double(valueText.filter(\.isNumber)) ?? 0, 1e9) }

    var body: some View {
        Group {
            if let m = store.amendment3 { content(m) } else if let e = store.appError("amendment3.json") {
                ContentUnavailableView("Couldn't load the calculator", systemImage: "wifi.slash", description: Text(e))
            } else { ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity) }
        }
        .navigationTitle("Amendment 3")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadAmendment3()
            if districtID.isEmpty, let m = store.amendment3 {
                districtID = m.districts.contains { $0.id == savedDistrict } ? savedDistrict : (m.districts.first?.id ?? "")
            }
        }
    }

    @ViewBuilder private func content(_ m: Amendment3Model) -> some View {
        let d = m.districts.first { $0.id == districtID } ?? m.districts[0]
        let s = Amendment3Calculator.scenarios(model: m, district: d, value: value, kind: kind)
        let today = s.first?.total ?? 0
        List {
            Section { PageIntro(path: "/public-money/amendment-3") }
            Section("Your property") {
                Picker("Where it is", selection: $districtID) { ForEach(m.districts) { Text($0.label).tag($0.id) } }
                HStack {
                    Text("Value before exemptions")
                    Spacer()
                    TextField("Value", text: $valueText).keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(maxWidth: 140)
                        .onChange(of: valueText) { _, new in
                            let digits = new.filter(\.isNumber)
                            let f = digits.isEmpty ? "" : Format.number(min(Double(digits) ?? 0, 1e9))
                            if f != new { valueText = f }
                        }
                }
                Picker("Kind", selection: $kind) { ForEach(Amendment3Calculator.Kind.allCases) { Text($0.label).tag($0) } }
                    .pickerStyle(.inline).labelsHidden()
            }
            Section {
                ForEach(Array(s.enumerated()), id: \.offset) { i, sc in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(sc.label).font(.subheadline.weight(.semibold))
                            Spacer()
                            Text(Format.money(sc.total)).font(.title3.weight(.semibold).monospacedDigit())
                        }
                        let save = today - sc.total
                        Text(i == 0 ? "per year" : save > 0.5 ? "\(Format.money(save)) less (\(Int((save / max(today, 1) * 100).rounded()))%)" : "No change")
                            .font(.caption).foregroundStyle(i > 0 && save > 0.5 ? Brand.good : .secondary)
                        StackBar(parts: [("County, city and districts", sc.total - sc.schoolTotal, Brand.blue), ("Schools", sc.schoolTotal, Brand.navy)])
                        Text("Schools taxed on \(Format.money(sc.schoolTaxable)); everything else on \(Format.money(sc.otherTaxable))").font(.caption2).foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 2)
                }
            } header: { Text("Your bill, before and after") } footer: { Text(Amendment3Calculator.note(kind: kind, scenarios: s)) }

            Section {
                let first = m.govs.first?.imp[1] ?? 1
                ForEach(m.govs) { g in
                    VStack(alignment: .leading, spacing: 3) {
                        HStack {
                            Text(g.n).font(.subheadline)
                            Spacer()
                            Text(g.imp[1] > 0 ? "−" + Format.compactMoney(g.imp[1]) : "$0").monospacedDigit()
                        }
                        GeometryReader { geo in RoundedRectangle(cornerRadius: 3).fill(Brand.blue).frame(width: g.imp[1] > 0 ? max(3, geo.size.width * g.imp[1] / first) : 0) }
                            .frame(height: 7)
                        Text(g.levy > 0 ? "\(Int((g.imp[1] / g.levy * 100).rounded()))% of its FY2026 property tax levy" : "No property tax levy").font(.caption2).foregroundStyle(.secondary)
                    }
                }
            } header: { Text("What local governments would collect less, FY2029") } footer: {
                Text("State Revenue Estimating Conference estimates for the first full year. Schools lose nothing, because school taxes aren't covered.")
            }
            Section { WebLink(title: "Officials' statements and the arguments, on BayCounty.me", symbol: "safari", url: URL(string: "https://baycounty.me/public-money/amendment-3")) }
        }
        .scrollDismissesKeyboard(.interactively)
    }
}
