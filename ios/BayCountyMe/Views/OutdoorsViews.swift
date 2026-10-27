import SwiftUI
import MapKit
import BayCountyKit

/// One dot on an outdoors map.
struct MapPoint: Identifiable {
    let id: String
    let title: String
    let coordinate: CLLocationCoordinate2D
    let color: Color
    var row: Row? = nil
}

/// Beach accesses, sampling sites, parks, ramps and trailheads as dots on a map of the county.
struct PointsMap: View {
    let points: [MapPoint]
    var onSelect: ((MapPoint) -> Void)? = nil

    var body: some View {
        Map(initialPosition: .region(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 30.15, longitude: -85.68),
            span: MKCoordinateSpan(latitudeDelta: 0.5, longitudeDelta: 0.7)))) {
            ForEach(points) { p in
                Annotation(p.title, coordinate: p.coordinate) {
                    Button { onSelect?(p) } label: {
                        Circle().fill(p.color.opacity(0.95)).frame(width: 12, height: 12)
                            .overlay(Circle().stroke(.white, lineWidth: 1.5))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(p.title)
                }
                .annotationTitles(.hidden)
            }
        }
        .mapStyle(.standard(pointsOfInterest: .excludingAll))
        .frame(height: 280)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }
}

private extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

private func point(_ r: Row, id: String, title: String, color: Color) -> MapPoint? {
    guard let lat = r.number("latitude"), let lon = r.number("longitude") else { return nil }
    return MapPoint(id: id, title: title, coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon), color: color, row: r)
}

private func ratingColor(_ r: String?) -> Color {
    switch r {
    case "Good": Color(hex: 0x2E9E5B)
    case "Moderate": Color(hex: 0xE0A526)
    case "Poor": Color(hex: 0xD84315)
    default: .secondary
    }
}

private func riskColor(_ r: String?) -> Color {
    switch r {
    case "High": Color(hex: 0xD84315)
    case "Moderate": Brand.amber
    case "Low": Brand.good
    default: .primary
    }
}

/// Wrapping row of small amenity tags.
struct TagFlow: View {
    let tags: [String]
    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 4) { ForEach(tags, id: \.self) { tag($0) } }
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(stride(from: 0, to: tags.count, by: 3)), id: \.self) { i in
                    HStack(spacing: 4) { ForEach(tags[i..<min(i + 3, tags.count)], id: \.self) { tag($0) } }
                }
            }
        }
    }
    private func tag(_ t: String) -> some View {
        Text(t).font(.caption2).lineLimit(1).padding(.horizontal, 7).padding(.vertical, 2)
            .background(Brand.sunken, in: Capsule())
    }
}

// MARK: Beaches

/// Beaches (/beaches): today's flag and rip current risk, the forecast, what the flags mean, water quality at each
/// state sampling site, and every public beach access on a map.
struct BeachesView: View {
    @Environment(AppStore.self) private var store
    @State private var filter: Outdoors.AccessFilter = .all
    @State private var query = ""
    @State private var showAll = false

