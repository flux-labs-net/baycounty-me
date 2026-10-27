import SwiftUI
import BayCountyKit

/// Volunteer (/volunteer): open volunteer needs from local nonprofits and the nonprofits that rely on volunteers, filtered
/// by one plain cause. Reads the volunteer-needs and volunteer-orgs datasets. Same sections as the Android VolunteerScreen.
struct VolunteerView: View {
    @Environment(AppStore.self) private var store
    @State private var cause: String = ""
    @State private var allNeeds = false
    @State private var allOrgs = false

    private var needs: [Row] { store.rows["volunteer-needs"] ?? [] }
    private var orgs: [Row] { store.rows["volunteer-orgs"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "Take part · Volunteer", title: "Volunteer in Bay County",
                     subtitle: "Local nonprofits looking for help right now, and the groups that rely on volunteers year-round.",
                     symbol: "hand.raised", tone: .teal)
            if needs.isEmpty && orgs.isEmpty {
                if Volunteer.datasets.contains(where: { store.errors[$0] != nil }) {
                    ContentUnavailableView("Couldn't load volunteer needs", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                ChipRow(chips: [(id: "", label: "All causes")] + Volunteer.causes(in: needs, orgs).map { (id: $0, label: $0) }, selected: cause) {
                    cause = $0; allNeeds = false; allOrgs = false
                }
                needsSection
                orgsSection
                howToHelp
            }
            CardList {
                RouteRow(route: .dataset("nonprofits"), title: "All nonprofits", symbol: "heart.text.square")
                RowDivider(inset: 50)
                WebRow(title: "Volunteer on BayCounty.me", detail: "Search every need and nonprofit", symbol: "safari",
                       url: URL(string: "https://baycounty.me/volunteer"))
            }
            FreshnessNote(key: "volunteer-needs")
        }
        .navigationTitle("Volunteer")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Volunteer.datasets) }
        .refreshable { for i in Volunteer.datasets { await store.load(i, force: true) } }
    }

    private var kpis: some View {
        let open = Volunteer.open(needs, today: Self.today)
        let posting = Set(open.compactMap { $0.string("organization") }).count
        let reported = orgs.compactMap { $0.number("volunteers_reported") }.reduce(0, +)
        return StatGrid {
            KPICard(title: "Open needs", value: "\(open.count)", caption: "From \(posting) organizations", symbol: "hand.raised", tone: .teal)
            KPICard(title: "Posted by local nonprofits", value: "\(open.filter { $0.string("nonprofit_id") != nil }.count)",
                    caption: "The rest are regional groups serving the county", symbol: "heart.text.square", tone: .salmon)
            KPICard(title: "Nonprofits that use volunteers", value: "\(orgs.count)", caption: "On their IRS filing, or posting a need now", symbol: "person.3", tone: .blue)
            KPICard(title: "Volunteers reported", value: Format.number(reported), caption: "Latest Form 990s", symbol: "chart.bar", tone: .amber)
        }
    }

    private var needsSection: some View {
        let list = Volunteer.open(needs, today: Self.today, cause: cause.isEmpty ? nil : cause)
        let shown = allNeeds ? list : Array(list.prefix(6))
        return PageSection(title: "Open needs right now", symbol: "hand.raised", tone: .teal,
                           caption: "Sign up on the organization's board. Check the details there before you go.") {
            VStack(alignment: .leading, spacing: 12) {
                if list.isEmpty {
                    Text("No open needs for this cause. Try another, or reach out to one of the nonprofits below.")
                        .font(.subheadline).foregroundStyle(.secondary).padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                } else {
                    CardList {
                        ForEach(shown) { r in
                            needRow(r)
                            if r.id != shown.last?.id { RowDivider(inset: 14) }
                        }
                    }
                    if !allNeeds && list.count > shown.count {
                        Button("Show \(list.count - shown.count) more") { allNeeds = true }
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                    }
                }
            }
        }
    }

    private func needRow(_ r: Row) -> some View {
        Button { store.open(r.url("url")) } label: {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Badge(text: r.string("cause") ?? "", color: Brand.good)
                    Badge(text: Volunteer.when(r), color: .secondary)
                }
                Text(r.string("title") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                    .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                Text("\(r.string("organization") ?? "") · \(Volunteer.whereLabel(r))").font(.caption).foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                if let d = r.string("description") {
                    Text(d).font(.caption).foregroundStyle(.primary).lineLimit(3).multilineTextAlignment(.leading)
                }
                Text("Sign up via \(r.string("board") ?? "the board")").font(.caption.weight(.semibold)).foregroundStyle(Brand.navy)
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens the sign-up page")
    }

    private var orgsSection: some View {
        let list = Volunteer.orgs(orgs, cause: cause.isEmpty ? nil : cause)
        let shown = allOrgs ? list : Array(list.prefix(8))
        return PageSection(title: "Nonprofits that rely on volunteers", symbol: "heart.text.square", tone: .blue,
                           caption: "Volunteer counts are each group's own estimate on its latest IRS Form 990.") {
            VStack(alignment: .leading, spacing: 12) {
                CardList {
                    ForEach(shown) { o in
                        orgRow(o)
                        if o.id != shown.last?.id { RowDivider(inset: 64) }
                    }
                }
                if !allOrgs && list.count > shown.count {
                    Button("Show \(list.count - shown.count) more") { allOrgs = true }
                        .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                }
            }
        }
    }

    private func orgRow(_ o: Row) -> some View {
        let nums = [
            o.number("open_needs").flatMap { $0 > 0 ? "\(Int($0)) open need\($0 > 1 ? "s" : "")" : nil },
            o.number("volunteers_reported").map { "\(Format.number($0)) volunteers" },
            o.string("city"),
        ].compactMap { $0 }.joined(separator: " · ")
        return Button { store.open(Volunteer.profileURL(o, "page_url") ?? o.url("website")) } label: {
            HStack(spacing: 12) {
                PersonInitials(name: o.string("name") ?? "", size: 38)
                VStack(alignment: .leading, spacing: 2) {
                    Text(o.string("name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary).multilineTextAlignment(.leading)
                    Text(o.string("cause") ?? "").font(.caption).foregroundStyle(Brand.good)
                    if !nums.isEmpty { Text(nums).font(.caption).foregroundStyle(.secondary) }
                }
                Spacer(minLength: 4)
                Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var howToHelp: some View {
        PageSection(title: "How to help", symbol: "lightbulb", tone: .amber) {
            VStack(alignment: .leading, spacing: 10) {
                Text("**Pick a cause and a schedule.** Ongoing roles like mentoring ask for a few hours a month; one-day events need no long commitment.")
                Text("**Sign up with the organization.** Roles with children or patients often ask for a background check and a short training first.")
                Text("**No need listed?** Most nonprofits here take volunteers year-round. Visit their website and ask what they need.")
            }
            .font(.subheadline)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .card(14)
        }
    }
}
