import Foundation

/// The links between records that the website draws: a contract's company and the vote that approved it,
/// a person's votes, pay and campaign money. Works on whatever dataset rows are loaded.
public enum RecordLinks {
    /// Datasets that name companies by `vendor_id` / `vendor_ids`.
    public static let vendorDatasets = ["contracts", "change-orders", "emergency-purchases", "cra-payments", "vendor-payments", "campaign-contributions-2026"]
    /// Datasets that name people by `person_id` (or, for votes, inside `members`).
    public static let personDatasets = ["officials-pay", "salary-leaders", "campaign-finance", "candidates-2026", "member-votes", "votes"]

    public static func vendorIDs(_ row: Row) -> [String] {
        var ids = row.strings("vendor_ids")
        if let v = row.string("vendor_id"), !ids.contains(v) { ids.insert(v, at: 0) }
        return ids
    }

    public static func personIDs(_ row: Row) -> [String] {
        var ids = [String]()
        if let p = row.string("person_id") { ids.append(p) }
        for m in row["members"]?.arrayValue ?? [] {
            if case .object(let o) = m, let p = o["person_id"]?.stringValue, !ids.contains(p) { ids.append(p) }
        }
        return ids
    }

    public static func voteIDs(_ row: Row) -> [String] {
        row.strings("vote_ids") + (row.string("vote_id").map { [$0] } ?? [])
    }

    /// Rows in each dataset that name this company, in the order of `vendorDatasets`.
    public static func records(forVendor id: String, in rows: [String: [Row]]) -> [(dataset: String, rows: [Row])] {
        vendorDatasets.compactMap { ds in
            let hits = (rows[ds] ?? []).filter { vendorIDs($0).contains(id) }
            return hits.isEmpty ? nil : (ds, hits)
        }
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
            let hits = (rows[ds] ?? []).filter { personIDs($0).contains(id) }
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
