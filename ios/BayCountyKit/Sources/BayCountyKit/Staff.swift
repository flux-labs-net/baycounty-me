import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// The staff app (BayCounty.me Staff): city and county staff, and the site owner, working in the government
/// workspace (/staff on the site) from a phone. Everything goes through /api/gov (api/gov.js). The rules are the
/// workspace's: staff post notices and send alerts for their own government; record data is read-only and can only
/// be flagged; the site owner (a BayCounty.me admin) is owner of every workspace and also sees the all-governments view.
public enum Staff {
    /// Roles from strongest to weakest, as the server ranks them (api/_gov.js ROLES).
    public static let rank: [String: Int] = ["viewer": 1, "auditor": 1, "records": 1, "official": 1, "publisher": 2, "alert_sender": 3, "owner": 4]
    public static let roleLabel: [String: String] = ["owner": "Owner", "alert_sender": "Alert sender", "publisher": "Publisher", "records": "Records sender", "viewer": "Viewer", "auditor": "Auditor", "official": "Elected official"]
    /// `need` is a role, or "submit" (send records): the records sender role, or publisher and up (api/_gov.js allowed).
    public static func can(_ role: String, _ need: String) -> Bool {
        if need == "submit" { return role == "records" || (rank[role] ?? 0) >= 2 }
        return (rank[role] ?? 0) >= (rank[need] ?? 9)
    }

    /// The kinds of record a government can send, in the order the app lists them (labels match api/_records.js).
    public static let recordKinds: [(key: String, label: String, hint: String)] = [
        ("checkbook", "Checkbook (every payment)", "The check register or payments report for one or more whole months."),
        ("budget", "Budget vs. actual", "The budget-vs-actual report, as of a month end."),
        ("contracts", "Contracts awarded", "Vendor, amount and award date at least."),
        ("payroll", "Payroll (job titles and pay)", "A payroll or position list: job title and pay. Names are removed before anything is published."),
        ("appointments", "Board appointments", "Who sits on each board you appoint: board, member and term."),
        ("fees", "Fee or rate changes", "A new or changed fee: what it is, the new amount and when it starts."),
    ]
    public static func recordKindLabel(_ k: String) -> String { recordKinds.first { $0.key == k }?.label ?? k.capitalized }

    /// Alert kinds in the order the form lists them (labels come from the server's `me` answer).
    public static let alertOrder = ["evacuation", "shelter", "boil-water", "road", "safety", "general"]
    public static let severities: [(key: String, label: String)] = [("extreme", "Extreme"), ("severe", "Severe"), ("moderate", "Moderate"), ("minor", "Minor"), ("info", "Information")]
    public static let noticeOrder = ["meeting", "hearing", "bid", "utility", "road", "other"]
    public static let hourChoices = [6, 12, 24, 48, 72, 168]
    public static func hoursLabel(_ h: Int) -> String { h % 24 == 0 ? (h == 24 ? "1 day" : h == 168 ? "1 week" : "\(h / 24) days") : "\(h) hours" }

    /// The workspace log's action names in words (same wording as site/staff.js).
    public static let actions: [String: String] = [
        "signed_in": "signed in", "notice_posted": "posted a notice", "notice_edited": "changed a notice", "notice_withdrawn": "withdrew a notice",
        "event_posted": "posted an event", "event_edited": "changed an event", "event_withdrawn": "withdrew an event", "job_posted": "posted a job",
        "job_edited": "changed a job", "job_withdrawn": "withdrew a job", "alert_sent": "sent an alert",
        "alert_drafted": "saved a countywide alert for a second person to confirm", "alert_confirmed": "confirmed an alert",
        "alert_ended": "ended an alert", "alert_cancelled": "cancelled an alert", "data_flagged": "flagged record data",
        "flag_answered": "BayCounty.me answered a flag", "member_set": "changed access", "member_removed": "removed access",
        "records_published": "published records", "records_withdrawn": "withdrew records", "records_confirmed": "confirmed a file",
        "records_review_published": "published a file after review", "records_review_held": "kept a file off the site after review", "intake_senders_changed": "changed who may email records in",
        "feed_agreed": "agreed to a source we read", "feed_unagreed": "took back agreement to a source",
    ]

