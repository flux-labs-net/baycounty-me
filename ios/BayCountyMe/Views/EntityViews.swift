import SwiftUI
import BayCountyKit

/// Every company paid by a Bay County government, CRA or tourism agency.
struct VendorsView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var gov: String? = nil

    private var list: [VendorDirectory.Vendor] {
        let q = query.lowercased().trimmingCharacters(in: .whitespaces)
        return (store.vendors?.vendors ?? [])
            .filter { gov == nil || $0.gov_ids.contains(gov!) }
            .filter { q.isEmpty || $0.name.lowercased().contains(q) || $0.aliases.contains { $0.lowercased().contains(q) } }
            .sorted { $0.recordCount != $1.recordCount ? $0.recordCount > $1.recordCount : $0.name < $1.name }
    }

    var body: some View {
        List {
            ListHeroSection(kicker: "Accountability", title: "Companies",
                            subtitle: "Every company or organization paid by a Bay County government, CRA or tourism agency, with its contracts, payments, the votes that approved them and gifts from the business to campaigns. A gift near a vote does not show why anyone voted the way they did.",
                            symbol: "building", tone: .blue)
            Section {
                RecordKindLegend()
            }
            .listRowBackground(Color.clear)
            Section("\(list.count) companies") {
                let maxCount = list.first?.recordCount ?? 1
                ForEach(list.prefix(400)) { v in
                    NavigationLink(value: Route.vendor(v.id)) {
                        VStack(alignment: .leading, spacing: 5) {
                            HStack(alignment: .firstTextBaseline) {
                                Text(v.name).font(.subheadline.weight(.semibold)).lineLimit(2)
                                Spacer(minLength: 6)
                                Text("\(v.recordCount)").font(.subheadline.weight(.semibold).monospacedDigit())
                            }
                            RecordKindBar(records: v.records, scale: Double(v.recordCount) / Double(max(maxCount, 1)))
                        }
                        .padding(.vertical, 2)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(v.name + ": " + v.records.sorted { $0.value > $1.value }.map { "\($0.value) \(Self.kind($0.key))" }.joined(separator: ", "))
                    }
                }
            }
        }
        .overlay { if store.vendors == nil { AppDataPending(file: "vendors.json", title: "Couldn't load companies") { await store.loadVendors() } } }
        .navigationTitle("Companies")
        .searchable(text: $query, prompt: "Look up a company")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Picker("Government", selection: $gov) {
                        Text("Every government").tag(String?.none)
                        ForEach(Governments.order, id: \.self) { Text(Governments.names[$0] ?? $0).tag(String?.some($0)) }
                    }
                } label: { Image(systemName: gov == nil ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill") }
                .accessibilityLabel("Filter by government")
            }
        }
        .task { await store.loadVendors() }
    }

    static func kind(_ k: String) -> String {
        ["contract": "contracts", "change_order": "change orders", "emergency": "emergency purchases", "register": "check register lines",
         "tdc": "tourism payments", "cra": "CRA records"][k] ?? k.replacingOccurrences(of: "_", with: " ")
    }
}

/// One company: its contracts, payments, the votes that approved them and gifts from the business.
struct VendorDetailView: View {
    @Environment(AppStore.self) private var store
    let vendorID: String