    private var conditions: [Row] { store.rows["beach-conditions"] ?? [] }
    private var sites: [Row] { store.rows["beach-water-sites"] ?? [] }
    private var access: [Row] { store.rows["beach-access"] ?? [] }
    private var parking: [Row] { store.rows["beach-parking"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "Outdoors · Beaches", title: "Beaches",
                     subtitle: "Today's flag and rip current risk, water quality at each state sampling site, and every public beach access.",
                     symbol: "beach.umbrella", tone: .teal)
            if conditions.isEmpty && access.isEmpty {
                if Outdoors.beachDatasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load the beaches", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                todaySection
                flagsSection
                waterSection
                accessSection
            }
            CardList {
                RouteRow(route: .parks, title: "Parks, boat ramps and trails", symbol: "tree")
                RowDivider(inset: 50)
                WebRow(title: "Beaches on BayCounty.me", detail: "Map, flag meanings and sources", symbol: "safari",
                       url: URL(string: "https://baycounty.me/beaches"))
            }
            FreshnessNote(key: "beach-conditions")
        }
        .navigationTitle("Beaches")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Outdoors.beachDatasets) }
        .refreshable { for i in Outdoors.beachDatasets { await store.load(i, force: true) } }
    }

    private var todaySection: some View {
        let fc = Outdoors.forecast(conditions)
        let now = fc.first
        let flag = Outdoors.flag(conditions)
        return PageSection(title: "Today at the beach", symbol: "sun.max", tone: .amber,
                           caption: "From the National Weather Service surf zone forecast. Flags can change during the day: check the pole at the beach.") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 14) {
                    HStack(alignment: .top, spacing: 0) {
                        Rectangle().fill(.secondary).frame(width: 3, height: 64)
                        VStack(spacing: 4) {
                            RoundedRectangle(cornerRadius: 3).fill(Color(hex: Outdoors.flagHex(flag?.color ?? ""))).frame(width: 40, height: 26)
                            if flag?.color == "Double red" {
                                RoundedRectangle(cornerRadius: 3).fill(Color(hex: Outdoors.flagHex("Double red"))).frame(width: 40, height: 26)
                            }
                        }
                    }
                    .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 3) {
                        Text("BEACH FLAG").font(.caption2.weight(.bold)).foregroundStyle(Brand.salmon)
                        Text(flag.map { "\($0.color) flag" } ?? "Not reported").font(.title2.weight(.bold))
                        if let m = flag?.meaning, !m.isEmpty { Text(m).font(.subheadline.weight(.semibold)) }
                    }
                    Spacer(minLength: 0)
                }
                .padding(16).frame(maxWidth: .infinity, alignment: .leading).card(18)
                .accessibilityElement(children: .combine)
                StatGrid {
                    KPICard(title: "Rip current risk", value: now?.string("rip_current_risk") ?? "—", symbol: "water.waves", tone: .salmon)
                    KPICard(title: "Surf", value: now?.string("surf_height") ?? "—", symbol: "wind", tone: .blue)
                    KPICard(title: "Water", value: (now?.string("water_temperature") ?? "—").replacingOccurrences(of: " degrees", with: "°F"), symbol: "thermometer.medium", tone: .teal)
                    KPICard(title: "UV index", value: now?.string("uv_index") ?? "—", symbol: "sun.max", tone: .amber)
                }
                ForEach(Outdoors.alerts(conditions)) { a in
                    Button { if let u = a.url("source_url") { store.open(u) } } label: {
                        TextRow(title: a.string("period") ?? "Alert", detail: a.string("summary"), badge: ("Alert", Brand.salmon))
                    }
                    .buttonStyle(.plain).card(14)
                }
                if fc.count > 1 {
                    CardList {
                        ForEach(fc.dropFirst()) { r in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(r.string("period") ?? "").font(.subheadline.weight(.semibold))
                                    Text(r.string("weather").map { w in [w, r.string("winds")].compactMap { $0 }.joined(separator: ", ") }
                                         ?? (r.string("summary") ?? "").replacingOccurrences(of: "*", with: ""))
                                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                                }
                                Spacer(minLength: 8)
                                VStack(alignment: .trailing, spacing: 2) {
                                    Text(r.string("rip_current_risk") ?? "—").font(.subheadline.weight(.bold)).foregroundStyle(riskColor(r.string("rip_current_risk")))
                                    Text("rip currents").font(.caption2).foregroundStyle(.secondary)
                                }
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10)
                            if r.id != fc.last?.id { RowDivider() }
                        }
                    }
                }
                Text("If you're caught in a rip current, swim parallel to shore, then back in. For a text when Panama City Beach's flags change, text PCBFLAGS to 888777.")
                    .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var flagsSection: some View {
        let legend = Outdoors.legend(conditions)
        return PageSection(title: "What the flags mean", symbol: "flag", tone: .salmon,
                           caption: "Double red flags close the water. No flag flying doesn't mean the water is safe.") {
            CardList {
                ForEach(legend) { l in
                    HStack(alignment: .top, spacing: 12) {
                        RoundedRectangle(cornerRadius: 3).fill(Color(hex: Outdoors.flagHex(l.string("flag_color") ?? ""))).frame(width: 26, height: 18).padding(.top, 2)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("\(l.string("flag_color") ?? ""): \(l.string("meaning") ?? "")").font(.subheadline.weight(.semibold))
                            Text(l.string("summary") ?? "").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .accessibilityElement(children: .combine)
                    if l.id != legend.last?.id { RowDivider(inset: 52) }
                }
            }
        }
    }

    private var waterSection: some View {
        let list = Outdoors.waterSites(sites)
        let poor = Outdoors.poorNow(sites, today: Self.today)
        return PageSection(title: "Water quality", symbol: "drop", tone: .blue,
                           caption: "Florida Healthy Beaches Program: enterococci per 100 mL. Good 0 to 35, moderate 36 to 70, poor 71 or more.") {
            VStack(alignment: .leading, spacing: 10) {
                Text(poor.isEmpty ? "No site was rated poor in the past six weeks." : "\(poor.count) site\(poor.count == 1 ? " was" : "s were") rated poor at a test in the past six weeks.")
                    .font(.subheadline)
                CardList {
                    ForEach(list) { s in
                        let rating = s.string("latest_rating")
                        HStack(alignment: .top) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(s.string("name") ?? "").font(.subheadline.weight(.semibold))
                                Text(["Latest \(s.string("latest_date") ?? "none")", s.number("latest_enterococcus").map { "\(Int($0)) per 100 mL" },
                                      s.bool("latest_advisory") == true ? "health advisory" : nil].compactMap { $0 }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(.secondary)
                                Text("\(Int(s.number("good") ?? 0)) good, \(Int(s.number("moderate") ?? 0)) moderate, \(Int(s.number("poor") ?? 0)) poor since \(s.string("first_date") ?? "")")
                                    .font(.caption2).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 6)
                            if let rating { Badge(text: rating, color: ratingColor(rating)) }
                        }
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .accessibilityElement(children: .combine)
                        if s.id != list.last?.id { RowDivider() }
                    }
                }
            }
        }
    }

    private var accessSection: some View {
        let list = Outdoors.accesses(access, filter: filter, query: query)
        let shown = showAll || !query.isEmpty ? list : Array(list.prefix(12))
        var pts: [MapPoint] = access.compactMap { point($0, id: "a" + $0.id, title: $0.string("name") ?? "Beach access", color: Brand.blue) }
        pts += Outdoors.waterSites(sites).compactMap { point($0, id: "w" + $0.id, title: $0.string("name") ?? "", color: ratingColor($0.string("latest_rating"))) }
        pts += parking.compactMap { point($0, id: "p" + $0.id, title: "County beach parking", color: .gray) }
        return PageSection(title: "Beach access and parking", symbol: "beach.umbrella", tone: .teal,
                           caption: "\(access.count) public accesses. Blue: access. Green to red: water sample site. Gray: county beach parking.") {
            VStack(alignment: .leading, spacing: 12) {
                PointsMap(points: pts) { p in if let r = p.row, let u = Outdoors.directions(r) { store.open(u) } }
                TextField("Search by name, number or street", text: $query)
                    .textFieldStyle(.roundedBorder)
                ChipRow(chips: Outdoors.AccessFilter.allCases.map { (id: $0, label: $0.label) }, selected: filter) { filter = $0; showAll = false }
                CardList {
                    ForEach(shown) { a in
                        Button { if let u = Outdoors.directions(a) { store.open(u) } } label: {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(a.string("name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                    Text([a.string("address"), a.string("area")].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                                    let tags = Outdoors.accessTags(a)
                                    if !tags.isEmpty { TagFlow(tags: tags) }
                                }
                                Spacer(minLength: 6)
                                Image(systemName: "arrow.triangle.turn.up.right.diamond").foregroundStyle(Brand.navy)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10).contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint("Opens directions")
                        if a.id != shown.last?.id { RowDivider() }
                    }
                }
                if shown.count < list.count {
                    Button("Show all \(list.count)") { showAll = true }
                        .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                }
            }
        }
    }
}

