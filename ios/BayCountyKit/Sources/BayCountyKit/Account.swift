import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// What's happening near one place: the answer of `/api/v1/nearby` (api/_nearby.js), which the website's My home page
/// (/account), the Monday "Your week near home" email and the app's My home screen all show.
public struct NearbyFeed: Decodable, Sendable {
    public struct Item: Decodable, Hashable, Sendable, Identifiable {
        public let kind: String
        public let title: String
        public let detail: String?
        public let date: String?
        public let url: String?
        public let miles: Double?
        public let entityId: String?
        public let level: String?
        public let allDay: Bool?
        public var id: String { kind + "|" + title + "|" + (date ?? "") }
        /// Work nearby leads with its distance; everything else with its date.
        public var leadsWithDistance: Bool { miles != nil && (date == nil || ["development", "sales-tax", "road"].contains(kind)) }
        /// A short label for the item's kind, or nil for kinds that don't need one.
        public var tag: String? {
            let t = ["evacuation": "Evacuation", "weather": "Weather", "boil-water": "Boil water", "road": "Road", "shelter": "Shelter", "utility": "Utility",
                     "agenda": "Agenda", "development": "Development", "sales-tax": "Sales tax"]
            if level == "closed" { return "Closed" }
            if level == "warning" { return "Warning" }
            return t[kind]
        }
        /// The link to open: a profile on the site for a named business or contractor, otherwise the item's own record.
        public var link: URL? {
            if let e = entityId, e.hasPrefix("business:") { return URL(string: "https://baycounty.me/profile/business/" + e.dropFirst("business:".count)) }
            return url.flatMap(URL.init(string:))
        }
    }
    public struct Section: Decodable, Sendable, Identifiable {
        public let id: String
        public let title: String
        public let count: Int?
        public let items: [Item]
        public let empty: String
    }
    public struct Pickup: Decodable, Hashable, Sendable { public let service: String; public let days: String; public let provider: String? }
    public struct Beach: Decodable, Sendable { public let flag: String; public let ripCurrentRisk: String?; public let waterTemperature: String?; public let milesToBeach: Double? }
    public struct TodayCard: Decodable, Sendable { public let trash: [Pickup]?; public let beach: Beach?; public let alerts: Int }
    public struct Gov: Decodable, Hashable, Sendable { public let govId: String; public let name: String; public let url: String }
    public struct Home: Decodable, Sendable { public let label: String?; public let address: String; public let city: String?; public let zip: String?; public let zone: String?; public let govId: String? }

    public let today: String
    public let city: String?
    public let zip: String?
    public let govId: String
    public let localGovernment: String
    public let zone: String?
    public let radiusMi: Double
    public let todayCard: TodayCard
    public let governments: [Gov]
    public let sections: [Section]
    public let note: String?
    public let home: Home?

    public var alerts: [Item] { sections.first { $0.id == "alerts" }?.items ?? [] }

    public static func decode(_ data: Data) throws -> NearbyFeed {
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase
        if let wrapped = try? d.decode(Wrapped.self, from: data) { return wrapped.data }
        return try d.decode(NearbyFeed.self, from: data)
    }
    private struct Wrapped: Decodable { let data: NearbyFeed }

