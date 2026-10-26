import Foundation

// Files the site publishes for the app in /data/app (written by site/app_data.py).

public struct AppDataIndex: Codable, Sendable {
    public let version: Int
    public let built: String?
    public let files: [String]
}

// MARK: - Tax model (/data/app/tax.json, the Tax Dollars page's data)

public struct TaxModel: Codable, Sendable {
    public struct Authority: Codable, Sendable {
        public let n: String
        public let g: String
        public let school: Bool
        public let m: [Double?]
        public let rb: [Double?]?
        public let lv: [Double?]?
        public var name: String { n }
        public var group: String { g }
    }

    public struct District: Codable, Sendable, Identifiable, Hashable {
        public let id: String
        public let label: String
        public let stack: [String]
        public let total: [Double]
    }

    public struct Bar: Codable, Sendable {
        public let n: String
        public let g: String
        public let v: Double
    }

    public struct GovBudget: Codable, Sendable, Identifiable {
        public struct Next: Codable, Sendable {
            public let fy: String
            public let total: Double?
            public let gf: Double?
            public let mills: Double?
            public let adopted: Bool?
            public let excl: Bool?
            public let src: [String]?
        }
        public struct Actual: Codable, Sendable {
            public let fy: String
            public let rev: [String: Double]
            public let exp: [String: Double]
            public let pop: Double?
            public let rt: Double?
            public let et: Double?
            public let rs: String?
            public let es: String?
        }
        public let id: String
        public let short: String
        public let name: String
        public let status: [String]
        public let total: Double?
        public let gf: Double?
        public let mills: Double?
        public let levy: Double?
        public let rev: [String: Double]?
        public let exp: [String: Double]?
        public let src: [[String?]]?
        public let ctx: [[String]]?
        public let hist: [[JSONValue]]?
        public let notes: [String]?
        public let next: Next?
        public let mix: [String: Double]?
        public let other: [String: Double]?
        public let act: [Actual]?

        public var statusOK: Bool { status.first == "ok" }
        public var statusText: String { status.dropFirst().first ?? "" }
    }

    public let years: [Int]
    public let fy: [String]
    public let second: [Double]
    public let groups: [[String]]
    public let auth: [String: Authority]
    public let districts: [District]
    public let levy: [String: [Double?]]
    public let bars: [Bar]
    public let govs: [GovBudget]
    public let gaps: [String]?

    public var latest: Int { years.count - 1 }
    public var groupIDs: [String] { groups.compactMap(\.first) }
    public func groupName(_ g: String) -> String { groups.first { $0.first == g }?.last ?? g }
}

// MARK: - Amendment 3 (/data/app/amendment3.json)

public struct Amendment3Model: Codable, Sendable {
    public struct Gov: Codable, Sendable, Identifiable {
        public let n: String
        public let levy: Double
        public let gf: Double?
        public let imp: [Double]
        public var id: String { n }
    }
    public let districts: [TaxModel.District]
    public let auth: [String: TaxModel.Authority]
    public let groups: [[String]]
    public let second: Double
    public let govs: [Gov]
    public let state: [Double]
    /// Election day ("2026-11-03"); older files don't carry it.
    public let vote: String?

    public static let fiscalYears = ["FY2028", "FY2029", "FY2030", "FY2031", "FY2032"]

    /// Revenue Bay County's local governments would lose in one fiscal year (index into `fiscalYears`), state estimate.
    public func localImpact(_ year: Int) -> Double {
        govs.compactMap { $0.imp.indices.contains(year) ? $0.imp[year] : nil }.reduce(0, +)
    }

    /// True until the end of election day, in Bay County time.
    public func isBeforeVote(now: Date = Date()) -> Bool {
        guard let vote, let day = Dates.parse(vote) else { return false }
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "America/Chicago")!
        guard let end = cal.date(byAdding: .day, value: 1, to: cal.startOfDay(for: day)) else { return false }
        return now < end
    }
}

// MARK: - Address lookup tables (/data/app/address.json)

