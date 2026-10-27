import SwiftUI
import BayCountyKit

/// Chambers of commerce (/chambers): the two chambers, what's coming up, regular programs, and who leads them.
/// Reads the chambers, chamber-leaders and chamber-events datasets.
struct ChambersView: View {
    @Environment(AppStore.self) private var store
    @State private var chamber: String = ""
    @State private var kind: Chambers.Kind = .all
    @State private var showAll = false
    @State private var boardChamber: String = "bay-chamber"

    private var chambers: [Row] { store.rows["chambers"] ?? [] }
    private var leaders: [Row] { store.rows["chamber-leaders"] ?? [] }
    private var events: [Row] { store.rows["chamber-events"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "People · Business community", title: "Chambers of commerce",
                     subtitle: "Who leads the Bay County and Panama City Beach chambers, what's coming up, and the public money they get.",
                     symbol: "storefront", tone: .teal)
            if chambers.isEmpty {
                if Chambers.datasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load the chambers", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                simpleVersion
                ForEach(chambers) { chamberCard($0) }
                eventsSection.id("events")
                programsSection
                boardSection
            }
            VStack(alignment: .leading, spacing: 8) {
                CardList {
                    RouteRow(route: .dataset("nonprofits"), title: "All nonprofits", symbol: "heart.text.square")
                    RowDivider(inset: 50)
                    WebRow(title: "Chambers on BayCounty.me", detail: "Board members' businesses and public money", symbol: "safari",
                           url: URL(string: "https://baycounty.me/chambers"))
                }
            }
            FreshnessNote(key: "chamber-events")
        }
        .navigationTitle("Chambers")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.load(Chambers.datasets)
            if let first = chambers.first?.string("chamber_id") { boardChamber = first }
        }
        .refreshable { for i in Chambers.datasets { await store.load(i, force: true) } }
    }

    private var kpis: some View {
        let up = Chambers.upcoming(events, today: Self.today)
        let money = chambers.compactMap { $0.number("public_money_total") }.reduce(0, +)
        return StatGrid {
            KPICard(title: "Board seats", value: "\(Chambers.boardSeats(leaders))",
                    caption: "Across both chambers, plus \(leaders.filter { $0.string("role_group") == "Staff" }.count) staff", symbol: "person.3", tone: .blue)
            KPICard(title: "Coming up", value: "\(up.count)",
                    caption: "\(up.filter { $0.bool("chamber_event") == true }.count) chamber events, the rest community events", symbol: "calendar", tone: .salmon)
            KPICard(title: "Paid by tourism agencies", value: Format.compactMoney(money),
                    caption: "Event fees and sponsorships, FY2024 to FY2026", symbol: "sun.max", tone: .amber)
            KPICard(title: "Revenue", value: Format.compactMoney(chambers.compactMap { $0.number("revenue") }.reduce(0, +)),
                    caption: "Both chambers, latest IRS filings", symbol: "chart.bar", tone: .teal)
        }
    }

    private var simpleVersion: some View {
        PageSection(title: "The simple version", symbol: "lightbulb", tone: .amber) {
            VStack(alignment: .leading, spacing: 10) {
                Text("**A private group of businesses.** Members pay dues to belong. A chamber is a nonprofit business league, not a government agency.")
                Text("**It connects, promotes and speaks up.** Networking events, leadership classes, a member directory, and positions on local issues.")
                Text("**Why it's here.** Their boards bring together business owners, public agency heads and military leaders, and the tourism agencies pay them for events and sponsorships.")
            }
            .font(.subheadline)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card(14)
        }
    }

    private func chamberCard(_ c: Row) -> some View {
        let id = c.string("chamber_id") ?? ""
        let tone: Tone = id == "pcb-chamber" ? .teal : .blue
        return VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                ToneIcon(symbol: "storefront", tone: tone, size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(c.string("name") ?? "").font(.headline).fixedSize(horizontal: false, vertical: true)
                    Text([c.string("tagline"), c.number("founded").map { "Since \(Int($0))" }].compactMap { $0 }.joined(separator: " · "))
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            Text(c.string("about") ?? "").font(.subheadline).fixedSize(horizontal: false, vertical: true)
            Text("Serves \(c.string("serves") ?? "").").font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            if let m = c.string("board_meets") { Text(m).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            HStack(spacing: 8) {
                fact("Revenue\(c.number("latest_return_year").map { ", \(Int($0))" } ?? "")", Format.compactMoney(c.number("revenue") ?? 0))
                fact("IRS staff", c.number("employees").map { "\(Int($0))" } ?? "—")
                fact("Board seats", "\(Chambers.boardSeats(leaders, chamber: id))")
            }
            CardList {
                WebRow(title: "Website", symbol: "globe", url: c.url("website"))
                RowDivider(inset: 50)
                WebRow(title: "Member directory", symbol: "person.2", url: c.url("directory_url"))
                RowDivider(inset: 50)
                WebRow(title: "Events calendar", symbol: "calendar", url: c.url("events_url"))
                RowDivider(inset: 50)
                WebRow(title: "Profile and connections", symbol: "point.3.connected.trianglepath.dotted", url: Chambers.profileURL(c, "page_url"))
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(18)
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption2).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.8)
            Text(value).font(.subheadline.weight(.semibold).monospacedDigit())
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Brand.hairline.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private var eventsSection: some View {
        let chips = [(id: "", label: "Both")] + chambers.map { (id: $0.string("chamber_id") ?? "", label: $0.string("short_name") ?? "") }
        let list = Chambers.upcoming(events, today: Self.today, chamber: chamber.isEmpty ? nil : chamber, kind: kind)
        let shown = showAll ? list : Array(list.prefix(6))
        return PageSection(title: "Coming up", symbol: "calendar", tone: .salmon, caption: "From each chamber's public calendar. Check the chamber's page before you go.") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: chips, selected: chamber) { chamber = $0; showAll = false }
                ChipRow(chips: Chambers.Kind.allCases.map { (id: $0, label: $0.label) }, selected: kind) { kind = $0; showAll = false }
                if list.isEmpty {
                    Text(chamber == "bay-chamber" ? "The Bay County Chamber's calendar can't be read automatically yet. See its events calendar and regular programs."
                                                  : "No upcoming events match.")
                        .font(.subheadline).foregroundStyle(.secondary).padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                } else {
                    CardList {
                        ForEach(shown) { ev in
                            eventRow(ev)
                            if ev.id != shown.last?.id { RowDivider(inset: 72) }
                        }
                    }
                    if !showAll && list.count > shown.count {
                        Button("Show \(list.count - shown.count) more") { showAll = true }
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .card(14)
                    }
                }
            }
        }
    }

    private func eventRow(_ ev: Row) -> some View {
        let d = Chambers.date(ev)
        let isChamber = ev.bool("chamber_event") == true
        return Button { if let u = ev.url("url") { store.open(u) } } label: {
            HStack(alignment: .top, spacing: 12) {
                VStack(spacing: 0) {
                    Text(d.map { HomeView.month.string(from: $0).uppercased() } ?? "").font(.caption2.weight(.bold))
                        .foregroundStyle(.white).frame(maxWidth: .infinity).padding(.vertical, 2).background(Brand.salmonFill)
                    Text(d.map { HomeView.dayNumber.string(from: $0) } ?? "").font(.title3.weight(.semibold).monospacedDigit()).padding(.top, 2)
                    Text(d.map { HomeView.weekday.string(from: $0) } ?? "").font(.caption2).foregroundStyle(.secondary).padding(.bottom, 4)
                }
                .frame(width: 48)
                .background(Brand.surface)
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(Brand.hairline))
                VStack(alignment: .leading, spacing: 3) {
                    Text(ev.string("title") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                        .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                    Text(Chambers.when(ev)).font(.caption).foregroundStyle(.secondary)
                    let place = [ev.string("venue"), ev.string("city")].compactMap { $0 }.joined(separator: ", ")
                    if !place.isEmpty { Text(place).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading) }
                    Badge(text: isChamber ? (ev.string("chamber") ?? "Chamber") : "Community event",
                          color: isChamber ? (ev.string("chamber_id") == "pcb-chamber" ? Brand.good : Brand.navy) : .secondary)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14).padding(.vertical, 11)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the event page")
    }

    private var programsSection: some View {
        PageSection(title: "Regular programs", symbol: "repeat", tone: .amber, caption: "Monthly meetings, yearly events and leadership classes") {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(chambers) { c in
                    let ps = Chambers.programs(events, chamber: c.string("chamber_id") ?? "")
                    if !ps.isEmpty {
                        Text(c.string("short_name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
                        CardList {
                            ForEach(ps) { p in
                                Button { if let u = p.url("url") { store.open(u) } } label: {
                                    TextRow(title: p.string("title") ?? "", detail: [p.string("schedule"), p.string("about")].compactMap { $0 }.joined(separator: " · "))
                                }
                                .buttonStyle(.plain)
                                if p.id != ps.last?.id { RowDivider() }
                            }
                        }
                    }
                }
            }
        }
    }

    private var boardSection: some View {
        let chips = chambers.map { (id: $0.string("chamber_id") ?? "", label: $0.string("short_name") ?? "") }
        let groups = Chambers.leaders(leaders, chamber: boardChamber)
        let past = Chambers.pastChairs(leaders, chamber: boardChamber)
        return PageSection(title: "Who leads them", symbol: "person.3", tone: .blue,
                           caption: "As listed on each chamber's website. Tap a name for every other board, business and record it appears in.") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: chips, selected: boardChamber) { boardChamber = $0 }
                ForEach(groups, id: \.group) { g in
                    Text(Chambers.groupLabel(g.group)).font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
                    CardList {
                        ForEach(g.rows) { r in
                            leaderRow(r)
                            if r.id != g.rows.last?.id { RowDivider(inset: 64) }
                        }
                    }
                }
                if !past.isEmpty {
                    Text("Past chairs since 2016").font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
                    CardList {
                        ForEach(past) { r in
                            leaderRow(r, detail: r.number("year").map { String(Int($0)) })
                            if r.id != past.last?.id { RowDivider(inset: 64) }
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder private func leaderRow(_ r: Row, detail: String? = nil) -> some View {
        let name = r.string("person_name") ?? ""
        let sub = detail ?? [r.string("title"), r.string("organization")].compactMap { $0 }.joined(separator: " · ")
        let label = HStack(spacing: 12) {
            PersonInitials(name: name, size: 38, photo: Chambers.profileURL(r, "photo"))
            VStack(alignment: .leading, spacing: 2) {
                Text(name).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                Text(sub).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 4)
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
        .contentShape(Rectangle())
        if let pid = Chambers.personID(r) {
            NavigationLink(value: Route.person(pid)) { label }.buttonStyle(.plain)
        } else {
            Button { if let u = Chambers.profileURL(r, "person_url") { store.open(u) } } label: { label }.buttonStyle(.plain)
        }
    }
}
