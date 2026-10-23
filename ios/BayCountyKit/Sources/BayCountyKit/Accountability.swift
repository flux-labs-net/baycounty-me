import Foundation

/// The Accountability console (/public-money/accountability): public projects followed from first budget
/// to close-out, with flags raised by published rules, records still missing, and each agency's reply.
/// Read from /data/accountability.json, the same file the website's console uses.
/// A flag is a question for the agency, not a finding of wrongdoing; the app's wording must stay that way.
public struct AccountabilityConsole: Codable, Sendable {
    public struct Rule: Codable, Sendable, Identifiable, Hashable {
        public let id: String
        public let title: String
        public let when: String?
        public let means: String?
        public let not: String?
    }

    public struct Stats: Codable, Sendable, Hashable {
        public let projects: Int?
        public let flagged: Int?
        public let flags: Int?
        public let gaps: Int?
        public let replied: Int?
        public let sent: Int?
        public let money: Double?
    }

    public struct Figure: Codable, Sendable, Hashable {
        public let a: Double?
        public let t: String?
    }

    public struct Event: Codable, Sendable, Hashable, Identifiable {
        public let d: String?
        public let k: String
        public let a: Double?
        public let approx: Bool?
        public let t: String
        public let payee: String?
        public let u: String?
        public let vid: String?
        public let s: String?
        public let side: Bool?
        public var id: String { (s ?? d ?? "") + "|" + k + "|" + t }
        public var url: URL? { u.flatMap(URL.init(string:)) }
    }

    public struct Flag: Codable, Sendable, Hashable, Identifiable {
        public let r: String
        public let sev: String?
        public let note: String
        public var id: String { r + note }
    }

    public struct Gap: Codable, Sendable, Hashable, Identifiable {
        public let q: String
        public var id: String { q }
    }

    public struct Reply: Codable, Sendable, Hashable {
        public let status: String?
        public let sent: String?
        public let date: String?
        public let text: String?
        public let u: String?
    }

    public struct Project: Codable, Sendable, Hashable, Identifiable {
        public let id: String
        public let n: String
        public let gk: String?
        public let g: String?
        public let agency: String?
        public let `where`: String?
        public let what: String?
        public let funding: String?
        public let status: String?
        public let src: String?
        public let ev: [Event]
        public let flags: [Flag]
        public let gaps: [Gap]
        public let base: Figure?
        public let now: Figure?
        public let total: Figure?
        public let growth: Double?
        public let late_days: Double?
        public let sev: String?
        public let reply: Reply?
        public let first: String?
        public let last: String?
        public let money: Double?
        public let vendor: String?

        /// The latest firm figure: final total, else current contract or estimate.
        public var latest: Figure? { total ?? now }
        public var stageLabel: String { AccountabilityConsole.stage(status) }
        /// Timeline oldest to newest, as the site shows it.
        public var timeline: [Event] { ev.sorted { ($0.s ?? $0.d ?? "") < ($1.s ?? $1.d ?? "") } }
    }

    public let about: String?
    public let rules: [Rule]
    public let stats: Stats?
    public let projects: [Project]

    public func rule(_ id: String) -> Rule? { rules.first { $0.id == id } }

    /// Stage names as the website shows them.
    public static let stages = ["budgeted": "Budgeted", "committed": "Approved", "design": "In design", "contract": "Under contract",
        "construction": "Under construction", "delayed": "Delayed", "phase-done": "Phase done", "complete": "Complete",
        "closed": "Closed out", "sale": "Land sale", "removed": "Removed", "unknown": "Status unclear"]
    public static func stage(_ s: String?) -> String { stages[s ?? ""] ?? "Status unclear" }

    /// Timeline event kinds as the website shows them.
    public static let kinds = ["budget": "Budget", "estimate": "Estimate", "approval": "Approved", "award": "Contract",
        "change": "Change order", "vote": "Vote", "payment": "Payment", "spent": "Spent to date", "complete": "Done",
        "milestone": "Milestone", "sale": "Sale"]
    public static func kind(_ k: String) -> String { kinds[k] ?? k.capitalized }

    public static func source(_ s: String?) -> String {
        ["reviewed": "Reviewed history", "contracts": "Contract", "surtax": "Sales tax project"][s ?? ""] ?? "Project"
    }

    public static func reply(_ s: String?) -> String {
        ["not_sent": "Not yet sent to the agency", "sent": "Sent to the agency, awaiting a reply",
         "replied": "Agency replied"][s ?? ""] ?? "Not yet sent to the agency"
    }

    /// Stages grouped for the list's filter: still going, finished, or stopped.
    public enum Phase: String, CaseIterable, Sendable, Identifiable {
        case active = "In progress", done = "Finished", stopped = "Removed or sold"
        public var id: String { rawValue }
        public static func of(_ status: String?) -> Phase {
            switch status {
            case "complete", "closed", "phase-done": .done
            case "removed", "sale": .stopped
            default: .active
            }
        }
    }
}

public extension BayCountyClient {
    func accountability() async throws -> (AccountabilityConsole, Freshness) {
        let r = try await get("/data/accountability.json")
        return (try JSONDecoder().decode(AccountabilityConsole.self, from: r.data), r.freshness)
    }
}
