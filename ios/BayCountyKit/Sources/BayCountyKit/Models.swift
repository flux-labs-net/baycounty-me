import Foundation

/// Local governments the site covers, keyed the way the data keys them (`gov_id`).
public enum Governments {
    public static let names: [String: String] = [
        "county": "Bay County", "schools": "Bay District Schools", "pc": "Panama City", "pcb": "Panama City Beach",
        "lh": "Lynn Haven", "cw": "Callaway", "sp": "Springfield", "parker": "Parker", "mb": "Mexico Beach",
    ]

    /// Board names as the site lists them (data/meetings/fetch_meetings.py BOARDS), shortened for phone screens.
    public static let boards: [String: String] = [
        "county": "Bay County Commission", "county-planning": "Bay County Planning Commission",
        "schools": "Bay District School Board", "pc": "Panama City Commission", "pc-cra": "Panama City CRA Board",
        "pcb": "Panama City Beach City Council", "lh": "Lynn Haven City Commission", "lh-cra": "Lynn Haven CRA Board",
        "cw": "Callaway City Commission", "cw-cra": "Callaway CRA Board", "sp": "Springfield City Commission",
        "parker": "Parker City Council", "mb": "Mexico Beach City Council",
    ]

    /// Meeting board id ("lh-cra", "county-planning", "pc") to a readable name.
    public static func boardName(_ board: String) -> String {
        if let known = boards[board] { return known }
        let parts = board.split(separator: "-", maxSplits: 1).map(String.init)
        let gov = names[parts.first ?? ""] ?? board
        guard parts.count > 1 else { return gov }
        return parts[1] == "cra" ? "\(gov) CRA Board" : "\(gov) \(Format.label(parts[1]))"
    }
}

/// One government profile (`government-profiles` dataset).
public struct Government: Identifiable, Hashable, Sendable {
    public let row: Row
    public init(row: Row) { self.row = row }

    public var id: String { govID }
    public var govID: String { row.string("gov_id") ?? slug }
    public var name: String { row.string("government") ?? "Government" }
    public var kind: String { row.string("kind") ?? "" }
    public var pageURL: URL? { row.url("page") }
    public var slug: String { row.string("slug") ?? pageURL?.lastPathComponent ?? name.lowercased() }

    public var population: Double? { row.number("population_2025") }
    public var budgetTotal: Double? { row.number("budget_total") }
    public var generalFund: Double? { row.number("general_fund") }
    public var budgetStatus: String? { row.string("budget_status") }
    public var millage: Double? { row.number("millage") }
    public var propertyTaxLevy: Double? { row.number("property_tax_levy") }
    public var debtTotal: Double? { row.number("debt_total") }
    public var debtYear: String? { row.string("debt_year") }
    public var auditYear: String? { row.string("audit_year") }
    public var auditFindings: Int? { row.number("audit_findings").map { Int($0) } }
    public var repeatFindings: Int? { row.number("repeat_findings").map { Int($0) } }
    public var votesRecorded: Int? { row.number("votes_recorded").map { Int($0) } }
    public var splitVotes: Int? { (row.number("split_votes") ?? row.number("split_vote")).map { Int($0) } }
    public var employees: Double? { row.number("employees_fte") }
    public var typicalUtilityBill: Double? { row.number("typical_utility_bill") }
    public var femaMichael: Double? { row.number("fema_michael_obligated") }

    public var budgetPerResident: Double? {
        guard let b = budgetTotal, let p = population, p > 0 else { return nil }
        return b / p
    }

    public var debtPerResident: Double? {
        guard let d = debtTotal, let p = population, p > 0 else { return nil }
        return d / p
    }
}

/// One public meeting (`meetings` dataset).
public struct Meeting: Identifiable, Hashable, Sendable {
    public let row: Row
    public init(row: Row) { self.row = row }

