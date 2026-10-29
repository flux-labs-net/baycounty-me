import SwiftUI
import UIKit
import SafariServices
import MapKit
import BayCountyKit

/// Colors from the site's tokens (site/tokens.css), with dark-mode variants in the asset catalog.
enum Brand {
    static let navy = Color("Navy")
    static let blue = Color("Blue")
    static let salmon = Color("Salmon")
    static let amber = Color("Amber")
    static let good = Color("Good")
    static let canvas = Color("Canvas")
    static let surface = Color("Surface")
    static let sunken = Color("Sunken")
    /// Solid backgrounds that carry white text (selected chips, buttons, banners). Darker than navy in dark mode.
    static let navyFill = Color("NavyFill")
    static let salmonFill = Color("SalmonFill")
    /// Card edges, so cards stay visible on the dark canvas.
    static let hairline = Color("Hairline")

    /// Matches the CRA Spending page: Spent green, Committed blue, Budgeted amber, Proposed salmon.
    static func status(_ s: String) -> Color {
        switch s {
        case "Spent": good
        case "Committed": blue
        case "Budgeted": amber
        case "Proposed": salmon
        default: .secondary
        }
    }
}

/// Places a row can lead to. Every tab's NavigationStack resolves these the same way, on the same canvas.
enum Route: Hashable {
    case dataset(String, filters: [String: String] = [:])
    case record(String, rowID: Int)
    case government(String)
    case meeting(String)
    case cra
    case myAddress
    case address(AddressMatch)
    case taxCalculator(districtID: String? = nil, value: Double? = nil, homestead: Bool? = nil)
    case amendment3(districtID: String? = nil, value: Double? = nil, homestead: Bool? = nil)
    case glossary
    case vendors
    case vendor(String)
    case people
    case person(String)
    case donorContracts
    case moneyMap
    case updates
    case about
    case explore
    case accountability
    case accountabilityProject(String)
    case search
    case budgetCompare(govID: String? = nil)
    case craIncrement
    case chambers
    case events
    case beaches
    case parks
    case schools
    case emergency
    case hurricanePrep
    case utilities(AddressMatch? = nil)
    case volunteer
    case military
    case restaurants
    case restaurant(String)
    case myHome
    case meetings

    /// The screen's name in the anonymous usage counts (AppUsage): the case name, plus the list or government for
    /// those two, and the list a record came from. Never a person, address, search or record id.
    var usageName: String {
        switch self {
        case .dataset(let id, _): return "dataset/" + id
        case .record(let id, _): return "record/" + id
        case .government(let g): return "government/" + g
        default: return String(String(describing: self).prefix { $0 != "(" }).lowercased()
        }
    }
}

/// Counts a screen view for the anonymous usage counts when the screen appears.
private struct TrackScreen: ViewModifier {
    @Environment(AppStore.self) private var store
    let name: String
    func body(content: Content) -> some View { content.onAppear { store.usage.viewed(name) } }
}

extension View {
    func trackScreen(_ name: String) -> some View { modifier(TrackScreen(name: name)) }

    func withRoutes() -> some View {
        navigationDestination(for: Route.self) { route in
            Group {
                switch route {
                case .dataset(let id, let filters): DatasetView(datasetID: id, preset: filters)
                case .record(let id, let rowID): RecordDetailView(datasetID: id, rowID: rowID)
                case .government(let govID): GovernmentDetailView(govID: govID)
                case .meeting(let id): MeetingDetailView(meetingID: id)
                case .cra: CRAView()
                case .myAddress: MyAddressView()
                case .address(let m): AddressReportView(match: m)
                case .taxCalculator(let d, let v, let h): TaxCalculatorView(districtID: d, value: v, homestead: h)
                case .amendment3(let d, let v, let h): Amendment3View(districtID: d, value: v, homestead: h)
                case .glossary: GlossaryView()
                case .vendors: VendorsView()
                case .vendor(let id): VendorDetailView(vendorID: id)
                case .people: PeopleView()
                case .person(let id): PersonDetailView(personID: id)
                case .donorContracts: DonorContractsView()
                case .moneyMap: MoneyMapView()
                case .updates: UpdatesView()
                case .about: AboutView()
                case .explore: ExploreView()
                case .accountability: AccountabilityView()
                case .accountabilityProject(let id): AccountabilityProjectView(projectID: id)
                case .search: SearchView()
                case .budgetCompare(let g): BudgetCompareView(govID: g)
                case .craIncrement: CRAIncrementView()
                case .chambers: ChambersView()
                case .events: EventsView()
                case .beaches: BeachesView()
                case .parks: ParksView()
                case .schools: SchoolsView()
                case .meetings: MeetingsList()
                case .emergency: EmergencyView()
                case .hurricanePrep: HurricanePrepView()
                case .utilities(let m): UtilitiesView(match: m)
                case .volunteer: VolunteerView()
                case .military: MilitaryView()
                case .restaurants: RestaurantsView()
                case .restaurant(let lic): RestaurantDetailView(license: lic)
                case .myHome: MyHomeView()
                }
            }
            .pageBackground()
            .trackScreen(route.usageName)
        }
    }
}

