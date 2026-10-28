import Foundation

/// Volunteer and nonprofit needs board (/volunteer), from the volunteer-needs and volunteer-orgs datasets. The same
/// causes, order, "still open" rule and date labels as site/volunteer_page.py and the Android `Volunteer`.
public enum Volunteer {
    public static let datasets = ["volunteer-needs", "volunteer-orgs"]

    /// Plain causes in the order the site's filter shows them (site/volunteer_data.py CAUSES).
    public static let causes = [
        "Kids and mentoring", "Schools and reading", "Food and basic needs", "Health and hospice", "Seniors",
        "Disaster and emergency", "Housing and neighborhoods", "Animals", "Arts and culture", "Environment",
        "Veterans and service clubs", "Sports and recreation", "Events and fundraisers", "Faith", "Other",
    ]

    /// The causes that appear in either list, in filter order.
    public static func causes(in needs: [Row], _ orgs: [Row]) -> [String] {
        let used = Set((needs + orgs).compactMap { $0.string("cause") })
        return causes.filter { used.contains($0) }
    }

    private static func rank(_ c: String?) -> Int { causes.firstIndex(of: c ?? "") ?? 99 }

    /// Needs still open on `today` (yyyy-MM-dd): dated ones soonest first, then ongoing, by cause and organization.
    public static func open(_ needs: [Row], today: String, cause: String? = nil, nonprofit: String? = nil) -> [Row] {
        needs.filter { r in
            let until = r.string("closes") ?? r.string("ends") ?? "9999"
            return until >= today && (cause == nil || r.string("cause") == cause) && (nonprofit == nil || r.string("nonprofit_id") == nonprofit)
        }
        .sorted { a, b in
            let ka = (a.string("starts") == nil ? 1 : 0, a.string("starts") ?? "", rank(a.string("cause")), a.string("organization") ?? "")
            let kb = (b.string("starts") == nil ? 1 : 0, b.string("starts") ?? "", rank(b.string("cause")), b.string("organization") ?? "")
            return ka < kb
        }
    }

    /// Nonprofits for one cause (or all): open needs first, then by volunteers reported.
    public static func orgs(_ rows: [Row], cause: String? = nil) -> [Row] {
        rows.filter { cause == nil || $0.string("cause") == cause }
            .sorted { a, b in
                let ka = (-(a.number("open_needs") ?? 0), -(a.number("volunteers_reported") ?? 0), a.string("name") ?? "")
                let kb = (-(b.number("open_needs") ?? 0), -(b.number("volunteers_reported") ?? 0), b.string("name") ?? "")
                return ka < kb
            }
    }

    static func day(_ s: String?) -> Date? {
        guard let s else { return nil }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "yyyy-MM-dd"
        return f.date(from: String(s.prefix(10)))
    }

    /// "Ongoing", "Multiple shifts", "Thu, Dec 3" or "Nov 1 to Nov 8".
    public static func when(_ r: Row) -> String {
        if r.string("schedule") == "Shifts" { return "Multiple shifts" }
        guard let s = day(r.string("starts")) else { return "Ongoing" }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago")
        if let e = day(r.string("ends")), e != s {
            f.dateFormat = "MMM d"
            return "\(f.string(from: s)) to \(f.string(from: e))"
        }
        f.dateFormat = "EEE, MMM d"
        return f.string(from: s)
    }

    /// Where a need happens: its city, "Remote or from home", or "Location varies".
    public static func whereLabel(_ r: Row) -> String {
        r.string("city") ?? (r.bool("remote") == true ? "Remote or from home" : "Location varies")
    }

    /// The organization's profile page on the site, when the board's name matched a local nonprofit.
    public static func profileURL(_ row: Row, _ key: String, site: String = "https://baycounty.me") -> URL? {
        guard let p = row.string(key), p.hasPrefix("/") else { return nil }
        return URL(string: site + p)
    }
}
