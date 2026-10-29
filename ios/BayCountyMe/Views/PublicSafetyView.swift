import SwiftUI
import Charts
import BayCountyKit

/// Police, fire and the Sheriff (/public-safety): who covers each town and what it costs, crimes each police agency
/// reported to the FBI since 2016 (rates against Florida), the share solved, cost per resident and officers. Reads the
/// safety-agencies, crime-counts and police-staffing datasets. Counts only: nothing here names a person.
struct PublicSafetyView: View {
    @Environment(AppStore.self) private var store
    @State private var town: String?
    @State private var offense: PublicSafety.Offense = .violent

    private var agencies: [Row] { store.rows["safety-agencies"] ?? [] }
    private var crimes: [Row] { store.rows["crime-counts"] ?? [] }
    private var staff: [Row] { store.rows["police-staffing"] ?? [] }

    var body: some View {
        PageScroll {
            PageHero(kicker: "Living here · Police, fire and the Sheriff", title: "Police, fire and the Sheriff",
                     subtitle: "Who answers when you call 911 in each part of Bay County, what each police and fire department costs, how many crimes each police agency has reported since 2016, and how many officers they have.",
                     symbol: "shield.lefthalf.filled", tone: .blue)
            if agencies.isEmpty {
                if let e = PublicSafety.datasets.lazy.compactMap({ store.errors[$0] }).first {
                    ContentUnavailableView("Couldn't load public safety", systemImage: "wifi.slash", description: Text(e))
                } else {
                    ProgressView().frame(maxWidth: .infinity, minHeight: 160)
                }
            } else {
                kpis
                explainer
                townSection
                trendSection.id("chart")
                solvedSection
                costSection
                staffSection
                CardList {
                    WebRow(title: "Ask for police and fire records", detail: "Each agency's records contact", symbol: "doc.text", url: URL(string: "https://baycounty.me/records"))
                    RowDivider(inset: 50)
                    RouteRow(route: .dataset("crime-counts"), title: "Every crime count", detail: "What each agency reported to the FBI, by year", symbol: "tablecells")
                    RowDivider(inset: 50)
                    RouteRow(route: .dataset("safety-agencies"), title: "Every department", detail: "Budgets and who covers each town", symbol: "building.columns")
                }
                Text("Crime counts and staffing come from the FBI Crime Data Explorer, checked every week. Offenses known to police, not arrests or convictions. No Florida agency reported for 2021, Panama City Beach has not reported since 2020, and from 2025 agencies send monthly incident reports, so 2025 and later are not directly comparable.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            FreshnessNote(key: "crime-counts")
        }
        .navigationTitle("Public safety")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.load(PublicSafety.datasets) }
        .refreshable { for i in PublicSafety.datasets { await store.load(i, force: true) } }
    }

    private var kpis: some View {
        let t = PublicSafety.totals(agencies), fy = PublicSafety.fiscalYear(agencies), h = PublicSafety.headline(crimes)
        return StatGrid {
            KPICard(title: "Police budgets, \(fy)", value: PublicSafety.money(t.police),
                    caption: "Including \(PublicSafety.money(t.contracts)) cities pay the Sheriff by contract", symbol: "shield", tone: .blue)
            KPICard(title: "Fire budgets, \(fy)", value: PublicSafety.money(t.fire), caption: "\(t.fireDepartments) fire departments", symbol: "flame", tone: .salmon)
            KPICard(title: "Sworn officers", value: Format.number(Double(t.officers)), caption: "Latest count each agency gave the FBI", symbol: "person.3", tone: .teal)
            KPICard(title: "Violent crimes, \(h.map { String($0.year) } ?? "")", value: h.map { Format.number(Double($0.violent)) } ?? "—",
                    caption: h.map { h in [h.violentChange.map { "\($0 > 0 ? "+" : "")\($0)% since \(h.firstYear), same agencies" }, "\(Format.number(Double(h.property))) property crimes"].compactMap { $0 }.joined(separator: "; ") },
                    symbol: "chart.bar", tone: .amber)
        }
    }

    private var explainer: some View {
        PageSection(title: "Who covers what", symbol: "info.circle", tone: .blue, caption: "The simple version") {
            VStack(alignment: .leading, spacing: 10) {
                step(1, "The Sheriff covers the whole county.", "The Bay County Sheriff's Office patrols everywhere outside city limits, runs the county jail, and polices Callaway and Mexico Beach, which pay it by contract.")
                step(2, "Five cities have their own police.", "Panama City, Panama City Beach, Lynn Haven, Springfield and Parker run police departments paid from their city budgets.")
                step(3, "Every city has a fire department.", "Bay County Fire Rescue covers the unincorporated areas, paid by a fire fee on tax bills there.")
            }
            .padding(14).card(14)
        }
    }

    private func step(_ n: Int, _ head: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("\(n)").font(.caption.weight(.bold)).foregroundStyle(.white).frame(width: 22, height: 22).background(Brand.navyFill, in: Circle())
            (Text(head).bold() + Text(" " + body)).font(.subheadline).fixedSize(horizontal: false, vertical: true)
        }
    }

