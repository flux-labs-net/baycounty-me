import SwiftUI
import BayCountyKit

/// Searches every page, record and glossary term on BayCounty.me (`/api/v1/search`). Opens from the field on Today.
struct SearchView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var results: [SearchResult] = []
    @State private var searching = false
    @State private var error: String?

    private let suggestions = ["Millville", "Front Beach Road", "stormwater", "homestead", "Lynn Haven CRA", "FEMA debris"]

    private let browse: [(title: String, symbol: String, route: Route)] = [
        ("Glossary", "character.book.closed", .glossary),
        ("Every dataset", "square.grid.2x2", .explore),
        ("Companies", "building", .vendors),
        ("Accountability console", "checklist", .accountability),
        ("People", "person.3", .people),
        ("What's new", "sparkles", .updates),
        ("About and privacy", "info.circle", .about),
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if query.trimmingCharacters(in: .whitespaces).count < 2 {
                    VStack(alignment: .leading, spacing: 10) {
                        EyebrowHeader(text: "Try")
                        FlowLayout(spacing: 8) {
                            ForEach(suggestions, id: \.self) { s in
                                Button { query = s } label: {
                                    Text(s).font(.subheadline.weight(.medium)).foregroundStyle(.primary)
                                        .padding(.horizontal, 14).frame(minHeight: 38)
                                        .background(Brand.surface, in: Capsule())
                                        .overlay { Capsule().strokeBorder(Brand.hairline) }
                                }
                                .buttonStyle(.plain)
                                .accessibilityLabel("Search for \(s)")
                            }
                        }
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        EyebrowHeader(text: "Browse")
                        CardList {
                            ForEach(browse, id: \.title) { b in
                                RouteRow(route: b.route, title: b.title, symbol: b.symbol)
                                if b.title != browse.last?.title { RowDivider(inset: 50) }
                            }
                        }
                    }
                } else if let error {
                    ContentUnavailableView("Search isn't available", systemImage: "wifi.slash", description: Text(error))
                } else if results.isEmpty && !searching {
                    ContentUnavailableView.search(text: query)
                } else if !results.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        EyebrowHeader(text: results.count == 1 ? "1 result" : "\(results.count) results")
                        CardList {
                            ForEach(results) { r in
                                Button { store.open(r.link) } label: {
                                    HStack(alignment: .top, spacing: 10) {
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(r.title ?? "Result").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                            if let s = r.summary {
                                                Text(s).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                                            }
                                        }
                                        Spacer(minLength: 4)
                                        if let t = r.type { Badge(text: t, color: Brand.blue) }
                                    }
                                    .multilineTextAlignment(.leading)
                                    .padding(14)
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                                if r.id != results.last?.id { RowDivider() }
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .background(Brand.canvas)
        .navigationTitle("Search")
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "Names, projects, streets, terms")
        .overlay { if searching && results.isEmpty { ProgressView() } }
        .task(id: query) { await run() }
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
