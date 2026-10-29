import SwiftUI
import BayCountyKit

/// My home (/account): sign in with an emailed code, save a home address, then see what's happening near it —
/// alerts, trash day, meetings, things to do, building and road work, notices, inspections and new businesses.
/// Reads /api/account, the same answers the website's My home page shows.
struct MyHomeView: View {
    @Environment(AppStore.self) private var store
    @State private var account = AccountManager.shared
    @State private var showSettings = false

    var body: some View {
        PageScroll {
            if !account.signedIn {
                SignInCard()
            } else if let me = account.me, let home = me.home {
                header(me, home)
                if let f = account.feed { FeedContent(feed: f) }
                else if account.error == nil { ProgressView().frame(maxWidth: .infinity, minHeight: 160) }
            } else if account.me != nil {
                PageHero(kicker: "My home", title: "Where do you live?",
                         subtitle: "Save your address to see meetings, events, road work, alerts and trash day for your street.",
                         symbol: "house", tone: .blue)
                HomeSearch()
            } else {
                ProgressView().frame(maxWidth: .infinity, minHeight: 160)
            }
            if let e = account.error, account.signedIn {
                Text(e).font(.footnote).foregroundStyle(Brand.salmon)
            }
        }
        .navigationTitle("My home")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if account.signedIn && account.me != nil {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel("Settings")
                }
            }
        }
        .sheet(isPresented: $showSettings) { AccountSettingsView() }
        .task { if account.me == nil { await account.refresh() } }
        .refreshable { await account.refresh() }
        .onAppear { if AccountManager.demo, ProcessInfo.processInfo.arguments.contains("myhome:settings") { showSettings = true } }
    }

    @ViewBuilder private func header(_ me: AccountMe, _ home: AccountMe.Home) -> some View {
        PageHero(kicker: greeting(me.user.firstName), title: home.address, subtitle: home.subtitle.isEmpty ? nil : home.subtitle) {
            ToneIcon(symbol: "house.fill", tone: .blue, size: 44)
        }
        HStack(spacing: 8) {
            if let c = home.city { HomeChip(text: c, symbol: "building.2") }
            if let z = home.zone { HomeChip(text: "Evacuation zone \(z)", symbol: "wind") }
            Spacer(minLength: 0)
        }
    }

    private func greeting(_ name: String?) -> String {
        let h = Calendar.current.component(.hour, from: Date())
        let part = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening"
        return [part, name].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }
}

/// A small rounded label under the home's address.
struct HomeChip: View {
    let text: String
    var symbol: String? = nil
    var body: some View {
        HStack(spacing: 4) {
            if let symbol { Image(systemName: symbol).font(.caption2.weight(.semibold)) }
            Text(text)
        }
        .font(.caption.weight(.semibold))
        .foregroundStyle(Brand.navy)
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(Brand.sunken, in: Capsule())
    }
}

// MARK: Sign in

/// Email, then the 6-digit code from the email. No password.
private struct SignInCard: View {
    @State private var account = AccountManager.shared
    @State private var email = ""
    @State private var code = ""
    @State private var sent = false
    @State private var busy = false
    @FocusState private var focus: Field?
    enum Field { case email, code }

