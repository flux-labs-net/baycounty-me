import Foundation

/// Where records overlap (/connections/overlaps): the headline numbers and the top few of each overlap, and the live
/// parts from GET /api/v1/overlaps. Same counts and order as site/overlaps_page.py. A row puts two public records side by
/// side; it is not a finding. Individual donors are never named.
public enum Overlaps {
    public static let datasets = ["donor-votes", "vote-mentions", "agenda-parties", "bid-trail", "emergency-purchase-donors",
                                  "shared-owner-vendors", "chamber-overlaps", "development-companies", "campaign-results"]
    public static let livePath = "/api/v1/overlaps"

    /// One overlap: a headline, the top three, and the dataset that holds every row.
    public struct Card: Identifiable, Sendable {
        public var id: String { dataset }
        public let title: String
        public let stat: String
        public let items: [String]
        public let dataset: String
        public let symbol: String
    }

    static func money(_ n: Double?) -> String { Format.compactMoney(n ?? 0) }

    /// Contested races (two or more candidates with a report and a result): (races, races the top fundraiser won).
    public static func races(_ results: [Row]) -> (contested: Int, topWon: Int) {
        var by: [String: [Row]] = [:]
        for r in results { by["\(r.string("election_date") ?? "")|\(r.string("office") ?? "")", default: []].append(r) }
        let contested = by.values.filter { $0.count > 1 }
        let won = contested.filter { rs in rs.contains { $0.number("money_rank") == 1 && $0.number("vote_rank") == 1 } }.count
        return (contested.count, won)
    }

    public struct Headline: Sendable {
        public let donorVotes: Int, pairs: Int, mentionVotes: Int, mentionEntities: Int, contested: Int, topWon: Int, emergencyFromDonors: Int, emergency: Int
    }

    public static func headline(_ rows: [String: [Row]]) -> Headline {
        let dv = rows["donor-votes"] ?? [], vm = rows["vote-mentions"] ?? [], ep = rows["emergency-purchase-donors"] ?? []
        let pairs = Set(dv.map { "\($0.string("member_id") ?? "")|\($0.string("company_id") ?? "")" }).count
        let r = races(rows["campaign-results"] ?? [])
        return Headline(donorVotes: Set(dv.compactMap { $0.string("vote_id") }).count, pairs: pairs,
                        mentionVotes: Set(vm.compactMap { $0.string("vote_id") }).count, mentionEntities: Set(vm.compactMap { $0.string("entity_id") }).count,
                        contested: r.contested, topWon: r.topWon,
                        emergencyFromDonors: ep.filter { $0.bool("gave_to_officials_here") == true }.count, emergency: ep.count)
    }

    /// Keys of a dictionary of sets, biggest set first.
    private static func top<K: Hashable>(_ d: [K: Set<String>], _ n: Int = 3) -> [(K, Int)] {
        d.map { ($0.key, $0.value.count) }.sorted { $0.1 > $1.1 }.prefix(n).map { $0 }
    }

