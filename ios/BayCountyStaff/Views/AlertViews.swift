import SwiftUI
import MapKit
import BayCountyKit

/// This government's alerts: live first, waiting ones a second person can confirm, then past ones.
struct AlertsView: View {
    @Environment(StaffStore.self) private var store
    @State private var sending = Launch.screen == "send"

    var body: some View {
        Group {
            if store.workspaceId == nil {
                PickGovernment(what: "alerts")
            } else {
                List {
                    if store.can("alert_sender") {
                        Section {
                            Button { sending = true } label: { Label("Send an alert", systemImage: "exclamationmark.triangle.fill").frame(maxWidth: .infinity) }
                                .buttonStyle(PrimaryButton(color: Brand.salmonFill))
                                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                        }
                    }
                    let now = store.alerts.filter { $0.isLive || $0.isWaiting }
                    let past = store.alerts.filter { !$0.isLive && !$0.isWaiting }
                    Section("Now") {
                        if now.isEmpty { Text("No live alerts.").foregroundStyle(.secondary) }
                        ForEach(now) { a in NavigationLink(value: a) { AlertRow(a: a) } }
                    }
                    if !past.isEmpty {
                        Section("Past") { ForEach(past) { a in NavigationLink(value: a) { AlertRow(a: a) } } }
                    }
                }
                .navigationDestination(for: StaffAlert.self) { AlertDetailView(alert: $0) }
                .refreshable { await store.refresh() }
            }
        }
        .staffPage()
        .navigationTitle("Alerts")
        .toolbar { WorkspaceMenu() }
        .sheet(isPresented: $sending) { SendAlertView() }
    }
}

