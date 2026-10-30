import SwiftUI
import WidgetKit
import BayCountyKit

/// The complication faces, shared so the watch app can draw them for screenshots too.
struct ComplicationView: View {
    @Environment(\.widgetFamily) private var widgetFamily
    let brief: WatchBrief.Brief
    /// Set when the watch app draws a face outside a watch face (screenshots); nil inside a real complication.
    var family: WidgetFamily? = nil

    var body: some View {
        switch family ?? widgetFamily {
        case .accessoryCircular: circular
        case .accessoryRectangular: rectangular
        case .accessoryCorner:
            Image(systemName: WatchStyle.alertSymbol(brief))
                .font(.title2)
                .widgetLabel(brief.inline)
        default:
            Label(brief.inline, systemImage: WatchStyle.alertSymbol(brief))
        }
    }

    var circular: some View {
        ZStack {
            if family == nil { AccessoryWidgetBackground() } else { Circle().fill(.white.opacity(0.14)) }
            VStack(spacing: 0) {
                Image(systemName: WatchStyle.alertSymbol(brief)).font(.caption)
                Text(brief.circular).font(.title3.weight(.semibold)).minimumScaleFactor(0.6)
            }
            .foregroundStyle(WatchStyle.alertColor(brief))
        }
        .widgetAccentable()
        .accessibilityLabel(brief.alertTitle)
    }

    var rectangular: some View {
        VStack(alignment: .leading, spacing: 1) {
            HStack(spacing: 4) {
                Image(systemName: WatchStyle.alertSymbol(brief)).foregroundStyle(WatchStyle.alertColor(brief))
                Text(brief.alertTitle).font(.headline).widgetAccentable()
            }
            Text(brief.rectangularDetail).font(.caption)
            Text(brief.place).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
