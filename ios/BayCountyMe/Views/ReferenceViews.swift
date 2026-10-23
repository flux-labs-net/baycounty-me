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
                ProgressView().frame(maxWidth: .infinity)
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

    var body: some View {
        List {
            Section {
                Text("BayCounty.me puts Bay County, Florida public records in plain view: budgets, taxes, contracts, votes, campaign money and meetings. Every figure comes from a public record with a linked source. Nothing is estimated.")
                    .font(.subheadline)
            }
            Section("What the labels mean") {
                label("Spent", "Reported paid.")
                label("Committed", "Awarded, not fully paid.")
                label("Budgeted / Proposed", "Plans, not proof of payment.")
                label("Not in totals", "Totals count each dollar once. Parts of a listed total, possible duplicates and non-CRA money stay in the list but are left out.")
            }
            Section("Data") {
                if let c = store.catalog {
                    if let u = c.updated { LabeledContent("Data updated", value: u) }
                    LabeledContent("Datasets", value: "\(c.datasets.count)")
                }
                if let r = store.lastRefresh { LabeledContent("Checked", value: r.formatted(date: .abbreviated, time: .shortened)) }
                Button { Task { await store.refreshAll() } } label: { Label("Check for new data", systemImage: "arrow.clockwise") }
            }
            Section {
                WebLink(title: "Send a correction", symbol: "exclamationmark.bubble", url: URL(string: "https://baycounty.me/about#contact"))
                WebLink(title: "Privacy", symbol: "hand.raised", url: URL(string: "https://baycounty.me/privacy"))
                WebLink(title: "Sources and method", symbol: "doc.text", url: URL(string: "https://baycounty.me/about"))
                WebLink(title: "baycounty.me", symbol: "safari", url: URL(string: "https://baycounty.me"))
            } footer: {
                Text("The app collects no data: no accounts, analytics or ads. A saved home address stays on your phone.")
            }
            Section { PoweredByFlux() }.listRowBackground(Color.clear)
        }
        .navigationTitle("About")
    }

    private func label(_ t: String, _ d: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(t).font(.subheadline.weight(.semibold))
            Text(d).font(.footnote).foregroundStyle(.secondary)
        }
    }
}
