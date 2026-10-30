import SwiftUI
import BayCountyKit

/// The Home tab ("My home dashboard"): a line about your home, an alert strip when notices are active, then tiles that
/// each give one answer (HomeTiles). Owners lead with the tax bill, renters with utilities. Each tile opens one short
/// screen. Then your address and this weekend's events.
struct HomeView: View {
    @Environment(AppStore.self) private var store
    @State private var path: [Route] = []
    @State private var utilities: UtilityLookup?
    @State private var showSetup = false
    @AppStorage("taxDistrict") private var savedDistrict = ""

    private var today: String { Events.todayKey() }
    private var tenure: HomeTiles.Tenure { store.tenure ?? .unset }

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    greeting
                    alertStrip
                    tileGrid
                    addressCard
                    weekendSection
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
            .navigationTitle("Home")
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
            .sheet(isPresented: $showSetup) { HomeSetupView() }
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
                // The saved home's trash day and city. The address isn't logged by the API and the answer isn't kept on disk.
                guard let home = store.home else { utilities = nil; return }
                utilities = try? await store.client.utilities(at: home.point)
            }
        }
    }

    // MARK: Greeting

    /// "YOUR HOME · LYNN HAVEN · RENTING" over "Good morning", or "BAY COUNTY" before a home is saved.
    private var greeting: some View {
        let place = store.home == nil ? nil : (utilities.map { $0.area == "county" ? "Bay County" : $0.areaName } ?? "Bay County")
        return VStack(alignment: .leading, spacing: 4) {
            Text(HomeTiles.eyebrow(place: place, tenure: tenure).uppercased())
                .font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(.secondary)
            Text(TodayBrief.greeting(hour: TodayBrief.hour())).font(.largeTitle.weight(.bold)).foregroundStyle(.primary)
        }
        .padding(.top, 8)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }

    // MARK: Alert strip

    @ViewBuilder private var alertStrip: some View {
        if let a = HomeTiles.alert(store.rows["emergency-notices"] ?? []) {
            NavigationLink(value: Route.emergency) {
                HStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle.fill").font(.title3).foregroundStyle(Brand.amber)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(a.title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                        Text(a.detail).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                }
                .padding(14)
                .background(Brand.amber.opacity(0.16), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("alertStrip")
        }
    }

    // MARK: Tiles

    /// The tax estimate for the saved home's district (or the calculator's), at the sample value with homestead.
    private var taxTotal: Double? {
        guard let m = store.taxModel, let d = HomeTiles.taxDistrict(model: m, utilities: utilities, saved: savedDistrict) else { return nil }
        return TaxCalculator.estimate(model: m, district: d, value: HomeTiles.sampleValue, homestead: true).total
    }

    private var electionDay: String? {
        guard let a3 = store.amendment3, a3.isBeforeVote() else { return nil }
        return a3.vote
    }

    /// Two tiles a row; with an odd count the lead tile spans the first row.
    private var tileGrid: some View {
        let tiles = HomeTiles.tiles(tenure: tenure, hasHome: store.home != nil, utilities: utilities, taxTotal: taxTotal,
                                    beach: store.rows["beach-conditions"] ?? [], meetings: store.meetings, electionDay: electionDay)
        let lead = tiles.count % 2 == 1 ? [tiles[0]] : []
        let rest = Array(tiles.dropFirst(lead.count))
        let pairs = stride(from: 0, to: rest.count, by: 2).map { Array(rest[$0..<min($0 + 2, rest.count)]) }
        return VStack(spacing: 10) {
            ForEach(lead) { t in tileButton(t, wide: true) }
            ForEach(pairs, id: \.self) { pair in
                HStack(spacing: 10) { ForEach(pair) { t in tileButton(t, wide: false) } }
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityIdentifier("homeTiles")
    }

    private func tileButton(_ t: HomeTiles.Tile, wide: Bool) -> some View {
        Button { open(t.target) } label: { HomeTileView(tile: t, wide: wide) }
            .buttonStyle(PressScale())
    }

    private func open(_ target: HomeTiles.Target) {
        switch target {
        case .setup: showSetup = true
        case .taxBill: path.append(.taxBill(districtID: store.taxModel.flatMap { HomeTiles.taxDistrict(model: $0, utilities: utilities, saved: savedDistrict)?.id }))
        case .utilities: path.append(.utilities(store.home))
        case .beaches: path.append(.beaches)
        case .meetings: path.append(.meetings)
        case .election: store.openSite("/elections/voting")
        case .representatives: path.append(store.home.map { .address($0) } ?? .people)
        case .schools: path.append(.schools)
        }
    }

    // MARK: My Address

    /// Everything for the saved home (tax estimate, representatives, schools, flood zone), or a prompt to set one.
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
                Divider().padding(.leading, 14)
                Button { showSetup = true } label: {
                    HStack {
                        Text("Own or rent").font(.subheadline.weight(.medium)).foregroundStyle(.primary)
                        Spacer()
                        Text(store.tenure.map { $0 == .unset ? "Not set" : $0.label } ?? "Not set").font(.subheadline).foregroundStyle(.secondary)
                        Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                    }
                    .padding(.horizontal, 14).padding(.vertical, 12)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("tenureRow")
            } else {
                Button { showSetup = true } label: {
                    AddressCardRow(symbol: "mappin.and.ellipse", eyebrow: "My Address", title: "What applies to your address?",
                                   detail: "Trash day, who represents you, schools, flood and evacuation zones")
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
        let all = store.rows[Events.dataset] ?? []
        if !all.isEmpty {
            let w = weekendPicks(all, town: AccountManager.shared.me?.home?.town)
            let picks = w.rows
            VStack(alignment: .leading, spacing: 12) {
                SectionHeader(title: w.title, action: "All events") { path.append(.events) }
                if let note = w.note {
                    Text(note).font(.subheadline).foregroundStyle(.secondary)
                }
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

    /// This weekend's one-off events (else the next three weeks'). Signed in: the home's town first; with nothing
    /// listed there, a note says so and the rest of the county shows.
    private func weekendPicks(_ all: [Row], town: String?) -> (title: String, note: String?, rows: [Row]) {
        func pick(_ rows: [Row]) -> (weekend: Bool, rows: [Row]) {
            let w = TodayBrief.weekendEvents(rows, today: today)
            return w.isEmpty ? (false, Array(Events.featured(rows, today: today, until: Events.plusDays(21)).prefix(4))) : (true, w)
        }
        if let town {
            let mine = pick(all.filter { $0.string("town") == town })
            if !mine.rows.isEmpty { return ((mine.weekend ? "This weekend" : "Coming up") + " in \(town)", nil, mine.rows) }
            let rest = pick(all)
            return (rest.weekend ? "This weekend" : "Coming up", "Nothing listed in \(town) yet. Here's the rest of Bay County.", rest.rows)
        }
        let rest = pick(all)
        return (rest.weekend ? "This weekend" : "Coming up", nil, rest.rows)
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
            "publicsafety": .publicSafety, "overlaps": .overlaps, "taxbill": .taxBill(),
        ]
        if arg == "setup" { showSetup = true; return }
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

/// One Home tab tile: a label with its icon, one big answer, and a line under it. The lead tile is navy.
struct HomeTileView: View {
    let tile: HomeTiles.Tile
    var wide = false

    private var tone: Color {
        switch tile.tone { case "teal": Brand.good; case "amber": Brand.amber; case "salmon": Brand.salmon; default: Brand.navy }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label(tile.eyebrow, systemImage: tile.symbol)
                .font(.caption.weight(.semibold))
                .foregroundStyle(tile.featured ? AnyShapeStyle(Color.white.opacity(0.9)) : AnyShapeStyle(tone))
            Text(tile.value)
                .font(.title2.weight(.semibold)).monospacedDigit()
                .foregroundStyle(tile.featured ? AnyShapeStyle(Color.white) : AnyShapeStyle(HierarchicalShapeStyle.primary))
                .lineLimit(2).minimumScaleFactor(0.8)
            Text(tile.detail)
                .font(.caption)
                .foregroundStyle(tile.featured ? AnyShapeStyle(Color.white.opacity(0.85)) : AnyShapeStyle(HierarchicalShapeStyle.secondary))
                .multilineTextAlignment(.leading)
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: wide ? 0 : 118, alignment: .topLeading)
        .padding(14)
        .background {
            if tile.featured {
                RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Brand.navyFill)
            } else {
                RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Brand.surface)
                    .overlay { RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Brand.hairline) }
            }
        }
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("tile-" + tile.id)
    }
}
