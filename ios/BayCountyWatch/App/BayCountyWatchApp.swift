import SwiftUI
import WidgetKit
import BayCountyKit

/// BayCounty.me for Apple Watch: today's alerts, the saved home's trash day, the beach flag and the next meeting,
/// at a glance. The saved home comes from the iPhone app (PhoneLink); alerts reach the watch as the phone's
/// notifications, which watchOS shows on the wrist when the phone is locked.
@main
struct BayCountyWatchApp: App {
    @State private var model = WatchModel()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            BriefView()
                .environment(model)
                .task { PhoneLink.shared.start { Task { await model.refresh() } } }
        }
        .onChange(of: phase, initial: true) { _, p in if p == .active { Task { await model.refresh() } } }
    }
}

/// The brief on screen, reloaded when the app comes to the front, on pull to refresh, or when the phone sends a new home.
@MainActor
@Observable
final class WatchModel {
    private(set) var brief: WatchBrief.Brief?
    private(set) var updated: Date?
    private(set) var loading = false

    func refresh() async {
        guard !loading else { return }
        loading = true; defer { loading = false }
        brief = await WatchData.load()
        updated = Date()
        // Keep the watch face in step with what the app just showed.
        WidgetCenter.shared.reloadAllTimelines()
    }
}
