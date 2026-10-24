import Foundation

/// A person, company, nonprofit, business or government a record names, with its BayCounty.me profile.
/// `kind:key` ids and profile paths follow site/entity_graph.py (`page_url`).
public struct EntityRef: Hashable, Sendable, Identifiable {
    public let kind: String
    public let key: String
    public let name: String
    /// What this entity is to the record ("Nonprofit", "Board member").
    public let label: String

    public var id: String { "\(kind):\(key)" }

    public init(kind: String, key: String, name: String, label: String) {
        self.kind = kind; self.key = key; self.name = name; self.label = label
    }

    /// The profile page, by the site's one link rule (vendors with their own page and governments open natively in the app).
    public var profilePath: String {
        kind == "person" ? "/people/\(key)" : "/profile/\(kind)/\(key)"
    }

    public var profileURL: URL? {
        let allowed = CharacterSet.urlPathAllowed.subtracting(CharacterSet(charactersIn: "?#"))
        return URL(string: "https://baycounty.me" + (profilePath.addingPercentEncoding(withAllowedCharacters: allowed) ?? profilePath))
    }

    public var symbol: String {
        switch kind {
        case "person", "member": "person"
        case "nonprofit": "heart"
        case "business", "vendor": "building.2"
        case "committee": "megaphone"
        case "gov": "building.columns"
        default: "circle.hexagongrid"
        }
    }

    /// A parsed "kind:key" id, as entity-profiles and entity-connections carry them.
    public static func parse(_ id: String?, name: String?, label: String? = nil) -> EntityRef? {
        guard let id, let i = id.firstIndex(of: ":"), let name, !name.isEmpty else { return nil }
        let kind = String(id[..<i]), key = String(id[id.index(after: i)...])
        guard !kind.isEmpty, !key.isEmpty else { return nil }
        return EntityRef(kind: kind, key: key, name: Format.orgName(name), label: label ?? Self.kindLabel(kind))
    }

    public static func kindLabel(_ kind: String) -> String {
        ["person": "Official or candidate", "member": "Board member", "nonprofit": "Nonprofit", "business": "Registered business",
         "vendor": "Company", "committee": "Political committee", "gov": "Government"][kind] ?? kind.capitalizingFirstLetter
    }
}

/// How a record's detail screen presents one row, worked out from the row alone (plus its own list for related rows):
/// the people and organizations it names, its tags, headline numbers, years on file and related records.
/// Every list gets this; datasets that need more say so in the tables below.
public enum RecordProfile {

    // MARK: - Who and what the record names

    /// Id columns paired with the column holding the name, and the kind of entity they point to.
    /// `person_id` means an elected official in most lists, but a board member in the nonprofit lists.
    static func refColumns(_ datasetID: String) -> [(id: String, name: String, kind: String)] {
        let member = datasetID.hasPrefix("nonprofit") || datasetID == "charity-registrations"
        var cols: [(String, String, String)] = [
            ("nonprofit_id", "nonprofit", "nonprofit"),
            ("doc_number", "business", "business"),
        ]
        if member { cols.insert(("person_id", "person", "member"), at: 0) }
        if datasetID == "nonprofit-officials" { cols.insert(("person_id", "official", "person"), at: 0) }
        return cols
    }

    /// The entities this record names, in reading order (the person first, then the organization), not counting itself.
    public static func refs(_ datasetID: String, _ row: Row) -> [EntityRef] {
        var out = [EntityRef]()
        if datasetID == "entity-connections" {
            for side in ["from", "to"] {
                if let r = EntityRef.parse(row.string("\(side)_id"), name: row.string("\(side)_name")) { out.append(r) }
            }
            return out
        }
        for c in refColumns(datasetID) {
            guard let key = row.string(c.id), let name = row.string(c.name) else { continue }
            if datasetID == "nonprofits" && c.kind == "nonprofit" { continue }
            let k = c.kind == "business" ? key.lowercased() : key
            out.append(EntityRef(kind: c.kind, key: k, name: c.kind == "member" || c.kind == "person" ? name : Format.orgName(name),
                                 label: EntityRef.kindLabel(c.kind)))
        }
        return out
    }

