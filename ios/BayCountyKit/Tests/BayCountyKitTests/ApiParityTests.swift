import XCTest
@testable import BayCountyKit

/// The app's "Who's in charge" and budget comparison must give the same answers as the site's API
/// (api/_officials.js, api/_budget.js). Fixtures come from ios/scripts/make_fixtures.js.
final class ApiParityTests: XCTestCase {
    struct Fixture: Decodable {
        struct Officials: Decodable {
            struct Seat: Decodable { let seat: String; let holders: [String] }
            let gov: String; let year: Int; let seats: [Seat]
        }
        struct Budget: Decodable {
            struct L: Decodable { let key: String; let from: Double?; let to: Double? }
            let gov: String; let basis: String; let from: Int; let to: Int
            let totals: [L]; let sections: [String: [L]]; let notes: [String]; let up: String?; let down: String?
        }
        let officials: [Officials]; let budget: [Budget]
    }

    var fixture: Fixture!

    override func setUpWithError() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "api-parity", withExtension: "json", subdirectory: "Fixtures"))
        fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))
    }

    func rows(_ id: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json")))
    }

    func testWhoHeldEachSeatMatchesTheAPI() throws {
        let terms = try rows("officeholder-terms")
        for c in fixture.officials {
            let seats = Officeholders.inOffice(terms, gov: c.gov, year: c.year)
            XCTAssertEqual(seats.map(\.seat), c.seats.map(\.seat), "\(c.gov) FY\(c.year)")
            for (s, e) in zip(seats, c.seats) {
                let got = s.holders.map { ($0.personName.isEmpty ? "null" : $0.personName) + ($0.partOfPeriod ? "*" : "") }
                XCTAssertEqual(got, e.holders, "\(c.gov) FY\(c.year) \(s.seat)")
            }
        }
    }

    func testBudgetComparisonMatchesTheAPI() throws {
        let budgets = try rows("budget-years")
        for c in fixture.budget {
            let r = try XCTUnwrap(BudgetCompare.compare(budgets, gov: c.gov, basis: BudgetCompare.Basis(rawValue: c.basis)!), "\(c.gov) \(c.basis)")
            let label = "\(c.gov) \(c.basis)"
            XCTAssertEqual(r.from, c.from, label)
            XCTAssertEqual(r.to, c.to, label)
            func same(_ got: [BudgetCompare.Line], _ want: [Fixture.Budget.L], _ what: String) {
                XCTAssertEqual(Array(got.prefix(5)).map(\.key), want.map(\.key), "\(label) \(what)")
                for (g, w) in zip(got, want) {
                    XCTAssertEqual(g.from ?? -1, w.from ?? -1, accuracy: 0.5, "\(label) \(what) \(g.key)")
                    XCTAssertEqual(g.to ?? -1, w.to ?? -1, accuracy: 0.5, "\(label) \(what) \(g.key)")
                }
            }
            same(r.totals, c.totals, "totals")
            for (k, want) in c.sections {
                same(try XCTUnwrap(r.sections.first { $0.key == k }, "\(label) \(k)").lines, want, k)
            }
            XCTAssertEqual(r.notes, c.notes, label)
            XCTAssertEqual(r.biggestIncrease?.key, c.up, label)
            XCTAssertEqual(r.biggestDecrease?.key, c.down, label)
        }
    }

    func testFiscalYearWindows() {
        XCTAssertEqual(Officeholders.fyWindow(gov: "lh", year: 2026).from, "2025-10-01")
        XCTAssertEqual(Officeholders.fyWindow(gov: "lh", year: 2026).to, "2026-09-30")
        XCTAssertEqual(Officeholders.fyWindow(gov: "schools", year: 2024).from, "2023-07-01")
        XCTAssertEqual(Officeholders.fyWindow(gov: "schools", year: 2024).to, "2024-06-30")
    }

    func testCRAIncrementHeadlineMatchesThePage() throws {
        let agencies = try rows("cra-agencies"), years = try rows("cra-tax-increment")
        let h = try XCTUnwrap(CRAIncrement.headline(agencies: agencies, years: years))
        XCTAssertEqual(h.agencies, 7)
        XCTAssertGreaterThanOrEqual(h.firstYear, Cutoff.firstYear)
        XCTAssertGreaterThan(h.total, h.county)
        XCTAssertGreaterThan(h.toComeHigh, h.toComeLow)
        let series = CRAIncrement.byYear(years)
        XCTAssertEqual(series.first?.fiscalYear, h.firstYear)
        XCTAssertEqual(series.first { $0.fiscalYear == h.lastYear }?.amount ?? 0, h.total, accuracy: 1)
        XCTAssertTrue(series.contains { $0.projected })
    }

    func testPersonLinksIncludeTermsAndPastRaces() throws {
        var all: [String: [Row]] = [:]
        for id in RecordLinks.personDatasets { all[id] = try rows(id) }
        let recs = Dictionary(uniqueKeysWithValues: RecordLinks.records(forPerson: "robert-carroll", in: all).map { ($0.dataset, $0.rows) })
        XCTAssertFalse(recs["officeholder-terms"]?.isEmpty ?? true)
        XCTAssertFalse(recs["campaign-history"]?.isEmpty ?? true)
        XCTAssertFalse(Officeholders.terms(all["officeholder-terms"]!, personID: "robert-carroll").isEmpty)
        // Year pickers stop at the site's first year.
        XCTAssertEqual(Officeholders.years(all["officeholder-terms"]!, gov: "lh").last, Cutoff.firstYear)
    }
}
