import SwiftUI
import BayCountyKit

/// Events (/events): what's happening around the county in the next two months, from the community-events dataset.
struct EventsView: View {
    @Environment(AppStore.self) private var store
    @State private var town = ""
    @State private var kind = ""
    @State private var oneOff = false
    @State private var query = ""
    @State private var days = 7

    private var rows: [Row] { store.rows[Events.dataset] ?? [] }

    var body: some View {
        let today = Events.todayKey()
        let list = Events.upcoming(rows, today: today, town: town.isEmpty ? nil : town, kind: kind.isEmpty ? nil : kind, oneOff: oneOff, query: query)
        let groups = Events.byDay(list, today: today)
        PageScroll {
            PageHero(kicker: "Community · Calendar", title: "Events in Bay County",
                     subtitle: "What's happening around the county, from the county and city calendars, the library system, the visitor bureaus and the chambers.",
                     symbol: "calendar", tone: .salmon)
            if rows.isEmpty {
                if store.errors[Events.dataset] != nil {
                    ContentUnavailableView("Couldn't load events", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                let all = Events.upcoming(rows, today: today)
                StatGrid {
                    KPICard(title: "This week", value: "\(all.filter { String(($0.string("starts") ?? "").prefix(10)) <= Events.plusDays(7) }.count)",
                            caption: "Events in the next seven days", symbol: "calendar", tone: .salmon)
                    KPICard(title: "Public meetings", value: "\(all.filter { $0.string("category") == "Public meeting" }.count)",
                            caption: "Commissions, boards and workshops", symbol: "building.columns", tone: .blue)
                }
                VStack(alignment: .leading, spacing: 10) {
                    ChipRow(chips: [(id: "", label: "Every town")] + Events.towns(rows).map { (id: $0, label: $0) }, selected: town) { town = $0; days = 7 }
                    ChipRow(chips: [(id: "", label: "All kinds")] + Events.kinds.map { (id: $0, label: $0) }, selected: kind) { kind = $0; days = 7 }
                    TextField("Search events, places, organizers", text: $query)
                        .textFieldStyle(.roundedBorder)
                    Toggle("One-off events only", isOn: $oneOff).font(.subheadline)
                }
                if groups.isEmpty {
                    Text("No upcoming events match.").font(.subheadline).foregroundStyle(.secondary)
                        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                }
                ForEach(Array(groups.prefix(days)), id: \.day) { g in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text(Events.dayLabel(g.day, today: today)).font(.headline)
                            Spacer()
                            Text("\(g.rows.count)").font(.caption).foregroundStyle(.secondary)
                        }
                        CardList {
                            ForEach(g.rows) { r in
                                EventRow(row: r, showSource: true)
                                if r.id != g.rows.last?.id { RowDivider(inset: 86) }
                            }
                        }
                    }
                }
                if groups.count > days {
                    Button("Show more days") { days += 7 }
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .card(14)
                }
            }
            Text("Times are local. Details change, so check the organizer's page (tap an event) before you go.")
                .font(.caption).foregroundStyle(.secondary)
            FreshnessNote(key: Events.dataset)
        }
        .navigationTitle("Events")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Events.dataset) }
        .refreshable { await store.load(Events.dataset, force: true) }
    }
}

/// One event: time, title, place and kind. Opens the organizer's page.
struct EventRow: View {
    @Environment(AppStore.self) private var store
    let row: Row
    var showSource = false

    var body: some View {
        Button { if let u = row.url("url") { store.open(u) } } label: {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(Events.time(row)).font(.caption.weight(.semibold).monospacedDigit()).foregroundStyle(.secondary)
                    .frame(width: 60, alignment: .leading)
                VStack(alignment: .leading, spacing: 3) {
                    Text(row.string("title") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                        .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                    let place = [row.string("venue"), row.string("town"), showSource ? row.string("source") : nil].compactMap { $0 }.joined(separator: " · ")
                    if !place.isEmpty { Text(place).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading) }
                    Badge(text: row.string("category") ?? "", color: EventRow.color(row.string("category")))
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14).padding(.vertical, 11)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the event page")
    }

    static func color(_ c: String?) -> Color {
        switch c { case "Public meeting": Brand.navy; case "Library": Brand.good; case "Chamber": Brand.amber; default: Brand.salmon }
    }
}