    var body: some View {
        let v = store.vendor(vendorID)
        List {
            ListHeroSection(kicker: "Company", title: v?.name ?? "Company",
                            subtitle: subtitle(v),
                            symbol: "building", tone: .blue)
            let recs = RecordLinks.records(forVendor: vendorID, in: store.rows)
            let deals = recs.filter { ["contracts", "change-orders", "emergency-purchases"].contains($0.dataset) }.flatMap(\.rows)
            if !deals.isEmpty {
                Section {
                    vendorSummary(deals: deals, recs: recs)
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 6, leading: 0, bottom: 6, trailing: 0))
                .listRowSeparator(.hidden)
            }
            ForEach(recs, id: \.dataset) { group in
                let spec = DatasetSpec.for(group.dataset)
                let maxAmount = group.rows.compactMap(spec.amount).max() ?? 0
                Section(store.info(group.dataset)?.title ?? Format.label(group.dataset)) {
                    ForEach(group.rows.prefix(25)) { row in
                        NavigationLink(value: Route.record(group.dataset, rowID: row.id)) {
                            CompactRecordRow(spec: spec, row: row, maxAmount: maxAmount, hide: spec.titleKeys.first)
                        }
                    }
                    if group.rows.count > 25 {
                        NavigationLink(value: Route.dataset(group.dataset, filters: ["vendor_id": vendorID])) { Text("All \(group.rows.count)") }
                    }
                }
            }
            let votes = RecordLinks.votes(forVendor: vendorID, in: store.rows)
            if !votes.isEmpty {
                Section {
                    ForEach(votes) { row in
                        NavigationLink(value: Route.record("votes", rowID: row.id)) { VoteRow(row: row, summary: VoteSummary(row)) }
                    }
                } header: { Text("Votes that approved its contracts") } footer: {
                    Text("Matched from the minutes. A gift near a vote does not show why anyone voted the way they did.")
                }
            }
            if let matches = store.donorContracts?.matches.filter({ $0.vendor_id == vendorID }), !matches.isEmpty {
                Section("Gifts from the business to campaigns") {
                    ForEach(matches) { m in DonorMatchRow(match: m) }
                }
            }
            if recs.isEmpty && votes.isEmpty && store.loading.isEmpty == false {
                Section { ProgressView() }
            }
            if let url = v?.pageURL { Section { WebLink(title: "Company page on BayCounty.me", url: url) } }
            else { Section { WebLink(title: "Profile and connections on BayCounty.me", url: URL(string: "https://baycounty.me/profile/vendor/\(vendorID)")) } }
        }
        .screenshotScroll()
        .navigationTitle(v?.name ?? "Company")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadVendors()
            await store.loadDonorContracts()
            await store.load(RecordLinks.vendorDatasets + ["votes"])
        }
    }

    /// Headline numbers and a chart of approvals by year for one company.
    private func vendorSummary(deals: [Row], recs: [(dataset: String, rows: [Row])]) -> some View {
        let contracts = recs.first { $0.dataset == "contracts" }?.rows ?? []
        let spec = DatasetSpec.for("contracts")
        let approved = contracts.compactMap(spec.amount).reduce(0, +)
        let govs = Set(deals.compactMap { $0.string("government") }).count
        var byYear = [Int: Double]()
        for r in contracts { if let y = Period.of(r)?.year { byYear[y, default: 0] += spec.amount(r) ?? 0 } }
        let points = byYear.keys.sorted().map { (label: String($0), value: byYear[$0]!) }
        return VStack(spacing: 10) {
            StatStrip(tiles: [
                .init(title: "Contracts", value: "\(contracts.count)"),
                .init(title: "Approved", value: Format.compactMoney(approved)),
                .init(title: govs == 1 ? "Government" : "Governments", value: "\(govs)"),
            ])
            if points.count >= 2 { YearBars(title: "Contracts approved each year", points: points) }
            Text("Approved amounts, often not-to-exceed. Not proof of payment.")
                .font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    /// Which governments paid it, and other spellings of its name.
    private func subtitle(_ v: VendorDirectory.Vendor?) -> String? {
        guard let v else { return nil }
        var lines: [String] = []
        let govs = v.gov_ids.compactMap { Governments.names[$0] ?? Self.agency[$0] }
        if !govs.isEmpty { lines.append(govs.joined(separator: " · ")) }
        if !v.aliases.isEmpty { lines.append("Also spelled: " + v.aliases.prefix(5).joined(separator: "; ")) }
        return lines.isEmpty ? nil : lines.joined(separator: "\n")
    }

    static let agency = ["visit_pcb": "Visit Panama City Beach", "destination_pc": "Destination Panama City", "mb_cdc": "Mexico Beach CDC",
                         "sheriff": "Sheriff", "airport": "Airport", "port": "Port Panama City"]
}

/// Kinds of company records, in a fixed order and color, for the Companies list.
enum RecordKind {
    static let order = ["contract", "change_order", "emergency", "cra", "tdc", "register"]
    static func color(_ k: String) -> Color {
        switch k {
        case "contract": Brand.navy
        case "change_order": Brand.blue
        case "emergency": Brand.salmon
        case "cra": Brand.good
        case "tdc": Brand.amber
        default: Color.secondary.opacity(0.45)
        }
    }
    static func label(_ k: String) -> String {
        ["contract": "Contracts", "change_order": "Change orders", "emergency": "Emergency", "register": "Checks",
         "tdc": "Tourism", "cra": "CRA"][k] ?? k
    }
}

/// One company's records as a stacked bar, its length scaled to the busiest company.
struct RecordKindBar: View {
    let records: [String: Int]
    let scale: Double

    var body: some View {
        let total = Double(records.values.reduce(0, +))
        let keys = RecordKind.order.filter { (records[$0] ?? 0) > 0 } + records.keys.filter { !RecordKind.order.contains($0) }.sorted()
        GeometryReader { g in
            HStack(spacing: 1.5) {
                ForEach(keys, id: \.self) { k in
                    Rectangle().fill(RecordKind.color(k))
                        .frame(width: max(3, g.size.width * max(scale, 0.04) * Double(records[k] ?? 0) / max(total, 1)))
                }
                Spacer(minLength: 0)
            }
            .clipShape(RoundedRectangle(cornerRadius: 3))
        }
        .frame(height: 7)
    }
}

struct RecordKindLegend: View {
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100), alignment: .leading)], alignment: .leading, spacing: 6) {
            ForEach(RecordKind.order, id: \.self) { k in
                HStack(spacing: 5) {
                    RoundedRectangle(cornerRadius: 2).fill(RecordKind.color(k)).frame(width: 10, height: 10)
                    Text(RecordKind.label(k)).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityHidden(true)
    }
}

/// A business gift to a campaign, matched to the business's contracts.
struct DonorMatchRow: View {
    @Environment(AppStore.self) private var store
    let match: DonorContracts.Match
    var showCandidate = true

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                if showCandidate, let pid = match.person_id {
                    NavigationLink(value: Route.person(pid)) { Text(match.candidate ?? pid).font(.subheadline.weight(.medium)) }
                } else if let vid = match.vendor_id, !showCandidate {
                    NavigationLink(value: Route.vendor(vid)) { Text(match.vendor_name ?? match.vendor ?? match.contributor ?? vid).font(.subheadline.weight(.medium)) }
                } else {
                    Text(showCandidate ? (match.candidate ?? "") : (match.vendor_name ?? match.contributor ?? "")).font(.subheadline.weight(.medium))
                }
                Spacer()
                if let a = match.contribution_amount { Text(Format.money(a)).monospacedDigit() }
            }
            Text([match.office, match.election].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
            if let govs = match.contract_governments, govs.count > 1 {
                Text("Paid by " + govs.joined(separator: ", ")).font(.caption2).foregroundStyle(.secondary)
            }
            if let items = match.contract_ids_or_descriptions, !items.isEmpty {
                Text(items.prefix(3).joined(separator: "\n") + (items.count > 3 ? "\n+\(items.count - 3) more" : "")).font(.caption2)
            }
            if match.same_government_as_office == true {
                Badge(text: "Contract with the same government", color: Brand.salmon)
            }
        }
        .padding(.vertical, 2)
    }
}

