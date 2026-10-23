import XCTest
@testable import BayCountyKit

/// Keeps the app in step with the website. When the site adds a page or a dataset, these fail until the app
/// decides how to show it: add the page to SitePages.pages (native screen, dataset list, or web view) and
/// give the dataset a DatasetSpec entry.
final class SitePagesTests: XCTestCase {
    private var site: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../../../site/public").standardized
    }

    func testEverySitePageHasAnAppDecision() throws {
        let url = site.appendingPathComponent("data/app/pages.json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        let pages = try JSONDecoder().decode([PageInfo].self, from: Data(contentsOf: url))
        let missing = pages.map(\.path).filter { SitePages.coverage($0) == nil }
        XCTAssertEqual(missing, [], "Site pages with no app decision. Add each to SitePages.pages: \(missing)")
    }

    func testEveryDatasetPageListIsReal() throws {
        let url = site.appendingPathComponent("downloads/index.json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        let ids = Set(try JSONDecoder().decode(Catalog.self, from: Data(contentsOf: url)).datasets.map(\.id))
        for (path, c) in SitePages.pages {
            if case .dataset(let id) = c { XCTAssertTrue(ids.contains(id), "\(path) points at dataset \(id), which the site no longer publishes") }
        }
    }

    func testEveryDatasetHasASpec() throws {
        let url = site.appendingPathComponent("downloads/index.json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        let ids = try JSONDecoder().decode(Catalog.self, from: Data(contentsOf: url)).datasets.map(\.id)
        let missing = ids.filter { DatasetSpec.known[$0] == nil && !DatasetSpec.ownScreens.contains($0) }
        XCTAssertEqual(missing, [], "Datasets the app only shows with the generic fallback. Add a DatasetSpec for each: \(missing)")
    }

    func testAccountabilityFileDecodes() throws {
        let url = site.appendingPathComponent("data/accountability.json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        let c = try JSONDecoder().decode(AccountabilityConsole.self, from: Data(contentsOf: url))
        XCTAssertGreaterThan(c.projects.count, 50)
        XCTAssertGreaterThan(c.rules.count, 3)
        // Every flag names a published rule.
        for p in c.projects { for f in p.flags { XCTAssertNotNil(c.rule(f.r), "\(p.id) flag \(f.r) has no rule") } }
        // Every stage and event kind the site uses has a label in the app.
        let stages = Set(c.projects.compactMap(\.status)).subtracting(AccountabilityConsole.stages.keys)
        XCTAssertEqual(stages, [], "Stages with no app label")
        let kinds = Set(c.projects.flatMap { $0.ev.map(\.k) }).subtracting(AccountabilityConsole.kinds.keys)
        XCTAssertEqual(kinds, [], "Timeline event kinds with no app label")
        XCTAssertEqual(c.stats?.projects, c.projects.count)
    }
}
