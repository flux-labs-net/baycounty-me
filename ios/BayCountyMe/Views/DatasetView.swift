import SwiftUI
import BayCountyKit

/// Any dataset on the site. Opens on the current year, newest first, with a summary (headline numbers, a chart
/// by month or year, the biggest names), then the records grouped by month (or government, company…) in compact
/// rows with a bar showing each amount's size. Table mode lines records up in sortable columns; Map mode plots them.
/// Votes get their own layout: grouped by meeting, with each member's vote as a dot.
struct DatasetView: View {
    @Environment(AppStore.self) private var store
    let datasetID: String
    let preset: [String: String]

    enum Sort: String, CaseIterable, Identifiable {
        case standard = "Site order"
        case amount = "Largest first"
        case newest = "Newest first"
        case name = "A to Z"
        var id: String { rawValue }
    }

    enum Mode: String, CaseIterable { case list = "List", table = "Table", map = "Map" }

    @State private var query = ""
    @State private var filters: [String: String] = [:]
    @State private var sortChoice: Sort?
    /// Year the list shows; nil means every year.
    @State private var period: Period?
    @State private var years = YearIndex()
    @State private var mode: Mode = .list
    @State private var path: Route?
    @State private var groupChoice: Browse.GroupKey?
    @State private var collapsed: Set<String> = []
    /// A month ("2026-09") or year ("FY2026") picked by tapping the chart.
    @State private var bucket: String?
    @State private var tableSort = TableSort(column: .date, ascending: false)
    @State private var voteFilter: VoteFilter = .all

    init(datasetID: String, preset: [String: String] = [:]) {
        self.datasetID = datasetID
        self.preset = preset
        _filters = State(initialValue: preset)
    }

    private var spec: DatasetSpec { DatasetSpec.for(datasetID) }
    private var info: DatasetInfo? { store.info(datasetID) }
    private var all: [Row] { store.rows[datasetID] ?? [] }
    private var isVotes: Bool { datasetID == "votes" }

    /// Newest first whenever the records carry dates.
    private var sort: Sort { sortChoice ?? (years.periods.isEmpty ? .standard : .newest) }
    private var sortBinding: Binding<Sort> { Binding(get: { sort }, set: { sortChoice = $0 }) }

    /// Records in the chosen year and filters, before the chart's month/year pick (the chart shows these).
    private var inPeriod: [Row] {
        let q = query.trimmingCharacters(in: .whitespaces)
        return all.filter { row in
            (period == nil || years.byRow[row.id] == period) &&
            filters.allSatisfy { key, value in row.string(key) == value || (row[key].map { Format.value($0, column: key) } == value) }
                && store.matches(datasetID, row: row, query: q)
        }
    }

    private func sorted(_ rows: [Row]) -> [Row] {
        switch sort {
        case .standard: return rows
        case .amount: return rows.sorted { (spec.amount($0) ?? -.infinity) > (spec.amount($1) ?? -.infinity) }
        case .newest: return rows.sorted { spec.newestKey($0) > spec.newestKey($1) }
        case .name: return rows.sorted { spec.title($0).localizedCaseInsensitiveCompare(spec.title($1)) == .orderedAscending }
        }
    }

    private func inBucket(_ rows: [Row]) -> [Row] {
        guard let bucket else { return rows }
        if bucket.count == 7, bucket.dropFirst(4).first == "-" { return rows.filter { Browse.monthKey($0) == bucket } }
        return rows.filter { years.byRow[$0.id]?.label == bucket }
    }

    private var hasLocations: Bool { all.contains { $0.number("lat") != nil } }
    private var govColumn: String? { Browse.governmentColumn(spec, rows: all) }
    private var totalInfo: (label: String, note: String?)? { Browse.totals[datasetID] }

    /// Filter choices: the spec's preferred columns, then any column the catalog lists a short set of values for.
    private var filterColumns: [(key: String, choices: [String])] {
        guard let info else { return [] }
        var keys = spec.filterKeys
        for c in info.columns where !keys.contains(c.name) && !DatasetSpec.hiddenColumns.contains(c.name)
            && (2...12).contains(c.choices.count) { keys.append(c.name) }
        return keys.prefix(6).compactMap { key in
            var choices = info.column(key)?.choices ?? []
            if choices.isEmpty {
                choices = Array(Set(all.compactMap { r in r[key].map { Format.value($0, column: key) } }.filter { !$0.isEmpty })).sorted()
            }
            return (2...80).contains(choices.count) ? (key, choices) : nil
        }
    }

