import XCTest
@testable import BayCountyKit

/// The staff app's answers from /api/gov decode, roles match the server's ranks, and requests carry the app token.
final class StaffTests: XCTestCase {
    func demo() throws -> StaffDemo {
        let url = try XCTUnwrap(Bundle.module.url(forResource: "staff-demo", withExtension: "json", subdirectory: "Fixtures"))
        return try StaffDemo.decode(Data(contentsOf: url))
    }

    func testDecodesEveryDemoAnswer() throws {
        let d = try demo()
        XCTAssertTrue(d.me.admin)
        XCTAssertEqual(d.me.workspaces.first?.id, "county")
        XCTAssertEqual(d.overview.totals.openFlags, 3)
        XCTAssertEqual(d.overview.workspaces.filter(\.needsAttention).map(\.id), ["county", "lh", "pc"])
        XCTAssertEqual(d.home.counts.liveAlerts, 1)
        XCTAssertEqual(d.alerts.alerts.map(\.statusLabel), ["Live", "Ended"])
        XCTAssertEqual(d.notices.posts.first?.kindLabel, "Public hearing or ordinance")
        XCTAssertFalse(d.notices.fromRecords.first!.editable)
        XCTAssertEqual(d.flags.flags.first?.subject, "Budget by year · General Fund, 2026 · amount")
    }

    func testRolesFollowTheServer() {
        XCTAssertTrue(Staff.can("owner", "alert_sender"))
        XCTAssertTrue(Staff.can("alert_sender", "publisher"))
        XCTAssertFalse(Staff.can("publisher", "alert_sender"))
        XCTAssertFalse(Staff.can("auditor", "publisher"))
        XCTAssertFalse(Staff.can("nobody", "viewer"))
    }

    func testRecordsSendersCanOnlySendRecords() {
        XCTAssertTrue(Staff.can("records", "submit"))
        XCTAssertTrue(Staff.can("publisher", "submit"))
        XCTAssertTrue(Staff.can("owner", "submit"))
        XCTAssertFalse(Staff.can("viewer", "submit"))
        XCTAssertFalse(Staff.can("auditor", "submit"))
        XCTAssertFalse(Staff.can("records", "publisher"))
        XCTAssertEqual(Staff.roleLabel["records"], "Records sender")
    }