    public static func decoder() -> JSONDecoder { let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase; return d }

    /// "Nov 1, 9:05 AM" in Bay County time, for server timestamps; plain dates ("2026-11-01") as "Nov 1, 2026".
    /// Government names as staff say them: "City of Panama City" -> "Panama City". Other names stay whole.
    public static func short(_ name: String) -> String {
        name.hasPrefix("City of ") ? String(name.dropFirst("City of ".count)) : name
    }
    public static func short(_ name: String?) -> String? { name.map { short($0) } }

    public static func when(_ s: String?) -> String {
        guard let s, !s.isEmpty else { return "" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        if s.count == 10, let d = ISO8601DateFormatter.day.date(from: s) { f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "MMM d, yyyy"; return f.string(from: d) }
        guard let d = parse(s) else { return s }
        f.dateFormat = "MMM d, h:mm a"
        return f.string(from: d)
    }
    static func parse(_ s: String) -> Date? {
        let a = ISO8601DateFormatter(); a.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = a.date(from: s) { return d }
        a.formatOptions = [.withInternetDateTime]
        return a.date(from: s)
    }
}

extension ISO8601DateFormatter {
    static let day: ISO8601DateFormatter = { let f = ISO8601DateFormatter(); f.formatOptions = [.withFullDate]; return f }()
}

/// Database ids are bigints, which the server sends as strings ("12"); older answers and the demo file use numbers.
@propertyWrapper
public struct RecordID: Decodable, Hashable, Sendable {
    public var wrappedValue: Int
    public init(wrappedValue: Int) { self.wrappedValue = wrappedValue }
    public init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let n = try? c.decode(Int.self) { wrappedValue = n; return }
        let s = try c.decode(String.self)
        guard let n = Int(s) else { throw DecodingError.dataCorruptedError(in: c, debugDescription: "Not a record id: \(s)") }
        wrappedValue = n
    }
}

public struct StaffWorkspace: Decodable, Hashable, Sendable, Identifiable {
    public let id: String
    public let name: String
    public let countywide: Bool?
    public let role: String
    /// An elected official's seat on record (officeholder-terms person_id); nil for staff.
    public let personId: String?
    /// An elected commissioner or council member: opens on their board dashboard.
    public var isOfficial: Bool { role == "official" }
    public var roleLabel: String { Staff.roleLabel[role] ?? role.capitalized }
    public func can(_ need: String) -> Bool { Staff.can(role, need) }
}

/// GET ?action=me: who is signed in and what they can open.
public struct StaffMe: Decodable, Sendable {
    public let email: String
    public let admin: Bool
    public let workspaces: [StaffWorkspace]
    public let alertKinds: [String: String]?
    public let noticeKinds: [String: String]?
    /// Only in the answer to a sign-in from the app.
    public var token: String?
    public static func decode(_ data: Data) throws -> StaffMe { try Staff.decoder().decode(StaffMe.self, from: data) }
}

public struct StaffActivity: Decodable, Hashable, Sendable, Identifiable {
    public let email: String
    public let action: String
    public let detail: JSONValue?
    public let at: String
    public let govName: String?
    public var id: String { email + action + at }
    /// "clerk@example.gov posted a notice: Budget hearing".
    public var sentence: String {
        var s = "\(email) \(Staff.actions[action] ?? action.replacingOccurrences(of: "_", with: " "))"
        if case .object(let o)? = detail, case .string(let t)? = o["title"], !t.isEmpty { s += ": " + t }
        return s
    }
}

/// GET ?action=home: one workspace's counts and latest activity.
public struct StaffHome: Decodable, Sendable {
    public struct Counts: Decodable, Sendable {
        public let notices: Int
        public let events: Int
        public let jobs: Int
        public let liveAlerts: Int
        public let waitingAlerts: Int
        public let openFlags: Int
        public let members: Int
    }
    public let role: String
    public let counts: Counts
    public let activity: [StaffActivity]
    public static func decode(_ data: Data) throws -> StaffHome { try Staff.decoder().decode(StaffHome.self, from: data) }
}

