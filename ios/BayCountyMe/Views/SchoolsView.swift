import SwiftUI
import MapKit
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
    @State private var zoneLevel = "None"
    @State private var showAllSpending = false

    private var schools: [Row] { store.rows["schools"] ?? [] }
    private var calendar: [Row] { store.rows["school-calendar"] ?? [] }
    private var enrollment: [Row] { store.rows["school-enrollment"] ?? [] }
    private var grades: [Row] { store.rows["school-grades"] ?? [] }
    private var gradeState: [Row] { store.rows["school-grade-state"] ?? [] }
    private var spend: [Row] { store.rows["school-spending"] ?? [] }
    private var bell: [Row] { store.rows["school-bell-times"] ?? [] }

    private static let today: String = {
        let f = DateFormatter(); f.timeZone = TimeZone(identifier: "America/Chicago"); f.dateFormat = "yyyy-MM-dd"; return f.string(from: Date())
    }()

    var body: some View {
        PageScroll {
            PageHero(kicker: "Governments · Bay District Schools", title: "Public schools",
                     subtitle: "Find the schools zoned for your address, see what's coming up on the school calendar, and compare every public school in Bay County: grades, students, spending and how each has changed since 2016.",
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
                mapSection
                calendarSection
                schoolsSection
                gradesSection
                spendingSection
                enrollmentSection
                closedSection
                boardSection
            }
            FreshnessNote(key: "school-calendar")
        }
        .navigationTitle("Schools")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(Schools.datasets); await store.load(Schools.zonesDataset) }
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
            if let g = Schools.gradeCounts(schools, grades: grades) {
                KPICard(title: "A schools, \(Schools.yearLabel(g.year))", value: "\(g.a)",
                        caption: "of \(g.graded) graded. \(g.b) B, \(g.c) C, \(g.df) D or F", symbol: "star", tone: .teal)
            } else {
                KPICard(title: "State school grades", value: "—", caption: "Being added from the Florida Department of Education", symbol: "star", tone: .teal)
            }
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
                if let early = Schools.earlyRelease(bell) {
                    Text("Early release days (\(Schools.bellYear(bell) ?? "")): \(early). Each school's start and end times are under Every public school.")
                        .font(.footnote).foregroundStyle(.secondary)
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
                    GradeBadge(grade: s.string("latest_grade"))
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
        let sp = Schools.spending(spend, school: id)
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                fact("Students\(s.string("enrollment_year").map { ", \($0)" } ?? "")", s.number("enrollment").map { Format.number($0) } ?? "—")
                fact("Per teacher", s.number("students_per_teacher").map { Format.number($0) } ?? "—")
                fact("Spent per student\(sp.map { ", \(Schools.yearLabel($0.year))" } ?? "")", sp.map { Format.money($0.perStudent.rounded()) } ?? "—")
            }
            if !g.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("State grades").font(.caption).foregroundStyle(.secondary)
                    FlowLayout(spacing: 6) {
                        ForEach(g.reversed()) { r in
                            VStack(spacing: 2) {
                                GradeBadge(grade: r.string("grade"), size: 26)
                                Text(String(Int(r.number("year") ?? 0))).font(.system(size: 10).monospacedDigit()).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("State grades: " + g.map { "\(Int($0.number("year") ?? 0)) \($0.string("grade") ?? "")" }.joined(separator: ", "))
            }
            if let sc = Schools.scores(grades: grades, state: gradeState, school: id) { ScoreBars(title: sc.title, stateLabel: sc.stateLabel, items: sc.items) }
            if years.count > 1, let first = years.first, let last = years.last {
                Text("Students: \(Format.number(first.students)) in \(first.year), \(Format.number(last.students)) in \(last.year)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let h = Schools.hours(bell, school: id) {
                (Text("School day \(Schools.bellYear(bell) ?? ""): ").bold() + Text(h)).font(.caption)
            }
            if let lunch = s.number("free_reduced_lunch_pct") {
                Text("\(Format.number(lunch.rounded()))% of students qualify for free or reduced-price lunch.").font(.caption).foregroundStyle(.secondary)
            }
            CardList {
                if let u = Schools.mapsURL(s) {
                    Button { store.open(u) } label: {
                        RowLabel(title: [s.string("address"), s.string("city")].compactMap { $0 }.joined(separator: ", "), detail: "Open in Maps", symbol: "map")
                    }.buttonStyle(.plain)
                    RowDivider(inset: 50)
                }
                if let ph = Schools.phone(s) {
                    Button { store.open(ph.url) } label: { RowLabel(title: ph.label, detail: "Call the school", symbol: "phone") }.buttonStyle(.plain)
                    RowDivider(inset: 50)
                }
                WebRow(title: "On BayCounty.me", symbol: "safari", url: Schools.pageURL(s))
            }
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

    private static func gradeColor(_ g: String?) -> Color {
        switch g { case "A": Brand.good; case "B": Brand.blue; case "C": Brand.amber; case "D", "F": Brand.salmon; default: .gray }
    }

    /// Every open school as a dot colored by its latest grade, with one level's attendance zones drawn under them.
    private var mapSection: some View {
        let pts: [MapPoint] = Schools.open(schools).compactMap { s in
            guard let lat = s.number("latitude"), let lon = s.number("longitude") else { return nil }
            return MapPoint(id: s.string("school_id") ?? "\(s.id)", title: "\(s.string("name") ?? "")\(s.string("latest_grade").map { ", grade \($0)" } ?? "")",
                            coordinate: CLLocationCoordinate2D(latitude: lat, longitude: lon), color: Self.gradeColor(s.string("latest_grade")), row: s)
        }
        let zones = zoneLevel == "None" ? [] : Schools.zones(store.rows[Schools.zonesDataset] ?? [], level: zoneLevel)
        return PageSection(title: "Map of every school", symbol: "map", tone: .blue, caption: "Colored by the latest state grade") {
            VStack(alignment: .leading, spacing: 10) {
                ChipRow(chips: [("None", "No zones"), ("Elementary", "Elementary zones"), ("Middle", "Middle"), ("High", "High")].map { (id: $0.0, label: $0.1) },
                        selected: zoneLevel) { zoneLevel = $0 }
                PointsMap(points: pts, zones: zones) { p in
                    if let id = p.row?.string("school_id") { withAnimation { open = id; filter = .all; query = "" } }
                }
                HStack(spacing: 12) {
                    ForEach([("A", "A"), ("B", "B"), ("C", "C"), ("D", "D or F"), ("", "No grade")], id: \.1) { g, label in
                        HStack(spacing: 4) { Circle().fill(Self.gradeColor(g)).frame(width: 9, height: 9); Text(label) }
                    }
                }
                .font(.caption).foregroundStyle(.secondary)
                Text("Tap a school to open it below. Zones are the county's attendance zones; your own zoned schools are on My Address.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder private var gradesSection: some View {
        if let y = Schools.latestGradeYear(grades) {
            let mix = Schools.gradeMix(grades: grades, state: gradeState, year: y)
            PageSection(title: "School grades", symbol: "star", tone: .teal, caption: "Florida Department of Education") {
                VStack(alignment: .leading, spacing: 12) {
                    if let fl = mix.florida {
                        Text("In \(Schools.yearLabel(y)), **\(Int(Schools.aShare(mix.local).rounded()))%** of Bay County's graded public schools earned an A, compared with **\(Int(Schools.aShare(fl).rounded()))%** of schools statewide. Open a school above to see the test scores behind its grade next to the Florida average.")
                            .font(.subheadline)
                        VStack(alignment: .leading, spacing: 10) {
                            GradeMixBar(label: "Bay County", count: mix.local.values.reduce(0, +), mix: mix.local)
                            GradeMixBar(label: "Florida", count: fl.values.reduce(0, +), mix: fl)
                        }
                        .padding(14).card(14)
                    }
                    Text("No school grades were given for 2019-20, when state testing was canceled. For 2020-21, only schools that asked got a grade. 2022-23 grades were an informational baseline after the state changed its tests.")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
        }
    }

    @ViewBuilder private var spendingSection: some View {
        if let r = Schools.spendingRanking(spend, schools: schools), let top = r.rows.first?.perStudent {
            let shown = showAllSpending ? r.rows : Array(r.rows.prefix(10))
            PageSection(title: "Spending per school", symbol: "dollarsign.circle", tone: .amber, caption: "Per-pupil expenditure reports") {
                VStack(alignment: .leading, spacing: 12) {
                    Text("What each school spent per student in \(Schools.yearLabel(r.year)), counting federal, state and local money. Across these schools the average was about **\(Format.money(r.average.rounded()))** per student. Schools for students with disabilities, alternative schools and small schools cost more per student.")
                        .font(.subheadline)
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(shown, id: \.id) { x in
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Text(x.name).font(.caption).lineLimit(1)
                                    Spacer(minLength: 6)
                                    Text(Format.money(x.perStudent.rounded())).font(.caption.weight(.semibold).monospacedDigit())
                                }
                                GeometryReader { geo in
                                    Capsule().fill(Brand.amber).frame(width: max(4, geo.size.width * x.perStudent / top))
                                }
                                .frame(height: 6)
                            }
                            .accessibilityElement(children: .combine)
                        }
                    }
                    .padding(14).card(14)
                    if r.rows.count > shown.count {
                        Button("Show all \(r.rows.count) schools") { showAllSpending = true }
                            .font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity, minHeight: 44).card(14)
                    }
                    CardList {
                        RouteRow(route: .overlaps, title: "Where records overlap", detail: "School spending next to grades, and more", symbol: "point.3.connected.trianglepath.dotted")
                    }
                }
            }
        }
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

/// A school's letter grade in its grade color (A teal, B blue, C amber, D or F salmon).
struct GradeBadge: View {
    let grade: String?
    var size: CGFloat = 36

    private var color: Color {
        switch grade { case "A": Brand.good; case "B": Brand.blue; case "C": Brand.amber; case "D", "F": Brand.salmon; default: .secondary }
    }

    var body: some View {
        Text(grade ?? "–").font(size > 30 ? .headline : .caption.weight(.bold))
            .foregroundStyle(grade == nil ? .secondary : color)
            .frame(width: size, height: size)
            .background((grade == nil ? Brand.hairline : color).opacity(0.2), in: RoundedRectangle(cornerRadius: size / 4, style: .continuous))
            .accessibilityLabel(grade.map { "Grade \($0)" } ?? "No grade")
    }
}

/// The parts of a school's grade: a bar per score with a mark for the Florida average, and the change from the year before.
struct ScoreBars: View {
    let title: String
    let stateLabel: String
    let items: [Schools.Score]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            ForEach(items, id: \.label) { it in
                HStack(spacing: 8) {
                    Text(it.label).font(.caption2).frame(width: 104, alignment: .leading).lineLimit(2).minimumScaleFactor(0.85)
                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Brand.hairline.opacity(0.5))
                            Capsule().fill(Brand.navy).frame(width: geo.size.width * min(100, it.value) / 100)
                            if let st = it.state {
                                Rectangle().fill(Brand.salmon).frame(width: 2, height: 12).offset(x: geo.size.width * min(100, st) / 100 - 1)
                            }
                        }
                    }
                    .frame(height: 8)
                    Text("\(Int(it.value.rounded()))%").font(.caption2.weight(.semibold).monospacedDigit()).frame(width: 34, alignment: .trailing)
                    Text(it.change.map { $0 > 0 ? "+\($0)" : $0 == 0 ? "±0" : "\($0)" } ?? "")
                        .font(.caption2.monospacedDigit()).foregroundStyle((it.change ?? 0) > 0 ? Brand.good : (it.change ?? 0) < 0 ? Brand.salmon : .secondary)
                        .frame(width: 26, alignment: .trailing)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(it.label): \(Int(it.value.rounded())) percent\(it.state.map { ", Florida \(Int($0.rounded()))" } ?? "")")
            }
            HStack(spacing: 12) {
                HStack(spacing: 4) { Capsule().fill(Brand.navy).frame(width: 14, height: 6); Text("This school") }
                HStack(spacing: 4) { Rectangle().fill(Brand.salmon).frame(width: 2, height: 10); Text(stateLabel) }
            }
            .font(.caption2).foregroundStyle(.secondary)
        }
        .padding(12)
        .background(Brand.hairline.opacity(0.2), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
    }
}

/// Grades A to F as one stacked bar, like the site's grade mix.
struct GradeMixBar: View {
    let label: String
    let count: Int
    let mix: [String: Int]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("\(label) · \(Format.number(Double(count))) schools").font(.caption.weight(.semibold))
            GeometryReader { geo in
                HStack(spacing: 1) {
                    ForEach(["A", "B", "C", "D", "F"], id: \.self) { g in
                        let n = mix[g] ?? 0
                        if n > 0 {
                            let share = Double(n) / Double(max(1, count))
                            ZStack {
                                Rectangle().fill(color(g).opacity(0.3))
                                if share >= 0.1 { Text("\(g) \(Int((share * 100).rounded()))%").font(.caption2.weight(.semibold)).foregroundStyle(color(g)) }
                            }
                            .frame(width: geo.size.width * share)
                        }
                    }
                }
            }
            .frame(height: 22)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): " + ["A", "B", "C", "D", "F"].map { "\($0) \(mix[$0] ?? 0)" }.joined(separator: ", "))
    }

    private func color(_ g: String) -> Color {
        switch g { case "A": Brand.good; case "B": Brand.blue; case "C": Brand.amber; default: Brand.salmon }
    }
}