/// The website page's lead paragraph and "how it works" explainer, with its glossary terms as chips.
struct PageIntro: View {
    @Environment(AppStore.self) private var store
    let path: String?
    @State private var expanded = false

    var body: some View {
        if let page = store.page(path), page.lede != nil || page.explainer != nil {
            VStack(alignment: .leading, spacing: 8) {
                if let lede = page.lede { Text(lede).font(.subheadline) }
                if let ex = page.explainer {
                    DisclosureGroup(isExpanded: $expanded) {
                        VStack(alignment: .leading, spacing: 6) {
                            ForEach(ex.paragraphs, id: \.self) { Text($0).font(.footnote).foregroundStyle(.secondary) }
                        }
                        .padding(.top, 4)
                    } label: {
                        Text(ex.heading).font(.footnote.weight(.semibold))
                    }
                }
                TermChips(text: ([page.lede ?? ""] + (page.explainer?.paragraphs ?? [])).joined(separator: " "))
            }
            .padding(.vertical, 4)
        }
    }
}

/// Glossary terms that appear in some text, as tappable chips that open the plain-English explanation.
struct TermChips: View {
    @Environment(AppStore.self) private var store
    let text: String
    var limit = 6

    var body: some View {
        let terms = Array((store.glossary?.terms(in: text) ?? []).prefix(limit))
        if !terms.isEmpty {
            FlowLayout(spacing: 6) {
                Image(systemName: "character.book.closed").font(.caption).foregroundStyle(.secondary)
                    .accessibilityHidden(true)
                ForEach(terms) { t in
                    Button { store.presentedTerm = t } label: {
                        Text(t.matchWords.last ?? t.term)
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 10).padding(.vertical, 5)
                            .foregroundStyle(Brand.navy)
                            .background(Brand.navy.opacity(0.1), in: Capsule())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Explain \(t.term)")
                }
            }
        }
    }
}

/// A glossary term in a sheet: the simple version, then the detail and an example.
struct TermSheet: View {
    let term: Glossary.Term
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section { Text(term.simple).font(.body) }
                if let more = term.more { Section("More detail") { Text(more).font(.callout) } }
                if let ex = term.example { Section("Example") { Text(ex).font(.callout) } }
            }
            .navigationTitle(term.term)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
        .presentationDetents([.medium, .large])
    }
}

/// A horizontal bar split into colored parts (the site's stack bar).
struct StackBar: View {
    let parts: [(label: String, value: Double, color: Color)]

    var body: some View {
        let total = max(parts.reduce(0) { $0 + $1.value }, 1)
        GeometryReader { geo in
            HStack(spacing: 2) {
                ForEach(Array(parts.enumerated()), id: \.offset) { _, p in
                    Rectangle().fill(p.color).frame(width: max(2, geo.size.width * p.value / total - 2))
                }
            }
        }
        .frame(height: 14)
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .accessibilityElement()
        .accessibilityLabel(parts.map { "\($0.label) \(Format.money($0.value))" }.joined(separator: ", "))
    }
}

/// Group colors, matching the website's --s1...--s5 series.
enum TaxColors {
    static func color(_ group: String) -> Color {
        switch group {
        case "school": Brand.navy
        case "county": Brand.blue
        case "city": Brand.salmon
        case "countysvc": Brand.amber
        default: Brand.good
        }
    }
}

