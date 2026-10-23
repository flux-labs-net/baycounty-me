import SwiftUI
import BayCountyKit

/// The Accountability console: public projects followed from first budget to close-out, with questions raised
/// by published rules. Mirrors /public-money/accountability. A flag is a question, not a finding.
struct AccountabilityView: View {
    @Environment(AppStore.self) private var store
    @State private var phase: AccountabilityConsole.Phase?
    @State private var onlyQuestions = false
    @State private var rule: String?
    @State private var gov: String?
    @State private var sort: Sort = .recent
    @State private var query = ""

    enum Sort: String, CaseIterable, Identifiable {
        case recent = "Most recent", growth = "Most cost growth", money = "Largest"
        var id: String { rawValue }
    }

    var body: some View {
        Group {
            if let c = store.accountability { list(c) } else {
                AppDataPending(file: "accountability.json", title: "Couldn't load the console") { await store.loadAccountability(force: true) }
            }
        }
        .navigationTitle("Accountability")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $query, prompt: "Find a project")
        .toolbar { toolbar }
        .task { await store.loadAccountability() }
        .refreshable { await store.loadAccountability(force: true) }
    }

    private func filtered(_ c: AccountabilityConsole) -> [AccountabilityConsole.Project] {
        let q = query.lowercased().trimmingCharacters(in: .whitespaces)
        let rows = c.projects.filter { p in
            (phase == nil || AccountabilityConsole.Phase.of(p.status) == phase)
                && (!onlyQuestions || !p.flags.isEmpty)
                && (rule == nil || p.flags.contains { $0.r == rule })
                && (gov == nil || p.gk == gov)
                && (q.isEmpty || p.n.lowercased().contains(q) || (p.agency ?? "").lowercased().contains(q) || (p.vendor ?? "").lowercased().contains(q))
        }
        switch sort {
        case .recent: return rows.sorted { ($0.last ?? "") > ($1.last ?? "") }
        case .growth: return rows.sorted { ($0.growth ?? -.infinity) > ($1.growth ?? -.infinity) }
        case .money: return rows.sorted { ($0.money ?? 0) > ($1.money ?? 0) }
        }
    }

    private func list(_ c: AccountabilityConsole) -> some View {
        let rows = filtered(c)
        let maxMoney = rows.compactMap(\.money).max() ?? 0
        let ruleCounts = c.rules.compactMap { r -> CompareBars.Item? in
            let n = c.projects.filter { $0.flags.contains { $0.r == r.id } }.count
            return n > 0 ? .init(id: r.id, label: r.title, value: Double(n)) : nil
        }.sorted { $0.value > $1.value }
        return List {
            Section {
                PageIntro(path: "/public-money/accountability")
                if query.isEmpty {
                    StatStrip(tiles: [
                        .init(title: "Projects", value: "\(c.stats?.projects ?? c.projects.count)"),
                        .init(title: "With questions", value: "\(c.stats?.flagged ?? 0)"),
                        .init(title: "Records missing", value: "\(c.stats?.gaps ?? 0)"),
                    ])
                    Label("A flag is a question for the agency, not a finding of wrongdoing. Each one names the published rule that raised it.",
                          systemImage: "questionmark.bubble")
                        .font(.footnote).foregroundStyle(.secondary)
                    if !ruleCounts.isEmpty {
                        CompareBars(title: "Questions by rule", caption: "Projects flagged by each rule. Tap one to see them.",
                                    items: ruleCounts, highlight: rule, format: { "\(Int($0))" },
                                    onTap: { id in rule = rule == id ? nil : id }, labelsAbove: true)
                    }
                }
                Picker("Stage", selection: $phase) {
                    Text("All").tag(AccountabilityConsole.Phase?.none)
                    ForEach(AccountabilityConsole.Phase.allCases) { Text($0.rawValue).tag(Optional($0)) }
                }
                .pickerStyle(.segmented)
                activeFilters(c, count: rows.count)
            }
            .listRowSeparator(.hidden)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))

            Section {
                ForEach(rows) { p in
                    NavigationLink(value: Route.accountabilityProject(p.id)) { ProjectRow(project: p, maxMoney: maxMoney) }
                }
            }
            if let about = c.about {
                Section { } footer: { Text(about) }
            }
        }
        .listStyle(.insetGrouped)
        .overlay { if rows.isEmpty { ContentUnavailableView.search(text: query) } }
    }

    @ViewBuilder private func activeFilters(_ c: AccountabilityConsole, count: Int) -> some View {
        HStack(spacing: 6) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    if let r = rule { FilterChip(text: c.rule(r)?.title ?? r) { rule = nil } }
                    if let g = gov { FilterChip(text: Governments.names[g] ?? g) { gov = nil } }
                    if onlyQuestions { FilterChip(text: "With questions") { onlyQuestions = false } }
                }
            }
            Spacer(minLength: 4)
            Text("\(count) of \(c.projects.count)").font(.footnote).foregroundStyle(.secondary).monospacedDigit()
        }
    }

    @ToolbarContentBuilder private var toolbar: some ToolbarContent {
        ToolbarItem(placement: .topBarTrailing) {
            Menu {
                Picker("Sort", selection: $sort) { ForEach(Sort.allCases) { Text($0.rawValue).tag($0) } }
                Toggle("Only projects with questions", isOn: $onlyQuestions)
                Picker("Government", selection: $gov) {
                    Text("Every government").tag(String?.none)
                    ForEach(Governments.order, id: \.self) { Text(Governments.names[$0] ?? $0).tag(String?.some($0)) }
                }
                .pickerStyle(.menu)
                Divider()
                Button("Open on BayCounty.me") { store.openSite("/public-money/accountability") }
            } label: {
                Image(systemName: rule == nil && gov == nil && !onlyQuestions ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
            }
            .accessibilityLabel("Sort and filter")
        }
    }
}