public struct AddressModel: Codable, Sendable {
    public struct District: Codable, Sendable {
        public let label: String
        public let stack: [String]
        public let total: Double
    }
    public struct Auth: Codable, Sendable {
        public let n: String
        public let g: String
        public let school: Bool
        public let m: Double
    }
    public struct CRATotal: Codable, Sendable {
        public let spent: Double
        public let n: Int
    }
    public struct GovLink: Codable, Sendable {
        public let s: String
        public let slug: String
        public let c: String?
        public let f: String?
        public let cra: String?
        public let b: Bool
    }
    public let taxdist: [String: String]
    public let craAgency: [String: String]
    public let cra: [String: CRATotal]
    public let districts: [String: District]
    public let auth: [String: Auth]
    public let groups: [[String]]
    public let fy: String
    public let second2026: Double
    public let navLabel: [String: String]
    public let shards: [String: Int]
    public let govs: [String: GovLink]
    public let craId: [String: String]
    /// Government key -> [[member name as in recorded votes, yes count, no count]]
    public let members: [String: [[JSONValue]]]
    public let elections: Bool?
}

// MARK: - Glossary, pages, updates

public struct Glossary: Codable, Sendable {
    public struct Group: Codable, Sendable, Identifiable, Hashable {
        public let id: String
        public let name: String
    }
    public struct Term: Codable, Sendable, Identifiable, Hashable {
        public let id: String
        public let group: String
        public let term: String
        public let simple: String
        public let more: String?
        public let example: String?

        /// The word as it appears in running text: "Community Redevelopment Agency (CRA)" -> ["Community Redevelopment Agency", "CRA"].
        public var matchWords: [String] {
            var out = [String]()
            let base = term.replacingOccurrences(of: #"\s*\([^)]*\)"#, with: "", options: .regularExpression)
            out.append(base)
            if let r = term.range(of: #"\(([^)]+)\)"#, options: .regularExpression) {
                out.append(String(term[r]).trimmingCharacters(in: CharacterSet(charactersIn: "()")))
            }
            return out.filter { $0.count >= 3 }
        }
    }
    public let groups: [Group]
    public let terms: [Term]

    /// Glossary terms that appear in a piece of text, in the order they first appear.
    public func terms(in text: String) -> [Term] {
        let lower = text.lowercased()
        return terms.compactMap { t -> (Term, String.Index)? in
            for w in t.matchWords {
                if let r = lower.range(of: w.lowercased()), Self.isWordBoundary(lower, r) { return (t, r.lowerBound) }
            }
            return nil
        }
        .sorted { $0.1 < $1.1 }
        .map(\.0)
    }

    static func isWordBoundary(_ s: String, _ r: Range<String.Index>) -> Bool {
        let before = r.lowerBound == s.startIndex ? nil : s[s.index(before: r.lowerBound)]
        let after = r.upperBound == s.endIndex ? nil : s[r.upperBound]
        let ok: (Character?) -> Bool = { c in c.map { !$0.isLetter && !$0.isNumber } ?? true }
        return ok(before) && ok(after)
    }
}

public struct PageInfo: Codable, Sendable, Identifiable, Hashable {
    public struct Explainer: Codable, Sendable, Hashable {
        public let heading: String
        public let paragraphs: [String]
    }
    public let path: String
    public let title: String
    public let description: String
    public let lede: String?
    public let explainer: Explainer?
    public var id: String { path }
    public var url: URL { BayCountyClient.site.appendingPathComponent(path == "/" ? "" : String(path.dropFirst())) }
}

public struct SiteUpdate: Codable, Sendable, Identifiable, Hashable {
    public let date: String
    public let title: String
    public let text: String
    public let pages: [String]
    public var id: String { date + title }
}

// MARK: - Companies and people

public struct VendorDirectory: Codable, Sendable {
    public struct Vendor: Codable, Sendable, Identifiable, Hashable {
        public let id: String
        public let name: String
        public let aliases: [String]
        public let gov_ids: [String]
        public let records: [String: Int]
        public let type: String?
        public let page: String?
        public var recordCount: Int { records.values.reduce(0, +) }
        public var pageURL: URL? { page.map { BayCountyClient.site.appendingPathComponent(String($0.dropFirst())) } }
    }
    public let about: String?
    public let vendors: [Vendor]
}

public struct PeopleDirectory: Codable, Sendable {
    public struct Person: Codable, Sendable, Identifiable, Hashable {
        public struct Role: Codable, Sendable, Hashable {
            public let role: String?
            public let gov_id: String?
            public let seat: String?
        }
        public let id: String
        public let name: String
        public let district: String?
        public let gov_ids: [String]
        /// The site's one line about them ("County Commissioner, District 2, Bay County · running again in 2026").
        public var subtitle: String? = nil
        /// Elected official, Department leader, Candidate, Former official or Past candidate.
        public var label: String? = nil
        /// The People page's filter groups: elected, candidate, staff, past.
        public var kinds: [String]? = nil
        public let roles: [Role]

