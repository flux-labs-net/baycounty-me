import SwiftUI
import BayCountyKit

/// A section title with an optional text button on the right ("See all").
struct SectionHeader: View {
    let title: String
    var action: String? = nil
    var onAction: (() -> Void)? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title).font(.title3.weight(.bold))
            Spacer()
            if let action, let onAction {
                Button(action, action: onAction).font(.subheadline.weight(.semibold)).foregroundStyle(Brand.navy)
            }
        }
    }
}

/// Rows on one rounded card, the grouped-list look without a List.
struct CardList<Content: View>: View {
    @ViewBuilder let content: Content

    var body: some View {
        VStack(spacing: 0) { content }
            .card(16)
    }
}

/// A meeting on the Today tab: government badge, board, time and place, and the dollars on its agenda.
struct TodayMeetingRow: View {
    let meeting: Meeting

    /// "Bay County Govt. Center - 840 W. 11th St Panama City FL" -> "Bay County Govt. Center"
    private var place: String? {
        guard let loc = meeting.location else { return nil }
        let first = loc.components(separatedBy: " - ").first ?? loc
        return (first.components(separatedBy: ",").first ?? first).trimmingCharacters(in: .whitespaces)
    }

    var body: some View {
        HStack(spacing: 12) {
            GovBadge(govID: meeting.govID)
            VStack(alignment: .leading, spacing: 2) {
                Text(meeting.boardName).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text([meeting.hasTime ? meeting.start.map { MeetingRow.time.string(from: $0) } : "Time not posted", place]
                        .compactMap { $0 }.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 4)
            if meeting.moneyTotal > 0 {
                Text(Format.compactMoney(meeting.moneyTotal))
                    .font(.caption.weight(.bold).monospacedDigit())
                    .foregroundStyle(Brand.good)
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background(Brand.good.opacity(0.14), in: Capsule())
                    .accessibilityLabel("\(Format.compactMoney(meeting.moneyTotal)) on the agenda")
            } else if meeting.isExpected {
                Badge(text: "Expected", color: Brand.amber)
            }
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14)
        .frame(minHeight: 64)
        .contentShape(Rectangle())
    }
}

/// A big number with a small bar chart of how it splits across governments, biggest first.
struct NumberTile: View {
    let value: String
    let label: String
    let bars: [Double]
    let color: Color
    let route: Route

    var body: some View {
        NavigationLink(value: route) {
            VStack(alignment: .leading, spacing: 8) {
                let top = Array(bars.sorted(by: >).prefix(5))
                let peak = max(top.first ?? 1, 1)
                HStack(alignment: .bottom, spacing: 4) {
                    ForEach(Array(top.enumerated()), id: \.offset) { i, v in
                        RoundedRectangle(cornerRadius: 3)
                            .fill(color.opacity(1 - Double(i) * 0.16))
                            .frame(height: max(3, 28 * v / peak))
                    }
                }
                .frame(height: 28, alignment: .bottom)
                .accessibilityHidden(true)
                Text(value).font(.title2.weight(.heavy).monospacedDigit()).foregroundStyle(.primary).lineLimit(1).minimumScaleFactor(0.7)
                Text(label).font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .card(16)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label), \(value)")
    }
}

/// The government's two-letter badge (BC, PC, LH...).
struct GovBadge: View {
    let govID: String

