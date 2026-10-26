import Foundation

/// The numbers and groupings behind a record list's summary, chart, groups and table.
public enum Browse {
    /// Lists where adding up the amount column means something on its own, with the word for the total
    /// and a note on what it is not. Everything else shows counts and the largest single amount.
    public static let totals: [String: (label: String, note: String?)] = [
        "contracts": ("Approved", "Approved amounts, often not-to-exceed. Not proof of payment."),
        "change-orders": ("Added", "Added to existing contracts by change orders."),
        "emergency-purchases": ("Approved", nil),
        "campaign-contributions-2026": ("Given", nil),
        "campaign-contributions-history": ("Given", nil),
        "business-donor-sunbiz": ("Given", nil),
        "owner-gifts": ("Given", nil),
        "fema-michael-projects": ("Federal share", "FEMA's share obligated so far, not all paid out."),
        "bed-tax-collections": ("Collected", nil),
        "vendor-payments": ("Paid", nil),
    ]

    /// Lists of single campaign gifts. Florida caps a gift at $1,000 per election, so the largest single gift
    /// says little: these rank each giver by its total and show how many gifts it made.
    public static let giftLists: Set<String> = ["campaign-contributions-2026", "campaign-contributions-history"]

    /// What a list's records are called on its summary ("Contracts", "Votes").
    public static func noun(_ datasetID: String) -> String {
        ["contracts": "Contracts", "votes": "Votes", "member-votes": "Votes", "change-orders": "Change orders",
         "emergency-purchases": "Purchases", "salary-positions": "Positions", "salary-leaders": "Positions",
         "fema-michael-projects": "Projects", "sales-tax-projects": "Projects", "audit-findings": "Findings",
         "campaign-contributions-2026": "Gifts", "campaign-contributions-history": "Gifts", "cra-payments": "Records", "bonds": "Bonds"][datasetID] ?? "Records"
    }

    /// A readable name for a value: government ids ("pc") become names, codes ("special_district") become words.
    public static func displayName(_ v: String, column: String) -> String {
        if let n = Governments.names[v] { return n }
        let agencies = ["special_district": "Special districts", "visit_pcb": "Visit Panama City Beach",
                        "destination_pc": "Destination Panama City", "mb_cdc": "Mexico Beach CDC", "sheriff": "Sheriff",
                        "airport": "Airport", "port": "Port Panama City", "clerk": "Clerk of Court", "tax_collector": "Tax Collector",
                        "property_appraiser": "Property Appraiser", "supervisor_of_elections": "Supervisor of Elections"]
        if let a = agencies[v] { return a }
        if v.contains("_"), v == v.lowercased() { return v.replacingOccurrences(of: "_", with: " ").capitalizingFirstLetter }
        return v
    }

    /// "2026-09" for a record dated in September 2026, from its single event date.
    public static func monthKey(_ row: Row) -> String? {
        guard let d = row.first(Period.eventKeys), d.count >= 7, d.first?.isNumber == true else { return nil }
        let k = String(d.prefix(7))
        return k.dropFirst(4).first == "-" ? k : nil
    }

    static let monthNames = ["January", "February", "March", "April", "May", "June", "July", "August",
                             "September", "October", "November", "December"]

    /// "September 2026" (or "September" when the year is implied).
    public static func monthName(_ key: String, withYear: Bool = true) -> String {
        guard let m = Int(key.suffix(2)), (1...12).contains(m) else { return key }
        return withYear ? "\(monthNames[m - 1]) \(key.prefix(4))" : monthNames[m - 1]
    }

    public struct Bucket: Identifiable, Hashable, Sendable {
        public let key: String
        public let label: String
        public let count: Int
        public let amount: Double
        public var id: String { key }
    }

    /// Records per month of one year, January through the last month with records (or December for past years).
    public static func months(_ rows: [Row], spec: DatasetSpec, year: Int, through lastMonth: Int? = nil) -> [Bucket] {
        var count = [Int: Int](), amount = [Int: Double]()
        for r in rows {
            guard let k = monthKey(r), k.hasPrefix(String(year)), let m = Int(k.suffix(2)) else { continue }
            count[m, default: 0] += 1
            amount[m, default: 0] += spec.amount(r) ?? 0
        }
        guard let maxMonth = lastMonth ?? count.keys.max() else { return [] }
        return (1...max(maxMonth, count.keys.max() ?? 1)).map { m in
            Bucket(key: String(format: "%04d-%02d", year, m), label: String(monthNames[m - 1].prefix(3)),
                   count: count[m] ?? 0, amount: amount[m] ?? 0)
        }
    }

