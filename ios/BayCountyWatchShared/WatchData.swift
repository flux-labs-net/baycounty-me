import Foundation
import BayCountyKit

/// Loads the watch's brief. Shared by the watch app and its watch face complications, which both read the saved
/// home the phone sent (kept in the app group so the complications can see it).
enum WatchData {
    static let appGroup = "group.me.baycounty.app"
    private static var defaults: UserDefaults { UserDefaults(suiteName: appGroup) ?? .standard }

    /// The saved home's map point, from the phone. Nil until the resident saves a home on the phone.
    static var home: WatchBrief.Home? {
        get { defaults.data(forKey: "home").flatMap { try? JSONDecoder().decode(WatchBrief.Home.self, from: $0) } }
        set {
            if let newValue, let d = try? JSONEncoder().encode(newValue) { defaults.set(d, forKey: "home") }
            else { defaults.removeObject(forKey: "home") }
        }
    }

    /// Screenshots: `-demo` shows a made-up day (no network), `-demo-clear` the same day with no alerts.
    static var demo: Bool { ProcessInfo.processInfo.arguments.contains { $0.hasPrefix("-demo") } }

    static func load() async -> WatchBrief.Brief {
        if demo { return demoBrief(clear: ProcessInfo.processInfo.arguments.contains("-demo-clear")) }
        let client = BayCountyClient()
        let home = self.home
        async let feed = fetchFeed(client)
        async let utilities = fetchUtilities(client, home)
        async let beach = fetchRows(client, "beach-conditions")
        async let meetings = fetchMeetings(client)
        return WatchBrief.make(feed: await feed, utilities: await utilities, beach: await beach, meetings: await meetings)
    }

    private static func fetchFeed(_ c: BayCountyClient) async -> Emergency.Feed? {
        guard let r = try? await c.get(Emergency.feedPath), r.freshness == .live else { return nil }
        return try? Emergency.parseFeed(r.data)
    }

    private static func fetchUtilities(_ c: BayCountyClient, _ home: WatchBrief.Home?) async -> UtilityLookup? {
        guard let home else { return nil }
        return try? await c.utilities(at: home.point)
    }

    private static func fetchRows(_ c: BayCountyClient, _ id: String) async -> [Row] {
        (try? await c.rows(datasetID: id).0) ?? []
    }

    private static func fetchMeetings(_ c: BayCountyClient) async -> [Meeting] {
        (try? await c.meetings().0) ?? []
    }

    // MARK: - Made-up day for screenshots and previews

    static func demoBrief(clear: Bool = false) -> WatchBrief.Brief {
        let feed = #"""
        {"headline":"No weather warnings or evacuation orders right now.","notices":[
         {"notice_id":"d1","kind":"boil-water","gov_id":"lh","title":"Boil-water notice for the 900 block of Sample Ave","summary":"Bring water to a rolling boil for one minute before drinking or cooking until the city lifts the notice.","source":"City of Lynn Haven","severity":"moderate","issued":"2026-10-30T13:40:00Z","status":"active"},
         {"notice_id":"d2","kind":"road","gov_id":"county","title":"Example Rd closed between 1st and 3rd St","summary":"Drainage work. Use Sample Blvd instead.","source":"Bay County","severity":"minor","issued":"2026-10-30T11:05:00Z","status":"active"}
        ]}
        """#
        let utilities = #"""
        {"data":{"area":"lh","area_name":"Lynn Haven","services":[],"rates":[],"holidays":[],
         "pickup":[{"service":"garbage","service_label":"Garbage","provider":"City of Lynn Haven","days":"Monday, Thursday"}]}}
        """#
        let beach = Row(id: 0, values: ["kind": .string("forecast"), "sort_order": .number(0),
                                        "flag_color": .string("Yellow"), "rip_current_risk": .string("Moderate")])
        let meeting = Meeting(row: Row(id: 0, values: ["board": .string("lh-commission"), "gov_id": .string("lh"),
                                                       "start": .string("2026-11-10T17:00:00-06:00")]))
        var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "America/Chicago")!
        let thursday = c.date(from: DateComponents(year: 2026, month: 10, day: 29, hour: 8, minute: 10))!
        let f = clear ? #"{"headline":"No weather warnings or evacuation orders right now.","notices":[]}"# : feed
        return WatchBrief.make(feed: try? Emergency.parseFeed(Data(f.utf8)), utilities: try? UtilityLookup.decode(Data(utilities.utf8)),
                               beach: [beach], meetings: [meeting], now: thursday)
    }
}
