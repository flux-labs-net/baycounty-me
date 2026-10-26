import SwiftUI
import Charts
import BayCountyKit

// MARK: - Chips

/// The look of a menu chip: filled navy for the current year, outlined for other choices.
struct ChipLabel: View {
    let text: String
    var filled = false

    var body: some View {
        HStack(spacing: 4) {
            Text(text)
            Image(systemName: "chevron.up.chevron.down").font(.caption2.weight(.semibold))
        }
        .font(.subheadline.weight(.semibold))
        .padding(.horizontal, 16)
        .frame(minHeight: 40)
        .foregroundStyle(filled ? Color.white : Brand.navy)
        .background(filled ? AnyShapeStyle(Brand.navyFill) : AnyShapeStyle(Brand.surface), in: Capsule())
        .overlay { if !filled { Capsule().strokeBorder(Brand.navy.opacity(0.2)) } }
    }
}

/// A filter in force, tapped to remove it.
struct FilterChip: View {
    let text: String
    let remove: () -> Void

    var body: some View {
        Button(action: remove) {
            HStack(spacing: 4) {
                Text(text).lineLimit(1)
                Image(systemName: "xmark").font(.caption2.weight(.bold))
            }
            .font(.footnote.weight(.medium))
            .padding(.horizontal, 12)
            .frame(minHeight: 34)
            .foregroundStyle(Brand.navy)
            .background(Brand.navy.opacity(0.12), in: Capsule())
            .padding(.vertical, 5)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScale())
        .accessibilityLabel("Remove filter \(text)")
    }
}

// MARK: - Summary

/// Headline numbers, a bar chart by month or year (tap a bar to see its records), and the biggest names.
struct ListSummary: View {
    struct Tile: Identifiable {
        let title: String
        let value: String
        var id: String { title }
    }

    let tiles: [Tile]
    let chartTitle: String
    let buckets: [Browse.Bucket]
    let byAmount: Bool
    @Binding var selected: String?
    let topTitle: String?
    let top: [Browse.Bucket]
    let onTop: (String) -> Void
    var countUnit: String? = nil
    let note: String?

