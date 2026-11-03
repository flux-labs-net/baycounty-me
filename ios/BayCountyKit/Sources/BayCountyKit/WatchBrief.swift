import Foundation

/// What the watch apps show: active alerts first, then the saved home's trash day, the beach flag and the next
/// meeting, plus the short lines the watch face complications use. Built from the same live feed and rules as the
/// phone's Home tab (Emergency, TodayBrief). Mirrored in android/kit WatchBrief.kt.
public enum WatchBrief {
    /// One active alert, already worded for a small screen.
    public struct Alert: Hashable, Sendable, Identifiable {
        public let id: String
        public let kind: String
        /// "Boil-water notice", "Road closure" ...
        public let label: String
        public let symbol: String
        public let title: String
        public let summary: String
        public let source: String
        /// "Oct 29, 3:49 PM"
        public let posted: String
        public let severity: String
        /// Posted by the saved home's city (or the county for a home outside city limits).
        public let nearHome: Bool
    }

    public struct Brief: Sendable {
        /// "Lynn Haven", or "Bay County" without a saved home.
        public let place: String
        public let hasHome: Bool
        /// False when the live alert feed couldn't be reached.
        public let alertsLoaded: Bool
        public let headline: String
        public let alerts: [Alert]
        /// The trash card, only on pickup day or from 4 p.m. the day before (TodayBrief.trashCard).
        public let trash: TodayBrief.Card?
        /// "Next pickup Friday" on the other days, when the home has a set garbage day.
        public let nextPickup: String?
        public let beach: TodayBrief.Card
        public let meeting: TodayBrief.Card

        public var alertCount: Int { alerts.count }
        public var alertTitle: String {
            guard alertsLoaded else { return "Alerts didn't load" }
            return alertCount == 0 ? "No active alerts" : "\(alertCount) active alert\(alertCount == 1 ? "" : "s")"
        }

        /// The one line under the time on a watch face: alerts first, then a trash reminder, else all clear.
        public var inline: String {
            if alertsLoaded, alertCount > 0 { return alertTitle }
            if let t = trash { return t.title }
            return alertsLoaded ? "No active alerts" : "BayCounty.me"
        }

        /// The small round complication: the alert count, or "0".
        public var circular: String { alertsLoaded ? String(alertCount) : "–" }

        /// The rectangular complication's second line: the trash reminder, else the beach flag.
        public var rectangularDetail: String { trash?.title ?? beach.title }
    }

    /// `feed` is /api/v1/emergency (nil when it couldn't load), `utilities` the saved home's /api/v1/utilities answer.
    public static func make(feed: Emergency.Feed?, utilities: UtilityLookup?, beach: [Row], meetings: [Meeting],
                            now: Date = Date(), limit: Int = 12) -> Brief {
        let area = utilities?.area
        let active = Emergency.sorted((feed?.notices ?? []).filter {
            ($0.string("status") ?? "active") == "active" && ($0.string("same_as") ?? "").isEmpty
        })
        let alerts = active.prefix(limit).enumerated().map { i, n in
            let kind = n.string("kind") ?? "other"
            return Alert(id: n.string("notice_id") ?? "n\(i)", kind: kind, label: Emergency.label(kind), symbol: Emergency.symbol(kind),
                         title: n.string("title") ?? Emergency.label(kind),
                         summary: clean(n.first(["summary", "instruction"]) ?? ""),
                         source: n.string("source") ?? "", posted: Emergency.posted(n), severity: n.string("severity") ?? "",
                         nearHome: area != nil && n.string("gov_id") == area)
        }
        // Meetings of the home's own government first; the whole county when it has none coming up.
        let own = area.map { a in meetings.filter { $0.govID == a } } ?? []
        let meeting = TodayBrief.meetingCard(Meeting.upcoming(own, now: now).isEmpty ? meetings : own, now: now)
        let trash = TodayBrief.trashCard(utilities, now: now)
        var next: String?
        if trash == nil, let days = TodayBrief.trashDays(utilities) {
            var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!
            if let d = PickupDays.next(days, from: now, calendar: c) {
                next = "Next pickup " + PickupDays.names[c.component(.weekday, from: d) - 1]
            }
        }
        let place = utilities.map { $0.area == "county" ? "Bay County" : $0.areaName } ?? "Bay County"
        return Brief(place: place, hasHome: utilities != nil, alertsLoaded: feed != nil,
                     headline: feed?.headline ?? "Couldn't reach BayCounty.me. Check again in a minute.",
                     alerts: Array(alerts), trash: trash, nextPickup: next,
                     beach: TodayBrief.beachCard(beach), meeting: meeting)
    }

    /// Collapses runs of spaces and blank lines so a summary reads as one paragraph on a watch.
    static func clean(_ s: String) -> String {
        s.replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression).trimmingCharacters(in: .whitespaces)
    }

    // MARK: - The saved home, sent from the phone

    /// The only thing the phone sends the watch: the saved home's map point. The watch looks up the city and trash
    /// day itself from /api/v1/utilities, like the phone does, and nothing else about the resident leaves the phone.
    public struct Home: Codable, Equatable, Sendable {
        public let lat: Double
        public let lon: Double
        public init(lat: Double, lon: Double) { self.lat = lat; self.lon = lon }
        public var point: GeoPoint { GeoPoint(x: lon, y: lat) }

        /// The phone-to-watch message (WatchConnectivity application context / Wear data item). No home = cleared.
        public static func message(_ home: Home?) -> [String: Any] {
            guard let home else { return ["home": false] }
            return ["home": true, "lat": home.lat, "lon": home.lon]
        }

        /// Reads a message. `.some(nil)` means the phone has no saved home; nil means it isn't a home message.
        public static func from(message m: [String: Any]) -> Home?? {
            guard let has = m["home"] as? Bool else { return nil }
            guard has, let lat = m["lat"] as? Double, let lon = m["lon"] as? Double else { return .some(nil) }
            return .some(Home(lat: lat, lon: lon))
        }
    }
}
