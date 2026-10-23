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

/// Places a row can lead to. Every tab's NavigationStack resolves these the same way.
enum Route: Hashable {
    case dataset(String, filters: [String: String] = [:])
    case record(String, rowID: Int)
    case government(String)
    case meeting(String)
    case cra
}

extension View {
    func withRoutes() -> some View {
        navigationDestination(for: Route.self) { route in
            switch route {
            case .dataset(let id, let filters): DatasetView(datasetID: id, preset: filters)
            case .record(let id, let rowID): RecordDetailView(datasetID: id, rowID: rowID)
            case .government(let govID): GovernmentDetailView(govID: govID)
            case .meeting(let id): MeetingDetailView(meetingID: id)
            case .cra: CRAView()
            }
        }
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
