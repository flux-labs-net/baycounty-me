import XCTest
@testable import BayCountyKit

/// The school, public safety and overlap screens against the site's published datasets: the same numbers
/// site/schools_page.py, site/safety_page.py and site/overlaps_page.py print (Android: SitePagesAddedTest).
final class SitePagesAddedTests: XCTestCase {
    private func rows(_ id: String) throws -> [Row] {
        let url = DataTests.downloads.appendingPathComponent("\(id).json")
        guard FileManager.default.fileExists(atPath: url.path) else { throw XCTSkip("site build not present") }
        return try Row.decodeList(Data(contentsOf: url))
    }

    func testSchoolGradesScoresSpendingAndHours() throws {
        let schools = try rows("schools"), grades = try rows("school-grades"), state = try rows("school-grade-state")
        let spend = try rows("school-spending"), bell = try rows("school-bell-times"), zones = try rows("school-zones")
        let c = try XCTUnwrap(Schools.gradeCounts(schools, grades: grades))
        XCTAssertEqual(c.year, 2026)
        XCTAssertGreaterThan(c.a, 10)
        let mosley = "03-0491"
        let s = try XCTUnwrap(Schools.scores(grades: grades, state: state, school: mosley))
        XCTAssertTrue(s.title.hasPrefix("Scores behind the 2025-26 grade"))
        XCTAssertTrue(s.items.contains { $0.label == "Graduation rate" })
        XCTAssertTrue(s.items.allSatisfy { $0.state != nil })
        XCTAssertEqual(Schools.hours(bell, school: mosley), "8:15 a.m. to 3:00 p.m.")
        XCTAssertEqual(Schools.hours(bell, school: "03-0571"), "Elementary (K-5): 7:30 a.m. to 2:00 p.m.; Middle (6-8): 7:30 a.m. to 2:05 p.m.")
        XCTAssertEqual(Schools.time("13:50"), "1:50 p.m.")
        XCTAssertEqual(Schools.time("00:05"), "12:05 a.m.")
        let r = try XCTUnwrap(Schools.spendingRanking(spend, schools: schools))
        XCTAssertEqual(r.year, 2025)
        XCTAssertEqual(r.rows.first?.name, "St. Andrew School at Oakland Terrace")
        XCTAssertEqual(r.average, 10764, accuracy: 1)
        let mix = Schools.gradeMix(grades: grades, state: state, year: 2026)
        XCTAssertNotNil(mix.florida)
        XCTAssertGreaterThan(Schools.aShare(mix.local), 0)
        let row = try XCTUnwrap(schools.first { $0.string("school_id") == mosley })
        XCTAssertEqual(Schools.phone(row)?.label, "(850) 767-4400")
        XCTAssertEqual(Schools.phone(row)?.url.absoluteString, "tel:+18507674400")
        XCTAssertTrue(Schools.mapsURL(row)?.absoluteString.contains("501%20Mosley%20Dr") == true)
        XCTAssertFalse(Schools.zones(zones, level: "High").isEmpty)
        XCTAssertTrue(Schools.zones(zones, level: "Elementary").allSatisfy { !$0.rings.isEmpty && $0.rings[0].count > 3 })
    }

    func testPublicSafety() throws {
        let a = try rows("safety-agencies"), c = try rows("crime-counts"), s = try rows("police-staffing")
        let t = PublicSafety.totals(a)
        XCTAssertEqual(t.police, 130_393_108, accuracy: 1)
        XCTAssertEqual(t.officers, 492)
        let h = try XCTUnwrap(PublicSafety.headline(c))
        XCTAssertEqual(h.year, 2024); XCTAssertEqual(h.firstYear, 2016)
        XCTAssertEqual(h.violent, 598); XCTAssertEqual(h.violentChange, -23)
        let solved = PublicSafety.solved(c, offense: .violent)
        XCTAssertEqual(solved.first?.name, "Panama City Beach police")
        XCTAssertEqual(Int((solved.first!.share * 100).rounded()), 75)
        let towns = PublicSafety.towns(a)
        XCTAssertEqual(towns.first?.id, "county")
        let callaway = try XCTUnwrap(towns.first { $0.id == "cw" })
        XCTAssertTrue(PublicSafety.townCrime(callaway, crimes: c).sheriffCovers)
        XCTAssertFalse(PublicSafety.trends(c, offense: .property).isEmpty)
        XCTAssertTrue(PublicSafety.trends(c, offense: .violent).allSatisfy { $0.points.allSatisfy { $0.year != 2021 } })
        XCTAssertFalse(PublicSafety.staffingSummary(s).isEmpty)
        XCTAssertEqual(PublicSafety.shortName("Panama City Police Department"), "Panama City police")
        XCTAssertEqual(PublicSafety.money(74_437_440), "$74.4M")
    }

    func testOverlaps() throws {
        var all: [String: [Row]] = [:]
        for d in Overlaps.datasets { all[d] = try rows(d) }
        let h = Overlaps.headline(all)
        XCTAssertEqual(h.donorVotes, 318); XCTAssertEqual(h.pairs, 116)
        XCTAssertEqual(h.contested, 68); XCTAssertEqual(h.topWon, 51)
        let cards = Overlaps.cards(all)
        XCTAssertEqual(cards.count, 8)
        XCTAssertTrue(cards.allSatisfy { Overlaps.datasets.contains($0.dataset) })
        let live = try Overlaps.decodeLive(Data(#"{"data":{"split_purchases":{"rows":[{"payee":"Acme","payments":2,"threshold":5000,"total":9800,"government":"Lynn Haven"}],"error":null}}}"#.utf8))
        let line = Overlaps.liveLine("split_purchases", try XCTUnwrap(live["split_purchases"]?.first))
        XCTAssertEqual(line.title, "Acme")
        XCTAssertTrue(line.detail.hasPrefix("2 payments just under $5,000"))
    }
}
