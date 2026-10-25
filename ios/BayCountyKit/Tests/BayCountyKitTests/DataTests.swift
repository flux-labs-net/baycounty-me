import XCTest
@testable import BayCountyKit

/// Runs against the files the site publishes (site/public/downloads in this repo), so the app is
/// checked against exactly what baycounty.me serves.
final class DataTests: XCTestCase {
    static let downloads: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()          // BayCountyKitTests
        .deletingLastPathComponent()          // Tests
        .deletingLastPathComponent()          // BayCountyKit
        .deletingLastPathComponent()          // ios
        .deletingLastPathComponent()          // repo root
        .appendingPathComponent("site/public/downloads")

    func load(_ name: String) throws -> Data {
        try Data(contentsOf: Self.downloads.appendingPathComponent(name))
    }

    func catalog() throws -> Catalog {
        try JSONDecoder().decode(Catalog.self, from: load("index.json"))
    }

    func testJSONValueKeepsTypes() throws {
        let rows = try Row.decodeList(Data(#"[{"a":true,"b":1.5,"c":null,"d":"x","e":[1,"y"],"f":{"g":2}}]"#.utf8))
        let r = rows[0]
        XCTAssertEqual(r["a"], .bool(true))
        XCTAssertEqual(r.number("b"), 1.5)
        XCTAssertNil(r.string("c"))
        XCTAssertEqual(r.string("d"), "x")
        XCTAssertEqual(r.strings("e"), ["1", "y"])
        XCTAssertNotNil(r["f"])
    }

    func testEveryPublishedDatasetDecodesAndReads() throws {
        let cat = try catalog()
        XCTAssertGreaterThan(cat.datasets.count, 20)
        for d in cat.datasets {
            let rows = try Row.decodeList(load("\(d.id).json"))
            XCTAssertEqual(rows.count, d.rows ?? rows.count, "\(d.id) row count")
            let spec = DatasetSpec.for(d.id)
            let titled = rows.filter { spec.title($0) != "Record" }.count
            XCTAssertGreaterThanOrEqual(Double(titled), Double(rows.count) * 0.95, "\(d.id): most rows need a title")
            // A database-only dataset (filled after deploy, e.g. checkbook-payments) publishes no rows in the build.
            if !rows.isEmpty, !spec.amountKeys.isEmpty, !DatasetSpec.ownScreens.contains(d.id) {
                let withAmount = rows.filter { spec.amount($0) != nil }.count
                XCTAssertGreaterThan(withAmount, 0, "\(d.id): amount column never filled")
            }
            if DatasetSpec.known[d.id] != nil {
                for key in spec.titleKeys + spec.subtitleKeys + spec.amountKeys + spec.filterKeys + spec.dateKeys {
                    XCTAssertNotNil(d.column(key), "\(d.id): spec names unknown column \(key)")
                }
            }
            if let r = rows.first { XCTAssertFalse(DatasetSpec.fields(r, columns: d.columns).isEmpty) }
        }
    }

    func testCRATotalsFollowCountingRules() throws {
        let rows = try Row.decodeList(load("cra-payments.json"))
        // Independent recomputation of the rule the site uses.
        var paid = 0.0, pending = 0.0
        for r in rows where r.bool("count") == true {
            let a = r.number("amount") ?? 0
            if r.string("status") == "Spent" { paid += a }
            if ["Committed", "Budgeted"].contains(r.string("status") ?? "") { pending += a }
        }
        XCTAssertEqual(CRALedger.paidOut(rows), paid, accuracy: 0.01)
        XCTAssertEqual(CRALedger.pending(rows), pending, accuracy: 0.01)
        let summaries = CRALedger.summaries(rows)
        XCTAssertGreaterThanOrEqual(summaries.count, 6)
        XCTAssertEqual(summaries.map(\.paidOut).reduce(0, +), paid, accuracy: 0.01)
        XCTAssertEqual(summaries.map(\.records).reduce(0, +), rows.count)
        XCTAssertGreaterThan(paid, 0)
        // A row that is a total of other rows must not count.
        XCTAssertTrue(rows.contains { $0.bool("count") == false && ($0.number("amount") ?? 0) > 0 })
        print("CRA paid out \(Format.money(paid)), committed/budgeted \(Format.money(pending))")
    }

    func testGovernmentsAndMeetings() throws {
        let govs = try Row.decodeList(load("government-profiles.json")).map(Government.init(row:))
        XCTAssertEqual(govs.count, 9)
        XCTAssertTrue(govs.allSatisfy { $0.population != nil && $0.pageURL != nil })
        XCTAssertEqual(Set(govs.map(\.govID)), Set(Governments.names.keys))

        let meetings = try Row.decodeList(load("meetings.json")).map(Meeting.init(row:))
        let dated = meetings.filter { $0.row.string("start") != nil }
        XCTAssertEqual(dated.filter { $0.start != nil }.count, dated.count, "every start date parses")
        XCTAssertTrue(meetings.allSatisfy { !$0.boardName.contains("-") }, "every board has a name")
        let early = Dates.parse("2026-01-01")!
        let upcoming = Meeting.upcoming(meetings, now: early)
        XCTAssertFalse(upcoming.contains { $0.isPast || $0.isCancelled })
        XCTAssertEqual(upcoming, upcoming.sorted { $0.start! < $1.start! })
    }

    func testFormatting() {
        XCTAssertEqual(Format.money(1779883.75), "$1,779,884")
        XCTAssertEqual(Format.money(218.03), "$218.03")
        XCTAssertEqual(Format.compactMoney(90_808_899), "$90.8M")
        XCTAssertEqual(Format.compactMoney(148_377), "$148K")
        XCTAssertEqual(Format.compactMoney(1_200_000_000), "$1.2B")
        XCTAssertEqual(Format.label("date_or_fy"), "When")
        XCTAssertEqual(Format.label("total_raised"), "Total raised")
        XCTAssertEqual(Format.value(.number(4.05), column: "millage"), "4.05")
        XCTAssertEqual(Format.value(.number(7674166), column: "property_tax_levy"), "$7,674,166")
        XCTAssertEqual(Format.value(.number(46089), column: "parcels"), "46,089")
        XCTAssertEqual(Format.value(.bool(false), column: "count"), "No")
        XCTAssertEqual(Format.value(.string("in_progress"), column: "status"), "In progress")
        XCTAssertEqual(Format.value(.string("2026-10-27"), column: "date"), "Oct 27, 2026")
        XCTAssertEqual(Format.value(.string("2026-10-27T18:00:00-05:00"), column: "start"), "Oct 27, 2026 at 6:00 PM")
        XCTAssertEqual(Governments.boardName("lh-cra"), "Lynn Haven CRA Board")
    }

    /// Opt-in: BCM_LIVE=1 swift test. Hits baycounty.me.
    func testLiveSite() async throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["BCM_LIVE"] == "1", "set BCM_LIVE=1 to test against baycounty.me")
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("bcm-test-\(UUID().uuidString)")
        let client = BayCountyClient(cacheDirectory: dir)
        let (cat, f1) = try await client.catalog()
        XCTAssertEqual(f1, .live)
        XCTAssertGreaterThan(cat.datasets.count, 20)
        let (_, f2) = try await client.catalog()   // revalidates with If-None-Match
        XCTAssertEqual(f2, .live)
        let (govs, _) = try await client.governments()
        XCTAssertEqual(govs.count, 9)
        let (cra, _) = try await client.rows(datasetID: "cra-payments")
        XCTAssertGreaterThan(cra.count, 100)
        let hits = try await client.search("millville")
        XCTAssertFalse(hits.isEmpty)
        XCTAssertNotNil(hits.first?.link)

        // Offline: an unreachable host falls back to the saved copy.
        let offline = BayCountyClient(baseURL: URL(string: "https://offline.invalid")!, cacheDirectory: dir)
        let (_, f3) = try await offline.catalog()
        XCTAssertEqual(f3, .cached)
    }
}

