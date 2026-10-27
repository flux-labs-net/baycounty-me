import SwiftUI
import UIKit
import UserNotifications
import BayCountyKit

/// Phone notifications: asks permission, gets the device token from Apple and signs the phone up at
/// https://baycounty.me/api/push with the topics, cities and saved place chosen on the Emergencies screen.
/// Nothing but the token, the choices and a rounded map point is sent.
@MainActor
@Observable
final class PushManager {
    static let shared = PushManager()

    private(set) var token: String?
    private(set) var authorized = false
    private(set) var status: String?

    var topics: Set<String> { didSet { save() } }
    var govs: [String] { didSet { save() } }
    var useHomeForAgenda: Bool { didSet { save() } }
    var radius: Double { didSet { save() } }
    var enabled: Bool { didSet { save() } }

    private init() {
        let d = UserDefaults.standard
        topics = Set(d.stringArray(forKey: "push.topics") ?? Array(Emergency.defaultTopics))
        govs = d.stringArray(forKey: "push.govs") ?? []
        useHomeForAgenda = d.object(forKey: "push.home") as? Bool ?? true
        radius = d.object(forKey: "push.radius") as? Double ?? 1
        enabled = d.bool(forKey: "push.enabled")
        Task { await refreshAuthorization() }
    }

    private func save() {
        let d = UserDefaults.standard
        d.set(Array(topics), forKey: "push.topics"); d.set(govs, forKey: "push.govs")
        d.set(useHomeForAgenda, forKey: "push.home"); d.set(radius, forKey: "push.radius"); d.set(enabled, forKey: "push.enabled")
    }

    func refreshAuthorization() async {
        let s = await UNUserNotificationCenter.current().notificationSettings()
        authorized = s.authorizationStatus == .authorized || s.authorizationStatus == .provisional
    }

    /// Turn notifications on: ask permission (once), then register with Apple; the token arrives in the app delegate.
    func enable() async {
        do {
            authorized = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
        } catch { authorized = false }
        guard authorized else { status = "Notifications are off for BayCounty.me in Settings."; enabled = false; return }
        enabled = true
        UIApplication.shared.registerForRemoteNotifications()
    }

    func disable() async {
        enabled = false
        guard let token else { return }
        var req = URLRequest(url: BayCountyClient.site.appendingPathComponent("api/push"))
        req.httpMethod = "POST"; req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["token": token, "platform": "ios", "action": "unregister"])
        _ = try? await URLSession.shared.data(for: req)
        status = "Notifications turned off."
    }

    func didRegister(_ deviceToken: Data) {
        token = Emergency.hexToken(deviceToken)
        Task { await sync(home: nil) }
    }

    /// Send the current choices. `home` is the saved address's point, used for agenda items near me.
    func sync(home: GeoPoint?) async {
        guard enabled, let token else { return }
        let pt = useHomeForAgenda ? (home ?? Self.savedHome()) : nil
        var req = URLRequest(url: BayCountyClient.site.appendingPathComponent("api/push"))
        req.httpMethod = "POST"; req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = Emergency.pushBody(token: token, platform: "ios", topics: topics, govs: govs, lat: pt?.y, lng: pt?.x, radius: radius,
                                          appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String)
        do {
            let (_, r) = try await URLSession.shared.data(for: req)
            status = (r as? HTTPURLResponse)?.statusCode == 200 ? "Alerts are on for this phone." : "Couldn't save your choices. Try again later."
        } catch { status = "Couldn't reach BayCounty.me. Your choices will be sent next time." }
    }

    private static func savedHome() -> GeoPoint? {
        guard let d = UserDefaults.standard.data(forKey: "home"), let m = try? JSONDecoder().decode(AddressMatch.self, from: d) else { return nil }
        return m.point
    }
}

/// Receives the device token and opens the notice when a notification is tapped.
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        Task { @MainActor in PushManager.shared.didRegister(deviceToken) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {}

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let info = response.notification.request.content.userInfo
        guard let s = info["url"] as? String, let url = URL(string: s) else { return }
        await MainActor.run { NotificationCenter.default.post(name: .openNotice, object: url) }
    }
}

extension Notification.Name {
    static let openNotice = Notification.Name("bc.openNotice")
}
