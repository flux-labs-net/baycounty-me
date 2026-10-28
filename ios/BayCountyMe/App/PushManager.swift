import SwiftUI
import UIKit
import UserNotifications
import BayCountyKit

/// Phone notifications. Alerts need a BayCounty.me account: the switch lives in My home > Settings, and the phone is
/// tied to the account (POST /api/account device), so its alerts follow the home and choices saved there. Only the
/// token is sent from here; the server keeps the account's choices and a rounded map point of the home.
@MainActor
@Observable
final class PushManager {
    static let shared = PushManager()

    private(set) var token: String?
    private(set) var authorized = false
    private(set) var status: String?
    private(set) var enabled: Bool { didSet { UserDefaults.standard.set(enabled, forKey: "push.enabled") } }

    private init() {
        enabled = UserDefaults.standard.bool(forKey: "push.enabled")
        Task { await refreshAuthorization() }
    }

    func refreshAuthorization() async {
        let s = await UNUserNotificationCenter.current().notificationSettings()
        authorized = s.authorizationStatus == .authorized || s.authorizationStatus == .provisional
    }

    /// Turn alerts on for the signed-in account: ask permission (once), then register with Apple. The token arrives in
    /// the app delegate, which ties it to the account.
    func enable() async {
        guard AccountManager.shared.signedIn else { status = "Sign in to get alerts."; return }
        do {
            authorized = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
        } catch { authorized = false }
        guard authorized else { status = "Notifications are off for BayCounty.me in the iPhone's Settings app."; enabled = false; return }
        enabled = true
        status = nil
        UIApplication.shared.registerForRemoteNotifications()
    }

    func disable() async {
        enabled = false
        if let token { await AccountManager.shared.unlinkDevice(pushToken: token) }
        status = "Alerts are off on this phone."
    }

    /// Signing out turns alerts off: the server drops this phone in the same call (AccountManager.signOut).
    func signedOut() { enabled = false; status = nil }

    func didRegister(_ deviceToken: Data) {
        token = Emergency.hexToken(deviceToken)
        Task { await linkAccount() }
    }

    /// Ties this phone to the signed-in account (after sign-in, a new token, or a change to the home or choices).
    func linkAccount() async {
        guard enabled, let token, AccountManager.shared.signedIn else { return }
        status = await AccountManager.shared.linkDevice(pushToken: token) ? "Alerts are on for this phone." : "Couldn't reach BayCounty.me. Try again later."
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