// MARK: Parks

/// Parks (/parks): every public park with its amenities, boat ramps, trails and each government's recreation pages.
struct ParksView: View {
    @Environment(AppStore.self) private var store
    @State private var filter: Outdoors.ParkFilter = .all
    @State private var gov = ""
    @State private var query = ""
    @State private var showAll = false

    private var parks: [Row] { store.rows["parks"] ?? [] }
    private var ramps: [Row] { store.rows["boat-ramps"] ?? [] }
    private var trails: [Row] { store.rows["trails"] ?? [] }
    private var rec: [Row] { store.rows["recreation-departments"] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Outdoors · Parks", title: "Parks, boat ramps and trails",
                     subtitle: "Every public park, boat ramp and trail, what each has, who runs it, and where to sign up for programs.",
                     symbol: "tree", tone: .teal)
            if parks.isEmpty {
                if Outdoors.parkDatasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load the parks", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                PointsMap(points: parks.compactMap { point($0, id: "k" + $0.id, title: $0.string("name") ?? "", color: Brand.good) }
                          + ramps.compactMap { point($0, id: "r" + $0.id, title: $0.string("name") ?? "", color: Brand.blue) }
                          + trails.compactMap { point($0, id: "t" + $0.id, title: $0.string("name") ?? "", color: Brand.amber) }) { p in
                    if let r = p.row, let u = Outdoors.directions(r) { store.open(u) }
                }
                parksSection
                signUpSection
                rampsSection
                trailsSection
            }
            CardList {
                RouteRow(route: .beaches, title: "Beaches", symbol: "beach.umbrella")
                RowDivider(inset: 50)
                WebRow(title: "Parks on BayCounty.me", detail: "Map and sources", symbol: "safari", url: URL(string: "https://baycounty.me/parks"))
            }
            FreshnessNote(key: "parks")
        }
        .navigationTitle("Parks")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Outdoors.parkDatasets) }
        .refreshable { for i in Outdoors.parkDatasets { await store.load(i, force: true) } }
    }

    private var kpis: some View {
        let miles = trails.compactMap { $0.number("miles") }.reduce(0, +)
        return StatGrid {
            KPICard(title: "Public parks", value: "\(parks.count)", caption: "Run by the cities, the county and the state", symbol: "tree", tone: .teal)
            KPICard(title: "With a playground", value: "\(parks.filter { $0.bool("playground") == true }.count)",
                    caption: "\(parks.filter { $0.bool("restroom") == true }.count) have restrooms", symbol: "figure.play", tone: .amber)
            KPICard(title: "Boat ramps", value: "\(ramps.count)", caption: "\(ramps.filter { ($0.string("water") ?? "").lowercased().hasPrefix("salt") }.count) on salt water", symbol: "sailboat", tone: .blue)
            KPICard(title: "Trail miles", value: "\(Int(miles.rounded()))", caption: "\(trails.count) named trails", symbol: "figure.hiking", tone: .salmon)
        }
    }

    private var parksSection: some View {
        var seen = Set<String>()
        var govs: [(id: String, label: String)] = [(id: "", label: "All")]
        for r in parks {
            if let g = r.string("gov_id"), !seen.contains(g) {
                seen.insert(g)
                govs.append((id: g, label: r.string("run_by") ?? g))
            }
        }
        let list = Outdoors.parks(parks, filter: filter, gov: gov, query: query)
        let shown = showAll || !query.isEmpty ? list : Array(list.prefix(12))
        return PageSection(title: "Parks", symbol: "tree", tone: .teal, caption: "\(list.count) of \(parks.count) parks. Tap one for directions.") {
            VStack(alignment: .leading, spacing: 12) {
                TextField("Search parks by name or street", text: $query).textFieldStyle(.roundedBorder)
                ChipRow(chips: govs, selected: gov) { gov = $0; showAll = false }
                ChipRow(chips: Outdoors.ParkFilter.allCases.map { (id: $0, label: $0.label) }, selected: filter) { filter = $0; showAll = false }
                CardList {
                    ForEach(shown) { p in
                        Button { if let u = Outdoors.directions(p) { store.open(u) } } label: {
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(p.string("name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                                    Text([p.string("address"), p.string("run_by").map { "Run by \($0)" }, p.number("acres").map { "\(Format.number($0)) acres" }]
                                        .compactMap { $0 }.joined(separator: " · "))
                                        .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
                                    let tags = Outdoors.parkTags(p)
                                    if !tags.isEmpty { TagFlow(tags: tags) }
                                }
                                Spacer(minLength: 6)
                                Image(systemName: "arrow.triangle.turn.up.right.diamond").foregroundStyle(Brand.navy)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10).contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityHint("Opens directions")
                        if p.id != shown.last?.id { RowDivider() }
                    }
                }
                if shown.count < list.count {
                    Button("Show all \(list.count)") { showAll = true }
                        .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                }
            }
        }
    }

    private var signUpSection: some View {
        PageSection(title: "Programs, leagues and rentals", symbol: "figure.run", tone: .amber, caption: "Each government runs its own sign-ups") {
            CardList {
                ForEach(rec) { d in
                    WebRow(title: d.string("name") ?? "", detail: d.string("programs_label") ?? "Parks and facilities", symbol: "arrow.up.right.square",
                           url: d.url("programs_url") ?? d.url("parks_url"))
                    if d.id != rec.last?.id { RowDivider(inset: 50) }
                }
            }
        }
    }

    private var rampsSection: some View {
        PageSection(title: "Boat ramps and launches", symbol: "sailboat", tone: .blue, caption: "\(ramps.count) public ramps") {
            CardList {
                ForEach(ramps) { r in
                    Button { if let u = Outdoors.directions(r) { store.open(u) } } label: {
                        TextRow(title: r.string("name") ?? "",
                                detail: [r.string("waterbody"), r.string("water").map { "\($0) water" }, r.string("run_by")].compactMap { $0 }.joined(separator: " · "))
                    }
                    .buttonStyle(.plain)
                    if r.id != ramps.last?.id { RowDivider() }
                }
            }
        }
    }

    private var trailsSection: some View {
        let list = trails.sorted { ($0.number("miles") ?? 0) > ($1.number("miles") ?? 0) }
        return PageSection(title: "Trails", symbol: "figure.hiking", tone: .salmon, caption: "Longest first. Miles add up each trail's mapped segments.") {
            CardList {
                ForEach(list) { t in
                    Button { if let u = Outdoors.directions(t) { store.open(u) } } label: {
                        TextRow(title: t.string("name") ?? "",
                                detail: [t.string("area"), t.string("surface"), t.string("uses")].compactMap { $0 }.joined(separator: " · "),
                                value: t.number("miles").map { String(format: "%.1f mi", $0) })
                    }
                    .buttonStyle(.plain)
                    if t.id != list.last?.id { RowDivider() }
                }
            }
        }
    }
}