/// Businesses that gave to campaigns and also hold local government contracts.
struct DonorContractsView: View {
    @Environment(AppStore.self) private var store
    @State private var sameOnly = false

    private struct Group: Identifiable {
        let id: String
        let name: String
        let vendorID: String?
        let matches: [DonorContracts.Match]
        let total: Double
    }

    private var groups: [Group] {
        let all = store.donorContracts?.matches ?? []
        let list = sameOnly ? all.filter { $0.same_government_as_office == true } : all
        let grouped = Dictionary(grouping: list) { (m: DonorContracts.Match) -> String in m.vendor_id ?? m.contributor ?? "" }
        var out: [Group] = []
        for (key, ms) in grouped {
            let total: Double = ms.compactMap { $0.contribution_amount }.reduce(0, +)
            let name: String = ms.first?.vendor_name ?? ms.first?.vendor ?? ms.first?.contributor ?? key
            out.append(Group(id: key, name: name, vendorID: ms.first?.vendor_id, matches: ms, total: total))
        }
        return out.sorted { $0.total > $1.total }
    }

    var body: some View {
        List {
            ListHeroSection(kicker: "Connections", title: "Donors with contracts",
                            subtitle: "Businesses that gave to a local campaign and also hold a contract, grant or payment from a Bay County government. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.",
                            symbol: "link", tone: .salmon)
            Section {
                Toggle("Only where the contract is with the same government", isOn: $sameOnly)
            }
            let gs = groups
            if !gs.isEmpty {
                Section {
                    StatStrip(tiles: [
                        .init(title: "Gifts", value: "\(gs.map(\.matches.count).reduce(0, +))"),
                        .init(title: "Given", value: Format.compactMoney(gs.map(\.total).reduce(0, +))),
                        .init(title: "Companies", value: "\(gs.count)"),
                    ])
                    CompareBars(title: "Biggest givers", items: gs.prefix(6).map { CompareBars.Item(id: $0.id, label: $0.name, value: $0.total) },
                                format: { Format.compactMoney($0) })
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 6, leading: 0, bottom: 6, trailing: 0))
                .listRowSeparator(.hidden)
            }
            ForEach(groups) { g in
                Section {
                    ForEach(g.matches) { DonorMatchRow(match: $0) }
                } header: {
                    if let vid = g.vendorID {
                        NavigationLink(value: Route.vendor(vid)) { Text(g.name) }
                    } else { Text(g.name) }
                }
            }
            if let m = store.donorContracts?.method { Section("Method") { Text(m).font(.footnote) } }
        }
        .overlay { if store.donorContracts == nil { AppDataPending(file: "donor-contracts.json", title: "Couldn't load donor matches") { await store.loadDonorContracts() } } }
        .navigationTitle("Donors with contracts")
        .task { await store.loadDonorContracts() }
    }
}

