import SwiftUI
import BayCountyKit

/// The site's colors (site/tokens.css) from the asset catalog, with the same dark-mode values as the resident app.
enum Brand {
    static let navy = Color("Navy")
    static let navyFill = Color("NavyFill")
    static let blue = Color("Blue")
    static let salmon = Color("Salmon")
    static let salmonFill = Color("SalmonFill")
    static let amber = Color("Amber")
    static let good = Color("Good")
    static let canvas = Color("Canvas")
    static let surface = Color("Surface")
    static let sunken = Color("Sunken")
    static let hairline = Color("Hairline")
}

extension View {
    /// A white card with a hairline edge, like the site's cards.
    func card(_ radius: CGFloat = 16) -> some View {
        background(Brand.surface, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(Brand.hairline))
    }
    /// The page background and spacing every screen shares.
    func staffPage() -> some View {
        scrollContentBackground(.hidden).background(Brand.canvas)
    }
}

struct PrimaryButton: ButtonStyle {
    var color: Color = Brand.navyFill
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .foregroundStyle(.white)
            .padding(.vertical, 14).padding(.horizontal, 18)
            .frame(minHeight: 48)
            .background(color.opacity(configuration.isPressed ? 0.85 : 1), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

/// A small uppercase label over a group.
struct Eyebrow: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(.caption.weight(.semibold)).tracking(0.6).foregroundStyle(.secondary)
    }
}

/// A count with a label; tinted when it needs attention.
struct StatTile: View {
    let value: Int
    let label: String
    var symbol: String
    var alert: Bool = false
    var tint: Color = Brand.navy

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: symbol).font(.system(size: 15, weight: .semibold))
                .foregroundStyle(alert ? Brand.salmon : tint)
                .frame(width: 30, height: 30)
                .background((alert ? Brand.salmon : tint).opacity(0.13), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            Text(value.formatted()).font(.title2.weight(.bold)).monospacedDigit()
                .foregroundStyle(alert ? Brand.salmon : .primary)
            Text(label).font(.footnote).foregroundStyle(.secondary).lineLimit(2, reservesSpace: true)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(14)
        .accessibilityElement(children: .combine)
    }
}

/// A rounded status label.
struct Chip: View {
    let text: String
    var color: Color = Brand.navy
    var body: some View {
        Text(text).font(.caption.weight(.semibold)).foregroundStyle(color)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.13), in: Capsule())
    }
}

func alertColor(_ a: StaffAlert) -> Color {
    if a.isWaiting { return Brand.amber }
    if a.isLive { return Brand.salmon }
    return .secondary
}

func flagColor(_ f: StaffFlag) -> Color {
    switch f.status { case "open": return Brand.amber; case "fixed": return Brand.good; default: return .secondary }
}

/// "Made by Flux Labs" at the foot of sign-in and lock screens.
struct FluxFooter: View {
    var body: some View {
        HStack(spacing: 6) {
            Text("Made by").font(.caption).foregroundStyle(.secondary)
            Image("FluxLogo").resizable().scaledToFit().frame(height: 14).accessibilityLabel("Flux Labs")
        }
        .padding(.bottom, 12)
    }
}

/// The government switcher in every screen's toolbar: the owner picks any government or All governments; staff with
/// more than one workspace pick theirs. Hidden for staff with one.
struct WorkspaceMenu: ToolbarContent {
    var body: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) { WorkspacePicker() }
    }
}

private struct WorkspacePicker: View {
    @Environment(StaffStore.self) private var store
    var body: some View {
        if let me = store.me, me.admin || me.workspaces.count > 1 {
            Menu {
                if me.admin {
                    Button { Task { await store.open(nil) } } label: { Label("All governments", systemImage: store.workspaceId == nil ? "checkmark" : "square.grid.2x2") }
                    Divider()
                }
                ForEach(me.workspaces) { w in
                    Button { Task { await store.open(w.id) } } label: {
                        if w.id == store.workspaceId { Label(Staff.short(w.name), systemImage: "checkmark") } else { Text(Staff.short(w.name)) }
                    }
                }
            } label: {
                HStack(spacing: 4) {
                    Text(Staff.short(store.workspace?.name) ?? "All governments").font(.subheadline.weight(.semibold)).lineLimit(1)
                    Image(systemName: "chevron.down").font(.caption2.weight(.bold))
                }
            }
            .accessibilityLabel("Government: \(Staff.short(store.workspace?.name) ?? "All governments")")
        }
    }
}

/// Shown on the per-government tabs when the owner is on All governments.
struct PickGovernment: View {
    @Environment(StaffStore.self) private var store
    let what: String
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                Text("Pick a government to see its \(what).").font(.subheadline).foregroundStyle(.secondary)
                ForEach(store.me?.workspaces ?? []) { w in
                    Button { Task { await store.open(w.id) } } label: {
                        HStack {
                            Text(Staff.short(w.name)).font(.body.weight(.semibold)).foregroundStyle(.primary)
                                .multilineTextAlignment(.leading).frame(maxWidth: .infinity, alignment: .leading)
                            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                        .padding(14).frame(minHeight: 48).card(12)
                    }
                }
            }
            .padding(16)
        }
        .background(Brand.canvas)
    }
}

/// A red line under a form when something didn't go through.
struct ErrorLine: View {
    let text: String?
    var body: some View {
        if let text, !text.isEmpty {
            Label(text, systemImage: "exclamationmark.circle").font(.footnote).foregroundStyle(Brand.salmon)
        }
    }
}