    // MARK: Your town

    private var townSection: some View {
        let towns = PublicSafety.towns(agencies)
        let pick = towns.first { $0.id == (town ?? towns.first?.id) } ?? towns[0]
        let crime = PublicSafety.townCrime(pick, crimes: crimes)
        return PageSection(title: "Your town", symbol: "mappin.and.ellipse", tone: .teal, caption: "Pick where you live") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: towns.map { (id: $0.id, label: $0.name) }, selected: pick.id) { town = $0 }
                townCard("Police", pick.police, officers: pick.police.flatMap { PublicSafety.staffing(staff, agency: $0.string("agency_id") ?? "") })
                townCard("Fire", pick.fire, officers: nil)
                VStack(alignment: .leading, spacing: 8) {
                    Text(crime.sheriffCovers ? "CRIMES REPORTED BY \(crime.agencyName.uppercased())" : "CRIMES REPORTED")
                        .font(.caption2.weight(.semibold)).tracking(0.5).foregroundStyle(.secondary)
                    HStack(alignment: .top, spacing: 16) {
                        crimeStat(crime.violent, noun: "violent", year: crime.year)
                        crimeStat(crime.property, noun: "property", year: crime.year)
                    }
                    if let y = crime.year, y < 2024 {
                        Text("\(crime.agencyName.prefix(1).uppercased() + crime.agencyName.dropFirst()) has not sent the FBI a full year since \(y).").font(.caption).foregroundStyle(.secondary)
                    }
                    if crime.sheriffCovers {
                        Text("\(pick.name) is policed by the Sheriff, so its crimes are counted in the Sheriff's numbers for all the areas it patrols.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
                RouteRow(route: .government(pick.id), title: pick.name, detail: "Budget, officials, meetings and votes", symbol: "building.columns")
                    .card(14)
            }
        }
    }