/// One project: name and stage, first and latest cost with the growth between them, and its questions.
struct ProjectRow: View {
    let project: AccountabilityConsole.Project
    let maxMoney: Double

    var body: some View {
        let p = project
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(p.n).font(.subheadline.weight(.semibold)).lineLimit(2)
                Spacer(minLength: 4)
                if let m = p.money { Text(Format.compactMoney(m)).font(.subheadline.weight(.semibold).monospacedDigit()) }
            }
            if let m = p.money, maxMoney > 0 { MagnitudeBar(fraction: m / maxMoney) }
            HStack(spacing: 6) {
                Badge(text: p.stageLabel, color: AccountabilityStyle.stage(p.status))
                Text(p.g ?? "").font(.caption).foregroundStyle(.secondary).lineLimit(1)
                Spacer(minLength: 0)
                if let g = p.growth { GrowthPill(growth: g) }
                if !p.flags.isEmpty { FlagCount(flags: p.flags) }
            }
        }
        .padding(.vertical, 3)
    }
}

/// Cost growth from the first figure to the latest, colored when it passes the 10% and 25% rule lines.
struct GrowthPill: View {
    let growth: Double

    var body: some View {
        let color = growth > 25 ? Brand.salmon : growth > 10 ? Brand.amber : Color.secondary
        Text((growth >= 0 ? "+" : "") + Format.number((growth * 10).rounded() / 10) + "%")
            .font(.caption.weight(.semibold).monospacedDigit())
            .padding(.horizontal, 7).padding(.vertical, 2)
            .foregroundStyle(color)
            .background(color.opacity(0.12), in: Capsule())
            .accessibilityLabel("Cost changed \(Format.number(growth)) percent")
    }
}

/// How many questions a project has, with its worst severity as the color.
struct FlagCount: View {
    let flags: [AccountabilityConsole.Flag]

    var body: some View {
        let worst = flags.contains { $0.sev == "high" } ? "high" : flags.contains { $0.sev == "warn" } ? "warn" : "info"
        Label("\(flags.count)", systemImage: "questionmark.circle.fill")
            .font(.caption.weight(.semibold))
            .foregroundStyle(AccountabilityStyle.severity(worst))
            .accessibilityLabel("\(flags.count) \(flags.count == 1 ? "question" : "questions")")
    }
}

