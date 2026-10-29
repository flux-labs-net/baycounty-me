import SwiftUI
import BayCountyKit

/// Every term on the site, explained simply first.
struct GlossaryView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""

    var body: some View {
        List {
            if let g = store.glossary {
                Section {
                    Text("Government money comes with a lot of jargon. Here is every term on BayCounty.me, explained simply first, with more detail after.")
                        .font(.subheadline)
                }
                ForEach(g.groups) { grp in
                    let terms = g.terms.filter { $0.group == grp.id && matches($0) }
                    if !terms.isEmpty {
                        Section(grp.name) {
                            ForEach(terms) { t in
                                Button { store.presentedTerm = t } label: {
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(t.term).font(.body.weight(.medium)).foregroundStyle(.primary)
                                        Text(t.simple).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                AppDataPending(file: "glossary.json", title: "Couldn't load the glossary") { await store.loadGlossary() }
            }
        }
        .navigationTitle("Glossary")
        .searchable(text: $query, prompt: "Find a term")
    }

    private func matches(_ t: Glossary.Term) -> Bool {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return q.isEmpty || t.term.lowercased().contains(q) || t.simple.lowercased().contains(q)
    }
}

/// The site's change log.
struct UpdatesView: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        List {
            if store.updates.isEmpty {
                AppDataPending(file: "updates.json", title: "Couldn't load updates") { await store.loadUpdates() }
            }
            ForEach(store.updates) { u in
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(u.title).font(.headline)
                        Text(u.text).font(.subheadline)
                    }
                    .padding(.vertical, 2)
                } header: {
                    Text(Dates.parse(u.date).map { Dates.display($0, hasTime: false) } ?? u.date)
                }
            }
        }
        .navigationTitle("What's new")
    }
}

/// What BayCounty.me is, where the information comes from, privacy and corrections.
struct AboutView: View {
    @Environment(AppStore.self) private var store
    @AppStorage(AppUsage.enabledKey) private var shareUsage = true

    var body: some View {
        List {
            Section {
                Text("BayCounty.me is an independent, free website and app that puts Bay County, Florida public records in one place, in plain language: all nine local governments, their budgets, taxes, contracts, votes, campaign money and meetings, plus what's happening near your address. Every figure links to its public record, back to 2016. It is not run by any government.")
                    .font(.subheadline)
            }
            Section("What the labels mean") {
                label("Spent", "Reported paid.")
                label("Committed", "Awarded, not fully paid.")
                label("Budgeted / Proposed", "Plans, not proof of payment.")
                label("Not in totals", "Totals count each dollar once. Parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out.")
            }
            Section("Who runs it") {
                Text("Built and run by Flux Labs, a managed IT company in Panama City. We live and work here, and we built this so public records are easy to read without a records request. No ads, no tracking, and no money from any government, candidate or campaign.")
                    .font(.subheadline)
            }
            Section("Data") {
                if let c = store.catalog {
                    if let u = c.updated { LabeledContent("Data updated", value: u) }
                    LabeledContent("Datasets", value: "\(c.datasets.count)")
                }
                if let r = store.lastRefresh { LabeledContent("Checked", value: r.formatted(date: .abbreviated, time: .shortened)) }
                Button { Task { await store.refreshAll() } } label: { Label("Check for new data", systemImage: "arrow.clockwise") }
            }
            Section("App") {
                LabeledContent("Version", value: Self.appVersion)
            }
            Section {
                Toggle("Share anonymous usage counts", isOn: $shareUsage)
                    .onChange(of: shareUsage) { _, on in store.usage.enabled = on }
            } footer: {
                Text("Once a day the app sends how many times it was opened and which screens were viewed, with the app version. Nothing that identifies you or your phone is sent: no name, account, address or device id. It helps us see what residents use.")
            }
            Section {
                WebLink(title: "Send a correction", symbol: "exclamationmark.bubble", url: URL(string: "https://baycounty.me/about#contact"))
                WebLink(title: "Privacy", symbol: "hand.raised", url: URL(string: "https://baycounty.me/privacy"))
                WebLink(title: "Sources and method", symbol: "doc.text", url: URL(string: "https://baycounty.me/about"))
                WebLink(title: "baycounty.me", symbol: "safari", url: URL(string: "https://baycounty.me"))
            } footer: {
                Text("No ads and no tracking. The address saved on My Address stays on your phone. A My home account keeps only your email, home address and first name, to show what's near you, and you can delete it any time.")
            }
            Section { PoweredByFlux() }.listRowBackground(Color.clear)
        }
        .navigationTitle("About")
    }

    /// "1.0 (7)": marketing version and build number, so a TestFlight or Xcode build can be told apart.
    static var appVersion: String {
        let info = Bundle.main.infoDictionary
        let v = info?["CFBundleShortVersionString"] as? String ?? "?"
        let b = info?["CFBundleVersion"] as? String ?? "?"
        return "\(v) (\(b))"
    }

    private func label(_ t: String, _ d: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(t).font(.subheadline.weight(.semibold))
            Text(d).font(.footnote).foregroundStyle(.secondary)
        }
    }
}