private struct AlertRow: View {
    @Environment(StaffStore.self) private var store
    let a: StaffAlert
    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Chip(text: a.statusLabel, color: alertColor(a))
                Text(store.alertKinds[a.kind].map { $0.components(separatedBy: " (").first ?? $0 } ?? a.kind).font(.caption).foregroundStyle(.secondary)
                if a.countywide { Text("· Countywide").font(.caption).foregroundStyle(.secondary) }
            }
            Text(a.title).font(.body.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
            Text(a.isLive ? "Sent \(Staff.when(a.sentAt)) · ends \(Staff.when(a.endsAt))" : "By \(a.createdBy) · \(Staff.when(a.createdAt))")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct AlertDetailView: View {
    @Environment(StaffStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    let alert: StaffAlert
    @State private var busy = false
    @State private var sure = false
    @State private var error: String?

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Chip(text: alert.statusLabel, color: alertColor(alert))
                    Text(alert.title).font(.title3.weight(.bold))
                    Text(alert.message).font(.body)
                    if let i = alert.instruction, !i.isEmpty {
                        Text(i).font(.body.weight(.semibold)).foregroundStyle(Brand.navy)
                    }
                }
                .padding(.vertical, 6)
            }
            if let map = AlertArea.parse(alert.geometry) {
                Section("Where it applies") { AlertMapView(area: map).listRowInsets(EdgeInsets()) }
            }
            Section("Details") {
                LabeledContent("Kind", value: store.alertKinds[alert.kind] ?? alert.kind)
                LabeledContent("Reaches", value: alert.countywide ? "All of Bay County" : (store.workspace?.name ?? ""))
                LabeledContent("Severity", value: Staff.severities.first { $0.key == alert.severity }?.label ?? "Severe")
                LabeledContent("Written by", value: alert.createdBy)
                if let c = alert.confirmedBy { LabeledContent("Confirmed by", value: c) }
                if let s = alert.sentAt { LabeledContent("Sent", value: Staff.when(s)) }
                if let e = alert.endsAt { LabeledContent(alert.isLive ? "Ends" : "Ended", value: Staff.when(e)) }
                if let n = alert.sentSentence { LabeledContent("Sent to", value: n) }
            }
            if store.can("alert_sender") && (alert.isLive || alert.isWaiting) {
                Section {
                    if alert.isWaiting {
                        if alert.canConfirm(as: store.me?.email ?? "") {
                            Button { run { await store.confirm(alert) } } label: { Text("Confirm and send to all of Bay County").frame(maxWidth: .infinity) }
                                .buttonStyle(PrimaryButton(color: Brand.salmonFill)).disabled(busy)
                        } else {
                            Text("You wrote this alert, so another alert sender has to confirm it.").font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    Button(role: .destructive) {
                        if sure { run { await store.end(alert) } } else { sure = true }
                    } label: {
                        Text(sure ? (alert.isWaiting ? "Cancel it: are you sure?" : "End it now: are you sure?") : (alert.isWaiting ? "Cancel this alert" : "End this alert"))
                            .frame(maxWidth: .infinity)
                    }
                    .disabled(busy)
                } footer: { ErrorLine(text: error) }
                .listRowBackground(Color.clear)
            }
        }
        .staffPage()
        .navigationTitle("Alert")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func run(_ f: @escaping () async -> String?) {
        busy = true
        Task { error = await f(); busy = false; if error == nil { dismiss() } }
    }
}

/// Write and send an alert. Shows who it reaches before it goes; a countywide alert waits for a second person.
struct SendAlertView: View {
    @Environment(StaffStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @State private var kind = "boil-water"
    @State private var title = ""
    @State private var message = ""
    @State private var instruction = ""
    @State private var severity = "severe"
    @State private var countywide = false
    @State private var hours = 24
    @State private var reach: StaffReach?
    @State private var review = false
    @State private var busy = false
    @State private var error: String?
    @State private var done: String?
    @State private var pins: [AlertArea.Coord] = []
    @State private var radius: Double = 76

    private var ready: Bool { !title.trimmingCharacters(in: .whitespaces).isEmpty && !message.trimmingCharacters(in: .whitespaces).isEmpty }

    var body: some View {
        NavigationStack {
            Form {
                if let done {
                    Section {
                        Label(done, systemImage: "checkmark.circle.fill").foregroundStyle(Brand.good).font(.body.weight(.semibold))
                        Button("Close") { dismiss() }
                    }
                } else {
                    Section("What kind") {
                        Picker("Kind", selection: $kind) {
                            ForEach(Staff.alertOrder.filter { store.alertKinds[$0] != nil }, id: \.self) { Text(store.alertKinds[$0] ?? $0).tag($0) }
                        }
                        .pickerStyle(.navigationLink)
                        Picker("How serious", selection: $severity) { ForEach(Staff.severities, id: \.key) { Text($0.label).tag($0.key) } }
                        Picker("Ends after", selection: $hours) { ForEach(Staff.hourChoices, id: \.self) { Text(Staff.hoursLabel($0)).tag($0) } }
                        if store.workspace?.countywide == true {
                            Toggle("All of Bay County", isOn: $countywide)
                        }
                    }
                    Section {
                        TextField("Headline", text: $title, axis: .vertical).lineLimit(1...3)
                        TextField("What is happening", text: $message, axis: .vertical).lineLimit(3...8)
                        TextField("What people should do (optional)", text: $instruction, axis: .vertical).lineLimit(2...5)
                    } header: { Text("The alert") } footer: { Text("Keep the headline short: it is what shows on a locked phone.") }
                    Section {
                        PinDropMap(pins: $pins, radius: radius).frame(height: 260).listRowInsets(EdgeInsets())
                        Picker("Circle around each pin", selection: $radius) { ForEach(Self.radii) { Text($0.label).tag($0.m) } }
                        if !pins.isEmpty { Button("Clear the map", role: .destructive) { pins = [] } }
                    } header: { Text("Map (optional)") } footer: {
                        Text(pins.isEmpty ? "Tap the map where it applies, like a main break or the street that's closed. Residents see it with the alert. Lines and drawn areas are on the web workspace."
                             : "\(pins.count) pin\(pins.count == 1 ? "" : "s"). Tap a pin to take it off.")
                    }
                    Section {
                        Label(reach?.sentence ?? "Checking who this reaches…", systemImage: "person.3")
                            .font(.subheadline)
                        if countywide {
                            Label("A countywide alert waits until a second alert sender confirms it.", systemImage: "person.2").font(.subheadline).foregroundStyle(Brand.amber)
                        }
                    } header: { Text("Who gets it") }
                    Section {
                        Button { review = true } label: { Text(countywide ? "Review and save" : "Review and send").frame(maxWidth: .infinity) }
                            .buttonStyle(PrimaryButton(color: Brand.salmonFill)).disabled(!ready || busy)
                            .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                    } footer: { ErrorLine(text: error) }
                }
            }
            .staffPage()
            .navigationTitle("Send an alert")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } } }
            .onAppear {
                if Launch.demo, Launch.screen == "send", title.isEmpty {
                    title = "Boil water: Ohio Ave, 5th to 9th St"; severity = "moderate"; hours = 48
                    message = "A water main broke on Ohio Ave. Crews are repairing it now. Pressure may be low."
                    instruction = "Boil water for one minute before drinking or cooking until we lift this notice."
                }
            }
            .task(id: "\(kind)|\(countywide)") { reach = await store.reach(kind: kind, countywide: countywide) }
            .confirmationDialog(countywide ? "Save this countywide alert?" : "Send this alert now?", isPresented: $review, titleVisibility: .visible) {
                Button(countywide ? "Save for a second person" : "Send to \(store.workspace?.name ?? "your city")", role: .destructive, action: send)
                Button("Keep editing", role: .cancel) {}
            } message: {
                Text("\(title)\n\n\(reach?.sentence ?? "")" + (pins.isEmpty ? "" : "\n\nThe map shows with it."))
            }
        }
    }

    /// The circles the web workspace offers (site/area_map.js), in meters.
    struct Radius: Identifiable { let m: Double; let label: String; var id: Double { m } }
    static let radii = [Radius(m: 0, label: "No circle"), Radius(m: 30, label: "100 ft"), Radius(m: 76, label: "¼ block (250 ft)"), Radius(m: 152, label: "500 ft"),
                        Radius(m: 402, label: "¼ mile"), Radius(m: 805, label: "½ mile"), Radius(m: 1609, label: "1 mile")]

    private func send() {
        busy = true; error = nil
        Task {
            switch await store.sendAlert(kind: kind, title: title, message: message, instruction: instruction, severity: severity, countywide: countywide, hours: hours,
                                         geometry: AlertArea.pinsGeoJSON(pins, radius: radius)) {
            case .success(let m): done = m
            case .failure(let e): error = e.localizedDescription
            }
            busy = false
        }
    }
}

