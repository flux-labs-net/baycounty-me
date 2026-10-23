import SwiftUI
import BayCountyKit

/// Searches every page, record and glossary term on BayCounty.me (`/api/v1/search`).
struct SearchView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var searching = false
    @State private var error: String?

    private let suggestions = ["Millville", "Front Beach Road", "stormwater", "homestead", "Lynn Haven CRA", "FEMA debris"]

    var body: some View {
        NavigationStack {
            List {
                if query.trimmingCharacters(in: .whitespaces).count < 2 {
                    Section("Try") {
                        ForEach(suggestions, id: \.self) { s in
                            Button { query = s } label: { Label(s, systemImage: "magnifyingglass") }
                        }
                    }
                    Section("Browse") {
                        NavigationLink(value: Route.glossary) { Label("Glossary", systemImage: "character.book.closed") }
                        NavigationLink(value: Route.explore) { Label("Every dataset", systemImage: "square.grid.2x2") }
                        NavigationLink(value: Route.vendors) { Label("Companies", systemImage: "building") }
                        NavigationLink(value: Route.people) { Label("People", systemImage: "person.3") }
                        NavigationLink(value: Route.updates) { Label("What's new", systemImage: "sparkles") }
                        NavigationLink(value: Route.about) { Label("About and privacy", systemImage: "info.circle") }
                    }
                } else if let error {
                    ContentUnavailableView("Search isn't available", systemImage: "wifi.slash", description: Text(error))
                } else if results.isEmpty && !searching {
                    ContentUnavailableView.search(text: query)
                } else {
                    ForEach(results) { r in
                        Button { store.open(r.link) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(r.title ?? "Result").font(.subheadline.weight(.medium)).foregroundStyle(.primary)
                                    Spacer()
                                    if let t = r.type { Badge(text: t, color: Brand.blue) }
                                }
                                if let s = r.summary {
                                    Text(s).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                                }
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }
            }
            .navigationTitle("Search")
            .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Names, projects, streets, terms")
            .overlay { if searching && results.isEmpty { ProgressView() } }
            .task(id: query) { await run() }
            .withRoutes()
        }
    }

    private func run() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else { results = []; error = nil; return }
        try? await Task.sleep(for: .milliseconds(350))   // wait for typing to pause
        guard !Task.isCancelled else { return }
        searching = true
        defer { searching = false }
        do {
            let r = try await store.client.search(q)
            guard !Task.isCancelled else { return }
            results = r; error = nil
        } catch {
            guard !Task.isCancelled else { return }
            self.error = error.localizedDescription
        }
    }
}
