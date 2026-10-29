import SwiftUI
import BayCountyKit

/// Where records overlap (/connections/overlaps): the same company, organization or person in more than one public
/// record. Headline numbers and the top few of each overlap (from the overlap datasets), each opening its full list,
/// then the live parts from /api/v1/overlaps. A row is two public records side by side, not a finding.
struct OverlapsView: View {
    @Environment(AppStore.self) private var store
    @State private var live: [String: [Row]]?
    @State private var liveFailed = false

    private var all: [String: [Row]] { Dictionary(uniqueKeysWithValues: Overlaps.datasets.map { ($0, store.rows[$0] ?? []) }) }
    private var loaded: Bool { Overlaps.datasets.contains { !(store.rows[$0] ?? []).isEmpty } }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Your government · Connections", title: "Where the records overlap",
                     subtitle: "The same company, organization or person often shows up in more than one public record: a campaign report, the minutes, an agenda, a check register, a state business filing. This is the summary.",
                     symbol: "point.3.connected.trianglepath.dotted", tone: .blue)
            if !loaded {
                if let e = Overlaps.datasets.lazy.compactMap({ store.errors[$0] }).first {
                    ContentUnavailableView("Couldn't load the overlaps", systemImage: "wifi.slash", description: Text(e))
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                explainer
                PageSection(title: "Every overlap", symbol: "square.grid.2x2", tone: .teal, caption: "The top few of each; tap for the full list") {
                    VStack(spacing: 10) { ForEach(Overlaps.cards(all)) { card($0) } }
                }
                .id("chart")
                liveSection
            }
            Text("Names in votes and agendas are matched to profiles by name. Gifts come from campaign reports filed with the Supervisor of Elections since 2016. Officials, candidates and people who run a registered business are named; individual donors never are.")
                .font(.footnote).foregroundStyle(.secondary)
            FreshnessNote(key: "donor-votes")
        }
        .navigationTitle("Overlaps")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.load(Overlaps.datasets)
            await loadLive()
        }
        .refreshable {
            for i in Overlaps.datasets { await store.load(i, force: true) }
            await loadLive()
        }
    }

    private func loadLive() async {
        do { live = try Overlaps.decodeLive(try await store.client.get(Overlaps.livePath).data); liveFailed = false } catch { liveFailed = true }
    }

    private var kpis: some View {
        let h = Overlaps.headline(all)
        return StatGrid {
            KPICard(title: "Votes naming a donor", value: Format.number(Double(h.donorVotes)), caption: "\(h.pairs) official and company pairs since 2016", symbol: "link", tone: .blue)
            KPICard(title: "Votes naming a company or group", value: Format.number(Double(h.mentionVotes)), caption: "\(h.mentionEntities) companies and organizations named", symbol: "text.magnifyingglass", tone: .teal)
            KPICard(title: "Top fundraiser won", value: "\(h.topWon) of \(h.contested)", caption: "contested local races with a report and a result", symbol: "chart.bar", tone: .amber)
            KPICard(title: "Emergency buys from donors", value: "\(h.emergencyFromDonors) of \(h.emergency)", caption: "bought without bidding from a company that gave", symbol: "exclamationmark.triangle", tone: .salmon)
        }
    }

    private var explainer: some View {
        PageSection(title: "What an overlap is, and isn't", symbol: "info.circle", tone: .blue, caption: "The simple version") {
            VStack(alignment: .leading, spacing: 10) {
                line("Two records, one name.", "A company that gave to a commissioner's campaign is named in a motion that commissioner voted on. Both facts are public; this lines them up.")
                line("It is not a finding.", "Most of these votes passed unanimously, many on a consent agenda with dozens of routine items. A gift near a vote does not show why anyone voted the way they did.")
            }
            .padding(14).card(14)
        }
    }

    private func line(_ head: String, _ body: String) -> some View {
        (Text(head).bold() + Text(" " + body)).font(.subheadline).fixedSize(horizontal: false, vertical: true)
    }

    private func card(_ c: Overlaps.Card) -> some View {
        NavigationLink(value: Route.dataset(c.dataset)) {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 10) {
                    ToneIcon(symbol: c.symbol, tone: .blue, size: 30)
                    Text(c.title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary).multilineTextAlignment(.leading)
                    Spacer(minLength: 4)
                    Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                }
                Text(c.stat).font(.caption.weight(.semibold)).foregroundStyle(.primary)
                ForEach(c.items, id: \.self) { Text("• " + $0).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading) }
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
        }
        .buttonStyle(PressScale())
    }

    @ViewBuilder private var liveSection: some View {
        PageSection(title: "Read live", symbol: "bolt", tone: .amber, caption: "Hand-checked matches and check registers, read from the database") {
            VStack(alignment: .leading, spacing: 14) {
                if let live {
                    ForEach(Overlaps.liveSections, id: \.key) { s in
                        let rows = live[s.key] ?? []
                        if !rows.isEmpty {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(s.title).font(.subheadline.weight(.semibold))
                                Text(s.caption).font(.caption).foregroundStyle(.secondary)
                                CardList {
                                    let shown = Array(rows.prefix(5))
                                    ForEach(shown) { r in
                                        liveRow(s.key, r)
                                        if r.id != shown.last?.id { RowDivider() }
                                    }
                                }
                                if rows.count > 5 { Text("\(rows.count - 5) more on BayCounty.me").font(.caption).foregroundStyle(.secondary) }
                            }
                        }
                    }
                } else if liveFailed {
                    Text("Couldn't load this part right now. Pull to try again.").font(.subheadline).foregroundStyle(.secondary)
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 60)
                }
                CardList {
                    WebRow(title: "Every overlap on BayCounty.me", detail: "Full tables, sorting and sources", symbol: "safari", url: URL(string: "https://baycounty.me/connections/overlaps"))
                }
            }
        }
    }

    @ViewBuilder private func liveRow(_ section: String, _ r: Row) -> some View {
        let l = Overlaps.liveLine(section, r)
        if let id = l.entity, let route = Self.route(id) {
            NavigationLink(value: route) { RowLabel(title: l.title, detail: l.detail) }.buttonStyle(.plain)
        } else if let id = l.entity, case let p = id.split(separator: ":"), p.count == 2 {
            Button { store.openSite("/profile/\(p[0])/\(p[1])") } label: { RowLabel(title: l.title, detail: l.detail) }.buttonStyle(.plain)
        } else {
            TextRow(title: l.title, detail: l.detail)
        }
    }

    /// Profiles the app shows natively: people and companies.
    static func route(_ entity: String) -> Route? {
        let p = entity.split(separator: ":", maxSplits: 1).map(String.init)
        guard p.count == 2 else { return nil }
        switch p[0] { case "person": return .person(p[1]); case "vendor": return .vendor(p[1]); default: return nil }
    }
}
