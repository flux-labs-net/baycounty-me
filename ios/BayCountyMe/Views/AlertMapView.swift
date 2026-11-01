import SwiftUI
import MapKit
import BayCountyKit

/// The map government staff drew on an alert (where a boil-water notice or a closure applies), or the stretch of a
/// road closure placed from the streets it names: circles around pins, street or pipe lines and areas, in red, fitted
/// to the drawing. Read-only, like BCMap.view on /emergency.
struct AlertMapView: View {
    let area: AlertArea
    var height: CGFloat = 200

    private static let red = Color(red: 0.82, green: 0.26, blue: 0.26)
    private func ll(_ c: AlertArea.Coord) -> CLLocationCoordinate2D { CLLocationCoordinate2D(latitude: c.lat, longitude: c.lng) }

    private var region: MKCoordinateRegion {
        guard let b = area.bounds else {
            return MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 30.2, longitude: -85.66), span: MKCoordinateSpan(latitudeDelta: 0.4, longitudeDelta: 0.5))
        }
        // A little room around the drawing, and never closer than a few blocks.
        return MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: (b.south + b.north) / 2, longitude: (b.west + b.east) / 2),
                                  span: MKCoordinateSpan(latitudeDelta: max((b.north - b.south) * 1.5, 0.006), longitudeDelta: max((b.east - b.west) * 1.5, 0.006)))
    }

    var body: some View {
        Map(initialPosition: .region(region)) {
            ForEach(Array(area.shapes.enumerated()), id: \.offset) { _, s in
                switch s {
                case .pin(let c, let r):
                    if let r {
                        MapCircle(center: ll(c), radius: r).foregroundStyle(Self.red.opacity(0.18)).stroke(Self.red, lineWidth: 2)
                    }
                    Marker("", coordinate: ll(c)).tint(Self.red)
                case .line(let cs):
                    MapPolyline(coordinates: cs.map(ll)).stroke(Self.red, lineWidth: 4)
                case .area(let rings):
                    MapPolygon(coordinates: (rings.first ?? []).map(ll)).foregroundStyle(Self.red.opacity(0.18)).stroke(Self.red, lineWidth: 2)
                }
            }
        }
        .mapStyle(.standard(pointsOfInterest: .excludingAll))
        .frame(height: height)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        .accessibilityLabel("Map of where this applies")
    }
}
