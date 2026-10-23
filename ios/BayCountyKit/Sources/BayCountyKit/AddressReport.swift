import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Everything My Address shows for one address. Built by `AddressReport.load`, which runs every lookup at once.
public struct AddressReport: Sendable {
    public let match: AddressMatch
    public let parcel: GISClient.Feature?
    /// The 2026 roll's [school taxable, non-school taxable, homestead, additional homestead, other exemptions], when on file.
    public let exemptions: [Double]?
    /// Flat fees on the FY2026 tax bill: [(levy code, dollars)]. nil = couldn't load.
    public let fees: [(code: String, amount: Double)]?
    public let cityName: String?
    public let cra: GISClient.Feature?
    public let craChecked: Bool
    public let commission: GISClient.Feature?
    public let cityCouncil: GISClient.Feature?
    public let schoolBoard: GISClient.Feature?
    public let floridaHouse: GISClient.Feature?
    public let floridaSenate: GISClient.Feature?
    public let usHouse: GISClient.Feature?
    public let elementary: String?
    public let middle: String?
    public let high: String?
    public let flood: GISClient.Flood?
    public let floodChecked: Bool
    public let evacuationZone: String?
    public let mosquito: GISClient.Feature?
    public let touristTaxArea: String?
    public let fireStation: (feature: GISClient.Feature, miles: Double)?
    public let library: (feature: GISClient.Feature, miles: Double)?
    public let park: (feature: GISClient.Feature, miles: Double)?
    public let development: Development?

    public var govKey: String { AddressReport.govKey(cityName: cityName) }

    static func govKey(cityName: String?) -> String {
        guard let c = cityName else { return "county" }
        return Governments.names.first { $0.value == c }?.key ?? "county"
    }

    // MARK: - Property tax

    public struct TaxParts: Sendable, Equatable {
        public let homestead: Bool
        public let assessed: Double
        public let just: Double
        public let exempt: Double
        public let schoolTaxable: Double
        public let otherTaxable: Double
        public let homesteadAmount: Double
        public let additionalHomestead: Double
        public let otherExemptions: Double
        public let fromRoll: Bool
        public let fullyExempt: Bool
    }

