import Foundation

public enum Format {
    private static let wholeDollars: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = "USD"
        f.locale = Locale(identifier: "en_US")
        f.minimumFractionDigits = 0
        f.maximumFractionDigits = 0
        return f
    }()

    private static let centsDollars: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = "USD"
        f.locale = Locale(identifier: "en_US")
        f.minimumFractionDigits = 2
        f.maximumFractionDigits = 2
        return f
    }()

    private static let plain: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.locale = Locale(identifier: "en_US")
        f.maximumFractionDigits = 4
        return f
    }()

    /// $1,234,567 (cents kept under $1,000 so per-resident and fee figures stay exact).
    public static func money(_ value: Double?) -> String {
        guard let value else { return "Not stated" }
        let f = abs(value) < 1000 && value != value.rounded() ? centsDollars : wholeDollars
        return f.string(from: NSNumber(value: value)) ?? "$\(value)"
    }

    /// $1.2M, $340K, $950.
    public static func compactMoney(_ value: Double) -> String {
        let a = abs(value), sign = value < 0 ? "-" : ""
        func trim(_ x: Double) -> String {
            let s = String(format: x >= 100 ? "%.0f" : "%.1f", x)
            return s.hasSuffix(".0") ? String(s.dropLast(2)) : s
        }
        switch a {
        case 1e9...: return "\(sign)$\(trim(a / 1e9))B"
        case 1e6...: return "\(sign)$\(trim(a / 1e6))M"
        case 1e4...: return "\(sign)$\(trim(a / 1e3))K"
        default: return money(value)
        }
    }

    public static func number(_ value: Double) -> String {
        plain.string(from: NSNumber(value: value)) ?? String(value)
    }

    // MARK: - Columns

    private static let labelOverrides: [String: String] = [
        "cra": "CRA", "gov": "Government", "fy": "Fiscal year", "date_or_fy": "When", "count": "Counted in totals",
        "pct_complete": "Percent complete", "pct_of_original": "Percent of original", "fema_michael_obligated": "FEMA (Hurricane Michael)",
        "population_2025": "Population (2025)", "population_2025_estimate": "Population (2025)", "employees_fte": "Employees (full-time equivalent)",
        "budgeted_fte": "Budgeted positions (FTE)", "n_contributions": "Contributions", "tally": "Vote", "split": "Split vote",
        "residential_single_family_amount": "Typical home pays", "per_resident": "Per resident", "rolled_back_rate": "Rolled-back rate",
        "location_name": "Location", "plain_english": "In plain English", "voted_yes": "Voted yes", "voted_no": "Voted no",
        "absent_or_abstained": "Absent or abstained", "par_amount": "Amount borrowed", "applies_to": "Applies to",
        "first_obligated": "First approved", "last_obligated": "Last approved", "own_money": "Own money", "url": "Link",
    ]

    /// "date_or_fy" -> "When", "total_raised" -> "Total raised".
    public static func label(_ column: String) -> String {
        if let o = labelOverrides[column] { return o }
        let words = column.split(separator: "_").map(String.init)
        let fixed = words.map { w -> String in
            switch w.lowercased() {
            case "fy": return "FY"
            case "fema": return "FEMA"
            case "cra": return "CRA"
            case "id": return "ID"
            case "pct": return "%"
            default: return w
            }
        }
        let s = fixed.joined(separator: " ")
        return s.prefix(1).uppercased() + s.dropFirst()
    }

    private static let moneyWords = ["amount", "cost", "total", "budget", "levy", "fund", "debt", "salary", "annual", "raised",
                                     "spent", "share", "outstanding", "value", "per_resident", "eligible", "obligated", "bill",
                                     "pay_min", "pay_mid", "pay_max", "hourly", "removed", "own_money", "from_organizations", "par"]
    private static let notMoneyWords = ["pct", "count", "n_", "payments", "parcels", "homesteads", "population", "residents",
                                        "fte", "millage", "rate", "votes", "findings", "year", "contributions", "note", "status",
                                        "as_of", "level", "line", "schedule_fy"]

    public static func isMoneyColumn(_ column: String) -> Bool {
        let c = column.lowercased()
        if notMoneyWords.contains(where: { c.contains($0) }) { return false }
        return moneyWords.contains { c.contains($0) }
    }

    /// Readable text for a value in a given column.
    public static func value(_ v: JSONValue, column: String) -> String {
        switch v {
        case .null: return ""
        case .bool(let b): return b ? "Yes" : "No"
        case .number(let n):
            if isMoneyColumn(column) { return money(n) }
            if column.hasPrefix("pct") { return "\(number(n))%" }
            if column.contains("year") || column == "fy" { return String(Int(n)) }
            return number(n)
        case .string(let s):
            if s == "True" || s == "False" { return s == "True" ? "Yes" : "No" }
            if let d = Dates.parse(s), s.count >= 10, s.count <= 25 { return Dates.display(d, hasTime: s.count > 10) }
            if ["government", "gov", "employer", "gov_id"].contains(column), let n = Governments.names[s] { return n }
            return humanizeCode(s, column: column)
        case .array(let a):
            return a.map { value($0, column: column) }.filter { !$0.isEmpty }.joined(separator: column == "actual_salaries" ? ", " : "\n")
        case .object(let o):
            return o.sorted { $0.key < $1.key }.map { "\($0.key): \(value($0.value, column: column))" }.joined(separator: ", ")
        }
    }

    /// Snake-case status codes like "in_progress" read as "In progress".
    static func humanizeCode(_ s: String, column: String) -> String {
        guard ["status", "race_status", "kind", "level", "category", "outcome", "vote", "type", "contributor_type", "pay_status"].contains(column),
              s.range(of: "^[a-z0-9_]+$", options: .regularExpression) != nil else { return s }
        let t = s.replacingOccurrences(of: "_", with: " ")
        return t.prefix(1).uppercased() + t.dropFirst()
    }
}

public enum Dates {
    static let chicago = TimeZone(identifier: "America/Chicago")!

    private static let iso: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    private static let day: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = chicago
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let shownDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US")
        f.timeZone = chicago
        f.dateFormat = "MMM d, yyyy"
        return f
    }()

    private static let shownTime: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US")
        f.timeZone = chicago
        f.dateFormat = "MMM d, yyyy 'at' h:mm a"
        return f
    }()

    /// Parses "2026-10-27T18:00:00-05:00" or "2026-10-27".
    public static func parse(_ s: String) -> Date? {
        if s.count == 10, s.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil { return day.date(from: s) }
        if s.count > 10, s.contains("T") { return iso.date(from: s) }
        return nil
    }

    public static func display(_ d: Date, hasTime: Bool) -> String {
        (hasTime ? shownTime : shownDay).string(from: d)
    }

    /// Calendar day in Bay County time, for grouping.
    public static func dayKey(_ d: Date) -> String { day.string(from: d) }
}