    var body: some View {
        VStack(spacing: 10) {
            if !tiles.isEmpty {
                HStack(spacing: 8) {
                    ForEach(tiles) { t in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(t.title).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                            Text(t.value).font(.title3.weight(.bold).monospacedDigit()).lineLimit(1).minimumScaleFactor(0.6)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 12).padding(.vertical, 10)
                        .card(12)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            if !buckets.isEmpty {
                BucketChart(title: chartTitle, buckets: buckets, byAmount: byAmount, selected: $selected)
            }
            if let topTitle, top.count >= 2 {
                TopBars(title: topTitle, items: top, byAmount: byAmount, countUnit: countUnit, onTap: onTop)
            }
            if let note {
                Text(note).font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

struct BucketChart: View {
    let title: String
    let buckets: [Browse.Bucket]
    let byAmount: Bool
    @Binding var selected: String?
    @State private var touched: String?

    private func value(_ b: Browse.Bucket) -> Double { byAmount ? b.amount : Double(b.count) }
    private func text(_ v: Double) -> String { byAmount ? Format.compactMoney(v) : Format.number(v) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(.subheadline.weight(.semibold))
                Spacer()
                if selected != nil {
                    Button("Show all") { selected = nil }.font(.caption.weight(.medium))
                } else {
                    Text("Tap a bar").font(.caption).foregroundStyle(.secondary)
                }
            }
            Chart(buckets) { b in
                BarMark(x: .value("Period", b.label), y: .value("Value", value(b)), width: .ratio(0.7))
                    .foregroundStyle(selected == nil || selected == b.key ? Brand.navy : Brand.navy.opacity(0.25))
                    .cornerRadius(3)
            }
            .chartYAxis {
                AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { v in
                    AxisGridLine().foregroundStyle(Brand.hairline)
                    AxisValueLabel { if let d = v.as(Double.self) { Text(text(d)).font(.caption2) } }
                }
            }
            .chartXAxis {
                // A label under every bar runs together past six or so; show every other (or third), always the newest.
                AxisMarks(values: ChartTicks.shownLabels(buckets.map(\.label))) { v in
                    AxisValueLabel(collisionResolution: .disabled) { if let s = v.as(String.self) { Text(s).font(.caption2) } }
                }
            }
            .chartXSelection(value: $touched)
            .onChange(of: touched) { _, label in
                guard let label, let b = buckets.first(where: { $0.label == label }) else { return }
                selected = selected == b.key ? nil : b.key
            }
            .frame(height: 130)
            .accessibilityLabel(title)
            .accessibilityValue(buckets.map { "\($0.label) \(text(value($0)))" }.joined(separator: ", "))

            if let s = selected, let b = buckets.first(where: { $0.key == s }) {
                Text("\(b.key.count == 7 ? Browse.monthName(b.key, withYear: false) : b.label): \(byAmount ? Format.compactMoney(b.amount) + " across " : "")\(b.count) \(b.count == 1 ? "record" : "records")")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .card(12)
    }
}

/// The biggest names in a list, as bars. Tapping one filters the list to it.
struct TopBars: View {
    let title: String
    let items: [Browse.Bucket]
    let byAmount: Bool
    /// Shows how many records make up each total ("12 gifts") next to the amount.
    var countUnit: String? = nil
    let onTap: (String) -> Void

    var body: some View {
        let maxV = items.map { byAmount ? $0.amount : Double($0.count) }.max() ?? 1
        VStack(alignment: .leading, spacing: 10) {
            Text(title).font(.subheadline.weight(.semibold))
            ForEach(items) { item in
                let v = byAmount ? item.amount : Double(item.count)
                Button { onTap(item.key) } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(item.label).font(.subheadline).lineLimit(1).foregroundStyle(.primary)
                            Spacer(minLength: 8)
                            if byAmount, let u = countUnit {
                                Text("\(item.count) \(item.count == 1 ? u : u + "s")").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                            }
                            Text(byAmount ? Format.compactMoney(v) : "\(item.count)")
                                .font(.subheadline.weight(.semibold).monospacedDigit()).foregroundStyle(.primary)
                        }
                        MagnitudeBar(fraction: maxV > 0 ? v / maxV : 0, height: 6)
                    }
                }
                .buttonStyle(.plain)
                .accessibilityHint("Shows only these records")
            }
        }
        .padding(14)
        .card(12)
    }
}

/// A thin bar showing how big one amount is next to the largest in view.
struct MagnitudeBar: View {
    let fraction: Double
    var height: CGFloat = 4

    var body: some View {
        GeometryReader { g in
            ZStack(alignment: .leading) {
                Capsule().fill(Brand.sunken)
                Capsule().fill(Brand.blue).frame(width: max(height, g.size.width * min(max(fraction, 0), 1)))
            }
        }
        .frame(height: height)
        .accessibilityHidden(true)
    }
}

// MARK: - Grouped list

struct GroupHeader: View {
    let title: String
    var subtitle: String? = nil
    let count: Int
    var noun = "record"
    let total: Double?

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.headline).foregroundStyle(.primary).lineLimit(2)
                if let subtitle { Text(subtitle).font(.caption).foregroundStyle(.secondary) }
            }
            Spacer(minLength: 4)
            Text([Format.number(Double(count)) + " " + (count == 1 ? noun : noun + "s"), total.map(Format.compactMoney)]
                    .compactMap { $0 }.joined(separator: " · "))
                .font(.caption).foregroundStyle(.secondary).monospacedDigit()
        }
        .textCase(nil)
    }
}

/// One record in a line or two: name and amount, then a size bar and where and when.
struct CompactRecordRow: View {
    let spec: DatasetSpec
    let row: Row
    let maxAmount: Double
    /// A column the group header already names.
    var hide: String? = nil

    private var meta: String {
        spec.subtitleKeys
            .filter { $0 != spec.titleKeys.first && $0 != hide }
            .compactMap { key -> String? in
                guard let v = row[key], !v.isEmpty else { return nil }
                let s = Format.value(v, column: key)
                return ["government", "gov", "employer", "gov_id", "board"].contains(key) ? Browse.shortGovernment(s) : s
            }
            .joined(separator: " · ")
    }

    var body: some View {
        let amount = spec.amount(row)
        VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(spec.title(row)).font(.subheadline.weight(.semibold)).lineLimit(2)
                Spacer(minLength: 4)
                if let amount { Text(Format.compactMoney(amount)).font(.subheadline.weight(.semibold).monospacedDigit()) }
            }
            HStack(spacing: 8) {
                if let amount, maxAmount > 0 {
                    MagnitudeBar(fraction: amount / maxAmount).frame(maxWidth: .infinity)
                }
                let m = meta
                if !m.isEmpty {
                    Text(m).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                        .layoutPriority(1)
                }
                if amount == nil { Spacer(minLength: 0) }
                if let b = spec.badge(row) { Badge(text: b, color: Brand.status(b)) }
            }
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Table

enum TableColumn: String, CaseIterable {
    case date = "Date", title = "Name", gov = "Gov", amount = "Amount"

