import Foundation

/// The parts of a government screen. The screen itself shows the year, "At a glance" and one row per part that has
/// records for that government; each row opens that part on its own screen, for the same year, so the screen
/// doesn't run on as one long page. Mirrors android/kit GovParts.kt.
public enum GovPart: String, CaseIterable, Sendable, Identifiable {
    case who, money, compare, meetings, debt, audits, savings, cra, records

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .who: "Who's in charge"
        case .money: "Money in, money out"
        case .compare: "Compared with the others"
        case .meetings: "Upcoming meetings"
        case .debt: "Debt"
        case .audits: "What the auditors found"
        case .savings: "Where it could spend less"
        case .cra: "Redevelopment (CRA)"
        case .records: "Every record"
        }
    }

    /// SF Symbol name (the Android app maps the same names to its icons).
    public var symbol: String {
        switch self {
        case .who: "person.3"
        case .money: "chart.pie"
        case .compare: "chart.bar.xaxis"
        case .meetings: "calendar"
        case .debt: "creditcard"
        case .audits: "magnifyingglass"
        case .savings: "dollarsign.arrow.circlepath"
        case .cra: "building.2"
        case .records: "tray.full"
        }
    }

    /// The parts to list, in screen order: only those with records (`has`); "Compared with the others" always.
    public static func shown(_ has: (GovPart) -> Bool) -> [GovPart] {
        allCases.filter { $0 == .compare || has($0) }
    }
}