final class LinkTests: XCTestCase {
    func rows(_ ids: [String]) throws -> [String: [Row]] {
        var out = [String: [Row]]()
        for id in ids { out[id] = try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json"))) }
        return out
    }

    func testVendorLinksFindContractsAndVotes() throws {
        let all = try rows(RecordLinks.vendorDatasets + ["votes"])
        let recs = RecordLinks.records(forVendor: "roberts-and-roberts", in: all)
        XCTAssertTrue(recs.contains { $0.dataset == "contracts" }, "\(recs.map(\.dataset))")
        let votes = RecordLinks.votes(forVendor: "roberts-and-roberts", in: all)
        XCTAssertFalse(votes.isEmpty)
        XCTAssertTrue(votes.allSatisfy { $0.string("vote_id") != nil })
    }

    func testPersonLinksFindVotesAndPay() throws {
        let all = try rows(RecordLinks.personDatasets)
        let recs = RecordLinks.records(forPerson: "clair-pease", in: all)
        let ds = Set(recs.map(\.dataset))
        XCTAssertTrue(ds.contains("member-votes"), "\(ds)")
        XCTAssertTrue(ds.contains("votes"), "\(ds)")
        let mv = try XCTUnwrap(recs.first { $0.dataset == "member-votes" }?.rows)
        let t = RecordLinks.tally(mv)
        XCTAssertEqual(t.total, mv.count)
        XCTAssertGreaterThan(t.yes, 0)
        let v = try XCTUnwrap(recs.first { $0.dataset == "votes" }?.rows.first)
        XCTAssertNotNil(RecordLinks.vote(of: "clair-pease", in: v))
    }
}
