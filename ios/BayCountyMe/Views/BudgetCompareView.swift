import SwiftUI
import BayCountyKit

/// Budget compare: one government's budget in two fiscal years, line by line (/public-money/budget-compare).
/// Reads the budget-years dataset; the comparison is BudgetCompare, the same rules as /api/v1/budget-compare.
struct BudgetCompareView: View {
    @Environment(AppStore.self) private var store
    @State private var govID: String
    @State private var basis: BudgetCompare.Basis = .adopted
    @State private var from: Int?
    @State private var to: Int?
    @State private var expanded: Set<String> = []
    private let id = "budget-years"

    init(govID: String? = nil) { _govID = State(initialValue: govID ?? "county") }

    private var rows: [Row] { store.rows[id] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Where it goes", title: "Budget compare",
                     subtitle: "Pick a government and two years to see what grew, what shrank and what's new.",
                     symbol: "arrow.left.arrow.right", tone: .blue)
            if rows.isEmpty {
                if let e = store.errors[id] {
                    ContentUnavailableView("Couldn't load budgets", systemImage: "wifi.slash", description: Text(e))
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                pickers
                if let r = BudgetCompare.compare(rows, gov: govID, basis: basis, from: from, to: to) {
                    results(r)
                } else {
                    Text("There aren't two years on record to compare for this government yet.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
            }
            FreshnessNote(key: id)
        }
        .navigationTitle("Budget compare")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(id) }
        .refreshable { await store.load(id, force: true) }
    }

    // MARK: Pickers

    private var pickers: some View {
        let govs = BudgetCompare.governments(rows, basis: basis)
        let years = BudgetCompare.years(rows, gov: govID, basis: basis)
        let current = BudgetCompare.compare(rows, gov: govID, basis: basis, from: from, to: to)
        return VStack(alignment: .leading, spacing: 12) {
            ChipRow(chips: govs.map { (id: $0, label: Governments.names[$0].map(shortName) ?? $0) }, selected: govID) { g in
                govID = g; from = nil; to = nil; expanded = []
            }
            ChipRow(chips: [(id: BudgetCompare.Basis.adopted, label: "Adopted budgets"), (id: .actual, label: "Audited actuals")],
                    selected: basis) { b in basis = b; from = nil; to = nil; expanded = [] }
            HStack(spacing: 10) {
                yearMenu("From", years: years.filter { $0 != current?.to }, value: current?.from) { from = $0 }
                Image(systemName: "arrow.right").foregroundStyle(.secondary).accessibilityHidden(true)
                yearMenu("To", years: years.filter { $0 != current?.from }, value: current?.to) { to = $0 }
            }
        }
    }

    private func shortName(_ n: String) -> String { n.replacingOccurrences(of: "Bay District ", with: "") }

