import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Who provides water, sewer, power, gas and garbage at one address, and its trash pickup days.
/// The same answer as `/api/v1/utilities` (api/_utilities.js), which the site's /utilities page and the address card use.
/// The address isn't logged by the API, and the app doesn't cache lookups.
public struct UtilityLookup: Decodable, Sendable {
    public struct Provider: Decodable, Hashable, Sendable {
        public let provider: String
        public let entityId: String?
        public let providerKind: String?
        public let phone: String?
        public let website: String?
        public let outageUrl: String?
        public let notes: String?
        public let sourceUrl: String?
    }
    public struct Service: Decodable, Hashable, Sendable {
        public let service: String
        public let serviceLabel: String
        public let providers: [Provider]
    }
    public struct Pickup: Decodable, Hashable, Sendable {
        public let service: String
        public let serviceLabel: String
        public let provider: String
        public let zone: String?
        public let zoneLabel: String?
        public let days: String?
        public let zoneArea: String?
        public let rule: String?
        public let notes: String?
        public let fromMap: Bool?
        /// "Friday (route ROUTE-E)"-style label: the zone only when it adds something to the days.
        public var zoneText: String? {
            guard let z = zone, !z.isEmpty, z != days else { return nil }
            return z.allSatisfy(\.isNumber) ? "\(zoneLabel ?? "zone") \(z)" : z
        }
    }
    public struct Holiday: Decodable, Hashable, Sendable {
        public let provider: String?
        public let holiday: String
        public let whenObserved: String?
        public let garbage: String?
        public let yardWaste: String?
    }
    public struct Rate: Decodable, Hashable, Sendable {
        public let provider: String?
        public let service: String?
        public let serviceLabel: String?
        public let charge: String?
        public let amount: Double?
        public let unit: String?
        public let notes: String?
    }
    public let area: String
    public let areaName: String
    public let services: [Service]
    public let pickup: [Pickup]
    public let holidays: [Holiday]
    public let rates: [Rate]
    public let note: String?

    /// The typical monthly water and sewer bill at 5,000 gallons.
    public var typicalBill: Double? { rates.first { $0.service == "bill" }?.amount }
    /// Services with no trash-day card (garbage, yard waste and bulk providers show on their pickup card).
    public var otherServices: [Service] { services.filter { s in !pickup.contains { $0.service == s.service } } }
    public func provider(for pickup: Pickup) -> Provider? { services.first { $0.service == pickup.service }?.providers.first }

    public static func decode(_ data: Data) throws -> UtilityLookup {
        struct Envelope: Decodable { let data: UtilityLookup }
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return try d.decode(Envelope.self, from: data).data
    }
}

public enum PickupDays {
    static let names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

    /// Weekdays named in "Monday, Thursday" (Sunday = 1, as Calendar counts them).
    public static func weekdays(_ days: String?) -> [Int] {
        guard let days else { return [] }
        return names.enumerated().compactMap { i, n in days.range(of: "\\b\(n)\\b", options: .regularExpression) != nil ? i + 1 : nil }
    }

    /// The next date one of these weekdays comes up, today included.
    public static func next(_ days: String?, from date: Date = Date(), calendar: Calendar = .current) -> Date? {
        let want = weekdays(days)
        guard !want.isEmpty else { return nil }
        let start = calendar.startOfDay(for: date)
        for i in 0..<8 {
            guard let d = calendar.date(byAdding: .day, value: i, to: start) else { continue }
            if want.contains(calendar.component(.weekday, from: d)) { return d }
        }
        return nil
    }
}

extension BayCountyClient {
    /// One address's utilities and pickup days from `/api/v1/utilities`. Not cached.
    public func utilities(at point: GeoPoint, session: URLSession = .shared) async throws -> UtilityLookup {
        var c = URLComponents(url: BayCountyClient.site.appendingPathComponent("api/v1/utilities"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "lat", value: String(format: "%.6f", point.y)), URLQueryItem(name: "lon", value: String(format: "%.6f", point.x))]
        var req = URLRequest(url: c.url!, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 25)
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await session.data(for: req)
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else { throw ClientError.http(code) }
        return try UtilityLookup.decode(data)
    }
}