public struct StaffAlert: Decodable, Hashable, Sendable, Identifiable {
    @RecordID public var id: Int
    public let kind: String
    public let title: String
    public let message: String
    public let instruction: String?
    public let severity: String?
    public let countywide: Bool
    public let status: String
    public let createdBy: String
    public let createdAt: String
    public let confirmedBy: String?
    public let sentAt: String?
    public let endsAt: String?
    public let live: Bool?
    public let geometry: String?
    /// How many phones, inboxes and texts it was sent to ({push, email, sms}); staff and admins only.
    public let sent: [String: Int]?

    public var isLive: Bool { live ?? (status == "sent") }
    /// "2 phones, 1 inbox", or nil before anything went out.
    public var sentSentence: String? {
        guard let s = sent else { return nil }
        func n(_ k: String, _ one: String, _ many: String) -> String? { (s[k] ?? 0) > 0 ? "\(s[k]!) \(s[k] == 1 ? one : many)" : nil }
        let parts = [n("push", "phone", "phones"), n("email", "inbox", "inboxes"), n("sms", "text", "texts")].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: ", ")
    }
    public var isWaiting: Bool { status == "pending" }
    /// The status chip: Live, Waiting for a second person, Ended, Cancelled, Expired.
    public var statusLabel: String {
        if isWaiting { return "Needs a second person" }
        if isLive { return "Live" }
        switch status { case "ended": return "Ended"; case "cancelled": return "Cancelled"; case "removed": return "Removed"; case "sent": return "Expired"; default: return status.capitalized }
    }
    /// Who else can confirm a waiting alert: anyone with alert rights but the person who wrote it.
    public func canConfirm(as email: String) -> Bool { isWaiting && createdBy.lowercased() != email.lowercased() }
}

public struct StaffAlerts: Decodable, Sendable {
    public let countywide: Bool?
    public let alerts: [StaffAlert]
    public static func decode(_ data: Data) throws -> StaffAlerts { try Staff.decoder().decode(StaffAlerts.self, from: data) }
}

/// GET ?action=reach: how many phones and inboxes an alert would reach now.
public struct StaffReach: Decodable, Sendable, Equatable {
    public let topic: String?
    public let phones: Int?
    public let emails: Int?
    public let note: String?
    public init(topic: String?, phones: Int?, emails: Int?, note: String?) { self.topic = topic; self.phones = phones; self.emails = emails; self.note = note }
    public var sentence: String {
        if let note, topic == nil { return note }
        func n(_ v: Int?, _ one: String, _ many: String) -> String { guard let v else { return "some " + many }; return "\(v.formatted()) " + (v == 1 ? one : many) }
        return "Reaches \(n(phones, "phone", "phones")) and \(n(emails, "inbox", "inboxes")) now, plus the public alert timeline."
    }
}

public struct StaffPost: Decodable, Hashable, Sendable, Identifiable {
    @RecordID public var id: Int
    public let title: String
    public let kind: String?
    public let kindLabel: String?
    public let published: String?
    public let eventDate: String?
    public let text: String?
    public let pdfUrl: String?
    public let geometry: String?
    public let editable: Bool
}

public struct StaffPosts: Decodable, Sendable {
    public let kind: String
    public let posts: [StaffPost]
    public let fromRecords: [StaffPost]
    public static func decode(_ data: Data) throws -> StaffPosts { try Staff.decoder().decode(StaffPosts.self, from: data) }
}