    /// Taxable values for the parcel (address.js taxParts): the certified 2026 roll when on file, else worked out from GIS values.
    public static func taxParts(parcel p: GISClient.Feature, exemptions ex: [Double]?, second2026: Double) -> TaxParts {
        let assessed = p.n("VASTOTAL") ?? 0, just = p.n("VASJUST") ?? 0
        if let ex, ex.count >= 5 {
            let (tsd, tnsd, h1, h2, oth) = (ex[0], ex[1], ex[2], ex[3], ex[4])
            let exempt = h1 + h2 + oth
            return TaxParts(homestead: h1 > 0, assessed: assessed, just: just, exempt: exempt, schoolTaxable: tsd, otherTaxable: tnsd,
                            homesteadAmount: h1, additionalHomestead: h2, otherExemptions: oth, fromRoll: true,
                            fullyExempt: tsd == 0 && tnsd == 0 && exempt > 0)
        }
        let codes = p.s("DEXEMPTS") ?? ""
        let hx = codes.range(of: #"\bHX\b"#, options: .regularExpression) != nil
        let exempt = p.n("VASEXEMPT") ?? 0, taxable = p.n("VASTAXABLE") ?? 0
        let second = hx ? min(max(assessed - 50_000, 0), second2026) : 0
        let other = hx ? max(0, exempt - min(assessed, 25_000) - second) : exempt
        let fullEx = taxable == 0 && codes.range(of: #"\b(13|14|VT|96)\b"#, options: .regularExpression) != nil
        let school = fullEx ? 0 : hx ? max(0, taxable + second) : max(0, just - exempt)
        return TaxParts(homestead: hx, assessed: assessed, just: just, exempt: exempt, schoolTaxable: school, otherTaxable: taxable,
                        homesteadAmount: hx ? min(assessed, 25_000) : 0, additionalHomestead: second, otherExemptions: other,
                        fromRoll: false, fullyExempt: fullEx)
    }

    public struct TaxEstimate: Sendable {
        public let districtID: String
        public let districtLabel: String
        public let mills: Double
        /// The tax district came from the parcel record (not inferred from the city on the map).
        public let exact: Bool
        public let parts: TaxParts
        public let lines: [TaxCalculator.Line]
        public var total: Double { lines.reduce(0) { $0 + $1.amount } }
        public func byGroup(_ groups: [String]) -> [TaxCalculator.GroupAmount] {
            groups.map { g in TaxCalculator.GroupAmount(group: g, amount: lines.filter { $0.group == g }.reduce(0) { $0 + $1.amount }) }.filter { $0.amount > 0.5 }
        }
        public var cityName: String? { lines.first { $0.group == "city" }?.name }
    }

    public func taxEstimate(_ m: AddressModel) -> TaxEstimate? {
        guard let p = parcel else { return nil }
        let code = (p.s("DTAXDIST") ?? "").trimmingCharacters(in: .whitespaces)
        var id = m.taxdist[code]
        let exact = id != nil
        if id == nil { id = cityName.flatMap { m.districts[$0] != nil ? $0 : nil } ?? "unincorporated" }
        guard let distID = id, let d = m.districts[distID] else { return nil }
        let t = Self.taxParts(parcel: p, exemptions: exemptions, second2026: m.second2026)
        let lines = d.stack.compactMap { aid -> TaxCalculator.Line? in
            guard let a = m.auth[aid], a.m > 0 else { return nil }
            let base = a.school ? t.schoolTaxable : t.otherTaxable
            return TaxCalculator.Line(id: aid, name: a.n, group: a.g, mills: a.m, base: base, amount: base / 1000 * a.m)
        }
        return TaxEstimate(districtID: distID, districtLabel: d.label, mills: d.total, exact: exact, parts: t, lines: lines)
    }

    /// Amendment 3 savings for a homestead: county, city and district taxes with the full $250,000 exemption on today's value.
    public func amendment3Savings(_ m: AddressModel) -> (savings: Double, toZero: Bool)? {
        guard let e = taxEstimate(m), e.parts.homestead, let d = m.districts[e.districtID] else { return nil }
        let nonM = d.stack.compactMap { m.auth[$0] }.filter { !$0.school }.reduce(0) { $0 + $1.m }
        let after = max(0, e.parts.assessed - 250_000 - e.parts.otherExemptions)
        return ((e.parts.otherTaxable - after) / 1000 * nonM, after == 0)
    }

    /// Florida DOR land-use codes where someone could live and claim a homestead.
    public var isResidential: Bool {
        (parcel?.s("DORAPPCODE") ?? "").range(of: #"^0[12458]"#, options: .regularExpression) != nil
    }

    // MARK: - Local officials and their recorded votes

    static func normName(_ s: String) -> [String] {
        s.lowercased().replacingOccurrences(of: #"[.,]"#, with: " ", options: .regularExpression)
            .split(separator: " ").map(String.init)
            .filter { $0.count > 1 && !["jr", "sr", "ii", "iii", "iv"].contains($0) }
    }

    /// A representative's name from GIS matched to the name in recorded votes (one clear match or none):
    /// returns (vote name, yes, no).
    public static func matchMember(_ rep: String, gov: String, model: AddressModel) -> (name: String, yes: Int, no: Int)? {
        let a = normName(rep)
        guard a.count >= 2 else { return nil }
        let hits = (model.members[gov] ?? []).filter { row in
            guard let n = row.first?.stringValue else { return false }
            let b = normName(n)
            return b.count > 1 && b.last == a.last && (b[0].hasPrefix(a[0]) || a[0].hasPrefix(b[0]))
        }
        guard hits.count == 1, let n = hits[0].first?.stringValue else { return nil }
        return (n, Int(hits[0].dropFirst().first?.doubleValue ?? 0), Int(hits[0].dropFirst(2).first?.doubleValue ?? 0))
    }

    // MARK: - Development nearby

    public struct Development: Sendable {
        public struct Project: Sendable, Identifiable {
            public let name: String
            public let detail: String?
            public let status: String?
            public let when: String?
            public let address: String?
            public let miles: Double?
            public let source: String
            public let time: Double
            public var id: String { "\(source)|\(name)|\(time)" }
        }
        public struct Rezoning: Sendable, Identifiable {
            public let ordinance: String
            public let time: Double
            public let changes: [String]
            public var id: String { ordinance }
        }
        public let zoning: String?
        public let futureLandUse: String?
        public let projects: [Project]
        public let rezonings: [Rezoning]
        public let conditionalUses: [String]
        public let failed: Bool
    }

    // MARK: - Loading

    public static func load(_ match: AddressMatch, gis: GISClient = GISClient(), client: BayCountyClient, model: AddressModel) async -> AddressReport {
        let pt = match.point
        async let parcelQ: GISClient.Feature? = {
            if let r = match.renum, !r.isEmpty {
                return (try? await gis.query(GISClient.county, "Admin_A12/MapServer/6", ["where": "A1RENUM='\(r.replacingOccurrences(of: "'", with: ""))'"]))?.first
            }
            return await gis.atPoint("Admin_A12/MapServer/6", pt)?.first
        }()
        async let cityQ = gis.atPoint("Admin_A12/MapServer/26", pt)
        async let craQ = gis.atPoint("Admin_A12/MapServer/27", pt)
        async let commQ = gis.atPoint("Admin_A12/MapServer/28", pt)
        async let localQ = gis.atPoint("Admin_A12/MapServer/30", pt)
        async let mosqQ = gis.atPoint("Admin_A12/MapServer/34", pt)
        async let floodQ = gis.flood(at: pt)
        async let evacQ = gis.atPoint("Admin_A12/MapServer/80", pt)
        async let tdcQ = gis.atPoint("Admin_A12/MapServer/84", pt)
        async let sbQ = gis.atPoint("ElectionAdministration/MapServer/2", pt)
        async let houseQ = gis.atPoint("ElectionAdministration/MapServer/3", pt)
        async let senateQ = gis.atPoint("ElectionAdministration/MapServer/4", pt)
        async let ushQ = gis.atPoint("ElectionAdministration/MapServer/5", pt)
        async let esQ = gis.atPoint("SchoolAttendanceZones/MapServer/0", pt)
        async let msQ = gis.atPoint("SchoolAttendanceZones/MapServer/1", pt)
        async let hsQ = gis.atPoint("SchoolAttendanceZones/MapServer/2", pt)
        async let fireQ = gis.nearest(42, pt)
        async let libQ = gis.nearest(39, pt)
        async let parkQ = gis.nearest(41, pt)

        let parcel = await parcelQ
        let pid = parcel?.s("A1RENUM")
        async let exQ: [Double]? = shard(client, "ex", pid, model)?.arrayValue?.compactMap(\.doubleValue)
        async let navQ: JSONValue?? = shardRaw(client, "nav", pid, model)

        let city = await cityQ
        let cityName = city?.compactMap { $0.s("NAME") }.first { !$0.lowercased().contains("unincorp") }
        async let devQ = development(gis, pt, cityName: cityName)

        let flood = await floodQ
        let navRaw = await navQ
        var fees: [(String, Double)]? = nil
        if let got = navRaw {   // nil outer = couldn't load
            fees = (got?.arrayValue ?? []).compactMap { item in
                guard let a = item.arrayValue, a.count >= 2, let c = a[0].stringValue, let v = a[1].doubleValue else { return nil }
                return (c, v)
            }
        }
        let cra = await craQ
        return AddressReport(
            match: match, parcel: parcel, exemptions: await exQ, fees: fees, cityName: cityName,
            cra: cra?.first, craChecked: cra != nil,
            commission: await commQ?.first, cityCouncil: await localQ?.first, schoolBoard: await sbQ?.first,
            floridaHouse: await houseQ?.first, floridaSenate: await senateQ?.first, usHouse: await ushQ?.first,
            elementary: await esQ?.first?.s("NAME"), middle: await msQ?.first?.s("NAME"), high: await hsQ?.first?.s("NAME"),
            flood: flood, floodChecked: flood != nil,
            evacuationZone: await evacQ?.first?.s("EZONE"), mosquito: await mosqQ?.first, touristTaxArea: await tdcQ?.first?.s("ID"),
            fireStation: await fireQ, library: await libQ, park: await parkQ, development: await devQ)
    }

    /// One parcel's entry from a split per-parcel file. Outer nil = couldn't load; inner nil = parcel not in the file.
    static func shardRaw(_ client: BayCountyClient, _ kind: String, _ pid: String?, _ m: AddressModel) async -> JSONValue?? {
        guard let pid, let n = m.shards[kind] else { return nil }
        guard let r = try? await client.get("/data/\(kind)/\(parcelShard(pid, count: n)).json"),
              let obj = try? JSONDecoder().decode([String: JSONValue].self, from: r.data) else { return nil }
        return .some(obj[pid])
    }

    static func shard(_ client: BayCountyClient, _ kind: String, _ pid: String?, _ m: AddressModel) async -> JSONValue? {
        (await shardRaw(client, kind, pid, m)) ?? nil
    }

    static let jurisdictions = ["BC": "county code", "LH": "Lynn Haven code", "PC": "Panama City code", "PCB": "Panama City Beach code", "CW": "Callaway code",
                                "SF": "Springfield code", "SP": "Springfield code", "PK": "Parker code", "MB": "Mexico Beach code"]

    static func codeLabel(_ v: String?) -> String {
        var s = (v ?? "").replacingOccurrences(of: #"^v\s+"#, with: "", options: [.regularExpression, .caseInsensitive])
        if let r = s.range(of: #"\s*\(([A-Z]+)\)\s*$"#, options: .regularExpression) {
            let j = s[r].trimmingCharacters(in: CharacterSet(charactersIn: " ()"))
            if let name = jurisdictions[j] { s = s[..<r.lowerBound] + " (\(name))" }
        }
        return s.trimmingCharacters(in: .whitespaces)
    }

    static func bareCode(_ v: String?) -> String {
        codeLabel(v).replacingOccurrences(of: #" \([^)]*code\)$"#, with: "", options: .regularExpression)
    }

    /// ArcGIS dates come as epoch milliseconds or ISO strings.
    static func time(_ v: JSONValue?) -> Double {
        if let n = v?.doubleValue, case .number = v! { return n }
        if let s = v?.stringValue, let d = Dates.parse(s.count == 10 ? s : String(s.prefix(10))) { return d.timeIntervalSince1970 * 1000 }
        return 0
    }

    static func monthYear(_ ms: Double) -> String {
        guard ms > 0 else { return "" }
        let d = Date(timeIntervalSince1970: ms / 1000)
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US"); f.dateFormat = "MMM yyyy"; f.timeZone = TimeZone(identifier: "UTC")
        let y = Calendar(identifier: .gregorian).component(.year, from: d)
        return y < 1990 ? "" : f.string(from: d)
    }

    static func development(_ gis: GISClient, _ pt: GeoPoint, cityName: String?) async -> Development {
        let half = ["distance": "0.5", "units": "esriSRUnit_StatuteMile"]
        let fiveYears = Date().addingTimeInterval(-5 * 365.25 * 86400)
        let since = Dates.dayKey(fiveYears)
        let inPC = cityName == "Panama City", inPCB = cityName == "Panama City Beach"
        @Sendable func q(_ base: URL, _ path: String, _ p: [String: String]) async -> [GISClient.Feature]? {
            var params = ["geometry": "\(pt.x),\(pt.y)", "geometryType": "esriGeometryPoint", "inSR": "4326", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects"]
            params.merge(p) { _, n in n }
            return try? await gis.query(base, path, params)
        }
        let C = GISClient.county, PC = GISClient.panamaCity, AGO = GISClient.agol
        async let zon = q(C, "LandUsePlanning/MapServer/1", ["outFields": "ZONING,Label,ORD_NUM,ORD_DATE"])
        async let flu = q(C, "LandUsePlanning/MapServer/2", ["outFields": "FLU_CODE,Label,ORD_NUM,ORD_DATE"])
        async let pcz = inPC ? q(PC, "Zoning_CPC/FeatureServer/0", ["outFields": "LABEL,ZONE_TYPE,ordinance,ordinancedate"]) : nil
        async let pcf = inPC ? q(PC, "FutureLandUse_CPC/FeatureServer/0", ["outFields": "LANDUSE"]) : nil
        async let pcbf = inPCB ? q(C, "PanamaCityBeach/PanamaCityBeachPublic/MapServer/8", ["outFields": "FLU_CODE,Label"]) : nil
        async let dos = q(C, "Departmental/Planning/MapServer/18", half.merging(["outFields": "NAME,NUMBER,DESCRIPTION,SIZE,LOCATION,APPLICATION_RECEIVED,DO_ISSUED,TYPE", "returnGeometry": "true"]) { _, n in n })
        async let lhd = q(AGO, "LH_Development_Planning_Projects/FeatureServer/0", half.merging(["outFields": "Project,Number_of_Units,Acres,Address,DO_Status,City_Commission_Approval_Date,DO_Expires", "returnGeometry": "true"]) { _, n in n })
        async let pcbd = q(AGO, "PCB_Planning_Projects_Editing/FeatureServer/0", half.merging(["outFields": "TYPE,Name,SIZE,DEVTYPE,DateApplied,DateIssued", "returnGeometry": "true"]) { _, n in n })
        async let rez = q(C, "LandUsePlanning/MapServer/1", half.merging(["where": "ORD_DATE >= DATE '\(since)'", "outFields": "ZONING,Label,ORD_NUM,ORD_DATE,COMMENTS", "orderByFields": "ORD_DATE DESC"]) { _, n in n })
        async let pcr = inPC ? q(PC, "Zoning_CPC/FeatureServer/0", half.merging(["where": "ordinancedate >= DATE '\(since)'", "outFields": "LABEL,ZONE_TYPE,ordinance,ordinancedate,previouszone"]) { _, n in n }) : nil
        async let cond = q(C, "Departmental/Planning/MapServer/17", ["distance": "0.25", "units": "esriSRUnit_StatuteMile", "outFields": "REF__NUM,TYPE,CONDITION,CONDITION2,CONDITION3", "returnGeometry": "true"])

        let (zonR, fluR, dosR) = (await zon, await flu, await dos)
        let pczR = await pcz, pcfR = await pcf, pcbfR = await pcbf
        var zoning: String? = nil
        if let z = pczR?.first { zoning = (z.s("LABEL") ?? "") + (z.s("ZONE_TYPE").map { " (\($0))" } ?? "") }
        else if let z = zonR?.first { zoning = z.s("ZONING") == "See FLU" ? "Set by the future land use map" : codeLabel(z.s("Label") ?? z.s("ZONING")) }
        let fluText = pcfR?.first?.s("LANDUSE") ?? {
            let v = codeLabel(pcbfR?.first?.s("Label") ?? fluR?.first?.s("Label") ?? fluR?.first?.s("FLU_CODE"))
            return v.isEmpty ? nil : v
        }()

        var proj = [Development.Project]()
        let dist: (GISClient.Feature) -> Double? = { f in f.geometry.map { pt.miles(to: $0) } }
        for d in dosR ?? [] {
            let issued = time(d.attributes["DO_ISSUED"]), applied = time(d.attributes["APPLICATION_RECEIVED"])
            proj.append(.init(name: d.s("NAME") ?? "Project", detail: d.s("DESCRIPTION"), status: d.s("TYPE"),
                              when: issued > 0 ? "issued " + monthYear(issued) : applied > 0 ? "applied " + monthYear(applied) : nil,
                              address: d.s("LOCATION"), miles: dist(d), source: "Bay County", time: issued > 0 ? issued : applied))
        }
        for d in await lhd ?? [] {
            let t = time(d.attributes["City_Commission_Approval_Date"])
            let units = d.s("Number_of_Units").flatMap { $0 == "N/A" ? nil : "\($0) units" }
            let acres = d.s("Acres").map { "\($0) acres" }
            proj.append(.init(name: d.s("Project") ?? "Project", detail: [units, acres].compactMap { $0 }.joined(separator: ", "), status: d.s("DO_Status"),
                              when: t > 0 ? "approved " + monthYear(t) : nil, address: d.s("Address"), miles: dist(d), source: "Lynn Haven", time: t))
        }
        for d in await pcbd ?? [] {
            let issued = time(d.attributes["DateIssued"]), applied = time(d.attributes["DateApplied"])
            proj.append(.init(name: d.s("Name") ?? "Project", detail: d.s("TYPE"), status: d.s("DEVTYPE"),
                              when: issued > 0 ? "issued " + monthYear(issued) : applied > 0 ? "applied " + monthYear(applied) : nil,
                              address: nil, miles: dist(d), source: "Panama City Beach", time: issued > 0 ? issued : applied))
        }
        let cutoff = fiveYears.timeIntervalSince1970 * 1000
        let recent = proj.filter { $0.time == 0 || $0.time >= cutoff }.sorted { $0.time > $1.time }.prefix(8)

        struct RZ { let z: String; let zc: String?; let o: String; let t: Double; let prev: String }
        var rz = (await rez ?? []).map { r in
            RZ(z: bareCode(r.s("Label") ?? r.s("ZONING")), zc: nil, o: r.s("ORD_NUM") ?? "", t: time(r.attributes["ORD_DATE"]),
               prev: bareCode((r.s("COMMENTS") ?? "").replacingOccurrences(of: #"^pre\.?\s*"#, with: "", options: [.regularExpression, .caseInsensitive])))
        }
        rz += (await pcr ?? []).map { r in
            RZ(z: bareCode(r.s("LABEL")), zc: bareCode(r.s("LABEL")), o: r.s("ordinance") ?? "", t: time(r.attributes["ordinancedate"]), prev: bareCode(r.s("previouszone")))
        }
        let now = Date().timeIntervalSince1970 * 1000
        rz = rz.filter { r in
            r.t > 0 && r.t <= now + 86_400_000 &&
                (r.prev.isEmpty || r.prev.components(separatedBy: " (")[0] != (r.zc ?? r.z).components(separatedBy: " (")[0])
        }
        var byOrd: [String: Development.Rezoning] = [:], order: [String] = []
        for r in rz {
            let change = (r.prev.isEmpty ? "to " : r.prev + " \u{2192} ") + r.z
            if let g = byOrd[r.o] {
                if !g.changes.contains(change) { byOrd[r.o] = .init(ordinance: g.ordinance, time: g.time, changes: g.changes + [change]) }
            } else { byOrd[r.o] = .init(ordinance: r.o, time: r.t, changes: [change]); order.append(r.o) }
        }
        let rezonings = order.compactMap { byOrd[$0] }.sorted { $0.time > $1.time }.prefix(5)
        let cu = (await cond ?? []).compactMap { c -> String? in
            guard let t = c.s("TYPE") else { return nil }
            let detail = [c.s("CONDITION"), c.s("CONDITION2"), c.s("CONDITION3")].compactMap { $0 }.joined(separator: " ")
            return [t, detail, c.s("REF__NUM").map { "(\($0))" }].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " ")
        }.prefix(4)
        return Development(zoning: zoning, futureLandUse: fluText, projects: Array(recent), rezonings: Array(rezonings),
                           conditionalUses: Array(cu), failed: zonR == nil && fluR == nil && dosR == nil)
    }
}

/// Flood zone in plain words (address.js renderSafe).
public enum FloodText {
    public static func describe(_ f: GISClient.Flood?) -> (headline: String, detail: String?) {
        guard let f else { return ("Couldn't check right now", nil) }
        guard let z = f.zone else {
            return (f.source == .county ? "Outside the high-risk areas on Bay County's copy of the flood map" : "Not on FEMA's flood map here", nil)
        }
        let zone = z.s("FLD_ZONE") ?? "", bfe = z.n("STATIC_BFE") ?? 0
        let bfeText = bfe > 0 ? " · base flood elevation \(Format.number(bfe)) ft" + (z.s("V_DATUM").map { " (\($0))" } ?? "") : ""
        var head: String
        if z.s("SFHA_TF") == "T" || zone.hasPrefix("A") || zone.hasPrefix("V") {
            head = "Zone \(zone) · FEMA high-risk area" + (zone.hasPrefix("V") ? ", coastal waves" : "") + bfeText
            if let depth = z.n("DEPTH"), depth > 0 { head += " · flood depth \(Format.number(depth)) ft" }
        } else if zone == "X", (z.s("ZONE_SUBTY") ?? "").contains("0.2") {
            head = "Zone X (shaded) · moderate risk, outside the high-risk area (0.2% annual chance flood)"
        } else if zone == "X" {
            head = "Zone X · minimal flood hazard on FEMA's map"
        } else if zone == "D" {
            head = "Zone D · flood risk not determined"
        } else {
            head = "Zone \(zone)" + bfeText
        }
        var detail = [String]()
        if let p = f.panel?.s("FIRM_PAN") {
            var line = "FIRM panel \(p)" + (f.panel?.n("EFF_DATE").map { ", effective " + day($0) } ?? "")
            if let c = f.lomr?.s("CASE_NO") { line += " · map revision (LOMR) \(c)" + (f.lomr?.n("EFF_DATE").map { ", " + day($0) } ?? "") }
            detail.append(line)
        }
        if f.source == .county {
            detail.append("FEMA's live map didn't respond, so this is Bay County's older copy, which predates the October 2024 maps.")
        }
        return (head, detail.isEmpty ? nil : detail.joined(separator: "\n"))
    }

    static func day(_ ms: Double) -> String {
        let f = DateFormatter(); f.locale = Locale(identifier: "en_US"); f.dateFormat = "MMM d, yyyy"; f.timeZone = TimeZone(identifier: "UTC")
        return f.string(from: Date(timeIntervalSince1970: ms / 1000))
    }
}

/// CRA spending and sales tax projects near an address (address.js nearHtml).
public struct NearbyMoney: Sendable {
    public struct CRAItem: Sendable, Identifiable {
        public let id: Int
        public let amount: Double?
        public let purpose: String
        public let status: String
        public let when: String?
        public let miles: Double
        public let url: URL?
        public let cra: String
    }
    public struct Project: Sendable, Identifiable {
        public let id: String
        public let name: String
        public let cost: Double?
        public let status: String
        public let percent: Double?
        public let government: String?
        public let miles: Double
    }
    public let cra: [CRAItem]
    public let projects: [Project]
    public var craTotal: Double { cra.filter { $0.status == "Spent" || $0.status == "Committed" }.compactMap(\.amount).reduce(0, +) }

    public static func load(near pt: GeoPoint, client: BayCountyClient) async throws -> NearbyMoney {
        async let a = client.get("/data/cra-pay-1.json")
        async let b = client.get("/data/cra-pay-2.json")
        async let s = client.get("/data/surtax-projects.json")
        let pays = try Row.decodeList(try await a.data) + Row.decodeList(try await b.data)
        let projs = try Row.decodeList(try await s.data)
        let cra = pays.compactMap { p -> CRAItem? in
            guard p.bool("count") == true, p.string("placed") == "site", let lat = p.number("lat"), let lng = p.number("lng") else { return nil }
            let mi = pt.miles(to: GeoPoint(x: lng, y: lat))
            guard mi <= 0.5 else { return nil }
            return CRAItem(id: Int(p.number("id") ?? Double(p.id)), amount: p.number("amount"), purpose: p.first(["purpose", "payee"]) ?? "",
                           status: p.string("status") ?? "", when: p.string("when"), miles: mi, url: p.url("url"), cra: p.string("cra") ?? "")
        }.sorted { $0.miles < $1.miles }
        let near = projs.compactMap { p -> Project? in
            guard let x = p.number("x"), let y = p.number("yy") else { return nil }
            let mi = pt.miles(to: GeoPoint(x: x, y: y))
            guard mi <= 1 else { return nil }
            return Project(id: p.string("id") ?? "\(p.id)", name: p.string("n") ?? "Project", cost: p.number("k"), status: p.string("s") ?? "unknown",
                           percent: p.number("p"), government: p.string("g"), miles: mi)
        }.sorted { $0.miles < $1.miles }
        return NearbyMoney(cra: cra, projects: near)
    }

    public static func statusLabel(_ s: String) -> String {
        ["completed": "Completed", "in_progress": "In progress", "not_started": "Not started"][s] ?? "Status unknown"
    }
}