enum AccountabilityStyle {
    static func severity(_ s: String?) -> Color {
        switch s { case "high": Brand.salmon; case "warn": Brand.amber; default: Brand.blue }
    }
    static func severityLabel(_ s: String?) -> String {
        switch s { case "high": "High"; case "warn": "Question"; default: "Note" }
    }
    static func stage(_ s: String?) -> Color {
        switch AccountabilityConsole.Phase.of(s) {
        case .done: Brand.good
        case .stopped: .secondary
        case .active: s == "delayed" ? Brand.amber : Brand.blue
        }
    }
    static func kind(_ k: String) -> Color {
        switch k {
        case "budget", "estimate": .secondary
        case "award", "approval", "vote": Brand.navy
        case "change": Brand.amber
        case "payment", "spent": Brand.good
        case "complete": Brand.good
        default: Brand.blue
        }
    }
    /// "2021-03-15" → Mar 15, 2021; "2021-03" → Mar 2021; "FY2015" stays.
    static func date(_ s: String?) -> String {
        guard let s, !s.isEmpty else { return "" }
        if s.count >= 10, let d = Dates.parse(String(s.prefix(10))) { return Dates.display(d, hasTime: false) }
        if s.count == 7, let m = Int(s.suffix(2)), (1...12).contains(m) {
            return String(Calendar.current.shortMonthSymbols[m - 1]) + " " + s.prefix(4)
        }
        return s
    }
}

struct AccountabilityProjectView: View {
    @Environment(AppStore.self) private var store
    let projectID: String

    var body: some View {
        Group {
            if let c = store.accountability, let p = c.projects.first(where: { $0.id == projectID }) {
                detail(p, console: c)
            } else if store.accountability == nil {
                AppDataPending(file: "accountability.json", title: "Couldn't load the console") { await store.loadAccountability(force: true) }
            } else {
                ContentUnavailableView("Project not found", systemImage: "checklist")
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadAccountability() }
    }

    private func detail(_ p: AccountabilityConsole.Project, console c: AccountabilityConsole) -> some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 6) {
                    Text(p.n).font(.title3.weight(.semibold))
                    Text([p.g, p.agency].compactMap { $0 }.joined(separator: " · ")).font(.subheadline).foregroundStyle(.secondary)
                    HStack(spacing: 6) {
                        Badge(text: p.stageLabel, color: AccountabilityStyle.stage(p.status))
                        Badge(text: AccountabilityConsole.source(p.src), color: .secondary)
                        if let d = p.late_days, d > 0 { Badge(text: "About \(Int(d)) days late", color: Brand.amber) }
                    }
                }
                .padding(.vertical, 4)
                if let w = p.what { Text(w).font(.callout) }
                if let w = p.`where` { LabeledContent("Where") { Text(w).multilineTextAlignment(.trailing) } }
                if let f = p.funding { LabeledContent("Paid for by") { Text(f).multilineTextAlignment(.trailing) } }
            }

            if p.base?.a != nil || p.latest?.a != nil {
                Section("Cost") { costCard(p) }
            }

            if !p.flags.isEmpty {
                Section {
                    ForEach(p.flags) { f in FlagRow(flag: f, rule: c.rule(f.r)) }
                } header: {
                    Text("Questions raised")
                } footer: {
                    Text("Raised by the published rules. A question, not a finding of wrongdoing.")
                }
            }

            if !p.gaps.isEmpty {
                Section {
                    ForEach(p.gaps) { g in Label(g.q, systemImage: "doc.questionmark").font(.callout) }
                    WebLink(title: "Request a public record", symbol: "envelope", url: URL(string: "https://baycounty.me/records-request"))
                } header: {
                    Text("Records still missing")
                }
            }

            Section("Agency reply") {
                Label(AccountabilityConsole.reply(p.reply?.status),
                      systemImage: p.reply?.status == "replied" ? "checkmark.bubble" : "bubble.left")
                if let t = p.reply?.text { Text(t).font(.callout) }
                if let u = p.reply?.u.flatMap(URL.init(string:)) { WebLink(title: "The agency's reply", symbol: "doc.text", url: u) }
            }

            Section("Timeline") {
                ForEach(Array(p.timeline.enumerated()), id: \.offset) { i, e in
                    TimelineRow(event: e, isLast: i == p.timeline.count - 1)
                }
            }
            .listRowSeparator(.hidden)

            Section {
                WebLink(title: "This project on BayCounty.me", url: URL(string: "https://baycounty.me/public-money/accountability#\(p.id)"))
            }
        }
        .navigationTitle(p.n)
    }

    /// First and latest firm figures as two bars, with the growth between them.
    private func costCard(_ p: AccountabilityConsole.Project) -> some View {
        let first = p.base?.a ?? 0, latest = p.latest?.a ?? 0
        let maxV = max(first, latest, 1)
        return VStack(alignment: .leading, spacing: 10) {
            if let a = p.base?.a { costLine("First", a, p.base?.t, fraction: a / maxV, color: Brand.blue) }
            if let a = p.latest?.a { costLine("Latest", a, p.latest?.t, fraction: a / maxV, color: Brand.navy) }
            if let g = p.growth ?? (first > 0 && latest > 0 ? (latest - first) / first * 100 : nil) {
                HStack(spacing: 6) {
                    GrowthPill(growth: g)
                    // Only repeat the rule when the site actually raised it; approximate figures don't trigger it.
                    Text(p.flags.contains { $0.r == "growth" } ? "Past the 10% that raises a question" : "Change from the first figure")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            if let m = p.money, m != latest, m != first {
                Text("Money followed on this project: \(Format.money(m))").font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 4)
    }

    private func costLine(_ label: String, _ amount: Double, _ what: String?, fraction: Double, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(label).font(.subheadline.weight(.semibold))
                Spacer()
                Text(Format.money(amount)).font(.subheadline.weight(.semibold).monospacedDigit())
            }
            GeometryReader { g in
                Capsule().fill(color).frame(width: max(6, g.size.width * fraction))
            }
            .frame(height: 10)
            if let what { Text(what.capitalizingFirst).font(.caption).foregroundStyle(.secondary) }
        }
    }
}

