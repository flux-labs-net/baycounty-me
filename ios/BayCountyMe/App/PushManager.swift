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
        UserDefaults.standard.removeObject(forKey: Self.linkedKey)
        status = "Alerts are off on this phone."
    }

    /// Signing out turns alerts off: the server drops this phone in the same call (AccountManager.signOut).
    func signedOut() { enabled = false; status = nil; UserDefaults.standard.removeObject(forKey: Self.linkedKey) }

    /// Each time the app opens: if alerts are on, register with Apple again. Apple can hand the phone a new token
    /// (a reinstall, a restore, a new TestFlight or App Store build), and the old one then stops working; without this
    /// the server kept sending to the old token and the phone got nothing. If notifications were turned off in the
    /// iPhone's Settings app, say so on the switch.
    func resume() async {
        guard enabled, AccountManager.shared.signedIn else { return }
        await refreshAuthorization()
        guard authorized else { status = "Notifications are off for BayCounty.me in the iPhone's Settings app."; return }
        UIApplication.shared.registerForRemoteNotifications()
    }

    func didRegister(_ deviceToken: Data) {
        let new = Emergency.hexToken(deviceToken)
        let old = UserDefaults.standard.string(forKey: Self.linkedKey)
        token = new
        Task {
            // A replaced token is dropped from the account, so alerts don't go to a token Apple no longer delivers to.
            if let old, old != new, AccountManager.shared.signedIn { await AccountManager.shared.unlinkDevice(pushToken: old) }
            await linkAccount(force: old != new)
        }
    }

    private static let linkedKey = "push.linkedToken", linkedAtKey = "push.linkedAt"

    /// Ties this phone to the signed-in account (after sign-in, a new token, or a change to the home or choices).
    /// Opening the app re-links at most once a day when nothing changed, which also tells the server the phone is still in use.
    func linkAccount(force: Bool = true) async {
        guard enabled, let token, AccountManager.shared.signedIn else { return }
        let last = UserDefaults.standard.double(forKey: Self.linkedAtKey)
        if !force, UserDefaults.standard.string(forKey: Self.linkedKey) == token, Date().timeIntervalSince1970 - last < 86_400 { return }
        let ok = await AccountManager.shared.linkDevice(pushToken: token)
        if ok {
            UserDefaults.standard.set(token, forKey: Self.linkedKey)
            UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: Self.linkedAtKey)
        }
        status = ok ? "Alerts are on for this phone." : "Couldn't reach BayCounty.me. Try again later."
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
