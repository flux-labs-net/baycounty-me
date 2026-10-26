import Foundation

/// Who held each elected seat in a fiscal year, from the officeholder-terms dataset.
/// A Swift port of api/_officials.js `inOffice`, so the app's "Who's in charge" matches the government pages.
public enum Officeholders {
    public struct Holder: Sendable, Hashable, Identifiable {
        public let personName: String
        public let personID: String?
        public let vacant: Bool
        public let confirmed: Bool
        public let startDate: String?
        public let endDate: String?
        public let how: String?
        /// Joined or left during the period, so someone else held the seat for part of it.
        public let partOfPeriod: Bool
        public let note: String?
        public var id: String { "\(personName)|\(startDate ?? "")" }
    }

    public struct Seat: Sendable, Hashable, Identifiable {
        public let seat: String
        public let appointed: Bool
        public var holders: [Holder]
        public var id: String { seat }
    }

    /// One term a person served (for their profile).
    public struct Term: Sendable, Hashable, Identifiable {
        public let government: String
        public let govID: String
        public let seat: String
        public let appointed: Bool
        public let startDate: String?
        public let endDate: String?
        public let how: String?
        public var id: String { "\(govID)|\(seat)|\(startDate ?? "")" }
        /// "2016 to 2020", "Since 2022", "Until 2018".
        public var years: String {
            let s = startDate.map { String($0.prefix(4)) }, e = endDate.map { String($0.prefix(4)) }
            switch (s, e) {
            case let (s?, e?): return s == e ? s : "\(s) to \(e)"
            case let (s?, nil): return "Since \(s)"
            case let (nil, e?): return "Until \(e)"
            default: return ""
            }
        }
    }

    /// Fiscal years start in October; the school district's in July. FY2026 = 2025-10-01 to 2026-09-30.
    public static func fyWindow(gov: String, year: Int) -> (from: String, to: String) {
        let m = gov == "schools" ? 7 : 10
        let lastMonth = m == 1 ? 12 : m - 1
        let lastDay = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][lastMonth - 1]
            + (lastMonth == 2 && year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) ? 1 : 0)
        func pad(_ n: Int) -> String { n < 10 ? "0\(n)" : "\(n)" }
        return ("\(year - 1)-\(pad(m))-01", "\(m == 1 ? year - 1 : year)-\(pad(lastMonth))-\(pad(lastDay))")
    }

    /// A term ends on the day its successor starts, so an end date equal to `from` is out.
    static func overlaps(_ r: Row, from: String, to: String) -> Bool {
        (r.string("start_date").map { $0 <= to } ?? true) && (r.string("end_date").map { $0 > from } ?? true)
    }

    /// The fiscal year a date falls in for a government (Oct to Sep; schools Jul to Jun).
    public static func fiscalYear(gov: String, date: Date = Date()) -> Int {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago")!
        let c = cal.dateComponents([.year, .month], from: date)
        return (c.month ?? 1) >= (gov == "schools" ? 7 : 10) ? (c.year ?? 2026) + 1 : (c.year ?? 2026)
    }

    /// Fiscal years with terms on record for a government, newest first, from the site's first year (2016).
    public static func years(_ rows: [Row], gov: String, now: Date = Date()) -> [Int] {
        guard rows.contains(where: { $0.string("gov_id") == gov }) else { return [] }
        return Array((Cutoff.firstYear...fiscalYear(gov: gov, date: now)).reversed())
    }

    /// Seats in order, each with the people who held it during the fiscal year (or on `date`, YYYY-MM-DD).
    public static func inOffice(_ all: [Row], gov: String, year: Int? = nil, date: String? = nil, today: Date = Date()) -> [Seat] {
        let rows = all.filter { $0.string("gov_id") == gov }
        let from: String, to: String
        if let date {
            from = date; to = date
        } else if let year {
            (from, to) = fyWindow(gov: gov, year: year)
        } else {
            let f = DateFormatter()
            f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"
            from = f.string(from: today); to = from
        }
        var order: [String] = []
        var seats: [String: Seat] = [:]
        let sorted = rows.sorted {
            let a = ($0.number("seat_order") ?? 0, $0.number("term_order") ?? 0), b = ($1.number("seat_order") ?? 0, $1.number("term_order") ?? 0)
            return a < b
        }
        for r in sorted {
            let name = r.string("seat") ?? ""
            if seats[name] == nil { order.append(name); seats[name] = Seat(seat: name, appointed: r.bool("appointed") ?? false, holders: []) }
            guard overlaps(r, from: from, to: to) else { continue }
            let part = (r.string("start_date").map { $0 > from } ?? false) || (r.string("end_date").map { $0 <= to } ?? false)
            seats[name]?.holders.append(Holder(
                personName: r.string("person_name") ?? "", personID: r.string("person_id"), vacant: r.bool("vacant") ?? false,
                confirmed: r.bool("confirmed") != false, startDate: r.string("start_date"), endDate: r.string("end_date"),
                how: r.string("how"), partOfPeriod: part, note: r.string("note")))
        }
        return order.compactMap { seats[$0] }
    }

    /// Every term a person served, newest first.
    public static func terms(_ all: [Row], personID: String) -> [Term] {
        all.filter { $0.string("person_id") == personID && $0.bool("vacant") != true }
            .map { r in
                Term(government: r.string("government") ?? Governments.names[r.string("gov_id") ?? ""] ?? "",
                     govID: r.string("gov_id") ?? "", seat: r.string("seat") ?? "", appointed: r.bool("appointed") ?? false,
                     startDate: r.string("start_date"), endDate: r.string("end_date"), how: r.string("how"))
            }
            .sorted { ($0.endDate ?? "9999") > ($1.endDate ?? "9999") }
    }
}

/// The site's first year: nothing from 2015 or earlier is shown anywhere (entities/cutoff.py, api/_cutoff.js).
public enum Cutoff {
    public static let firstYear = 2016
}
