import SwiftUI
import BayCountyKit

/// Every active alert, most serious first. Alerts posted by the home's own city say so.
struct AlertsView: View {
    let brief: WatchBrief.Brief

    var body: some View {
        List {
            if brief.alerts.isEmpty {
                Text(brief.headline).font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(brief.alerts) { a in
                NavigationLink { AlertDetailView(alert: a) } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        Label(a.label, systemImage: WatchStyle.symbol(a.symbol))
                            .font(.footnote.weight(.semibold)).foregroundStyle(WatchStyle.salmon)
                        Text(a.title).font(.body).lineLimit(3)
                        Text(a.nearHome ? "Your city · \(a.posted)" : a.posted).font(.footnote).foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .navigationTitle(brief.alertTitle)
        .containerBackground(WatchStyle.deep.gradient, for: .navigation)
    }
}

struct AlertDetailView: View {
    let alert: WatchBrief.Alert

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 8) {
                Label(alert.label, systemImage: WatchStyle.symbol(alert.symbol))
                    .font(.footnote.weight(.semibold)).foregroundStyle(WatchStyle.salmon)
                Text(alert.title).font(.headline)
                if !alert.summary.isEmpty { Text(alert.summary).font(.body) }
                Text([alert.source, alert.posted].filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .containerBackground(WatchStyle.deep.gradient, for: .navigation)
    }
}