public struct StaffFlag: Decodable, Hashable, Sendable, Identifiable {
    @RecordID public var id: Int
    public let email: String
    public let dataset: String
    public let recordLabel: String?
    public let field: String?
    public let shownValue: String?
    public let correctValue: String?
    public let evidenceUrl: String?
    public let note: String?
    public let status: String
    public let reply: String?
    public let createdAt: String
    public let govName: String?
    public let workspaceId: String?
    public var statusLabel: String { ["open": "Open", "fixed": "Fixed", "not_changed": "Not changed"][status] ?? status }
    /// "Budget by year · General Fund · amount".
    public var subject: String {
        [StaffFlag.datasetLabel[dataset] ?? dataset, recordLabel, field].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
    }
    public static let datasetLabel: [String: String] = [
        "budget-years": "Budget by year", "officeholder-terms": "Who held each seat", "people-directory": "Officials and staff",
        "utility-rates": "Utility rates", "trash-pickup": "Trash and recycling pickup", "parks": "Parks", "development-projects": "Development projects",
        "public-notices": "Public notices", "job-openings": "Job openings", "community-events": "Events", "other": "Other",
    ]
}

public struct StaffFlags: Decodable, Sendable {
    public let flags: [StaffFlag]
    public static func decode(_ data: Data) throws -> StaffFlags { try Staff.decoder().decode(StaffFlags.self, from: data) }
}

/// GET ?action=overview (site owner only): every government at a glance.
public struct StaffOverview: Decodable, Sendable {
    public struct Totals: Decodable, Sendable {
        public let workspaces: Int
        public let members: Int
        public let liveAlerts: Int
        public let waitingAlerts: Int
        public let openFlags: Int
        public let notices: Int
    }
    public struct Row: Decodable, Hashable, Sendable, Identifiable {
        public let id: String
        public let name: String
        public let countywide: Bool?
        public let members: Int
        public let lastActivity: String?
        public let liveAlerts: Int
        public let waitingAlerts: Int
        public let openFlags: Int
        public let notices: Int
        /// What needs the owner first: waiting alerts, then open flags.
        public var needsAttention: Bool { waitingAlerts > 0 || openFlags > 0 }
    }
    public let totals: Totals
    public let workspaces: [Row]
    public let activity: [StaffActivity]
    public static func decode(_ data: Data) throws -> StaffOverview { try Staff.decoder().decode(StaffOverview.self, from: data) }
}

/// GET ?action=submissions: what's due, the government's intake email address and every file sent.
public struct StaffSubmissions: Decodable, Sendable {
    public struct Due: Decodable, Hashable, Sendable, Identifiable {
        public let kind: String
        public let label: String
        public let want: String
        public let have: String?
        public let current: Bool
        public let text: String
        public var id: String { kind }
    }
    public let address: String?
    public let due: [Due]
    public let files: [StaffRecordFile]
    public static func decode(_ data: Data) throws -> StaffSubmissions { try Staff.decoder().decode(StaffSubmissions.self, from: data) }
}

/// One file a government sent ("f12" from the finance importer, "c3" a contract list).
public struct StaffRecordFile: Decodable, Hashable, Sendable, Identifiable {
    public let id: String
    public let kind: String
    public let name: String
    public let status: String
    public let via: String?
    public let sentBy: String?
    public let sentAt: String?
    public let periodStart: String?
    public let periodEnd: String?
    public let rows: Int?
    public let problem: String?
    public let publishedAt: String?
    /// Waiting for your OK, Being checked, In review, Published, Doesn’t add up, Not published after review, Withdrawn.
    public var statusLabel: String {
        ["waiting": "Waiting for your OK", "checking": "Being checked", "in_review": "In review", "published": "Published", "held": "Doesn’t add up", "not_published": "Not published after review", "withdrawn": "Withdrawn"][status] ?? status.capitalized
    }
    public var canPublish: Bool { status == "waiting" }
    public var canWithdraw: Bool { status == "waiting" || status == "published" || status == "in_review" }
    /// "Contracts awarded · 14 rows · through Sep 30, 2026".
    public var detail: String {
        var parts = [Staff.recordKindLabel(kind)]
        if let rows { parts.append("\(rows.formatted()) row\(rows == 1 ? "" : "s")") }
        if let periodEnd { parts.append("through " + Staff.when(periodEnd)) }
        return parts.joined(separator: " · ")
    }
}