    var body: some View {
        PageHero(kicker: "My home", title: "Your corner of Bay County",
                 subtitle: "Sign in to save your home and see what's happening around it: meetings, events, road work, alerts and your trash day.",
                 symbol: "house", tone: .blue)
        VStack(alignment: .leading, spacing: 12) {
            if !sent {
                Text("Sign in or create an account").font(.headline)
                TextField("you@example.com", text: $email)
                    .textContentType(.emailAddress).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                    .focused($focus, equals: .email).submitLabel(.send).onSubmit { Task { await send() } }
                    .padding(12).background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
                Button { Task { await send() } } label: { primary(busy ? "Sending…" : "Email me a code") }
                    .disabled(busy || !email.contains("@"))
                Text("We'll email you a 6-digit code. No password to remember.").font(.footnote).foregroundStyle(.secondary)
            } else {
                Text("Check your email").font(.headline)
                Text("We sent a 6-digit code to \(email). It works for 15 minutes.").font(.subheadline).foregroundStyle(.secondary)
                TextField("123456", text: $code)
                    .textContentType(.oneTimeCode).keyboardType(.numberPad).font(.title2.monospacedDigit())
                    .focused($focus, equals: .code)
                    .padding(12).background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
                    .onChange(of: code) { _, v in
                        code = String(v.filter(\.isNumber).prefix(6))
                        if code.count == 6 { Task { await verify() } }
                    }
                Button { Task { await verify() } } label: { primary(busy ? "Checking…" : "Sign in") }
                    .disabled(busy || code.count != 6)
                Button("Use a different email") { sent = false; code = ""; account.error = nil }
                    .font(.subheadline)
            }
            if let e = account.error { Text(e).font(.footnote).foregroundStyle(Brand.salmon) }
        }
        .padding(16)
        .card(16)
        PageSection(title: "What you get", symbol: "sparkles", tone: .teal) {
            CardList {
                RowLabel(title: "Near my home", detail: "Meetings, events, road work and notices within the distance you pick", symbol: "mappin.and.ellipse")
                RowDivider(inset: 50)
                RowLabel(title: "Your trash day and evacuation zone", detail: "Pickup days and the zone for your street", symbol: "trash")
                RowDivider(inset: 50)
                RowLabel(title: "A Monday email", detail: "Your week near home, if you want it", symbol: "envelope")
                RowDivider(inset: 50)
                RowLabel(title: "Alerts for your street", detail: "Evacuation orders for your zone and boil-water notices for your city", symbol: "bell")
            }
        }
        Text("Your email and home address are kept private and never shown on the site. Delete your account any time in Settings.")
            .font(.footnote).foregroundStyle(.secondary)
    }

    private func primary(_ t: String) -> some View {
        Text(t).font(.body.weight(.semibold)).foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 12))
    }

    private func send() async {
        busy = true; defer { busy = false }
        if await account.start(email: email.trimmingCharacters(in: .whitespaces)) { sent = true; focus = .code }
    }

    private func verify() async {
        guard !busy else { return }
        busy = true; defer { busy = false }
        if !(await account.verify(email: email.trimmingCharacters(in: .whitespaces), code: code)) { code = "" }
    }
}

// MARK: Home search

/// Finds a Bay County address on the county's map server and saves it as the account's home.
struct HomeSearch: View {
    @Environment(AppStore.self) private var store
    @State private var account = AccountManager.shared
    @State private var query = ""
    @State private var results: [AddressMatch] = []
    @State private var message: String?
    @State private var saving = false
    var onSaved: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            TextField("e.g. 825 Ohio Ave", text: $query)
                .textContentType(.fullStreetAddress).autocorrectionDisabled()
                .padding(12).background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
            if let message { Text(message).font(.footnote).foregroundStyle(.secondary) }
            if !results.isEmpty {
                CardList {
                    ForEach(Array(results.enumerated()), id: \.element.id) { i, m in
                        Button { Task { await save(m) } } label: { RowLabel(title: m.display, detail: m.subtitle.isEmpty ? nil : m.subtitle, symbol: "house") }
                            .buttonStyle(.plain).disabled(saving)
                        if i < results.count - 1 { RowDivider(inset: 50) }
                    }
                }
            }
            if let h = store.home, query.isEmpty, results.isEmpty {
                Button { Task { await save(h) } } label: { RowLabel(title: "Use \(h.display)", detail: "The address saved on this phone", symbol: "location") }
                    .buttonStyle(.plain).padding(.vertical, 4)
            }
        }
        .task(id: query) { await search() }
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

    private func save(_ m: AddressMatch) async {
        saving = true; defer { saving = false }
        await account.saveHome(m)
        if account.me?.home != nil { query = ""; results = []; onSaved?() }
    }
}

// MARK: Feed

/// Today tiles, then one card per section, then the home's governments.
private struct FeedContent: View {
    @Environment(AppStore.self) private var store
    let feed: NearbyFeed

