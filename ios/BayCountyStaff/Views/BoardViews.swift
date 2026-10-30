import SwiftUI
import BayCountyKit

/// An elected official's board dashboard (GET /api/gov?action=official): next meetings and what's on each agenda,
/// their voting record and the budget. Read only, like the web dashboard; the PDF reports are on the web.
struct BoardView: View {
    @Environment(StaffStore.self) private var store

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let b = store.board {
                    if let o = b.official {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(o.name).font(.title2.weight(.bold))
                            Text([o.seat, o.body, o.since.map { "since " + Staff.when($0) }].compactMap { $0 }.joined(separator: " · "))
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        ValueTile(value: b.nextMeeting.map { shortDay($0.date) } ?? "None set", label: "Next meeting")
                        ValueTile(value: "\(b.meetings.upcoming.count)", label: "Meetings in the next 90 days")
                        if let v = b.votes {
                            ValueTile(value: v.count.votes.formatted(), label: "Votes on record")
                            ValueTile(value: "\(v.count.split)", label: "Split votes, \(v.count.onLosingSide) on the losing side")
                        }
                        if let y = b.latestBudget { ValueTile(value: StaffBoard.money(y.total ?? y.generalFund), label: "FY\(String(y.fiscalYear)) adopted budget") }
                        ValueTile(value: StaffBoard.money(b.numbers?.contracts?.total), label: "Contracts, last 12 months")
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Eyebrow(text: "Coming up")
                        if b.meetings.upcoming.isEmpty {
                            Text("No meetings on the calendar for the next 90 days.").font(.subheadline).foregroundStyle(.secondary).padding(14).frame(maxWidth: .infinity, alignment: .leading).card()
                        }
                        ForEach(Array(b.meetings.upcoming.prefix(4).enumerated()), id: \.offset) { _, m in MeetingCard(m: m) }
                    }
                    if let years = b.numbers?.budget?.history, !years.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Eyebrow(text: "Adopted budget")
                            VStack(spacing: 0) {
                                ForEach(Array(years.reversed().enumerated()), id: \.offset) { i, y in
                                    if i > 0 { Divider().padding(.leading, 14) }
                                    HStack {
                                        Text("FY\(String(y.fiscalYear))")
                                        Spacer()
                                        Text(StaffBoard.money(y.total ?? y.generalFund)).fontWeight(.semibold).monospacedDigit()
                                    }
                                    .padding(.horizontal, 14).padding(.vertical, 11)
                                }
                            }
                            .card()
                        }
                    }
                    Link(destination: URL(string: "https://baycounty.me/staff#board")!) {
                        VStack(alignment: .leading, spacing: 2) {
                            Label("PDF reports", systemImage: "doc.richtext").font(.body.weight(.semibold))
                            Text("Full briefing, agendas, voting record and numbers, on the web workspace.").font(.footnote).foregroundStyle(.secondary)
                        }
                        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card()
                    }
                    Text("Public record, read from agendas, minutes and budgets. It can't be changed here; flag anything that looks wrong.")
                        .font(.footnote).foregroundStyle(.secondary)
                } else if store.loading {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                }
                ErrorLine(text: store.error)
            }
            .padding(16)
        }
        .background(Brand.canvas)
        .navigationTitle(store.workspace?.name ?? "Board")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await store.refresh() }
    }
}

private struct MeetingCard: View {
    let m: StaffBoard.Meeting
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(longDay(m)).font(.body.weight(.semibold))
            Text([m.boardName, m.location].compactMap { $0 }.joined(separator: " · ")).font(.footnote).foregroundStyle(.secondary).lineLimit(2)
            if let s = m.statusLabel { Chip(text: s, color: m.status == "cancelled" ? Brand.salmon : Brand.navy) }
            ForEach(Array(m.items.prefix(5).enumerated()), id: \.offset) { _, i in
                Text("• \(i.title)\(i.amount.map { "  \($0)" } ?? "")").font(.subheadline).lineLimit(3)
            }
            if m.items.count > 5 { Text("And \(m.items.count - 5) more items").font(.footnote).foregroundStyle(.secondary) }
            HStack(spacing: 14) {
                if let a = m.agendaUrl.flatMap(URL.init(string:)) { Link("Agenda", destination: a).font(.body.weight(.semibold)) }
                if let p = m.packetUrl.flatMap(URL.init(string:)) { Link("Full packet", destination: p).font(.body.weight(.semibold)) }
            }
            .padding(.top, 4)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
    }
}

/// The official's votes: counts, then the latest motions with how they voted.
struct VotesView: View {
    @Environment(StaffStore.self) private var store
    var body: some View {
        List {
            if let v = store.board?.votes {
                Section {
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                        ValueTile(value: v.count.yes.formatted(), label: "Yes")
                        ValueTile(value: v.count.no.formatted(), label: "No")
                        ValueTile(value: (v.count.absent + v.count.abstain).formatted(), label: "Absent or abstained")
                        ValueTile(value: v.presentRate.map { "\($0.formatted())%" } ?? "—", label: "Present")
                    }
                    .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
                }
                Section {
                    ForEach(Array(v.recent.prefix(60).enumerated()), id: \.offset) { _, x in
                        HStack(alignment: .top, spacing: 10) {
                            VStack(alignment: .leading, spacing: 3) {
                                Text(x.headline ?? "Motion").font(.subheadline).lineLimit(3)
                                Text([x.date.map { Staff.when($0) }, x.result.isEmpty ? nil : x.result, x.amount.map { StaffBoard.money($0) }].compactMap { $0 }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                            Spacer(minLength: 0)
                            Chip(text: x.voteLabel, color: x.vote == "yes" ? Brand.good : x.vote == "no" ? Brand.salmon : .secondary)
                        }
                    }
                } header: { Text("Latest votes") } footer: {
                    Text("From the official minutes and hand-checked money votes. The full record and a PDF are on the web workspace.")
                }
            } else if store.board != nil {
                Text("No seat on record is tied to this account yet.").foregroundStyle(.secondary)
            } else if store.loading {
                ProgressView()
            }
        }
        .staffPage()
        .navigationTitle("Voting record")
        .refreshable { await store.refresh() }
    }
}

/// A short value (a date, an amount) with a label.
struct ValueTile: View {
    let value: String
    let label: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(value).font(.title2.weight(.bold)).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            Text(label).font(.footnote).foregroundStyle(.secondary).lineLimit(2, reservesSpace: true)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .card(14)
        .accessibilityElement(children: .combine)
    }
}

private func shortDay(_ d: String) -> String {
    let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
    guard let date = f.date(from: d) else { return d }
    let o = DateFormatter(); o.locale = Locale(identifier: "en_US"); o.dateFormat = "MMM d"
    return o.string(from: date)
}

private func longDay(_ m: StaffBoard.Meeting) -> String {
    let o = DateFormatter(); o.locale = Locale(identifier: "en_US"); o.timeZone = TimeZone(identifier: "America/Chicago")
    if let s = m.start, s.count > 10, let d = ISO8601DateFormatter().date(from: s) { o.dateFormat = "EEEE, MMM d, h:mm a"; return o.string(from: d) }
    let f = DateFormatter(); f.locale = Locale(identifier: "en_US_POSIX"); f.dateFormat = "yyyy-MM-dd"
    guard let d = f.date(from: m.date) else { return m.date }
    o.timeZone = .current; o.dateFormat = "EEEE, MMM d"
    return o.string(from: d)
}