        /// Roles with the duplicates removed. Sources word the same office differently
        /// ("board member", "County Commissioner", "officeholder: Bay County Commission, District 5"),
        /// so within one government the generic wordings give way to a specific one,
        /// and a role that is a shorter form of another ("County Commissioner") is dropped.
        public var mainRoles: [Role] {
            func generic(_ r: Role) -> Bool {
                let t = (r.role ?? "").lowercased()
                return t == "board member" || t.hasPrefix("officeholder:")
            }
            var out: [Role] = []
            var govs: [String?] = []
            for r in roles where !govs.contains(r.gov_id) { govs.append(r.gov_id) }
            for g in govs {
                let here = roles.filter { $0.gov_id == g }
                let specific = here.filter { !generic($0) }
                var keep = specific.isEmpty ? here : specific
                // A past race ("2020 candidate: ...") gives way to any other role in the same government.
                func pastRace(_ r: Role) -> Bool {
                    let t = r.role ?? ""
                    return t.range(of: #"^20\d\d candidate:"#, options: .regularExpression) != nil && !t.hasPrefix("2026 candidate")
                }
                if keep.contains(where: { !pastRace($0) }) { keep = keep.filter { !pastRace($0) } }
                if specific.isEmpty, keep.contains(where: { ($0.role ?? "").lowercased().hasPrefix("officeholder:") }) {
                    keep = keep.filter { ($0.role ?? "").lowercased().hasPrefix("officeholder:") }
                }
                // Candidate filings and the elections office name some seats two ways.
                func norm(_ r: Role) -> String {
                    var t = (r.role ?? "").lowercased()
                    for w in ["city of ", "bay district ", "residential golf "] { t = t.replacingOccurrences(of: w, with: "") }
                    return t.replacingOccurrences(of: "commissioner, ward", with: "commission, ward")
                }
                let texts = keep.map(norm)
                var seen = Set<String>()
                for r in keep {
                    let t = norm(r)
                    if texts.contains(where: { $0 != t && $0.hasPrefix(t) }) { continue }
                    if seen.insert(t).inserted { out.append(r) }
                }
            }
            return out
        }

        public var headline: String {
            if let subtitle, !subtitle.isEmpty { return subtitle }
            let main = mainRoles
            let r = main.first { r in let t = r.role ?? ""; return !t.hasPrefix("former") && !t.hasPrefix("2026 candidate") }
                ?? main.first { !($0.role ?? "").hasPrefix("former") } ?? main.first
            let gov = (r?.gov_id ?? gov_ids.first).flatMap { Governments.names[$0] } ?? ""
            let role = (r?.role ?? "").prefix(1).uppercased() + (r?.role ?? "").dropFirst()
            return [role, gov].filter { !$0.isEmpty }.joined(separator: ", ")
        }
    }
    public let about: String?
    public let people: [Person]
}

public struct DonorContracts: Codable, Sendable {
    public struct Match: Codable, Sendable, Identifiable, Hashable {
        public let contributor: String?
        public let vendor: String?
        public let vendor_id: String?
        public let candidate: String?
        public let person_id: String?
        public let office: String?
        public let office_gov_id: String?
        public let election: String?
        public let contribution_amount: Double?
        public let contribution_dates: [String]?
        public let contract_ids_or_descriptions: [String]?
        public let record_ids: [String]?
        public let contract_source_urls: [String]?
        public let contract_government: String?
        public let contract_gov_id: String?
        public let match_confidence: String?
        public let note: String?
        public let campaign_report_url: String?
        public let same_government_as_office: Bool?
        public var id: String { [contributor, candidate, election, (record_ids ?? []).joined(separator: ",")].compactMap { $0 }.joined(separator: "|") }
    }
    public let as_of: String?
    public let method: String?
    public let matches: [Match]
}

/// The Money Map page's data: business donors, the officials they gave to, their contracts and the votes on them.
public struct MoneyMap: Codable, Sendable {
    public struct Official: Codable, Sendable, Identifiable, Hashable {
        public let id: Int
        public let n: String
        public let off: String?
        public let g: String
        public let raised: Double?
        public let ind: Double?
        public let indn: Int?
        public let url: String?
    }
    public struct Donor: Codable, Sendable, Identifiable, Hashable {
        public let id: Int
        public let n: String
        public let t: String?
        public let vp: String?
        public let k: Bool?
        public let tot: Double?
        /// Holds local government contracts.
        public var holdsContracts: Bool { k ?? false }
    }
    public struct Gift: Codable, Sendable, Hashable {
        public let d: Int
        public let o: Int
        public let a: Double
        public let same: Bool?
        public let dates: [String]?
    }
    public struct Contract: Codable, Sendable, Hashable {
        public let d: Int
        public let g: String
        public let a: Double?
        public let items: [String]?
        public let urls: [String]?
        public let ent: String?
    }
    public struct VoteGroup: Codable, Sendable, Hashable, Identifiable {
        public struct Member: Codable, Sendable, Hashable {
            public let n: String
            public let vote: String?
            public let o: Int?
            public let gift: Double?
            public let when: String?
        }
        public let d: Int
        public let g: String
        public let date: String
        public let h: String?
        public let amount: Double?
        public let outcome: String?
        public let tally: String?
        public let consent: Bool?
        public let url: String?
        public let roll: [Member]
        public var id: String { "\(d)|\(date)|\(h ?? "")" }
    }
    public let officials: [Official]
    public let donors: [Donor]
    public let gifts: [Gift]
    public let contracts: [Contract]
    public let vgroups: [VoteGroup]
    public let govs: [String: String]?
    public let as_of: String?

