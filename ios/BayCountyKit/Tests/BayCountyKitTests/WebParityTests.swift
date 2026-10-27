import XCTest
@testable import BayCountyKit

/// The app's calculators and address parser must give the same answers as the website's JavaScript.
/// Fixtures come from ios/scripts/make_fixtures.js, which runs the site's own code.
final class WebParityTests: XCTestCase {
    struct Fixture: Decodable {
        struct Tax: Decodable { let d: String; let v: Double; let h: Bool; let total: Double; let trend: [Double] }
        struct A3: Decodable { let d: String; let v: Double; let k: String; let totals: [Double] }
        struct Parse: Decodable {
            struct P: Decodable {
                struct Tok: Decodable { let alts: [String]; let kind: String; let word: Bool?; let partial: Bool? }
                let house: String; let unit: String; let place: String; let toks: [Tok]
            }
            let input: String; let parsed: P?; let `where`: [String]?
        }
        struct Shard: Decodable { let p: String; let ex: String; let nav: String }
        let tax: [Tax]; let a3: [A3]; let parse: [Parse]; let shards: [Shard]
    }

    static let downloads = DataTests.downloads
    var fixture: Fixture!
    var tax: TaxModel!
    var a3: Amendment3Model!

    override func setUpWithError() throws {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "web-parity", withExtension: "json", subdirectory: "Fixtures"))
        fixture = try JSONDecoder().decode(Fixture.self, from: Data(contentsOf: url))
        let app = Self.downloads.deletingLastPathComponent().appendingPathComponent("data/app")
        tax = try JSONDecoder().decode(TaxModel.self, from: Data(contentsOf: app.appendingPathComponent("tax.json")))
        a3 = try JSONDecoder().decode(Amendment3Model.self, from: Data(contentsOf: app.appendingPathComponent("amendment3.json")))
    }

    func testTaxCalculatorMatchesWebsite() throws {
        for c in fixture.tax {
            let d = try XCTUnwrap(tax.districts.first { $0.id == c.d })
            let e = TaxCalculator.estimate(model: tax, district: d, value: c.v, homestead: c.h)
            XCTAssertEqual(e.total, c.total, accuracy: 0.005, "\(c.d) \(c.v) homestead=\(c.h)")
            XCTAssertEqual(e.trend.count, c.trend.count)
            for (a, b) in zip(e.trend.map(\.total), c.trend) { XCTAssertEqual(a, b, accuracy: 0.005, "\(c.d) trend") }
        }
    }

    func testAmendment3MatchesWebsite() throws {
        for c in fixture.a3 {
            let d = try XCTUnwrap(a3.districts.first { $0.id == c.d })
            let s = Amendment3Calculator.scenarios(model: a3, district: d, value: c.v, kind: try XCTUnwrap(.init(rawValue: c.k)))
            XCTAssertEqual(s.map(\.total).count, 3)
            for (a, b) in zip(s.map(\.total), c.totals) { XCTAssertEqual(a, b, accuracy: 0.005, "\(c.d) \(c.v) \(c.k)") }
        }
    }

    func testAddressParserMatchesWebsite() {
        for c in fixture.parse {
            let p = AddressParser.parse(c.input)
            guard let want = c.parsed else { XCTAssertNil(p, c.input); continue }
            guard let p else { XCTFail("no parse: \(c.input)"); continue }
            XCTAssertEqual(p.house, want.house, c.input)
            XCTAssertEqual(p.unit, want.unit, c.input)
            XCTAssertEqual(p.place, want.place, c.input)
            XCTAssertEqual(p.tokens.map(\.alts), want.toks.map(\.alts), c.input)
            XCTAssertEqual(p.tokens.map(\.kind.rawValue), want.toks.map(\.kind), c.input)
            XCTAssertEqual(AddressParser.whereClause(p, keep: [.name, .type, .dir]), c.where?[0], c.input)
            XCTAssertEqual(AddressParser.whereClause(p, keep: [.name]), c.where?[1], c.input)
        }
    }

    func testParcelShardsMatchWebsite() {
        for c in fixture.shards {
            XCTAssertEqual(parcelShard(c.p, count: 96), c.ex)
            XCTAssertEqual(parcelShard(c.p, count: 128), c.nav)
        }
    }

    func testGlossaryFindsTermsInText() throws {
        let app = Self.downloads.deletingLastPathComponent().appendingPathComponent("data/app")
        let g = try JSONDecoder().decode(Glossary.self, from: Data(contentsOf: app.appendingPathComponent("glossary.json")))
        let found = g.terms(in: "Each CRA keeps the tax increment from its district; millage is set each September.").map(\.id)
        XCTAssertTrue(found.contains("cra"), "\(found)")
        XCTAssertTrue(found.contains("tif"), "\(found)")
    }

    func testEveryAppDataFileDecodes() throws {
        let app = Self.downloads.deletingLastPathComponent().appendingPathComponent("data/app")
        let dec = JSONDecoder()
        let idx = try dec.decode(AppDataIndex.self, from: Data(contentsOf: app.appendingPathComponent("index.json")))
        XCTAssertTrue(idx.files.contains("tax.json"))
        _ = try dec.decode(AddressModel.self, from: Data(contentsOf: app.appendingPathComponent("address.json")))
        let pages = try dec.decode([PageInfo].self, from: Data(contentsOf: app.appendingPathComponent("pages.json")))
        XCTAssertGreaterThan(pages.count, 30)
        XCTAssertGreaterThan(try dec.decode([SiteUpdate].self, from: Data(contentsOf: app.appendingPathComponent("updates.json"))).count, 10)
        let v = try dec.decode(VendorDirectory.self, from: Data(contentsOf: app.appendingPathComponent("vendors.json")))
        XCTAssertGreaterThan(v.vendors.count, 500)
        let p = try dec.decode(PeopleDirectory.self, from: Data(contentsOf: app.appendingPathComponent("people.json")))
        XCTAssertGreaterThan(p.people.count, 100)
        // Same office, worded by several sources, shows once.
        if let pease = p.people.first(where: { $0.id == "clair-pease" }) {
            XCTAssertEqual(pease.mainRoles.map(\.role), ["County Commissioner, District 5 (Chairman)"])
            XCTAssertEqual(pease.headline, "County Commissioner, District 5 (Chairman), Bay County")
        }
        if let a = p.people.first(where: { $0.id == "nick-atkinson" }) { XCTAssertEqual(a.mainRoles.count, 1) }
        for person in p.people { XCTAssertFalse(person.mainRoles.isEmpty, person.id) }
        // The People list's order: government, then title, then last name, like the site.
        let groups = PeopleDirectory.grouped(p.people)
        XCTAssertEqual(groups.first?.title, "Bay County")
        XCTAssertEqual(groups.first?.people.first?.id, "clair-pease")  // the chair leads the county
        for g in groups { XCTAssertEqual(g.people.map { $0.rank ?? 99 }, g.people.map { $0.rank ?? 99 }.sorted(), g.title) }
        let dc = try dec.decode(DonorContracts.self, from: Data(contentsOf: app.appendingPathComponent("donor-contracts.json")))
        XCTAssertGreaterThan(dc.matches.count, 50)
        let mm = try dec.decode(MoneyMap.self, from: Data(contentsOf: app.appendingPathComponent("money-map.json")))
        XCTAssertGreaterThan(mm.donors.count, 100)
        let heat = mm.heat()
        XCTAssertEqual(heat.donors.count, 15)
        XCTAssertFalse(heat.govs.isEmpty)
    }

    /// Opt-in (BCM_LIVE=1): a real lookup against Bay County's and FEMA's map servers.
    func testLiveAddressLookup() async throws {
        try XCTSkipUnless(ProcessInfo.processInfo.environment["BCM_LIVE"] == "1")
        let gis = GISClient()
        let (matches, _) = try await gis.search("825 Ohio Ave")
        let m = try XCTUnwrap(matches.first { $0.community?.uppercased() == "LYNN HAVEN" } ?? matches.first)
        XCTAssertTrue(m.address.hasPrefix("825 OHIO"))
        let app = Self.downloads.deletingLastPathComponent().appendingPathComponent("data/app")
        let model = try JSONDecoder().decode(AddressModel.self, from: Data(contentsOf: app.appendingPathComponent("address.json")))
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("bcm-addr-\(UUID().uuidString)")
        let r = await AddressReport.load(m, gis: gis, client: BayCountyClient(cacheDirectory: dir), model: model)
        XCTAssertEqual(r.cityName, "Lynn Haven")
        XCTAssertNotNil(r.parcel)
        XCTAssertNotNil(r.commission?.s("REPNAME"))
        XCTAssertNotNil(r.elementary)
        XCTAssertTrue(r.floodChecked)
        let est = try XCTUnwrap(r.taxEstimate(model))
        XCTAssertEqual(est.districtID, "Lynn Haven")
        print("825 Ohio Ave:", est.districtLabel, Format.money(est.total), "zone", FloodText.describe(r.flood).headline,
              "| zoning", r.development?.zoning ?? "-", "| projects", r.development?.projects.count ?? 0, "| fees", r.fees?.count ?? -1)
        let near = try await NearbyMoney.load(near: m.point, client: BayCountyClient(cacheDirectory: dir))
        print("nearby CRA", near.cra.count, Format.money(near.craTotal), "projects", near.projects.count)
        let nearby = try await gis.addresses(near: m.point)
        XCTAssertFalse(nearby.isEmpty)
    }
}