/// A map of the city: tap to drop a pin where the alert applies, tap a pin to take it off. Each pin gets the circle picked.
struct PinDropMap: View {
    @Binding var pins: [AlertArea.Coord]
    let radius: Double
    private static let red = Color(red: 0.82, green: 0.26, blue: 0.26)
    @State private var position: MapCameraPosition = .region(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 30.2, longitude: -85.66),
                                                                               span: MKCoordinateSpan(latitudeDelta: 0.18, longitudeDelta: 0.2)))
    var body: some View {
        MapReader { proxy in
            Map(position: $position) {
                ForEach(Array(pins.enumerated()), id: \.offset) { i, p in
                    let c = CLLocationCoordinate2D(latitude: p.lat, longitude: p.lng)
                    if radius > 0 { MapCircle(center: c, radius: radius).foregroundStyle(Self.red.opacity(0.18)).stroke(Self.red, lineWidth: 2) }
                    Annotation("", coordinate: c) {
                        Button { pins.remove(at: i) } label: {
                            Circle().fill(Self.red).frame(width: 18, height: 18).overlay(Circle().stroke(.white, lineWidth: 2))
                        }
                        .buttonStyle(.plain).accessibilityLabel("Remove pin \(i + 1)")
                    }
                    .annotationTitles(.hidden)
                }
            }
            .mapStyle(.standard(pointsOfInterest: .excludingAll))
            .onTapGesture { pt in
                if let c = proxy.convert(pt, from: .local) { pins.append(AlertArea.Coord(lat: c.latitude, lng: c.longitude)) }
            }
        }
        .accessibilityLabel("Map. Tap where the alert applies to drop a pin.")
    }
}