    static func columns(spec: DatasetSpec, hasDates: Bool, govColumn: String?) -> [TableColumn] {
        var c: [TableColumn] = []
        if hasDates { c.append(.date) }
        c.append(.title)
        if govColumn != nil { c.append(.gov) }
        if !spec.amountKeys.isEmpty { c.append(.amount) }
        return c
    }
}

struct TableSort: Equatable {
    var column: TableColumn
    var ascending: Bool

    func apply(_ rows: [Row], spec: DatasetSpec, govColumn: String?) -> [Row] {
        let sorted: [Row]
        switch column {
        case .date: sorted = rows.sorted { spec.newestKey($0) < spec.newestKey($1) }
        case .title: sorted = rows.sorted { spec.title($0).localizedCaseInsensitiveCompare(spec.title($1)) == .orderedAscending }
        case .gov: sorted = rows.sorted { ($0.string(govColumn ?? "") ?? "~") < ($1.string(govColumn ?? "") ?? "~") }
        case .amount: sorted = rows.sorted { (spec.amount($0) ?? -.infinity) < (spec.amount($1) ?? -.infinity) }
        }
        return ascending ? sorted : sorted.reversed()
    }
}

/// Records lined up in columns. Tap a column heading to sort by it; tap again to flip the order.
struct RecordTable<Header: View>: View {
    typealias Column = TableColumn

    let spec: DatasetSpec
    let rows: [Row]
    let columns: [Column]
    @Binding var sort: TableSort
    let govColumn: String?
    let open: (Row) -> Void
    @ViewBuilder let header: () -> Header

    private func width(_ c: Column) -> CGFloat? {
        switch c { case .date: 58; case .gov: 74; case .amount: 70; case .title: nil }
    }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0, pinnedViews: [.sectionHeaders]) {
                header()
                Section {
                    ForEach(Array(rows.enumerated()), id: \.element.id) { i, row in
                        Button { open(row) } label: { line(row) }
                            .buttonStyle(.plain)
                            .background(i.isMultiple(of: 2) ? Brand.surface : Brand.canvas)
                    }
                } header: {
                    headings
                }
            }
        }
        .background(Brand.surface)
    }

    private var headings: some View {
        HStack(spacing: 8) {
            ForEach(columns, id: \.self) { c in
                Button {
                    sort = sort.column == c ? TableSort(column: c, ascending: !sort.ascending)
                                            : TableSort(column: c, ascending: c == .title || c == .gov)
                } label: {
                    HStack(spacing: 2) {
                        Text(c == .title ? Browse.GroupKey.column(spec.titleKeys.first ?? "name").label : c.rawValue)
                        if sort.column == c { Image(systemName: sort.ascending ? "chevron.up" : "chevron.down").font(.caption2.weight(.bold)) }
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(sort.column == c ? Brand.navy : .secondary)
                    .frame(maxWidth: width(c) ?? .infinity, alignment: c == .amount ? .trailing : .leading)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Sort by \(c.rawValue)")
            }
        }
        .padding(.horizontal, 16).padding(.vertical, 9)
        .background(Brand.sunken)
    }

    private func line(_ row: Row) -> some View {
        HStack(spacing: 8) {
            ForEach(columns, id: \.self) { c in
                cell(c, row).frame(maxWidth: width(c) ?? .infinity, alignment: c == .amount ? .trailing : .leading)
            }
        }
        .font(.subheadline)
        .padding(.horizontal, 16)
        .frame(minHeight: 44)
        .contentShape(Rectangle())
    }

    @ViewBuilder private func cell(_ c: Column, _ row: Row) -> some View {
        switch c {
        case .date: Text(RecordTable.shortDate(row)).foregroundStyle(.secondary).lineLimit(1)
        case .title: Text(spec.title(row)).lineLimit(1)
        case .gov: Text(govColumn.flatMap { row.string($0) }.map(Browse.shortGovernment) ?? "").font(.caption).foregroundStyle(.secondary).lineLimit(1)
        case .amount: Text(spec.amount(row).map(Format.compactMoney) ?? "").fontWeight(.semibold).monospacedDigit()
        }
    }

    static func shortDate(_ row: Row) -> String { tableShortDate(row) }
}

/// "Oct 22" this year, "Oct '25" in earlier years, or the fiscal year for records without a date.
func tableShortDate(_ row: Row) -> String {
    if let s = row.first(Period.eventKeys + ["date_end"]), let d = Dates.parse(s) {
        let f = DateFormatter()
        f.dateFormat = Calendar.current.component(.year, from: d) == Calendar.current.component(.year, from: Date()) ? "MMM d" : "MMM ''yy"
        return f.string(from: d)
    }
    return Period.of(row)?.label ?? ""
}

// MARK: - Votes

/// One mark per member: filled for yes, a ring for no, grey for absent or abstained.
struct VoteDots: View {
    let summary: VoteSummary
    var size: CGFloat = 12

    private var choices: [VoteSummary.Choice] {
        if !summary.members.isEmpty {
            return summary.members.sorted { order($0.choice) < order($1.choice) }.map(\.choice)
        }
        return Array(repeating: .yes, count: summary.yes) + Array(repeating: .no, count: summary.no)
    }

    private func order(_ c: VoteSummary.Choice) -> Int { c == .yes ? 0 : c == .no ? 1 : 2 }

    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(choices.prefix(11).enumerated()), id: \.offset) { _, c in
                switch c {
                case .yes: Circle().fill(Brand.good).frame(width: size, height: size)
                case .no: Circle().strokeBorder(Brand.salmon, lineWidth: 2.5).frame(width: size, height: size)
                case .other: Circle().fill(Color.secondary.opacity(0.3)).frame(width: size, height: size)
                }
            }
        }
        .accessibilityElement()
        .accessibilityLabel("\(summary.yes) yes, \(summary.no) no" + (summary.other > 0 ? ", \(summary.other) absent" : ""))
    }
}