    var body: some View {
        content
            .navigationTitle(info?.title ?? Format.label(datasetID))
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $query, prompt: "Search \(info?.title.lowercased() ?? "records")")
            .toolbar { toolbar }
            .task { await store.load(datasetID); indexYears() }
            .refreshable { await store.load(datasetID, force: true); indexYears() }
            .onChange(of: all.count) { indexYears() }
            .onChange(of: period) { bucket = nil; groupChoice = nil; collapsed = [] }
            .navigationDestination(item: $path) { route in
                if case .record(let id, let rowID) = route { RecordDetailView(datasetID: id, rowID: rowID) }
            }
    }

    @ViewBuilder private var content: some View {
        if all.isEmpty {
            if let e = store.errors[datasetID] {
                ContentUnavailableView("Couldn't load this data", systemImage: "wifi.slash", description: Text(e))
            } else {
                ProgressView("Loading \(info?.title ?? "records")…").frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        } else {
            let base = inPeriod
            let rows = sorted(inBucket(base))
            switch mode {
            case .map:
                RecordsMap(datasetID: datasetID, rows: rows) { row in path = .record(datasetID, rowID: row.id) }
                    .safeAreaInset(edge: .bottom) { controls(rows).padding().background(.bar) }
            case .table:
                tableContent(rows)
            case .list:
                if isVotes { votesContent(base: base, rows: rows) } else { listContent(base: base, rows: rows) }
            }
        }
    }

    // MARK: - List

    private var groupOptions: [Browse.GroupKey] {
        Browse.groupOptions(all, spec: spec, periods: years.byRow, period: period)
    }

    private var group: Browse.GroupKey {
        if let groupChoice { return groupChoice }
        guard sort == .newest else { return .none }
        return groupOptions.first.map { [.month, .year].contains($0) ? $0 : .none } ?? .none
    }

    @ViewBuilder private func listContent(base: [Row], rows: [Row]) -> some View {
        let groups = Browse.groups(rows, by: group, spec: spec, periods: years.byRow)
        let maxAmount = rows.compactMap(spec.amount).max() ?? 0
        List {
            Section {
                controls(rows)
                if query.isEmpty { summaryCard(base) }
            }
            .listRowSeparator(.hidden)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))

            ForEach(groups) { g in
                Section(isExpanded: Binding(get: { !collapsed.contains(g.key) },
                                            set: { open in if open { collapsed.remove(g.key) } else { collapsed.insert(g.key) } })) {
                    ForEach(g.rows) { row in
                        NavigationLink(value: Route.record(datasetID, rowID: row.id)) {
                            CompactRecordRow(spec: spec, row: row, maxAmount: maxAmount, hide: hiddenMeta)
                        }
                    }
                } header: {
                    if group != .none {
                        GroupHeader(title: g.title, count: g.rows.count, total: totalInfo != nil ? g.total : nil)
                    }
                }
            }

            if let desc = info?.description {
                Section { } footer: {
                    Text(desc + " Every record links to its source; check the original before relying on one figure.")
                }
            }
        }
        .listStyle(.sidebar)
        .scrollContentBackground(.hidden)
        .background(Brand.canvas)
        .overlay { if rows.isEmpty { emptyState } }
    }

    /// What the group header already says, so rows don't repeat it.
    private var hiddenMeta: String? {
        if case .column(let c) = group { return c }
        return nil
    }

    @ViewBuilder private var emptyState: some View {
        if query.isEmpty, let p = period {
            ContentUnavailableView {
                Label("Nothing from \(p.label)", systemImage: "calendar")
            } description: {
                Text("No records match for this year.")
            } actions: {
                Button("Show all years") { period = nil }.buttonStyle(.bordered)
            }
        } else {
            ContentUnavailableView.search(text: query)
        }
    }

    /// Year, group and count, plus any filters in force.
    private func controls(_ rows: [Row]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                if years.periods.count > 1 { yearMenu }
                if mode == .list && !isVotes && groupOptions.count > 1 { groupMenu }
                Spacer(minLength: 0)
                Text("\(Format.number(Double(rows.count))) of \(Format.number(Double(all.count)))")
                    .font(.footnote).foregroundStyle(.secondary).monospacedDigit()
            }
            if !filters.isEmpty || bucket != nil { activeFilters }
            FreshnessNote(key: datasetID)
        }
    }

    private func summaryCard(_ base: [Row]) -> some View {
        ListSummary(
            tiles: tiles(base),
            chartTitle: chartTitle,
            buckets: buckets(base),
            byAmount: totalInfo != nil,
            selected: $bucket,
            topTitle: topKey.map { "Biggest by \(Browse.GroupKey.column($0).label.lowercased())" },
            top: topKey.map { Browse.top(base, key: $0, spec: spec, byAmount: totalInfo != nil) } ?? [],
            onTop: { name in if let k = topKey { filters[k] = name } },
            note: totalInfo?.note)
    }

    private var chartTitle: String {
        let what = totalInfo.map { "\($0.label) each" } ?? "\(Browse.noun(datasetID)) each"
        return period != nil ? "\(what) month" : (years.periods.first?.fiscal == true ? "\(what) fiscal year" : "\(what) year")
    }

    private func buckets(_ base: [Row]) -> [Browse.Bucket] {
        if let p = period {
            guard !p.fiscal else { return [] }
            let now = Period.currentYear()
            let last = p.year == now ? Calendar.current.component(.month, from: Date()) : 12
            let b = Browse.months(base, spec: spec, year: p.year, through: last)
            return b.filter { $0.count > 0 }.count >= 2 ? b : []
        }
        let b = Browse.years(base, spec: spec, periods: years.byRow)
        return b.count >= 2 ? Array(b.suffix(12)) : []
    }

    /// The column worth ranking: companies when names repeat, else the government.
    private var topKey: String? {
        let t = spec.titleKeys.first ?? ""
        if ["vendor", "payee", "contributor", "member", "candidate", "applicant"].contains(t) { return t }
        return govColumn
    }

    private func tiles(_ base: [Row]) -> [ListSummary.Tile] {
        var out = [ListSummary.Tile(title: Browse.noun(datasetID), value: Format.number(Double(base.count)))]
        let amounts = base.compactMap(spec.amount)
        if let t = totalInfo {
            out.append(.init(title: t.label, value: Format.compactMoney(amounts.reduce(0, +))))
        } else if let m = amounts.max() {
            out.append(.init(title: "Largest", value: Format.compactMoney(m)))
        }
        if let g = govColumn {
            let n = Set(base.compactMap { $0.string(g) }).count
            if n > 1 { out.append(.init(title: g == "board" ? "Boards" : "Governments", value: "\(n)")) }
        }
        return out
    }

    private var yearMenu: some View {
        Menu {
            Picker("Year", selection: $period) {
                Text("All years").tag(Period?.none)
                ForEach(years.periods) { p in Text(p.label).tag(Period?.some(p)) }
            }
        } label: {
            ChipLabel(text: period?.label ?? "All years", filled: true)
        }
        .accessibilityLabel("Year: \(period?.label ?? "All years")")
        .accessibilityHint("Shows records from another year")
    }

    private var groupMenu: some View {
        Menu {
            Picker("Group by", selection: Binding(get: { group }, set: { groupChoice = $0; collapsed = [] })) {
                Text("No groups").tag(Browse.GroupKey.none)
                ForEach(groupOptions) { g in Text(g.label).tag(g) }
            }
        } label: {
            ChipLabel(text: group == .none ? "Group" : "By \(group.label.lowercased())", filled: false)
        }
        .accessibilityLabel("Group records by \(group.label)")
    }

    /// Works out each record's year once per load, and opens the list on the default year the first time.
    private func indexYears() {
        guard !all.isEmpty, years.count != all.count else { return }
        let idx = Period.Index(all)
        var map = [Int: Period]()
        for r in all { if let p = idx.period(r) { map[r.id] = p } }
        let first = years.count == 0
        years = YearIndex(periods: idx.periods, byRow: map, count: all.count)
        if first { period = idx.defaultPeriod() }
    }

    private var activeFilters: some View {
        FlowLayout(spacing: 6) {
            if let b = bucket {
                FilterChip(text: b.count == 7 ? Browse.monthName(b) : b) { bucket = nil }
            }
            ForEach(filters.sorted { $0.key < $1.key }, id: \.key) { pair in
                FilterChip(text: pair.key == "gov_id" ? (Governments.names[pair.value] ?? pair.value) : pair.value) {
                    filters[pair.key] = nil
                }
            }
        }
    }

    // MARK: - Table

    private func tableContent(_ rows: [Row]) -> some View {
        let cols = TableColumn.columns(spec: spec, hasDates: !years.periods.isEmpty, govColumn: govColumn)
        return RecordTable(spec: spec, rows: tableSort.apply(rows, spec: spec, govColumn: govColumn), columns: cols,
                           sort: $tableSort, govColumn: govColumn) { row in path = .record(datasetID, rowID: row.id) } header: {
            controls(rows).padding(.horizontal, 16).padding(.vertical, 8)
        }
        .overlay { if rows.isEmpty { emptyState } }
    }

    // MARK: - Votes

    enum VoteFilter: String, CaseIterable { case all = "All", split = "Split", failed = "Failed" }

    @ViewBuilder private func votesContent(base: [Row], rows: [Row]) -> some View {
        let summaries = Dictionary(uniqueKeysWithValues: rows.map { ($0.id, VoteSummary($0)) })
        let splitCount = summaries.values.filter(\.split).count
        let failedCount = summaries.values.filter { $0.passed == false }.count
        let shown = rows.filter { r in
            switch voteFilter {
            case .all: true
            case .split: summaries[r.id]?.split == true
            case .failed: summaries[r.id]?.passed == false
            }
        }
        let meetings = Browse.meetings(shown)
        List {
            Section {
                controls(rows)
                ChipRow(chips: [(id: VoteFilter.all, label: "All"), (id: VoteFilter.split, label: "Split"), (id: VoteFilter.failed, label: "Failed")],
                        selected: voteFilter,
                        counts: [.all: rows.count, .split: splitCount, .failed: failedCount]) { voteFilter = $0 }
                VoteLegend()
                if query.isEmpty && voteFilter == .all { summaryCard(base) }
            }
            .listRowSeparator(.hidden)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))

            ForEach(meetings) { m in
                Section(isExpanded: Binding(get: { !collapsed.contains(m.id) },
                                            set: { open in if open { collapsed.remove(m.id) } else { collapsed.insert(m.id) } })) {
                    ForEach(m.votes) { v in
                        NavigationLink(value: Route.record(datasetID, rowID: v.id)) {
                            VoteRow(row: v, summary: summaries[v.id] ?? VoteSummary(v))
                        }
                    }
                } header: {
                    GroupHeader(title: m.board,
                                subtitle: Dates.parse(m.date).map { Dates.display($0, hasTime: false) } ?? m.date,
                                count: m.votes.count, noun: "vote", total: nil)
                }
            }
        }
        .listStyle(.sidebar)
        .scrollContentBackground(.hidden)
        .background(Brand.canvas)
        .overlay { if shown.isEmpty { emptyState } }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .topBarTrailing) {
            Menu {
                Picker("View", selection: $mode) {
                    Label("List", systemImage: "list.bullet").tag(Mode.list)
                    Label("Table", systemImage: "tablecells").tag(Mode.table)
                    if hasLocations { Label("Map", systemImage: "map").tag(Mode.map) }
                }
            } label: {
                Image(systemName: mode == .table ? "tablecells" : mode == .map ? "map" : "list.bullet")
            }
            .accessibilityLabel("View as \(mode.rawValue)")
            Menu {
                Picker("Sort", selection: sortBinding) {
                    ForEach(Sort.allCases.filter { s in
                        switch s {
                        case .amount: !spec.amountKeys.isEmpty
                        case .newest: !years.periods.isEmpty
                        default: true
                        }
                    }) { Text($0.rawValue).tag($0) }
                }
                ForEach(filterColumns, id: \.key) { col in
                    Picker(Format.label(col.key), selection: Binding(
                        get: { filters[col.key] },
                        set: { filters[col.key] = $0 })) {
                        Text("Any \(Format.label(col.key).lowercased())").tag(String?.none)
                        ForEach(col.choices, id: \.self) { Text($0).tag(String?.some($0)) }
                    }
                    .pickerStyle(.menu)
                }
                if !filters.isEmpty {
                    Button("Clear filters", role: .destructive) { filters = [:] }
                }
                Divider()
                if let url = info?.pageURL { Button("Open on BayCounty.me") { store.open(url) } }
                if let csv = info?.csvURL { ShareLink("Share CSV link", item: csv) }
            } label: {
                Image(systemName: filters.isEmpty ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
            }
            .accessibilityLabel("Sort and filter")
        }
    }
}

