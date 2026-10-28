import SwiftUI
import BayCountyKit

/// The Today tab: a greeting, what's going on right now (beach flag, notices, next meeting, trash day), your address,
/// this weekend's events, what's coming up at city hall, then your tax bill and the big numbers.
struct HomeView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []
    @State private var utilities: UtilityLookup?
    @AppStorage("taxDistrict") private var savedDistrict = ""

    private var today: String { Events.todayKey() }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    greeting
                    ballotBanner
                    rightNow
                    addressCard
                    weekendSection
                    cityHallSection
                    taxBillSection
                    numbersSection
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
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    // The app icon's mark, sized like an SF Symbol so it fits the toolbar's round button.
                    Button { path.append(.about) } label: { BayMark().frame(height: 24) }
                        .accessibilityLabel("About BayCounty.me")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { path.append(.search) } label: { Image(systemName: "magnifyingglass") }
                        .accessibilityLabel("Search")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { store.openSite("/ask") } label: { Image(systemName: "bubble.left.and.text.bubble.right") }
                        .accessibilityLabel("Ask a question")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { path.append(.myHome) } label: { Image(systemName: AccountManager.shared.signedIn ? "person.crop.circle.fill" : "person.crop.circle") }
                        .accessibilityLabel(AccountManager.shared.signedIn ? "My home" : "Sign in")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { path.append(.emergency) } label: { Image(systemName: "bell") }
                        .accessibilityLabel("Emergencies and alerts")
                }
            }
            .refreshable { await store.refreshAll() }
            .withRoutes()
            .onReceive(NotificationCenter.default.publisher(for: .openNotice)) { note in
                // A tapped notification: emergency notices open the Emergencies screen, agenda items their agenda.
                guard let url = note.object as? URL else { return }
                if url.path.hasPrefix("/emergency") { store.tab = .home; path = [.emergency] } else { store.open(url) }
            }
            .task {
                await store.loadTax()
                await store.loadAmendment3()
                await store.load([Events.dataset, "beach-conditions", "emergency-notices"])
                await openScreenshotRoute()
            }
            .task(id: store.home?.id) {
                // The saved home's trash day. The address isn't logged by the API and the answer isn't kept on disk.
                guard let home = store.home else { utilities = nil; return }
                utilities = try? await store.client.utilities(at: home.point)
            }
        }
    }

    // MARK: Greeting

    /// "Good morning" over "WEDNESDAY, OCT 28 · LYNN HAVEN": the date, and the saved home's city once it's known.
    private var greeting: some View {
        let place = utilities.map { $0.area == "county" ? "Bay County" : $0.areaName } ?? "Bay County"
        return VStack(alignment: .leading, spacing: 4) {
            Text("\(TodayBrief.dateLine(today)) · \(place)".uppercased())
                .font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(.secondary)
            Text(TodayBrief.greeting(hour: TodayBrief.hour())).font(.largeTitle.weight(.bold)).foregroundStyle(.primary)
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }

    // MARK: Right now

    /// Beach flag, active notices, next meeting and trash day, two by two. Same cards as the site's home page.
    private var rightNow: some View {
        let cards = TodayBrief.cards(beach: store.rows["beach-conditions"] ?? [], notices: store.rows["emergency-notices"] ?? [],
                                     meetings: store.meetings, trashDays: TodayBrief.trashDays(utilities))
        return LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
            ForEach(cards) { c in
                NavigationLink(value: route(c.target)) { RightNowCard(card: c) }
                    .buttonStyle(PressScale())
            }
        }
        .accessibilityIdentifier("rightNow")
    }

    private func route(_ t: TodayBrief.Target) -> Route {
        switch t {
        case .beaches: .beaches
        case .emergency: .emergency
        case .meetings: .meetings
        case .utilities: .utilities(store.home)
        }
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

    // MARK: This weekend

    /// One-off events this weekend (the coming Friday to Sunday, or the rest of it), or the next few weeks when the
    /// weekend has nothing listed.
    @ViewBuilder private var weekendSection: some View {
        let rows = store.rows[Events.dataset] ?? []
        if !rows.isEmpty {
            let weekend = TodayBrief.weekendEvents(rows, today: today)
            let picks = weekend.isEmpty ? Array(Events.featured(rows, today: today, until: Events.plusDays(21)).prefix(4)) : weekend
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(title: weekend.isEmpty ? "Coming up" : "This weekend", action: "All events") { path.append(.events) }
                if picks.isEmpty {
                    Text("Nothing listed yet.").font(.subheadline).foregroundStyle(.secondary)
                        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                } else {
                    CardList {
                        ForEach(picks) { r in
                            WeekendEventRow(row: r)
                            if r.id != picks.last?.id { RowDivider(inset: 74) }
                        }
                    }
                }
            }
        }
    }

    // MARK: At city hall

    /// The next three public meetings.
    @ViewBuilder private var cityHallSection: some View {
        let next = Array(Meeting.upcoming(store.meetings).prefix(3))
        if !next.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(title: "At city hall", action: "Meetings") { path.append(.meetings) }
                CardList {
                    ForEach(next) { m in
                        NavigationLink(value: Route.meeting(m.id)) { TodayMeetingRow(meeting: m, showDay: true) }
                            .buttonStyle(.plain)
                        if m.id != next.last?.id { Divider().padding(.leading, 66) }
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
            "budget": .budgetCompare(govID: "lh"), "craincrement": .craIncrement, "chambers": .chambers, "events": .events, "beaches": .beaches, "parks": .parks, "schools": .schools, "emergency": .emergency, "hurricaneprep": .hurricanePrep, "volunteer": .volunteer, "military": .military, "myhome": .myHome, "myhome:settings": .myHome, "pastelections": .dataset("campaign-history"),
            "roads": .dataset("road-contracts"), "development": .dataset("development-projects"),
            "restaurants": .restaurants, "restaurant": .restaurant("1305433"), "newbusinesses": .dataset("new-businesses"),
        ]
        if let r = simple[arg] { path = [r]; return }
        if arg == "tab:search" { store.tab = .search; return }
        if arg == "tab:meetings" { path = [.meetings]; return }
        let tabs: [String: AppStore.Tab] = ["tab:governments": .decides, "tab:decides": .decides, "tab:living": .living, "tab:money": .money]
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
        if arg.hasPrefix("utilities:") {
            let q = String(arg.dropFirst("utilities:".count))
            if let m = try? await store.gis.search(q).matches.first { path = [.utilities(m)] }
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
