import Foundation
import Security
import BayCountyKit

/// The resident's BayCounty.me account on this phone: signs in with an emailed code, keeps the session token in the
/// Keychain, and loads the saved home, choices and "near my home" feed from https://baycounty.me/api/account.
@MainActor
@Observable
final class AccountManager {
    static let shared = AccountManager()

    private(set) var me: AccountMe?
    private(set) var feed: NearbyFeed?
    private(set) var loading = false
    var error: String?

    private let client: AccountClient
    var signedIn: Bool { client.token != nil }

    private init() {
        client = AccountClient(token: Keychain.read())
        if Self.demo { loadDemo() }
    }

    /// Emails a sign-in code. Returns the message to show under the field.
    func start(email: String) async -> Bool {
        error = nil
        do { _ = try await client.start(email: email); return true } catch { self.error = error.localizedDescription; return false }
    }

    func verify(email: String, code: String) async -> Bool {
        error = nil
        do {
            let m = try await client.verify(email: email, code: code)
            if let t = m.token { Keychain.save(t) }
            me = m
            await PushManager.shared.linkAccount()
            await loadFeed()
            return true
        } catch { self.error = error.localizedDescription; return false }
    }

    func refresh() async {
        guard signedIn, !Self.demo else { return }
        loading = true; defer { loading = false }
        do { me = try await client.me(); await loadFeed() } catch { handle(error) }
    }

    func loadFeed() async {
        guard me?.home != nil else { feed = nil; return }
        do { feed = try await client.feed() } catch { handle(error) }
    }

    func saveHome(_ m: AddressMatch) async {
        error = nil
        do {
            me = try await client.saveHome(address: m.display + (m.zip.map { " " + $0 } ?? ""), lat: m.point.y, lon: m.point.x)
            await loadFeed()
            await PushManager.shared.linkAccount()
        } catch { handle(error) }
    }

    func removeHome() async {
        do { me = try await client.removeHome(); feed = nil } catch { handle(error) }
    }

    func save(prefs: AccountMe.Prefs) async {
        do { me = try await client.save(prefs: prefs); await loadFeed(); await PushManager.shared.linkAccount() } catch { handle(error) }
    }

    func save(firstName: String) async {
        do { me = try await client.save(firstName: firstName) } catch { handle(error) }
    }

    /// Ties this phone's alerts to the account so they follow the saved home and choices.
    func linkDevice(pushToken: String) async {
        guard signedIn, !Self.demo else { return }
        try? await client.linkDevice(pushToken: pushToken, appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String)
    }

    func signOut() async {
        await client.logout()
        clear()
    }

    func deleteAccount() async {
        do { try await client.deleteAccount(); clear() } catch { handle(error) }
    }

    private func clear() {
        Keychain.delete(); client.token = nil; me = nil; feed = nil
    }

    private func handle(_ e: Error) {
        if case AccountClient.AccountError.signedOut = e { clear(); error = "You were signed out. Sign in again."; return }
        error = e.localizedDescription
    }

    // MARK: Automated screenshots

    /// `-screen myhome` shows a saved feed for 825 Ohio Ave so the picture doesn't need an account or the live site.
    static var demo: Bool {
        let a = ProcessInfo.processInfo.arguments
        guard let i = a.firstIndex(of: "-screen"), i + 1 < a.count else { return false }
        return a[i + 1].hasPrefix("myhome")
    }

    private func loadDemo() {
        guard let url = Bundle.main.url(forResource: "nearby-sample", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return }
        feed = try? NearbyFeed.decode(data)
        let j = #"""
        {"user":{"email":"resident@example.com","first_name":"Sam"},
         "home":{"label":"Home","address":"825 Ohio Ave","city":"Lynn Haven","zip":"32444","lat":30.2449,"lon":-85.6483,"gov_id":"lh","zone":"D"},
         "prefs":{"weekly_email":true,"alert_email":["evacuation","water"],"push_topics":["weather","evacuation","shelters","water","agenda"],"radius_mi":1,"topics":["meetings","events","projects","notices","food","business"]},
         "devices":1,
         "choices":{"topics":{"meetings":"Public meetings","events":"Things to do","projects":"Building and road work","notices":"Public notices","food":"Restaurant inspections","business":"New businesses"},
                    "radius_mi":[0.25,0.5,1,2,5],
                    "push_topics":{"weather":"Weather warnings","evacuation":"Evacuation orders","shelters":"Shelters opening","water":"Boil-water notices","roads":"Road closures","agenda":"Agenda items near my home"},
                    "alert_email":{"evacuation":"Evacuation orders for my zone","water":"Boil-water notices for my city","weather":"Weather warnings","shelters":"Shelters opening"}}}
        """#
        me = try? AccountMe.decode(Data(j.utf8))
        client.token = "demo"
    }
}

/// The session token, kept in the Keychain on this phone only.
private enum Keychain {
    static let service = "me.baycounty.account"
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: "session"]
    }

    static func read() -> String? {
        var q = query; q[kSecReturnData as String] = true; q[kSecMatchLimit as String] = kSecMatchLimitOne
        var out: AnyObject?
        guard SecItemCopyMatching(q as CFDictionary, &out) == errSecSuccess, let d = out as? Data else { return nil }
        return String(data: d, encoding: .utf8)
    }

    static func save(_ token: String) {
        delete()
        var q = query
        q[kSecValueData as String] = Data(token.utf8)
        q[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(q as CFDictionary, nil)
    }

    static func delete() { SecItemDelete(query as CFDictionary) }
}
