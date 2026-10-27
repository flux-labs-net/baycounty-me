import SwiftUI
import BayCountyKit

/// One government, in the same order as its page on BayCounty.me: at a glance, who's in charge, the money,
/// how it compares, meetings, debt, audit findings, savings ideas and its redevelopment agency.
struct GovernmentDetailView: View {
    @Environment(AppStore.self) private var store
    let govID: String
    @State private var year: Int?
    @State private var allFindings = false
    @State private var allBonds = false

    /// Datasets this screen reads, besides the government profiles.
    private static let datasets = ["officeholder-terms", "budget-years", "debt", "bonds", "audit-findings", "savings-opportunities", "cra-agencies"]

    /// A city page includes its port; the county page includes the airport district (as on the site).
    private var debtIDs: Set<String> {
        var ids: Set<String> = [govID]
        if govID == "pc" { ids.insert("port") }
        if govID == "county" { ids.insert("airport") }
        return ids
    }

    private func rows(_ id: String) -> [Row] { store.rows[id] ?? [] }

    /// Datasets that carry a gov_id column, so they can be filtered to this government.
    private var related: [DatasetInfo] {
        (store.catalog?.datasets ?? []).filter { !DatasetSpec.ownScreens.contains($0.id) && $0.column("gov_id") != nil }
    }

    var body: some View {
        if let g = store.government(govID) {
            PageScroll {
                PageHero(kicker: "Governments", title: g.name,
                         subtitle: g.population.map { "\(Format.number($0)) residents (2025 estimate)" }) {
                    GovBadge(govID: govID).scaleEffect(1.2).frame(width: 48, height: 48)
                }
                glance(g)
                whosInCharge
                moneySection(g)
                compared(g)
                meetingsSection
                Group {
                    debtSection
                    auditSection
                    savingsSection
                    craSection
                    recordsSection(g)
                }
            }
            .navigationTitle(g.name)
            .navigationBarTitleDisplayMode(.inline)
            .task {
                await store.load(Self.datasets)
                await store.loadPeople()
            }
            .refreshable { for d in Self.datasets { await store.load(d, force: true) } }
        } else {
            ContentUnavailableView("Not found", systemImage: "building.columns")
        }
    }

    // MARK: At a glance

    private func glance(_ g: Government) -> some View {
        PageSection(title: "At a glance", symbol: "gauge.with.dots.needle.33percent", tone: .blue) {
            StatGrid {
                if let v = g.budgetTotal { KPICard(title: "Total budget", value: Format.compactMoney(v), caption: g.budgetStatus) }
                if let v = g.budgetPerResident { KPICard(title: "Budget per resident", value: Format.money(v.rounded())) }
                if let v = g.generalFund { KPICard(title: "General fund", value: Format.compactMoney(v)) }
                if let v = g.propertyTaxLevy { KPICard(title: "Property tax levied", value: Format.compactMoney(v)) }
                if let v = g.millage { KPICard(title: "Tax rate (mills)", value: Format.number(v), caption: "Per $1,000 of taxable value") }
                if let v = g.debtTotal { KPICard(title: "Debt", value: Format.compactMoney(v), caption: g.debtPerResident.map { "\(Format.money($0.rounded())) per resident" }) }
                if let v = g.auditFindings { KPICard(title: "Audit findings", value: "\(v)", caption: [g.auditYear, g.repeatFindings.map { "\($0) repeat" }].compactMap { $0 }.joined(separator: " · ")) }
                if let v = g.votesRecorded { KPICard(title: "Votes recorded", value: "\(v)", caption: g.splitVotes.map { "\($0) split" }) }
                if let v = g.typicalUtilityBill { KPICard(title: "Typical utility bill", value: Format.money(v), caption: "Per month") }
                if let v = g.femaMichael { KPICard(title: "FEMA, Hurricane Michael", value: Format.compactMoney(v)) }
            }
        }
    }

    // MARK: Who's in charge

