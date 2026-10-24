import SwiftUI
import Charts
import BayCountyKit

/// A row of headline numbers on white tiles.
struct StatStrip: View {
    let tiles: [ListSummary.Tile]

    var body: some View {
        HStack(spacing: 8) {
            ForEach(tiles) { t in
                VStack(alignment: .leading, spacing: 2) {
                    Text(t.title).font(.caption).foregroundStyle(.secondary).lineLimit(2).minimumScaleFactor(0.8)
                    Text(t.value).font(.title3.weight(.bold).monospacedDigit()).lineLimit(1).minimumScaleFactor(0.6)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(Brand.surface, in: RoundedRectangle(cornerRadius: 12))
                .accessibilityElement(children: .combine)
            }
        }
    }
}

/// Horizontal bars comparing one number across items (governments, years), with one item highlighted.
struct CompareBars: View {
    struct Item: Identifiable {
        let id: String
        let label: String
        let value: Double
    }

    let title: String
    var caption: String? = nil
    let items: [Item]
    var highlight: String? = nil
    let format: (Double) -> String
    var onTap: ((String) -> Void)? = nil
    /// Put each label on its own line above its bar, for long names.
    var labelsAbove = false

    var body: some View {
        let maxV = items.map(\.value).max() ?? 1
        VStack(alignment: .leading, spacing: 9) {
            Text(title).font(.subheadline.weight(.semibold))
            if let caption { Text(caption).font(.caption).foregroundStyle(.secondary) }
            ForEach(items) { item in
                let on = highlight == nil || highlight == item.id
                let row = VStack(alignment: .leading, spacing: 3) {
                  if labelsAbove {
                    Text(item.label).font(.caption.weight(highlight == item.id ? .bold : .regular))
                        .foregroundStyle(.primary).lineLimit(2)
                  }
                  HStack(spacing: 8) {
                    if !labelsAbove {
                        Text(item.label).font(.caption.weight(highlight == item.id ? .bold : .regular))
                            .foregroundStyle(.primary).lineLimit(1).minimumScaleFactor(0.8).frame(width: 122, alignment: .leading)
                    }
                    GeometryReader { g in
                        Capsule().fill(on ? Brand.navy : Brand.navy.opacity(0.25))
                            .frame(width: max(4, g.size.width * (maxV > 0 ? item.value / maxV : 0)))
                    }
                    .frame(height: 10)
                    Text(format(item.value)).font(.caption.weight(.semibold).monospacedDigit())
                        .foregroundStyle(.primary).frame(width: 58, alignment: .trailing)
                  }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(item.label): \(format(item.value))")
                if let onTap {
                    Button { onTap(item.id) } label: { row }.buttonStyle(.plain)
                } else {
                    row
                }
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Brand.surface, in: RoundedRectangle(cornerRadius: 12))
    }
}

/// One bar split into parts (yes / no / absent; raised / spent), with a legend underneath.
struct ShareBar: View {
    struct Part: Identifiable {
        let label: String
        let value: Double
        let color: Color
        var id: String { label }
    }

    let parts: [Part]
    var valueText: (Double) -> String = { Format.number($0) }

    var body: some View {
        let total = parts.map(\.value).reduce(0, +)
        VStack(alignment: .leading, spacing: 8) {
            GeometryReader { g in
                HStack(spacing: 2) {
                    ForEach(parts.filter { $0.value > 0 }) { p in
                        Rectangle().fill(p.color).frame(width: max(3, (g.size.width - 6) * p.value / max(total, 1)))
                    }
                }
                .clipShape(Capsule())
            }
            .frame(height: 14)
            .accessibilityHidden(true)
            HStack(spacing: 14) {
                ForEach(parts) { p in
                    HStack(spacing: 5) {
                        RoundedRectangle(cornerRadius: 2).fill(p.color).frame(width: 10, height: 10)
                        Text("\(p.label) \(valueText(p.value))").font(.caption).foregroundStyle(.secondary)
                        if total > 0 { Text("\(Int((p.value / total * 100).rounded()))%").font(.caption.weight(.semibold)) }
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

/// Topics as a two-column grid of cards with an icon, a title and a short line.
struct TopicGrid: View {
    struct Topic: Identifiable {
        let title: String
        let symbol: String
        let detail: String
        let route: Route
        var id: String { title }
    }

    let topics: [Topic]

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
            ForEach(topics) { t in
                NavigationLink(value: t.route) {
                    VStack(alignment: .leading, spacing: 6) {
                        Image(systemName: t.symbol).font(.title3).foregroundStyle(Brand.navy)
                            .frame(width: 36, height: 36)
                            .background(Brand.navy.opacity(0.1), in: RoundedRectangle(cornerRadius: 9))
                        Text(t.title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                            .multilineTextAlignment(.leading).lineLimit(2)
                        Text(t.detail).font(.caption).foregroundStyle(.secondary)
                            .multilineTextAlignment(.leading).lineLimit(3)
                        Spacer(minLength: 0)
                    }
                    .frame(maxWidth: .infinity, minHeight: 128, alignment: .topLeading)
                    .padding(12)
                    .background(Brand.surface, in: RoundedRectangle(cornerRadius: 14))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

/// A small bar chart of amounts by year (a company's contracts, an official's pay).
struct YearBars: View {
    let title: String
    let points: [(label: String, value: Double)]
    var format: (Double) -> String = Format.compactMoney

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.subheadline.weight(.semibold))
            Chart(Array(points.enumerated()), id: \.offset) { _, p in
                BarMark(x: .value("Year", p.label), y: .value("Amount", p.value))
                    .foregroundStyle(Brand.navy)
                    .cornerRadius(3)
                    .annotation(position: .top) { Text(format(p.value)).font(.caption2).foregroundStyle(.secondary) }
            }
            .chartYAxis(.hidden)
            .frame(height: 120)
            .accessibilityLabel(title)
            .accessibilityValue(points.map { "\($0.label) \(format($0.value))" }.joined(separator: ", "))
        }
        .padding(14)
        .background(Brand.surface, in: RoundedRectangle(cornerRadius: 12))
    }
}
