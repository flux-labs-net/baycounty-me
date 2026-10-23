import SwiftUI
import BayCountyKit

/// Any dataset on the site: search, filter, sort, total, map (when rows have locations) and record detail.
/// Lists open on the current year (or fiscal year), newest first, with a menu to step back to earlier years.
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

    enum Mode: String, CaseIterable { case list = "List", map = "Map" }

    @State private var query = ""
    @State private var filters: [String: String] = [:]
    @State private var sortChoice: Sort?
    /// Year the list shows; nil means every year.
    @State private var period: Period?
    @State private var years = YearIndex()
    @State private var mode: Mode = .list
    @State private var path: Route?

    init(datasetID: String, preset: [String: String] = [:]) {
        self.datasetID = datasetID
        self.preset = preset
        _filters = State(initialValue: preset)
    }

    private var spec: DatasetSpec { DatasetSpec.for(datasetID) }
    private var info: DatasetInfo? { store.info(datasetID) }
    private var all: [Row] { store.rows[datasetID] ?? [] }

    /// Newest first whenever the records carry dates.
    private var sort: Sort { sortChoice ?? (years.periods.isEmpty ? .standard : .newest) }
    private var sortBinding: Binding<Sort> { Binding(get: { sort }, set: { sortChoice = $0 }) }

    private var filtered: [Row] {
        let q = query.trimmingCharacters(in: .whitespaces)
        let rows = all.filter { row in
            (period == nil || years.byRow[row.id] == period) &&
            filters.allSatisfy { key, value in row.string(key) == value || (row[key].map { Format.value($0, column: key) } == value) }
                && store.matches(datasetID, row: row, query: q)
        }
        switch sort {
        case .standard: return rows
        case .amount: return rows.sorted { (spec.amount($0) ?? -.infinity) > (spec.amount($1) ?? -.infinity) }
        case .newest: return rows.sorted { spec.newestKey($0) > spec.newestKey($1) }
        case .name: return rows.sorted { spec.title($0).localizedCaseInsensitiveCompare(spec.title($1)) == .orderedAscending }
        }
    }

    private var hasLocations: Bool { all.contains { $0.number("lat") != nil } }

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
        } else if mode == .map {
            RecordsMap(datasetID: datasetID, rows: filtered) { row in path = .record(datasetID, rowID: row.id) }
                .safeAreaInset(edge: .bottom) { summary.padding().background(.bar) }
        } else {
            List {
                if query.isEmpty, store.page(spec.page) != nil {
                    Section { PageIntro(path: spec.page.map { "/" + $0 }) }
                }
                Section {
                    ForEach(filtered) { row in
                        NavigationLink(value: Route.record(datasetID, rowID: row.id)) { RecordRow(spec: spec, row: row) }
                    }
                } header: {
                    VStack(alignment: .leading, spacing: 6) {
                        if !filters.isEmpty { activeFilters }
                        summary
                        FreshnessNote(key: datasetID)
                    }
                    .textCase(nil)
                }
                if let desc = info?.description {
                    Section { } footer: { Text(desc + " Every record links to its source; check the original before relying on one figure.") }
                }
            }
            .listStyle(.plain)
            .overlay {
                if filtered.isEmpty {
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
            }
        }
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

    private var yearMenu: some View {
        Menu {
            Picker("Year", selection: $period) {
                Text("All years").tag(Period?.none)
                ForEach(years.periods) { p in Text(p.label).tag(Period?.some(p)) }
            }
        } label: {
            HStack(spacing: 4) {
                Text(period?.label ?? "All years")
                Image(systemName: "chevron.up.chevron.down").font(.caption2.weight(.semibold))
            }
            .font(.subheadline.weight(.semibold))
            .padding(.horizontal, 10).padding(.vertical, 5)
            .foregroundStyle(Brand.navy)
            .background(Brand.navy.opacity(0.12), in: Capsule())
        }
        .accessibilityLabel("Year: \(period?.label ?? "All years")")
        .accessibilityHint("Shows records from another year")
    }

    private var summary: some View {
        let rows = filtered
        let total = spec.summable ? rows.compactMap { spec.amount($0) }.reduce(0, +) : nil
        return HStack {
            if years.periods.count > 1 { yearMenu }
            Text(period == nil
                 ? "\(Format.number(Double(rows.count))) of \(Format.number(Double(all.count))) records"
                 : "\(Format.number(Double(rows.count))) records · \(Format.number(Double(all.count))) in all")
            Spacer()
            if let total, total > 0 { Text("\(Format.compactMoney(total)) total").monospacedDigit() }
        }
        .font(.footnote)
        .foregroundStyle(.secondary)
    }

    private var activeFilters: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(filters.sorted { $0.key < $1.key }, id: \.key) { pair in
                    Button {
                        filters[pair.key] = nil
                    } label: {
                        HStack(spacing: 4) {
                            Text(pair.key == "gov_id" ? (Governments.names[pair.value] ?? pair.value) : pair.value)
                            Image(systemName: "xmark").font(.caption2.weight(.bold))
                        }
                        .font(.caption.weight(.medium))
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .foregroundStyle(Brand.navy)
                        .background(Brand.navy.opacity(0.12), in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Remove filter \(pair.value)")
                }
            }
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .topBarTrailing) {
            if hasLocations {
                Picker("View", selection: $mode) {
                    ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .frame(width: 110)
            }
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
                        } else if let b = spec.badge(row) {
                            Badge(text: b, color: Brand.status(b))
                        }
                    }
                    .padding(.vertical, 4)
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
                    let vote = (m.vote ?? "").capitalized
                    if let pid = m.pid {
                        NavigationLink(value: Route.person(pid)) {
                            HStack { Text(m.name); Spacer(); Badge(text: vote, color: vote == "Yes" ? Brand.good : vote == "No" ? Brand.salmon : .secondary) }
                        }
                    } else {
                        HStack { Text(m.name); Spacer(); Badge(text: vote, color: vote == "Yes" ? Brand.good : vote == "No" ? Brand.salmon : .secondary) }
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
