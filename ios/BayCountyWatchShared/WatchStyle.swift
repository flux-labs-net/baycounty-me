import SwiftUI
import BayCountyKit

/// The phone app's brand colors, in their dark-mode shades (a watch is always dark).
enum WatchStyle {
    static let navy = Color(red: 0.616, green: 0.722, blue: 0.918)
    static let blue = Color(red: 0.498, green: 0.651, blue: 0.855)
    static let salmon = Color(red: 1.0, green: 0.549, blue: 0.510)
    static let amber = Color(red: 1.0, green: 0.765, blue: 0.420)
    static let good = Color(red: 0.373, green: 0.827, blue: 0.604)
    static let teal = Color(red: 0.36, green: 0.80, blue: 0.80)
    /// The navy behind the app's screens.
    static let deep = Color(red: 0.118, green: 0.227, blue: 0.463)

    static func tone(_ t: String) -> Color {
        switch t { case "teal": teal; case "amber": amber; case "salmon": salmon; default: blue }
    }

    /// Phone-app symbol names that differ on the watch's older SF Symbols set fall back to a plain one.
    static func symbol(_ name: String) -> String {
        name == "car.side.arrowtriangle.up.fill" ? "car.fill" : name
    }

    static func alertColor(_ brief: WatchBrief.Brief) -> Color {
        !brief.alertsLoaded ? .gray : brief.alertCount > 0 ? salmon : good
    }

    static func alertSymbol(_ brief: WatchBrief.Brief) -> String {
        !brief.alertsLoaded ? "wifi.slash" : brief.alertCount > 0 ? "exclamationmark.triangle.fill" : "checkmark.shield.fill"
    }
}
