import SwiftUI
import BayCountyKit

/// A person with initials, name and the site's one line about them, and a tag when they're a 2026 candidate.
struct PersonRow: View {
    let person: PeopleDirectory.Person

    private var isCandidate: Bool {
        (person.kinds ?? []).contains("candidate") || person.mainRoles.contains { ($0.role ?? "").hasPrefix("2026 candidate") }
    }

    var body: some View {
        HStack(spacing: 12) {
            PersonInitials(name: person.name, size: 38)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(person.name).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                    if isCandidate { Badge(text: "Candidate", color: Brand.amber) }
                }
                Text(person.headline.replacingOccurrences(of: "2026 candidate: ", with: "Running for "))
                    .font(.caption).foregroundStyle(.secondary).lineLimit(2).multilineTextAlignment(.leading)
            }
            Spacer(minLength: 4)
        }
        .padding(.vertical, 1)
    }
}

/// Initials on a circle tinted by name, like the site's people cards.
struct PersonInitials: View {
    let name: String
    var size: CGFloat = 38

    private var initials: String {
        name.split(separator: " ").filter { $0.first?.isLetter == true }.prefix(2).map { String($0.prefix(1)) }.joined()
    }
    private var tone: Tone {
        let tones: [Tone] = [.blue, .teal, .amber, .salmon]
        return tones[abs(name.unicodeScalars.reduce(0) { ($0 &* 31 &+ Int($1.value)) % 9973 }) % tones.count]
    }

    var body: some View {
        Text(initials).font(.system(size: size * 0.38, weight: .semibold)).foregroundStyle(tone.color)
            .frame(width: size, height: size)
            .background(tone.color.opacity(0.13), in: Circle())
            .accessibilityHidden(true)
    }
}

/// Officials, department leaders and candidates since 2016, grouped by government, with the site's filter chips.
struct PeopleView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var kind: PeopleKind = .everyone

    var body: some View {
        let q = query.lowercased()
        let all = store.people?.people ?? []
        let people = all.filter { kind.includes($0) && (q.isEmpty || $0.name.lowercased().contains(q)) }
        let counts = Dictionary(uniqueKeysWithValues: PeopleKind.allCases.map { k in (k, all.filter { k.includes($0) }.count) })
        PageScroll {
            PageHero(kicker: "Connections · People", title: "Officials and candidates",
                     subtitle: "Every elected official, department leader and local candidate since 2016 in these records. Rank-and-file employees appear only by job title, never by name.",
                     symbol: "person.3", tone: .teal)
            if !all.isEmpty {
                ChipRow(chips: PeopleKind.allCases.map { (id: $0, label: $0.label) }, selected: kind, counts: counts) { kind = $0 }
            }
            LazyVStack(alignment: .leading, spacing: 22) {
                ForEach(Governments.order, id: \.self) { g in
                    group(Governments.names[g] ?? g, people.filter { $0.gov_ids.first == g })
                }
                group("Other offices", people.filter { !Governments.order.contains($0.gov_ids.first ?? "") })
            }
            if !all.isEmpty && people.isEmpty {
                Text("No one matches.").font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .overlay { if store.people == nil { AppDataPending(file: "people.json", title: "Couldn't load people") { await store.loadPeople() } } }
        .navigationTitle("People")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: "Find a person")
        .task { await store.loadPeople() }
    }

    @ViewBuilder private func group(_ title: String, _ list: [PeopleDirectory.Person]) -> some View {
        if !list.isEmpty {
            let sorted = list.sorted { $0.name < $1.name }
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    Text(title).font(.headline)
                    Spacer()
                    Text("\(list.count)").font(.subheadline.monospacedDigit()).foregroundStyle(.secondary)
                }
                CardList {
                    ForEach(sorted) { p in
                        NavigationLink(value: Route.person(p.id)) {
                            HStack {
                                PersonRow(person: p)
                                Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 8)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        if p.id != sorted.last?.id { RowDivider(inset: 64) }
                    }
                }
            }
        }
    }
}

/// One official, leader or candidate: where they serve, the terms they held, pay, every campaign since 2016
/// with its money, gifts from businesses and business owners, and their recorded votes.
struct PersonDetailView: View {
    @Environment(AppStore.self) private var store
    let personID: String
    @State private var allGifts = false