    func testDecodesSentRecords() throws {
        let s = try XCTUnwrap(try demo().submissions)
        XCTAssertEqual(s.address, "lynnhaven@ingest.baycounty.me")
        XCTAssertEqual(s.due.map(\.current), [true, false, false])
        XCTAssertEqual(s.files.map(\.statusLabel), ["Waiting for your OK", "Published", "Doesn’t add up"])
        XCTAssertEqual(s.files[0].detail, "Contracts awarded · 6 rows · through Oct 27, 2026")
        XCTAssertTrue(s.files[0].canPublish)
        XCTAssertTrue(s.files[1].canWithdraw)
        XCTAssertFalse(s.files[2].canWithdraw)
        let bad = try StaffRecordPreview.decode(Data(#"{"id":"c2","kind":"contracts","ok":false,"missing":["vendor","amount"]}"#.utf8))
        XCTAssertEqual(bad.problem, "We couldn't find: vendor, amount.")
    }

    func testActivityReadsAsASentence() throws {
        let a = try demo().home.activity[0]
        XCTAssertEqual(a.sentence, "utilities@example.gov sent an alert: Boil water: Ohio Ave, 5th to 9th St")
        XCTAssertEqual(try demo().home.activity[3].sentence, "clerk@example.gov signed in")
    }

    func testAlertsNeedASecondPerson() throws {
        let j = #"{"id":5,"kind":"general","title":"Sandbags","message":"Open","countywide":true,"status":"pending","created_by":"Em1@x.gov","created_at":"2026-10-30T14:00:00Z"}"#
        let a = try Staff.decoder().decode(StaffAlert.self, from: Data(j.utf8))
        XCTAssertEqual(a.statusLabel, "Needs a second person")
        XCTAssertFalse(a.canConfirm(as: "em1@x.gov"), "the writer cannot confirm their own alert")
        XCTAssertTrue(a.canConfirm(as: "em2@x.gov"))
    }

    func testReachSentence() {
        XCTAssertEqual(StaffReach(topic: "water", phones: 1240, emails: 1, note: nil).sentence, "Reaches 1,240 phones and 1 inbox now, plus the public alert timeline.")
        XCTAssertEqual(StaffReach(topic: nil, phones: 0, emails: 0, note: "Timeline only.").sentence, "Timeline only.")
    }

    func testRequestsUseTheBearerToken() throws {
        let r = StaffClient.request(action: "alert", token: "bcmg_x", body: ["workspace": "lh", "kind": "road"])
        XCTAssertEqual(r.url?.absoluteString, "https://baycounty.me/api/gov?action=alert")
        XCTAssertEqual(r.value(forHTTPHeaderField: "Authorization"), "Bearer bcmg_x")
        XCTAssertEqual(r.httpMethod, "POST")
        let g = StaffClient.request(action: "reach", query: ["workspace": "lh", "kind": "road"], token: nil, body: nil)
        XCTAssertEqual(g.url?.query, "action=reach&kind=road&workspace=lh")
    }

    func testDates() {
        XCTAssertEqual(Staff.when("2026-10-30T13:05:00Z"), "Oct 30, 8:05 AM")
        XCTAssertEqual(Staff.when("2026-11-12"), "Nov 12, 2026")
        XCTAssertEqual(Staff.hoursLabel(48), "2 days")
        XCTAssertEqual(Staff.hoursLabel(6), "6 hours")
    }
}

#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Answers /api/gov the way the real server does: verify gives only the token, me gives the account.
final class StaffServerStub: URLProtocol {
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let action = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "action" }?.value
        let body: String
        switch action {
        case "verify": body = #"{"ok":true,"email":"owner@example.gov","expires_in_days":14,"token":"bcmg_test"}"#
        case "me":
            body = request.value(forHTTPHeaderField: "Authorization") == "Bearer bcmg_test"
                ? #"{"email":"owner@example.gov","admin":true,"workspaces":[{"id":"lh","name":"City of Lynn Haven","countywide":false,"role":"owner"}],"alert_kinds":{},"notice_kinds":{}}"#
                : #"{"error":"Sign in first."}"#
        default: body = #"{"error":"unexpected"}"#
        }
        let resp = HTTPURLResponse(url: request.url!, statusCode: body.contains("error") ? 401 : 200, httpVersion: nil, headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: resp, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data(body.utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

final class StaffSignInTests: XCTestCase {
    func testVerifyLoadsTheAccountAfterTheToken() async throws {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StaffServerStub.self]
        let client = StaffClient(token: nil, session: URLSession(configuration: config))
        let me = try await client.verify(email: "owner@example.gov", code: "123456")
        XCTAssertEqual(client.token, "bcmg_test")
        XCTAssertEqual(me.token, "bcmg_test")
        XCTAssertTrue(me.admin)
        XCTAssertEqual(me.workspaces.first?.id, "lh")
    }

    func testReadsBigintIdsSentAsStrings() throws {
        let posts = try StaffPosts.decode(Data(#"{"kind":"notice","posts":[],"from_records":[{"id":"1","notice_id":"pn:1","title":"From the notice site","kind":null,"published":"2026-10-01","editable":false}]}"#.utf8))
        XCTAssertEqual(posts.fromRecords.first?.id, 1)
        let alerts = try StaffAlerts.decode(Data(#"{"alerts":[{"id":"42","kind":"road","title":"Hwy 390","message":"Closed","countywide":false,"status":"sent","created_by":"a@example.gov","created_at":"2026-10-30T12:00:00Z"}]}"#.utf8))
        XCTAssertEqual(alerts.alerts.first?.id, 42)
    }
}
