import SwiftUI
import BayCountyKit

/// Public schools (/schools): the district calendar, every public school with its grade and students, enrollment
/// since 2016, closed schools and the School Board. Zoned schools for an address are on My Address (the same
/// county attendance zones). Reads the schools, school-calendar, school-enrollment and school-grades datasets.
struct SchoolsView: View {
    @Environment(AppStore.self) private var store
    @State private var kind: Schools.Kind = .all
    @State private var filter: Schools.Filter = .all
    @State private var query = ""
    @State private var showAllEvents = false
    @State private var open: String?

    private var schools: [Row] { store.rows["schools"] ?? [] }
    private var calendar: [Row] { store.rows["school-calendar"] ?? [] }
    private var enrollment: [Row] { store.rows["school-enrollment"] ?? [] }
    private var grades: [Row] { store.rows["school-grades"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "Governments · Bay District Schools", title: "Public schools",
                     subtitle: "What's coming up on the school calendar, and every public school in Bay County: grades, students and how each has changed since 2016.",
                     symbol: "graduationcap", tone: .blue)
            if schools.isEmpty {
                if store.errors["schools"] != nil {
                    ContentUnavailableView("Couldn't load the schools", systemImage: "wifi.slash")
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                CardList {
                    RouteRow(route: .myAddress, title: "Which schools serve your address", detail: "Your zoned elementary, middle and high school", symbol: "mappin.and.ellipse")
                }
                calendarSection
                schoolsSection
                enrollmentSection
                closedSection
                boardSection
            }
            FreshnessNote(key: "school-calendar")
        }
        .navigationTitle("Schools")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Schools.datasets) }
        .refreshable { for i in Schools.datasets { await store.load(i, force: true) } }
    }

    private var kpis: some View {
        let openS = Schools.open(schools)
        let charter = openS.filter { $0.bool("charter") == true }.count
        let total = Schools.districtEnrollment(enrollment).last
        let off = Schools.nextDayOff(calendar, today: Self.today)
        return StatGrid {
            KPICard(title: "Public schools", value: "\(openS.count)", caption: "\(openS.count - charter) run by the district, \(charter) charter schools",
                    symbol: "graduationcap", tone: .amber)
            KPICard(title: "Students\(total.map { ", \($0.year)" } ?? "")", value: total.map { Format.number($0.students) } ?? "—",
                    caption: "Enrolled in the fall, from the federal school directory", symbol: "person.3", tone: .blue)
            KPICard(title: "School grades", value: grades.isEmpty ? "—" : "\(Set(grades.compactMap { $0.number("year") }).count) years",
                    caption: grades.isEmpty ? "Being added from the Florida Department of Education" : "Florida Department of Education", symbol: "star", tone: .teal)
            KPICard(title: "Next day off", value: off.flatMap(Schools.date).map { HomeView.month.string(from: $0) + " " + HomeView.dayNumber.string(from: $0) } ?? "—",
                    caption: off?.string("title"), symbol: "calendar", tone: .salmon)
        }
    }

    private var calendarSection: some View {
        let list = Schools.upcoming(calendar, today: Self.today, kind: kind)
        let shown = showAllEvents ? list : Array(list.prefix(6))
        return PageSection(title: "School calendar", symbol: "calendar", tone: .salmon, caption: "From the district's calendar, checked daily") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: Schools.Kind.allCases.map { (id: $0, label: $0.label) }, selected: kind) { kind = $0; showAllEvents = false }
                if list.isEmpty {
                    Text("Nothing coming up in this group.").font(.subheadline).foregroundStyle(.secondary)
                        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                } else {
                    CardList {
                        ForEach(shown) { ev in
                            eventRow(ev)
                            if ev.id != shown.last?.id { RowDivider(inset: 72) }
                        }
                    }
                    if !showAllEvents && list.count > shown.count {
                        Button("Show \(list.count - shown.count) more") { showAllEvents = true }
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                    }
                }
                CardList {
                    WebRow(title: "The district's full calendar", symbol: "safari", url: URL(string: "https://www.bay.k12.fl.us/o/bds/page/academic-calendar"))
                }
            }
        }
    }

    private func eventRow(_ ev: Row) -> some View {
        let d = Schools.date(ev)
        let k = ev.string("kind") ?? ""
        let color: Color = k == "no-school" || k == "break" ? Brand.salmon : k == "board-meeting" ? Brand.navy : Brand.good
        return HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Text(d.map { HomeView.month.string(from: $0).uppercased() } ?? "").font(.caption2.weight(.bold))
                    .foregroundStyle(.white).frame(maxWidth: .infinity).padding(.vertical, 2).background(Brand.salmonFill)
                Text(d.map { HomeView.dayNumber.string(from: $0) } ?? "").font(.title3.weight(.semibold).monospacedDigit()).padding(.top, 2)
                Text(d.map { HomeView.weekday.string(from: $0) } ?? "").font(.caption2).foregroundStyle(.secondary).padding(.bottom, 4)
            }
            .frame(width: 48)
            .background(Brand.surface)
            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(Brand.hairline))
            VStack(alignment: .leading, spacing: 3) {
                Text(ev.string("title") ?? "").font(.subheadline.weight(.semibold)).fixedSize(horizontal: false, vertical: true)
                Text(Schools.when(ev)).font(.caption).foregroundStyle(.secondary)
                if let v = ev.string("venue") { Text(v).font(.caption).foregroundStyle(.secondary) }
                Badge(text: Schools.kindLabel(k), color: color)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14).padding(.vertical, 11)
        .accessibilityElement(children: .combine)
    }

    private var schoolsSection: some View {
        let list = Schools.open(schools, filter: filter, query: query)
        return PageSection(title: "Every public school", symbol: "graduationcap", tone: .amber, caption: "\(list.count) schools · tap one for its details") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: Schools.Filter.allCases.map { (id: $0, label: $0.label) }, selected: filter) { filter = $0 }
                TextField("Find a school or city", text: $query)
                    .textFieldStyle(.plain).padding(12).card(12)
                CardList {
                    ForEach(list) { s in
                        schoolRow(s)
                        if s.id != list.last?.id { RowDivider(inset: 64) }
                    }
                }
                Text("The letter is the school's latest Florida school grade. Students are from the federal school directory.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private func schoolRow(_ s: Row) -> some View {
        let id = s.string("school_id") ?? ""
        let expanded = open == id
        VStack(alignment: .leading, spacing: 10) {
            Button { withAnimation { open = expanded ? nil : id } } label: {
                HStack(spacing: 12) {
                    Text(s.string("latest_grade") ?? "–").font(.headline).frame(width: 36, height: 36)
                        .background(Brand.hairline.opacity(0.4), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
                    VStack(alignment: .leading, spacing: 2) {
                        Text(s.string("name") ?? "").font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                            .multilineTextAlignment(.leading).fixedSize(horizontal: false, vertical: true)
                        Text(Schools.subtitle(s)).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
                    }
                    Spacer(minLength: 4)
                    Image(systemName: expanded ? "chevron.up" : "chevron.down").font(.caption.weight(.semibold)).foregroundStyle(.tertiary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if expanded { schoolDetail(s) }
        }
        .padding(.horizontal, 14).padding(.vertical, 10)
    }

    @ViewBuilder private func schoolDetail(_ s: Row) -> some View {
        let id = s.string("school_id") ?? ""
        let years = Schools.enrollment(enrollment, school: id)
        let g = Schools.grades(grades, school: id)
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                fact("Students\(s.string("enrollment_year").map { ", \($0)" } ?? "")", s.number("enrollment").map { Format.number($0) } ?? "—")
                fact("Per teacher", s.number("students_per_teacher").map { Format.number($0) } ?? "—")
                fact("Free or reduced lunch", s.number("free_reduced_lunch_pct").map { "\(Format.number($0))%" } ?? "—")
            }
            if let a = s.string("address") {
                Text([a, s.string("city"), s.string("phone")].compactMap { $0 }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
            }
            if !g.isEmpty {
                Text("Grades: " + g.prefix(6).map { "\(Int($0.number("year") ?? 0)) \($0.string("grade") ?? "")" }.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
            }
            if years.count > 1, let first = years.first, let last = years.last {
                Text("Students: \(Format.number(first.students)) in \(first.year), \(Format.number(last.students)) in \(last.year)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            WebRow(title: "On BayCounty.me", symbol: "safari", url: Schools.pageURL(s))
        }
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption2).foregroundStyle(.secondary).lineLimit(2).minimumScaleFactor(0.8)
            Text(value).font(.subheadline.weight(.semibold).monospacedDigit())
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Brand.hairline.opacity(0.35), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    private var enrollmentSection: some View {
        let ys = Schools.districtEnrollment(enrollment)
        let hi = ys.map(\.students).max() ?? 1
        return PageSection(title: "Students by year", symbol: "chart.bar", tone: .blue, caption: "Every public school, fall enrollment") {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .bottom, spacing: 6) {
                    ForEach(ys, id: \.year) { y in
                        VStack(spacing: 4) {
                            Text(String(format: "%.1fK", y.students / 1000)).font(.system(size: 9, weight: .semibold)).lineLimit(1).minimumScaleFactor(0.7)
                            RoundedRectangle(cornerRadius: 4)
                                .fill(y.year == "2019-20" || y.year == "2020-21" ? Brand.salmon : Brand.navy)
                                .frame(height: max(4, 110 * y.students / hi))
                            Text(String(y.year.suffix(2))).font(.system(size: 9)).foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .padding(14).card(14)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(ys.map { "\($0.year): \(Format.number($0.students))" }.joined(separator: ", "))
                Text("Red: the two school years after Hurricane Michael (October 2018), when enrollment fell and several schools closed or merged.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    private var closedSection: some View {
        let list = Schools.closed(schools)
        return PageSection(title: "Schools closed since 2016", symbol: "xmark.circle", tone: .amber, caption: "\(list.count) schools") {
            CardList {
                ForEach(list) { s in
                    TextRow(title: s.string("name") ?? "", detail: ["Last listed \(s.string("last_year_open") ?? "")", s.string("city")].compactMap { $0 }.joined(separator: " · "))
                    if s.id != list.last?.id { RowDivider() }
                }
            }
        }
    }

    private var boardSection: some View {
        PageSection(title: "Who runs the schools", symbol: "person.3", tone: .blue,
                    caption: "An elected five-member School Board and an elected superintendent") {
            CardList {
                RouteRow(route: .government("schools"), title: "Bay District Schools", detail: "Budget, debt, audits, board members and meetings", symbol: "building.columns")
                RowDivider(inset: 50)
                RouteRow(route: .dataset("votes", filters: ["board": "Bay District School Board"]), title: "How the board voted", symbol: "hand.raised")
            }
        }
    }
}