    @ViewBuilder private var whosInCharge: some View {
        let terms = rows("officeholder-terms")
        let years = Officeholders.years(terms, gov: govID)
        if let picked = year ?? years.first {
            let seats = Officeholders.inOffice(terms, gov: govID, year: picked)
            PageSection(title: "Who's in charge", symbol: "person.3", tone: .teal,
                        caption: "Who held each seat in fiscal year \(String(picked)). Pick another year to see who served then.") {
                Menu {
                    ForEach(years, id: \.self) { y in Button("FY\(String(y))") { year = y } }
                } label: {
                    HStack(spacing: 6) {
                        Text("FY\(String(picked))").font(.subheadline.weight(.semibold).monospacedDigit())
                        Image(systemName: "chevron.up.chevron.down").font(.caption2)
                    }
                    .padding(.horizontal, 16)
                    .frame(minHeight: 44)
                    .card(22)
                }
                .accessibilityLabel("Fiscal year \(String(picked))")
                CardList {
                    ForEach(seats) { s in
                        seatRow(s)
                        if s.id != seats.last?.id { RowDivider() }
                    }
                }
                NavigationLink(value: Route.people) {
                    Label("Everyone in office and on the ballot", systemImage: "person.3").font(.subheadline.weight(.semibold))
                }
                .foregroundStyle(Brand.navy)
            }
        }
    }

