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
        .onChange(of: store.tab, initial: true) { _, t in
            let names: [AppStore.Tab: String] = [.home: "today", .living: "living", .money: "money", .decides: "decides", .search: "search"]
            store.usage.viewed("tab/" + (names[t] ?? "today"))
        }
        // Signed in: the account's saved home is the phone's address too (Today card, tax bill, trash day), so it
        // follows the resident to any phone. Signing out leaves the phone's address as it was.
        .task { if AccountManager.shared.signedIn, AccountManager.shared.me == nil { await AccountManager.shared.refresh() } }
        .onChange(of: AccountManager.shared.me?.home, initial: true) { _, home in
            if let m = home?.addressMatch, store.home?.id != m.id || store.home?.point != m.point { store.home = m }
        }
    }
}
