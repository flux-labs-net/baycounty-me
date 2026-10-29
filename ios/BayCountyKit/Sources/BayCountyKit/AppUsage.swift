import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Anonymous app usage counts (POST /api/app-usage, shown in /admin > App usage).
///
/// The app counts how often it's opened and which screens are viewed, on the phone. Once a day it sends those totals
/// with the platform, app version and whether this is the phone's first check-in ever, this month and this week, then
/// starts counting again. No device id, account, address or search is sent, so a phone can be counted but not followed.
/// The resident can turn it off (`enabled`), and nothing is counted or sent while it's off.
public final class AppUsage: @unchecked Sendable {
    public static let enabledKey = "usage.enabled"
    private static let lastKey = "usage.last", everKey = "usage.ever", opensKey = "usage.opens", screensKey = "usage.screens"

    private let defaults: UserDefaults
    private let platform: String
    private let version: String
    private let lock = NSLock()

    public init(defaults: UserDefaults = .standard, platform: String = "ios", version: String) {
        self.defaults = defaults
        self.platform = platform
        self.version = version
    }

    /// On unless the resident turned it off.
    public var enabled: Bool {
        get { defaults.object(forKey: Self.enabledKey) as? Bool ?? true }
        set {
            defaults.set(newValue, forKey: Self.enabledKey)
            if !newValue { lock.lock(); defaults.removeObject(forKey: Self.opensKey); defaults.removeObject(forKey: Self.screensKey); lock.unlock() }
        }
    }

    /// The app came to the front.
    public func opened() {
        guard enabled else { return }
        lock.lock(); defer { lock.unlock() }
        defaults.set(defaults.integer(forKey: Self.opensKey) + 1, forKey: Self.opensKey)
    }

    /// A screen was shown. `name` is a short screen name such as "restaurants" or "dataset/votes".
    public func viewed(_ name: String) {
        guard enabled, let name = Self.screenName(name) else { return }
        lock.lock(); defer { lock.unlock() }
        var s = defaults.dictionary(forKey: Self.screensKey) as? [String: Int] ?? [:]
        guard s[name] != nil || s.count < 120 else { return }
        s[name, default: 0] += 1
        defaults.set(s, forKey: Self.screensKey)
    }

    /// Lowercase letters, digits and `:/_-`, at most 60 characters, or nil.
    public static func screenName(_ raw: String) -> String? {
        let n = raw.lowercased()
        guard !n.isEmpty, n.count <= 60, let f = n.first, f.isLetter || f.isNumber,
              n.allSatisfy({ ($0.isASCII && ($0.isLetter || $0.isNumber)) || ":/_-".contains($0) }) else { return nil }
        return n
    }

    /// Today's check-in body, or nil when it's off or this phone already checked in today (in its own time zone).
    public func checkIn(now: Date = Date(), calendar: Calendar = .current) -> [String: Any]? {
        guard enabled else { return nil }
        lock.lock(); defer { lock.unlock() }
        var cal = calendar
        cal.firstWeekday = 2  // weeks start on Monday, like the admin page
        let today = Self.dayString(now, cal)
        let last = defaults.string(forKey: Self.lastKey)
        if last == today { return nil }
        let lastDate = last.flatMap { Self.date($0, cal) }
        let sameMonth = lastDate.map { cal.isDate($0, equalTo: now, toGranularity: .month) } ?? false
        let sameWeek = lastDate.map { cal.isDate($0, equalTo: now, toGranularity: .weekOfYear) } ?? false
        return ["platform": platform, "version": version, "new": !defaults.bool(forKey: Self.everKey),
                "month": !sameMonth, "week": !sameWeek, "opens": max(1, defaults.integer(forKey: Self.opensKey)),
                "screens": defaults.dictionary(forKey: Self.screensKey) as? [String: Int] ?? [:]]
    }

    /// The check-in went through: remember the day and start counting again.
    public func sent(now: Date = Date(), calendar: Calendar = .current) {
        lock.lock(); defer { lock.unlock() }
        defaults.set(Self.dayString(now, calendar), forKey: Self.lastKey)
        defaults.set(true, forKey: Self.everKey)
        defaults.removeObject(forKey: Self.opensKey)
        defaults.removeObject(forKey: Self.screensKey)
    }

    /// Sends today's check-in if one is due. Errors are ignored; the next launch tries again.
    public func send(baseURL: URL = BayCountyClient.site, session: URLSession = .shared) async {
        guard let body = checkIn(), let data = try? JSONSerialization.data(withJSONObject: body) else { return }
        var req = URLRequest(url: baseURL.appendingPathComponent("api/app-usage"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = data
        req.timeoutInterval = 15
        guard let (_, resp) = try? await session.data(for: req), let code = (resp as? HTTPURLResponse)?.statusCode,
              (200..<300).contains(code) else { return }
        sent()
    }

    private static func dayString(_ d: Date, _ cal: Calendar) -> String {
        let c = cal.dateComponents([.year, .month, .day], from: d)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    private static func date(_ s: String, _ cal: Calendar) -> Date? {
        let p = s.split(separator: "-").compactMap { Int($0) }
        guard p.count == 3 else { return nil }
        return cal.date(from: DateComponents(year: p[0], month: p[1], day: p[2], hour: 12))
    }
}

/// Links into BayCounty.me opened from the app carry `utm_source=ios-app` (or `android-app`) and `utm_medium=app`,
/// so the website's analytics shows them as app traffic instead of "Unknown".
public enum AppLinks {
    public static func tagged(_ url: URL, source: String = "ios-app") -> URL {
        let host = url.host?.lowercased() ?? ""
        guard host == "baycounty.me" || host == "www.baycounty.me",
              var c = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return url }
        var items = c.queryItems ?? []
        guard !items.contains(where: { $0.name == "utm_source" }) else { return url }
        items += [URLQueryItem(name: "utm_source", value: source), URLQueryItem(name: "utm_medium", value: "app")]
        c.queryItems = items
        return c.url ?? url
    }
}
