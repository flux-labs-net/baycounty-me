import Foundation
import Security
import BayCountyKit

/// Everything the staff app shows, loaded from /api/gov with the session token in the Keychain.
/// `-demo` (screenshots, App Review) loads made-up answers from staff-demo.json and never calls the server.
@MainActor
@Observable
final class StaffStore {
    static let shared = StaffStore()

    private(set) var me: StaffMe?
    private(set) var overview: StaffOverview?
    private(set) var home: StaffHome?
    private(set) var alerts: [StaffAlert] = []
    private(set) var notices: StaffPosts?
    private(set) var flags: [StaffFlag] = []
    private(set) var submissions: StaffSubmissions?
    private(set) var loading = false
    var error: String?
    /// The workspace open now. The site owner starts on the all-governments view (nil).
    var workspaceId: String?

    private let client: StaffClient
    let demo: StaffDemo?

    var signedIn: Bool { demo != nil || client.token != nil }
    var isOwner: Bool { me?.admin == true }
    var workspace: StaffWorkspace? { me?.workspaces.first { $0.id == workspaceId } }
    var role: String { workspace?.role ?? (isOwner ? "owner" : "viewer") }
    func can(_ need: String) -> Bool { Staff.can(role, need) }
    var alertKinds: [String: String] { me?.alertKinds ?? [:] }
    var noticeKinds: [String: String] { me?.noticeKinds ?? [:] }

    private init() {
        let args = ProcessInfo.processInfo.arguments
        let d: StaffDemo? = args.contains("-demo") ? Bundle.main.url(forResource: "staff-demo", withExtension: "json")
            .flatMap { try? Data(contentsOf: $0) }.flatMap { try? StaffDemo.decode($0) } : nil
        demo = d
        client = StaffClient(token: d == nil ? StaffKeychain.read() : nil)
        guard let d else { return }
        overview = d.overview; home = d.home; alerts = d.alerts.alerts; notices = d.notices; submissions = d.submissions
        if args.contains("-asStaff") {
            // A city alert sender's view: one workspace, no all-governments view.
            let json = #"{"email":"utilities@example.gov","admin":false,"workspaces":[{"id":"lh","name":"City of Lynn Haven","countywide":false,"role":"alert_sender"}],"alert_kinds":\#(Self.kindsJSON(d.me.alertKinds)),"notice_kinds":\#(Self.kindsJSON(d.me.noticeKinds))}"#
            me = try? StaffMe.decode(Data(json.utf8))
            workspaceId = "lh"
            flags = d.flags.flags.filter { $0.workspaceId == "lh" }
        } else {
            me = d.me
            flags = d.flags.flags
            if let w = args.firstIndex(of: "-workspace"), w + 1 < args.count { workspaceId = args[w + 1] }
        }
    }

    private static func kindsJSON(_ k: [String: String]?) -> String {
        (try? JSONSerialization.data(withJSONObject: k ?? [:])).flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
    }

    // MARK: sign-in

    func login(email: String) async -> Bool {
        error = nil
        do { _ = try await client.login(email: email); return true } catch { self.error = error.localizedDescription; return false }
    }