    public func donor(_ id: Int) -> Donor? { donors.first { $0.id == id } }
    public func official(_ id: Int) -> Official? { officials.first { $0.id == id } }
    public func gifts(toOfficial id: Int) -> [Gift] { gifts.filter { $0.o == id }.sorted { $0.a > $1.a } }
    public func gifts(fromDonor id: Int) -> [Gift] { gifts.filter { $0.d == id }.sorted { $0.a > $1.a } }
    public func contracts(forDonor id: Int) -> [Contract] { contracts.filter { $0.d == id } }

    /// Total business giving to each government's officials, per donor: the heat map's cells.
    public func heat(topDonors limit: Int = 15) -> (donors: [Donor], govs: [String], cells: [Int: [String: Double]]) {
        var cells: [Int: [String: Double]] = [:]
        for g in gifts {
            guard let o = official(g.o) else { continue }
            cells[g.d, default: [:]][o.g, default: 0] += g.a
        }
        let top = donors.filter { cells[$0.id] != nil }
            .sorted { (cells[$0.id]?.values.reduce(0, +) ?? 0) > (cells[$1.id]?.values.reduce(0, +) ?? 0) }
            .prefix(limit)
        let govs = Array(Set(officials.map(\.g))).sorted { (Governments.order.firstIndex(of: $0) ?? 99) < (Governments.order.firstIndex(of: $1) ?? 99) }
        return (Array(top), govs, cells)
    }
}

extension Governments {
    public static let order = ["county", "schools", "pc", "pcb", "lh", "cw", "sp", "parker", "mb"]
}

// MARK: - Client

extension BayCountyClient {
    public func appData<T: Decodable>(_ name: String, as type: T.Type = T.self) async throws -> (T, Freshness) {
        let r = try await get("/data/app/\(name)")
        return (try JSONDecoder().decode(T.self, from: r.data), r.freshness)
    }
}

/// The People list's filter groups, the same chips as the site's /people page.
public enum PeopleKind: String, Sendable, CaseIterable, Identifiable {
    case everyone, elected, candidate, staff, past
    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .everyone: "Everyone"
        case .elected: "Elected"
        case .candidate: "2026 candidates"
        case .staff: "Department leaders"
        case .past: "Past candidates"
        }
    }

    public func includes(_ p: PeopleDirectory.Person) -> Bool {
        self == .everyone || (p.kinds ?? ["elected"]).contains(rawValue)
    }
}
