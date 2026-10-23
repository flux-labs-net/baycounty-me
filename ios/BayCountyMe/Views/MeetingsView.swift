import SwiftUI
import BayCountyKit

struct MeetingsView: View {
    @Environment(AppStore.self) private var store
    @State private var gov: String? = nil

    private var upcoming: [Meeting] {
        Meeting.upcoming(store.meetings).filter { gov == nil || $0.govID == gov }
    }

    private var days: [(key: String, meetings: [Meeting])] {
        let grouped = Dictionary(grouping: upcoming) { $0.start.map(Dates.dayKey) ?? "" }
        return grouped.keys.sorted().map { ($0, grouped[$0]!) }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    FreshnessNote(key: "meetings")
                    Link(destination: BayCountyClient.meetingsCalendarURL(gov: gov)) {
                        Label(gov == nil ? "Add every meeting to Calendar" : "Add \(Governments.names[gov!] ?? "these") meetings to Calendar",
                              systemImage: "calendar.badge.plus")
                    }
                }
                if upcoming.isEmpty {
                    ContentUnavailableView("No upcoming meetings", systemImage: "calendar",
                                           description: Text("New agendas appear here as soon as they're posted."))
                }
                ForEach(days, id: \.key) { day in
                    Section(day.meetings.first.map { Dates.display($0.start!, hasTime: false) } ?? "") {
                        ForEach(day.meetings) { m in
                            NavigationLink(value: Route.meeting(m.id)) { MeetingRow(meeting: m, showDate: false) }
                        }
                    }
                }
            }
            .navigationTitle("Meetings")
            .refreshable { await store.loadMeetings() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Picker("Government", selection: $gov) {
                            Text("All governments").tag(String?.none)
                            ForEach(Governments.names.sorted { $0.value < $1.value }, id: \.key) { pair in
                                Text(pair.value).tag(String?.some(pair.key))
                            }
                        }
                    } label: {
                        Image(systemName: gov == nil ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
                    }
                    .accessibilityLabel("Filter by government")
                }
            }
            .withRoutes()
        }
    }
}

struct MeetingRow: View {
    let meeting: Meeting
    var showDate = true

    /// Meeting times are shown in Bay County time wherever the phone is.
    static let time: DateFormatter = {
        let f = DateFormatter()
        f.timeZone = TimeZone(identifier: "America/Chicago")
        f.dateFormat = "h:mm a"
        return f
    }()

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(meeting.boardName).font(.subheadline.weight(.medium))
            Text(meeting.title).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            HStack(spacing: 6) {
                if let s = meeting.start {
                    Text(showDate ? meeting.whenText : (meeting.hasTime ? Self.time.string(from: s) : "Time not posted"))
                }
                if meeting.isExpected { Badge(text: "Expected", color: Brand.amber) }
                else if meeting.agendaURL != nil { Badge(text: "Agenda posted", color: Brand.good) }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}

struct MeetingDetailView: View {
    @Environment(AppStore.self) private var store
    let meetingID: String

    var body: some View {
        if let m = store.meetings.first(where: { $0.id == meetingID }) {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(m.title).font(.title3.weight(.semibold))
                        Text(m.whenText).foregroundStyle(.secondary)
                        if m.isExpected {
                            Label("Expected from the board's regular schedule. Confirm before you go.", systemImage: "info.circle")
                                .font(.footnote).foregroundStyle(Brand.amber)
                        }
                    }
                    .padding(.vertical, 4)
                    if let loc = m.location {
                        Link(destination: URL(string: "maps://?q=\(loc.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")")!) {
                            Label(loc, systemImage: "mappin.and.ellipse")
                        }
                    }
                }
                if !m.agendaItems.isEmpty {
                    Section("On the agenda") {
                        ForEach(Array(m.agendaItems.enumerated()), id: \.offset) { _, item in
                            Text(item).font(.callout)
                        }
                    }
                }
                Section("Documents") {
                    WebLink(title: "Agenda", symbol: "doc.text", url: m.agendaURL)
                    WebLink(title: "Agenda packet", symbol: "doc.on.doc", url: m.packetURL)
                    WebLink(title: "Minutes", symbol: "text.book.closed", url: m.minutesURL)
                    WebLink(title: "Meeting page", symbol: "safari", url: m.detailURL)
                    if m.agendaURL == nil && m.packetURL == nil && m.minutesURL == nil {
                        Text("No documents posted yet.").foregroundStyle(.secondary)
                    }
                }
                Section {
                    Link(destination: BayCountyClient.meetingsCalendarURL(gov: m.govID)) {
                        Label("Add \(Governments.names[m.govID] ?? "these") meetings to Calendar", systemImage: "calendar.badge.plus")
                    }
                    WebLink(title: "Email alerts for this government", symbol: "envelope", url: URL(string: "https://baycounty.me/alerts"))
                }
            }
            .navigationTitle(m.boardName)
            .navigationBarTitleDisplayMode(.inline)
        } else {
            ContentUnavailableView("Meeting not found", systemImage: "calendar")
        }
    }
}