    public static func cards(_ rows: [String: [Row]]) -> [Card] {
        let h = headline(rows)
        let dv = rows["donor-votes"] ?? [], ap = (rows["agenda-parties"] ?? []).filter { $0.string("entity_id") != nil && $0.string("entity_kind") != "gov" }
        let bt = rows["bid-trail"] ?? [], ep = rows["emergency-purchase-donors"] ?? [], so = rows["shared-owner-vendors"] ?? []
        let ch = rows["chamber-overlaps"] ?? [], dc = rows["development-companies"] ?? []

        var pairs: [String: Set<String>] = [:]
        for r in dv { pairs["\(r.string("member") ?? "") on \(r.string("company") ?? "")", default: []].insert(r.string("vote_id") ?? "") }
        var named: [String: Set<String>] = [:]
        for r in ap { named[r.string("entity_name") ?? r.string("party") ?? "", default: []].insert(r.string("meeting_date") ?? "") }
        var notices: [String] = [], seen = Set<String>()
        for r in bt { if let id = r.string("notice_id"), seen.insert(id).inserted { notices.append(r.string("notice_title") ?? r.string("reference") ?? "") } }
        var groups: [String: [Row]] = [:]
        for r in so { groups[r.string("group_id") ?? "", default: []].append(r) }
        let topGroups = groups.values.sorted { a, b in a.compactMap { $0.number("paid_by_this_government") }.reduce(0, +) > b.compactMap { $0.number("paid_by_this_government") }.reduce(0, +) }
        let chamberWeight = { (r: Row) in (r.number("organization_paid_by_governments") ?? 0) + (r.number("organization_gave_to_campaigns") ?? 0) }
        let gave = ep.filter { $0.bool("gave_to_officials_here") == true }.sorted { ($0.number("amount") ?? 0) > ($1.number("amount") ?? 0) }

        return [
            Card(title: "Votes naming a member's donor", stat: "\(Format.number(Double(h.donorVotes))) votes · \(h.pairs) official and company pairs",
                 items: top(pairs).map { "\($0.0): \($0.1) votes" }, dataset: "donor-votes", symbol: "link"),
            Card(title: "Companies on agendas", stat: "\(ap.count) agenda items name a company or group",
                 items: top(named).map { "\($0.0): \($0.1) meetings" }, dataset: "agenda-parties", symbol: "list.bullet.rectangle"),
            Card(title: "Bids from notice to award", stat: "\(seen.count) bids followed by number", items: Array(notices.prefix(3)),
                 dataset: "bid-trail", symbol: "doc.text.magnifyingglass"),
            Card(title: "Emergency purchases from donors", stat: "\(h.emergencyFromDonors) of \(h.emergency) bought from a company that gave",
                 items: gave.prefix(3).map { "\($0.string("vendor") ?? ""): \(money($0.number("amount")))" }, dataset: "emergency-purchase-donors", symbol: "exclamationmark.triangle"),
            Card(title: "Shared officers among vendors", stat: "\(groups.count) groups paid by one government",
                 items: topGroups.prefix(3).map { "\($0[0].string("officer") ?? ""): \($0.count) companies" }, dataset: "shared-owner-vendors", symbol: "person.2"),
            Card(title: "Chamber boards", stat: "\(ch.count) board members who are officials, donors or vendors",
                 items: ch.sorted { chamberWeight($0) > chamberWeight($1) }.prefix(3).map { "\($0.string("person") ?? ""), \($0.string("chamber") ?? "")" },
                 dataset: "chamber-overlaps", symbol: "storefront"),
            Card(title: "Developers behind projects", stat: "\(dc.count) projects named after a business",
                 items: dc.prefix(3).map { "\($0.string("project") ?? ""): \($0.string("company") ?? "")" }, dataset: "development-companies", symbol: "building.2"),
            Card(title: "Money raised and votes won", stat: "The top fundraiser won \(h.topWon) of \(h.contested) contested races",
                 items: ["\(h.contested - h.topWon) races went to a candidate who raised less"], dataset: "campaign-results", symbol: "chart.bar"),
        ]
    }

    // MARK: Live parts (/api/v1/overlaps)

    /// The live sections, in the site's order, with their titles.
    public static let liveSections: [(key: String, title: String, caption: String)] = [
        ("official_business_votes", "Votes on an official's own business", "Hand-checked matches: an official's registered business named in a motion they voted on"),
        ("nonprofit_board_money", "Nonprofits with an official on the board", "Payments from that official's government and their votes naming it"),
        ("checkbook_donors", "Checkbook payees that gave to campaigns", "From each city's check register"),
        ("split_purchases", "Payments just under a threshold", "Two or more payments to one payee within 30 days, each just under a purchasing limit"),
    ]

    /// {section: rows} from the /api/v1/overlaps answer ({data: {section: {rows, error}}}).
    public static func decodeLive(_ data: Data) throws -> [String: [Row]] {
        guard let top = try JSONDecoder().decode([String: JSONValue].self, from: data)["data"]?.objectValue else { return [:] }
        var out: [String: [Row]] = [:]
        for (k, v) in top {
            let list = v.objectValue?["rows"]?.arrayValue ?? []
            out[k] = list.enumerated().compactMap { i, x in x.objectValue.map { Row(id: i, values: $0) } }
        }
        return out
    }

    /// One live row as title, detail and the profile it names.
    public static func liveLine(_ section: String, _ r: Row) -> (title: String, detail: String, entity: String?) {
        switch section {
        case "official_business_votes":
            return ("\(r.string("official") ?? "") · \(r.string("business") ?? "")",
                    [r.string("date"), r.string("headline"), r.string("official_vote").map { "Voted \($0)" }].compactMap { $0 }.joined(separator: " · "), r.string("business_id"))
        case "nonprofit_board_money":
            let votes = r["votes"]?.arrayValue?.count ?? 0
            return ("\(r.string("official") ?? "") · \(r.string("nonprofit") ?? "")",
                    [r.number("paid_by_own_government").map { "\(money($0)) from \(r.string("payers") ?? "their government")" },
                     votes > 0 ? "\(votes) votes naming it" : "No vote naming it on file"].compactMap { $0 }.joined(separator: " · "), r.string("nonprofit_id"))
        case "checkbook_donors":
            return (r.string("payee") ?? "",
                    "Paid \(money(r.number("paid"))) by \(r.string("government") ?? r.string("gov_id") ?? "") · gave \(money(r.number("gave_to_campaigns"))) to campaigns",
                    r.string("payee_id"))
        default:
            return (r.string("payee") ?? "",
                    "\(Int(r.number("payments") ?? 0)) payments just under \(money(r.number("threshold"))) · \(money(r.number("total"))) total · \(r.string("government") ?? "")",
                    r.string("payee_id"))
        }
    }
}
