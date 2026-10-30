import SwiftUI
import BayCountyKit

/// The watch's one screen: alerts first (tap for the list), then trash day, the beach flag and the next meeting.
struct BriefView: View {
    @Environment(WatchModel.self) private var model

    var body: some View {
        NavigationStack {
            Group {
                if let b = model.brief {
                    if Self.screen == "faces" { FacesPreview(brief: b) } else { list(b) }
                } else { ProgressView() }
            }
            .navigationTitle("BayCounty.me")
            .containerBackground(WatchStyle.deep.gradient, for: .navigation)
            .onChange(of: model.brief != nil) { _, loaded in
                // Screenshots: `-screen alerts` opens the alert list once the brief is in.
                if loaded, Self.screen == "alerts" { showAlerts = true }
            }
            .navigationDestination(isPresented: $showAlerts) {
                if let b = model.brief { AlertsView(brief: b) }
            }
        }
    }

    @State private var showAlerts = false

    /// Screenshots: `-screen alerts` opens the alert list, `-screen faces` draws the complications.
    static var screen: String? {
        let a = ProcessInfo.processInfo.arguments
        guard let i = a.firstIndex(of: "-screen"), i + 1 < a.count else { return nil }
        return a[i + 1]
    }

    private func list(_ b: WatchBrief.Brief) -> some View {
        List {
            Section {
                Button { showAlerts = true } label: { alertCard(b) }
                    .listRowBackground(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(WatchStyle.alertColor(b).opacity(0.22)))
                    .accessibilityIdentifier("alerts")
            } header: {
                Text(b.place).font(.footnote.weight(.semibold)).foregroundStyle(WatchStyle.navy).textCase(nil)
            }

            if let t = b.trash {
                row(symbol: "trash.fill", tone: WatchStyle.teal, title: t.title, detail: t.detail)
            } else if let next = b.nextPickup {
                row(symbol: "trash", tone: WatchStyle.teal, title: next, detail: "Trash at your home")
            }
            row(symbol: "flag.fill", tone: WatchStyle.amber, title: b.beach.title, detail: b.beach.detail)
            row(symbol: "calendar", tone: WatchStyle.blue, title: b.meeting.title, detail: b.meeting.detail)

            Section {
                VStack(alignment: .leading, spacing: 4) {
                    if !b.hasHome {
                        Text("Save your home in the iPhone app to see your trash day here.")
                    }
                    if let u = model.updated {
                        Text("Updated \(u.formatted(date: .omitted, time: .shortened))")
                    }
                }
                .font(.footnote).foregroundStyle(.secondary)
                .listRowBackground(Color.clear)
            }
        }
        .refreshable { await model.refresh() }
    }

    private func alertCard(_ b: WatchBrief.Brief) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: WatchStyle.alertSymbol(b)).foregroundStyle(WatchStyle.alertColor(b))
                Text(b.alertTitle).font(.headline)
            }
            Text(b.alertCount > 0 ? b.alerts.map(\.label).uniqued().joined(separator: ", ") : b.headline)
                .font(.footnote).foregroundStyle(.secondary).lineLimit(3)
        }
        .padding(.vertical, 4)
    }

    private func row(symbol: String, tone: Color, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: symbol).foregroundStyle(tone).frame(width: 20)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.body.weight(.semibold)).lineLimit(2)
                Text(detail).font(.footnote).foregroundStyle(.secondary).lineLimit(2)
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .combine)
    }
}

extension Array where Element: Hashable {
    /// The items in order, each once.
    func uniqued() -> [Element] { var seen = Set<Element>(); return filter { seen.insert($0).inserted } }
}

#Preview { BriefView().environment(WatchModel()) }
