import SwiftUI
import BayCountyKit

// The site's page look (site/ui.css): a hero card with a badge and a small section label, then sections that each
// open with a colored icon tile. Deeper screens use these so they match the government pages on BayCounty.me.

/// The four tones the site gives its icons and badges.
enum Tone {
    case blue, teal, amber, salmon

    var color: Color {
        switch self {
        case .blue: Brand.navy
        case .teal: Brand.good
        case .amber: Brand.amber
        case .salmon: Brand.salmon
        }
    }
}

/// An SF Symbol on a soft square of its tone, like the site's section icons.
struct ToneIcon: View {
    let symbol: String
    var tone: Tone = .blue
    var size: CGFloat = 30

    var body: some View {
        Image(systemName: symbol)
            .font(.system(size: size * 0.48, weight: .semibold))
            .foregroundStyle(tone.color)
            .frame(width: size, height: size)
            .background(tone.color.opacity(0.13), in: RoundedRectangle(cornerRadius: size * 0.28, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// The top of a page: a badge, a small label for where it sits, the title and a line under it.
struct PageHero<Badge: View>: View {
    let kicker: String
    let title: String
    var subtitle: String? = nil
    @ViewBuilder var badge: Badge

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            badge
            VStack(alignment: .leading, spacing: 4) {
                EyebrowHeader(text: kicker)
                Text(title).font(.title2.weight(.bold)).foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                if let subtitle, !subtitle.isEmpty {
                    Text(subtitle).font(.subheadline).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(18)
        .accessibilityElement(children: .combine)
    }
}

extension PageHero where Badge == ToneIcon {
    init(kicker: String, title: String, subtitle: String? = nil, symbol: String, tone: Tone = .blue) {
        self.init(kicker: kicker, title: title, subtitle: subtitle) { ToneIcon(symbol: symbol, tone: tone, size: 48) }
    }
}

/// A section: icon tile and heading, an optional line under it, then its content.
struct PageSection<Content: View>: View {
    let title: String
    var symbol: String? = nil
    var tone: Tone = .blue
    var caption: String? = nil
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                if let symbol { ToneIcon(symbol: symbol, tone: tone) }
                Text(title).font(.title3.weight(.bold)).accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
            }
            if let caption { Text(caption).font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            content
        }
    }
}

/// A label and a value on one line of a card, the value wrapping under the label when it's long.
struct FactRow: View {
    let label: String
    let value: String
    var detail: String? = nil

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label).font(.subheadline).foregroundStyle(.primary).fixedSize(horizontal: false, vertical: true)
                if let detail { Text(detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            }
            Spacer(minLength: 8)
            Text(value).font(.subheadline.weight(.semibold).monospacedDigit()).multilineTextAlignment(.trailing)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .accessibilityElement(children: .combine)
    }
}

/// A row on a CardList that is plain text, not a link: a title, a line or two of detail, and an optional value.
struct TextRow: View {
    let title: String
    var detail: String? = nil
    var value: String? = nil
    var badge: (text: String, color: Color)? = nil

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title).font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                if let detail, !detail.isEmpty {
                    Text(detail).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                }
                if let badge { Badge(text: badge.text, color: badge.color) }
            }
            Spacer(minLength: 6)
            if let value { Text(value).font(.subheadline.weight(.bold).monospacedDigit()) }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// A row that opens a record, with the same layout as TextRow and a chevron.
struct RecordLinkRow: View {
    let route: Route
    let title: String
    var detail: String? = nil
    var value: String? = nil

    var body: some View {
        NavigationLink(value: route) {
            HStack(spacing: 8) {
                TextRow(title: title, detail: detail, value: value)
                Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary).padding(.trailing, 14)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}

/// A scrolling page on the canvas with the standard side margins.
struct PageScroll<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) { content }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 28)
        }
        .background(Brand.canvas)
        .screenshotScroll()
    }
}

extension View {
    /// For automated screenshots: `-scrollTo <id>` starts the screen scrolled to the view marked `.id(<id>)`
    /// (charts use "chart"), once its data has had a few seconds to load.
    func screenshotScroll() -> some View {
        let args = ProcessInfo.processInfo.arguments
        let target = args.firstIndex(of: "-scrollTo").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil }
        return ScrollViewReader { proxy in
            self.task {
                guard let target else { return }
                try? await Task.sleep(for: .seconds(6))
                proxy.scrollTo(target, anchor: .top)
            }
        }
    }
}

/// Number pads have no return key, so a field using one gets a Done button above the keyboard.
/// Only the focused field shows it, so two such fields on one screen don't stack two buttons.
private struct NumberPadDone: ViewModifier {
    @FocusState private var focused: Bool
    func body(content: Content) -> some View {
        content
            .focused($focused)
            .toolbar {
                ToolbarItemGroup(placement: .keyboard) {
                    if focused {
                        Spacer()
                        Button("Done") { focused = false }.fontWeight(.semibold)
                    }
                }
            }
    }
}

extension View {
    /// Adds a Done button above the number pad (see `NumberPadDone`).
    func numberPadDone() -> some View { modifier(NumberPadDone()) }
}

/// A two-column grid of stat tiles on white cards.
struct StatGrid<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) { content }
    }
}

/// A headline number on a white card (the site's KPI card).
struct KPICard: View {
    let title: String
    let value: String
    var caption: String? = nil
    var symbol: String? = nil
    var tone: Tone = .blue

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                if let symbol { ToneIcon(symbol: symbol, tone: tone, size: 22) }
                Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary).lineLimit(2).fixedSize(horizontal: false, vertical: true)
            }
            Text(value).font(.title3.weight(.bold).monospacedDigit()).lineLimit(1).minimumScaleFactor(0.6)
            if let caption {
                Text(caption).font(.caption2).foregroundStyle(.secondary).lineLimit(3).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, minHeight: 92, alignment: .topLeading)
        .padding(12)
        .card(14)
        .accessibilityElement(children: .combine)
    }
}

/// "Source" link under a section.
struct SourceLink: View {
    @Environment(AppStore.self) private var store
    var title = "Source"
    let url: URL?

    var body: some View {
        if let url {
            Button { store.open(url) } label: {
                Label(title, systemImage: "doc.text.magnifyingglass").font(.caption.weight(.semibold))
            }
            .buttonStyle(.plain)
            .foregroundStyle(Brand.navy)
        }
    }
}

/// A short money figure; "—" when missing.
func shortMoney(_ v: Double?) -> String { v.map(Format.compactMoney) ?? "—" }

/// A PageHero as the first row of a List, for the screens that stay as long lists.
struct ListHeroSection: View {
    let kicker: String
    let title: String
    var subtitle: String? = nil
    let symbol: String
    var tone: Tone = .blue

    var body: some View {
        Section {
            PageHero(kicker: kicker, title: title, subtitle: subtitle, symbol: symbol, tone: tone)
        }
        .listRowBackground(Color.clear)
        .listRowInsets(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))
        .listRowSeparator(.hidden)
    }
}
