import SwiftUI
import BayCountyKit

struct RootView: View {
    @Environment(AppStore.self) private var store

    var body: some View {
        @Bindable var store = store
        TabView(selection: $store.tab) {
            HomeView()
                .tabItem { Label("Today", systemImage: "house") }
                .tag(AppStore.Tab.home)
            LivingHereView()
                .tabItem { Label("Living here", systemImage: "mappin.and.ellipse") }
                .tag(AppStore.Tab.living)
            MoneyView()
                .tabItem { Label("Money", systemImage: "dollarsign.circle") }
                .tag(AppStore.Tab.money)
            GovernmentsView()
                .tabItem { Label("Who decides", systemImage: "building.columns") }
                .tag(AppStore.Tab.decides)
            NavigationStack {
                SearchView().withRoutes()
            }
            .tabItem { Label("Search", systemImage: "magnifyingglass") }
            .tag(AppStore.Tab.search)
        }
        .sheet(item: $store.presentedPage) { page in
            SafariView(url: page.url).ignoresSafeArea()
        }
        .sheet(item: $store.presentedTerm) { term in
            TermSheet(term: term)
        }
    }
}
