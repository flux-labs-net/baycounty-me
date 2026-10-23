import SwiftUI
import CoreLocation
import BayCountyKit

/// Finds a Bay County address: type it, or use where you are.
struct MyAddressView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var results: [AddressMatch] = []
    @State private var relaxed = false
    @State private var searching = false
    @State private var message: String?
    @State private var locator = Locator()

    var body: some View {
        List {
            Section {
                Text("Type a Bay County street address to see your property tax estimate, who represents you, your schools, your flood and evacuation zones, and whether you're inside a redevelopment district.")
                    .font(.subheadline)
                Button {
                    Task { await useLocation() }
                } label: {
                    Label(locator.busy ? "Finding you…" : "Use my location", systemImage: "location")
                }
                .disabled(locator.busy)
            } footer: {
                Text("Lookups go straight to Bay County's public map server. BayCounty.me doesn't store what you search, and your location is only used once, to find the nearest address.")
            }

            if let message {
                Section { Text(message).foregroundStyle(.secondary) }
            }

            if !results.isEmpty {
                Section(relaxed ? "Closest matches" : "Addresses") {
                    ForEach(results) { m in
                        NavigationLink(value: Route.address(m)) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(m.display).font(.body.weight(.medium))
                                Text(m.subtitle).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }

            if let home = store.home, query.isEmpty, results.isEmpty {
                Section("Saved") {
                    NavigationLink(value: Route.address(home)) { Label(home.display, systemImage: "house.fill") }
                }
            }
        }
        .navigationTitle("My Address")
        .searchable(text: $query, placement: .navigationBarDrawer(displayMode: .always), prompt: "e.g. 825 Ohio Ave")
        .overlay { if searching && results.isEmpty { ProgressView() } }
        .task(id: query) { await search() }
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 3 else { results = []; message = nil; return }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        guard AddressParser.parse(q).map({ !$0.tokens.isEmpty }) ?? false else {
            results = []; message = "Start with the house number, then the street (for example \"1614 Ohio\")."
            return
        }
        searching = true; defer { searching = false }
        do {
            let r = try await store.gis.search(q)
            guard !Task.isCancelled else { return }
            results = r.matches; relaxed = r.relaxed
            message = r.matches.isEmpty ? "No matching address. Check the house number, or try just the number and street name (for example \"1614 Ohio\")." : nil
        } catch {
            guard !Task.isCancelled else { return }
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }

    private func useLocation() async {
        do {
            let loc = try await locator.current()
            let pt = GeoPoint(x: loc.coordinate.longitude, y: loc.coordinate.latitude)
            let near = try await store.gis.addresses(near: pt)
            results = near; relaxed = false
            message = near.isEmpty ? "No Bay County address found within 150 feet of where you are. Try typing it." : nil
        } catch let e as Locator.Failure {
            message = e.message
        } catch {
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }
}

/// One-shot location for "Use my location".
@MainActor
@Observable
final class Locator: NSObject, CLLocationManagerDelegate {
    enum Failure: Error {
        case denied, unavailable
        var message: String {
            switch self {
            case .denied: "Location is off for BayCounty.me. You can turn it on in Settings, or type the address."
            case .unavailable: "Couldn't find your location. Try typing the address."
            }
        }
    }

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocation, Error>?
    private(set) var busy = false

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyNearestTenMeters
    }

    func current() async throws -> CLLocation {
        busy = true
        defer { busy = false }
        return try await withCheckedThrowingContinuation { c in
            continuation = c
            switch manager.authorizationStatus {
            case .notDetermined: manager.requestWhenInUseAuthorization()
            case .denied, .restricted: finish(.failure(Failure.denied))
            default: manager.requestLocation()
            }
        }
    }

    private func finish(_ r: Result<CLLocation, Error>) {
        continuation?.resume(with: r)
        continuation = nil
    }

    nonisolated func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        Task { @MainActor in
            guard continuation != nil else { return }
            switch m.authorizationStatus {
            case .authorizedWhenInUse, .authorizedAlways: manager.requestLocation()
            case .denied, .restricted: finish(.failure(Failure.denied))
            default: break
            }
        }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didUpdateLocations locs: [CLLocation]) {
        Task { @MainActor in if let l = locs.last { finish(.success(l)) } }
    }

    nonisolated func locationManager(_ m: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in finish(.failure(Failure.unavailable)) }
    }
}

