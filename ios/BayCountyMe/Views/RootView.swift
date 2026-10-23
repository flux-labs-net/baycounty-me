import SwiftUI
import BayCountyKit

struct RootView: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        @Bindable var store = store
        TabView(selection: $store.tab) {
            HomeView()
                .tabItem { Label("Home", systemImage: "house") }
                .tag(AppStore.Tab.home)
            GovernmentsView()
                .tabItem { Label("Governments", systemImage: "building.columns") }
                .tag(AppStore.Tab.governments)
            MeetingsView()
                .tabItem { Label("Meetings", systemImage: "calendar") }
                .tag(AppStore.Tab.meetings)
            ExploreView()
                .tabItem { Label("Explore", systemImage: "square.grid.2x2") }
                .tag(AppStore.Tab.explore)
            SearchView()
                .tabItem { Label("Search", systemImage: "magnifyingglass") }
                .tag(AppStore.Tab.search)
        }
        .sheet(item: $store.presentedPage) { page in
            SafariView(url: page.url).ignoresSafeArea()
        }
    }
}