/// One member's vote as a single mark, with the word beside it.
struct VoteMark: View {
    let choice: VoteSummary.Choice

    var body: some View {
        HStack(spacing: 5) {
            switch choice {
            case .yes: Circle().fill(Brand.good).frame(width: 12, height: 12)
            case .no: Circle().strokeBorder(Brand.salmon, lineWidth: 2.5).frame(width: 12, height: 12)
            case .other: Circle().fill(Color.secondary.opacity(0.3)).frame(width: 12, height: 12)
            }
            Text(choice == .yes ? "Yes" : choice == .no ? "No" : "Absent").font(.caption.weight(.medium)).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

struct VoteLegend: View {
    var body: some View {
        HStack(spacing: 14) {
            Label { Text("Yes") } icon: { Circle().fill(Brand.good).frame(width: 10, height: 10) }
            Label { Text("No") } icon: { Circle().strokeBorder(Brand.salmon, lineWidth: 2).frame(width: 10, height: 10) }
            Label { Text("Absent") } icon: { Circle().fill(Color.secondary.opacity(0.3)).frame(width: 10, height: 10) }
            Spacer()
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .accessibilityHidden(true)
    }
}

struct VoteRow: View {
    let row: Row
    let summary: VoteSummary

    private var outcome: String {
        switch summary.passed {
        case true?: "Passed"
        case false?: "Failed"
        case nil: (row.string("outcome") ?? "Outcome not published").capitalizingFirst
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(row.string("headline") ?? "Vote").font(.subheadline.weight(.semibold)).lineLimit(3)
                Spacer(minLength: 4)
                if let a = row.number("amount") { Text(Format.compactMoney(a)).font(.subheadline.weight(.semibold).monospacedDigit()) }
            }
            HStack(spacing: 8) {
                if summary.hasTally { VoteDots(summary: summary) }
                Text(summary.hasTally && summary.passed != nil ? "\(outcome) \(summary.tallyText)" : outcome)
                    .font(.caption.weight(summary.passed == false ? .bold : .regular))
                    .foregroundStyle(summary.passed == false ? .primary : .secondary)
                    .lineLimit(1)
                Spacer(minLength: 0)
                if summary.split { Badge(text: "Split", color: Brand.amber) }
            }
        }
        .padding(.vertical, 2)
    }
}

extension String {
    var capitalizingFirst: String { prefix(1).uppercased() + dropFirst() }
}