    var body: some View {
        Text(Governments.initials(govID))
            .font(.footnote.weight(.bold))
            .foregroundStyle(Brand.navy)
            .frame(width: 40, height: 40)
            .background(Brand.navy.opacity(0.1), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// One row on a CardList: optional icon, title, a line of detail, a number on the right, and a chevron.
struct RowLabel: View {
    let title: String
    var detail: String? = nil
    var symbol: String? = nil
    var value: String? = nil

    var body: some View {
        HStack(spacing: 12) {
            if let symbol {
                Image(systemName: symbol).foregroundStyle(Brand.navy).frame(width: 24).accessibilityHidden(true)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(detail == nil ? .body : .subheadline.weight(.semibold)).foregroundStyle(.primary)
                if let detail { Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2) }
            }
            Spacer(minLength: 4)
            if let value {
                Text(value).font(.subheadline.weight(.bold).monospacedDigit()).foregroundStyle(.primary)
            }
            Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, detail == nil ? 0 : 10)
        .frame(minHeight: detail == nil ? 50 : 62)
        .contentShape(Rectangle())
    }
}

/// A NavigationLink row for a CardList.
struct RouteRow: View {
    let route: Route
    let title: String
    var detail: String? = nil
    var symbol: String? = nil
    var value: String? = nil

    var body: some View {
        NavigationLink(value: route) { RowLabel(title: title, detail: detail, symbol: symbol, value: value) }
            .buttonStyle(.plain)
    }
}

/// A row for a CardList that opens a website page in the in-app browser.
struct WebRow: View {
    @Environment(AppStore.self) private var store
    let title: String
    var detail: String? = nil
    var symbol: String? = nil
    let url: URL?

    var body: some View {
        if let url {
            Button { store.open(url) } label: { RowLabel(title: title, detail: detail, symbol: symbol) }
                .buttonStyle(.plain)
        }
    }
}

/// The divider between rows on a CardList, inset past an icon or badge.
struct RowDivider: View {
    var inset: CGFloat = 14
    var body: some View { Divider().padding(.leading, inset) }
}

/// The app's one switcher: a set of pill buttons, one selected (navy), filling the width. Chips that don't fit
/// wrap into evenly split lines (4 become 2 + 2), so every choice is always in view with no sideways scrolling.
/// Every chip is at least 44pt tall.
/// `counts` adds a number after a label ("Split 6").
struct ChipRow<ID: Hashable>: View {
    let chips: [(id: ID, label: String)]
    let selected: ID
    var counts: [ID: Int] = [:]
    let onPick: (ID) -> Void

    var body: some View {
        ChipLayout(spacing: 8) {
            ForEach(chips, id: \.id) { c in
                let on = c.id == selected
                Button { onPick(c.id) } label: {
                    HStack(spacing: 5) {
                        Text(c.label)
                        if let n = counts[c.id] {
                            Text("\(n)").fontWeight(.medium).monospacedDigit()
                                .foregroundStyle(on ? Color.white.opacity(0.75) : .secondary)
                        }
                    }
                    .font(.subheadline.weight(.semibold))
                    .lineLimit(1)
                    .padding(.horizontal, 16)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .foregroundStyle(on ? Color.white : .primary)
                    .background(on ? Brand.navyFill : Brand.surface, in: Capsule())
                    .overlay { Capsule().strokeBorder(on ? Color.clear : Brand.hairline) }
                    .contentShape(Capsule())
                }
                .buttonStyle(PressScale())
                .accessibilityLabel(counts[c.id].map { "\(c.label), \($0)" } ?? c.label)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }
}

/// Lays chips out in as few lines as fit, splitting them evenly across lines (5 become 3 + 2, never 4 + 1),
/// and stretches each line to the full width, sharing the spare room equally between its chips.
struct ChipLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? subviews.map { $0.sizeThatFits(.unspecified).width }.reduce(0, +)
            + spacing * CGFloat(max(subviews.count - 1, 0))
        let lines = arrange(width: width, subviews: subviews)
        let height = lines.map { line in line.map { subviews[$0].sizeThatFits(.unspecified).height }.max() ?? 0 }.reduce(0, +)
            + spacing * CGFloat(max(lines.count - 1, 0))
        return CGSize(width: width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for line in arrange(width: bounds.width, subviews: subviews) {
            let sizes = line.map { subviews[$0].sizeThatFits(.unspecified) }
            let used = sizes.map(\.width).reduce(0, +) + spacing * CGFloat(line.count - 1)
            let extra = max(0, bounds.width - used) / CGFloat(line.count)
            let height = sizes.map(\.height).max() ?? 0
            var x = bounds.minX
            for (i, size) in zip(line, sizes) {
                let w = min(size.width + extra, bounds.width)
                subviews[i].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(width: w, height: height))
                x += w + spacing
            }
            y += height + spacing
        }
    }

    /// The fewest lines whose even split fits the width.
    private func arrange(width: CGFloat, subviews: Subviews) -> [[Int]] {
        let n = subviews.count
        guard n > 0 else { return [] }
        let widths = subviews.map { $0.sizeThatFits(.unspecified).width }
        for lines in 1...n {
            let per = Int((Double(n) / Double(lines)).rounded(.up))
            let split = stride(from: 0, to: n, by: per).map { Array($0..<min($0 + per, n)) }
            let fits = split.allSatisfy { line in
                line.map { widths[$0] }.reduce(0, +) + spacing * CGFloat(line.count - 1) <= width
            }
            if fits { return split }
        }
        return (0..<n).map { [$0] }
    }
}

/// Press feedback for chips and buttons: a quick shrink to 96%, released as soon as the finger lifts.
struct PressScale: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

/// A small caps label above a group ("TRY", "BROWSE").
struct EyebrowHeader: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(.footnote.weight(.bold)).tracking(0.8).foregroundStyle(.secondary)
            .accessibilityAddTraits(.isHeader)
    }
}

extension View {
    /// The app's page look: lists and scroll views sit on the light canvas, cards are white.
    func pageBackground() -> some View {
        scrollContentBackground(.hidden).background(Brand.canvas)
    }
}

/// Lays children out in rows, wrapping to a new line when the next one doesn't fit.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        let height = rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(rows.count - 1, 0))
        return CGSize(width: proposal.width ?? rows.map(\.width).max() ?? 0, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in arrange(width: bounds.width, subviews: subviews) {
            var x = bounds.minX
            for i in row.items {
                let size = subviews[i].sizeThatFits(.unspecified)
                subviews[i].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row { var items: [Int] = []; var width: CGFloat = 0; var height: CGFloat = 0 }

    private func arrange(width: CGFloat, subviews: Subviews) -> [Row] {
        var rows: [Row] = [Row()]
        for i in subviews.indices {
            let size = subviews[i].sizeThatFits(.unspecified)
            let extra = rows[rows.count - 1].items.isEmpty ? size.width : size.width + spacing
            if rows[rows.count - 1].width + extra > width, !rows[rows.count - 1].items.isEmpty {
                rows.append(Row())
            }
            let gap: CGFloat = rows[rows.count - 1].items.isEmpty ? 0 : spacing
            rows[rows.count - 1].items.append(i)
            rows[rows.count - 1].width += size.width + gap
            rows[rows.count - 1].height = max(rows[rows.count - 1].height, size.height)
        }
        return rows
    }
}

extension View {
    /// A white card with a hairline edge, so it stays distinct from the canvas in dark mode.
    func card(_ radius: CGFloat = 16) -> some View {
        background(Brand.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay { RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(Brand.hairline) }
    }
}
