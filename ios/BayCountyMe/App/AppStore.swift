import Foundation
import Observation
import UIKit
import BayCountyKit

/// App-wide state: the catalog, governments, meetings, any dataset rows loaded so far, and the site's /data/app files.
@MainActor
@Observable
final class AppStore {
    /// Home, Around me (the site's Living here), Money, Government and Ask (search and the question box).
    enum Tab: Hashable { case home, living, money, decides, search }

    let client = BayCountyClient(baseURL: AppStore.apiBase, seedBundle: .main)

    /// Debug builds only: `-apiBase <url>` points the app at the store screenshot server (store/demo_server.py),
    /// which swaps in made-up restaurants and a sample beach day. Release builds always read baycounty.me.
    nonisolated static var apiBase: URL {
        #if DEBUG
        if let s = UserDefaults.standard.string(forKey: "apiBase"), let url = URL(string: s) { return url }
        #endif
        return BayCountyClient.site
    }
    let gis = GISClient()
    /// Anonymous usage counts: one check-in a day, which the resident can turn off in About.
    let usage = AppUsage(version: AppStore.appVersion)

    /// "1.0 (7)": marketing version and build number.
    nonisolated static var appVersion: String {
        let info = Bundle.main.infoDictionary
        return "\(info?["CFBundleShortVersionString"] as? String ?? "?") (\(info?["CFBundleVersion"] as? String ?? "?"))"
    }

    /// The app came to the front: count it and send today's check-in if one is due. Debug builds (Xcode runs and the
    /// screenshot workflows) don't send, so they never show up in the counts.
    func becameActive() {
        usage.opened()
        #if !DEBUG
        let usage = usage
        Task.detached { await usage.send() }
        #endif
    }

    var tab: Tab = .home
    /// A page the app is showing in the in-app browser.
    var presentedPage: PresentedPage?
    /// A glossary term shown in a sheet.
    var presentedTerm: Glossary.Term?

    private(set) var catalog: Catalog?
    private(set) var governments: [Government] = []
    private(set) var meetings: [Meeting] = []
    private(set) var rows: [String: [Row]] = [:]
    private(set) var searchIndex: [String: [Int: String]] = [:]
    private(set) var freshness: [String: BayCountyClient.Freshness] = [:]
    private(set) var errors: [String: String] = [:]
    private(set) var loading: Set<String> = []
    private(set) var lastRefresh: Date?

    // /data/app files
    private(set) var taxModel: TaxModel?
    private(set) var addressModel: AddressModel?
    private(set) var amendment3: Amendment3Model?
    private(set) var glossary: Glossary?
    private(set) var pages: [PageInfo] = []
    private(set) var updates: [SiteUpdate] = []
    private(set) var vendors: VendorDirectory?
    private(set) var people: PeopleDirectory?
    private(set) var donorContracts: DonorContracts?
    private(set) var moneyMap: MoneyMap?
    private(set) var accountability: AccountabilityConsole?

    /// The saved home address, kept only on this phone.
    var home: AddressMatch? {
        didSet {
            do {
                if let home { UserDefaults.standard.set(try JSONEncoder().encode(home), forKey: "home") }
                else { UserDefaults.standard.removeObject(forKey: "home") }
            } catch {}
        }
    }

    /// Own or rent, from the setup screen or My home; nil until the resident answers. Kept only on this phone.
    var tenure: HomeTiles.Tenure? {
        didSet { UserDefaults.standard.set(tenure?.rawValue, forKey: "tenure") }
    }
    /// The setup screen (address, own or rent) shows once, on first launch.
    var setupSeen: Bool {
        didSet { UserDefaults.standard.set(setupSeen, forKey: "setupSeen") }
    }

    init() {
        if let d = UserDefaults.standard.data(forKey: "home") { home = try? JSONDecoder().decode(AddressMatch.self, from: d) }
        tenure = UserDefaults.standard.string(forKey: "tenure").flatMap(HomeTiles.Tenure.init(rawValue:))
        // Screenshot runs (-screen) and residents who already saved a home before this screen existed skip it.
        setupSeen = UserDefaults.standard.bool(forKey: "setupSeen") || ProcessInfo.processInfo.arguments.contains("-screen") || home != nil
        // Screenshots: `-tenure own|rent|unset` draws the Home tab for that answer without saving it.
        let a = ProcessInfo.processInfo.arguments
        if let i = a.firstIndex(of: "-tenure"), i + 1 < a.count { tenure = HomeTiles.Tenure(rawValue: a[i + 1]) }
    }

    /// True when anything on screen came from a saved or bundled copy rather than the live site.
    var isShowingSavedData: Bool { freshness.values.contains { $0 != .live } }