    /// The record's own subject, when it has a profile (a nonprofit's row, a board member's seat, an entity profile).
    public static func subject(_ datasetID: String, _ row: Row) -> EntityRef? {
        switch datasetID {
        case "nonprofits", "charity-registrations":
            guard let id = row.string("nonprofit_id"), let n = row.string("name") else { return nil }
            return EntityRef(kind: "nonprofit", key: id, name: Format.orgName(n), label: "Nonprofit")
        case "entity-profiles":
            return EntityRef.parse(row.string("entity_id"), name: row.string("name"), label: row.string("kind_label"))
        default:
            return refs(datasetID, row).first { $0.kind == "member" || $0.kind == "person" }
        }
    }

    // MARK: - Header

    /// The record's title, with ALL-CAPS organization names in normal case.
    public static func title(_ datasetID: String, _ row: Row) -> String { DatasetSpec.for(datasetID).title(row) }

    /// Columns that hold an organization's name, as filings write it.
    public static let orgColumns: Set<String> = ["nonprofit", "business", "recipient", "grantor", "organization"]

    /// The line under the title: a person's roles ("Treasurer and Director"), else the list's subtitle.
    public static func roleLine(_ datasetID: String, _ row: Row) -> String? {
        if let t = row.string("titles") { return sentenceList(t.components(separatedBy: ", ")) }
        let s = DatasetSpec.for(datasetID).subtitle(row)
        return s.isEmpty ? nil : s
    }

    /// "Treasurer, Director, Trustee" -> "Treasurer, Director and Trustee".
    public static func sentenceList(_ items: [String]) -> String {
        let xs = items.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        guard xs.count > 1 else { return xs.first ?? "" }
        return xs.dropLast().joined(separator: ", ") + " and " + xs.last!
    }

    /// Initials for a person's avatar ("Kathy Bass" -> "KB"), or nil when the record isn't about a person.
    public static func initials(_ datasetID: String, _ row: Row) -> String? {
        let titleKey = DatasetSpec.for(datasetID).titleKeys.first
        let isPerson = ["person", "official"].contains(titleKey)
            || (datasetID == "entity-profiles" && ["person", "member"].contains(row.string("kind") ?? ""))
        guard isPerson else { return nil }
        let words = DatasetSpec.for(datasetID).title(row).split(separator: " ").filter { $0.first?.isLetter == true }
        guard let f = words.first?.first else { return nil }
        let l = words.count > 1 ? words.last?.first.map(String.init) ?? "" : ""
        return (String(f) + l).uppercased()
    }

    public enum Tone: Sendable { case good, accent, neutral, warn }

    public struct Chip: Hashable, Sendable {
        public let text: String
        public let tone: Tone
    }

    /// Short tags for the header: current or past, the role, where it was filed.
    public static func chips(_ datasetID: String, _ row: Row) -> [Chip] {
        var out = [Chip]()
        if let cur = row.bool("current") { out.append(Chip(text: cur ? "Current" : "Past", tone: cur ? .good : .neutral)) }
        if let role = row.string("role"), !role.lowercased().hasPrefix("past") || row.bool("current") == nil {
            out.append(Chip(text: role.replacingOccurrences(of: "Past ", with: "").capitalizingFirstLetter, tone: .accent))
        }
        for s in (row.string("sources") ?? "").components(separatedBy: ", ") where !s.isEmpty && !s.hasPrefix("http") {
            out.append(Chip(text: s, tone: .neutral))
        }
        for key in ["status", "sunbiz_status", "fdacs_status", "kind", "match"] where key != DatasetSpec.for(datasetID).badgeKey {
            if let v = row.string(key), v.count < 32 {
                let t = Format.value(row[key]!, column: key)
                if !out.contains(where: { $0.text == t }) { out.append(Chip(text: t, tone: .neutral)) }
            }
        }
        return out
    }

    // MARK: - Numbers and years

    public struct Fact: Hashable, Sendable {
        public let value: String
        public let label: String
    }