    var body: some View {
        StatGrid {
            KPICard(title: "Alerts", value: feed.todayCard.alerts == 0 ? "None" : "\(feed.todayCard.alerts)",
                    caption: feed.todayCard.alerts == 0 ? "Nothing for your street right now" : "For your street", symbol: "bell", tone: feed.todayCard.alerts == 0 ? .teal : .salmon)
            KPICard(title: "Pickup", value: pickupValue, caption: pickupCaption, symbol: "trash", tone: .teal)
            KPICard(title: "Evacuation zone", value: feed.zone ?? "None", caption: feed.zone == nil ? "Not in a zone" : "Leave when zone \(feed.zone!) is called", symbol: "wind", tone: .amber)
            if let b = feed.todayCard.beach {
                KPICard(title: "Beach flag", value: b.flag.capitalized, caption: b.ripCurrentRisk.map { "Rip current risk: \($0)" }, symbol: "flag", tone: .blue)
            } else {
                KPICard(title: "Your government", value: feed.city ?? "Bay County", caption: feed.city == nil ? "Unincorporated Bay County" : feed.localGovernment, symbol: "building.columns", tone: .blue)
            }
        }
        ForEach(feed.sections) { s in
            if !s.items.isEmpty || s.id == "alerts" {
                PageSection(title: s.title, symbol: symbol(s.id), tone: tone(s.id)) {
                    if s.items.isEmpty {
                        Text(s.empty).font(.subheadline).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading).padding(14).card(16)
                    } else {
                        CardList {
                            ForEach(Array(s.items.prefix(6).enumerated()), id: \.element.id) { i, item in
                                FeedRow(item: item)
                                if i < min(s.items.count, 6) - 1 { RowDivider(inset: 70) }
                            }
                        }
                    }
                }
            }
        }
        PageSection(title: "Your governments", symbol: "building.columns", tone: .blue) {
            CardList {
                ForEach(Array(feed.governments.enumerated()), id: \.element) { i, g in
                    RouteRow(route: .government(g.govId), title: g.name, symbol: "building.columns")
                    if i < feed.governments.count - 1 { RowDivider(inset: 50) }
                }
                RowDivider(inset: 50)
                RouteRow(route: .myAddress, title: "Full address report", detail: "Taxes, flood zone, schools and who represents you", symbol: "doc.text.magnifyingglass")
                // Same account as the realtor console: agents get a way in from here, like the site's My home.
                if AccountManager.shared.me?.realtor == "active" {
                    RowDivider(inset: 50)
                    WebRow(title: "Realtor console", detail: "Branded address reports for your clients", symbol: "briefcase", url: URL(string: "https://baycounty.me/realtor"))
                }
            }
        }
        if let n = feed.note { Text(n).font(.footnote).foregroundStyle(.secondary) }
    }

    private var pickupValue: String {
        guard let t = feed.todayCard.trash?.first else { return "—" }
        return t.days
    }
    private var pickupCaption: String {
        guard let t = feed.todayCard.trash, !t.isEmpty else { return "No pickup days found" }
        return t.dropFirst().map { "\($0.service): \($0.days)" }.first ?? t[0].service
    }

    private func symbol(_ id: String) -> String {
        ["alerts": "exclamationmark.triangle", "meetings": "person.3", "events": "calendar", "projects": "hammer",
         "notices": "doc.plaintext", "food": "fork.knife", "business": "storefront"][id] ?? "circle"
    }
    private func tone(_ id: String) -> Tone {
        ["alerts": .salmon, "meetings": .blue, "events": .teal, "projects": .amber, "notices": .blue, "food": .teal, "business": .amber][id] ?? .blue
    }
}

/// One item: a date or distance tile, its title and a two-line detail, and a tag.
private struct FeedRow: View {
    @Environment(AppStore.self) private var store
    let item: NearbyFeed.Item

