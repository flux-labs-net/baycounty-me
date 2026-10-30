import SwiftUI
import BayCountyKit

/// Emergencies and alerts (/emergency): what's happening now (from /api/v1/emergency, checked every 5 minutes on the
/// server), the evacuation zone for the saved address or any address, every county shelter, phone alerts, and the
/// numbers to call. Falls back to the last daily archive when the live feed can't be reached.
struct EmergencyView: View {
    @Environment(AppStore.self) private var store
    @State private var feed: Emergency.Feed?
    @State private var live = false
    @State private var kind = ""
    @State private var address = ""
    @State private var zone: Emergency.ZoneResult?
    @State private var zoneError: String?
    @State private var looking = false
    /// The saved home shown in the address box, so a typed address is never replaced.
    @State private var homeShown: String?

    private var resources: [Row] { store.rows["emergency-resources"] ?? [] }
    /// The live feed once it loads; until then (or offline) the last daily archive.
    private var shown: Emergency.Feed? {
        feed ?? store.rows["emergency-notices"].map {
            Emergency.offlineFeed(notices: $0, shelters: store.rows["emergency-shelters"] ?? [], zones: store.rows["evacuation-zones"] ?? [])
        }
    }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Take part · Stay safe", title: "Emergencies and alerts",
                     subtitle: "Weather warnings, evacuation orders, shelters, boil-water notices and road closures in Bay County, checked every few minutes.",
                     symbol: "exclamationmark.triangle", tone: .salmon)
            if let feed = shown {
                status(feed)
                kpis(feed)
                zoneSection
                nowSection(feed)
                sheltersSection(feed)
                numbersSection
            } else {
                ProgressView().frame(maxWidth: .infinity, minHeight: 160)
            }
            CardList {
                RouteRow(route: .hurricanePrep, title: "Hurricane prep", detail: "Sandbags, generators, rebuild money by ZIP code", symbol: "hurricane")
                RowDivider(inset: 50)
                RouteRow(route: .myHome, title: "Phone alerts", detail: "Sign in, then turn them on in My home settings", symbol: "bell.badge")
                RowDivider(inset: 50)
                WebRow(title: "Zone map and every notice", detail: "On BayCounty.me", symbol: "safari", url: URL(string: "https://baycounty.me/emergency"))
            }
            Text("In an emergency, call 911. BayCounty.me is an independent site: follow instructions from emergency officials.")
                .font(.footnote).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        .navigationTitle("Emergencies")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.load(Emergency.datasets)
            await loadFeed()
        }
        // The saved home (the account's, when signed in) is looked up right away, and again if it changes.
        .task(id: store.home?.id) {
            guard let home = store.home, address.isEmpty || address == homeShown else { return }
            address = home.display; homeShown = home.display
            await lookup(home: home)
        }
        .refreshable { await loadFeed() }
    }

    // MARK: Loading

    private func loadFeed() async {
        do {
            let r = try await store.client.get(Emergency.feedPath)
            feed = try Emergency.parseFeed(r.data)
            live = r.freshness == .live
        } catch {
            feed = Emergency.offlineFeed(notices: store.rows["emergency-notices"] ?? [], shelters: store.rows["emergency-shelters"] ?? [],
                                         zones: store.rows["evacuation-zones"] ?? [])
            live = false
        }
    }

    private func lookup(home: AddressMatch? = nil) async {
        let url = home.map { Emergency.zoneURL(lat: $0.point.y, lng: $0.point.x) } ?? Emergency.zoneURL(address: address)
        looking = true; zoneError = nil
        defer { looking = false }
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            zone = try Emergency.parseZone(data)
        } catch { zoneError = "Couldn't look that up. Check your connection and try again." }
    }

    // MARK: Sections

    private func status(_ f: Emergency.Feed) -> some View {
        let tone: Tone = f.count("evacuation") > 0 ? .salmon : f.notices.isEmpty ? .teal : .amber
        return HStack(alignment: .top, spacing: 12) {
            ToneIcon(symbol: f.count("evacuation") > 0 ? "exclamationmark.octagon" : "bell", tone: tone, size: 40)
            VStack(alignment: .leading, spacing: 4) {
                Text(f.headline).font(.headline).fixedSize(horizontal: false, vertical: true)
                Text(live ? "Checked \(f.checkedAt.map { $0.formatted(.relative(presentation: .named)) } ?? "recently")." : "From the last saved check. Pull to refresh.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading).card(18)
        .accessibilityElement(children: .combine)
    }

    private func kpis(_ f: Emergency.Feed) -> some View {
        StatGrid {
            KPICard(title: "Weather alerts", value: "\(f.count("weather"))", symbol: "cloud.bolt.rain", tone: .blue)
            KPICard(title: "Evacuation orders", value: "\(f.count("evacuation"))", symbol: "car.side.arrowtriangle.up.fill", tone: .salmon)
            KPICard(title: "Shelters open", value: "\(f.sheltersOpen)", symbol: "house.lodge", tone: .teal)
            KPICard(title: "Boil-water notices", value: "\(f.count("boil-water"))", symbol: "drop.triangle", tone: .amber)
        }
    }

    private var zoneSection: some View {
        PageSection(title: "Your evacuation zone", symbol: "map", tone: .blue, caption: "From Bay County's evacuation zone map. Zone A leaves first.") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    TextField("Street address, like 825 Ohio Ave", text: $address)
                        .textContentType(.fullStreetAddress).submitLabel(.search)
                        .onSubmit { Task { await lookup() } }
                        .padding(.horizontal, 12).frame(minHeight: 44)
                        .background(Brand.hairline.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    Button("Look up") { Task { await lookup() } }
                        .buttonStyle(.borderedProminent).disabled(address.trimmingCharacters(in: .whitespaces).count < 4 || looking)
                }
                if let h = homeShown, address == h {
                    Text("This is your saved home. Type another address to look somewhere else.").font(.caption).foregroundStyle(.secondary)
                }
                if looking { ProgressView() }
                if let zoneError { Text(zoneError).font(.subheadline).foregroundStyle(.secondary) }
                if let z = zone { zoneCard(z) }
            }
        }
    }

    private func zoneCard(_ z: Emergency.ZoneResult) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                Text(z.zone ?? "–").font(.title.weight(.bold)).foregroundStyle(.white)
                    .frame(width: 52, height: 52)
                    .background(zoneColor(z.zone), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(z.found ? (z.zone.map { "Evacuation Zone \($0)" } ?? "Not in an evacuation zone") : "No match").font(.headline)
                    if let a = z.address { Text(a.capitalized).font(.caption).foregroundStyle(.secondary) }
                }
            }
            Text(z.whatToDo).font(.subheadline).fixedSize(horizontal: false, vertical: true)
            if z.orders.isEmpty {
                Text("No evacuation order is in effect right now.").font(.footnote).foregroundStyle(.secondary)
            } else {
                ForEach(Array(z.orders.enumerated()), id: \.offset) { _, o in
                    Label(o.title, systemImage: o.includesYou ? "exclamationmark.octagon.fill" : "info.circle")
                        .font(.subheadline.weight(o.includesYou ? .semibold : .regular)).fixedSize(horizontal: false, vertical: true)
                }
            }
            if !z.nearestShelters.isEmpty {
                Text("Nearest county shelters (open only when the county opens them)").font(.footnote.weight(.semibold))
                ForEach(z.nearestShelters) { s in
                    Text("\(s.string("name") ?? "") · \(s.number("miles").map { String(format: "%.1f mi", $0) } ?? "") · \(s.string("status") ?? "")")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
        }
        .padding(16).frame(maxWidth: .infinity, alignment: .leading).card(18)
    }

    private func zoneColor(_ z: String?) -> Color {
        switch z {
        case "A": Color(red: 0.82, green: 0.29, blue: 0.36)
        case "B": Color(red: 0.93, green: 0.55, blue: 0.23)
        case "C": Color(red: 0.75, green: 0.62, blue: 0.13)
        case "D": Color(red: 0.31, green: 0.62, blue: 0.41)
        default: .gray
        }
    }

    private func nowSection(_ f: Emergency.Feed) -> some View {
        let present = Emergency.kinds.filter { k in f.notices.contains { $0.string("kind") == k } }
        let chips = [(id: "", label: "Everything")] + present.map { (id: $0, label: Emergency.label($0)) }
        let list = kind.isEmpty ? f.notices : f.notices.filter { $0.string("kind") == kind }
        return PageSection(title: "Happening now", symbol: "bell", tone: .salmon, caption: "Most serious first") {
            VStack(alignment: .leading, spacing: 10) {
                if present.count > 1 { ChipRow(chips: chips, selected: kind) { kind = $0 } }
                if list.isEmpty {
                    Text("Nothing posted right now.").font(.subheadline).foregroundStyle(.secondary)
                        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                }
                ForEach(list) { noticeCard($0) }
            }
        }
    }

    private func noticeCard(_ n: Row) -> some View {
        let k = n.string("kind") ?? "storm"
        let more = [n.string("summary").flatMap { $0 == n.string("title") ? nil : $0 }, n.string("instruction")].compactMap { $0 }.joined(separator: "\n\n")
        return VStack(alignment: .leading, spacing: 6) {
            Label(k == "weather" ? (n.string("event") ?? "Weather") : Emergency.label(k), systemImage: Emergency.symbol(k))
                .font(.caption.weight(.semibold)).foregroundStyle(.secondary).textCase(.uppercase)
            Text(n.string("title") ?? "").font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
            if let a = n.string("area") { Text(a).font(.footnote).foregroundStyle(.secondary).lineLimit(3) }
            if !more.isEmpty {
                DisclosureGroup("Details") { Text(more).font(.footnote).fixedSize(horizontal: false, vertical: true).padding(.top, 4) }
                    .font(.footnote)
            }
            HStack(spacing: 6) {
                Text([n.string("source"), Emergency.posted(n).nilIfEmpty].compactMap { $0 }.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                if let u = n.url("url") { Button("Source") { store.open(u) }.font(.caption) }
            }
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
    }

    private func sheltersSection(_ f: Emergency.Feed) -> some View {
        PageSection(title: "Shelters", symbol: "house.lodge", tone: .teal,
                    caption: "Not every shelter opens for every storm. Plan to stay with family or friends outside the zone if you can; special needs shelters need registration ahead of time.") {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(Emergency.sheltersByType(f.shelters), id: \.type) { g in
                    Text(Emergency.shelterTypeLabel(g.type)).font(.subheadline.weight(.semibold))
                    CardList {
                        ForEach(g.rows) { s in
                            HStack(alignment: .top, spacing: 12) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(s.string("name") ?? "").font(.subheadline).fixedSize(horizontal: false, vertical: true)
                                    Text(s.string("address") ?? "").font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                                }
                                Spacer()
                                Text((s.string("status") ?? "").capitalized).font(.caption.weight(.bold))
                                    .foregroundStyle(s.string("status") == "open" ? Brand.good : .secondary)
                            }
                            .padding(.horizontal, 14).padding(.vertical, 10)
                            if s.id != g.rows.last?.id { RowDivider() }
                        }
                    }
                }
            }
        }
    }

    private var numbersSection: some View {
        PageSection(title: "Phone numbers and links", symbol: "phone", tone: .blue) {
            CardList {
                ForEach(resources) { r in
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(r.string("name") ?? "").font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                            if let a = r.string("about") { Text(a).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
                        }
                        Spacer()
                        if let p = r.string("phone"), let tel = URL(string: "tel:" + p.filter { $0.isNumber }) {
                            Link(p, destination: tel).font(.caption.weight(.semibold).monospacedDigit())
                        } else if let u = r.url("url") {
                            Button { store.open(u) } label: { Image(systemName: "arrow.up.right.square") }.accessibilityLabel("Open \(r.string("name") ?? "")")
                        }
                    }
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    if r.id != resources.last?.id { RowDivider() }
                }
            }
        }
    }
}

private extension String {
    var nilIfEmpty: String? { isEmpty ? nil : self }
}
