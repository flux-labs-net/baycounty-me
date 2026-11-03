import Foundation

/// The links between records that the website draws: a contract's company and the vote that approved it,
/// a person's votes, pay and campaign money. Works on whatever dataset rows are loaded.
public enum RecordLinks {
    /// Datasets that name companies by `vendor_id` / `vendor_ids`.
    public static let vendorDatasets = ["contracts", "change-orders", "emergency-purchases", "cra-payments", "vendor-payments", "campaign-contributions-2026"]
    /// Datasets that name people by `person_id` (or, for votes, inside `members`; for owner gifts, `candidate_id`).
    public static let personDatasets = ["officials-pay", "salary-leaders", "campaign-finance", "candidates-2026", "member-votes", "votes",
                                        "officeholder-terms", "campaign-history", "business-donor-sunbiz", "owner-gifts",
                                        "contract-dollar-totals", "member-contract-dollars"]

    public static func vendorIDs(_ row: Row) -> [String] {
        var ids = row.strings("vendor_ids")
        if let v = row.string("vendor_id"), !ids.contains(v) { ids.insert(v, at: 0) }
        return ids
    }

    public static func personIDs(_ row: Row) -> [String] {
        var ids = [String]()
        if let p = row.string("person_id") { ids.append(p) }
        if let c = row.string("candidate_id"), !ids.contains(c) { ids.append(c) }
        for m in row["members"]?.arrayValue ?? [] {
            if case .object(let o) = m, let p = o["person_id"]?.stringValue, !ids.contains(p) { ids.append(p) }
        }
        return ids
    }

    public static func voteIDs(_ row: Row) -> [String] {
        row.strings("vote_ids") + (row.string("vote_id").map { [$0] } ?? [])
    }

    /// Rows in each dataset that name this company, in the order of `vendorDatasets`, newest first.
    public static func records(forVendor id: String, in rows: [String: [Row]]) -> [(dataset: String, rows: [Row])] {
        vendorDatasets.compactMap { ds in
            let hits = newestFirst((rows[ds] ?? []).filter { vendorIDs($0).contains(id) }, ds)
            return hits.isEmpty ? nil : (ds, hits)
        }
    }

    static func newestFirst(_ rows: [Row], _ dataset: String) -> [Row] {
        let spec = DatasetSpec.for(dataset)
        return rows.sorted { spec.newestKey($0) > spec.newestKey($1) }
    }

    /// Recorded votes that approved this company's contracts, change orders or emergency purchases.
    public static func votes(forVendor id: String, in rows: [String: [Row]]) -> [Row] {
        let deals = ["contracts", "change-orders", "emergency-purchases"].flatMap { rows[$0] ?? [] }.filter { vendorIDs($0).contains(id) }
        let ids = Set(deals.flatMap(voteIDs))
        let recordIDs = Set(deals.compactMap { $0.string("record_id") })
        return (rows["votes"] ?? []).filter { v in
            (v.string("vote_id").map(ids.contains) ?? false) || v.strings("contract_ids").contains { recordIDs.contains($0) }
        }
        .sorted { ($0.string("date") ?? "") > ($1.string("date") ?? "") }
    }

    public static func records(forPerson id: String, in rows: [String: [Row]]) -> [(dataset: String, rows: [Row])] {
        personDatasets.compactMap { ds in
            let hits = newestFirst((rows[ds] ?? []).filter { personIDs($0).contains(id) }, ds)
            return hits.isEmpty ? nil : (ds, hits)
        }
    }

    /// How a person voted on one recorded vote (from its roll call).
    public static func vote(of personID: String, in voteRow: Row) -> String? {
        for m in voteRow["members"]?.arrayValue ?? [] {
            if case .object(let o) = m, o["person_id"]?.stringValue == personID { return o["vote"]?.stringValue }
        }
        return nil
    }

    public struct Tally: Sendable, Equatable {
        public var yes = 0, no = 0, other = 0
        public var total: Int { yes + no + other }
    }

    /// The dollars in the contract votes one official cast (dataset contract-dollar-totals, one row per government):
    /// yes on items that passed, yes on items that failed, no, the votes behind each, and what is left out.
    public struct ContractDollars: Sendable, Equatable {
        public var yes = 0.0, yesFailed = 0.0, no = 0.0
        public var yesVotes = 0, yesFailedVotes = 0, noVotes = 0, contractVotes = 0, consent = 0, notCounted = 0
        public var first: String?, last: String?
    }

    public static func contractDollars(_ totals: [Row]) -> ContractDollars? {
        guard !totals.isEmpty else { return nil }
        var c = ContractDollars()
        let n = { (r: Row, k: String) in r.number(k) ?? 0 }
        for r in totals {
            c.yes += n(r, "yes_total"); c.yesFailed += n(r, "yes_failed_total"); c.no += n(r, "no_total")
            c.yesVotes += Int(n(r, "yes_votes")); c.yesFailedVotes += Int(n(r, "yes_failed_votes")); c.noVotes += Int(n(r, "no_votes"))
            c.contractVotes += Int(n(r, "contract_votes")); c.consent += Int(n(r, "not_counted_consent"))
            c.notCounted += Int(n(r, "not_counted_no_amount") + n(r, "not_counted_unclear") + n(r, "not_counted_not_spending"))
            if let f = r.string("first_date"), c.first.map({ f < $0 }) ?? true { c.first = f }
            if let l = r.string("last_date"), c.last.map({ l > $0 }) ?? true { c.last = l }
        }
        c.yes = (c.yes * 100).rounded() / 100; c.no = (c.no * 100).rounded() / 100; c.yesFailed = (c.yesFailed * 100).rounded() / 100
        return c.contractVotes > 0 ? c : nil
    }

    public static func tally(_ memberVotes: [Row]) -> Tally {
        memberVotes.reduce(into: Tally()) { t, r in
            switch (r.string("vote") ?? "").lowercased() {
            case "yes": t.yes += 1
            case "no": t.no += 1
            default: t.other += 1
            }
        }
    }
}
