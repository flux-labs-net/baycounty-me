import Foundation
import WatchConnectivity
import BayCountyKit

/// Sends the saved home to the Apple Watch app, so the watch can show that home's trash day and city. Only the
/// home's map point goes over (WatchBrief.Home); the address, account and settings stay on the phone.
final class WatchSync: NSObject, WCSessionDelegate {
    static let shared = WatchSync()
    private var latest: [String: Any] = WatchBrief.Home.message(nil)

    /// Call once at launch with the saved home, then `update` whenever it changes.
    func start(home: AddressMatch?) {
        update(home)
        guard WCSession.isSupported() else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func update(_ home: AddressMatch?) {
        latest = WatchBrief.Home.message(home.map { WatchBrief.Home(lat: $0.point.y, lon: $0.point.x) })
        send()
    }

    private func send() {
        guard WCSession.isSupported() else { return }
        let s = WCSession.default
        guard s.activationState == .activated, s.isPaired, s.isWatchAppInstalled else { return }
        try? s.updateApplicationContext(latest)
    }

    func session(_ session: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        DispatchQueue.main.async { self.send() }
    }
    func sessionDidBecomeInactive(_ session: WCSession) {}
    func sessionDidDeactivate(_ session: WCSession) { session.activate() }
    func sessionWatchStateDidChange(_ session: WCSession) { DispatchQueue.main.async { self.send() } }
}
