import SwiftUI
import BayCountyKit

/// Email, then the 6-digit code. Only workspace members (and the site owner) get a code; the answer is the same
/// either way, so the form can't be used to find out who has access.
struct SignInView: View {
    @Environment(StaffStore.self) private var store
    @State private var email = ""
    @State private var code = ""
    @State private var sent = false
    @State private var busy = false
    @FocusState private var focus: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Image("AppMark").resizable().scaledToFit().frame(width: 56, height: 56)
                    .clipShape(RoundedRectangle(cornerRadius: 13, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 13, style: .continuous).strokeBorder(Brand.hairline))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 6) {
                    Text("BayCounty.me Staff").font(.largeTitle.weight(.bold))
                    Text("For city and county staff. Send alerts, post notices and flag data for your government.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                VStack(alignment: .leading, spacing: 12) {
                    if !sent {
                        Eyebrow(text: "Work email")
                        TextField("you@city.gov", text: $email)
                            .textContentType(.emailAddress).keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                            .focused($focus).submitLabel(.send).onSubmit(send)
                            .padding(14).background(Brand.sunken, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                        Button(action: send) { Text(busy ? "Sending…" : "Email me a code").frame(maxWidth: .infinity) }
                            .buttonStyle(PrimaryButton()).disabled(busy || !email.contains("@"))
                    } else {
                        Text("If **\(email)** has access, a 6-digit code is on its way. It expires in 10 minutes.").font(.subheadline)
                        TextField("123456", text: $code)
                            .textContentType(.oneTimeCode).keyboardType(.numberPad).focused($focus)
                            .font(.title2.monospacedDigit()).padding(14)
                            .background(Brand.sunken, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                            .toolbar { ToolbarItemGroup(placement: .keyboard) { Spacer(); Button("Done") { focus = false } } }
                        Button(action: verify) { Text(busy ? "Checking…" : "Sign in").frame(maxWidth: .infinity) }
                            .buttonStyle(PrimaryButton()).disabled(busy || code.filter(\.isNumber).count != 6)
                        Button("Use a different email") { sent = false; code = ""; store.error = nil }.font(.subheadline)
                    }
                    ErrorLine(text: store.error)
                }
                .padding(16).card()
                Text("Staff never change numbers that came from public records. If something is wrong, flag it and we check it against the source.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .padding(20)
            .padding(.top, 30)
        }
        .safeAreaInset(edge: .bottom) { FluxFooter() }
        .background(Brand.canvas)
    }

    private func send() {
        guard !busy else { return }
        busy = true
        Task { sent = await store.login(email: email.trimmingCharacters(in: .whitespaces)); busy = false; if sent { focus = true } }
    }
    private func verify() {
        busy = true
        Task { _ = await store.verify(email: email.trimmingCharacters(in: .whitespaces), code: code.filter(\.isNumber)); busy = false }
    }
}

/// The site owner's home: every government, what needs attention first, and the latest activity everywhere.
struct OverviewView: View {
    @Environment(StaffStore.self) private var store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let o = store.overview {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        StatTile(value: o.totals.waitingAlerts, label: "Alerts waiting for a second person", symbol: "person.2", alert: o.totals.waitingAlerts > 0)
                        StatTile(value: o.totals.openFlags, label: "Data flags to answer", symbol: "flag", alert: o.totals.openFlags > 0)
                        StatTile(value: o.totals.liveAlerts, label: "Live alerts", symbol: "dot.radiowaves.left.and.right", tint: Brand.good)
                        StatTile(value: o.totals.members, label: "Staff in \(o.totals.workspaces) governments", symbol: "person.crop.circle")
                    }
                    VStack(alignment: .leading, spacing: 10) {
                        Eyebrow(text: "Governments")
                        VStack(spacing: 0) {
                            ForEach(Array(sorted(o.workspaces).enumerated()), id: \.element.id) { i, w in
                                if i > 0 { Divider().padding(.leading, 14) }
                                Button { Task { await store.open(w.id) } } label: { GovRow(w: w) }
                            }
                        }
                        .card()
                    }
                    ActivityList(title: "Latest everywhere", items: o.activity, showGov: true)
                } else if store.loading {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
                ErrorLine(text: store.error)
            }
            .padding(16)
        }
        .background(Brand.canvas)
        .navigationTitle("All governments")
        .toolbar { WorkspaceMenu() }
        .refreshable { await store.refresh() }
    }

    /// Governments that need something first, then the rest in their usual order.
    private func sorted(_ rows: [StaffOverview.Row]) -> [StaffOverview.Row] {
        rows.filter(\.needsAttention) + rows.filter { !$0.needsAttention }
    }
}

private struct GovRow: View {
    let w: StaffOverview.Row
    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(w.name).font(.body.weight(.semibold)).foregroundStyle(.primary)
                Text(detail).font(.footnote).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer(minLength: 8)
            if w.waitingAlerts > 0 { Chip(text: "\(w.waitingAlerts) waiting", color: Brand.amber) }
            else if w.openFlags > 0 { Chip(text: "\(w.openFlags) flag\(w.openFlags == 1 ? "" : "s")", color: Brand.amber) }
            else if w.liveAlerts > 0 { Chip(text: "Live alert", color: Brand.salmon) }
            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14).padding(.vertical, 12)
        .frame(minHeight: 56)
        .contentShape(Rectangle())
    }
    private var detail: String {
        let staff = w.members == 0 ? "No staff yet" : "\(w.members) staff"
        guard let last = w.lastActivity else { return staff }
        return staff + " · active " + Staff.when(last)
    }
}

