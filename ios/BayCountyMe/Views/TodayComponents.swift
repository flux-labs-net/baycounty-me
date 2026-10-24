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
            .background(Brand.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
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
            Text(Governments.initials(meeting.govID))
                .font(.footnote.weight(.bold))
                .foregroundStyle(Brand.navy)
                .frame(width: 40, height: 40)
                .background(Brand.navy.opacity(0.1), in: RoundedRectangle(cornerRadius: 11, style: .continuous))
                .accessibilityHidden(true)
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
            .background(Brand.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label), \(value)")
    }
}
