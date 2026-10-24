import XCTest
@testable import BayCountyKit

/// The record screen's names, links, tags and related rows, checked against the published nonprofit lists.
final class RecordProfileTests: XCTestCase {
    func rows(_ id: String) throws -> [Row] {
        try Row.decodeList(Data(contentsOf: DataTests.downloads.appendingPathComponent("\(id).json")))
    }

    func testOrgNameCasing() {
        XCTAssertEqual(Format.orgName("455 HARRISON AVENUE GROUP, INC."), "455 Harrison Avenue Group, Inc.")
        XCTAssertEqual(Format.orgName("VFW POST 10085 OF PANAMA CITY"), "VFW Post 10085 of Panama City")
        XCTAssertEqual(Format.orgName("THE ARC OF BAY COUNTY, INC."), "The ARC of Bay County, Inc.")
        XCTAssertEqual(Format.orgName("PCB SENIOR CENTER"), "PCB Senior Center")
        XCTAssertEqual(Format.orgName("KREWE OF ST. ANDREWS INC"), "Krewe of St. Andrews Inc")
        XCTAssertEqual(Format.orgName("FIRST BAPTIST CHURCH OF LYNN HAVEN"), "First Baptist Church of Lynn Haven")
        XCTAssertEqual(Format.orgName("21ST CENTURY KIDS-PANAMA CITY"), "21st Century Kids-Panama City")
        XCTAssertEqual(Format.orgName("Bay County Chamber of Commerce, Inc."), "Bay County Chamber of Commerce, Inc.", "mixed case is kept")
    }

    func testSentenceList() {
        XCTAssertEqual(RecordProfile.sentenceList(["Treasurer", "Director"]), "Treasurer and Director")
        XCTAssertEqual(RecordProfile.sentenceList(["COO", "Vice President", "Trustee"]), "COO, Vice President and Trustee")
        XCTAssertEqual(RecordProfile.sentenceList(["Chair"]), "Chair")
    }

    func testBoardMemberRecordReadsLikeAProfile() throws {
        let all = try rows("nonprofit-board-members")
        let ds = "nonprofit-board-members"
        guard let row = all.first(where: { $0.string("person_id") == "b_353fe5f7887b" && $0.string("nonprofit_id") == "np-sb-n01000008288" }) else {
            throw XCTSkip("example board seat is no longer published")
        }
        XCTAssertEqual(RecordProfile.title(ds, row), "Kathy Bass")
        XCTAssertEqual(RecordProfile.roleLine(ds, row), "Treasurer and Director")
        XCTAssertEqual(RecordProfile.initials(ds, row), "KB")

        let refs = RecordProfile.refs(ds, row)
        XCTAssertEqual(refs.map(\.id), ["member:b_353fe5f7887b", "nonprofit:np-sb-n01000008288"])
        XCTAssertEqual(refs[1].name, "455 Harrison Avenue Group, Inc.")
        XCTAssertEqual(refs[0].profileURL?.absoluteString, "https://baycounty.me/profile/member/b_353fe5f7887b")
        XCTAssertEqual(RecordProfile.subject(ds, row)?.kind, "member")

        let chips = RecordProfile.chips(ds, row).map(\.text)
        XCTAssertEqual(Array(chips.prefix(3)), ["Current", "Board", "State filing"])
        XCTAssertEqual(RecordProfile.years(row), 2026...2026)

        let board = try XCTUnwrap(RecordProfile.groups(ds, row).first { $0.column == "nonprofit_id" })
        let peers = RecordProfile.members(of: board, in: all, excluding: row.id, sameDataset: true)
        XCTAssertFalse(peers.contains { $0.id == row.id })
        XCTAssertTrue(peers.allSatisfy { $0.string("nonprofit_id") == "np-sb-n01000008288" })
        XCTAssertFalse(peers.isEmpty)

        let shown = RecordProfile.otherFields(ds, row, columns: []).map(\.label)
        XCTAssertFalse(shown.contains("Nonprofit ID"))
        XCTAssertFalse(shown.contains("County"))
        XCTAssertFalse(shown.contains("Person"))
    }

    func testNoRawSunbizCodesInPublishedTitles() throws {
        let codes: Set<String> = ["Td", "Pd", "Sd", "Vd", "Dire", "Secr", "Mgrm", "Boar"]
        for r in try rows("nonprofit-board-members") {
            for t in (r.string("titles") ?? "").components(separatedBy: ", ") {
                XCTAssertFalse(codes.contains(t), "\(t) in \(r.string("person") ?? "")")
            }
        }
    }

    func testEveryDatasetBuildsAProfile() throws {
        let cat = try JSONDecoder().decode(Catalog.self, from: Data(contentsOf: DataTests.downloads.appendingPathComponent("index.json")))
        for d in cat.datasets {
            for row in try rows(d.id).prefix(20) {
                XCTAssertFalse(RecordProfile.title(d.id, row).isEmpty, d.id)
                _ = RecordProfile.chips(d.id, row)
                XCTAssertLessThanOrEqual(RecordProfile.facts(d.id, row).count, 4, d.id)
                for r in RecordProfile.refs(d.id, row) { XCTAssertNotNil(r.profileURL, "\(d.id) \(r.id)") }
            }
        }
    }
}
