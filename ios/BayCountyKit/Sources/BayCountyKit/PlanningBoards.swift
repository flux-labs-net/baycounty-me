import Foundation

/// Planning and zoning boards on a government's screen, from the planning-boards and planning-board-members datasets.
/// Mirrors the Kotlin `PlanningBoards` and site/planning_boards.py: same order, member lines and meeting wording.
public enum PlanningBoards {
    public static let datasets = ["planning-boards", "planning-board-members"]

    /// A government's boards, in the order the site lists them.
    public static func boards(_ rows: [Row], gov: String) -> [Row] { rows.filter { $0.string("gov_id") == gov } }

    /// One board's members: chair, vice chair, members, alternates (the dataset's sort_order).
    public static func members(_ rows: [Row], board: String?) -> [Row] {
        rows.filter { $0.string("board_id") == board }.sorted { ($0.number("sort_order") ?? 99) < ($1.number("sort_order") ?? 99) }
    }

    /// "Chair · Post 3 · term ends Jan 8, 2027"; "Member" when there is nothing more to say.
    public static func memberLine(_ m: Row) -> String {
        let parts = [m.string("role").flatMap { r in r == "Member" || (m.string("seat")?.hasPrefix(r) ?? false) ? nil : r }, m.string("seat"),
                     m.string("term_end").flatMap { day($0) }.map { "term ends \($0)" }].compactMap { $0 }
        return parts.isEmpty ? "Member" : parts.joined(separator: " · ")
    }

    /// "Mon, Nov 9, 2026 at 4 PM", or the date alone when no time is posted. The time is the local time as written.
    public static func meetingLine(_ iso: String?) -> String? {
        guard let iso, iso.count >= 10 else { return nil }
        guard iso.contains("T"), iso.count >= 16 else { return day(iso, weekday: true) }
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd'T'HH:mm"
        guard let d = f.date(from: String(iso.prefix(16))) else { return nil }
        let cal = Calendar(identifier: .gregorian)
        let minute = cal.dateComponents(in: TimeZone(identifier: "UTC")!, from: d).minute ?? 0
        f.dateFormat = "EEE, MMM d, yyyy"
        let date = f.string(from: d)
        f.dateFormat = minute == 0 ? "h a" : "h:mm a"
        f.amSymbol = "AM"; f.pmSymbol = "PM"
        return "\(date) at \(f.string(from: d))"
    }

    /// "9 members listed" or "Members not published online", for the parts menu.
    public static func summary(_ boards: [Row]) -> String {
        let n = boards.reduce(0) { $0 + Int($1.number("members_listed") ?? 0) }
        return n > 0 ? "\(n) member\(n == 1 ? "" : "s") listed" : "Members not published online"
    }

    static func day(_ iso: String, weekday: Bool = false) -> String? {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        guard let d = f.date(from: String(iso.prefix(10))) else { return nil }
        f.dateFormat = weekday ? "EEE, MMM d, yyyy" : "MMM d, yyyy"
        return f.string(from: d)
    }
}