    /// Month, day and time for an item's date tile. Dates without an offset are Bay County clock times and are shown
    /// as written; dates with an offset are shown in Bay County time.
    public static func when(_ s: String?) -> (month: String, day: String, time: String?)? {
        guard let s, s.count >= 10 else { return nil }
        let naive = s.range(of: #"([zZ]|[+-]\d\d:?\d\d)$"#, options: .regularExpression) == nil
        let tz = naive ? TimeZone(identifier: "UTC")! : TimeZone(identifier: "America/Chicago")!
        let date: Date?
        if s.count == 10 { date = parse(s + "T12:00:00Z") }
        else if naive { date = parse(String(s.prefix(19)) + "Z") }
        else { date = parse(s) }
        guard let d = date else { return nil }
        func f(_ fmt: String) -> String { let x = DateFormatter(); x.locale = Locale(identifier: "en_US_POSIX"); x.timeZone = tz; x.dateFormat = fmt; return x.string(from: d) }
        let time: String? = s.count > 10 ? f("EEE h:mm a").replacingOccurrences(of: ":00", with: "") : nil
        return (f("MMM").uppercased(), f("d"), time)
    }
    private static func parse(_ s: String) -> Date? {
        let a = ISO8601DateFormatter(); a.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = a.date(from: s) { return d }
        a.formatOptions = [.withInternetDateTime]
        return a.date(from: s)
    }
}

/// A resident's account (api/_account.js): who they are, their saved home and what they want to hear about.
public struct AccountMe: Decodable, Sendable {
    public struct User: Decodable, Sendable { public let email: String; public let firstName: String? }
    public struct Home: Decodable, Sendable, Equatable {
        public let label: String?
        public let address: String
        public let city: String?
        public let zip: String?
        public let lat: Double
        public let lon: Double
        public let govId: String?
        public let zone: String?
        public let parcelId: String?
        public var subtitle: String { [city, zip].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ") }

        /// The saved home as the phone's address ("825 Ohio Ave #2 32444" → street 825 OHIO AVE, unit 2), so the
        /// Today card, tax bill and trash day use the account's home on any phone the resident signs in on. Same
        /// rules as window.BCHomeLink on the site.
        public var addressMatch: AddressMatch {
            var s = address.trimmingCharacters(in: .whitespaces)
            if let r = s.range(of: #"\s+\d{5}(-\d{4})?$"#, options: .regularExpression) { s = String(s[..<r.lowerBound]) }
            var unit: String?
            if let r = s.range(of: #"\s*#\s*\S+$"#, options: .regularExpression) {
                unit = s[r].replacingOccurrences(of: "#", with: "").trimmingCharacters(in: .whitespaces).uppercased()
                s = String(s[..<r.lowerBound])
            }
            let z = zip.map { String($0.prefix(5)) }
            return AddressMatch(address: s.uppercased(), unit: unit, community: city, zip: z?.isEmpty == false ? z : nil,
                                renum: parcelId?.isEmpty == false ? parcelId : nil, point: GeoPoint(x: lon, y: lat))
        }
    }
    public struct Prefs: Decodable, Sendable, Equatable {
        public var weeklyEmail: Bool
        public var alertEmail: [String]
        public var pushTopics: [String]
        public var radiusMi: Double
        public var topics: [String]
        /// Areas whose local alerts (boil water, road closures, outages) reach this person: "all", "county" or a city id.
        /// Empty means the home's area, or all of Bay County when there is no home.
        public var alertAreas: [String]?
        /// Overnight (10 pm to 7 am) alerts arrive without sound, except evacuation orders and the most severe warnings.
        public var quietHours: Bool?
    }
    public struct Choices: Decodable, Sendable {
        public let topics: [String: String]
        public let radiusMi: [Double]
        public let pushTopics: [String: String]
        public let alertEmail: [String: String]
        public let areas: [String: String]?
    }
    public let user: User
    /// The same email's status on the realtor console's agent list ("active", "pending"), or nil: one sign-in opens both.
    public let realtor: String?
    public let home: Home?
    public let prefs: Prefs?
    public let devices: Int?
    public let choices: Choices?
    /// Only in the answer to a sign-in from the app: the session token for the Authorization header.
    public let token: String?

    public static func decode(_ data: Data) throws -> AccountMe {
        let d = JSONDecoder(); d.keyDecodingStrategy = .convertFromSnakeCase
        return try d.decode(AccountMe.self, from: data)
    }
    /// Topic keys in the order the site lists them.
    public static let topicOrder = ["meetings", "events", "projects", "notices", "food", "business"]
    /// Alert types in the order the site lists them (the server sends the labels).
    public static let pushOrder = ["evacuation", "weather", "safety", "shelters", "water", "roads", "outages", "general", "agenda"]
    public static let alertEmailOrder = ["evacuation", "weather", "safety", "shelters", "water", "roads", "outages", "general"]
    public static let areaOrder = ["all", "county", "pc", "pcb", "lh", "cw", "sp", "parker", "mb"]
    public static let radii: [Double] = [0.25, 0.5, 1, 2, 5]
    public static func radiusLabel(_ r: Double) -> String {
        switch r { case 0.25: return "A quarter mile"; case 0.5: return "Half a mile"; case 1: return "1 mile"; default: return "\(Int(r)) miles" }
    }
}

/// Talks to /api/account with the session token the app keeps in the Keychain. Every call but start/verify needs it.
public final class AccountClient: @unchecked Sendable {
    public enum AccountError: LocalizedError {
        case server(String, Int)
        case signedOut
        public var errorDescription: String? {
            switch self { case .server(let m, _): return m; case .signedOut: return "Sign in first." }
        }
    }
    private let session: URLSession
    private let base: URL
    public var token: String?
    public let platform: String