    func verify(email: String, code: String) async -> Bool {
        error = nil
        do {
            let m = try await client.verify(email: email, code: code)
            if let t = m.token { StaffKeychain.save(t) }
            me = m
            pickDefaultWorkspace()
            await refresh()
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    func signOut() async {
        if demo == nil { await client.logout() }
        StaffKeychain.clear()
        me = nil; overview = nil; home = nil; alerts = []; notices = nil; flags = []; submissions = nil; workspaceId = nil
    }

    private func pickDefaultWorkspace() {
        guard let me else { return }
        if me.admin { workspaceId = nil } else if workspace == nil { workspaceId = me.workspaces.first?.id }
    }

    // MARK: loading

    func refresh() async {
        guard demo == nil, client.token != nil else { return }
        loading = true; defer { loading = false }
        do {
            if me == nil { me = try await client.me(); pickDefaultWorkspace() }
            try await loadCurrent()
        } catch { handle(error) }
    }

    func open(_ id: String?) async {
        workspaceId = id
        guard demo == nil else { return }
        loading = true; defer { loading = false }
        do { try await loadCurrent() } catch { handle(error) }
    }

    private func loadCurrent() async throws {
        if let ws = workspaceId {
            async let h = client.home(ws), a = client.alerts(ws), n = client.notices(ws), f = client.flags(ws)
            let (hh, aa, nn, ff) = try await (h, a, n, f)
            home = hh; alerts = aa.alerts; notices = nn; flags = ff.flags
            if can("submit") { submissions = try? await client.submissions(ws) } else { submissions = nil }
        } else if isOwner {
            async let o = client.overview(), f = client.reviewFlags(status: "all")
            let (oo, ff) = try await (o, f)
            overview = oo; flags = ff.flags
            home = nil; alerts = []; notices = nil; submissions = nil
        }
    }

    private func handle(_ e: Error) {
        if case StaffClient.StaffError.signedOut = e { StaffKeychain.clear(); client.token = nil; me = nil }
        error = e.localizedDescription
    }

    // MARK: actions (each returns an error message, or nil when it worked)

    func reach(kind: String, countywide: Bool) async -> StaffReach? {
        guard let ws = workspaceId else { return nil }
        if demo != nil { return StaffReach(topic: "water", phones: countywide ? 9120 : 1240, emails: countywide ? 3810 : 512, note: nil) }
        return try? await client.reach(ws, kind: kind, countywide: countywide)
    }

    func sendAlert(kind: String, title: String, message: String, instruction: String, severity: String, countywide: Bool, hours: Int) async -> Result<String, Error> {
        guard let ws = workspaceId else { return .failure(StaffClient.StaffError.server("Pick a government first.", 400)) }
        if demo != nil { return .success("Sent.") }
        do {
            let m = try await client.sendAlert(ws, kind: kind, title: title, message: message, instruction: instruction, severity: severity, countywide: countywide, hours: hours)
            try await loadCurrent()
            return .success(m)
        } catch { return .failure(error) }
    }

    func confirm(_ a: StaffAlert) async -> String? { await act { try await self.client.confirmAlert($0, id: a.id) } }
    func end(_ a: StaffAlert) async -> String? { await act { try await self.client.endAlert($0, id: a.id) } }
    func withdraw(_ p: StaffPost) async -> String? { await act { try await self.client.withdrawNotice($0, id: p.id) } }
    func saveNotice(id: Int?, kind: String, title: String, text: String, eventDate: String?) async -> String? {
        await act { try await self.client.saveNotice($0, id: id, kind: kind, title: title, text: text, eventDate: eventDate) }
    }
    func answer(_ f: StaffFlag, status: String, reply: String) async -> String? {
        if demo != nil { return nil }
        do { try await client.answerFlag(id: f.id, status: status, reply: reply); try await loadCurrent(); return nil } catch { return error.localizedDescription }
    }

    // MARK: send records

    /// Reads a file and saves it as waiting. Nothing is public until `publishRecords`.
    func previewRecords(kind: String, filename: String, content: Data) async -> Result<StaffRecordPreview, Error> {
        guard let ws = workspaceId else { return .failure(StaffClient.StaffError.server("Pick a government first.", 400)) }
        if content.count > StaffClient.maxInlineBytes {
            return .failure(StaffClient.StaffError.server("That file is over 3 MB. Send it from the web workspace or by email instead.", 413))
        }
        if demo != nil {
            let j = #"{"id":"c9","kind":"\#(kind)","ok":true,"label":"Contracts awarded","row_count":6,"parsed_total":1284310.5,"skipped":1,"already_on_site":2,"withheld":0,"period":{"start":"2026-10-02","end":"2026-10-27"}}"#
            return Result { try StaffRecordPreview.decode(Data(j.utf8)) }
        }
        do {
            let p = try await client.previewRecords(ws, kind: kind, filename: filename, content: content)
            submissions = try? await client.submissions(ws)
            return .success(p)
        } catch { return .failure(error) }
    }
    func publishRecords(id: String) async -> String? { await act { _ = try await self.client.publishRecords($0, id: id) } }
    func withdrawRecords(id: String) async -> String? { await act { try await self.client.withdrawRecords($0, id: id) } }

    private func act(_ f: @escaping (String) async throws -> Void) async -> String? {
        guard let ws = workspaceId else { return "Pick a government first." }
        if demo != nil { return nil }
        do { try await f(ws); try await loadCurrent(); return nil } catch { return error.localizedDescription }
    }
}

/// The staff session token, kept in the Keychain on this phone only (never in backups or iCloud).
enum StaffKeychain {
    private static let service = "me.baycounty.staff.session"
    private static var query: [String: Any] { [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "token"] }

    static func read() -> String? {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }
    static func save(_ token: String) {
        clear()
        var q = query
        q[kSecValueData as String] = Data(token.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        SecItemAdd(q as CFDictionary, nil)
    }
    static func clear() { SecItemDelete(query as CFDictionary) }
}
