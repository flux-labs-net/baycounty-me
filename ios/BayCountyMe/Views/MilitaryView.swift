import SwiftUI
import Charts
import BayCountyKit

/// Military and the bases (/military): Tyndall AFB and NSA Panama City, the latest news from their units, and
/// federal contracts to Bay County companies. Reads military-installations, military-news and federal-contract-years.
struct MilitaryView: View {
    @Environment(AppStore.self) private var store
    @State private var base: String = ""
    @State private var showAllNews = false
    @State private var showAllCompanies = false

    private var bases: [Row] { store.rows["military-installations"] ?? [] }
    private var news: [Row] { store.rows["military-news"] ?? [] }
    private var years: [Row] { store.rows["federal-contract-years"] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "People · Bases and military", title: "Military and the bases",
                     subtitle: "What Tyndall Air Force Base and NSA Panama City do, the latest news from their units, and federal contracts to Bay County companies.",
                     symbol: "shield", tone: .blue)
            if bases.isEmpty {
                if Military.datasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load the bases", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis(bases)
                ForEach(bases) { baseCard($0) }
                newsSection
                contractsSection
                companiesSection
            }
            CardList {
                WebRow(title: "Military on BayCounty.me", detail: "Biggest contracts and every agency", symbol: "safari",
                       url: URL(string: "https://baycounty.me/military"))
                RowDivider(inset: 50)
                RouteRow(route: .dataset("federal-contracts"), title: "Every federal contract", symbol: "doc.text")
            }
            FreshnessNote(key: "military-news")
        }
        .navigationTitle("Military")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Military.datasets) }
        .refreshable { for i in Military.datasets { await store.load(i, force: true) } }
    }

    private func kpis(_ bases: [Row]) -> some View {
        let latest = Military.stories(news).first?.string("published")
        return StatGrid {
            KPICard(title: "Bases", value: "\(bases.count)", caption: bases.compactMap { $0.string("short_name") }.joined(separator: " and "),
                    symbol: "shield", tone: .salmon)
            KPICard(title: "News stories", value: "\(news.count)", caption: latest.map { "Latest \(Military.dateLabel($0))" } ?? "From the units on each base",
                    symbol: "newspaper", tone: .blue)
            KPICard(title: "Federal contracts", value: Format.compactMoney(Military.total(years)),
                    caption: "To \(Military.companies(years).count) Bay County companies since 2016", symbol: "dollarsign.circle", tone: .teal)
            KPICard(title: "From the Defense Department", value: "\(Military.defenseShare(years))%",
                    caption: "Most of the rest is Coast Guard", symbol: "shield", tone: .amber)
        }
    }

    private func baseCard(_ b: Row) -> some View {
        let tone: Tone = b.string("branch") == "Navy" ? .teal : .blue
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                ToneIcon(symbol: "shield", tone: tone, size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(b.string("name") ?? "").font(.headline).fixedSize(horizontal: false, vertical: true)
                    Text([b.string("branch"), b.string("host_unit")].compactMap { $0 }.joined(separator: " · "))
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            Text(b.string("mission") ?? "").font(.subheadline).fixedSize(horizontal: false, vertical: true)
            if let s = b.string("storm") { Text(s).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            if let c = b.string("commander") {
                Text("**In command:** \(c), \(b.string("commander_title") ?? ""), since \(Military.dateLabel(b.string("commander_since")))")
                    .font(.footnote).fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 8) {
                if let o = b.number("opened") { fact("Opened", String(Int(o))) }
                if let a = b.number("acres") { fact("Acres", Format.number(a)) }
                if let p = b.number("personnel") { fact("People", "About \(Format.number(p))") }
                fact("Stories", "\(Int(b.number("stories") ?? 0))")
            }
            CardList {
                WebRow(title: "Base website", symbol: "globe", url: b.url("website"))
                RowDivider(inset: 50)
                WebRow(title: "All its news on DVIDS", symbol: "newspaper", url: b.url("dvids_url"))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(18)
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption2).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.8)
            Text(value).font(.subheadline.weight(.semibold).monospacedDigit()).lineLimit(1).minimumScaleFactor(0.8)
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Brand.hairline.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private var newsSection: some View {
        let chips = [(id: "", label: "Both bases")] + bases.map { (id: $0.string("installation_id") ?? "", label: $0.string("short_name") ?? "") }
        let list = Military.stories(news, base: base)
        let shown = showAllNews ? list : Array(list.prefix(6))
        return PageSection(title: "Latest news", symbol: "newspaper", tone: .blue, caption: "Stories by each unit's public affairs office. They open on DVIDS.") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: chips, selected: base) { base = $0; showAllNews = false }
                CardList {
                    ForEach(shown) { s in
                        Button { if let u = s.url("url") { store.open(u) } } label: {
                            TextRow(title: s.string("title") ?? "",
                                    detail: [Military.dateLabel(s.string("published")), s.string("unit")].compactMap { $0 }.joined(separator: " · "),
                                    badge: (s.string("installation") ?? "", s.string("installation_id") == "nsa-panama-city" ? Brand.good : Brand.navy))
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint("Opens the story")
                        if s.id != shown.last?.id { RowDivider() }
                    }
                }
                if !showAllNews && list.count > shown.count {
                    Button("Show \(list.count - shown.count) more stories") { showAllNews = true }
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .card(14)
                }
            }
        }
    }

    private var contractsSection: some View {
        let series = Military.byYear(years)
        return PageSection(title: "Federal contracts by year", symbol: "chart.bar", tone: .teal,
                           caption: "Money obligated to companies with a business address in Bay County. The work can happen anywhere.") {
            VStack(alignment: .leading, spacing: 10) {
                Chart {
                    ForEach(series, id: \.year) { y in
                        BarMark(x: .value("Year", String(y.year)), y: .value("Amount", max(y.defense, 0)), width: .ratio(0.7))
                            .foregroundStyle(by: .value("Agency", "Defense"))
                        BarMark(x: .value("Year", String(y.year)), y: .value("Amount", max(y.other, 0)), width: .ratio(0.7))
                            .foregroundStyle(by: .value("Agency", "Other agencies"))
                    }
                }
                .chartForegroundStyleScale(["Defense": Brand.navy, "Other agencies": Brand.good])
                .chartXAxis {
                    AxisMarks(values: series.map { String($0.year) }.filter { (Int($0) ?? 0) % 2 == 0 }) { v in
                        AxisValueLabel { if let s = v.as(String.self) { Text(s).font(.caption2) } }
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .trailing, values: .automatic(desiredCount: 4)) { v in
                        AxisGridLine().foregroundStyle(Brand.hairline)
                        AxisValueLabel { if let d = v.as(Double.self) { Text(Format.compactMoney(d)).font(.caption2) } }
                    }
                }
                .frame(height: 200)
                .accessibilityLabel("Federal contract money by year")
                .accessibilityValue(series.map { "\($0.year) \(Format.compactMoney($0.defense + $0.other))" }.joined(separator: ", "))
            }
            .padding(14)
            .card(14)
        }
    }

    private var companiesSection: some View {
        let list = Military.companies(years)
        let shown = showAllCompanies ? Array(list.prefix(100)) : Array(list.prefix(10))
        return PageSection(title: "Local companies", symbol: "building.2", tone: .amber, caption: "Since 2016, biggest first. Tap a company for its profile.") {
            VStack(alignment: .leading, spacing: 12) {
                CardList {
                    ForEach(shown) { c in
                        Button { if let u = Military.profileURL(c.url) { store.open(u) } } label: {
                            TextRow(title: c.name, detail: "\(c.topAgency) · \(c.defenseShare)% defense", value: Format.compactMoney(c.total))
                        }
                        .buttonStyle(.plain)
                        if c.id != shown.last?.id { RowDivider() }
                    }
                }
                if !showAllCompanies && list.count > shown.count {
                    Button("Show more companies") { showAllCompanies = true }
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .card(14)
                }
            }
        }
    }
}
