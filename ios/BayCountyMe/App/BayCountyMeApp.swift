import SwiftUI

@main
struct BayCountyMeApp: App {
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