/// A labelled amount row with a colored dot.
struct LegendRow: View {
    let color: Color
    let label: String
    let value: String
    var detail: String? = nil

    var body: some View {
        HStack {
            Circle().fill(color).frame(width: 9, height: 9).accessibilityHidden(true)
            Text(label)
            Spacer()
            if let detail { Text(detail).font(.caption).foregroundStyle(.secondary) }
            Text(value).monospacedDigit()
        }
        .font(.subheadline)
    }
}

struct Badge: View {
    let text: String
    var color: Color = .secondary

    var body: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .foregroundStyle(color)
            .background(color.opacity(0.14), in: Capsule())
    }
}

struct StatTile: View {
    let title: String
    let value: String
    var caption: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            Text(value).font(.title3.weight(.semibold).monospacedDigit()).minimumScaleFactor(0.7).lineLimit(1)
            if let caption { Text(caption).font(.caption2).foregroundStyle(.secondary).lineLimit(2) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Brand.sunken, in: RoundedRectangle(cornerRadius: 10))
    }
}

/// A link that opens in the in-app browser.
struct WebLink: View {
    @Environment(AppStore.self) private var store
    let title: String
    var symbol: String = "safari"
    let url: URL?

    var body: some View {
        if let url {
            Button { store.open(url) } label: {
                Label(title, systemImage: symbol)
            }
        }
    }
}

struct SafariView: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> SFSafariViewController {
        let vc = SFSafariViewController(url: url)
        vc.preferredControlTintColor = UIColor(named: "Navy")
        return vc
    }
    func updateUIViewController(_ vc: SFSafariViewController, context: Context) {}
}

/// A page shown in the in-app browser.
struct PresentedPage: Identifiable {
    let url: URL
    var id: String { url.absoluteString }
}

struct PoweredByFlux: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        Button { store.open(URL(string: "https://fluxlabs.net/")) } label: {
            HStack(spacing: 8) {
                Text("Powered by").font(.footnote).foregroundStyle(.secondary)
                Image("FluxLogo").resizable().scaledToFit().frame(height: 18)
                    .accessibilityLabel("Flux Labs")
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
        }
        .buttonStyle(.plain)
    }
}

/// "Showing saved data" note when the device is offline.
struct FreshnessNote: View {
    @Environment(AppStore.self) private var store
    var key: String? = nil