struct RecordDetailView: View {
    @Environment(AppStore.self) private var store
    let datasetID: String
    let rowID: Int

    var body: some View {
        let spec = DatasetSpec.for(datasetID)
        if let row = store.rows[datasetID]?.first(where: { $0.id == rowID }) {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(spec.title(row)).font(.title3.weight(.semibold))
                        if let a = spec.amount(row) {
                            Text(Format.money(a)).font(.largeTitle.weight(.semibold).monospacedDigit())
                                .minimumScaleFactor(0.6).lineLimit(1)
                            if let key = spec.amountKey(row) { Text(Format.label(key)).font(.caption).foregroundStyle(.secondary) }
                        }
                        if let status = row.string("status"), datasetID == "cra-payments" {
                            HStack { Badge(text: status, color: Brand.status(status)); Text(CRALedger.explain(status: status)).font(.footnote).foregroundStyle(.secondary) }
                            if row.bool("count") == false {
                                Label("Left out of totals so no dollar is counted twice.", systemImage: "minus.circle")
                                    .font(.footnote).foregroundStyle(.secondary)
                            }
                        } else if datasetID == "votes" {
                            let v = VoteSummary(row)
                            if v.hasTally {
                                HStack(spacing: 10) {
                                    VoteDots(summary: v, size: 16)
                                    Text(v.passed == false ? "Failed \(v.tallyText)" : v.passed == true ? "Passed \(v.tallyText)" : v.tallyText)
                                        .font(.subheadline.weight(.semibold))
                                    if v.split { Badge(text: "Split", color: Brand.amber) }
                                }
                            }
                        } else if let b = spec.badge(row) {
                            Badge(text: b, color: Brand.status(b))
                        }
                    }
                    .padding(.vertical, 4)
                }