    func loadEssentials() async {
        await loadCatalog()
        await loadGovernments()
        await loadMeetings()
        await loadGlossary()
        await loadApp("pages.json") { (p: [PageInfo]) in self.pages = p }
        await loadUpdates()
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
            let (all, f) = try await client.rows(datasetID: id)
            // A row with same_as is a post listed twice (a re-posted alert, one event on two calendars); its kept row stands for it.
            let r = all.filter { ($0.string("same_as") ?? "").isEmpty }
            rows[id] = r
            searchIndex[id] = Dictionary(uniqueKeysWithValues: r.map { ($0.id, $0.searchText) })
            freshness[id] = f; errors[id] = nil
        } catch { errors[id] = error.localizedDescription }
    }

    func load(_ ids: [String]) async {
        await withTaskGroup(of: Void.self) { g in
            for id in ids { g.addTask { await self.load(id) } }
        }
    }

    /// T is Sendable so its Decodable conformance can be used off the main actor (Xcode 26 warns otherwise).
    private func loadApp<T: Decodable & Sendable>(_ name: String, force: Bool = false, _ assign: (T) -> Void) async {
        guard force || errors["app:" + name] != nil || !loaded.contains(name) else { return }
        do {
            let (v, f): (T, BayCountyClient.Freshness) = try await client.appData(name)
            assign(v); freshness["app:" + name] = f; errors["app:" + name] = nil; loaded.insert(name)
        } catch { errors["app:" + name] = error.localizedDescription }
    }
    private var loaded: Set<String> = []

    func loadGlossary() async { await loadApp("glossary.json") { (g: Glossary) in self.glossary = g } }
    func loadUpdates() async { await loadApp("updates.json") { (u: [SiteUpdate]) in self.updates = u } }
    func loadTax() async { await loadApp("tax.json") { (m: TaxModel) in self.taxModel = m } }
    func loadAddressModel() async { await loadApp("address.json") { (m: AddressModel) in self.addressModel = m } }
    func loadAmendment3() async { await loadApp("amendment3.json") { (m: Amendment3Model) in self.amendment3 = m } }
    func loadVendors() async { await loadApp("vendors.json") { (m: VendorDirectory) in self.vendors = m } }
    func loadPeople() async { await loadApp("people.json") { (m: PeopleDirectory) in self.people = m } }
    func loadDonorContracts() async { await loadApp("donor-contracts.json") { (m: DonorContracts) in self.donorContracts = m } }
    func loadMoneyMap() async { await loadApp("money-map.json") { (m: MoneyMap) in self.moneyMap = m } }

    /// The Accountability console reads the site's own /data/accountability.json (errors keyed like app files).
    func loadAccountability(force: Bool = false) async {
        let key = "app:accountability.json"
        guard force || accountability == nil || errors[key] != nil else { return }
        do {
            let (c, f) = try await client.accountability()
            accountability = c; freshness[key] = f; errors[key] = nil
        } catch { errors[key] = error.localizedDescription }
    }

    func appError(_ name: String) -> String? { errors["app:" + name] }

    func info(_ id: String) -> DatasetInfo? { catalog?.dataset(id) }
    func government(_ govID: String) -> Government? { governments.first { $0.govID == govID } }
    func page(_ path: String?) -> PageInfo? { path.flatMap { p in pages.first { $0.path == "/" + p || $0.path == p } } }
    func vendor(_ id: String) -> VendorDirectory.Vendor? { vendors?.vendors.first { $0.id == id } }
    func person(_ id: String) -> PeopleDirectory.Person? { people?.people.first { $0.id == id } }
    func term(_ id: String) -> Glossary.Term? { glossary?.terms.first { $0.id == id } }

    func matches(_ id: String, row: Row, query: String) -> Bool {
        guard !query.isEmpty else { return true }
        let text = searchIndex[id]?[row.id] ?? row.searchText
        return query.lowercased().split(separator: " ").allSatisfy { text.contains($0) }
    }

    /// Datasets in Explore, grouped the way the website's menu groups them.
    var exploreSections: [(section: DatasetSpec.Section, datasets: [DatasetInfo])] {
        let shown = (catalog?.datasets ?? []).filter { !DatasetSpec.ownScreens.contains($0.id) && $0.rows != 0 }  // empty datasets wait until they have rows
        return DatasetSpec.Section.allCases.compactMap { section in
            let ds = shown.filter { DatasetSpec.for($0.id).section == section }
            return ds.isEmpty ? nil : (section, ds)
        }
    }

    /// Web pages open in the in-app browser; map/directions, phone and email links open their own app (Maps, Phone, Mail).
    func open(_ url: URL?) {
        guard let url else { return }
        if ExternalLinks.opensOutsideApp(url) { UIApplication.shared.open(url); return }
        presentedPage = PresentedPage(url: AppLinks.tagged(url))
    }
    func openSite(_ path: String) { open(URL(string: "https://baycounty.me" + (path.hasPrefix("/") ? path : "/" + path))) }
    func explain(_ termID: String) { presentedTerm = term(termID) }
}