    /// Up to four headline numbers. The record's main amount is shown separately.
    public static func facts(_ datasetID: String, _ row: Row) -> [Fact] {
        var out = [Fact]()
        if let pay = row.number("compensation"), pay > 0 {
            out.append(Fact(value: Format.compactMoney(pay), label: "Reported pay" + (row.number("compensation_year").map { " (\(Int($0)))" } ?? "")))
        }
        if let h = row.number("hours_per_week"), h > 0 { out.append(Fact(value: Format.number(h), label: "Hours a week")) }
        if let y = years(row), out.count < 2 {
            out.append(Fact(value: String(y.lowerBound), label: "On file since"))
            if out.count < 2 { out.append(Fact(value: String(y.count), label: y.count == 1 ? "Year on file" : "Years on file")) }
        }
        if let n = row.number("other_current_boards") {
            out.append(Fact(value: Format.number(n), label: n == 1 ? "Other local board" : "Other local boards"))
        }
        let counts: [(String, String)] = [("board_members_listed", "Board members"), ("shares_board_with", "Share a board member"),
                                          ("returns_on_file", "IRS returns"), ("employees", "Employees"), ("connections", "Connections"),
                                          ("records", "Records"), ("officers_listed", "Officers listed")]
        for (k, label) in counts where out.count < 4 {
            if let n = row.number(k), n > 0 { out.append(Fact(value: Format.number(n), label: label)) }
        }
        let money: [(String, String)] = [("total_revenue", "Revenue"), ("total_assets", "Assets"), ("gov_dollars_in_records", "From governments")]
        for (k, label) in money where out.count < 4 && k != DatasetSpec.for(datasetID).amountKey(row) {
            if let n = row.number(k), n != 0 { out.append(Fact(value: Format.compactMoney(n), label: label)) }
        }
        return Array(out.prefix(4))
    }

    /// The years a record covers (first_year to last_year), when it has them.
    public static func years(_ row: Row) -> ClosedRange<Int>? {
        guard let a = row.number("first_year").map(Int.init) ?? row.number("last_year").map(Int.init) else { return nil }
        let b = row.number("last_year").map(Int.init) ?? a
        return min(a, b)...max(a, b)
    }

    // MARK: - Related records

    /// Other rows that belong with this one: the rest of a board, a person's other boards, a nonprofit's board.
    public struct Group: Hashable, Sendable {
        public let title: String
        public let datasetID: String
        public let column: String
        public let value: String
    }

    public static func groups(_ datasetID: String, _ row: Row) -> [Group] {
        func g(_ title: String, _ ds: String, _ col: String, _ from: String? = nil) -> Group? {
            row.string(from ?? col).map { Group(title: title, datasetID: ds, column: col, value: $0) }
        }
        switch datasetID {
        case "nonprofit-board-members":
            return [g("Other boards", datasetID, "person_id"), g("Also on this board", datasetID, "nonprofit_id")].compactMap { $0 }
        case "nonprofit-board-businesses":
            return [g("Their nonprofit boards", "nonprofit-board-members", "person_id"), g("Their businesses", datasetID, "person_id")].compactMap { $0 }
        case "nonprofits", "charity-registrations":
            return [g("Board", "nonprofit-board-members", "nonprofit_id")].compactMap { $0 }
        default:
            return []
        }
    }

    /// The rows of one group, current seats first, without the record itself.
    public static func members(of group: Group, in rows: [Row], excluding id: Int?, sameDataset: Bool) -> [Row] {
        rows.filter { $0.string(group.column) == group.value && !(sameDataset && $0.id == id) }
            .sorted { a, b in
                let ca = a.bool("current") ?? false, cb = b.bool("current") ?? false
                if ca != cb { return ca }
                return (a.number("last_year") ?? 0) > (b.number("last_year") ?? 0)
            }
    }

    /// How a related row reads in a group: the person on a board's list, the nonprofit in a person's list.
    public static func groupRowTitle(_ group: Group, _ row: Row) -> String {
        if group.datasetID == "nonprofit-board-members" {
            return group.column == "person_id" ? Format.orgName(row.string("nonprofit") ?? "Nonprofit") : (row.string("person") ?? "Board member")
        }
        return title(group.datasetID, row)
    }

    public static func groupRowDetail(_ group: Group, _ row: Row) -> String {
        var parts = [String]()
        if let t = row.string("titles") { parts.append(sentenceList(t.components(separatedBy: ", "))) }
        if let y = years(row) { parts.append(y.count == 1 ? String(y.lowerBound) : "\(y.lowerBound)–\(y.upperBound)") }
        if row.bool("current") == false { parts.append("past") }
        if parts.isEmpty { parts.append(DatasetSpec.for(group.datasetID).subtitle(row)) }
        return parts.joined(separator: " · ")
    }

    // MARK: - All fields

    /// Columns the header, numbers, links and groups already show, so the folded list of every field doesn't repeat them.
    public static let shownColumns: Set<String> = [
        "person", "nonprofit", "titles", "role", "current", "first_year", "last_year", "sources", "other_current_boards",
        "compensation", "compensation_year", "hours_per_week", "county", "nonprofit_id", "doc_number", "entity_id",
        "from_id", "to_id", "from_url", "to_url", "from_kind", "to_kind", "page_url", "link_id",
    ]