    var body: some View {
        let p = store.person(personID)
        let recs = RecordLinks.records(forPerson: personID, in: store.rows)
        let byDS = Dictionary(uniqueKeysWithValues: recs.map { ($0.dataset, $0.rows) })
        PageScroll {
            PageHero(kicker: p?.label ?? "People", title: p?.name ?? "Person", subtitle: p?.headline) {
                PersonInitials(name: p?.name ?? "?", size: 52)
            }
            roles(p)
            terms(byDS)
            pay(byDS)
            campaigns(byDS)
            Group {
                businessGifts(byDS)
                ownerGifts(byDS)
                votes(byDS)
                donorContracts
                WebLink(title: "Profile and connections on BayCounty.me", symbol: "point.3.connected.trianglepath.dotted",
                        url: URL(string: "https://baycounty.me/people/\(personID)"))
                    .font(.subheadline)
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

    // MARK: Roles and terms

    @ViewBuilder private func roles(_ p: PeopleDirectory.Person?) -> some View {
        let main = p?.mainRoles ?? []
        if main.count > 1 {
            PageSection(title: "Where they serve", symbol: "building.columns", tone: .blue) {
                CardList {
                    ForEach(Array(main.enumerated()), id: \.offset) { i, r in
                        TextRow(title: (r.role.map { $0.prefix(1).uppercased() + $0.dropFirst() }) ?? "Role",
                                detail: [r.gov_id.flatMap { Governments.names[$0] }, r.seat.map { "Seat \($0)" }].compactMap { $0 }.joined(separator: " · "))
                        if i < main.count - 1 { RowDivider() }
                    }
                }
            }
        }
    }

    @ViewBuilder private func terms(_ byDS: [String: [Row]]) -> some View {
        let t = Officeholders.terms(byDS["officeholder-terms"] ?? [], personID: personID)
        if !t.isEmpty {
            PageSection(title: "Terms in office", symbol: "person.badge.clock", tone: .teal, caption: "Each seat they held since 2016, newest first.") {
                CardList {
                    ForEach(t) { term in
                        HStack(spacing: 12) {
                            GovBadge(govID: term.govID)
                            TextRow(title: term.seat + (term.appointed ? " (appointed)" : ""),
                                    detail: [term.government, term.years, term.how.map(Format.label)].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                        }
                        .padding(.leading, 14)
                        if term.id != t.last?.id { RowDivider(inset: 66) }
                    }
                }
            }
        }
    }

    // MARK: Pay

    @ViewBuilder private func pay(_ byDS: [String: [Row]]) -> some View {
        let rows = (byDS["officials-pay"] ?? []) + (byDS["salary-leaders"] ?? [])
        if !rows.isEmpty {
            PageSection(title: "Pay", symbol: "dollarsign.circle", tone: .amber) {
                let points = (byDS["officials-pay"] ?? []).compactMap { r -> (label: String, value: Double)? in
                    guard let v = r.firstNumber(["annual", "salary"]), let p = Period.of(r), p.fiscal else { return nil }
                    return (p.label, v)
                }
                let byLabel = Dictionary(points.map { ($0.label, $0.value) }, uniquingKeysWith: max)
                if byLabel.count >= 2 {
                    YearBars(title: "Pay by year", points: byLabel.keys.sorted().map { (label: $0, value: byLabel[$0]!) },
                             format: { Format.compactMoney($0) })
                }
                CardList {
                    ForEach(rows) { row in
                        FactRow(label: row.first(["title", "employer"]) ?? "Pay", value: Format.money(row.firstNumber(["annual", "salary"])),
                                detail: row.first(["year", "as_of"]))
                        if row.id != rows.last?.id { RowDivider() }
                    }
                }
            }
        }
    }

    // MARK: Campaigns

    private struct Campaign: Identifiable {
        let id: String
        let year: Int
        let title: String
        let detail: String
        let outcome: String?
        let raised: Double?
        let spent: Double?
        let report: URL?
    }

    /// Every campaign: the 2026 race and latest winning race, then every race since 2016 not already listed.
    private func campaignList(_ byDS: [String: [Row]]) -> [Campaign] {
        var out: [Campaign] = []
        for r in (byDS["candidates-2026"] ?? []) + (byDS["campaign-finance"] ?? []) {
            let election = r.first(["election"]) ?? "2026"
            let year = Int(election.prefix(4)) ?? 2026
            out.append(Campaign(id: "c\(r.id)-\(election)", year: year, title: r.first(["office", "race"]) ?? election, detail: election,
                                outcome: year >= 2026 ? "On the ballot" : nil, raised: r.number("total_raised"), spent: r.number("total_spent"),
                                report: r.url("report_url") ?? r.url("finance_report_url")))
        }
        let have = Set(out.map { "\($0.year)" })
        for r in byDS["campaign-history"] ?? [] {
            let year = r.number("election_year").map(Int.init) ?? 0
            if have.contains("\(year)") { continue }
            out.append(Campaign(id: "h\(r.id)", year: year, title: r.string("office") ?? "Campaign", detail: r.string("election") ?? "\(year)",
                                outcome: r.string("outcome"), raised: r.number("total_raised"), spent: r.number("total_spent"), report: r.url("source_url")))
        }
        return out.sorted { $0.year > $1.year }
    }

    @ViewBuilder private func campaigns(_ byDS: [String: [Row]]) -> some View {
        let list = campaignList(byDS)
        if !list.isEmpty {
            PageSection(title: "Campaigns", symbol: "flag", tone: .salmon, caption: "Every local race since 2016, with what the campaign raised and spent.") {
                CardList {
                    ForEach(list) { c in
                        campaignRow(c)
                        if c.id != list.last?.id { RowDivider() }
                    }
                }
            }
        }
    }

    private func campaignRow(_ c: Campaign) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(c.title).font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 4)
                if let o = c.outcome { Badge(text: Format.label(o), color: o == "won" ? Brand.good : o == "lost" ? Brand.salmon : Brand.amber) }
            }
            Text(c.detail).font(.caption).foregroundStyle(.secondary)
            if let r = c.raised {
                let spent = c.spent ?? 0
                let maxV = max(r, spent, 1)
                moneyBar("Raised", r, r / maxV)
                if c.spent != nil { moneyBar("Spent", spent, spent / maxV) }
            }
            if let u = c.report {
                Button("Campaign finance reports") { store.open(u) }.font(.caption.weight(.semibold)).buttonStyle(.borderless)
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
    }

    private func moneyBar(_ label: String, _ v: Double, _ fraction: Double) -> some View {
        HStack(spacing: 8) {
            Text(label).font(.caption).frame(width: 48, alignment: .leading)
            MagnitudeBar(fraction: fraction, height: 8)
            Text(Format.compactMoney(v)).font(.caption.weight(.semibold).monospacedDigit()).frame(width: 60, alignment: .trailing)
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Gifts

    /// Gifts from businesses and groups, summed by giver.
    @ViewBuilder private func businessGifts(_ byDS: [String: [Row]]) -> some View {
        let rows = byDS["business-donor-sunbiz"] ?? []
        if !rows.isEmpty {
            let givers = Self.givers(rows)
            let shown = allGifts ? givers : Array(givers.prefix(10))
            let total = givers.map(\.value.amount).reduce(0, +)
            PageSection(title: "Campaign gifts from businesses and groups", symbol: "envelope", tone: .amber,
                        caption: "\(givers.count) businesses and groups gave \(Format.compactMoney(total)) across their campaigns. Gifts from private individuals are never named.") {
                CardList {
                    ForEach(shown, id: \.key) { g in
                        if let v = g.value.vendor {
                            RecordLinkRow(route: .vendor(v), title: g.key, detail: "\(g.value.gifts) gift\(g.value.gifts == 1 ? "" : "s") · holds local contracts",
                                          value: Format.compactMoney(g.value.amount))
                        } else {
                            TextRow(title: g.key, detail: "\(g.value.gifts) gift\(g.value.gifts == 1 ? "" : "s")", value: Format.compactMoney(g.value.amount))
                        }
                        if g.key != shown.last?.key { RowDivider() }
                    }
                    if givers.count > 10 {
                        RowDivider()
                        Button(allGifts ? "Show fewer" : "All \(givers.count) givers") { allGifts.toggle() }
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
                    }
                }
            }
        }
    }

    private typealias Giver = (key: String, value: (amount: Double, gifts: Int, vendor: String?))

    private static func givers(_ rows: [Row]) -> [Giver] {
        var sums: [String: (amount: Double, gifts: Int, vendor: String?)] = [:]
        for r in rows {
            let k = r.string("contributor") ?? "Unknown"
            let old = sums[k] ?? (0, 0, nil)
            sums[k] = (old.amount + (r.number("contribution_amount") ?? 0), old.gifts + Int(r.number("contribution_items") ?? 1), old.vendor ?? r.string("vendor_id"))
        }
        return sums.map { (key: $0.key, value: $0.value) }.sorted { $0.value.amount > $1.value.amount }
    }

    /// People who run a registered business and gave (named by Jeremy's rule; never their address or job).
    @ViewBuilder private func ownerGifts(_ byDS: [String: [Row]]) -> some View {
        let rows = (byDS["owner-gifts"] ?? []).sorted { ($0.number("amount") ?? 0) > ($1.number("amount") ?? 0) }
        if !rows.isEmpty {
            PageSection(title: "Business owners who gave", symbol: "person.text.rectangle", tone: .blue,
                        caption: "Donors whose name and street address match an officer, manager or registered agent of a Florida business.") {
                CardList {
                    ForEach(rows.prefix(15)) { r in
                        TextRow(title: r.string("donor") ?? "", detail: [r.string("businesses"), r.string("election")].compactMap { $0 }.joined(separator: " · "),
                                value: shortMoney(r.number("amount")))
                        if r.id != rows.prefix(15).last?.id { RowDivider() }
                    }
                    if rows.count > 15 {
                        RowDivider()
                        RouteRow(route: .dataset("owner-gifts", filters: ["candidate_id": personID]), title: "All \(rows.count)")
                    }
                }
            }
        }
    }

    // MARK: Votes

    @ViewBuilder private func votes(_ byDS: [String: [Row]]) -> some View {
        if let mv = byDS["member-votes"], !mv.isEmpty {
            let t = RecordLinks.tally(mv)
            let latest = Array(mv.sorted { ($0.string("date") ?? "") > ($1.string("date") ?? "") }.prefix(25))
            PageSection(title: "Recorded votes on money decisions", symbol: "hand.raised", tone: .teal) {
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(t.total) recorded votes").font(.subheadline.weight(.semibold))
                    ShareBar(parts: [.init(label: "Yes", value: Double(t.yes), color: Brand.good),
                                     .init(label: "No", value: Double(t.no), color: Brand.salmon),
                                     .init(label: "Absent", value: Double(t.other), color: Color.secondary.opacity(0.35))])
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .card(14)
                CardList {
                    ForEach(latest) { row in
                        NavigationLink(value: Route.record("member-votes", rowID: row.id)) {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(row.string("headline") ?? "Vote").font(.subheadline).foregroundStyle(.primary).lineLimit(2).multilineTextAlignment(.leading)
                                    Text(row.string("date").flatMap(Dates.parse).map { Dates.display($0, hasTime: false) } ?? "").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                let v = (row.string("vote") ?? "").lowercased()
                                VoteMark(choice: v == "yes" ? .yes : v == "no" ? .no : .other)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        if row.id != latest.last?.id { RowDivider() }
                    }
                    if mv.count > latest.count {
                        RowDivider()
                        RouteRow(route: .dataset("member-votes", filters: ["person_id": personID]), title: "All \(mv.count) votes")
                    }
                }
            }
        }
    }

    @ViewBuilder private var donorContracts: some View {
        let gifts = store.donorContracts?.matches.filter { $0.person_id == personID } ?? []
        if !gifts.isEmpty {
            PageSection(title: "Business donors that hold local contracts", symbol: "link", tone: .salmon,
                        caption: "A gift near a vote does not show why anyone voted the way they did.") {
                CardList {
                    ForEach(gifts) { m in
                        DonorMatchRow(match: m, showCandidate: false).padding(.horizontal, 14).padding(.vertical, 8)
                        if m.id != gifts.last?.id { RowDivider() }
                    }
                }
            }
        }
    }
}
