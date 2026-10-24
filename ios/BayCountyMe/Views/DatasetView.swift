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
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
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
                Picker("Show", selection: $voteFilter) {
                    Text("All \(rows.count)").tag(VoteFilter.all)
                    Text("Split \(splitCount)").tag(VoteFilter.split)
                    Text("Failed \(failedCount)").tag(VoteFilter.failed)
                }
                .pickerStyle(.segmented)
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

/// One record, laid out as a profile: who or what it is, its tags and headline numbers, the years it covers,
/// the people and organizations it names (each opening its own record or profile), related records from the
/// same lists, and the source. The layout comes from `RecordProfile`, so every list gets it.
struct RecordDetailView: View {
    @Environment(AppStore.self) private var store
    let datasetID: String
    let rowID: Int

    var body: some View {
        let spec = DatasetSpec.for(datasetID)
        if let row = store.rows[datasetID]?.first(where: { $0.id == rowID }) {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    hero(row, spec: spec)
                    factsGrid(row)
                    if let years = RecordProfile.years(row) { YearsStrip(years: years, current: row.bool("current")) }
                    if let detail = spec.detail(row), spec.detailKey != "sources" {
                        Text(detail).font(.callout).frame(maxWidth: .infinity, alignment: .leading).padding(16).card(20)
                    }
                    if let a = spec.amount(row), datasetID != "votes" { compareCard(row, amount: a, spec: spec) }
                    connections(row)
                    ForEach(RecordProfile.groups(datasetID, row), id: \.self) { g in groupCard(g, row: row) }
                    if let me = RecordProfile.subject(datasetID, row) { profileButton(me) }
                    if row.number("lat") != nil {
                        RecordsMap(datasetID: datasetID, rows: [row])
                            .frame(height: 180)
                            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                            .overlay { RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Brand.hairline) }
                    }
                    sourceCard(row, spec: spec)
                    Text("From public records compiled by BayCounty.me. Check the original before relying on a single figure.")
                        .font(.caption).foregroundStyle(.secondary).padding(.horizontal, 4)
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle(Self.noun[datasetID] ?? store.info(datasetID)?.title ?? "Record")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let url = DatasetSpec.sourceURL(row) {
                    ShareLink(item: url, subject: Text(spec.title(row)),
                              message: Text([spec.title(row), spec.amount(row).map { Format.money($0) }].compactMap { $0 }.joined(separator: " · ")))
                }
            }
            .task { await loadRelated(row) }
        } else {
            ContentUnavailableView("Record not found", systemImage: "doc")
        }
    }

    /// What one record of a list is called, for the screen title.
    static let noun: [String: String] = [
        "nonprofit-board-members": "Board member", "nonprofits": "Nonprofit", "nonprofit-board-businesses": "Board member's business",
        "charity-registrations": "Charity registration", "nonprofit-grants": "Grant", "nonprofit-payments": "Payment",
        "nonprofit-officials": "Official on a board", "entity-profiles": "Profile", "entity-connections": "Connection",
        "contracts": "Contract", "change-orders": "Change order", "votes": "Vote", "member-votes": "Vote", "cra-payments": "CRA record",
    ]

    /// The other lists this record's links and groups read from.
    private func loadRelated(_ row: Row) async {
        await store.loadVendors()
        await store.loadPeople()
        var ids = Set(RecordProfile.groups(datasetID, row).map(\.datasetID)).subtracting([datasetID])
        if RecordProfile.refs(datasetID, row).contains(where: { $0.kind == "nonprofit" }) { ids.insert("nonprofits") }
        if !RecordLinks.voteIDs(row).isEmpty, datasetID != "votes" { ids.insert("votes") }
        for id in ids.sorted() { await store.load(id) }
    }

    // MARK: - Header

    @ViewBuilder private func hero(_ row: Row, spec: DatasetSpec) -> some View {
        let org: EntityRef? = datasetID == "nonprofits" ? nil : RecordProfile.refs(datasetID, row).first(where: { $0.kind == "nonprofit" })
        let chips = RecordProfile.chips(datasetID, row)
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .center, spacing: 14) {
                if let ini = RecordProfile.initials(datasetID, row) {
                    Text(ini)
                        .font(.title3.weight(.semibold))
                        .foregroundStyle(.white)
                        .frame(width: 56, height: 56)
                        .background(Brand.navyFill, in: Circle())
                        .accessibilityHidden(true)
                } else {
                    Image(systemName: spec.symbol)
                        .font(.title2)
                        .foregroundStyle(Brand.navy)
                        .frame(width: 56, height: 56)
                        .background(Brand.navy.opacity(0.1), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(spec.title(row)).font(.title2.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                    if let role = RecordProfile.roleLine(datasetID, row) {
                        Text(role).font(.subheadline).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            if let org {
                orgLink(org) {
                    Label { Text("at \(org.name)").multilineTextAlignment(.leading) } icon: { Image(systemName: "building.2") }
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Brand.navy)
                        .frame(minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .padding(.vertical, -6)
            }
            if let a = spec.amount(row) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(Format.money(a)).font(.largeTitle.weight(.semibold).monospacedDigit())
                        .minimumScaleFactor(0.6).lineLimit(1)
                    if let key = spec.amountKey(row) { Text(Format.label(key)).font(.caption).foregroundStyle(.secondary) }
                }
            }
            statusLine(row, spec: spec)
            if !chips.isEmpty {
                FlowLayout(spacing: 8) {
                    ForEach(chips, id: \.self) { c in TagChip(chip: c) }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(20)
        .card(20)
    }

    /// CRA status, a vote's tally, or the list's own badge.
    @ViewBuilder private func statusLine(_ row: Row, spec: DatasetSpec) -> some View {
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
        } else if let b = spec.badge(row), !RecordProfile.chips(datasetID, row).contains(where: { $0.text == b }) {
            Badge(text: b, color: Brand.status(b))
        }
    }

    // MARK: - Numbers

    @ViewBuilder private func factsGrid(_ row: Row) -> some View {
        let facts = RecordProfile.facts(datasetID, row)
        if !facts.isEmpty {
            let cols = Array(repeating: GridItem(.flexible(), spacing: 10, alignment: .top), count: facts.count == 4 ? 2 : facts.count)
            LazyVGrid(columns: cols, alignment: .leading, spacing: 10) {
                ForEach(facts, id: \.self) { f in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(f.value).font(.title2.weight(.semibold).monospacedDigit()).minimumScaleFactor(0.6).lineLimit(1)
                        Text(f.label).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, minHeight: 64, alignment: .topLeading)
                    .padding(14)
                    .card(16)
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    /// Where this amount sits among the same list's records from the same year: a dot on a line from smallest to largest.
    @ViewBuilder private func compareCard(_ row: Row, amount: Double, spec: DatasetSpec) -> some View {
        let all = store.rows[datasetID] ?? []
        let idx = Period.Index(all)
        let period = idx.period(row)
        let peers = all.filter { period == nil || idx.period($0) == period }.compactMap(spec.amount).sorted()
        if peers.count >= 5, let lo = peers.first, let hi = peers.last, hi > lo {
            let rank = peers.filter { $0 < amount }.count
            let pct = Int((Double(rank) / Double(peers.count) * 100).rounded())
            let median = peers[peers.count / 2]
            VStack(alignment: .leading, spacing: 10) {
                EyebrowHeader(text: "How it compares")
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
            .padding(16)
            .card(20)
        }
    }

    // MARK: - Connections

    /// The organization, companies, officials, votes and government the record names, each as a tappable card row.
    @ViewBuilder private func connections(_ row: Row) -> some View {
        let me: EntityRef? = datasetID == "entity-connections" ? nil : RecordProfile.subject(datasetID, row)
        let refs = RecordProfile.refs(datasetID, row).filter { r in r.kind != "member" && r != me }
        let vendors = RecordLinks.vendorIDs(row)
        let people = RecordLinks.personDatasets.contains(datasetID) && datasetID != "votes" ? RecordLinks.personIDs(row) : []
        let voteIDs = Set(RecordLinks.voteIDs(row))
        let votes = datasetID == "votes" ? [] : (store.rows["votes"] ?? []).filter { v in v.string("vote_id").map(voteIDs.contains) ?? false }
        let roll = datasetID == "votes" ? RollCall.members(row) : []
        let gov = row.string("gov_id").flatMap { store.government($0) }
        if !refs.isEmpty || !vendors.isEmpty || !people.isEmpty || !votes.isEmpty || gov != nil {
            VStack(alignment: .leading, spacing: 8) {
                EyebrowHeader(text: refs.contains { $0.kind == "nonprofit" } && refs.count == 1 ? "Organization" : "Connected to").padding(.horizontal, 4)
                VStack(spacing: 0) {
                    let items = linkItems(refs: refs, vendors: vendors, people: people, votes: votes, gov: gov)
                    ForEach(Array(items.enumerated()), id: \.offset) { i, item in
                        if i > 0 { RowDivider(inset: 70) }
                        item
                    }
                }
                .card(20)
            }
        }
        if !roll.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                EyebrowHeader(text: "How each member voted").padding(.horizontal, 4)
                CardList {
                    ForEach(Array(roll.enumerated()), id: \.offset) { i, m in
                        if i > 0 { RowDivider() }
                        let vote = (m.vote ?? "").lowercased()
                        let mark = VoteMark(choice: vote == "yes" ? .yes : vote == "no" ? .no : .other)
                        if let pid = m.pid {
                            NavigationLink(value: Route.person(pid)) { rollRow(m.name, mark: mark, chevron: true) }.buttonStyle(.plain)
                        } else {
                            rollRow(m.name, mark: mark, chevron: false)
                        }
                    }
                }
            }
        }
    }

    private func rollRow(_ name: String, mark: VoteMark, chevron: Bool) -> some View {
        HStack {
            Text(name)
            Spacer()
            mark
            if chevron { Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary) }
        }
        .padding(.horizontal, 16).frame(minHeight: 48).contentShape(Rectangle())
    }

    private func linkItems(refs: [EntityRef], vendors: [String], people: [String], votes: [Row], gov: Government?) -> [AnyView] {
        var out = [AnyView]()
        for r in refs { out.append(AnyView(entityRow(r))) }
        for id in vendors {
            out.append(AnyView(NavigationLink(value: Route.vendor(id)) {
                LinkCardLabel(symbol: "building.2", tint: Brand.navy, title: store.vendor(id)?.name ?? "Company", detail: "Company")
            }.buttonStyle(PressRowStyle())))
        }
        for id in people {
            if let p = store.person(id) {
                out.append(AnyView(NavigationLink(value: Route.person(id)) {
                    LinkCardLabel(symbol: "person", tint: Brand.navy, title: p.name, detail: p.headline)
                }.buttonStyle(PressRowStyle())))
            }
        }
        for v in votes {
            out.append(AnyView(NavigationLink(value: Route.record("votes", rowID: v.id)) {
                LinkCardLabel(symbol: "hand.raised", tint: Brand.amber, title: v.string("headline") ?? "Vote", detail: "Recorded vote")
            }.buttonStyle(PressRowStyle())))
        }
        if let gov {
            out.append(AnyView(NavigationLink(value: Route.government(gov.govID)) {
                LinkCardLabel(symbol: "building.columns", tint: Brand.navy, title: gov.name, detail: "Government")
            }.buttonStyle(PressRowStyle())))
        }
        return out
    }

    /// A named person or organization: its own record in the app when there is one, else its profile on BayCounty.me.
    @ViewBuilder private func entityRow(_ r: EntityRef) -> some View {
        let label = LinkCardLabel(symbol: r.symbol, tint: r.kind == "nonprofit" ? Brand.good : Brand.navy, title: r.name,
                                  detail: r.kind == "nonprofit" ? nonprofitMeta(r.key) ?? r.label : r.label)
        switch r.kind {
        case "nonprofit": orgLink(r) { label }
        case "person" where store.person(r.key) != nil:
            NavigationLink(value: Route.person(r.key)) { label }.buttonStyle(PressRowStyle())
        case "vendor" where store.vendor(r.key) != nil:
            NavigationLink(value: Route.vendor(r.key)) { label }.buttonStyle(PressRowStyle())
        case "gov" where store.government(r.key) != nil:
            NavigationLink(value: Route.government(r.key)) { label }.buttonStyle(PressRowStyle())
        default:
            Button { store.open(r.profileURL) } label: { label }.buttonStyle(PressRowStyle())
        }
    }

    /// A nonprofit opens its own record in the app when the nonprofits list has it, else its web profile.
    @ViewBuilder private func orgLink<L: View>(_ r: EntityRef, @ViewBuilder label: () -> L) -> some View {
        if let np = nonprofitRow(r.key) {
            NavigationLink(value: Route.record("nonprofits", rowID: np.id)) { label() }.buttonStyle(PressRowStyle())
        } else {
            Button { store.open(r.profileURL) } label: { label() }.buttonStyle(PressRowStyle())
        }
    }

    private func nonprofitRow(_ id: String) -> Row? {
        store.rows["nonprofits"]?.first { $0.string("nonprofit_id") == id }
    }

    /// "Nonprofit · Panama City · Active since 2001 · 4 board members"
    private func nonprofitMeta(_ id: String) -> String? {
        guard let n = nonprofitRow(id) else { return nil }
        var parts = [n.string("kind") ?? "Nonprofit"]
        if let c = n.string("city") { parts.append(c) }
        if n.string("sunbiz_status") == "Active", let f = n.string("sunbiz_filed") { parts.append("Active since \(f.prefix(4))") }
        if let b = n.number("board_members_listed"), b > 0 { parts.append("\(Int(b)) board member" + (b == 1 ? "" : "s")) }
        return parts.joined(separator: " · ")
    }

    // MARK: - Related records

    @ViewBuilder private func groupCard(_ g: RecordProfile.Group, row: Row) -> some View {
        let same = g.datasetID == datasetID
        let rows = RecordProfile.members(of: g, in: store.rows[g.datasetID] ?? [], excluding: row.id, sameDataset: same)
        if !rows.isEmpty {
            let people = g.datasetID == "nonprofit-board-members" && g.column != "person_id"
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline) {
                    EyebrowHeader(text: g.title)
                    Spacer()
                    Text("\(rows.count)").font(.footnote.weight(.semibold).monospacedDigit()).foregroundStyle(.secondary)
                }
                .padding(.horizontal, 4)
                CardList {
                    ForEach(Array(rows.prefix(6).enumerated()), id: \.offset) { i, r in
                        if i > 0 { RowDivider(inset: 64) }
                        NavigationLink(value: Route.record(g.datasetID, rowID: r.id)) {
                            groupRowLabel(g, r, people: people)
                        }
                        .buttonStyle(PressRowStyle())
                    }
                    if rows.count > 6 {
                        RowDivider()
                        RouteRow(route: .dataset(g.datasetID, filters: [g.column: g.value]), title: "See all \(rows.count)")
                    }
                }
            }
        }
    }

    private func groupRowLabel(_ g: RecordProfile.Group, _ r: Row, people: Bool) -> LinkCardLabel {
        let title = RecordProfile.groupRowTitle(g, r)
        let detail = RecordProfile.groupRowDetail(g, r)
        if people {
            return LinkCardLabel(initials: Self.initials(title), tint: Brand.navy, title: title, detail: detail, compact: true)
        }
        let symbol = g.datasetID == "nonprofit-board-members" ? "heart" : DatasetSpec.for(g.datasetID).symbol
        return LinkCardLabel(symbol: symbol, tint: Brand.good, title: title, detail: detail, compact: true)
    }

    static func initials(_ name: String) -> String {
        let w = name.split(separator: " ").filter { $0.first?.isLetter == true }
        return ((w.first?.first.map(String.init) ?? "") + (w.count > 1 ? w.last?.first.map(String.init) ?? "" : "")).uppercased()
    }

    // MARK: - Profile and source

    private func profileButton(_ me: EntityRef) -> some View {
        Button { store.open(me.profileURL) } label: {
            HStack(spacing: 12) {
                Image(systemName: "point.3.connected.trianglepath.dotted").font(.title3).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(me.name): profile and connections").font(.subheadline.weight(.semibold)).multilineTextAlignment(.leading)
                    Text("People, money and links on one map").font(.caption).opacity(0.85)
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.caption.weight(.bold)).accessibilityHidden(true)
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 18)
            .frame(maxWidth: .infinity, minHeight: 64)
            .background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
        .buttonStyle(PressScaleStyle())
    }

    @ViewBuilder private func sourceCard(_ row: Row, spec: DatasetSpec) -> some View {
        let fields = RecordProfile.otherFields(datasetID, row, columns: store.info(datasetID)?.columns ?? [])
        CardList {
            if let url = DatasetSpec.sourceURL(row) {
                WebRow(title: row.string("source_title") ?? Self.sourceName(url), symbol: "doc.text.magnifyingglass", url: url)
                RowDivider(inset: 50)
            }
            WebRow(title: "Send a correction", symbol: "exclamationmark.bubble",
                   url: URL(string: "https://baycounty.me/about?page=\(spec.page.map { "/" + $0 } ?? "/")#contact"))
            if !fields.isEmpty {
                RowDivider(inset: 50)
                AllFields(fields: fields)
            }
        }
    }

    /// "Florida corporate filing (Sunbiz)" for a sunbiz.org link, and so on.
    static func sourceName(_ url: URL) -> String {
        let host = url.host() ?? ""
        if host.contains("sunbiz") { return "Florida corporate filing (Sunbiz)" }
        if host.contains("gt990datalake") || host.contains("irs.gov") { return "IRS return" }
        if host.contains("propublica") { return "IRS filings (ProPublica)" }
        if host.contains("fdacs") { return "Florida charity registration" }
        return "Source record"
    }
}

/// A tag in a record's header.
struct TagChip: View {
    let chip: RecordProfile.Chip

    var body: some View {
        let color: Color = switch chip.tone {
        case .good: Brand.good
        case .accent: Brand.navy
        case .warn: Brand.amber
        case .neutral: .secondary
        }
        HStack(spacing: 6) {
            if chip.tone == .good { Circle().fill(color).frame(width: 7, height: 7).accessibilityHidden(true) }
            Text(chip.text).font(.footnote.weight(.semibold)).lineLimit(1)
        }
        .foregroundStyle(color)
        .padding(.horizontal, 12)
        .frame(minHeight: 28)
        .background(chip.tone == .neutral ? AnyShapeStyle(Brand.sunken) : AnyShapeStyle(color.opacity(0.14)), in: Capsule())
    }
}

/// A row on a card that leads somewhere: an icon tile (or initials), a name, a detail line and a chevron.
struct LinkCardLabel: View {
    var symbol: String? = nil
    var initials: String? = nil
    var tint: Color = Brand.navy
    let title: String
    var detail: String? = nil
    var compact = false

    var body: some View {
        HStack(spacing: 12) {
            Group {
                if let initials {
                    Text(initials).font(.footnote.weight(.semibold)).foregroundStyle(tint)
                        .frame(width: 36, height: 36).background(tint.opacity(0.12), in: Circle())
                } else if let symbol {
                    Image(systemName: symbol).font(compact ? .body : .title3).foregroundStyle(tint)
                        .frame(width: compact ? 36 : 44, height: compact ? 36 : 44)
                        .background(tint.opacity(0.12), in: RoundedRectangle(cornerRadius: compact ? 10 : 12, style: .continuous))
                }
            }
            .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary).multilineTextAlignment(.leading)
                if let detail, !detail.isEmpty {
                    Text(detail).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading).lineLimit(3)
                }
            }
            Spacer(minLength: 4)
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary).accessibilityHidden(true)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, compact ? 8 : 12)
        .frame(minHeight: 56)
        .contentShape(Rectangle())
    }
}

