import SwiftUI
import BayCountyKit

/// Notices this government posted (editable), and the ones read from its notice website (read-only).
struct NoticesView: View {
    @Environment(StaffStore.self) private var store
    @State private var editing: StaffPost?
    @State private var adding = Launch.screen == "notice"

    var body: some View {
        Group {
            if store.workspaceId == nil {
                PickGovernment(what: "notices")
            } else {
                List {
                    if store.can("publisher") {
                        Section {
                            Button { adding = true } label: { Label("Post a notice", systemImage: "plus").frame(maxWidth: .infinity) }
                                .buttonStyle(PrimaryButton())
                                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                        }
                    }
                    Section {
                        if (store.notices?.posts ?? []).isEmpty { Text("Nothing posted from here yet.").foregroundStyle(.secondary) }
                        ForEach(store.notices?.posts ?? []) { p in
                            Button { if store.can("publisher") { editing = p } } label: { NoticeRow(p: p) }
                                .foregroundStyle(.primary)
                        }
                    } header: { Text("Posted here") } footer: { Text("These show on BayCounty.me as soon as you post them.") }
                    if let read = store.notices?.fromRecords, !read.isEmpty {
                        Section {
                            ForEach(read) { NoticeRow(p: $0) }
                        } header: { Text("From your notice website") } footer: { Text("Read from public records, so they can't be changed here. Flag one if it's wrong.") }
                    }
                }
                .refreshable { await store.refresh() }
            }
        }
        .staffPage()
        .navigationTitle("Notices")
        .toolbar { WorkspaceMenu() }
        .sheet(isPresented: $adding) { NoticeEditor(post: nil) }
        .sheet(item: $editing) { NoticeEditor(post: $0) }
    }
}

private struct NoticeRow: View {
    let p: StaffPost
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(p.title).font(.body.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
            Text([p.kindLabel, p.eventDate.map { "on " + Staff.when($0) }, p.published.map { "posted " + Staff.when($0) }].compactMap { $0 }.joined(separator: " · "))
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(.vertical, 3)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
    }
}

/// Post or change a notice. Maps are drawn on the web workspace for now.
struct NoticeEditor: View {
    @Environment(StaffStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let post: StaffPost?
    @State private var kind = "meeting"
    @State private var title = ""
    @State private var text = ""
    @State private var hasDate = false
    @State private var date = Date()
    @State private var busy = false
    @State private var sure = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Kind", selection: $kind) { ForEach(Staff.noticeOrder, id: \.self) { Text(store.noticeKinds[$0] ?? $0).tag($0) } }
                    TextField("Title", text: $title, axis: .vertical).lineLimit(1...3)
                    Toggle("Has a date (meeting, hearing, deadline)", isOn: $hasDate)
                    if hasDate { DatePicker("Date", selection: $date, displayedComponents: .date) }
                }
                Section {
                    TextField("Paste the notice text", text: $text, axis: .vertical).lineLimit(6...20)
                } header: { Text("Notice text") } footer: {
                    Text(post?.geometry != nil ? "This notice has a map. To change the map, use the workspace on the web." : "To add a map (a pin, a street or an area), use the workspace on the web.")
                }
                Section {
                    Button { save() } label: { Text(busy ? "Saving…" : post == nil ? "Post notice" : "Save changes").frame(maxWidth: .infinity) }
                        .buttonStyle(PrimaryButton()).disabled(busy || title.trimmingCharacters(in: .whitespaces).isEmpty || text.trimmingCharacters(in: .whitespaces).isEmpty)
                        .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                    if let post {
                        Button(role: .destructive) {
                            if sure { run { await store.withdraw(post) } } else { sure = true }
                        } label: { Text(sure ? "Withdraw: are you sure?" : "Withdraw this notice").frame(maxWidth: .infinity) }
                        .listRowBackground(Color.clear)
                    }
                } footer: { ErrorLine(text: error) }
            }
            .staffPage()
            .navigationTitle(post == nil ? "Post a notice" : "Edit notice")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            .onAppear(perform: fill)
        }
    }

    private func fill() {
        if let p = post {
            kind = p.kind ?? "other"; title = p.title; text = p.text ?? ""
            if let d = p.eventDate, let x = ISO8601DateFormatter.dayOnly.date(from: d) { hasDate = true; date = x }
        } else if Launch.demo, Launch.screen == "notice" {
            kind = "hearing"; title = "Public hearing on the 2027 budget"; hasDate = true
            text = "The City Commission will hold a public hearing on the proposed 2027 budget at City Hall, 825 Ohio Ave, at 5:30 pm."
        }
    }

    private func save() {
        let d: String? = hasDate ? ISO8601DateFormatter.dayOnly.string(from: date) : nil
        run { await store.saveNotice(id: post?.id, kind: kind, title: title, text: text, eventDate: d) }
    }

    private func run(_ f: @escaping () async -> String?) {
        busy = true
        Task { error = await f(); busy = false; if error == nil { dismiss() } }
    }
}

