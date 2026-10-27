import Foundation

/// Military and the bases (/military), from the military-installations, military-news and federal-contract-years
/// datasets. The same totals and order as site/military_page.py. The app leaves out federal-contracts (one row per
/// contract, several MB) and links to the site for single contracts.
public enum Military {
    public static let datasets = ["military-installations", "military-news", "federal-contract-years"]

    /// News stories, newest first, optionally for one base.
    public static func stories(_ rows: [Row], base: String? = nil) -> [Row] {
        rows.filter { base == nil || base == "" || $0.string("installation_id") == base }
            .sorted { ($0.string("published") ?? "") > ($1.string("published") ?? "") }
    }

    public struct Company: Identifiable, Sendable {
        public let id: String
        public let name: String
        public let url: String?
        public var total: Double
        public var defense: Double
        public var byAgency: [String: Double]
        public var topAgency: String { byAgency.max { $0.value < $1.value }?.key ?? "" }
        public var defenseShare: Int { total > 0 ? Int((100 * defense / total).rounded()) : 0 }
    }

    /// Companies by money obligated since 2016, biggest first (net cuts below zero left out, as on the site).
    public static func companies(_ years: [Row]) -> [Company] {
        var by: [String: Company] = [:]
        for r in years {
            let id = r.string("recipient_entity_id") ?? r.string("recipient") ?? ""
            let amt = r.number("obligated") ?? 0
            var c = by[id] ?? Company(id: id, name: Format.orgName(r.string("recipient") ?? ""), url: r.string("recipient_url"), total: 0, defense: 0, byAgency: [:])
            c.total += amt
            if r.bool("defense") == true { c.defense += amt }
            c.byAgency[r.string("sub_agency") ?? r.string("agency") ?? "", default: 0] += amt
            by[id] = c
        }
        return by.values.filter { $0.total > 0 }.sorted { $0.total > $1.total }
    }

    /// Money obligated per calendar year: (year, defense, other agencies).
    public static func byYear(_ years: [Row]) -> [(year: Int, defense: Double, other: Double)] {
        var d: [Int: (Double, Double)] = [:]
        for r in years {
            guard let y = r.number("year") else { continue }
            var v = d[Int(y)] ?? (0, 0)
            if r.bool("defense") == true { v.0 += r.number("obligated") ?? 0 } else { v.1 += r.number("obligated") ?? 0 }
            d[Int(y)] = v
        }
        return d.keys.sorted().map { (year: $0, defense: d[$0]!.0, other: d[$0]!.1) }
    }

    public static func total(_ years: [Row]) -> Double { years.compactMap { $0.number("obligated") }.reduce(0, +) }

    public static func defenseShare(_ years: [Row]) -> Int {
        let t = total(years)
        let d = years.filter { $0.bool("defense") == true }.compactMap { $0.number("obligated") }.reduce(0, +)
        return t > 0 ? Int((100 * d / t).rounded()) : 0
    }

    /// "Sep 17, 2026" for a story's published time.
    public static func dateLabel(_ s: String?) -> String {
        guard let s else { return "" }
        let p = DateFormatter(); p.locale = Locale(identifier: "en_US_POSIX"); p.dateFormat = "yyyy-MM-dd"
        guard let d = p.date(from: String(s.prefix(10))) else { return "" }
        p.dateFormat = "MMM d, yyyy"
        return p.string(from: d)
    }

    public static func profileURL(_ path: String?, site: String = "https://baycounty.me") -> URL? {
        guard let p = path, p.hasPrefix("/") else { return nil }
        return URL(string: site + p)
    }
}
