import Foundation

/// Restaurant inspections (/restaurants and /restaurants/<name>-<license>), from the restaurants dataset (one row per
/// license, with its latest result and recent_results) and, for one restaurant, its rows in restaurant-inspections read
/// from /api/v1 by license number. Same order, filters and wording as site/restaurants_page.py. Same as the Android kit.
public enum Restaurants {
    public static let datasets = ["restaurants"]

    /// The list's filters, the same chips as the site.
    public enum Show: String, CaseIterable, Sendable {
        case latest = "", follow, closed, new, gone
        public var label: String {
            switch self {
            case .latest: return "Latest inspected"
            case .follow: return "Needs a follow-up"
            case .closed: return "Closed this year"
            case .new: return "New this year"
            case .gone: return "No longer licensed"
            }
        }
    }

    /// Result words short enough for a list row (site SHORT).
    public static let short: [String: String] = [
        "Met inspection standards": "Met standards", "Warning, follow-up visit set": "Warning", "Follow-up visit: fixed": "Fixed on follow-up",
        "Follow-up visit: more time given": "More time given", "Fine recommended (administrative complaint)": "Fine recommended",
        "Follow-up visit: not fixed, fine recommended": "Fine recommended", "Follow-up after complaint: fixed": "Fixed",
        "Follow-up after complaint: not fixed": "Not fixed", "Follow-up after complaint: more time given": "More time given",
        "Referred for an administrative decision": "Referred", "Ordered closed (emergency order)": "Closed by the state",
        "Allowed to reopen": "Reopened", "Stayed closed: not fixed": "Still closed", "Stayed closed: more time given": "Still closed",
    ]

    public static func shortResult(_ result: String?) -> String? {
        guard let result, !result.isEmpty else { return nil }
        return short[result] ?? result
    }

    /// How a result level is drawn: good, warning or bad (ok, warning, fine/closed).
    public enum Tone: Sendable { case good, warning, bad, none }

    public static func tone(_ level: String?) -> Tone {
        switch level {
        case "ok": return .good
        case "warning": return .warning
        case "fine", "closed": return .bad
        default: return .none
        }
    }

    /// The last six inspections' levels, oldest to newest, padded with "" at the start (no visit) to six.
    public static func strip(_ recent: String?) -> [String] {
        let lv = Array((recent ?? "").split(separator: " ").map(String.init).prefix(6).reversed())
        return Array(repeating: "", count: max(0, 6 - lv.count)) + lv
    }

    /// The day a year before `today` (yyyy-MM-dd), the start of "this year" on the chips.
    public static func yearAgo(_ today: String) -> String {
        guard let d = day.date(from: today), let y = Calendar(identifier: .gregorian).date(byAdding: .day, value: -365, to: d) else { return today }
        return day.string(from: y)
    }

