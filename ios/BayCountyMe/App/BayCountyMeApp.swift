import SwiftUI

@main
struct BayCountyMeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var store = AppStore()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
                .tint(Brand.navy)
                .task {
                    WatchSync.shared.start(home: store.home)
                    await store.loadEssentials()
                }
        }
        .onChange(of: phase, initial: true) { _, p in if p == .active { store.becameActive() } }
    }
}
