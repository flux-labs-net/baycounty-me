import SwiftUI
import UniformTypeIdentifiers
import BayCountyKit

/// Send records: a government's staff send the files their accounting system already makes (a check register, a
/// budget-vs-actual report, a list of contracts). We read the file, they check what we found, and it goes public
/// with the usual privacy rules. Same flow as the Send records tab on the web workspace (/staff).
struct RecordsView: View {
    @Environment(StaffStore.self) private var store
    @State private var sending = Launch.screen?.hasPrefix("send-file") == true
    @State private var confirm: StaffRecordFile?
    @State private var error: String?

    var body: some View {
        Group {
            if store.workspaceId == nil {
                PickGovernment(what: "records")
            } else {
                List {
                    if store.can("submit") {
                        Section {
                            Button { sending = true } label: { Label("Send a file", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity) }
                                .buttonStyle(PrimaryButton())
                                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                        }
                    }
                    if let s = store.submissions {
                        Section {
                            ForEach(s.due) { DueRow(d: $0) }
                        } header: { Text("What's due") }
                        if let addr = s.address {
                            Section {
                                LabeledContent("Email files to") { Text(addr).textSelection(.enabled).font(.subheadline.weight(.semibold)) }
                                    .contextMenu { Button("Copy address") { UIPasteboard.general.string = addr } }
                            } footer: { Text("Send from your work email. Emailed files wait here until someone checks them and presses Publish.") }
                        }
                        Section {
                            if s.files.isEmpty { Text("Nothing sent yet.").foregroundStyle(.secondary) }
                            ForEach(s.files) { f in
                                FileRow(f: f)
                                    .swipeActions {
                                        if store.can("submit") && f.canWithdraw {
                                            Button(f.canPublish ? "Discard" : "Withdraw", role: .destructive) { confirm = f }
                                        }
                                        if store.can("submit") && f.canPublish {
                                            Button("Publish") { run { await store.publishRecords(id: f.id) } }.tint(Brand.navyFill)
                                        }
                                    }
                            }
                        } header: { Text("Files sent") } footer: {
                            Text("Swipe a file to publish or withdraw it. Payments to private people are listed without their names.")
                        }
                    } else if store.loading {
                        ProgressView().frame(maxWidth: .infinity)
                    }
                    if let error { Section { ErrorLine(text: error) } }
                }
                .refreshable { await store.refresh() }
            }
        }
        .staffPage()
        .navigationTitle("Send records")
        .toolbar { WorkspaceMenu() }
        .sheet(isPresented: $sending) { SendFileView() }
        .confirmationDialog(confirm?.canPublish == true ? "Discard this file?" : "Take these records off the site?", isPresented: Binding(get: { confirm != nil }, set: { if !$0 { confirm = nil } }), titleVisibility: .visible) {
            if let f = confirm {
                Button(f.canPublish ? "Discard" : "Withdraw", role: .destructive) { run { await store.withdrawRecords(id: f.id) } }
            }
        } message: { Text("The file stays on record. You can send a corrected one any time.") }
    }

    private func run(_ f: @escaping () async -> String?) { Task { error = await f() } }
}

private struct DueRow: View {
    let d: StaffSubmissions.Due
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: d.current ? "checkmark.circle.fill" : "clock")
                .foregroundStyle(d.current ? Brand.good : Brand.amber).font(.title3)
            VStack(alignment: .leading, spacing: 2) {
                Text(d.label).font(.body.weight(.semibold))
                Text(d.current ? (d.kind == "contracts" ? "Sent " + Staff.when(d.have) : "In, through " + Staff.when(d.have)) : "Due: " + d.text)
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 2)
    }
}

private struct FileRow: View {
    let f: StaffRecordFile
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(f.name).font(.body.weight(.semibold)).lineLimit(1).truncationMode(.middle)
                Spacer(minLength: 8)
                Chip(text: f.statusLabel, color: color)
            }
            Text(f.detail).font(.caption).foregroundStyle(.secondary)
            Text([f.via == "email" ? "Emailed" : "Sent", f.sentBy.map { "by " + $0 }, f.sentAt.map(Staff.when)].compactMap { $0 }.joined(separator: " "))
                .font(.caption).foregroundStyle(.secondary)
            if let p = f.problem, f.status == "held" { Text(p).font(.caption).foregroundStyle(Brand.salmon) }
        }
        .padding(.vertical, 3)
    }
    private var color: Color {
        switch f.status { case "published": return Brand.good; case "waiting", "held": return Brand.amber; default: return .secondary }
    }
}