    /// Records per year (or fiscal year), oldest to newest.
    public static func years(_ rows: [Row], spec: DatasetSpec, periods: [Int: Period]) -> [Bucket] {
        var count = [Period: Int](), amount = [Period: Double]()
        for r in rows {
            guard let p = periods[r.id], p.year >= Cutoff.firstYear else { continue }
            count[p, default: 0] += 1
            amount[p, default: 0] += spec.amount(r) ?? 0
        }
        return count.keys.sorted().map { p in Bucket(key: p.label, label: p.label, count: count[p]!, amount: amount[p] ?? 0) }
    }

    /// The biggest names in a column (companies, governments): by total amount when the list has a total, else by count.
    public static func top(_ rows: [Row], key: String, spec: DatasetSpec, byAmount: Bool, limit: Int = 5) -> [Bucket] {
        var count = [String: Int](), amount = [String: Double]()
        for r in rows {
            guard let v = r[key].map({ Format.value($0, column: key) }), !v.isEmpty, !isPlaceholder(v) else { continue }
            count[v, default: 0] += 1
            amount[v, default: 0] += spec.amount(r) ?? 0
        }
        let ranked = count.keys.sorted { a, b in
            let (x, y) = byAmount ? (amount[a] ?? 0, amount[b] ?? 0) : (Double(count[a]!), Double(count[b]!))
            return x != y ? x > y : a < b
        }
        return ranked.prefix(limit).map { Bucket(key: $0, label: displayName($0, column: key), count: count[$0]!, amount: amount[$0] ?? 0) }
    }

    /// Values like "Not named in agenda recommendation" aren't a real name to rank.
    static func isPlaceholder(_ v: String) -> Bool {
        let l = v.lowercased()
        return l.hasPrefix("not named") || l.hasPrefix("not stated") || l == "unknown" || l == "n/a"
    }

    // MARK: - Grouping the list

    public enum GroupKey: Hashable, Sendable, Identifiable {
        case none, month, year, column(String)
        public var id: String {
            switch self { case .none: "none"; case .month: "month"; case .year: "year"; case .column(let c): c }
        }
        public var label: String {
            switch self {
            case .none: "None"
            case .month: "Month"
            case .year: "Year"
            case .column(let c): Browse.columnLabel(c)
            }
        }
    }

    static func columnLabel(_ c: String) -> String {
        switch c {
        case "gov_id", "gov", "government", "employer": "Government"
        case "vendor", "payee", "contributor": "Company"
        default: Format.label(c)
        }
    }

    public struct Group: Identifiable, Sendable {
        public let key: String
        public let title: String
        public let rows: [Row]
        public let total: Double
        public var id: String { key }
    }

    /// Splits rows (already sorted) into groups, keeping the rows' order inside each group.
    /// Months and years run newest first; other groups run largest first.
    public static func groups(_ rows: [Row], by key: GroupKey, spec: DatasetSpec, periods: [Int: Period]) -> [Group] {
        func label(_ r: Row) -> (String, String)? {
            switch key {
            case .none: return ("all", "All")
            case .month: return monthKey(r).map { ($0, monthName($0)) }
            case .year: return periods[r.id].map { (String(format: "%04d%@", $0.year, $0.fiscal ? "F" : ""), $0.label) }
            case .column(let c):
                guard let v = r[c].map({ Format.value($0, column: c) }), !v.isEmpty else { return nil }
                let shown = displayName(v, column: c)
                return (shown, shown)
            }
        }
        var order = [String](), titles = [String: String](), buckets = [String: [Row]]()
        var other = [Row]()
        for r in rows {
            guard let (k, t) = label(r) else { other.append(r); continue }
            if buckets[k] == nil { order.append(k); titles[k] = t }
            buckets[k, default: []].append(r)
        }
        var out = order.map { k in
            Group(key: k, title: titles[k]!, rows: buckets[k]!, total: buckets[k]!.compactMap(spec.amount).reduce(0, +))
        }
        switch key {
        case .month, .year: out.sort { $0.key > $1.key }
        case .column: out.sort { $0.rows.count != $1.rows.count ? $0.rows.count > $1.rows.count : $0.title < $1.title }
        case .none: break
        }
        if !other.isEmpty {
            out.append(Group(key: "~other", title: key == .month || key == .year ? "No date" : "Not stated",
                             rows: other, total: other.compactMap(spec.amount).reduce(0, +)))
        }
        return out
    }

    /// Ways a list can be grouped, given its records: by month or year when they carry dates, and by any
    /// column with a handful of values (government, category, company when names repeat).
    public static func groupOptions(_ rows: [Row], spec: DatasetSpec, periods: [Int: Period], period: Period?) -> [GroupKey] {
        var out: [GroupKey] = []
        if let period, !period.fiscal, rows.contains(where: { monthKey($0) != nil }) { out.append(.month) }
        if period == nil && Set(periods.values).count > 1 { out.append(.year) }
        var seen = Set<String>()
        let candidates = spec.filterKeys + spec.titleKeys.prefix(1)
        for c in candidates where !seen.contains(c) && c != "member" {
            seen.insert(c)
            let values = Set(rows.compactMap { $0.string(c) })
            let isTitle = spec.titleKeys.first == c
            if isTitle ? (values.count >= 2 && values.count < rows.count * 3 / 4) : (2...20).contains(values.count) {
                out.append(.column(c))
            }
            if out.count >= 4 { break }
        }
        return out
    }