/// Rows fade slightly while pressed.
struct PressRowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .opacity(configuration.isPressed ? 0.55 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

/// Buttons shrink a touch while pressed.
struct PressScaleStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// The years a record covers, as a strip of year cells (filled for the years on file).
struct YearsStrip: View {
    let years: ClosedRange<Int>
    var current: Bool? = nil

    private var cells: [Int] {
        let lo = min(years.lowerBound, years.upperBound - 7)
        return Array(max(lo, years.upperBound - 11)...years.upperBound)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text("Years on file").font(.subheadline.weight(.semibold))
                Spacer()
                Text(years.count == 1 ? String(years.lowerBound) : String(years.lowerBound) + "–" + String(years.upperBound))
                    .font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
            }
            HStack(spacing: 4) {
                ForEach(cells, id: \.self) { y in
                    let on = years.contains(y)
                    VStack(spacing: 6) {
                        Capsule().fill(on ? Brand.navyFill : Brand.sunken).frame(height: 10)
                        Text("’" + String(y % 100).leftPad(2)).font(.caption2.monospacedDigit())
                            .foregroundStyle(on ? .primary : .tertiary)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .accessibilityHidden(true)
        }
        .padding(16)
        .card(20)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(years.count == 1 ? "On file in " + String(years.lowerBound) : "On file from " + String(years.lowerBound) + " to " + String(years.upperBound))
    }
}

private extension String {
    func leftPad(_ n: Int) -> String { count >= n ? self : String(repeating: "0", count: n - count) + self }
}

/// Every remaining field, folded away under one row.
struct AllFields: View {
    let fields: [(label: String, value: String)]
    @State private var open = false

    var body: some View {
        VStack(spacing: 0) {
            Button { withAnimation(.easeOut(duration: 0.2)) { open.toggle() } } label: {
                HStack(spacing: 12) {
                    Image(systemName: "list.bullet.rectangle").foregroundStyle(Brand.navy).frame(width: 24).accessibilityHidden(true)
                    Text("All fields").foregroundStyle(.primary)
                    Spacer()
                    Text("\(fields.count)").font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
                    Image(systemName: "chevron.down").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                        .rotationEffect(.degrees(open ? 180 : 0))
                        .accessibilityHidden(true)
                }
                .padding(.horizontal, 14)
                .frame(minHeight: 50)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityValue(open ? "Shown" : "Hidden")
            if open {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(Array(fields.enumerated()), id: \.offset) { _, f in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(f.label).font(.caption).foregroundStyle(.secondary)
                            Text(f.value).font(.callout).textSelection(.enabled).fixedSize(horizontal: false, vertical: true)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 14)
                .transition(.opacity)
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
