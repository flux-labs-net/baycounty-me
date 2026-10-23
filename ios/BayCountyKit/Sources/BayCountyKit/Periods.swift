import Foundation

/// The year a record belongs to, so lists can open on the latest year and step back through earlier ones.
/// Records with a single date (a contract, a vote, a donation) use the calendar year of that date.
/// Records that cover a fiscal year (budgets, pay, audits) use that fiscal year, named for the year it ends.
public struct Period: Hashable, Comparable, Sendable, Identifiable {
    public let year: Int
    public let fiscal: Bool
    public var id: String { label }
    public var label: String { fiscal ? "FY\(year)" : String(year) }

    public init(year: Int, fiscal: Bool) { self.year = year; self.fiscal = fiscal }

    public static func < (a: Period, b: Period) -> Bool { a.year == b.year ? (a.fiscal && !b.fiscal) : a.year < b.year }

    /// Bay County governments run October to September; FY2027 began Oct 1, 2026.
    public static func currentFiscalYear(_ now: Date = Date()) -> Int {
        let c = Calendar(identifier: .gregorian).dateComponents(in: TimeZone(identifier: "America/Chicago")!, from: now)
        return (c.month ?? 1) >= 10 ? (c.year ?? 2026) + 1 : (c.year ?? 2026)
    }

    public static func currentYear(_ now: Date = Date()) -> Int {
        Calendar(identifier: .gregorian).dateComponents(in: TimeZone(identifier: "America/Chicago")!, from: now).year ?? 2026
    }

    /// The first four-digit year (19xx or 20xx) in a string such as "2026-03-10", "FY2024" or "2024 primary".
    static func year(in s: String?) -> Int? {
        guard let s else { return nil }
        let chars = Array(s)
        guard chars.count >= 4 else { return nil }
        for i in 0...(chars.count - 4) {
            let w = String(chars[i..<i + 4])
            if (w.hasPrefix("19") || w.hasPrefix("20")), let y = Int(w),
               (i == 0 || !chars[i - 1].isNumber), (i + 4 == chars.count || !chars[i + 4].isNumber) { return y }
        }
        return nil
    }

    /// Columns holding the single date a record happened on.
    public static let eventKeys = ["date", "dated_date", "last_obligated", "as_of"]
    /// Columns that name a fiscal year directly.
    static let fiscalKeys = ["fy", "fiscal_year", "date_or_fy", "year"]
    /// Columns that name a calendar year directly.
    static let yearKeys = ["tax_year", "election"]

    /// Reads one value: "2026-03-10" and "2024 primary" are calendar years; "FY2024" is a fiscal year;
    /// "FY2025-26" and "2025-26" are the fiscal year they end in.
    static func parse(_ v: String?) -> Period? {
        guard let v, let y = year(in: v) else { return nil }
        if v.range(of: #"\d{4}-\d{2}(?![\d-])"#, options: .regularExpression) != nil { return Period(year: y + 1, fiscal: true) }
        return Period(year: y, fiscal: v.hasPrefix("FY"))
    }

    /// The fiscal year (October to September) a calendar date such as "2025-11-04" falls in.
    static func fiscalYear(ofDate v: String?) -> Int? {
        guard let v, v.count >= 7, let y = Int(v.prefix(4)), let m = Int(v.dropFirst(5).prefix(2)) else { return nil }
        return m >= 10 ? y + 1 : y
    }

    /// The year this record belongs to, or nil when it carries no date.
    public static func of(_ row: Row) -> Period? {
        for k in eventKeys { if let p = parse(row.string(k)) { return p } }
        if let end = row.string("date_end"), let y = year(in: end) {
            // A start and end on the same day is a point in time, not a fiscal period.
            return Period(year: y, fiscal: row.string("date_start") != end)
        }
        for k in fiscalKeys {
            if let p = parse(row.string(k)) { return Period(year: p.year, fiscal: true) }
        }
        for k in yearKeys { if let y = year(in: row.string(k)) { return Period(year: y, fiscal: false) } }
        return nil
    }

    /// How one list's records map to years. A list uses one kind of year, whichever most of its records
    /// carry, so its menu never shows "2026" and "FY2026" side by side; dated records in a fiscal list
    /// move to the fiscal year their date falls in.
    public struct Index: Sendable {
        public let fiscal: Bool
        public let periods: [Period]
        public let datedShare: Double

        public init(_ rows: [Row]) {
            let raw = rows.compactMap(Period.of)
            fiscal = raw.filter(\.fiscal).count * 2 > raw.count
            datedShare = rows.isEmpty ? 0 : Double(raw.count) / Double(rows.count)
            let f = fiscal
            periods = Array(Set(rows.compactMap { Index.period($0, fiscal: f) })).sorted(by: >)
        }

        public func period(_ row: Row) -> Period? { Index.period(row, fiscal: fiscal) }

        static func period(_ row: Row, fiscal: Bool) -> Period? {
            guard let p = Period.of(row) else { return nil }
            if p.fiscal == fiscal { return p }
            if fiscal {
                let date = row.first(Period.eventKeys + ["date_end"])
                return Period(year: Period.fiscalYear(ofDate: date) ?? p.year, fiscal: true)
            }
            // A fiscal record in a calendar list goes under the year it started.
            return Period(year: Period.year(in: row.string("date_start")) ?? p.year, fiscal: false)
        }

        /// The year the list opens on, or nil to show every year: nil when there is only one year,
        /// or when more than a quarter of the records carry no date (so they aren't hidden by default).
        public func defaultPeriod(now: Date = Date()) -> Period? {
            guard periods.count > 1, datedShare >= 0.75 else { return nil }
            return Period.defaultPeriod(in: periods, now: now)
        }
    }

    /// Every period in these rows, newest first.
    public static func all(in rows: [Row]) -> [Period] { Index(rows).periods }

    /// The period a list of these rows should open on, or nil to show every year.
    public static func defaultPeriod(for rows: [Row], now: Date = Date()) -> Period? { Index(rows).defaultPeriod(now: now) }

    /// The period a list should open on: this year (or this fiscal year) when it has records,
    /// otherwise the newest period that isn't in the future, otherwise the newest of all.
    public static func defaultPeriod(in periods: [Period], now: Date = Date()) -> Period? {
        guard let newest = periods.first else { return nil }
        let current = newest.fiscal ? currentFiscalYear(now) : currentYear(now)
        let wanted = Period(year: current, fiscal: newest.fiscal)
        if periods.contains(wanted) { return wanted }
        return periods.first { $0.year <= current } ?? newest
    }
}

public extension DatasetSpec {
    /// A sortable key, newest last: the record's date when it has one, else its period.
    func newestKey(_ row: Row) -> String {
        if let d = row.first(Period.eventKeys + ["date_end"]), d.first?.isNumber == true { return d }
        return Period.of(row).map { String(format: "%04d-99", $0.year) } ?? (sortDate(row) ?? "")
    }
}