    private func yearMenu(_ label: String, years: [Int], value: Int?, pick: @escaping (Int) -> Void) -> some View {
        Menu {
            ForEach(years.reversed(), id: \.self) { y in Button("FY\(String(y))") { pick(y) } }
        } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.caption).foregroundStyle(.secondary)
                HStack(spacing: 4) {
                    Text(value.map { "FY\(String($0))" } ?? "Pick").font(.headline.monospacedDigit()).foregroundStyle(.primary)
                    Image(systemName: "chevron.up.chevron.down").font(.caption2).foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 14)
            .frame(maxWidth: .infinity, minHeight: 56, alignment: .leading)
            .card(14)
        }
        .accessibilityLabel("\(label) year, \(value.map { "fiscal \(String($0))" } ?? "not picked")")
    }

    // MARK: Results

    @ViewBuilder private func results(_ r: BudgetCompare.Result) -> some View {
        StatGrid {
            ForEach(r.totals.prefix(4)) { t in
                KPICard(title: t.name, value: shortMoney(t.to), caption: changeText(t, r), symbol: "chart.bar", tone: (t.change >= 0) ? .teal : .salmon)
            }
        }
        if r.biggestIncrease != nil || r.biggestDecrease != nil {
            CardList {
                if let up = r.biggestIncrease {
                    FactRow(label: "Grew the most", value: "+" + Format.compactMoney(up.change), detail: up.name)
                }
                if r.biggestIncrease != nil && r.biggestDecrease != nil { RowDivider() }
                if let down = r.biggestDecrease {
                    FactRow(label: "Shrank the most", value: "−" + Format.compactMoney(abs(down.change)), detail: down.name)
                }
            }
        }
        if !r.notes.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                ForEach(r.notes, id: \.self) { n in
                    Label(n, systemImage: "info.circle").font(.footnote).foregroundStyle(.secondary)
                }
            }
        }
        if r.history.count >= 2 {
            YearBars(title: "Total by year", points: r.history.map { (label: "'" + String(String($0.fiscalYear).suffix(2)), value: $0.total) })
        }
        ForEach(r.sections.filter { !$0.lines.isEmpty }) { s in
            PageSection(title: s.title, symbol: symbol(s.key), tone: tone(s.key), caption: "FY\(String(r.from)) to FY\(String(r.to)), biggest changes first") {
                let open = expanded.contains(s.key)
                let shown = open ? s.lines : Array(s.lines.prefix(10))
                CardList {
                    ForEach(shown) { l in
                        lineRow(l, r)
                        if l.id != shown.last?.id { RowDivider() }
                    }
                    if s.lines.count > 10 {
                        RowDivider()
                        Button(open ? "Show fewer" : "Show all \(s.lines.count)") {
                            if open { expanded.remove(s.key) } else { expanded.insert(s.key) }
                        }
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 44)
                    }
                }
            }
        }
        VStack(alignment: .leading, spacing: 6) {
            if let u = r.sources.from.first { SourceLink(title: "FY\(String(r.from)) source", url: u) }
            if let u = r.sources.to.first { SourceLink(title: "FY\(String(r.to)) source", url: u) }
            WebLink(title: "Budget compare on BayCounty.me", url: URL(string: "https://baycounty.me/public-money/budget-compare"))
                .font(.subheadline)
        }
    }

    private func lineRow(_ l: BudgetCompare.Line, _ r: BudgetCompare.Result) -> some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(l.name).font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                Text("\(shortMoney(l.from)) → \(shortMoney(l.to))").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                if l.status != "both" { Badge(text: l.status == "added" ? "New in FY\(String(r.to))" : "Not in FY\(String(r.to))", color: Brand.amber) }
            }
            Spacer(minLength: 6)
            VStack(alignment: .trailing, spacing: 2) {
                Text((l.change >= 0 ? "+" : "−") + Format.compactMoney(abs(l.change)))
                    .font(.subheadline.weight(.bold).monospacedDigit())
                    .foregroundStyle(l.change >= 0 ? Brand.good : Brand.salmon)
                if let p = l.pct { Text("\(p >= 0 ? "+" : "")\(Format.number(p))%").font(.caption.monospacedDigit()).foregroundStyle(.secondary) }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .accessibilityElement(children: .combine)
    }

    private func changeText(_ l: BudgetCompare.Line, _ r: BudgetCompare.Result) -> String {
        guard l.from != nil else { return "FY\(String(r.to))" }
        let sign = l.change >= 0 ? "+" : "−"
        return "\(sign)\(Format.compactMoney(abs(l.change))) from FY\(String(r.from))" + (l.pct.map { " (\($0 >= 0 ? "+" : "")\(Format.number($0))%)" } ?? "")
    }

    private func symbol(_ key: String) -> String {
        ["department": "building.columns", "fund": "tray.2", "service": "square.grid.2x2", "spending": "arrow.up.right", "revenue": "arrow.down.left"][key] ?? "list.bullet"
    }

    private func tone(_ key: String) -> Tone {
        ["department": .blue, "fund": .teal, "service": .amber, "spending": .salmon, "revenue": .teal][key] ?? .blue
    }
}