/// POST ?action=submit-preview: what we read from a file, before anyone publishes it.
public struct StaffRecordPreview: Decodable, Sendable {
    public struct Period: Decodable, Sendable { public let start: String?; public let end: String? }
    public let id: String
    public let kind: String
    public let ok: Bool
    public let missing: [String]?
    public let label: String?
    public let rowCount: Int?
    public let parsedTotal: Double?
    public let printedTotal: Double?
    public let skipped: Int?
    public let alreadyOnSite: Int?
    public let withheld: Int?
    public let alreadyAdded: Bool?
    public let period: Period?
    public let warnings: [String]?
    /// "We couldn't find: vendor, amount" when the file can't be read.
    public var problem: String? {
        guard !ok else { return nil }
        if alreadyAdded == true { return "This file was already sent." }
        let m = (missing ?? []).joined(separator: ", ")
        return m.isEmpty ? "We couldn't read this file." : "We couldn't find: \(m)."
    }
    public static func decode(_ data: Data) throws -> StaffRecordPreview { try Staff.decoder().decode(StaffRecordPreview.self, from: data) }
}

/// GET ?action=official: an elected official's board dashboard (api/_official.js). All public record, read only.
public struct StaffBoard: Decodable, Sendable {
    public struct Seat: Decodable, Sendable, Hashable { public let personId: String; public let name: String; public let seat: String; public let body: String?; public let since: String? }
    public struct Item: Decodable, Sendable, Hashable { public let title: String; public let amount: String? }
    public struct Meeting: Decodable, Sendable, Hashable {
        public let boardName: String; public let title: String; public let date: String; public let start: String?; public let location: String?
        public let agendaUrl: String?; public let packetUrl: String?; public let minutesUrl: String?; public let status: String?
        public let items: [Item]; public let moneyItems: Int
        public var statusLabel: String? {
            if status == "cancelled" { return "Cancelled" }
            if status == "expected" { return "Agenda not posted yet" }
            return agendaUrl != nil ? "Agenda posted" : nil
        }
    }
    public struct Meetings: Decodable, Sendable { public let upcoming: [Meeting]; public let recent: [Meeting] }
    public struct Count: Decodable, Sendable { public let votes, yes, no, absent, abstain, split, onLosingSide: Int }
    public struct Vote: Decodable, Sendable, Hashable {
        public let date: String?; public let vote: String; public let headline: String?; public let outcome: String?; public let tally: String?
        public let split: Bool; public let onLosingSide: Bool; public let amount: Double?; public let sourceUrl: String?
        public var voteLabel: String { ["yes": "Yes", "no": "No", "absent": "Absent", "abstain": "Abstained"][vote] ?? "Not recorded" }
        /// "Passed 3-2", leaving out tallies the minutes didn't give.
        public var result: String {
            let t = tally.flatMap { $0.range(of: #"^\d+\s*-\s*\d+$"#, options: .regularExpression) != nil ? $0 : nil }
            return [outcome.map { $0.prefix(1).uppercased() + $0.dropFirst() }, t].compactMap { $0 }.joined(separator: " ")
        }
    }
    public struct Votes: Decodable, Sendable { public let count: Count; public let presentRate: Double?; public let recent: [Vote]; public let first: String?; public let last: String? }
    public struct Year: Decodable, Sendable, Hashable { public let fiscalYear: Int; public let total: Double?; public let generalFund: Double? }
    public struct Budget: Decodable, Sendable { public let history: [Year] }
    public struct Contract: Decodable, Sendable, Hashable { public let date: String?; public let vendor: String; public let amount: Double?; public let purpose: String? }
    public struct Contracts: Decodable, Sendable { public let count: Int; public let total: Double; public let rows: [Contract] }
    public struct Numbers: Decodable, Sendable { public let budget: Budget?; public let contracts: Contracts? }

    public let official: Seat?
    public let board: [Seat]
    public let government: String
    public let meetings: Meetings
    public let votes: Votes?
    public let numbers: Numbers?

    public var latestBudget: Year? { numbers?.budget?.history.last }
    public var nextMeeting: Meeting? { meetings.upcoming.first { $0.status != "cancelled" } }
    /// "$789.1M", "$84K", "$950".
    public static func money(_ v: Double?) -> String {
        guard let v else { return "—" }
        let a = abs(v)
        if a >= 1e9 { return "$" + String(format: "%.2fB", v / 1e9) }
        if a >= 1e6 { return "$" + String(format: "%.1fM", v / 1e6) }
        if a >= 1e4 { return "$\(Int((v / 1e3).rounded()))K" }
        let f = NumberFormatter(); f.numberStyle = .decimal; f.locale = Locale(identifier: "en_US")
        return "$" + (f.string(from: NSNumber(value: v.rounded())) ?? "\(Int(v))")
    }
    public static func decode(_ data: Data) throws -> StaffBoard { try Staff.decoder().decode(StaffBoard.self, from: data) }
}

/// Made-up answers for screenshots and App Review (no real staff, no real alerts): `staff-demo.json`.
public struct StaffDemo: Decodable, Sendable {
    public let me: StaffMe
    public let overview: StaffOverview
    public let home: StaffHome
    public let alerts: StaffAlerts
    public let notices: StaffPosts
    public let flags: StaffFlags
    public let submissions: StaffSubmissions?
    public let board: StaffBoard?
    public static func decode(_ data: Data) throws -> StaffDemo { try Staff.decoder().decode(StaffDemo.self, from: data) }
}

/// Talks to /api/gov with the session token the staff app keeps in the Keychain.
public final class StaffClient: @unchecked Sendable {
    public enum StaffError: LocalizedError {
        case server(String, Int)
        case signedOut
        public var errorDescription: String? {
            switch self { case .server(let m, _): return m; case .signedOut: return "Your session ended. Sign in again." }
        }
    }
    private let session: URLSession
    private let base: URL
    public var token: String?

