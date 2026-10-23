import Foundation
import Observation
import BayCountyKit

/// App-wide state: the catalog, governments, meetings and any dataset rows loaded so far.
@MainActor
@Observable
final class AppStore {
    enum Tab: Hashable { case home, governments, meetings, explore, search }

    let client = BayCountyClient(seedBundle: .main)

    var tab: Tab = .home
    /// A page the app is showing in the in-app browser.
    var presentedPage: PresentedPage?

    private(set) var catalog: Catalog?
    private(set) var governments: [Government] = []
    private(set) var meetings: [Meeting] = []
    private(set) var rows: [String: [Row]] = [:]
    private(set) var searchIndex: [String: [Int: String]] = [:]
    private(set) var freshness: [String: BayCountyClient.Freshness] = [:]
    private(set) var errors: [String: String] = [:]
    private(set) var loading: Set<String> = []
    private(set) var lastRefresh: Date?

    /// True when anything on screen came from a saved or bundled copy rather than the live site.
    var isShowingSavedData: Bool { freshness.values.contains { $0 != .live } }

    func loadEssentials() async {
        await loadCatalog()
        await loadGovernments()
        await loadMeetings()
        lastRefresh = Date()
    }

    func refreshAll() async {
        await loadEssentials()
        for id in rows.keys { await load(id, force: true) }
    }

    func loadCatalog() async {
        do {
            let (c, f) = try await client.catalog()
            catalog = c; freshness["catalog"] = f; errors["catalog"] = nil
        } catch { errors["catalog"] = error.localizedDescription }
    }

    func loadGovernments() async {
        do {
            let (g, f) = try await client.governments()
            governments = g; freshness["government-profiles"] = f
        } catch { errors["government-profiles"] = error.localizedDescription }
    }

    func loadMeetings() async {
        do {
            let (m, f) = try await client.meetings()
            meetings = m; freshness["meetings"] = f
        } catch { errors["meetings"] = error.localizedDescription }
    }

    func load(_ id: String, force: Bool = false) async {
        guard force || rows[id] == nil, !loading.contains(id) else { return }
        loading.insert(id); defer { loading.remove(id) }
        do {
            let (r, f) = try await client.rows(datasetID: id)
            rows[id] = r
            searchIndex[id] = Dictionary(uniqueKeysWithValues: r.map { ($0.id, $0.searchText) })
            freshness[id] = f; errors[id] = nil
        } catch { errors[id] = error.localizedDescription }
    }

    func info(_ id: String) -> DatasetInfo? { catalog?.dataset(id) }
    func government(_ govID: String) -> Government? { governments.first { $0.govID == govID } }

    func matches(_ id: String, row: Row, query: String) -> Bool {
        guard !query.isEmpty else { return true }
        let text = searchIndex[id]?[row.id] ?? row.searchText
        return query.lowercased().split(separator: " ").allSatisfy { text.contains($0) }
    }

    /// Datasets in Explore, grouped the way the website's menu groups them.
    var exploreSections: [(section: DatasetSpec.Section, datasets: [DatasetInfo])] {
        let shown = (catalog?.datasets ?? []).filter { !DatasetSpec.ownScreens.contains($0.id) }
        return DatasetSpec.Section.allCases.compactMap { section in
            let ds = shown.filter { DatasetSpec.for($0.id).section == section }
            return ds.isEmpty ? nil : (section, ds)
        }
    }

    func open(_ url: URL?) { presentedPage = url.map(PresentedPage.init(url:)) }
}
