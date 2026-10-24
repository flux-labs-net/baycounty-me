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
            GovernmentsView()
                .tabItem { Label("Places", systemImage: "mappin.and.ellipse") }
                .tag(AppStore.Tab.governments)
            MoneyView()
                .tabItem { Label("Money", systemImage: "dollarsign.circle") }
                .tag(AppStore.Tab.money)
            MeetingsView()
                .tabItem { Label("Meetings", systemImage: "calendar") }
                .tag(AppStore.Tab.meetings)
        }
        .sheet(item: $store.presentedPage) { page in
            SafariView(url: page.url).ignoresSafeArea()
        }
        .sheet(item: $store.presentedTerm) { term in
            TermSheet(term: term)
        }
    }
}