    /// Every remaining readable field, with organization names in normal case.
    public static func otherFields(_ datasetID: String, _ row: Row, columns: [DatasetInfo.Column]) -> [(label: String, value: String)] {
        let titleKey = DatasetSpec.for(datasetID).titleKeys.first { row.string($0) != nil }
        let names = columns.isEmpty ? row.values.keys.sorted() : columns.map(\.name)
        return names.compactMap { name in
            guard name != titleKey, !shownColumns.contains(name), !DatasetSpec.hiddenColumns.contains(name), !name.hasSuffix("_url"),
                  let v = row[name], !v.isEmpty else { return nil }
            let s = Format.value(v, column: name)
            return (Format.label(name), orgColumns.contains(name) ? Format.orgName(s) : s)
        }
    }
}

extension Format {
    /// Words kept in capitals when an ALL-CAPS organization name is recased.
    static let keepUpper: Set<String> = [
        "USA", "US", "U.S.", "VFW", "YMCA", "YWCA", "PTA", "PTO", "PTSA", "HOA", "FL", "FSU", "UWF", "FAMU", "UF", "NAACP", "AMVETS",
        "LLC", "LLLP", "LP", "PA", "PC", "PLLC", "II", "III", "IV", "VI", "PCB", "NW", "NE", "SW", "SE", "ARC", "CDC", "CRA", "DBA",
        "AARP", "NAMI", "ROTC", "JROTC", "MOAA", "NFP", "CPA", "AFB", "USO", "AAUW", "BPOE", "IOOF", "AME", "CME", "GOP", "NRA",
        "AA", "NA", "4-H", "EMS", "PAL", "SPCA", "TV", "FM", "AM", "UMC", "ELCA", "HUD", "VA", "WWII", "AMC", "NJROTC", "BSA", "ESA",
    ]
    static let lowerWords: Set<String> = ["OF", "THE", "AND", "FOR", "IN", "AT", "ON", "A", "AN", "TO", "BY", "DE", "OR", "WITH"]

    /// "455 HARRISON AVENUE GROUP, INC." -> "455 Harrison Avenue Group, Inc." Names with any lower-case letter are left alone.
    public static func orgName(_ name: String) -> String {
        guard name.contains(where: \.isLetter), !name.contains(where: \.isLowercase) else { return name }
        var first = true
        return name.split(separator: " ", omittingEmptySubsequences: false).map { raw -> String in
            let w = String(raw)
            defer { if !w.isEmpty { first = false } }
            return caseWord(w, first: first)
        }.joined(separator: " ")
    }

    static func caseWord(_ w: String, first: Bool) -> String {
        // keep leading and trailing punctuation as written
        let core = w.trimmingCharacters(in: CharacterSet(charactersIn: ",.;:()\"'&!?"))
        guard !core.isEmpty, let r = w.range(of: core) else { return w }
        let pre = String(w[..<r.lowerBound]), post = String(w[r.upperBound...])
        return pre + caseCore(core, first: first, wholeWord: w) + post
    }

    static func caseCore(_ c: String, first: Bool, wholeWord: String) -> String {
        if keepUpper.contains(c) || keepUpper.contains(wholeWord.trimmingCharacters(in: CharacterSet(charactersIn: ",;:()"))) { return c }
        if !first, lowerWords.contains(c) { return c.lowercased() }
        for sep in ["-", "/"] where c.contains(sep) {
            return c.components(separatedBy: sep).enumerated().map { caseCore($0.element, first: first && $0.offset == 0, wholeWord: $0.element) }
                .joined(separator: sep)
        }
        if c.first?.isNumber == true { return c.lowercased() }  // "1ST", "21ST"
        let letters = c.filter(\.isLetter)
        let abbreviations: Set<String> = ["ST", "MT", "DR", "JR", "SR", "MR", "MRS", "MS", "FT", "PT", "BLVD", "HWY", "CTR"]
        if letters.count >= 2, !abbreviations.contains(c), !letters.contains(where: { "AEIOUY".contains($0) }) { return c }  // initialisms like "PCB", "NWF"
        if c.hasPrefix("MC"), c.count > 3 { return "Mc" + c.dropFirst(2).prefix(1) + c.dropFirst(3).lowercased() }
        if c.hasPrefix("O'"), c.count > 2 { return "O'" + c.dropFirst(2).prefix(1) + c.dropFirst(3).lowercased() }
        return c.prefix(1) + c.dropFirst().lowercased()
    }
}