/// One question: the rule's title with a severity tag, the note, and the rule's own explanation on tap.
struct FlagRow: View {
    let flag: AccountabilityConsole.Flag
    let rule: AccountabilityConsole.Rule?
    @State private var open = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Circle().fill(AccountabilityStyle.severity(flag.sev)).frame(width: 9, height: 9)
                Text(rule?.title ?? flag.r).font(.subheadline.weight(.semibold))
                Spacer()
                Text(AccountabilityStyle.severityLabel(flag.sev)).font(.caption.weight(.medium)).foregroundStyle(.secondary)
            }
            Text(flag.note).font(.callout)
            if let rule {
                DisclosureGroup(isExpanded: $open) {
                    VStack(alignment: .leading, spacing: 6) {
                        if let w = rule.when { ruleText("When it's raised", w) }
                        if let m = rule.means { ruleText("What it means", m) }
                        if let n = rule.not { ruleText("What it doesn't mean", n) }
                    }
                    .padding(.top, 4)
                } label: {
                    Text("How this rule works").font(.caption.weight(.semibold))
                }
            }
        }
        .padding(.vertical, 3)
    }

    private func ruleText(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(.caption.weight(.semibold))
            Text(body).font(.caption).foregroundStyle(.secondary)
        }
    }
}

/// A timeline step: a colored dot on a line, the date and kind, the amount, what happened and who was paid.
struct TimelineRow: View {
    @Environment(AppStore.self) private var store
    let event: AccountabilityConsole.Event
    let isLast: Bool

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle().fill(AccountabilityStyle.kind(event.k)).frame(width: 12, height: 12).padding(.top, 3)
                if !isLast { Rectangle().fill(Brand.sunken).frame(width: 2).frame(maxHeight: .infinity) }
            }
            .frame(width: 12)
            .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(AccountabilityConsole.kind(event.k)).font(.caption.weight(.semibold)).foregroundStyle(AccountabilityStyle.kind(event.k))
                    Text(AccountabilityStyle.date(event.d)).font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    if let a = event.a {
                        Text((event.approx == true ? "about " : "") + Format.money(a)).font(.subheadline.weight(.semibold).monospacedDigit())
                    }
                }
                Text(event.t).font(.callout)
                if let payee = event.payee {
                    if let vid = event.vid {
                        NavigationLink(value: Route.vendor(vid)) { Label(payee, systemImage: "building").font(.caption) }
                    } else {
                        Label(payee, systemImage: "building").font(.caption).foregroundStyle(.secondary)
                    }
                }
                if let u = event.url {
                    Button { store.open(u) } label: { Label("Source", systemImage: "doc.text.magnifyingglass").font(.caption) }
                        .buttonStyle(.borderless)
                }
            }
            .padding(.bottom, 10)
        }
    }
}