    var body: some View {
        Button { if let u = item.link { store.open(u) } } label: {
            HStack(alignment: .top, spacing: 12) {
                tile
                VStack(alignment: .leading, spacing: 3) {
                    if let tag = item.tag {
                        Text(tag.uppercased()).font(.caption2.weight(.bold)).foregroundStyle(item.level == "closed" || item.kind == "evacuation" ? Brand.salmon : Brand.navy)
                    }
                    Text(item.title).font(.subheadline.weight(.semibold)).foregroundStyle(.primary).lineLimit(2).multilineTextAlignment(.leading)
                    if !item.leadsWithDistance, item.allDay != true, let t = NearbyFeed.when(item.date)?.time {
                        Text(t).font(.caption.weight(.semibold)).foregroundStyle(Brand.navy)
                    }
                    if let d = item.detail, !d.isEmpty {
                        Text(d).font(.footnote).foregroundStyle(.secondary).lineLimit(2).multilineTextAlignment(.leading)
                    }
                }
                Spacer(minLength: 0)
                if item.link != nil { Image(systemName: "chevron.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary).padding(.top, 4) }
            }
            .padding(.horizontal, 14).padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(item.link == nil)
    }

    @ViewBuilder private var tile: some View {
        VStack(spacing: 0) {
            if item.leadsWithDistance, let mi = item.miles {
                Text(mi < 0.1 ? "<0.1" : String(format: "%.1f", mi)).font(.headline.monospacedDigit())
                Text("MI").font(.caption2.weight(.bold)).foregroundStyle(.secondary)
            } else if let w = NearbyFeed.when(item.date) {
                Text(w.month).font(.caption2.weight(.bold)).foregroundStyle(Brand.salmon)
                Text(w.day).font(.headline.monospacedDigit())
            } else {
                Image(systemName: "mappin").font(.headline).foregroundStyle(Brand.navy)
            }
        }
        .frame(width: 44, height: 46)
        .background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
    }
}

// MARK: Settings

/// Name, home, distance, emails, topics and phone alerts; sign out and delete the account.
struct AccountSettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var account = AccountManager.shared
    @State private var prefs: AccountMe.Prefs?
    @State private var name = ""
    @State private var changingHome = false
    @State private var confirmDelete = false
    @State private var push = PushManager.shared

    var body: some View {
        NavigationStack {
            Form {
                if let me = account.me {
                    Section("You") {
                        LabeledContent("Email", value: me.user.email)
                        TextField("First name", text: $name).textContentType(.givenName)
                    }
                    Section {
                        if let h = me.home, !changingHome {
                            LabeledContent(h.address, value: h.subtitle)
                            Button("Change address") { changingHome = true }
                            Button("Remove home", role: .destructive) { Task { await account.removeHome() } }
                        } else {
                            HomeSearch { changingHome = false }
                        }
                    } header: { Text("Home") } footer: { Text("Kept private. Used only to pick what's near you.") }
                }
                if let p = Binding($prefs), let c = account.me?.choices {
                    Section {
                        Toggle("Alerts on this phone", isOn: Binding(get: { push.enabled }, set: { on in Task { if on { await push.enable() } else { await push.disable() } } }))
                            .fontWeight(.semibold)
                        if push.enabled {
                            ForEach(AccountMe.pushOrder.filter { c.pushTopics[$0] != nil }, id: \.self) { k in
                                Toggle(c.pushTopics[k]!, isOn: member(p.pushTopics, k))
                            }
                        }
                    } header: { Text("Phone alerts") } footer: {
                        Text(push.status ?? (push.enabled
                            ? "For your home and the distance below. These follow your account on every phone you're signed in on."
                            : "Evacuation orders, weather warnings, boil-water notices and agenda items near your home."))
                    }
                    Section("Near my home") {
                        Picker("Distance", selection: p.radiusMi) {
                            ForEach(AccountMe.radii, id: \.self) { Text(AccountMe.radiusLabel($0)).tag($0) }
                        }
                        ForEach(AccountMe.topicOrder.filter { c.topics[$0] != nil }, id: \.self) { k in
                            Toggle(c.topics[k]!, isOn: member(p.topics, k))
                        }
                    }
                    Section {
                        Toggle("Monday email: your week near home", isOn: p.weeklyEmail)
                        ForEach(AccountMe.alertEmailOrder.filter { c.alertEmail[$0] != nil }, id: \.self) { k in
                            Toggle(c.alertEmail[k]!, isOn: member(p.alertEmail, k))
                        }
                    } header: { Text("Email") } footer: { Text("Emergency emails go out only when a notice reaches your home.") }
                }
                Section {
                    Button("Sign out") { Task { await account.signOut(); dismiss() } }
                    Button("Delete account", role: .destructive) { confirmDelete = true }
                } footer: { Text("Deleting removes your email, home and choices for good.") }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Save") { Task { await save() } }.fontWeight(.semibold) }
            }
            .confirmationDialog("Delete your account?", isPresented: $confirmDelete, titleVisibility: .visible) {
                Button("Delete account", role: .destructive) { Task { await account.deleteAccount(); dismiss() } }
            } message: { Text("Your email, home and choices are removed. This can't be undone.") }
            .onAppear { prefs = account.me?.prefs; name = account.me?.user.firstName ?? "" }
        }
    }

    private func member(_ list: Binding<[String]>, _ k: String) -> Binding<Bool> {
        Binding(get: { list.wrappedValue.contains(k) },
                set: { on in if on { if !list.wrappedValue.contains(k) { list.wrappedValue.append(k) } } else { list.wrappedValue.removeAll { $0 == k } } })
    }

    private func save() async {
        if name != (account.me?.user.firstName ?? "") { await account.save(firstName: name) }
        if let p = prefs, p != account.me?.prefs { await account.save(prefs: p) }
        if account.error == nil { dismiss() }
    }
}
