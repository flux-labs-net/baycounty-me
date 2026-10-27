import SwiftUI
import BayCountyKit

/// Utilities and trash day (/utilities): who provides water, sewer, power, gas and garbage at an address, its pickup
/// days, holiday changes and the typical water bill. Reads /api/v1/utilities, the same answer the site's page shows.
/// Opens on the given address, else the saved home, else a search.
struct UtilitiesView: View {
    @Environment(AppStore.self) private var store
    var match: AddressMatch? = nil
    @State private var picked: AddressMatch?
    @State private var query = ""
    @State private var results: [AddressMatch] = []
    @State private var message: String?
    @State private var lookup: UtilityLookup?
    @State private var failed = false

    private var current: AddressMatch? { picked ?? match ?? store.home }

    var body: some View {
        PageScroll {
            PageHero(kicker: "What you pay", title: "Utilities and trash day",
                     subtitle: "Who provides your water, sewer, power, gas and garbage pickup, your trash day, holiday changes and what your city charges.",
                     symbol: "trash", tone: .teal)
            if !query.isEmpty || current == nil { searchResults }
            if let m = current {
                VStack(alignment: .leading, spacing: 4) {
                    Text(m.display).font(.title3.weight(.semibold))
                    Text(lookup.map { $0.area == "county" ? "Unincorporated Bay County" : "City of \($0.areaName)" } ?? m.subtitle)
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                if let l = lookup {
                    UtilitiesReport(lookup: l)
                } else if failed {
                    ContentUnavailableView("Couldn't look up this address", systemImage: "wifi.slash",
                                           description: Text("The map servers didn't answer. Pull to try again."))
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 120)
                }
            }
            CardList {
                RouteRow(route: .dataset("utility-rates"), title: "Every utility charge", detail: "Base fees, tiers, garbage and stormwater by city", symbol: "drop")
                RowDivider(inset: 50)
                RouteRow(route: .dataset("utility-providers"), title: "Every provider", detail: "By city and service", symbol: "bolt")
                RowDivider(inset: 50)
                WebRow(title: "Utilities on BayCounty.me", detail: "Every city at a glance, outages and holiday schedules", symbol: "safari",
                       url: URL(string: "https://baycounty.me/utilities"))
            }
            Text("The address you look up isn't kept. Pickup days come from each city's route map; your bill names your electric provider.")
                .font(.footnote).foregroundStyle(.secondary)
        }
        .navigationTitle("Utilities")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: "e.g. 825 Ohio Ave")
        .task(id: query) { await search() }
        .task(id: current?.id) { await load() }
        .refreshable { await load(force: true) }
    }

    @ViewBuilder private var searchResults: some View {
        if let message { Text(message).font(.subheadline).foregroundStyle(.secondary) }
        if !results.isEmpty {
            CardList {
                ForEach(Array(results.enumerated()), id: \.element.id) { i, m in
                    Button { picked = m; query = ""; results = [] } label: {
                        RowLabel(title: m.display, detail: m.subtitle.isEmpty ? nil : m.subtitle)
                    }
                    .buttonStyle(.plain)
                    if i < results.count - 1 { RowDivider() }
                }
            }
        } else if current == nil && query.isEmpty {
            Text("Search for a Bay County address to see who provides each utility and your trash day.")
                .font(.subheadline).foregroundStyle(.secondary)
        }
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 3 else { results = []; message = nil; return }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        do {
            let r = try await store.gis.search(q)
            guard !Task.isCancelled else { return }
            results = r.matches
            message = r.matches.isEmpty ? "No matching address. Try just the house number and street name." : nil
        } catch {
            guard !Task.isCancelled else { return }
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }

    private func load(force: Bool = false) async {
        guard let m = current else { return }
        lookup = nil
        failed = false
        if Self.screenshotSample, let url = Bundle.main.url(forResource: "utilities-sample", withExtension: "json"),
           let data = try? Data(contentsOf: url), let sample = try? UtilityLookup.decode(data) {
            lookup = sample; return
        }
        do { lookup = try await store.client.utilities(at: m.point) } catch { failed = true }
    }

    /// Automated screenshots (`-screen utilities:<address>`) show a saved /api/v1/utilities answer for 825 Ohio Ave,
    /// so the picture doesn't depend on the live servers.
    private static var screenshotSample: Bool {
        let a = ProcessInfo.processInfo.arguments
        guard let i = a.firstIndex(of: "-screen"), i + 1 < a.count else { return false }
        return a[i + 1].hasPrefix("utilities:")
    }
}

/// The trash-day cards, providers, holiday changes and typical bill for one lookup. Also used on the address report.
struct UtilitiesReport: View {
    @Environment(AppStore.self) private var store
    let lookup: UtilityLookup
    var compact = false

