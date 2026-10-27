import SwiftUI
import BayCountyKit

/// The Today tab: what's coming up this week, the ballot, your tax bill, the big numbers, and a list to browse.
struct HomeView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []
    @State private var pickedDay: String?
    @AppStorage("taxDistrict") private var savedDistrict = ""

    private let browse: [(title: String, symbol: String, route: Route)] = [
        ("CRA spending", "building.2", .cra),
        ("Contracts", "signature", .dataset("contracts")),
        ("How they voted", "hand.raised", .dataset("votes")),
        ("Companies", "building", .vendors),
        ("Campaign money", "chart.bar", .dataset("campaign-finance")),
        ("Accountability console", "checklist", .accountability),
        ("Glossary", "character.book.closed", .glossary),
        ("What's new", "sparkles", .updates),
    ]

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    searchField
                    ballotBanner
                    addressCard
                    meetingsSection
                    taxBillSection
                    numbersSection
                    browseSection
                    VStack(spacing: 6) {
                        FreshnessNote()
                        PoweredByFlux()
                    }
                    .frame(maxWidth: .infinity)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle("Today")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    // The app icon's mark, sized like an SF Symbol so it fits the toolbar's round button.
                    Button { path.append(.about) } label: { BayMark().frame(height: 24) }
                        .accessibilityLabel("About BayCounty.me")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { store.openSite("/ask") } label: { Image(systemName: "bubble.left.and.text.bubble.right") }
                        .accessibilityLabel("Ask a question")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { store.openSite("/alerts") } label: { Image(systemName: "bell") }
                        .accessibilityLabel("Email alerts")
                }
            }
            .refreshable { await store.refreshAll() }
            .withRoutes()
            .task {
                await store.loadTax()
                await store.loadAmendment3()
                await openScreenshotRoute()
            }
        }
    }

    // MARK: Search

    private var searchField: some View {
        Button { path.append(.search) } label: {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                Text("Search people, contracts, votes")
                Spacer()
            }
            .font(.body)
            .foregroundStyle(.secondary)
            .padding(.horizontal, 14)
            .frame(height: 46)
            .card(14)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Search")
    }

    // MARK: Ballot

    @ViewBuilder private var ballotBanner: some View {
        if let a3 = store.amendment3, a3.isBeforeVote(), let vote = a3.vote, let day = Dates.parse(vote) {
            let year = 1   // FY2029, the year the site leads with
            NavigationLink(value: Route.amendment3()) {
                HStack(spacing: 12) {
                    VStack(spacing: 0) {
                        Text(Self.month.string(from: day).uppercased()).font(.caption2.weight(.bold))
                        Text(Self.dayNumber.string(from: day)).font(.title3.weight(.heavy).monospacedDigit())
                    }
                    .foregroundStyle(.white)
                    .frame(width: 46, height: 46)
                    .background(Brand.salmonFill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Amendment 3 is on the ballot").font(.subheadline.weight(.bold)).foregroundStyle(.primary)
                        Text("−\(Format.compactMoney(a3.localImpact(year))) to local budgets by \(Amendment3Model.fiscalYears[year]) · needs 60%")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(Brand.salmon)
                }
                .padding(14)
                .background(Brand.salmon.opacity(0.12), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: My Address

    /// The saved home address (tax estimate, representatives, schools, flood zone), or a prompt to look one up.
    private var addressCard: some View {
        CardList {
            if let home = store.home {
                NavigationLink(value: Route.address(home)) {
                    AddressCardRow(symbol: "house.fill", eyebrow: "My Address", title: home.display,
                                   detail: "Tax estimate, representatives, schools, flood zone")
                }
                .buttonStyle(.plain)
                Divider().padding(.leading, 62)
                NavigationLink(value: Route.myAddress) {
                    Label("Look up another address", systemImage: "magnifyingglass")
                        .font(.subheadline.weight(.medium)).foregroundStyle(Brand.navy)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 14).padding(.vertical, 12)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            } else {
                NavigationLink(value: Route.myAddress) {
                    AddressCardRow(symbol: "mappin.and.ellipse", eyebrow: "My Address", title: "What applies to your address?",
                                   detail: "Property tax estimate, who represents you, schools, flood and evacuation zones")
                }
                .buttonStyle(.plain)
            }
        }
        .accessibilityIdentifier("myAddressCard")
    }

    // MARK: Meetings

    /// The next few days that have meetings, within two weeks.
    private var meetingDays: [(key: String, date: Date, meetings: [Meeting])] {
        let soon = Meeting.upcoming(store.meetings).filter { ($0.start ?? .distantFuture) < Date().addingTimeInterval(14 * 86_400) }
        let grouped = Dictionary(grouping: soon) { $0.start.map(Dates.dayKey) ?? "" }
        return grouped.keys.sorted().prefix(4).compactMap { k in
            guard let ms = grouped[k], let d = ms.first?.start else { return nil }
            return (k, d, ms)
        }
    }

    @ViewBuilder private var meetingsSection: some View {
        let days = meetingDays
        if !days.isEmpty {
            let current = days.first { $0.key == pickedDay } ?? days[0]
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(title: "Meetings coming up", action: "See all") { store.tab = .meetings }
                HStack(spacing: 8) {
                    ForEach(days, id: \.key) { d in
                        let on = d.key == current.key
                        Button { withAnimation(.snappy) { pickedDay = d.key } } label: {
                            VStack(spacing: 1) {
                                Text(Self.weekday.string(from: d.date).uppercased()).font(.caption2.weight(.semibold))
                                Text(Self.dayNumber.string(from: d.date)).font(.title3.weight(.heavy).monospacedDigit())
                                Text(d.meetings.count == 1 ? "1 mtg" : "\(d.meetings.count) mtgs")
                                    .font(.caption2).foregroundStyle(on ? Color.white.opacity(0.8) : .secondary)
                            }
                            .frame(maxWidth: .infinity, minHeight: 64)
                            .foregroundStyle(on ? Color.white : .primary)
                            .background(on ? Brand.navyFill : Brand.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(Dates.display(d.date, hasTime: false)), \(d.meetings.count) meetings")
                        .accessibilityAddTraits(on ? .isSelected : [])
                    }
                }
                CardList {
                    ForEach(current.meetings) { m in
                        NavigationLink(value: Route.meeting(m.id)) { TodayMeetingRow(meeting: m) }
                            .buttonStyle(.plain)
                        if m.id != current.meetings.last?.id { Divider().padding(.leading, 66) }
                    }
                }
            }
        }
    }

    // MARK: Tax bill

    @ViewBuilder private var taxBillSection: some View {
        if let m = store.taxModel, let d = m.districts.first(where: { $0.id == savedDistrict }) ?? m.districts.first {
            let value = 250_000.0
            let e = TaxCalculator.estimate(model: m, district: d, value: value, homestead: true)
            let name: (String) -> String = { g in g == "city" ? "City" : m.groupName(g) }
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(title: "Your tax bill", action: "Change") { path.append(.taxCalculator(districtID: d.id)) }
                NavigationLink(value: Route.taxCalculator(districtID: d.id, value: value, homestead: true)) {
                    VStack(alignment: .leading, spacing: 12) {
                        HStack(alignment: .lastTextBaseline) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(d.label) · \(Format.compactMoney(value)) home, homestead").font(.caption).foregroundStyle(.secondary)
                                (Text(Format.money(e.total)).font(.largeTitle.weight(.heavy).monospacedDigit())
                                 + Text(" / yr").font(.subheadline).foregroundColor(.secondary))
                            }
                            Spacer()
                            Text("Every line").font(.subheadline.weight(.semibold)).foregroundStyle(Brand.navy)
                        }
                        StackBar(parts: e.byGroup.map { (name($0.group), $0.amount, TaxColors.color($0.group)) })
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], alignment: .leading, spacing: 8) {
                            ForEach(e.byGroup.prefix(6)) { g in
                                VStack(alignment: .leading, spacing: 2) {
                                    HStack(spacing: 5) {
                                        RoundedRectangle(cornerRadius: 2).fill(TaxColors.color(g.group)).frame(width: 8, height: 8)
                                        Text(name(g.group)).lineLimit(1)
                                    }
                                    .font(.caption).foregroundStyle(.secondary)
                                    Text(Format.money(g.amount)).font(.subheadline.weight(.bold).monospacedDigit())
                                }
                            }
                        }
                    }
                    .padding(18)
                    .card(18)
                }
                .buttonStyle(.plain)
                if let home = store.home {
                    NavigationLink(value: Route.address(home)) {
                        Label("Exact estimate for \(home.display)", systemImage: "house.fill").font(.subheadline.weight(.medium))
                    }
                } else {
                    NavigationLink(value: Route.myAddress) {
                        Label("Use your address for an exact estimate", systemImage: "mappin.and.ellipse").font(.subheadline.weight(.medium))
                    }
                }
            }
        }
    }

    // MARK: Numbers

    @ViewBuilder private var numbersSection: some View {
        let g = store.governments
        if !g.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Text("By the numbers").font(.title3.weight(.bold))
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                    NumberTile(value: Format.compactMoney(g.compactMap(\.propertyTaxLevy).reduce(0, +)), label: "Property tax levied",
                               bars: g.compactMap(\.propertyTaxLevy), color: Brand.navy, route: .taxCalculator())
                    NumberTile(value: Format.compactMoney(g.compactMap(\.femaMichael).reduce(0, +)), label: "FEMA after Michael",
                               bars: g.compactMap(\.femaMichael), color: Brand.blue, route: .dataset("fema-michael-projects"))
                    NumberTile(value: Format.compactMoney(g.compactMap(\.debtTotal).reduce(0, +)), label: "Owed by governments",
                               bars: g.compactMap(\.debtTotal), color: Brand.salmon, route: .dataset("debt"))
                    NumberTile(value: Format.number(Double(g.compactMap(\.auditFindings).reduce(0, +))), label: "Audit findings",
                               bars: g.compactMap { $0.auditFindings.map(Double.init) }, color: Brand.amber, route: .dataset("audit-findings"))
                }
                Text("County, school district and the seven cities.").font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    // MARK: Browse

    private var browseSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeader(title: "Browse", action: "All public money") { store.tab = .money }
            CardList {
                ForEach(browse, id: \.title) { b in
                    NavigationLink(value: b.route) {
                        HStack(spacing: 12) {
                            Image(systemName: b.symbol).foregroundStyle(Brand.navy).frame(width: 24)
                            Text(b.title).foregroundStyle(.primary)
                            Spacer()
                            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                        .frame(minHeight: 50)
                        .padding(.horizontal, 14)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if b.title != browse.last?.title { Divider().padding(.leading, 50) }
                }
            }
        }
    }

    static let weekday: DateFormatter = { let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "EEE"; return f }()
    static let dayNumber: DateFormatter = { let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "d"; return f }()
    static let month: DateFormatter = { let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "MMM"; return f }()

    /// For automated screenshots: `-screen <name>` opens one screen at launch (see .github/workflows/ios-screenshots.yml).
    private func openScreenshotRoute() async {
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screen"), i + 1 < args.count, path.isEmpty else { return }
        let arg = args[i + 1]
        let simple: [String: Route] = [
            "tax": .taxCalculator(districtID: "Lynn Haven", value: 250_000, homestead: true), "amendment3": .amendment3(districtID: "Panama City", value: 300_000, homestead: true),
            "glossary": .glossary, "vendors": .vendors, "people": .people, "moneymap": .moneyMap, "donors": .donorContracts,
            "updates": .updates, "about": .about, "cra": .cra, "myaddress": .myAddress, "contracts": .dataset("contracts"),
            "vendor": .vendor("roberts-and-roberts"), "person": .person("clair-pease"), "explore": .explore,
            "votes": .dataset("votes"), "salaries": .dataset("salary-positions"),
            "accountability": .accountability, "accproject": .accountabilityProject("pcb-fbr-seg3"),
            "budget": .budgetCompare(govID: "lh"), "craincrement": .craIncrement, "chambers": .chambers, "volunteer": .volunteer, "pastelections": .dataset("campaign-history"),
        ]
        if let r = simple[arg] { path = [r]; return }
        if arg == "tab:search" { path = [.search]; return }
        let tabs: [String: AppStore.Tab] = ["tab:governments": .governments, "tab:money": .money, "tab:meetings": .meetings]
        if let t = tabs[arg] { store.tab = t; return }
        if arg.hasPrefix("gov:") { path = [.government(String(arg.dropFirst(4)))]; return }
        if arg == "record:contract" || arg == "record:vote" {
            let ds = arg == "record:contract" ? "contracts" : "votes"
            await store.load(ds)
            let rows = store.rows[ds] ?? []
            let pick = ds == "contracts" ? rows.first { $0.string("vendor") == "Ten-8 Fire & Safety, LLC" }
                                         : rows.first { $0.string("headline") == "Approved $62.45 million FY2027 general fund budget" }
            if let r = pick ?? rows.first { path = [.record(ds, rowID: r.id)] }
            return
        }
        if arg == "record:board" || arg == "record:nonprofit" {
            let ds = arg == "record:board" ? "nonprofit-board-members" : "nonprofits"
            await store.load(ds)
            let rows = store.rows[ds] ?? []
            let pick = rows.first { $0.string("nonprofit_id") == "np-sb-n01000008288" && (ds == "nonprofits" || $0.string("person") == "Kathy Bass") }
            if let r = pick ?? rows.first { path = [.record(ds, rowID: r.id)] }
            return
        }
        if arg.hasPrefix("address:") {
            let q = String(arg.dropFirst("address:".count))
            if let m = try? await store.gis.search(q).matches.first { path = [.address(m)] }
        }
    }
}

/// One row on the Today tab's My Address card.
private struct AddressCardRow: View {
    let symbol: String
    let eyebrow: String
    let title: String
    let detail: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: symbol).font(.title3).foregroundStyle(Brand.navy)
                .frame(width: 36, height: 36)
                .background(Brand.navy.opacity(0.1), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(eyebrow).font(.caption).foregroundStyle(.secondary)
                Text(title).font(.headline).foregroundStyle(.primary).multilineTextAlignment(.leading)
                Text(detail).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 0)
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .padding(14)
        .contentShape(Rectangle())
    }
}