    var body: some View {
        let f = key.flatMap { store.freshness[$0] }
        if (key == nil && store.isShowingSavedData) || (f != nil && f != .live) {
            Label(f == .bundled ? "Offline. Showing data that came with the app." : "Offline. Showing your last saved copy.",
                  systemImage: "wifi.slash")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

/// One record in a list, laid out from its dataset's spec.
struct RecordRow: View {
    let spec: DatasetSpec
    let row: Row

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(spec.title(row)).font(.subheadline.weight(.medium)).lineLimit(2)
                Spacer(minLength: 4)
                if let a = spec.amount(row) {
                    Text(Format.compactMoney(a)).font(.subheadline.monospacedDigit()).foregroundStyle(.primary)
                }
            }
            if let detail = spec.detail(row), detail != spec.title(row) {
                Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            HStack(spacing: 6) {
                let sub = spec.subtitle(row)
                if !sub.isEmpty { Text(sub).lineLimit(1) }
                Spacer(minLength: 0)
                if let b = spec.badge(row) { Badge(text: b, color: Brand.status(b)) }
                if row.bool("count") == false, row["status"] != nil {
                    Image(systemName: "minus.circle").accessibilityLabel("Not in totals")
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}

/// Map of rows that carry lat/lng (CRA spending, sales tax projects).
struct RecordsMap: View {
    let datasetID: String
    let rows: [Row]
    var onSelect: ((Row) -> Void)? = nil

    private var located: [Row] {
        Array(rows.filter { $0.number("lat") != nil && $0.number("lng") != nil }.prefix(600))
    }

    var body: some View {
        let spec = DatasetSpec.for(datasetID)
        Map(initialPosition: .region(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 30.22, longitude: -85.68),
            span: MKCoordinateSpan(latitudeDelta: 0.45, longitudeDelta: 0.55)))) {
            ForEach(located) { row in
                Annotation(spec.title(row), coordinate: CLLocationCoordinate2D(latitude: row.number("lat")!, longitude: row.number("lng")!)) {
                    Button { onSelect?(row) } label: {
                        Circle()
                            .fill(Brand.status(row.string("status") ?? "").opacity(0.9))
                            .frame(width: 14, height: 14)
                            .overlay(Circle().stroke(.white, lineWidth: 1.5))
                    }
                    .buttonStyle(.plain)
                }
                .annotationTitles(.hidden)
            }
        }
        .mapStyle(.standard(pointsOfInterest: .excludingAll))
    }
}

/// Shown while one of the app's /data/app files loads, or with a retry button when it couldn't be loaded.
struct AppDataPending: View {
    @Environment(AppStore.self) private var store
    let file: String
    var title = "Couldn't load this page"
    let retry: () async -> Void

    var body: some View {
        if let e = store.appError(file) {
            ContentUnavailableView {
                Label(title, systemImage: "wifi.slash")
            } description: {
                Text(e)
            } actions: {
                Button("Try again") { Task { await retry() } }.buttonStyle(.bordered)
            }
        } else {
            ProgressView().frame(maxWidth: .infinity)
        }
    }
}

/// The app icon's mark: Bay County's outline with a salmon dot for Panama City. Navy in light mode, light blue in dark.
struct BayMark: View {
    var body: some View {
        ZStack {
            BayOutline().fill(Brand.navy)
            GeometryReader { g in
                // Dot centre and size as fractions of the outline's box (traced from icon-1024.png).
                let d = g.size.width * 0.16
                Circle().fill(Brand.salmon)
                    .frame(width: d, height: d)
                    .position(x: g.size.width * 0.548, y: g.size.height * 0.633)
            }
        }
        .aspectRatio(563.0 / 685.0, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// Bay County's outline, traced from the app icon and scaled to fill its frame.
struct BayOutline: Shape {
    private static let traced: [(CGFloat, CGFloat)] = [
        (698, 170), (793, 170), (790, 855), (775, 838), (760, 828), (720, 815), (700, 815), (680, 805),
        (650, 780), (612, 735), (605, 715), (590, 712), (545, 690), (505, 670), (470, 645), (435, 610),
        (400, 585), (350, 555), (300, 525), (230, 488), (233, 358), (360, 303), (696, 308),
    ]
    private static let points: [CGPoint] = traced.map { CGPoint(x: ($0.0 - 230) / 563, y: ($0.1 - 170) / 685) }

    func path(in rect: CGRect) -> Path {
        Path { p in
            p.addLines(Self.points.map { CGPoint(x: rect.minX + $0.x * rect.width, y: rect.minY + $0.y * rect.height) })
            p.closeSubpath()
        }
    }
}

// MARK: - Copy and Share

/// Copy and Share for one record or page (RecordShare in the kit, the same text as the website's Share button):
/// copy the text summary, copy the link, or open the share sheet with the link and the summary.
struct ShareMenu: View {
    let text: String
    let url: URL?

    var body: some View {
        Menu {
            ShareActions(text: text, url: url)
        } label: {
            Image(systemName: "square.and.arrow.up")
        }
        .accessibilityLabel("Share or copy")
    }
}

/// The three actions, for a toolbar menu or a row's long-press menu.
struct ShareActions: View {
    let text: String
    let url: URL?

    var body: some View {
        Button {
            UIPasteboard.general.string = text
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } label: { Label("Copy text", systemImage: "doc.on.doc") }
        if let url {
            Button {
                UIPasteboard.general.url = url
                UINotificationFeedbackGenerator().notificationOccurred(.success)
            } label: { Label("Copy link", systemImage: "link") }
            // the link goes as the item so Messages and others draw its preview card; the summary rides along as the message
            ShareLink(item: url, message: Text(text.replacingOccurrences(of: "\n" + url.absoluteString, with: ""))) {
                Label("Share…", systemImage: "square.and.arrow.up")
            }
        } else {
            ShareLink(item: text) { Label("Share…", systemImage: "square.and.arrow.up") }
        }
    }
}

extension View {
    /// Long-press a list row for Copy text, Copy link and Share.
    func shareContextMenu(text: @autoclosure @escaping () -> String, url: @autoclosure @escaping () -> URL?) -> some View {
        contextMenu { ShareActions(text: text(), url: url()) }
    }
}
