import SwiftUI
import BayCountyKit

/// Restaurant inspections (/restaurants): search first, then every place latest inspected first with its latest result
/// and a strip of its last six inspections. Reads the restaurants dataset; rules in BayCountyKit Restaurants. Same
/// screen as the Android RestaurantsScreen.
struct RestaurantsView: View {
    @Environment(AppStore.self) private var store
    @State private var query = ""
    @State private var city = ""
    @State private var show: Restaurants.Show = .latest
    @State private var limit = 40

    private var rows: [Row] { store.rows["restaurants"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "Living here · Restaurants", title: "Restaurant inspections",
                     subtitle: "Look up any restaurant, food truck or caterer and see what state inspectors found on every visit since 2016.",
                     symbol: "fork.knife", tone: .salmon)
            if rows.isEmpty {
                if store.errors["restaurants"] != nil {
                    ContentUnavailableView("Couldn't load restaurants", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                controls
                list
            }
            CardList {
                WebRow(title: "Closures, common problems and new places", detail: "On BayCounty.me", symbol: "safari",
                       url: URL(string: "https://baycounty.me/restaurants"))
            }
            FreshnessNote(key: "restaurants")
        }
        .navigationTitle("Restaurants")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Restaurants.datasets) }
        .refreshable { await store.load("restaurants", force: true) }
    }

    private var controls: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").foregroundStyle(Brand.blue)
                TextField("Restaurant, owner or street", text: $query)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .onChange(of: query) { limit = 40 }
                if !query.isEmpty {
                    Button { query = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary) }
                        .accessibilityLabel("Clear search")
                }
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 52)
            .background(Brand.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay { RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Brand.blue, lineWidth: 2) }
            Menu {
                Button("All cities") { city = ""; limit = 40 }
                ForEach(Restaurants.cities(rows), id: \.self) { c in Button(c) { city = c; limit = 40 } }
            } label: {
                HStack {
                    Text(city.isEmpty ? "All cities" : city).foregroundStyle(.primary)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down").font(.caption).foregroundStyle(.secondary)
                }
                .padding(.horizontal, 14).frame(minHeight: 46).card(14)
            }
            .accessibilityLabel("City, \(city.isEmpty ? "all cities" : city)")
            ChipRow(chips: Restaurants.Show.allCases.map { (id: $0, label: $0.label) }, selected: show) { show = $0; limit = 40 }
            let w = Restaurants.week(rows)
            if w.places > 0 {
                Text("**\(w.places)** places inspected in the week of \(Restaurants.dateLabel(w.start)).")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
        }
    }

    private var list: some View {
        let all = Restaurants.list(rows, query: query, city: city, show: show, today: Self.today)
        let shown = Array(all.prefix(limit))
        return VStack(alignment: .leading, spacing: 10) {
            Text("\(Format.number(Double(all.count))) place\(all.count == 1 ? "" : "s"), latest inspected first")
                .font(.footnote).foregroundStyle(.secondary)
            if shown.isEmpty {
                Text("Nothing matches. Try another name or street.").font(.subheadline).foregroundStyle(.secondary)
                    .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
            } else {
                CardList {
                    ForEach(shown) { r in
                        NavigationLink(value: Route.restaurant(r.string("license_number") ?? "")) { RestaurantRow(row: r) }
                            .buttonStyle(.plain)
                        if r.id != shown.last?.id { RowDivider(inset: 14) }
                    }
                }
                if all.count > shown.count {
                    Button("Show more") { limit += 60 }
                        .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                }
            }
            Text("The squares are the last six inspections, oldest to newest: green met standards, amber warning, red closed or fine recommended.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}

/// One place in the list: name, kind and city, then its latest result, date and six-visit strip.
struct RestaurantRow: View {
    let row: Row

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(row.string("business_name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                    .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                Text([row.string("kind"), row.string("city"), row.bool("licensed_now") == true ? nil : "No longer licensed"].compactMap { $0 }.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            VStack(alignment: .trailing, spacing: 4) {
                ResultPill(text: Restaurants.shortResult(row.string("last_result")) ?? "Not inspected yet", level: row.string("last_result_level"))
                Text(Restaurants.dateLabel(row.string("last_inspection"))).font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                if row.string("recent_results") != nil { InspectionStrip(recent: row.string("recent_results")) }
            }
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
    }
}

/// A result in its color: green met standards, amber warning, red closed or fine recommended.
struct ResultPill: View {
    let text: String
    let level: String?

    var body: some View {
        let c = Self.color(level)
        Text(text).font(.caption.weight(.semibold))
            .foregroundStyle(Restaurants.tone(level) == .warning ? Color.primary : c)
            .padding(.horizontal, 9).padding(.vertical, 3)
            .background(c.opacity(Restaurants.tone(level) == .warning ? 0.28 : 0.14), in: Capsule())
    }

    static func color(_ level: String?) -> Color {
        switch Restaurants.tone(level) {
        case .good: Brand.good
        case .warning: Brand.amber
        case .bad: Brand.salmon
        case .none: .secondary
        }
    }
}

/// The last six inspections as small squares, oldest on the left.
struct InspectionStrip: View {
    let recent: String?

    var body: some View {
        let lv = Restaurants.strip(recent)
        HStack(spacing: 3) {
            ForEach(Array(lv.enumerated()), id: \.offset) { _, l in
                RoundedRectangle(cornerRadius: 2.5, style: .continuous)
                    .fill(l.isEmpty ? Brand.hairline : ResultPill.color(l))
                    .frame(width: 10, height: 10)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Last inspections, oldest to newest: \(lv.filter { !$0.isEmpty }.joined(separator: ", "))")
    }
}

/// One restaurant (/restaurants/<name>-<license>): the plain summary, its numbers and every inspection since 2016,
/// read from /api/v1/datasets/restaurant-inspections by license number.
struct RestaurantDetailView: View {
    @Environment(AppStore.self) private var store
    let license: String
    @State private var visits: [Row]? = nil
    @State private var failed = false

    private var row: Row? { store.rows["restaurants"]?.first { $0.string("license_number") == license } }

    var body: some View {
        PageScroll {
            if let r = row {
                PageHero(kicker: "Restaurant inspections", title: r.string("business_name") ?? "",
                         subtitle: [r.string("kind"), r.string("address"), r.string("city")].compactMap { $0 }.joined(separator: " · "),
                         symbol: "fork.knife", tone: .salmon)
                Text(Restaurants.summary(r)).font(.body).padding(16).frame(maxWidth: .infinity, alignment: .leading).card(16)
                StatGrid {
                    KPICard(title: "Latest result", value: Restaurants.shortResult(r.string("last_result")) ?? "None yet",
                            caption: Restaurants.dateLabel(r.string("last_inspection")), symbol: "checkmark.seal", tone: .teal)
                    KPICard(title: "Inspections", value: Format.number(r.number("inspections") ?? 0),
                            caption: "\(Int(r.number("inspections_last_year") ?? 0)) in the last 12 months", symbol: "checklist", tone: .blue)
                    KPICard(title: "High-priority violations", value: Format.number(r.number("high_priority_last_year") ?? 0),
                            caption: "Cited in the last 12 months", symbol: "exclamationmark.triangle", tone: .amber)
                    KPICard(title: "Emergency closures", value: Format.number(r.number("closures") ?? 0),
                            caption: r.string("last_closure").map { "Last \(Restaurants.dateLabel($0))" } ?? "Since 2016", symbol: "flag", tone: .salmon)
                }
                if let who = r.string("licensee") {
                    CardList { FactRow(label: "License holder", value: who) }
                }
                PageSection(title: "Every inspection since 2016", symbol: "checklist", tone: .blue, caption: "Newest first") {
                    history
                }
                CardList {
                    WebRow(title: "Open on BayCounty.me", detail: "With the violation names for every visit", symbol: "safari", url: Restaurants.pageURL(r))
                }
            } else if store.errors["restaurants"] != nil {
                ContentUnavailableView("Couldn't load this restaurant", systemImage: "wifi.slash")
            } else {
                ProgressView().frame(maxWidth: .infinity, minHeight: 160)
            }
        }
        .navigationTitle(row?.string("business_name") ?? "Restaurant")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let r = row {
                ToolbarItem(placement: .topBarTrailing) {
                    let url = Restaurants.pageURL(r)
                    ShareMenu(text: RecordShare.page(title: r.string("business_name") ?? "Restaurant",
                                                     summary: [[r.string("kind"), r.string("address"), r.string("city")].compactMap { $0 }.joined(separator: " · "),
                                                               Restaurants.summary(r)],
                                                     path: url?.path ?? "/restaurants"),
                              url: url)
                }
            }
        }
        .task {
            await store.load(Restaurants.datasets)
            do { visits = try await store.client.restaurantInspections(license: license) } catch { failed = true }
        }
    }

    @ViewBuilder private var history: some View {
        if let v = visits {
            if v.isEmpty {
                Text("No inspections on file yet.").font(.subheadline).foregroundStyle(.secondary)
            } else {
                CardList {
                    ForEach(v) { x in
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(spacing: 8) {
                                Text(Restaurants.dateLabel(x.string("date"))).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                Spacer(minLength: 0)
                                ResultPill(text: x.string("result") ?? "", level: x.string("result_level"))
                            }
                            Text(Restaurants.visitLabel(x)).font(.subheadline.weight(.semibold))
                            Text(Restaurants.counts(x)).font(.caption).foregroundStyle(.secondary)
                            if let items = x.string("violation_items") {
                                Text(items).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .padding(.horizontal, 14).padding(.vertical, 11)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(x.string("disposition") == "Emergency order recommended" ? Brand.salmon.opacity(0.08) : Color.clear)
                        .accessibilityElement(children: .combine)
                        if x.id != v.last?.id { RowDivider(inset: 14) }
                    }
                }
            }
        } else if failed {
            Text("Couldn't load the inspections. Pull to try again, or open the page on BayCounty.me.").font(.subheadline).foregroundStyle(.secondary)
        } else {
            ProgressView().frame(maxWidth: .infinity, minHeight: 80)
        }
    }
}