/// One government's home: what's live, what's waiting, and who did what.
struct WorkspaceHomeView: View {
    @Environment(StaffStore.self) private var store
    @State private var sending = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let h = store.home {
                    if store.can("alert_sender") {
                        Button { sending = true } label: {
                            Label("Send an alert", systemImage: "exclamationmark.triangle.fill").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(PrimaryButton(color: Brand.salmonFill))
                    }
                    if let s = store.submissions, store.can("submit") {
                        RecordsDueCard(s: s)
                    }
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        StatTile(value: h.counts.liveAlerts, label: "Live alerts", symbol: "dot.radiowaves.left.and.right", alert: h.counts.liveAlerts > 0)
                        StatTile(value: h.counts.waitingAlerts, label: "Waiting for a second person", symbol: "person.2", alert: h.counts.waitingAlerts > 0)
                        StatTile(value: h.counts.notices, label: "Notices you posted", symbol: "doc.text")
                        StatTile(value: h.counts.openFlags, label: "Open data flags", symbol: "flag", tint: Brand.amber)
                    }
                    ActivityList(title: "Latest", items: h.activity, showGov: false)
                    Text("You're signed in as \(store.role == "alert_sender" ? "an" : "a") \(Staff.roleLabel[store.role]?.lowercased() ?? store.role). Numbers from public records can't be changed here, only flagged.")
                        .font(.footnote).foregroundStyle(.secondary)
                } else if store.loading {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
                ErrorLine(text: store.error)
            }
            .padding(16)
        }
        .background(Brand.canvas)
        .navigationTitle(store.workspace?.name ?? "Home")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { WorkspaceMenu() }
        .refreshable { await store.refresh() }
        .sheet(isPresented: $sending) { SendAlertView() }
    }
}

/// What records are due from this government, with a way in to send them.
struct RecordsDueCard: View {
    let s: StaffSubmissions
    var body: some View {
        let late = s.due.filter { !$0.current }
        let waiting = s.files.filter(\.canPublish).count
        NavigationLink { RecordsView() } label: {
            HStack(spacing: 12) {
                Image(systemName: late.isEmpty && waiting == 0 ? "checkmark.circle.fill" : "tray.and.arrow.up")
                    .font(.title3).foregroundStyle(late.isEmpty && waiting == 0 ? Brand.good : Brand.amber)
                VStack(alignment: .leading, spacing: 3) {
                    Text(waiting > 0 ? "\(waiting) file\(waiting == 1 ? "" : "s") waiting to publish" : late.isEmpty ? "Records are up to date" : "Records due: \(late.count)")
                        .font(.body.weight(.semibold)).foregroundStyle(.primary)
                    Text(late.isEmpty ? "Thanks for sending them." : late.map(\.text).joined(separator: " · "))
                        .font(.footnote).foregroundStyle(.secondary).lineLimit(2).multilineTextAlignment(.leading)
                }
                Spacer(minLength: 8)
                Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
            }
            .padding(14).frame(maxWidth: .infinity, alignment: .leading).card()
        }
    }
}

struct ActivityList: View {
    let title: String
    let items: [StaffActivity]
    let showGov: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Eyebrow(text: title)
            if items.isEmpty {
                Text("Nothing yet.").font(.subheadline).foregroundStyle(.secondary).padding(14).frame(maxWidth: .infinity, alignment: .leading).card()
            } else {
                VStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(items.enumerated()), id: \.element.id) { i, a in
                        if i > 0 { Divider().padding(.leading, 14) }
                        VStack(alignment: .leading, spacing: 3) {
                            Text(a.sentence).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                            Text([showGov ? a.govName : nil, Staff.when(a.at)].compactMap { $0 }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 14).padding(.vertical, 10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .card()
            }
        }
    }
}

/// Account, government, how the app is locked, and sign out.
struct MoreView: View {
    @Environment(StaffStore.self) private var store
    @State private var records = ["records", "send-file", "send-file-preview"].contains(Launch.screen ?? "")
    var body: some View {
        List {
            if store.isOwner || store.can("submit") {
                Section {
                    Button { records = true } label: {
                        HStack {
                            Label("Send records", systemImage: "square.and.arrow.up")
                            Spacer()
                            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                    }
                    .foregroundStyle(.primary)
                } footer: { Text("Send your check register, budget report or contract list straight from your accounting system.") }
            }
            Section("Signed in") {
                LabeledContent("Email", value: store.me?.email ?? "")
                LabeledContent("Access", value: store.isOwner ? "Site owner (every government)" : (store.workspace.map { "\($0.roleLabel), \($0.name)" } ?? ""))
            }
            if let me = store.me, !me.admin, me.workspaces.count > 1 {
                Section("Your governments") { ForEach(me.workspaces) { w in LabeledContent(w.name, value: w.roleLabel) } }
            }
            Section {
                Label("Face ID or your passcode after 5 minutes away", systemImage: "faceid")
                Label("Countywide alerts need a second person to confirm", systemImage: "person.2")
                Label("Every action is logged for your workspace owner", systemImage: "list.bullet.rectangle")
            } header: { Text("Safety") }
            Section {
                Link(destination: URL(string: "https://baycounty.me/staff")!) { Label("Open the full workspace on the web", systemImage: "safari") }
                Link(destination: URL(string: "mailto:hello@baycounty.me")!) { Label("Get help", systemImage: "questionmark.circle") }
            }
            Section {
                Button(role: .destructive) { Task { await store.signOut() } } label: { Text("Sign out") }
            } footer: {
                Text("BayCounty.me Staff \(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "") (\(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "")). Made by Flux Labs.")
            }
        }
        .staffPage()
        .navigationTitle("More")
        .toolbar { WorkspaceMenu() }
        .navigationDestination(isPresented: $records) { RecordsView() }
    }
}