    public init(token: String?, session: URLSession = .shared, base: URL = BayCountyClient.site) {
        self.token = token; self.session = session; self.base = base
    }

    public static func request(base: URL = BayCountyClient.site, action: String, query: [String: String] = [:], token: String?, body: [String: Any]?) -> URLRequest {
        var c = URLComponents(url: base.appendingPathComponent("api/gov"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "action", value: action)] + query.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) }
        var r = URLRequest(url: c.url!, timeoutInterval: 30)
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys])
        }
        return r
    }

    private func call(_ action: String, query: [String: String] = [:], _ body: [String: Any]? = nil) async throws -> Data {
        let (data, resp) = try await session.data(for: Self.request(base: base, action: action, query: query, token: token, body: body))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 { throw StaffError.signedOut }
        guard code == 200 else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw StaffError.server(msg ?? "Something went wrong. Try again.", code)
        }
        return data
    }
    private func message(_ d: Data) -> String { ((try? JSONSerialization.jsonObject(with: d) as? [String: Any])?["message"] as? String) ?? "Done." }

    public func login(email: String) async throws -> String { message(try await call("login", ["email": email])) }
    public func verify(email: String, code: String) async throws -> StaffMe {
        // The verify answer carries only the token, so the account (workspaces, admin) comes from `me` right after.
        struct Signed: Decodable { let token: String? }
        let signed = try Staff.decoder().decode(Signed.self, from: try await call("verify", ["email": email, "code": code, "client": "app"]))
        guard let t = signed.token else { throw StaffError.server("Sign-in didn't return a session. Try again.", 500) }
        token = t
        var account = try await self.me()
        account.token = t
        return account
    }
    public func me() async throws -> StaffMe { try StaffMe.decode(try await call("me")) }
    public func logout() async { _ = try? await call("logout", [:]); token = nil }

    public func overview() async throws -> StaffOverview { try StaffOverview.decode(try await call("overview")) }
    public func home(_ ws: String) async throws -> StaffHome { try StaffHome.decode(try await call("home", query: ["workspace": ws])) }
    public func alerts(_ ws: String) async throws -> StaffAlerts { try StaffAlerts.decode(try await call("alerts", query: ["workspace": ws])) }
    public func reach(_ ws: String, kind: String, countywide: Bool) async throws -> StaffReach {
        try Staff.decoder().decode(StaffReach.self, from: try await call("reach", query: ["workspace": ws, "kind": kind] .merging(countywide ? ["countywide": "1"] : [:]) { a, _ in a }))
    }
    /// Sends (or, countywide, saves for a second person). Returns the server's message.
    /// geometry: the map of where it applies (AlertArea.pinsGeoJSON), or nil for none.
    public func sendAlert(_ ws: String, kind: String, title: String, message msg: String, instruction: String, severity: String, countywide: Bool, hours: Int, geometry: String? = nil) async throws -> String {
        var b: [String: Any] = ["workspace": ws, "kind": kind, "title": title, "message": msg, "instruction": instruction, "severity": severity, "countywide": countywide, "hours": hours]
        if let geometry { b["geometry"] = geometry }
        return message(try await call("alert", b))
    }
    public func confirmAlert(_ ws: String, id: Int) async throws { _ = try await call("alert-confirm", ["workspace": ws, "id": id]) }
    public func endAlert(_ ws: String, id: Int) async throws { _ = try await call("alert-end", ["workspace": ws, "id": id]) }
    public func notices(_ ws: String) async throws -> StaffPosts { try StaffPosts.decode(try await call("posts", query: ["workspace": ws, "kind": "notice"])) }
    public func saveNotice(_ ws: String, id: Int?, kind: String, title: String, text: String, eventDate: String?) async throws {
        // `kind` names the post kind for the server; the notice type travels as notice_kind.
        var b: [String: Any] = ["workspace": ws, "kind": "notice", "notice_kind": kind, "title": title, "text": text]
        if let id { b["id"] = id }
        if let eventDate, !eventDate.isEmpty { b["event_date"] = eventDate }
        _ = try await call("post", b)
    }
    public func withdrawNotice(_ ws: String, id: Int) async throws { _ = try await call("withdraw", ["workspace": ws, "kind": "notice", "id": id]) }
    /// The board dashboard; `person` picks a board member (an official's own seat by default).
    public func board(_ ws: String, person: String? = nil) async throws -> StaffBoard {
        try StaffBoard.decode(try await call("official", query: ["workspace": ws].merging(person.map { ["person": $0] } ?? [:]) { a, _ in a }))
    }
    public func flags(_ ws: String) async throws -> StaffFlags { try StaffFlags.decode(try await call("flags", query: ["workspace": ws])) }
    /// Site owner only: flags from every government.
    public func reviewFlags(status: String = "open") async throws -> StaffFlags { try StaffFlags.decode(try await call("review-flags", query: ["status": status])) }
    public func answerFlag(id: Int, status: String, reply: String) async throws { _ = try await call("review-flag", ["id": id, "status": status, "reply": reply]) }

    // Send records (records sender, or publisher and up). Files up to 3 MB go inline; bigger ones are refused by the
    // server with a note to use the web workspace.
    public static let maxInlineBytes = 3 * 1024 * 1024
    public func submissions(_ ws: String) async throws -> StaffSubmissions { try StaffSubmissions.decode(try await call("submissions", query: ["workspace": ws])) }
    public func previewRecords(_ ws: String, kind: String, filename: String, content: Data, asOf: String? = nil, printedTotal: Double? = nil) async throws -> StaffRecordPreview {
        var b: [String: Any] = ["workspace": ws, "kind": kind, "filename": filename, "content": content.base64EncodedString()]
        if let asOf, !asOf.isEmpty { b["as_of"] = asOf }
        if let printedTotal { b["printed_total"] = printedTotal }
        return try StaffRecordPreview.decode(try await call("submit-preview", b))
    }
    public func publishRecords(_ ws: String, id: String) async throws -> String { message(try await call("submit-confirm", ["workspace": ws, "id": id])) }
    public func withdrawRecords(_ ws: String, id: String) async throws { _ = try await call("submit-withdraw", ["workspace": ws, "id": id]) }
}
