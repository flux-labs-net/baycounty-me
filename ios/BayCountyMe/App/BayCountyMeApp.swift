import SwiftUI

@main
struct BayCountyMeApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
                .tint(Brand.navy)
                .task { await store.loadEssentials() }
        }
    }
}