extension ISO8601DateFormatter {
    /// yyyy-MM-dd in Bay County time, for notice dates.
    static let dayOnly: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter(); f.formatOptions = [.withFullDate]; f.timeZone = TimeZone(identifier: "America/Chicago"); return f
    }()
}

/// Data flags: staff see the ones they sent and our answers; the site owner sees every government's and answers them.
struct FlagsView: View {
    @Environment(StaffStore.self) private var store
    @State private var filter = "open"
    @State private var openFirst = Launch.demo && Launch.screen == "flag"

    private var shown: [StaffFlag] { filter == "all" ? store.flags : store.flags.filter { $0.status == filter } }
    private var answering: Bool { store.isOwner && store.workspaceId == nil }

    var body: some View {
        List {
            Section {
                Picker("Show", selection: $filter) {
                    Text("Open").tag("open"); Text("Fixed").tag("fixed"); Text("All").tag("all")
                }
                .pickerStyle(.segmented)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            Section {
                if shown.isEmpty { Text(filter == "open" ? "No open flags." : "No flags.").foregroundStyle(.secondary) }
                ForEach(shown) { f in NavigationLink(value: f) { FlagRow(f: f, showGov: answering) } }
            } footer: {
                Text(answering ? "Flags from every government. Check each one against its source, then answer." :
                        "Numbers from public records can't be changed here. Flag what's wrong on the web workspace's Records tab; we check it against the source and answer here.")
            }
        }
        .navigationDestination(for: StaffFlag.self) { FlagDetailView(flag: $0, answering: answering) }
        .navigationDestination(isPresented: $openFirst) { if let f = shown.first { FlagDetailView(flag: f, answering: answering) } }
        .staffPage()
        .navigationTitle(answering ? "Flags to answer" : "Data flags")
        .toolbar { WorkspaceMenu() }
        .refreshable { await store.refresh() }
    }
}

private struct FlagRow: View {
    let f: StaffFlag
    let showGov: Bool
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Chip(text: f.statusLabel, color: flagColor(f))
                if showGov, let g = f.govName { Text(g).font(.caption).foregroundStyle(.secondary) }
            }
            Text(f.subject).font(.body.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
            if let s = f.shownValue, let c = f.correctValue {
                Text("Shows \(s), should be \(c)").font(.subheadline).foregroundStyle(.secondary)
            } else if let n = f.note {
                Text(n).font(.subheadline).foregroundStyle(.secondary).lineLimit(2)
            }
        }
        .padding(.vertical, 3)
    }
}

struct FlagDetailView: View {
    @Environment(StaffStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let flag: StaffFlag
    let answering: Bool
    @State private var reply = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Chip(text: flag.statusLabel, color: flagColor(flag))
                    Text(flag.subject).font(.title3.weight(.bold))
                }
                .padding(.vertical, 4)
                if let g = flag.govName { LabeledContent("Government", value: g) }
                LabeledContent("From", value: flag.email)
                LabeledContent("Sent", value: Staff.when(flag.createdAt))
                if let s = flag.shownValue { LabeledContent("Site shows", value: s) }
                if let c = flag.correctValue { LabeledContent("Should be", value: c) }
                if let e = flag.evidenceUrl, let u = URL(string: e) { Link(destination: u) { Label("Where it comes from", systemImage: "link") } }
                if let n = flag.note { Text(n).font(.subheadline) }
            }
            if let r = flag.reply {
                Section("Our answer") { Text(r) }
            }
            if answering && flag.status == "open" {
                Section {
                    TextField("Reply to the staff member (optional)", text: $reply, axis: .vertical).lineLimit(2...6)
                    Button { answer("fixed") } label: { Text("Fixed on the site").frame(maxWidth: .infinity) }
                        .buttonStyle(PrimaryButton(color: Brand.good)).disabled(busy)
                        .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                    Button { answer("not_changed") } label: { Text("Checked, not changed").frame(maxWidth: .infinity) }
                        .disabled(busy).listRowBackground(Color.clear)
                } header: { Text("Answer") } footer: {
                    Text("Check the value against the source first. A fix to record data is made in the data pipeline, not here.")
                    ErrorLine(text: error)
                }
            }
        }
        .staffPage()
        .navigationTitle("Flag")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func answer(_ status: String) {
        busy = true
        Task { error = await store.answer(flag, status: status, reply: reply); busy = false; if error == nil { dismiss() } }
    }
}