    public var id: String { "\(board)|\(row.string("start") ?? "")|\(title)" }
    public var board: String { row.string("board") ?? "" }
    public var boardName: String { Governments.boardName(board) }
    public var govID: String { row.string("gov_id") ?? String(board.split(separator: "-").first ?? "") }
    public var title: String { row.string("title") ?? "Meeting" }
    public var start: Date? { row.string("start").flatMap(Dates.parse) }
    public var hasTime: Bool { (row.string("start") ?? "").count > 10 }
    public var location: String? { row.string("location") }
    public var agendaURL: URL? { row.url("agenda_url") }
    public var packetURL: URL? { row.url("packet_url") }
    public var minutesURL: URL? { row.url("minutes_url") }
    public var detailURL: URL? { row.url("detail_url") }
    public var isPast: Bool { row.bool("past") ?? false }
    public var isCancelled: Bool { row.bool("cancelled") ?? false }
    /// Not posted yet; inferred from the board's regular schedule.
    public var isExpected: Bool { row.bool("expected") ?? false }
    public var agendaItems: [String] { row.strings("agenda_items") + row.strings("items") }

    public var whenText: String {
        guard let start else { return "Date not set" }
        return Dates.display(start, hasTime: hasTime)
    }

    /// Upcoming, not cancelled, soonest first.
    public static func upcoming(_ all: [Meeting], now: Date = Date()) -> [Meeting] {
        all.filter { m in
            guard !m.isPast, !m.isCancelled, let s = m.start else { return false }
            return s >= Calendar(identifier: .gregorian).startOfDay(for: now) || (m.hasTime && s >= now)
        }
        .sorted { ($0.start ?? .distantFuture) < ($1.start ?? .distantFuture) }
    }
}

/// CRA spending, with the site's counting rules: only rows with `count` true go into totals, and
/// "paid out" (Spent) is kept apart from money that is only committed or budgeted.
public enum CRALedger {
    public struct Summary: Identifiable, Hashable, Sendable {
        public let agency: String
        public let paidOut: Double
        public let pending: Double
        public let records: Int
        public var id: String { agency }
        public var total: Double { paidOut + pending }
    }

    public static func isCounted(_ row: Row) -> Bool { row.bool("count") ?? false }
    public static func status(_ row: Row) -> String { row.string("status") ?? "" }

    public static func paidOut(_ rows: [Row]) -> Double {
        rows.filter { isCounted($0) && status($0) == "Spent" }.compactMap { $0.number("amount") }.reduce(0, +)
    }

    public static func pending(_ rows: [Row]) -> Double {
        rows.filter { isCounted($0) && ["Committed", "Budgeted"].contains(status($0)) }.compactMap { $0.number("amount") }.reduce(0, +)
    }

    public static func summaries(_ rows: [Row]) -> [Summary] {
        Dictionary(grouping: rows) { $0.string("cra") ?? "Other" }
            .map { Summary(agency: $0.key, paidOut: paidOut($0.value), pending: pending($0.value), records: $0.value.count) }
            .sorted { $0.total > $1.total }
    }

    /// What each status means, in plain words (matches the site's data rules).
    public static func explain(status: String) -> String {
        switch status {
        case "Spent": return "Reported paid."
        case "Committed": return "Awarded or under contract, not fully paid."
        case "Budgeted": return "Set aside in a budget. A plan, not proof of payment."
        case "Proposed": return "Requested or proposed. No award confirmed."
        case "Incoming": return "Money coming in to the CRA, not spending."
        case "Not CRA-funded": return "Tied to a CRA project but paid with other money."
        default: return ""
        }
    }
}

/// One hit from `/api/v1/search`.
public struct SearchResult: Codable, Hashable, Identifiable, Sendable {
    public let type: String?
    public let title: String?
    public let summary: String?
    public let url: String?
    public var id: String { (url ?? "") + (title ?? "") }
    public var link: URL? { url.flatMap(URL.init(string:)) }
}

struct SearchResponse: Codable {
    let total: Int?
    let data: [SearchResult]
}
