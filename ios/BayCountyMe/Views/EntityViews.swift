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
            Section {
                Text("Every company or organization paid by a Bay County government, CRA or tourism agency, with its contracts, payments, the votes that approved them and gifts from the business to campaigns. A gift near a vote does not show why anyone voted the way they did.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            Section("\(list.count) companies") {
                ForEach(list.prefix(400)) { v in
                    NavigationLink(value: Route.vendor(v.id)) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(v.name).font(.subheadline.weight(.medium))
                            Text(v.records.sorted { $0.value > $1.value }.map { "\($0.value) \(Self.kind($0.key))" }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .overlay { if store.vendors == nil { ProgressView() } }
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
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text(v?.name ?? "Company").font(.title3.weight(.semibold))
                    if let v, !v.gov_ids.isEmpty {
                        Text(v.gov_ids.compactMap { Governments.names[$0] ?? Self.agency[$0] }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                    }
                    if let a = v?.aliases, !a.isEmpty {
                        Text("Also spelled: " + a.prefix(5).joined(separator: "; ")).font(.caption2).foregroundStyle(.secondary)
                    }
                }
            }
            let recs = RecordLinks.records(forVendor: vendorID, in: store.rows)
            ForEach(recs, id: \.dataset) { group in
                let spec = DatasetSpec.for(group.dataset)
                Section(store.info(group.dataset)?.title ?? Format.label(group.dataset)) {
                    ForEach(group.rows.prefix(25)) { row in
                        NavigationLink(value: Route.record(group.dataset, rowID: row.id)) { RecordRow(spec: spec, row: row) }
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
                        NavigationLink(value: Route.record("votes", rowID: row.id)) { RecordRow(spec: DatasetSpec.for("votes"), row: row) }
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
        }
        .navigationTitle(v?.name ?? "Company")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadVendors()
            await store.loadDonorContracts()
            await store.load(RecordLinks.vendorDatasets + ["votes"])
        }
    }

    static let agency = ["visit_pcb": "Visit Panama City Beach", "destination_pc": "Destination Panama City", "mb_cdc": "Mexico Beach CDC",
                         "sheriff": "Sheriff", "airport": "Airport", "port": "Port Panama City"]
}

/// Officials, department leaders and candidates.
struct PeopleView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""

    var body: some View {
        let q = query.lowercased()
        let people = (store.people?.people ?? []).filter { q.isEmpty || $0.name.lowercased().contains(q) }
        List {
            Section {
                Text("Elected officials, department leaders and 2026 local candidates named in the site's records. Rank-and-file employees appear only by job title, never by name.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(Governments.order, id: \.self) { g in
                let inGov = people.filter { $0.gov_ids.first == g }
                if !inGov.isEmpty {
                    Section(Governments.names[g] ?? g) {
                        ForEach(inGov.sorted { $0.name < $1.name }) { p in
                            NavigationLink(value: Route.person(p.id)) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(p.name).font(.subheadline.weight(.medium))
                                    Text(p.headline).font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            let other = people.filter { !Governments.order.contains($0.gov_ids.first ?? "") }
            if !other.isEmpty {
                Section("Other offices") {
                    ForEach(other.sorted { $0.name < $1.name }) { p in
                        NavigationLink(value: Route.person(p.id)) { Text(p.name) }
                    }
                }
            }
        }
        .overlay { if store.people == nil { ProgressView() } }
        .navigationTitle("People")
        .searchable(text: $query, prompt: "Find a person")
        .task { await store.loadPeople() }
    }
}

/// One official or candidate: roles, pay, voting record and campaign money.
struct PersonDetailView: View {
    @Environment(AppStore.self) private var store
    let personID: String

    var body: some View {
        let p = store.person(personID)
        let recs = RecordLinks.records(forPerson: personID, in: store.rows)
        let byDS = Dictionary(uniqueKeysWithValues: recs.map { ($0.dataset, $0.rows) })
        List {
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text(p?.name ?? "Person").font(.title3.weight(.semibold))
                    if let p { Text(p.headline).font(.subheadline).foregroundStyle(.secondary) }
                }
                ForEach(Array((p?.roles ?? []).enumerated()), id: \.offset) { _, r in
                    Text([r.role.map { $0.prefix(1).uppercased() + $0.dropFirst() }, r.gov_id.flatMap { Governments.names[$0] }, r.seat.map { "seat \($0)" }]
                        .compactMap { $0 }.joined(separator: ", ")).font(.caption)
                }
            }
            payAndMoney(byDS)
            if let mv = byDS["member-votes"], !mv.isEmpty {
                let t = RecordLinks.tally(mv)
                Section {
                    HStack(spacing: 16) {
                        StatTile(title: "Yes", value: "\(t.yes)")
                        StatTile(title: "No", value: "\(t.no)")
                        StatTile(title: "Other", value: "\(t.other)", caption: "Absent or abstained")
                    }
                    .listRowInsets(EdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12))
                    ForEach(mv.sorted { ($0.string("date") ?? "") > ($1.string("date") ?? "") }.prefix(40)) { row in
                        NavigationLink(value: Route.record("member-votes", rowID: row.id)) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(row.string("headline") ?? "Vote").font(.subheadline).lineLimit(2)
                                    Text(row.string("date").flatMap(Dates.parse).map { Dates.display($0, hasTime: false) } ?? "").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                let v = (row.string("vote") ?? "").capitalized
                                Badge(text: v, color: v == "Yes" ? Brand.good : v == "No" ? Brand.salmon : .secondary)
                            }
                        }
                    }
                    if mv.count > 40 {
                        NavigationLink(value: Route.dataset("member-votes", filters: ["person_id": personID])) { Text("All \(mv.count) votes") }
                    }
                } header: { Text("Recorded votes on money decisions") }
            }
            let gifts = store.donorContracts?.matches.filter { $0.person_id == personID } ?? []
            if !gifts.isEmpty {
                Section {
                    ForEach(gifts) { DonorMatchRow(match: $0, showCandidate: false) }
                } header: { Text("Business donors that hold local contracts") } footer: {
                    Text("A gift near a vote does not show why anyone voted the way they did.")
                }
            }
        }
        .navigationTitle(p?.name ?? "Person")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadPeople()
            await store.loadDonorContracts()
            await store.load(RecordLinks.personDatasets)
        }
    }

    @ViewBuilder private func payAndMoney(_ byDS: [String: [Row]]) -> some View {
        let pay = (byDS["officials-pay"] ?? []) + (byDS["salary-leaders"] ?? [])
        if !pay.isEmpty {
            Section("Pay") {
                ForEach(pay) { row in
                    LabeledContent(row.first(["title", "employer"]) ?? "Pay") {
                        VStack(alignment: .trailing) {
                            Text(Format.money(row.firstNumber(["annual", "salary"]))).monospacedDigit()
                            Text(row.first(["year", "as_of"]) ?? "").font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        let money = (byDS["campaign-finance"] ?? []) + (byDS["candidates-2026"] ?? [])
        if !money.isEmpty {
            Section("Campaign money") {
                ForEach(money) { row in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(row.first(["election", "office"]) ?? "Campaign").font(.subheadline.weight(.medium))
                        HStack {
                            if let r = row.number("total_raised") { Text("Raised \(Format.money(r))") }
                            if let s = row.number("total_spent") { Text("· spent \(Format.money(s))") }
                        }
                        .font(.caption)
                        if let u = row.url("report_url") ?? row.url("finance_report_url") {
                            Button("Campaign finance reports") { store.open(u) }.font(.caption).buttonStyle(.borderless)
                        }
                    }
                }
            }
        }
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
                    NavigationLink(value: Route.vendor(vid)) { Text(match.vendor ?? match.contributor ?? vid).font(.subheadline.weight(.medium)) }
                } else {
                    Text(showCandidate ? (match.candidate ?? "") : (match.contributor ?? "")).font(.subheadline.weight(.medium))
                }
                Spacer()
                if let a = match.contribution_amount { Text(Format.money(a)).monospacedDigit() }
            }
            Text([match.office, match.election].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
            if let items = match.contract_ids_or_descriptions, !items.isEmpty {
                Text(items.prefix(2).joined(separator: "\n")).font(.caption2)
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

    var body: some View {
        let all = store.donorContracts?.matches ?? []
        let list = sameOnly ? all.filter { $0.same_government_as_office == true } : all
        let byVendor = Dictionary(grouping: list) { $0.vendor_id ?? $0.contributor ?? "" }
            .sorted { $0.value.compactMap(\.contribution_amount).reduce(0, +) > $1.value.compactMap(\.contribution_amount).reduce(0, +) }
        List {
            Section {
                Text("Businesses that gave to a local campaign and also hold a contract, grant or payment from a Bay County government. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.")
                    .font(.footnote).foregroundStyle(.secondary)
                Toggle("Only where the contract is with the same government", isOn: $sameOnly)
            }
            ForEach(byVendor, id: \.key) { key, ms in
                Section {
                    ForEach(ms) { DonorMatchRow(match: $0) }
                } header: {
                    if let vid = ms.first?.vendor_id {
                        NavigationLink(value: Route.vendor(vid)) { Text(ms.first?.vendor ?? key) }
                    } else { Text(ms.first?.contributor ?? key) }
                }
            }
            if let m = store.donorContracts?.method { Section("Method") { Text(m).font(.footnote) } }
        }
        .overlay { if store.donorContracts == nil { ProgressView() } }
        .navigationTitle("Donors with contracts")
        .task { await store.loadDonorContracts() }
    }
}

/// Money Map: which businesses gave to which officials, and the votes on those donors' contracts.
struct MoneyMapView: View {
    @Environment(AppStore.self) private var store
    enum Mode: String, CaseIterable, Identifiable { case officials = "Officials", donors = "Donors", heat = "Heat map", votes = "Votes"; var id: String { rawValue } }
    @State private var mode: Mode = .officials
    @State private var gov: String? = nil

    var body: some View {
        List {
            Section {
                Picker("View", selection: $mode) { ForEach(Mode.allCases) { Text($0.rawValue).tag($0) } }.pickerStyle(.segmented)
                Text("Gifts from businesses and organizations to the campaigns of current officials, and where those donors hold local government contracts. Individual donors are never named. A gift near a vote does not show why anyone voted the way they did.")
                    .font(.footnote).foregroundStyle(.secondary)
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

    @ViewBuilder private func heat(_ mm: MoneyMap) -> some View {
        let h = mm.heat(topDonors: 15)
        let maxCell = h.cells.values.flatMap(\.values).max() ?? 1
        Section {
            ScrollView(.horizontal) {
                Grid(alignment: .leading, horizontalSpacing: 4, verticalSpacing: 4) {
                    GridRow {
                        Text("").frame(width: 150)
                        ForEach(h.govs, id: \.self) { g in
                            Text(Governments.names[g]?.replacingOccurrences(of: "Bay District ", with: "") ?? g)
                                .font(.caption2).frame(width: 64).lineLimit(2).multilineTextAlignment(.center)
                        }
                    }
                    ForEach(h.donors) { d in
                        GridRow {
                            Text(d.n).font(.caption).lineLimit(2).frame(width: 150, alignment: .leading)
                            ForEach(h.govs, id: \.self) { g in
                                let v = h.cells[d.id]?[g] ?? 0
                                RoundedRectangle(cornerRadius: 4)
                                    .fill(v > 0 ? Brand.salmon.opacity(0.15 + 0.85 * v / maxCell) : Brand.sunken)
                                    .frame(width: 64, height: 30)
                                    .overlay { if v > 0 { Text(Format.compactMoney(v)).font(.caption2.monospacedDigit()) } }
                                    .accessibilityLabel("\(d.n) to \(Governments.names[g] ?? g): \(Format.money(v))")
                            }
                        }
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