/// Everything that applies to one address (the website's My Address results).
struct AddressReportView: View {
    @Environment(AppStore.self) private var store
    let match: AddressMatch
    @State private var report: AddressReport?
    @State private var nearby: NearbyMoney?
    @State private var nearbyFailed = false

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 4) {
                    Text(match.display).font(.title3.weight(.semibold))
                    Text(subtitle).font(.subheadline).foregroundStyle(.secondary)
                }
                .padding(.vertical, 2)
                saveButton
            }
            if let r = report, let m = store.addressModel {
                taxSection(r, m)
                propertySection(r, m)
                amendmentSection(r, m)
                repsSection(r, m)
                schoolsSection(r)
                craSection(r, m)
                safetySection(r)
                developmentSection(r)
                nearbySection
                govSection(r, m)
                Section {
                    if let link = r.parcel?.s("PLINK"), let url = URL(string: link) {
                        WebLink(title: "Property Appraiser record", symbol: "doc.text.magnifyingglass", url: url)
                    }
                } footer: {
                    Text("Owner names are not shown here. They're public at the Property Appraiser's site. Representative names come from Bay County's GIS and may lag an election.")
                }
            } else if store.addressModel == nil, store.appError("address.json") != nil {
                Section { AppDataPending(file: "address.json", title: "Couldn't load the address report") { await load() } }
            } else {
                Section { HStack { ProgressView(); Text("Looking up this address…").foregroundStyle(.secondary) } }
            }
        }
        .navigationTitle("My Address")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable {
            guard let m = store.addressModel else { await load(); return }
            report = await AddressReport.load(match, gis: store.gis, client: store.client, model: m)
        }
    }

    private func load() async {
        await store.loadAddressModel()
        guard let m = store.addressModel else { return }
        if report == nil { report = await AddressReport.load(match, gis: store.gis, client: store.client, model: m) }
        if nearby == nil {
            do { nearby = try await NearbyMoney.load(near: match.point, client: store.client) } catch { nearbyFailed = true }
        }
    }

    private var subtitle: String {
        guard let r = report else { return match.subtitle + " · Loading…" }
        return [r.cityName.map { "City of \($0)" } ?? "Unincorporated Bay County", match.zip.map { "ZIP \($0)" },
                r.parcel?.s("A1RENUM").map { "Parcel \($0)" }].compactMap { $0 }.joined(separator: " · ")
    }

    @ViewBuilder private var saveButton: some View {
        if store.home == match {
            Button(role: .destructive) { store.home = nil } label: { Label("Remove as my home", systemImage: "house.slash") }
        } else {
            Button { store.home = match } label: { Label("Save as my home", systemImage: "house") }
        }
    }

    // MARK: Sections

    @ViewBuilder private func taxSection(_ r: AddressReport, _ m: AddressModel) -> some View {
        Section {
            if let e = r.taxEstimate(m) {
                let groups = e.byGroup(m.groups.compactMap(\.first))
                let gname: (String) -> String = { g in g == "city" ? (e.cityName ?? "City") : (m.groups.first { $0.first == g }?.last ?? g) }
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(Format.money(e.total)).font(.largeTitle.weight(.semibold).monospacedDigit())
                        Text("/ year").foregroundStyle(.secondary)
                    }
                    Text("\(e.districtLabel) · \(Format.number(e.mills)) mills\(e.exact ? "" : " (area inferred from the map)")")
                        .font(.caption).foregroundStyle(.secondary)
                    StackBar(parts: groups.map { (gname($0.group), $0.amount, TaxColors.color($0.group)) })
                }
                .padding(.vertical, 4)
                ForEach(groups) { g in
                    LegendRow(color: TaxColors.color(g.group), label: gname(g.group), value: Format.money(g.amount))
                }
                if let fees = r.fees {
                    if fees.isEmpty {
                        Text("No flat fees (non-ad valorem assessments) were on this parcel's FY2026 tax bill.").font(.footnote).foregroundStyle(.secondary)
                    } else {
                        ForEach(Array(fees.enumerated()), id: \.offset) { _, f in
                            LabeledContent(m.navLabel[f.code] ?? "Other charge (\(f.code))", value: Format.money(f.amount))
                        }
                        LabeledContent { Text(Format.money(e.total + fees.reduce(0) { $0 + $1.amount })).bold() } label: { Text("Estimated total bill").bold() }
                    }
                }
                NavigationLink(value: Route.taxCalculator(districtID: e.districtID, value: e.parts.assessed, homestead: e.parts.homestead)) {
                    Text("Try what-if numbers in the calculator")
                }
            } else {
                Text("No parcel record came back for this address, so there's no value to estimate from.").foregroundStyle(.secondary)
                NavigationLink(value: Route.taxCalculator()) { Text("Use the calculator") }
            }
        } header: {
            Text("Property tax estimate")
        } footer: {
            Text("Property tax: 2026 values × \(m.fy) rates. Fees: the FY2026 tax roll. Your official bill comes from the Tax Collector.")
        }
    }

    @ViewBuilder private func propertySection(_ r: AddressReport, _ m: AddressModel) -> some View {
        if let p = r.parcel {
            let t = AddressReport.taxParts(parcel: p, exemptions: r.exemptions, second2026: m.second2026)
            Section("The property") {
                if let use = p.s("DORAPPDESC") { LabeledContent("Use", value: AddressParser.titleCase(use)) }
                if let built = p.s("S1YRBLTACT") {
                    LabeledContent("Built", value: built + (p.n("S1AREAHEAT").map { " · \(Format.number($0.rounded())) heated sq ft" } ?? ""))
                }
                LabeledContent("Market (just) value", value: Format.money(t.just))
                LabeledContent("Assessed value", value: Format.money(t.assessed))
                if t.assessed < t.just {
                    Text("Capped \(Format.money(t.just - t.assessed)) below market.").font(.caption).foregroundStyle(.secondary)
                }
                if t.exempt > 0 {
                    LabeledContent("Exemptions", value: Format.money(t.exempt))
                    if t.homesteadAmount > 0 { LabeledContent("  Homestead", value: Format.money(t.homesteadAmount)).font(.footnote) }
                    if t.additionalHomestead > 0 { LabeledContent("  Additional homestead", value: Format.money(t.additionalHomestead)).font(.footnote) }
                    if t.otherExemptions > 0 {
                        LabeledContent("  Other exemptions", value: Format.money(t.otherExemptions)).font(.footnote)
                        Text("The kinds of other exemptions aren't shown, to protect owners' privacy.").font(.caption).foregroundStyle(.secondary)
                    }
                } else {
                    LabeledContent("Exemptions", value: "None")
                }
                LabeledContent("Taxable value", value: Format.money(t.otherTaxable))
                if t.schoolTaxable != t.otherTaxable {
                    Text("\(Format.money(t.schoolTaxable)) for school taxes").font(.caption).foregroundStyle(.secondary)
                }
                if t.fullyExempt { Text("No property tax is owed on this home.").bold() }
                if !t.homestead && r.isResidential {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("No homestead exemption").font(.subheadline.weight(.semibold))
                        Text("This home has no homestead exemption on the 2026 tax roll. That's normal for a rental or a second home. If you own it and it was your permanent home on January 1, you can apply with the Bay County Property Appraiser. Applications are due March 1 for that year's taxes.")
                            .font(.footnote)
                    }
                }
                HStack {
                    Button("Assessed value") { store.explain("assessed-value") }
                    Button("Taxable value") { store.explain("taxable-value") }
                    Button("Homestead") { store.explain("homestead") }
                }
                .buttonStyle(.borderless).font(.caption)
            }
        }
    }

    @ViewBuilder private func amendmentSection(_ r: AddressReport, _ m: AddressModel) -> some View {
        if let p = r.parcel, let e = r.taxEstimate(m) {
            let t = AddressReport.taxParts(parcel: p, exemptions: r.exemptions, second2026: m.second2026)
            Section("If Amendment 3 passes") {
                if let s = r.amendment3Savings(m) {
                    Text("With the full $250,000 homestead exemption on today's value and rates, this home's county, city and district taxes would drop by about **\(Format.money(s.savings)) a year**\(s.toZero ? ", to zero; it would still pay school tax" : "").")
                    Text("Assumes rates stay the same and the owner was a Florida resident before 2027.").font(.caption).foregroundStyle(.secondary)
                } else {
                    Text("This property has no homestead exemption, so Amendment 3 wouldn't lower its tax bill directly. It would limit how fast its taxed value can rise to **5% a year instead of 10%** for non-school taxes.\(t.assessed < t.just ? " Its value is already capped \(Format.money(t.just - t.assessed)) below market." : "")")
                }
                NavigationLink(value: Route.amendment3(districtID: e.districtID, value: t.assessed, homestead: t.homestead)) { Text("Try your own numbers") }
            }
        }
    }

    private func repLine(_ title: String, _ f: GISClient.Feature?, gov: String?, _ m: AddressModel) -> some View {
        let name = f?.s("REPNAME")
        let member = name.flatMap { n in gov.flatMap { AddressReport.matchMember(n, gov: $0, model: m) } }
        let person = name.flatMap { n in store.people?.people.first { p in p.name.lowercased() == n.lowercased() || (member.map { p.name == $0.name } ?? false) } }
        return VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            if let person {
                NavigationLink(value: Route.person(person.id)) { Text(name ?? "—").font(.body.weight(.medium)) }
            } else {
                Text(name ?? "—").font(.body.weight(.medium))
            }
            HStack(spacing: 8) {
                if let d = f?.s("NAME") { Text(d) }
                if let mm = member { Text("\(mm.yes) yes · \(mm.no) no in recorded money votes") }
            }
            .font(.caption).foregroundStyle(.secondary)
            if let u = f?.s("DISTRICTURL"), let url = URL(string: u) {
                Button("Website") { store.open(url) }.font(.caption).buttonStyle(.borderless)
            }
        }
        .padding(.vertical, 2)
    }

    @ViewBuilder private func repsSection(_ r: AddressReport, _ m: AddressModel) -> some View {
        Section("Who represents you") {
            repLine("County Commission", r.commission, gov: "county", m)
            if let city = r.cityName {
                let ck = r.govKey
                if r.cityCouncil != nil { repLine("City of \(city)", r.cityCouncil, gov: ck == "county" ? nil : ck, m) }
                else { LabeledContent("City", value: "City of \(city)") }
            } else {
                Text("No city (unincorporated). The County Commission is your local government.").font(.footnote).foregroundStyle(.secondary)
            }
            repLine("School Board", r.schoolBoard, gov: "schools", m)
            repLine("Florida House", r.floridaHouse, gov: nil, m)
            repLine("Florida Senate", r.floridaSenate, gov: nil, m)
            repLine("U.S. House", r.usHouse, gov: nil, m)
            NavigationLink(value: Route.dataset("candidates-2026", filters: ["gov_id": r.govKey])) { Text("2026 races for your area") }
        }
        .task { await store.loadPeople() }
    }

    @ViewBuilder private func schoolsSection(_ r: AddressReport) -> some View {
        Section {
            LabeledContent("Elementary", value: r.elementary ?? "—")
            LabeledContent("Middle", value: r.middle ?? "—")
            LabeledContent("High", value: r.high ?? "—")
        } header: { Text("Zoned public schools") } footer: {
            Text("Attendance zones from Bay District Schools via county GIS. Choice and magnet options differ.")
        }
    }

    @ViewBuilder private func craSection(_ r: AddressReport, _ m: AddressModel) -> some View {
        Section {
            if !r.craChecked {
                Text("Couldn't check right now.").foregroundStyle(.secondary)
            } else if let c = r.cra, let name = c.s("CRA") {
                let agency = m.craAgency[name]
                Text("This address is inside the **\(name)** district\(c.s("EST_YEAR").map { " (created \($0))" } ?? ""). The city and county taxes on growth in this area since then go to the \(agency ?? "CRA")'s fund and must be spent inside its districts.")
                if let a = agency, let s = m.cra[a] {
                    Text("\(a): \(Format.compactMoney(s.spent)) in documented spending and awards across \(s.n) records.").font(.footnote)
                    NavigationLink(value: Route.dataset("cra-payments", filters: ["cra": a])) { Text("See what it pays for") }
                }
                Button("What's a CRA?") { store.explain("cra") }.font(.caption).buttonStyle(.borderless)
            } else {
                Text("This address is **not inside a CRA district**, so all of its city and county property tax goes to those governments' regular budgets.")
                NavigationLink(value: Route.cra) { Text("See Bay County's CRAs") }
            }
        } header: { Text("Redevelopment district (CRA)") }
    }

    @ViewBuilder private func safetySection(_ r: AddressReport) -> some View {
        let flood = FloodText.describe(r.flood)
        Section {
            VStack(alignment: .leading, spacing: 3) {
                Text("Flood zone").font(.caption).foregroundStyle(.secondary)
                Text(flood.headline).font(.body.weight(.medium))
                if let d = flood.detail { Text(d).font(.caption).foregroundStyle(.secondary) }
            }
            LabeledContent("Evacuation zone", value: r.evacuationZone.map { "Zone \($0)" } ?? "Not in a mapped zone")
            nearest("Nearest fire station", r.fireStation)
            nearest("Nearest library", r.library)
            nearest("Nearest park", r.park)
            if let mq = r.mosquito?.s("DISTRICT") { LabeledContent("Mosquito control", value: mq) }
            if let tdc = r.touristTaxArea { LabeledContent("Tourist tax area", value: tdc) }
            if let url = femaURL { WebLink(title: "Check this address on FEMA's map", symbol: "map", url: url) }
        } header: { Text("Flood, storms and services") } footer: {
            Text("Flood zone is checked live against FEMA's National Flood Hazard Layer at the address point. A building's official zone comes from the flood map, your lender's flood determination or an elevation certificate.")
        }
    }

    private var femaURL: URL? {
        var c = URLComponents(string: "https://msc.fema.gov/portal/search")!
        c.queryItems = [URLQueryItem(name: "AddressQuery", value: "\(match.display), \(report?.cityName.map { "\($0), FL" } ?? "Bay County, FL")")]
        return c.url
    }

    private func nearest(_ title: String, _ x: (feature: GISClient.Feature, miles: Double)?) -> some View {
        LabeledContent(title) {
            if let x {
                VStack(alignment: .trailing) {
                    Text(x.feature.s("NAME") ?? "—")
                    Text("\(String(format: "%.1f", x.miles)) mi").font(.caption).foregroundStyle(.secondary)
                }
            } else {
                Text("None within 10 miles").foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private func developmentSection(_ r: AddressReport) -> some View {
        if let d = r.development {
            Section {
                if d.failed {
                    Text("Bay County's planning maps didn't answer. Try again in a moment.").foregroundStyle(.secondary)
                } else {
                    LabeledContent("Zoning", value: d.zoning ?? "Not mapped")
                    LabeledContent("Future land use", value: d.futureLandUse ?? "Not mapped")
                    if d.projects.isEmpty {
                        Text("No development projects on file within half a mile in the last 5 years.").font(.footnote).foregroundStyle(.secondary)
                    }
                    ForEach(d.projects) { p in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name + (p.detail.map { $0.isEmpty ? "" : " · \($0)" } ?? "")).font(.subheadline.weight(.medium))
                            Text([p.status, p.when, p.address, p.miles.map { String(format: "%.1f mi away", $0) }, p.source].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    ForEach(d.rezonings) { z in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Rezoning, ordinance \(z.ordinance)").font(.subheadline.weight(.medium))
                            Text(z.changes.prefix(4).joined(separator: "; ") + (z.changes.count > 4 ? " and \(z.changes.count - 4) more" : "")).font(.caption)
                        }
                    }
                    ForEach(d.conditionalUses, id: \.self) { Text("Conditional use: \($0)").font(.caption) }
                }
            } header: { Text("Zoning and development nearby") } footer: {
                Text("Projects and rezonings within half a mile, last 5 years, from Bay County, Panama City, Lynn Haven and Panama City Beach planning maps. Building permits aren't published as open data.")
            }
        }
    }

    @ViewBuilder private var nearbySection: some View {
        Section {
            if let n = nearby {
                Text("CRA spending within half a mile").font(.subheadline.weight(.semibold))
                if n.cra.isEmpty { Text("None on file nearby.").font(.footnote).foregroundStyle(.secondary) }
                else {
                    Text("\(n.cra.count) records · \(Format.compactMoney(n.craTotal)) spent or committed").font(.caption).foregroundStyle(.secondary)
                    ForEach(n.cra.prefix(5)) { c in
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(c.amount.map { Format.money($0) } ?? "—") · \(c.purpose)").font(.subheadline).lineLimit(2)
                            Text([c.status, c.when, String(format: "%.1f mi", c.miles)].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                Text("Sales tax projects within a mile").font(.subheadline.weight(.semibold)).padding(.top, 4)
                if n.projects.isEmpty { Text("None on file nearby.").font(.footnote).foregroundStyle(.secondary) }
                else {
                    Text("\(n.projects.count) projects").font(.caption).foregroundStyle(.secondary)
                    ForEach(n.projects.prefix(5)) { p in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name + (p.cost.map { " · \(Format.compactMoney($0))" } ?? "")).font(.subheadline).lineLimit(2)
                            Text([NearbyMoney.statusLabel(p.status), p.status == "in_progress" ? p.percent.map { "\(Int($0))%" } : nil, p.government, String(format: "%.1f mi", p.miles)]
                                .compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            } else if nearbyFailed {
                Text("Couldn't load right now.").foregroundStyle(.secondary)
            } else {
                ProgressView()
            }
        } header: { Text("Public money near you") } footer: {
            Text("Distances are from the address point. CRA records placed only somewhere in a district, and rows left out of CRA totals, aren't shown; the dollar total counts spent and committed money.")
        }
    }

    @ViewBuilder private func govSection(_ r: AddressReport, _ m: AddressModel) -> some View {
        Section("Your government's records") {
            ForEach(Array(Set([r.govKey, "county", "schools"])).sorted { (Governments.order.firstIndex(of: $0) ?? 9) < (Governments.order.firstIndex(of: $1) ?? 9) }, id: \.self) { k in
                NavigationLink(value: Route.government(k)) {
                    Label(Governments.names[k] ?? k, systemImage: "building.columns")
                }
            }
        }
    }
}