    /// The column that names the government a record belongs to, if the list has one.
    public static func governmentColumn(_ spec: DatasetSpec, rows: [Row]) -> String? {
        for c in ["government", "gov", "employer", "applicant", "authority", "board", "cra", "issuer", "gov_id"] {
            if rows.contains(where: { $0.string(c) != nil }) { return c }
        }
        return nil
    }

    /// A short form of a government's name for narrow table columns.
    public static func shortGovernment(_ s: String) -> String {
        let map = ["Bay County BOCC": "County", "Bay County": "County", "City of Panama City Beach": "PCB",
                   "Panama City Beach": "PCB", "City of Panama City": "Panama City", "City of Lynn Haven": "Lynn Haven",
                   "City of Callaway": "Callaway", "City of Springfield": "Springfield", "City of Parker": "Parker",
                   "City of Mexico Beach": "Mexico Bch", "Bay District Schools": "Schools", "Bay District School Board": "Schools"]
        if let m = map[s] { return m }
        if let n = Governments.names[s] { return shortGovernment(n) }
        if s.contains("_"), s == s.lowercased() { return displayName(s, column: "") }
        return s.replacingOccurrences(of: "City of ", with: "")
    }
}

/// One recorded vote's roll call, read from its members (or its tally text when no roll call was published).
public struct VoteSummary: Sendable, Equatable {
    public enum Choice: String, Sendable { case yes, no, other }
    public struct Member: Sendable, Equatable, Identifiable {
        public let name: String
        public let personID: String?
        public let choice: Choice
        public var id: String { personID ?? name }
    }

    public let members: [Member]
    public let yes: Int
    public let no: Int
    public let other: Int
    /// True when it passed, false when it failed, nil when the outcome isn't published yet.
    public let passed: Bool?
    public let split: Bool

    public init(_ row: Row) {
        var ms: [Member] = []
        for m in row["members"]?.arrayValue ?? [] {
            guard case .object(let o) = m else { continue }
            let v = (o["vote"]?.stringValue ?? "").lowercased()
            ms.append(Member(name: o["name"]?.stringValue ?? "Member", personID: o["person_id"]?.stringValue,
                             choice: v == "yes" ? .yes : v == "no" ? .no : .other))
        }
        members = ms
        if !ms.isEmpty {
            yes = ms.filter { $0.choice == .yes }.count
            no = ms.filter { $0.choice == .no }.count
            other = ms.filter { $0.choice == .other }.count
        } else {
            // "4-1", "5-0 (minutes: ...)"
            let digits = (row.string("tally") ?? "").split(whereSeparator: { !$0.isNumber }).prefix(2).compactMap { Int($0) }
            yes = digits.first ?? 0
            no = digits.count > 1 ? digits[1] : 0
            other = 0
        }
        let outcome = (row.string("outcome") ?? "").lowercased()
        passed = outcome.hasPrefix("passed") || outcome.hasPrefix("adopted") || outcome.hasPrefix("approved") ? true
            : outcome.hasPrefix("failed") || outcome.hasPrefix("denied") || outcome.hasPrefix("rejected") ? false : nil
        split = row.bool("split") ?? (yes > 0 && no > 0)
    }

    public var hasTally: Bool { yes + no + other > 0 }
    public var tallyText: String { other > 0 ? "\(yes)–\(no), \(other) absent" : "\(yes)–\(no)" }
}

public extension Browse {
    struct Meeting: Identifiable, Sendable {
        public let date: String
        public let board: String
        public let votes: [Row]
        public var id: String { date + "|" + board }
    }

    /// Votes grouped by the meeting they were taken at, newest meeting first, agenda order kept inside.
    static func meetings(_ votes: [Row]) -> [Meeting] {
        var order = [String](), rows = [String: [Row]]()
        for v in votes {
            let k = (v.string("date") ?? "") + "|" + (v.string("board") ?? "")
            if rows[k] == nil { order.append(k) }
            rows[k, default: []].append(v)
        }
        return order.map { k in
            let parts = k.split(separator: "|", maxSplits: 1, omittingEmptySubsequences: false)
            return Meeting(date: String(parts[0]), board: parts.count > 1 ? String(parts[1]) : "", votes: rows[k]!)
        }
        .sorted { $0.date != $1.date ? $0.date > $1.date : $0.board < $1.board }
    }
}

extension String {
    var capitalizingFirstLetter: String { prefix(1).uppercased() + dropFirst() }
}