    /// Latest inspected first, filtered like the site's list. A search looks at every license, licensed now or not.
    public static func list(_ rows: [Row], query: String = "", city: String? = nil, show: Show = .latest, today: String) -> [Row] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased(), ya = yearAgo(today)
        return rows.filter { r in
            let now = r.bool("licensed_now") == true
            if !q.isEmpty {
                let hay = [r.string("business_name"), r.string("licensee"), r.string("address")].compactMap { $0 }.joined(separator: " ").lowercased()
                if !hay.contains(q) { return false }
            }
            if let city, !city.isEmpty, r.string("city") != city { return false }
            switch show {
            case .latest: return q.isEmpty ? now : true
            case .follow: return now && ["warning", "fine", "closed"].contains(r.string("last_result_level") ?? "")
            case .closed: return (r.string("last_closure") ?? "") >= ya
            case .new: return now && (r.string("opened") ?? "") >= ya
            case .gone: return !now
            }
        }.sorted { a, b in
            let x = a.string("last_inspection") ?? "", y = b.string("last_inspection") ?? ""
            return x != y ? x > y : (a.string("business_name") ?? "") > (b.string("business_name") ?? "")
        }
    }

    /// Cities with a licensed place, the busiest first.
    public static func cities(_ rows: [Row]) -> [String] {
        var n: [String: Int] = [:]
        for r in rows where r.bool("licensed_now") == true { if let c = r.string("city") { n[c, default: 0] += 1 } }
        return n.keys.sorted { n[$0]! != n[$1]! ? n[$0]! > n[$1]! : $0 < $1 }
    }

    /// Places last inspected in the 7 days ending on the newest inspection date: (start day, count).
    public static func week(_ rows: [Row]) -> (start: String, places: Int) {
        guard let latest = rows.compactMap({ $0.string("last_inspection") }).max(), let d = day.date(from: latest),
              let s = Calendar(identifier: .gregorian).date(byAdding: .day, value: -6, to: d) else { return ("", 0) }
        let start = day.string(from: s)
        return (start, rows.filter { ($0.string("last_inspection") ?? "") >= start }.count)
    }

    /// One plain paragraph about a restaurant, from its row (the site's page says the same from every inspection).
    public static func summary(_ r: Row) -> String {
        let name = r.string("business_name") ?? "This place"
        guard let last = r.string("last_inspection"), let res = r.string("last_result") else {
            return "\(name) has no inspections on file since 2016 yet. New licenses are inspected soon after they open."
        }
        var out = ["Last inspected \(dateLabel(last)): \(res.prefix(1).lowercased() + res.dropFirst())."]
        let closures = Int(r.number("closures") ?? 0)
        if closures > 0, let c = r.string("last_closure") {
            out.append("The state has closed it \(times(closures)) since 2016, most recently \(dateLabel(c)).")
        } else {
            out.append("It has never been closed by the state since 2016.")
        }
        let n = Int(r.number("inspections") ?? 0)
        out.append("\(n) inspection\(n == 1 ? "" : "s") on file.")
        return out.joined(separator: " ")
    }

    static func times(_ n: Int) -> String { n == 1 ? "once" : n == 2 ? "twice" : "\(n) times" }

    /// The API query for one license's inspections, newest first.
    public static func inspectionsPath(_ license: String) -> String {
        let l = license.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? license
        return "/api/v1/datasets/restaurant-inspections?license_number=\(l)&sort=-date&limit=1000"
    }

    /// One license's inspections, newest first (the API already filters and sorts; a full download is filtered here).
    public static func inspections(_ rows: [Row], license: String) -> [Row] {
        rows.filter { ($0.string("license_number") ?? "").trimmingLeadingZeros == license.trimmingLeadingZeros }
            .sorted { a, b in
                let x = a.string("date") ?? "", y = b.string("date") ?? ""
                return x != y ? x > y : (a.number("visit_number") ?? 1) > (b.number("visit_number") ?? 1)
            }
    }

    /// "Follow-up visit" for a second visit, otherwise the plain inspection type.
    public static func visitLabel(_ r: Row) -> String {
        if (r.number("visit_number") ?? 1) > 1 { return "Follow-up visit" }
        return (r.string("inspection_type") ?? "").replacingOccurrences(of: " - Food", with: "")
            .replacingOccurrences(of: "Food-Licensing Inspection", with: "Licensing inspection")
            .replacingOccurrences(of: "Complaint Full", with: "Complaint").replacingOccurrences(of: "Complaint Partial", with: "Complaint (partial)")
    }

    /// "2 high priority, 1 intermediate, 3 basic" or "No violations".
    public static func counts(_ r: Row) -> String {
        let h = Int(r.number("high_priority") ?? 0), i = Int(r.number("intermediate") ?? 0), b = Int(r.number("basic") ?? 0)
        return h + i + b == 0 ? "No violations" : "\(h) high priority, \(i) intermediate, \(b) basic"
    }

    public static func dateLabel(_ s: String?) -> String {
        guard let s, let d = day.date(from: String(s.prefix(10))) else { return "" }
        return label.string(from: d)
    }

    public static func pageURL(_ r: Row, site: String = "https://baycounty.me") -> URL? {
        guard let p = r.string("page_url"), p.hasPrefix("/") else { return URL(string: site + "/restaurants") }
        return URL(string: site + p)
    }

    static let day: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "yyyy-MM-dd"; return f
    }()
    static let label: DateFormatter = {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC"); f.dateFormat = "MMM d, yyyy"; return f
    }()
}

extension String {
    var trimmingLeadingZeros: String { String(drop { $0 == "0" }) }
}

extension Row {
    /// Rows from an /api/v1/datasets response ({data: [...]}) or a plain download ([...]).
    public static func decodeRows(_ data: Data) throws -> [Row] {
        if let wrapped = try? JSONDecoder().decode([String: JSONValue].self, from: data), let list = wrapped["data"]?.arrayValue {
            return list.enumerated().compactMap { i, v in v.objectValue.map { Row(id: i, values: $0) } }
        }
        return try decodeList(data)
    }
}
