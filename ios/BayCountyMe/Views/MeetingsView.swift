import SwiftUI
import BayCountyKit

struct MeetingsView: View {
    @Environment(AppStore.self) private var store
    @State private var gov: String = "all"

    /// Chips in the order the site lists governments.
    private static let govOrder = ["county", "schools", "pc", "pcb", "lh", "cw", "sp", "parker", "mb"]
    private static let short = ["county": "County", "schools": "Schools"]

    private var upcoming: [Meeting] {
        Meeting.upcoming(store.meetings).filter { gov == "all" || $0.govID == gov }
    }

    private var days: [(key: String, meetings: [Meeting])] {
        let grouped = Dictionary(grouping: upcoming) { $0.start.map(Dates.dayKey) ?? "" }
        return grouped.keys.sorted().map { ($0, grouped[$0]!) }
    }

    /// Only governments that have something coming up, so no chip leads to an empty list.
    private var chips: [(id: String, label: String)] {
        let has = Set(Meeting.upcoming(store.meetings).map(\.govID))
        return [(id: "all", label: "All")] + Self.govOrder.filter(has.contains).map { (id: $0, label: Self.short[$0] ?? Governments.names[$0] ?? $0) }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    ChipRow(chips: chips, selected: gov) { id in withAnimation(.snappy) { gov = id } }
                    FreshnessNote(key: "meetings")
                    if upcoming.isEmpty {
                        VStack(spacing: 6) {
                            Image(systemName: "calendar").font(.title2).foregroundStyle(.secondary)
                            Text("No upcoming meetings").font(.headline)
                            Text("New agendas appear here as soon as they're posted.").font(.subheadline).foregroundStyle(.secondary)
                        }
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: .infinity)
                        .padding(32)
                        .card(16)
                    }
                    ForEach(days, id: \.key) { day in
                        VStack(alignment: .leading, spacing: 8) {
                            Text(day.meetings.first?.start.map { Dates.display($0, hasTime: false) } ?? "")
                                .font(.subheadline.weight(.bold)).foregroundStyle(.secondary)
                                .accessibilityAddTraits(.isHeader)
                            CardList {
                                ForEach(day.meetings) { m in
                                    NavigationLink(value: Route.meeting(m.id)) { TodayMeetingRow(meeting: m) }
                                        .buttonStyle(.plain)
                                    if m.id != day.meetings.last?.id { RowDivider(inset: 66) }
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle("Meetings")
            .refreshable { await store.loadMeetings() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Link(destination: BayCountyClient.meetingsCalendarURL(gov: gov == "all" ? nil : gov)) {
                        Image(systemName: "calendar.badge.plus")
                    }
                    .accessibilityLabel(gov == "all" ? "Add every meeting to Calendar" : "Add \(Governments.names[gov] ?? "these") meetings to Calendar")
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
    @State private var filter: AgendaItem.Kind?
    @State private var filterSet = false

    var body: some View {
        if let m = store.meetings.first(where: { $0.id == meetingID }) {
            let agenda = m.agenda
            let money = agenda.filter { $0.amount != nil }.sorted { ($0.amount ?? 0) > ($1.amount ?? 0) }
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    header(m)
                    if !money.isEmpty { moneyCard(money) }
                    if !agenda.isEmpty { agendaSection(agenda, hasMoney: !money.isEmpty) }
                    documents(m)
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .navigationTitle(m.boardName)
            .navigationBarTitleDisplayMode(.inline)
            .onAppear { if !filterSet { filter = money.isEmpty ? nil : .spending; filterSet = true } }
        } else {
            ContentUnavailableView("Meeting not found", systemImage: "calendar")
        }
    }

    private func header(_ m: Meeting) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text((Governments.names[m.govID] ?? m.boardName).uppercased())
                .font(.caption.weight(.bold)).tracking(0.8).foregroundStyle(Brand.salmon)
            Text(m.title).font(.title2.weight(.heavy))
            Text(m.whenText).font(.subheadline.weight(.semibold))
            if let loc = m.location {
                Link(destination: URL(string: "maps://?q=\(loc.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")")!) {
                    Label(loc, systemImage: "mappin.and.ellipse").font(.subheadline).multilineTextAlignment(.leading)
                }
            }
            if m.isExpected {
                Label("Expected from the board's regular schedule. Confirm before you go.", systemImage: "info.circle")
                    .font(.footnote).foregroundStyle(Brand.amber)
            }
            HStack(spacing: 8) {
                Link(destination: BayCountyClient.meetingsCalendarURL(gov: m.govID)) {
                    Text("Add to Calendar").frame(maxWidth: .infinity, minHeight: 44)
                        .foregroundStyle(.white).background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                }
                if let a = m.agendaURL {
                    Button { store.open(a) } label: {
                        Text("Agenda").frame(maxWidth: .infinity, minHeight: 44)
                            .foregroundStyle(Brand.navy).card(12)
                    }
                }
            }
            .font(.subheadline.weight(.semibold))
            .padding(.top, 10)
        }
        .padding(.top, 8)
    }

    private func moneyCard(_ money: [AgendaItem]) -> some View {
        let total = money.compactMap(\.amount).reduce(0, +)
        let shades = [Brand.navy, Brand.blue, Brand.blue.opacity(0.55)]
        let top = Array(money.prefix(3))
        let rest = money.dropFirst(3).compactMap(\.amount).reduce(0, +)
        var parts: [(label: String, value: Double, color: Color)] = top.enumerated().map { p in (label: p.element.shortTitle, value: p.element.amount ?? 0, color: shades[p.offset]) }
        if rest > 0 { parts.append((label: "\(money.count - 3) smaller items", value: rest, color: Color.secondary.opacity(0.3))) }
        return VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text(Format.compactMoney(total)).font(.title.weight(.heavy).monospacedDigit())
                Spacer()
                Text("up for a vote · \(money.count) item\(money.count == 1 ? "" : "s")").font(.caption).foregroundStyle(.secondary)
            }
            StackBar(parts: parts)
            VStack(spacing: 6) {
                ForEach(Array(parts.enumerated()), id: \.offset) { _, p in
                    HStack(spacing: 8) {
                        RoundedRectangle(cornerRadius: 2).fill(p.color).frame(width: 8, height: 8)
                        Text(p.label).lineLimit(1)
                        Spacer()
                        Text(Format.compactMoney(p.value)).fontWeight(.semibold).monospacedDigit()
                    }
                    .font(.caption)
                }
            }
        }
        .padding(16)
        .card(18)
    }

    private func agendaSection(_ agenda: [AgendaItem], hasMoney: Bool) -> some View {
        let shown = agenda.filter { filter == nil || $0.kind == filter }
        let ordered = filter == .spending ? shown.sorted { ($0.amount ?? 0) > ($1.amount ?? 0) } : shown
        let chips: [(label: String, kind: AgendaItem.Kind?)] = [("All", nil), ("Spending", .spending), ("Hearings", .hearing), ("Other", .other)]
        return VStack(alignment: .leading, spacing: 12) {
            Text("Agenda").font(.title3.weight(.bold))
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(chips, id: \.label) { c in
                        let n = c.kind == nil ? agenda.count : agenda.filter { $0.kind == c.kind }.count
                        let on = filter == c.kind
                        if n > 0 || c.kind == nil {
                            Button { withAnimation(.snappy) { filter = c.kind } } label: {
                                (Text(c.label) + Text(" \(n)").foregroundColor(on ? Color.white.opacity(0.75) : .secondary))
                                    .font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 12).frame(minHeight: 36)
                                    .foregroundStyle(on ? Color.white : .primary)
                                    .background(on ? Brand.navyFill : Brand.surface, in: Capsule())
                            }
                            .buttonStyle(.plain)
                            .accessibilityAddTraits(on ? .isSelected : [])
                        }
                    }
                }
            }
            CardList {
                ForEach(ordered) { it in
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(it.shortTitle).font(.subheadline).fixedSize(horizontal: false, vertical: true)
                            Text(it.kind.label).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer(minLength: 4)
                        if let a = it.amount {
                            Text(Format.compactMoney(a)).font(.subheadline.weight(.bold).monospacedDigit())
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if it.id != ordered.last?.id { Divider().padding(.leading, 14) }
                }
            }
            Text("From the posted agenda. Amounts are the first dollar figure in each item.").font(.caption).foregroundStyle(.secondary)
        }
    }

    private func documents(_ m: Meeting) -> some View {
        let docs: [(title: String, symbol: String, url: URL)] = [
            ("Agenda", "doc.text", m.agendaURL), ("Agenda packet", "doc.on.doc", m.packetURL),
            ("Minutes", "text.book.closed", m.minutesURL), ("Meeting page", "safari", m.detailURL),
            ("Email alerts for this government", "envelope", URL(string: "https://baycounty.me/alerts")),
        ].compactMap { d in d.2.map { (title: d.0, symbol: d.1, url: $0) } }
        return VStack(alignment: .leading, spacing: 12) {
            Text("Documents").font(.title3.weight(.bold))
            CardList {
                if m.agendaURL == nil && m.packetURL == nil && m.minutesURL == nil {
                    Text("No agenda or minutes posted yet.").font(.subheadline).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading).padding(.horizontal, 14)
                    Divider().padding(.leading, 14)
                }
                ForEach(docs, id: \.title) { d in
                    Button { store.open(d.url) } label: {
                        HStack(spacing: 12) {
                            Image(systemName: d.symbol).foregroundStyle(Brand.navy).frame(width: 24)
                            Text(d.title).foregroundStyle(.primary)
                            Spacer()
                            Image(systemName: "arrow.up.right").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                        }
                        .frame(minHeight: 48).padding(.horizontal, 14).contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if d.title != docs.last?.title { Divider().padding(.leading, 50) }
                }
            }
        }
    }
}