    private func seatRow(_ s: Officeholders.Seat) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(s.seat + (s.appointed ? " (appointed)" : "")).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            if s.holders.isEmpty {
                Text("No one on record").font(.subheadline).foregroundStyle(.secondary)
            }
            ForEach(s.holders) { h in
                let line = holderLine(h)
                if let pid = h.personID, store.person(pid) != nil {
                    NavigationLink(value: Route.person(pid)) {
                        HStack {
                            holderText(h, line)
                            Spacer(minLength: 4)
                            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                } else {
                    holderText(h, line)
                }
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func holderText(_ h: Officeholders.Holder, _ line: String) -> some View {
        HStack(spacing: 12) {
            // their official photo (official-photos), or initials, like the site's "Who's in charge" cards
            if !h.vacant && !h.personName.isEmpty {
                PersonInitials(name: h.personName, size: 36, photo: h.personID.flatMap { store.person($0) }?.photoURL)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(h.vacant ? "Vacant" : h.personName.isEmpty ? "Not confirmed" : h.personName)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(h.vacant || h.personName.isEmpty ? Color.secondary : Color.primary)
                if !line.isEmpty { Text(line).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            }
        }
    }

    private func holderLine(_ h: Officeholders.Holder) -> String {
        var parts: [String] = []
        if h.partOfPeriod {
            let s = h.startDate.map { "from \(Self.short($0))" }, e = h.endDate.map { "until \(Self.short($0))" }
            let range = [s, e].compactMap { $0 }
            parts.append("Part of the year" + (range.isEmpty ? "" : ", " + range.joined(separator: " ")))
        }
        if !h.confirmed { parts.append("Not confirmed from the records found") }
        return parts.joined(separator: " · ")
    }

    /// "2024-11-19" → "Nov 2024".
    static func short(_ d: String) -> String {
        guard let date = Dates.parse(d) else { return d }
        let f = DateFormatter(); f.dateFormat = "MMM yyyy"; f.timeZone = TimeZone(identifier: "America/Chicago")
        return f.string(from: date)
    }

    // MARK: Money

    @ViewBuilder private func moneySection(_ g: Government) -> some View {
        let budgets = rows("budget-years")
        let latest = BudgetCompare.compare(budgets, gov: govID)
        PageSection(title: "Money in, money out", symbol: "chart.pie", tone: .amber,
                    caption: latest.map { "Adopted budget, FY\(String($0.to)), and how it changed from FY\(String($0.from))." }) {
            if let r = latest, let funds = r.sections.first(where: { $0.key == "fund" }), funds.lines.contains(where: { $0.to != nil }) {
                let top = Array(funds.lines.filter { ($0.to ?? 0) > 0 }.sorted { ($0.to ?? 0) > ($1.to ?? 0) }.prefix(6))
                CompareBars(title: "Where the money is budgeted, by fund", caption: "Top \(top.count) funds, FY\(String(r.to))",
                            items: top.map { CompareBars.Item(id: $0.key, label: $0.name, value: $0.to ?? 0) }, format: Format.compactMoney, labelsAbove: true)
            }
            CardList {
                RouteRow(route: .budgetCompare(govID: govID), title: "Compare two budget years", symbol: "arrow.left.arrow.right")
                RowDivider(inset: 50)
                RouteRow(route: .dataset("budget-detail", filters: ["gov_id": govID]), title: "Every budget line", symbol: "list.bullet.rectangle")
                RowDivider(inset: 50)
                RouteRow(route: .taxCalculator(), title: "Your property tax bill", symbol: "percent")
            }
        }
    }

    // MARK: Compared with the others

    private func compared(_ g: Government) -> some View {
        PageSection(title: "Compared with the others", symbol: "chart.bar.xaxis", tone: .blue) {
            VStack(spacing: 12) {
                ForEach([GovMetric.perResident, .millage, .debt], id: \.self) { m in
                    let items = m.items(store.governments)
                    if items.contains(where: { $0.id == govID }) {
                        CompareBars(title: m.title, caption: m.caption, items: items, highlight: govID, format: m.format)
                    }
                }
                if let v = g.votesRecorded, let sv = g.splitVotes, v > 0 {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Recorded votes").font(.subheadline.weight(.semibold))
                        ShareBar(parts: [.init(label: "Unanimous", value: Double(v - sv), color: Brand.good),
                                         .init(label: "Split", value: Double(sv), color: Brand.amber)])
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .card(12)
                }
            }
        }
    }

    // MARK: Meetings

    @ViewBuilder private var meetingsSection: some View {
        let upcoming = Array(Meeting.upcoming(store.meetings).filter { $0.govID == govID }.prefix(3))
        if !upcoming.isEmpty {
            PageSection(title: "Upcoming meetings", symbol: "calendar", tone: .salmon) {
                CardList {
                    ForEach(upcoming) { m in
                        NavigationLink(value: Route.meeting(m.id)) { TodayMeetingRow(meeting: m) }.buttonStyle(.plain)
                        if m.id != upcoming.last?.id { RowDivider(inset: 66) }
                    }
                }
            }
        }
    }

    // MARK: Debt

    @ViewBuilder private var debtSection: some View {
        let debt = rows("debt").filter { debtIDs.contains($0.string("gov_id") ?? "") }
        let bonds = rows("bonds").filter { debtIDs.contains($0.string("gov_id") ?? "") }
            .sorted { ($0.number("outstanding") ?? 0) > ($1.number("outstanding") ?? 0) }
        if !debt.isEmpty || !bonds.isEmpty {
            PageSection(title: "Debt", symbol: "creditcard", tone: .salmon,
                        caption: "What it owes, from its latest audit, and every bond, note and loan behind it.") {
                if !debt.isEmpty {
                    CardList {
                        ForEach(debt) { d in
                            FactRow(label: d.string("government") ?? "Total debt", value: shortMoney(d.number("total_debt")),
                                    detail: d.string("fy"))
                            if d.id != debt.last?.id { RowDivider() }
                        }
                    }
                }
                if !bonds.isEmpty {
                    let shown = allBonds ? bonds : Array(bonds.prefix(5))
                    CardList {
                        ForEach(shown) { b in
                            RecordLinkRow(route: .record("bonds", rowID: b.id), title: b.string("series") ?? b.string("issuer") ?? "Bond",
                                          detail: [b.string("type").map(Format.label), b.string("interest_rate"), b.string("final_maturity").map { "matures \($0)" }]
                                            .compactMap { $0 }.joined(separator: " · "),
                                          value: shortMoney(b.number("outstanding") ?? b.number("par_amount")))
                            if b.id != shown.last?.id { RowDivider() }
                        }
                        if bonds.count > 5 {
                            RowDivider()
                            Button(allBonds ? "Show fewer" : "All \(bonds.count) bonds and loans") { allBonds.toggle() }
                                .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
                        }
                    }
                }
            }
        }
    }

    // MARK: Audits

    @ViewBuilder private var auditSection: some View {
        let findings = rows("audit-findings").filter { $0.string("gov_id") == govID }
            .sorted { ($0.string("fy") ?? "") > ($1.string("fy") ?? "") }
        if !findings.isEmpty {
            let shown = allFindings ? findings : Array(findings.prefix(4))
            PageSection(title: "What the auditors found", symbol: "magnifyingglass", tone: .amber,
                        caption: "Findings from the outside audits, newest first, in plain English.") {
                CardList {
                    ForEach(shown) { f in
                        NavigationLink(value: Route.record("audit-findings", rowID: f.id)) {
                            HStack(alignment: .top, spacing: 8) {
                                VStack(alignment: .leading, spacing: 4) {
                                    HStack(spacing: 6) {
                                        Text(String((f.string("fy") ?? "").prefix(6))).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                                        if f.bool("repeat") == true { Badge(text: "Repeat", color: Brand.salmon) }
                                    }
                                    Text(f.string("plain_english") ?? f.string("finding") ?? "")
                                        .font(.subheadline).foregroundStyle(.primary).lineLimit(4).multilineTextAlignment(.leading)
                                }
                                Spacer(minLength: 4)
                                Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 11)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        if f.id != shown.last?.id { RowDivider() }
                    }
                    if findings.count > 4 {
                        RowDivider()
                        Button(allFindings ? "Show fewer" : "All \(findings.count) findings") { allFindings.toggle() }
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44)
                    }
                }
            }
        }
    }

    // MARK: Savings

    @ViewBuilder private var savingsSection: some View {
        let ideas = rows("savings-opportunities").filter { $0.string("gov_id") == govID || $0.strings("gov_ids").contains(govID) }
        if !ideas.isEmpty {
            PageSection(title: "Where it could spend less", symbol: "dollarsign.arrow.circlepath", tone: .teal,
                        caption: "Estimates from the public records, with the next step to check each one.") {
                CardList {
                    ForEach(ideas) { i in
                        let low = i.number("savings_low"), high = i.number("savings_high")
                        RecordLinkRow(route: .record("savings-opportunities", rowID: i.id), title: i.string("title") ?? "Savings idea",
                                      detail: [i.string("lever"), i.string("confidence").map { "\($0) confidence" }].compactMap { $0 }.joined(separator: " · "),
                                      value: low.map { l in high.map { "\(Format.compactMoney(l))–\(Format.compactMoney($0))" } ?? Format.compactMoney(l) })
                        if i.id != ideas.last?.id { RowDivider() }
                    }
                }
            }
        }
    }

    // MARK: CRA

    @ViewBuilder private var craSection: some View {
        let cras = rows("cra-agencies").filter { $0.string("gov_id") == govID }
        if !cras.isEmpty {
            PageSection(title: "Redevelopment (CRA)", symbol: "building.2", tone: .blue,
                        caption: "Property tax on growth inside the district goes to the CRA instead of the general budget.") {
                CardList {
                    ForEach(cras) { c in
                        FactRow(label: c.string("cra") ?? "CRA", value: shortMoney(c.number("increment_fy2025")),
                                detail: "Tax increment, FY2025 · base year \(c.string("base_year") ?? "?")")
                        RowDivider()
                    }
                    RouteRow(route: .dataset("cra-payments", filters: ["gov_id": govID]), title: "What it spent the money on", symbol: "list.bullet")
                    RowDivider(inset: 50)
                    RouteRow(route: .craIncrement, title: "Tax increment for every CRA", symbol: "percent")
                }
            }
        }
    }

    // MARK: Records

    private func recordsSection(_ g: Government) -> some View {
        PageSection(title: "Every record", symbol: "tray.full", tone: .blue, caption: "Each dataset, filtered to \(g.name).") {
            CardList {
                ForEach(related) { d in
                    RouteRow(route: .dataset(d.id, filters: ["gov_id": govID]), title: d.title, symbol: DatasetSpec.for(d.id).symbol)
                    if d.id != related.last?.id { RowDivider(inset: 50) }
                }
            }
            WebLink(title: "Full profile on BayCounty.me", url: g.pageURL).font(.subheadline)
        }
    }
}