/// Pick the kind, pick the file, check what we read, publish.
struct SendFileView: View {
    @Environment(StaffStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @State private var kind = "contracts"
    @State private var picking = false
    @State private var busy = false
    @State private var fileName: String?
    @State private var preview: StaffRecordPreview?
    @State private var error: String?
    @State private var done: String?

    static let types: [UTType] = [.commaSeparatedText, .plainText, UTType("org.openxmlformats.spreadsheetml.sheet"), UTType("com.microsoft.excel.xls")].compactMap { $0 }

    var body: some View {
        NavigationStack {
            Form {
                if let done {
                    Section { Label(done, systemImage: "checkmark.circle.fill").foregroundStyle(Brand.good) }
                } else if let p = preview {
                    previewSections(p)
                } else {
                    Section {
                        Picker("What is it?", selection: $kind) {
                            ForEach(Staff.recordKinds, id: \.key) { Text($0.label).tag($0.key) }
                        }
                        .pickerStyle(.inline).labelsHidden()
                    } header: { Text("What are you sending?") } footer: { Text(Staff.recordKinds.first { $0.key == kind }?.hint ?? "") }
                    Section {
                        Button { picking = true } label: { Text(busy ? "Reading \(fileName ?? "the file")…" : "Choose a file").frame(maxWidth: .infinity) }
                            .buttonStyle(PrimaryButton()).disabled(busy)
                            .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                    } footer: { Text("Excel or CSV, up to 3 MB. Nothing is published until you check it.") }
                }
                Section { ErrorLine(text: error) }
            }
            .staffPage()
            .navigationTitle("Send a file")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button(done == nil ? "Cancel" : "Done") { dismiss() } } }
            .fileImporter(isPresented: $picking, allowedContentTypes: Self.types) { read($0) }
            .task { if Launch.demo, Launch.screen == "send-file-preview" { await demoPreview() } }
        }
    }

    @ViewBuilder private func previewSections(_ p: StaffRecordPreview) -> some View {
        Section {
            LabeledContent("File", value: fileName ?? "")
            LabeledContent("Kind", value: Staff.recordKindLabel(p.kind))
            if let n = p.rowCount { LabeledContent("Rows to publish", value: n.formatted()) }
            if let t = p.parsedTotal { LabeledContent("Total", value: t.formatted(.currency(code: "USD").precision(.fractionLength(0)))) }
            if let s = p.period?.start, let e = p.period?.end { LabeledContent("Dates", value: "\(Staff.when(s)) to \(Staff.when(e))") }
            if let n = p.alreadyOnSite, n > 0 { LabeledContent("Already on the site", value: "\(n) skipped") }
            if let n = p.skipped, n > 0 { LabeledContent("Rows we skipped", value: n.formatted()) }
            if let n = p.withheld, n > 0 { LabeledContent("Private people (names withheld)", value: n.formatted()) }
        } header: { Text("What we read") } footer: {
            Text(p.problem ?? "Check these match your report. Publishing puts them on BayCounty.me.")
                .foregroundStyle(p.ok ? Color.secondary : Brand.salmon)
        }
        ForEach(p.warnings ?? [], id: \.self) { Text($0).font(.footnote).foregroundStyle(Brand.amber) }
        Section {
            if p.ok {
                Button { publish(p) } label: { Text(busy ? "Publishing…" : "Publish").frame(maxWidth: .infinity) }
                    .buttonStyle(PrimaryButton()).disabled(busy)
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            Button(p.ok ? "Not now (keep it waiting)" : "Choose a different file") { preview = nil; error = nil }
                .frame(maxWidth: .infinity).listRowBackground(Color.clear)
        }
    }

    private func read(_ result: Result<URL, Error>) {
        error = nil
        guard case .success(let url) = result else { if case .failure(let e) = result { error = e.localizedDescription }; return }
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { error = "Couldn't open that file."; return }
        fileName = url.lastPathComponent
        busy = true
        Task {
            switch await store.previewRecords(kind: kind, filename: url.lastPathComponent, content: data) {
            case .success(let p): preview = p
            case .failure(let e): error = e.localizedDescription
            }
            busy = false
        }
    }

    private func publish(_ p: StaffRecordPreview) {
        busy = true
        Task {
            error = await store.publishRecords(id: p.id)
            busy = false
            if error == nil { done = p.rowCount.map { "Published \($0.formatted()) row\($0 == 1 ? "" : "s")." } ?? "Published." }
        }
    }

    private func demoPreview() async {
        fileName = "contracts-oct-2026.xlsx"
        if case .success(let p) = await store.previewRecords(kind: "contracts", filename: "contracts-oct-2026.xlsx", content: Data()) { preview = p }
    }
}