                if let a = spec.amount(row), datasetID != "votes" {
                    compareSection(row, amount: a, spec: spec)
                }

                if let detail = spec.detail(row) {
                    Section { Text(detail) }
                }

                Section("Details") {
                    ForEach(Array(DatasetSpec.fields(row, columns: store.info(datasetID)?.columns ?? []).enumerated()), id: \.offset) { _, f in
                        if f.value.count > 60 || f.value.contains("\n") {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(f.label).font(.caption).foregroundStyle(.secondary)
                                Text(f.value).font(.callout).textSelection(.enabled)
                            }
                        } else {
                            LabeledContent(f.label) { Text(f.value).multilineTextAlignment(.trailing).textSelection(.enabled) }
                        }
                    }
                }

                linksSection(row)

                if row.number("lat") != nil {
                    Section("Location") {
                        RecordsMap(datasetID: datasetID, rows: [row])
                            .frame(height: 180)
                            .listRowInsets(EdgeInsets())
                    }
                }

                Section {
                    if let url = DatasetSpec.sourceURL(row) {
                        WebLink(title: row.string("source_title") ?? "Source record", symbol: "doc.text.magnifyingglass", url: url)
                    }
                    WebLink(title: "Send a correction", symbol: "exclamationmark.bubble",
                            url: URL(string: "https://baycounty.me/about?page=\(spec.page.map { "/" + $0 } ?? "/")#contact"))
                } footer: {
                    Text("From public records compiled by BayCounty.me. Check the original before relying on a single figure.")
                }
            }
            .navigationTitle(store.info(datasetID)?.title ?? "Record")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let url = DatasetSpec.sourceURL(row) {
                    ShareLink(item: url, subject: Text(spec.title(row)),
                              message: Text([spec.title(row), spec.amount(row).map { Format.money($0) }].compactMap { $0 }.joined(separator: " · ")))
                }
            }
        } else {
            ContentUnavailableView("Record not found", systemImage: "doc")
        }
    }

    /// Where this amount sits among the same list's records from the same year: a dot on a line from smallest to largest.
    @ViewBuilder private func compareSection(_ row: Row, amount: Double, spec: DatasetSpec) -> some View {
        let all = store.rows[datasetID] ?? []
        let idx = Period.Index(all)
        let period = idx.period(row)
        let peers = all.filter { period == nil || idx.period($0) == period }.compactMap(spec.amount).sorted()
        if peers.count >= 5, let lo = peers.first, let hi = peers.last, hi > lo {
            let rank = peers.filter { $0 < amount }.count
            let pct = Int((Double(rank) / Double(peers.count) * 100).rounded())
            let median = peers[peers.count / 2]
            Section {
                VStack(alignment: .leading, spacing: 10) {
                    Text(pct >= 50 ? "Larger than \(pct)% of \(period?.label ?? "all") records in this list"
                                   : "Smaller than \(100 - pct)% of \(period?.label ?? "all") records in this list")
                        .font(.subheadline.weight(.semibold))
                    GeometryReader { g in
                        let x = { (v: Double) in g.size.width * CGFloat(log10(max(v, 1) / max(lo, 1)) / max(log10(max(hi, 1) / max(lo, 1)), 0.0001)) }
                        ZStack(alignment: .leading) {
                            Capsule().fill(Brand.sunken).frame(height: 6)
                            ForEach(Array(peers.enumerated()), id: \.offset) { _, v in
                                Circle().fill(Brand.blue.opacity(0.25)).frame(width: 6, height: 6).offset(x: x(v) - 3)
                            }
                            Rectangle().fill(Color.secondary).frame(width: 1.5, height: 16).offset(x: x(median))
                            Circle().fill(Brand.navy).frame(width: 16, height: 16).offset(x: x(amount) - 8)
                        }
                    }
                    .frame(height: 18)
                    .accessibilityHidden(true)
                    HStack {
                        Text("Smallest \(Format.compactMoney(lo))")
                        Spacer()
                        Text("Middle \(Format.compactMoney(median))")
                        Spacer()
                        Text("Largest \(Format.compactMoney(hi))")
                    }
                    .font(.caption2).foregroundStyle(.secondary)
                }
                .padding(.vertical, 4)
            } header: {
                Text("How it compares")
            }
        }
    }

    /// The record's company, people, approving votes and government, as the website links them.
    @ViewBuilder private func linksSection(_ row: Row) -> some View {
        let vendors = RecordLinks.vendorIDs(row)
        let people = datasetID == "votes" ? [] : RecordLinks.personIDs(row)
        let voteIDs = Set(RecordLinks.voteIDs(row))
        let votes = datasetID == "votes" ? [] : (store.rows["votes"] ?? []).filter { v in v.string("vote_id").map(voteIDs.contains) ?? false }
        let roll = datasetID == "votes" ? RollCall.members(row) : []
        let gov = row.string("gov_id").flatMap { store.government($0) }
        if !vendors.isEmpty || !people.isEmpty || !votes.isEmpty || !roll.isEmpty || gov != nil {
            Section("Linked records") {
                ForEach(vendors, id: \.self) { id in
                    NavigationLink(value: Route.vendor(id)) { Label(store.vendor(id)?.name ?? id, systemImage: "building") }
                }
                ForEach(people, id: \.self) { id in
                    NavigationLink(value: Route.person(id)) { Label(store.person(id)?.name ?? id, systemImage: "person") }
                }
                ForEach(votes) { v in
                    NavigationLink(value: Route.record("votes", rowID: v.id)) { Label(v.string("headline") ?? "Vote", systemImage: "hand.raised") }
                }
                ForEach(Array(roll.enumerated()), id: \.offset) { _, m in
                    let vote = (m.vote ?? "").lowercased()
                    let mark = VoteMark(choice: vote == "yes" ? .yes : vote == "no" ? .no : .other)
                    if let pid = m.pid {
                        NavigationLink(value: Route.person(pid)) { HStack { Text(m.name); Spacer(); mark } }
                    } else {
                        HStack { Text(m.name); Spacer(); mark }
                    }
                }
                if let gov { NavigationLink(value: Route.government(gov.govID)) { Label(gov.name, systemImage: "building.columns") } }
            }
            .task {
                await store.loadVendors()
                await store.loadPeople()
                if !voteIDs.isEmpty { await store.load("votes") }
            }
        }
    }

}

/// One member's vote on a recorded vote.
struct RollCall: Hashable {
    let name: String
    let pid: String?
    let vote: String?

    static func members(_ row: Row) -> [RollCall] {
        (row["members"]?.arrayValue ?? []).compactMap { m -> RollCall? in
            guard case .object(let o) = m, let n = o["name"]?.stringValue else { return nil }
            return RollCall(name: n, pid: o["person_id"]?.stringValue, vote: o["vote"]?.stringValue)
        }
    }
}

/// Each record's year for one list, worked out once per load.
struct YearIndex {
    var periods: [Period] = []
    var byRow: [Int: Period] = [:]
    var count = 0
}