    public init(token: String?, platform: String = "ios", session: URLSession = .shared, base: URL = BayCountyClient.site) {
        self.token = token; self.platform = platform; self.session = session; self.base = base
    }

    public static func request(base: URL = BayCountyClient.site, action: String, token: String?, body: [String: Any]?) -> URLRequest {
        var c = URLComponents(url: base.appendingPathComponent("api/account"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "action", value: action)]
        var r = URLRequest(url: c.url!, timeoutInterval: 30)
        if let token { r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        if let body {
            r.httpMethod = "POST"
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = try? JSONSerialization.data(withJSONObject: body)
        }
        return r
    }

    private func call(_ action: String, _ body: [String: Any]? = nil) async throws -> Data {
        let (data, resp) = try await session.data(for: Self.request(base: base, action: action, token: token, body: body))
        let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
        if code == 401 { throw AccountError.signedOut }
        guard code == 200 else {
            let msg = (try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["error"] as? String
            throw AccountError.server(msg ?? "Something went wrong. Try again.", code)
        }
        return data
    }

    /// Emails a 6-digit code. Returns the message to show.
    public func start(email: String) async throws -> String {
        let d = try await call("start", ["email": email, "client": platform])
        return ((try? JSONSerialization.jsonObject(with: d) as? [String: Any])?["message"] as? String) ?? "Check your email for the code."
    }
    /// Checks the code and returns the account; its `token` is the new session.
    public func verify(email: String, code: String) async throws -> AccountMe {
        let me = try AccountMe.decode(try await call("verify", ["email": email, "code": code, "client": platform]))
        token = me.token
        return me
    }
    public func me() async throws -> AccountMe { try AccountMe.decode(try await call("me")) }
    public func feed() async throws -> NearbyFeed { try NearbyFeed.decode(try await call("feed")) }
    public func saveHome(address: String, lat: Double?, lon: Double?, parcel: String? = nil) async throws -> AccountMe {
        var b: [String: Any] = ["address": address]
        if let lat, let lon { b["lat"] = lat; b["lon"] = lon }
        if let parcel { b["parcel_id"] = parcel }
        return try AccountMe.decode(try await call("home", b))
    }
    public func removeHome() async throws -> AccountMe { try AccountMe.decode(try await call("home_delete", [:])) }
    public func save(prefs p: AccountMe.Prefs) async throws -> AccountMe {
        try AccountMe.decode(try await call("prefs", ["weekly_email": p.weeklyEmail, "alert_email": p.alertEmail, "push_topics": p.pushTopics, "radius_mi": p.radiusMi, "topics": p.topics,
                                                          "alert_areas": p.alertAreas ?? [], "quiet_hours": p.quietHours ?? false]))
    }
    public func save(firstName: String) async throws -> AccountMe { try AccountMe.decode(try await call("profile", ["first_name": firstName])) }
    public func linkDevice(pushToken: String, appVersion: String?) async throws {
        _ = try await call("device", ["token": pushToken, "platform": platform, "app_version": appVersion ?? ""])
    }
    public func unlinkDevice(pushToken: String) async throws {
        _ = try await call("device", ["token": pushToken, "platform": platform, "off": true])
    }
    /// Ends the session; with this phone's push token, the phone stops getting alerts too.
    public func logout(pushToken: String? = nil) async {
        _ = try? await call("logout", pushToken.map { ["token": $0] } ?? [:]); token = nil
    }
    public func deleteAccount() async throws { _ = try await call("delete_account", [:]); token = nil }
}
