import SwiftUI
import BayCountyKit

struct ExploreView: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        NavigationStack {
            List {
                if store.catalog == nil {
                    if let e = store.errors["catalog"] {
                        ContentUnavailableView("Couldn't load the data list", systemImage: "wifi.slash", description: Text(e))
                    } else {
                        ProgressView().frame(maxWidth: .infinity)
                    }
                }
                ForEach(store.exploreSections, id: \.section) { group in
                    Section(group.section.rawValue) {
                        ForEach(group.datasets) { d in
                            NavigationLink(value: d.id == "cra-payments" ? Route.cra : Route.dataset(d.id)) {
                                HStack(spacing: 12) {
                                    Image(systemName: DatasetSpec.for(d.id).symbol)
                                        .foregroundStyle(Brand.navy)
                                        .frame(width: 26)
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(d.title).font(.body.weight(.medium))
                                        if let desc = d.description {
                                            Text(desc).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                                        }
                                    }
                                    Spacer()
                                    if let n = d.rows { Text(Format.number(Double(n))).font(.caption.monospacedDigit()).foregroundStyle(.secondary) }
                                }
                                .padding(.vertical, 2)
                            }
                        }
                    }
                }
                if let c = store.catalog {
                    Section {
                        WebLink(title: "Download every dataset", symbol: "arrow.down.circle", url: URL(string: "https://baycounty.me/open-data"))
                        WebLink(title: "API for developers", symbol: "curlybraces", url: URL(string: "https://baycounty.me/developers"))
                    } footer: {
                        VStack(alignment: .leading, spacing: 4) {
                            if let u = c.updated { Text("Data updated \(u).") }
                            if let l = c.license { Text(l) }
                        }
                    }
                }
            }
            .navigationTitle("Explore")
            .refreshable { await store.loadCatalog() }
            .withRoutes()
        }
    }
}