/// Money Map: which businesses gave to which officials, and the votes on those donors' contracts.
struct MoneyMapView: View {
    @Environment(AppStore.self) private var store
    enum Mode: String, CaseIterable, Identifiable { case officials = "Officials", donors = "Donors", heat = "By government", votes = "Votes"; var id: String { rawValue } }
    @State private var mode: Mode = .officials
    @State private var gov: String? = nil

    var body: some View {
        List {
            ListHeroSection(kicker: "Connections", title: "Money map",
                            subtitle: "Gifts from businesses and organizations to the campaigns of current officials, and where those donors hold local government contracts. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.",
                            symbol: "point.3.connected.trianglepath.dotted", tone: .amber)
            Section {
                ChipRow(chips: Mode.allCases.map { (id: $0, label: $0.rawValue) }, selected: mode) { mode = $0 }
            }
            if let mm = store.moneyMap {
                switch mode {
                case .officials: officials(mm)
                case .donors: donors(mm)
                case .heat: heat(mm)
                case .votes: votes(mm)
                }
            } else if let e = store.appError("money-map.json") {
                Text(e).foregroundStyle(.secondary)
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .navigationTitle("Money map")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Picker("Government", selection: $gov) {
                        Text("Every government").tag(String?.none)
                        ForEach(Governments.order, id: \.self) { Text(Governments.names[$0] ?? $0).tag(String?.some($0)) }
                    }
                } label: { Image(systemName: gov == nil ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill") }
            }
        }
        .task { await store.loadMoneyMap(); await store.loadPeople() }
    }

    private func personID(_ name: String) -> String? {
        store.people?.people.first { $0.name.lowercased() == name.lowercased() }?.id
    }

    @ViewBuilder private func officials(_ mm: MoneyMap) -> some View {
        ForEach(mm.officials.filter { gov == nil || $0.g == gov }) { o in
            let gifts = mm.gifts(toOfficial: o.id)
            Section {
                ForEach(gifts.prefix(8), id: \.self) { g in
                    if let d = mm.donor(g.d) {
                        HStack {
                            Text(d.n).font(.subheadline)
                            if d.holdsContracts { Badge(text: "Holds contracts", color: Brand.salmon) }
                            Spacer()
                            Text(Format.money(g.a)).monospacedDigit().font(.subheadline)
                        }
                    }
                }
                if gifts.count > 8 { Text("and \(gifts.count - 8) more").font(.caption).foregroundStyle(.secondary) }
                if gifts.isEmpty { Text("No business or organization gifts on file.").font(.caption).foregroundStyle(.secondary) }
            } header: {
                VStack(alignment: .leading, spacing: 2) {
                    if let pid = personID(o.n) { NavigationLink(value: Route.person(pid)) { Text(o.n) } } else { Text(o.n) }
                    Text([o.off, o.raised.map { "raised \(Format.compactMoney($0))" }].compactMap { $0 }.joined(separator: " · ")).font(.caption2).textCase(nil)
                }
            }
        }
    }

    @ViewBuilder private func donors(_ mm: MoneyMap) -> some View {
        let ds = mm.donors.filter { d in gov == nil || mm.gifts(fromDonor: d.id).contains { mm.official($0.o)?.g == gov } }
            .sorted { ($0.tot ?? 0) > ($1.tot ?? 0) }
        Section("\(ds.count) donors") {
            ForEach(ds.prefix(150)) { d in
                DisclosureGroup {
                    ForEach(mm.gifts(fromDonor: d.id), id: \.self) { g in
                        if let o = mm.official(g.o) { LabeledContent(o.n, value: Format.money(g.a)).font(.caption) }
                    }
                    ForEach(Array(mm.contracts(forDonor: d.id).enumerated()), id: \.offset) { _, c in
                        Text((Governments.names[c.g] ?? c.g) + ": " + (c.items ?? []).prefix(2).joined(separator: "; ")).font(.caption2)
                    }
                    if let vp = d.vp { NavigationLink(value: Route.vendor(vp)) { Text("Company page") } }
                } label: {
                    HStack {
                        Text(d.n).font(.subheadline)
                        if d.holdsContracts { Badge(text: "Holds contracts", color: Brand.salmon) }
                        Spacer()
                        Text(Format.compactMoney(d.tot ?? 0)).monospacedDigit().font(.subheadline)
                    }
                }
            }
        }
    }

    /// Each top donor with a bar per government whose officials it gave to. Fits the screen width (no sideways scrolling).
    @ViewBuilder private func heat(_ mm: MoneyMap) -> some View {
        let h = mm.heat(topDonors: 15)
        let maxCell = h.cells.values.flatMap(\.values).max() ?? 1
        Section {
            ForEach(h.donors) { d in
                let cells = h.govs.compactMap { g -> (gov: String, amount: Double)? in
                    let v = h.cells[d.id]?[g] ?? 0
                    return v > 0 ? (g, v) : nil
                }.sorted { $0.amount > $1.amount }
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(d.n).font(.subheadline.weight(.semibold)).lineLimit(2)
                        Spacer(minLength: 6)
                        Text(Format.compactMoney(cells.map(\.amount).reduce(0, +))).font(.subheadline.weight(.bold).monospacedDigit())
                    }
                    ForEach(cells, id: \.gov) { c in
                        HStack(spacing: 8) {
                            Text(Governments.names[c.gov]?.replacingOccurrences(of: "Bay District ", with: "") ?? c.gov)
                                .font(.caption).frame(width: 110, alignment: .leading).lineLimit(1).minimumScaleFactor(0.8)
                            MagnitudeBar(fraction: c.amount / maxCell, height: 8)
                            Text(Format.compactMoney(c.amount)).font(.caption.monospacedDigit()).frame(width: 56, alignment: .trailing)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(d.n) to \(Governments.names[c.gov] ?? c.gov): \(Format.money(c.amount))")
                    }
                }
                .padding(.vertical, 4)
            }
        } header: { Text("Who gave to which government's officials, top 15 donors") }
    }

    @ViewBuilder private func votes(_ mm: MoneyMap) -> some View {
        let vs = mm.vgroups.filter { gov == nil || $0.g == gov }
        Section {
            ForEach(vs.prefix(60)) { v in
                VStack(alignment: .leading, spacing: 4) {
                    Text(v.h ?? "Vote").font(.subheadline.weight(.medium))
                    Text([mm.donor(v.d)?.n, Dates.parse(v.date).map { Dates.display($0, hasTime: false) }, v.tally, v.amount.map { Format.compactMoney($0) }]
                        .compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                    ForEach(v.roll.filter { $0.gift != nil }, id: \.self) { m in
                        Text("\(m.n) voted \(m.vote ?? "—") · got \(Format.money(m.gift ?? 0)) from the donor\(m.when.map { $0 == "before" ? ", given after the vote" : ", given before the vote" } ?? "")")
                            .font(.caption2)
                    }
                }
                .padding(.vertical, 2)
            }
        } header: { Text("Votes on a donor's contract") } footer: {
            Text("Each vote approved a contract with a business that gave to at least one member's campaign.")
        }
    }
}