    private func townCard(_ label: String, _ r: Row?, officers: Row?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label.uppercased()).font(.caption2.weight(.semibold)).tracking(0.5).foregroundStyle(.secondary)
            Text(r?.string("agency") ?? "—").font(.headline)
            if let a = r?.string("arrangement") { Text(a).font(.caption).foregroundStyle(.secondary) }
            if let c = r?.number("cost_per_resident") {
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text(Format.money(c.rounded())).font(.title2.weight(.semibold).monospacedDigit())
                    Text("per resident, \(r?.string("budget_fiscal_year") ?? "")").font(.caption).foregroundStyle(.secondary)
                }
            }
            if let o = officers, let y = o.number("year"), y >= 2023, let n = o.number("officers") {
                let per = o.number("population").map { String(format: ", %.1f officers per 1,000 people", 1000 * n / $0) } ?? ""
                Text("\(Format.number(n)) sworn officers and \(Format.number(o.number("civilians") ?? 0)) civilian staff in \(Int(y))\(per).")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(14).frame(maxWidth: .infinity, alignment: .leading).card(14)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder private func crimeStat(_ r: Row?, noun: String, year: Int?) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let r, let rate = r.number("per_1000"), let y = year {
                Text(Format.number(rate)).font(.title2.weight(.semibold).monospacedDigit())
                Text("\(noun) per 1,000 people, \(y)").font(.caption).foregroundStyle(.secondary)
                Text("\(Format.number(r.number("count") ?? 0)) reported\(PublicSafety.versusFlorida(r).map { "; \($0)" } ?? "").")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            } else {
                Text("No full year of \(noun) crime reported to the FBI.").font(.caption).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: Crime over time

    private var trendSection: some View {
        let t = PublicSafety.trends(crimes, offense: offense)
        let top = PublicSafety.trendMax(t) * 1.1
        let years = t.flatMap { $0.points.map(\.year) }
        let lo = years.min() ?? 2016, hi = years.max() ?? 2025
        return PageSection(title: "Crime over time", symbol: "chart.xyaxis.line", tone: .amber, caption: "Crimes reported per 1,000 people, full years only") {
            VStack(alignment: .leading, spacing: 12) {
                ChipRow(chips: PublicSafety.Offense.allCases.map { (id: $0, label: $0.label) }, selected: offense) { offense = $0 }
                HStack(spacing: 14) {
                    HStack(spacing: 4) { Capsule().fill(Brand.navy).frame(width: 14, height: 3); Text("The agency") }
                    HStack(spacing: 4) { Capsule().fill(Color.secondary).frame(width: 14, height: 2); Text("Florida (dashed)") }
                }
                .font(.caption).foregroundStyle(.secondary)
                LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                    ForEach(t, id: \.id) { a in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(a.name).font(.caption.weight(.semibold)).lineLimit(2).minimumScaleFactor(0.85)
                            Text("Latest \(a.points.last.map { String($0.year) } ?? ""): \(a.points.last.map { Format.number($0.rate) } ?? "—")")
                                .font(.caption2).foregroundStyle(.secondary)
                            panel(a.points, lo: lo, hi: hi, top: top)
                        }
                        .padding(10).card(12)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(a.name): " + a.points.map { "\($0.year) \(Format.number($0.rate))" }.joined(separator: ", "))
                    }
                }
                Text("Every panel uses the same scale. Gaps are years the agency sent the FBI nothing. Panama City Beach's rate counts only residents, not the visitors police there also serve.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    /// Breaks a line where years are missing, so a gap shows as a gap.
    private static func segments(_ pts: [PublicSafety.RatePoint]) -> [(seg: Int, p: PublicSafety.RatePoint)] {
        var seg = 0, last: Int?
        return pts.map { p in
            if let l = last, p.year != l + 1 { seg += 1 }
            last = p.year
            return (seg, p)
        }
    }

    private func panel(_ pts: [PublicSafety.RatePoint], lo: Int, hi: Int, top: Double) -> some View {
        let segs = Self.segments(pts)
        return Chart {
            ForEach(pts) { p in
                if let fl = p.florida {
                    LineMark(x: .value("Year", p.year), y: .value("Florida", fl), series: .value("Line", "fl"))
                        .foregroundStyle(Color.secondary).lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3]))
                }
            }
            ForEach(segs, id: \.p.year) { s in
                LineMark(x: .value("Year", s.p.year), y: .value("Rate", s.p.rate), series: .value("Line", "a\(s.seg)"))
                    .foregroundStyle(Brand.navy).lineStyle(StrokeStyle(lineWidth: 2))
                PointMark(x: .value("Year", s.p.year), y: .value("Rate", s.p.rate)).foregroundStyle(Brand.navy).symbolSize(14)
            }
        }
        .chartXScale(domain: lo...hi)
        .chartYScale(domain: 0...top)
        .chartXAxis { AxisMarks(values: [lo, hi]) { v in AxisValueLabel { if let y = v.as(Int.self) { Text(String(y)).font(.system(size: 9)) } } } }
        .chartYAxis { AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { AxisGridLine(); AxisValueLabel().font(.system(size: 9)) } }
        .frame(height: 96)
    }

    // MARK: Solved, cost, staff

    private var solvedSection: some View {
        let list = PublicSafety.solved(crimes, offense: offense)
        return PageSection(title: "Share of crimes solved", symbol: "checkmark.seal", tone: .teal,
                           caption: "\(offense.label): cleared by arrest or otherwise closed, each agency's latest three yearly reports") {
            VStack(alignment: .leading, spacing: 10) {
                ForEach(list, id: \.name) { b in
                    bar(label: b.name, sub: b.span, share: b.share, value: "\(Int((b.share * 100).rounded()))%", color: Brand.navy)
                        .accessibilityLabel("\(b.name): \(b.cleared) of \(b.count) cleared, \(b.span)")
                }
                Text("Uses the switch above. Agencies with fewer than 20 crimes in those years are left out.").font(.footnote).foregroundStyle(.secondary)
            }
            .padding(14).card(14)
        }
    }

    private var costSection: some View {
        let list = PublicSafety.perResident(agencies)
        let top = list.flatMap { [$0.police ?? 0, $0.fire ?? 0] }.max() ?? 1
        return PageSection(title: "What police and fire cost per resident", symbol: "dollarsign.circle", tone: .amber, caption: "\(PublicSafety.fiscalYear(agencies)) budgets") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 14) {
                    HStack(spacing: 4) { RoundedRectangle(cornerRadius: 2).fill(Brand.navy).frame(width: 10, height: 10); Text("Police") }
                    HStack(spacing: 4) { RoundedRectangle(cornerRadius: 2).fill(Brand.salmon).frame(width: 10, height: 10); Text("Fire") }
                }
                .font(.caption).foregroundStyle(.secondary)
                ForEach(list, id: \.name) { r in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(r.name).font(.caption.weight(.semibold))
                        if let p = r.police { bar(label: nil, sub: nil, share: p / top, value: Format.money(p.rounded()), color: Brand.navy) }
                        if let f = r.fire { bar(label: nil, sub: nil, share: f / top, value: Format.money(f.rounded()), color: Brand.salmon) }
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(r.name): police \(r.police.map { Format.money($0.rounded()) } ?? "none"), fire \(r.fire.map { Format.money($0.rounded()) } ?? "none") per resident")
                }
                Text("The budget divided by the people it serves: each city's residents, the whole county for the Sheriff (it runs the jail for everyone), and the unincorporated county for Bay County Fire Rescue. Beach towns serve many visitors who are not counted as residents.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .padding(14).card(14)
        }
    }

    private func bar(label: String?, sub: String?, share: Double, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            if let label {
                HStack(spacing: 4) {
                    Text(label).font(.caption.weight(.semibold))
                    if let sub { Text(sub).font(.caption2).foregroundStyle(.secondary) }
                }
            }
            HStack(spacing: 8) {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 4).fill(Brand.sunken)
                        RoundedRectangle(cornerRadius: 4).fill(color).frame(width: max(2, geo.size.width * min(1, share)))
                    }
                }
                .frame(height: 12)
                Text(value).font(.caption.weight(.semibold).monospacedDigit()).frame(width: 52, alignment: .trailing)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var staffSection: some View {
        let list = PublicSafety.staffingSummary(staff)
        return PageSection(title: "Police officers and staff", symbol: "person.3", tone: .blue, caption: "Sworn officers on October 31 each year, with civilian staff") {
            CardList {
                ForEach(list, id: \.id) { s in
                    TextRow(title: s.name, detail: "\(Format.number(Double(s.civilians))) civilian staff, \(s.year) · \(Format.number(Double(s.firstOfficers))) officers in \(s.firstYear)",
                            value: "\(Format.number(Double(s.officers)))")
                    if s.id != list.last?.id { RowDivider() }
                }
            }
        }
    }
}
