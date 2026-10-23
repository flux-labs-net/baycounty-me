import XCTest
@testable import BayCountyKit

final class BrowseTests: XCTestCase {
    private var dir: URL {
        URL(fileURLWithPath: #filePath).deletingLastPathComponent().appendingPathComponent("../../../../site/public/downloads").standardized
    }
    private func rows(_ id: String) throws -> [Row] {
        guard FileManager.default.fileExists(atPath: dir.path) else { throw XCTSkip("site build not present") }
        return try Row.decodeList(Data(contentsOf: dir.appendingPathComponent("\(id).json")))
    }

    func testContractsSummary() throws {
        let all = try rows("contracts")
        let spec = DatasetSpec.for("contracts")
        let y2026 = all.filter { ($0.string("date") ?? "").hasPrefix("2026") }
        let months = Browse.months(y2026, spec: spec, year: 2026)
        XCTAssertEqual(months.first?.label, "Jan")
        XCTAssertEqual(months.map(\.count).reduce(0, +), y2026.count)
        let top = Browse.top(y2026, key: "vendor", spec: spec, byAmount: true)
        XCTAssertEqual(top.count, 5)
        XCTAssertFalse(top.contains { $0.label.lowercased().hasPrefix("not named") })
        XCTAssertGreaterThanOrEqual(top[0].amount, top[1].amount)
    }

    func testGroups() throws {
        let all = try rows("contracts")
        let spec = DatasetSpec.for("contracts")
        let sorted = all.sorted { spec.newestKey($0) > spec.newestKey($1) }
        let idx = Period.Index(all)
        var periods = [Int: Period](); for r in all { periods[r.id] = idx.period(r) }
        let byMonth = Browse.groups(sorted, by: .month, spec: spec, periods: periods)
        XCTAssertEqual(byMonth.map(\.rows.count).reduce(0, +), all.count)
        XCTAssertGreaterThan(byMonth[0].key, byMonth[1].key)
        XCTAssertTrue(byMonth[0].title.hasSuffix(String(byMonth[0].key.prefix(4))))
        let opts = Browse.groupOptions(sorted, spec: spec, periods: periods, period: Period(year: 2026, fiscal: false))
        XCTAssertEqual(opts.first, .month)
        XCTAssertTrue(opts.contains(.column("government")))
        XCTAssertEqual(Browse.GroupKey.column("government").label, "Government")
        XCTAssertEqual(Browse.shortGovernment("City of Panama City Beach"), "PCB")
        XCTAssertFalse(Browse.groupOptions(sorted, spec: spec, periods: periods, period: nil).contains(.month))
        XCTAssertEqual(Browse.displayName("pc", column: "government"), "Panama City")
        XCTAssertEqual(Browse.displayName("special_district", column: "employer"), "Special districts")
        let votes = try rows("votes")
        let top = Browse.top(votes, key: "government", spec: DatasetSpec.for("votes"), byAmount: false)
        XCTAssertTrue(top.allSatisfy { Governments.names[$0.label] == nil }, "labels are names, not ids")
    }

    func testVotes() throws {
        let votes = try rows("votes")
        let budget = try XCTUnwrap(votes.first { $0.string("headline") == "Approved $62.45 million FY2027 general fund budget" })
        let s = VoteSummary(budget)
        XCTAssertEqual(s.yes, 4); XCTAssertEqual(s.no, 1)
        XCTAssertEqual(s.passed, true); XCTAssertTrue(s.split)
        XCTAssertEqual(s.members.count, 5)
        let meetings = Browse.meetings(votes)
        XCTAssertGreaterThanOrEqual(meetings[0].date, meetings[1].date)
        XCTAssertEqual(meetings.map(\.votes.count).reduce(0, +), votes.count)
        let failed = votes.filter { VoteSummary($0).passed == false }
        XCTAssertGreaterThan(failed.count, 0)
        let noRollCall = Row(id: 0, values: ["tally": .string("5-0 (minutes: 'carried unanimously')"), "outcome": .string("passed")])
        XCTAssertEqual(VoteSummary(noRollCall).yes, 5)
        XCTAssertEqual(VoteSummary(noRollCall).tallyText, "5–0")
    }
}
