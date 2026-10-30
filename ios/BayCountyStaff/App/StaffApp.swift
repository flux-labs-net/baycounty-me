import SwiftUI
import LocalAuthentication
import BayCountyKit

/// BayCounty.me Staff: the government workspace on a phone, for city and county staff and the site owner.
/// Launch arguments for screenshots: -demo (made-up data), -asStaff (a city alert sender instead of the owner),
/// -asOfficial (an elected commissioner: board dashboard; -screen board|votes),
/// -workspace lh (open one government), -screen overview|home|alerts|send|notices|notice|flags|flag|more|records|send-file|send-file-preview|signin|signin-code|locked.
@main
struct BayCountyStaffApp: App {
    @State private var store = StaffStore.shared
    @State private var lock = AppLock()
    @Environment(\.scenePhase) private var phase

    var body: some Scene {
        WindowGroup {
            Group {
                if !store.signedIn || Launch.screen == "signin" {
                    SignInView()
                } else if Launch.screen == "signin-code" {
                    SignInView(codeSentTo: "clerk@example.gov")
                } else if store.me == nil {
                    LoadingView()
                } else if lock.locked || Launch.screen == "locked" {
                    LockView(lock: lock)
                } else {
                    StaffRoot()
                }
            }
            .environment(store)
            .tint(Brand.navy)
            .task { if store.signedIn { await store.refresh() } }
        }
        .onChange(of: phase) { _, p in
            if p == .background { lock.backgrounded() }
            if p == .active { lock.resume() }
        }
    }
}

/// Face ID (or the passcode) after 5 minutes away, because this app can send alerts to every phone in a city.
@MainActor
@Observable
final class AppLock {
    private(set) var locked: Bool
    private var leftAt: Date?
    static let grace: TimeInterval = 300

    init() { locked = !Launch.demo && StaffKeychain.read() != nil }

    func backgrounded() { leftAt = Date() }
    func resume() {
        guard !Launch.demo, StaffKeychain.read() != nil else { return }
        if let leftAt, Date().timeIntervalSince(leftAt) > Self.grace { locked = true }
        if locked { unlock() }
    }
    func unlock() {
        let ctx = LAContext()
        var err: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) else { locked = false; return }
        ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Unlock BayCounty.me Staff") { ok, _ in
            Task { @MainActor in if ok { self.locked = false; self.leftAt = nil } }
        }
    }
}

enum Launch {
    static let args = ProcessInfo.processInfo.arguments
    static var demo: Bool { args.contains("-demo") }
    static var screen: String? { args.firstIndex(of: "-screen").flatMap { $0 + 1 < args.count ? args[$0 + 1] : nil } }
}

/// Signed in, waiting for the first answer (or showing why it failed).
struct LoadingView: View {
    @Environment(StaffStore.self) private var store
    var body: some View {
        VStack(spacing: 14) {
            if let e = store.error {
                Text(e).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.horizontal, 32)
                Button("Try again") { Task { await store.refresh() } }.buttonStyle(PrimaryButton()).padding(.horizontal, 32)
                Button("Sign out") { Task { await store.signOut() } }.foregroundStyle(Brand.salmon)
            } else {
                ProgressView()
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Brand.canvas)
    }
}

struct LockView: View {
    let lock: AppLock
    var body: some View {
        VStack(spacing: 18) {
            Spacer()
            Image(systemName: "faceid").font(.system(size: 54, weight: .regular)).foregroundStyle(Brand.navy)
            Text("BayCounty.me Staff is locked").font(.title3.weight(.bold))
            Text("Unlock with Face ID or your passcode. The app locks after 5 minutes away.")
                .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.horizontal, 32)
            Button { lock.unlock() } label: { Text("Unlock").frame(maxWidth: .infinity) }
                .buttonStyle(PrimaryButton()).padding(.horizontal, 32)
            Spacer()
            FluxFooter()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Brand.canvas)
        .onAppear { if !Launch.demo { lock.unlock() } }
    }
}

/// The tabs. The owner's first tab is every government at a glance; staff open on their own government.
struct StaffRoot: View {
    @Environment(StaffStore.self) private var store
    @State private var tab: String = {
        switch Launch.screen {
        case "alerts", "send": return "alerts"
        case "notices", "notice": return "notices"
        case "flags", "flag": return "flags"
        case "more", "records", "send-file", "send-file-preview": return "more"
        case "board": return "board"
        case "votes": return "votes"
        default: return ProcessInfo.processInfo.arguments.contains("-asOfficial") ? "board" : "home"
        }
    }()

    var body: some View {
        if store.isOfficial { officialTabs } else { staffTabs }
    }

    /// An elected official sees their board dashboard and votes; staff see the workspace.
    private var officialTabs: some View {
        TabView(selection: $tab) {
            NavigationStack { BoardView() }
                .tabItem { Label("Board", systemImage: "building.columns") }.tag("board")
            NavigationStack { VotesView() }
                .tabItem { Label("Votes", systemImage: "checkmark.seal") }.tag("votes")
            NavigationStack { FlagsView() }
                .tabItem { Label("Flags", systemImage: "flag") }.tag("flags")
            NavigationStack { MoreView() }
                .tabItem { Label("More", systemImage: "ellipsis.circle") }.tag("more")
        }
        .onAppear { if tab == "home" { tab = "board" } }
    }

    private var staffTabs: some View {
        TabView(selection: $tab) {
            NavigationStack { store.workspaceId == nil && store.isOwner ? AnyView(OverviewView()) : AnyView(WorkspaceHomeView()) }
                .tabItem { Label(store.workspaceId == nil && store.isOwner ? "Overview" : "Home", systemImage: "square.grid.2x2") }.tag("home")
            NavigationStack { AlertsView() }
                .tabItem { Label("Alerts", systemImage: "exclamationmark.triangle") }.tag("alerts")
                .badge(store.alerts.filter(\.isWaiting).count)
            NavigationStack { NoticesView() }
                .tabItem { Label("Notices", systemImage: "doc.text") }.tag("notices")
            NavigationStack { FlagsView() }
                .tabItem { Label("Flags", systemImage: "flag") }.tag("flags")
                .badge(store.flags.filter { $0.status == "open" }.count)
            NavigationStack { MoreView() }
                .tabItem { Label("More", systemImage: "ellipsis.circle") }.tag("more")
        }
    }
}