    private static let day: DateFormatter = { let f = DateFormatter(); f.dateFormat = "EEEE, MMMM d"; return f }()

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if !lookup.pickup.isEmpty {
                PageSection(title: "Trash day", symbol: "trash", tone: .teal) {
                    ForEach(lookup.pickup, id: \.self) { pickupCard($0) }
                }
            }
            if !compact {
                PageSection(title: "Who provides what", symbol: "bolt", tone: .blue) {
                    CardList {
                        let rows = lookup.otherServices.flatMap { s in s.providers.enumerated().map { (s, $0.offset, $0.element) } }
                        ForEach(Array(rows.enumerated()), id: \.offset) { i, r in
                            providerRow(r.0, index: r.1, r.2)
                            if i < rows.count - 1 { RowDivider() }
                        }
                    }
                }
                if !lookup.holidays.isEmpty {
                    PageSection(title: "Holiday changes", symbol: "calendar", tone: .amber) {
                        CardList {
                            ForEach(Array(lookup.holidays.enumerated()), id: \.offset) { i, h in
                                TextRow(title: h.holiday, detail: [h.whenObserved, h.garbage.map { "Garbage: \($0)" }, h.yardWaste.map { "Yard waste: \($0)" }].compactMap { $0 }.joined(separator: "\n"))
                                if i < lookup.holidays.count - 1 { RowDivider() }
                            }
                        }
                    }
                }
                if let bill = lookup.typicalBill {
                    CardList { FactRow(label: "Typical water and sewer bill", value: String(format: "$%.2f", bill), detail: "5,000 gallons a month") }
                }
            }
        }
    }

    private func pickupCard(_ p: UtilityLookup.Pickup) -> some View {
        let prov = lookup.provider(for: p)
        return VStack(alignment: .leading, spacing: 6) {
            Text(p.serviceLabel.uppercased()).font(.caption.weight(.bold)).foregroundStyle(.secondary)
            if let days = p.days {
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    Text(days).font(.title3.weight(.bold))
                    if let z = p.zoneText { Text("(\(z))").font(.subheadline).foregroundStyle(.secondary) }
                }
                if let next = PickupDays.next(days) { Text("Next: \(Self.day.string(from: next))").font(.subheadline).foregroundStyle(.secondary) }
            }
            if let area = p.zoneArea { Text([p.days == nil ? p.zone : nil, area].compactMap { $0 }.joined(separator: ": ")).font(.caption).foregroundStyle(.secondary) }
            if let rule = p.rule { Text(rule).font(.subheadline) }
            if let notes = p.notes { Text(notes).font(.caption).foregroundStyle(.secondary) }
            if let prov {
                Text(prov.provider).font(.subheadline.weight(.semibold))
                links(prov)
            } else {
                Text(p.provider).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(16)
    }

    private func providerRow(_ s: UtilityLookup.Service, index: Int, _ p: UtilityLookup.Provider) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(s.serviceLabel.uppercased() + (s.providers.count > 1 ? (index == 0 ? " · MOST LIKELY" : " · OR") : ""))
                .font(.caption2.weight(.bold)).foregroundStyle(.secondary)
            Button { open(p) } label: {
                Text(p.provider).font(.subheadline.weight(.semibold)).foregroundStyle(p.entityId == nil ? Color.primary : Brand.navy)
                    .multilineTextAlignment(.leading)
            }
            .buttonStyle(.plain)
            .disabled(p.entityId == nil)
            if let n = p.notes { Text(n).font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true) }
            links(p)
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func links(_ p: UtilityLookup.Provider) -> some View {
        HStack(spacing: 16) {
            if let phone = p.phone, let url = URL(string: "tel:" + phone.filter { $0.isNumber || $0 == "+" }) {
                Link(destination: url) { Label(phone, systemImage: "phone") }
            }
            if let w = p.website, let url = URL(string: w) { Button { store.open(url) } label: { Label("Website", systemImage: "safari") } }
            if let o = p.outageUrl, o != p.website, let url = URL(string: o) { Button { store.open(url) } label: { Label("Outages", systemImage: "bolt.slash") } }
        }
        .font(.caption.weight(.semibold))
        .foregroundStyle(Brand.navy)
        .buttonStyle(.plain)
    }

    /// A government opens its own screen; any other provider opens its profile on the site.
    private func open(_ p: UtilityLookup.Provider) {
        guard let id = p.entityId else { return }
        let parts = id.split(separator: ":", maxSplits: 1).map(String.init)
        guard parts.count == 2 else { return }
        store.openSite("/profile/\(parts[0])/\(parts[1])")
    }
}

/// The utilities section on an address report: trash day, with a link to the full screen.
struct AddressUtilitiesSection: View {
    @Environment(AppStore.self) private var store
    let match: AddressMatch
    @State private var lookup: UtilityLookup?
    @State private var failed = false

    var body: some View {
        Section {
            if let l = lookup {
                ForEach(l.pickup, id: \.self) { p in
                    LabeledContent(p.serviceLabel) {
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(p.days ?? "See details")
                            if let z = p.zoneText { Text(z).font(.caption).foregroundStyle(.secondary) }
                        }
                    }
                }
                ForEach(l.otherServices.filter { ["water", "electric"].contains($0.service) }, id: \.self) { s in
                    LabeledContent(s.serviceLabel, value: s.providers.map(\.provider).joined(separator: " or "))
                }
                NavigationLink(value: Route.utilities(match)) { Text("All utilities, phone numbers and holidays") }
            } else if failed {
                Text("The utility lookup didn't answer.").foregroundStyle(.secondary)
                NavigationLink(value: Route.utilities(match)) { Text("Try the utilities screen") }
            } else {
                HStack { ProgressView(); Text("Looking up utilities…").foregroundStyle(.secondary) }
            }
        } header: { Text("Utilities and trash day") }
        .task(id: match.id) {
            do { lookup = try await store.client.utilities(at: match.point) } catch { failed = true }
        }
    }
}
