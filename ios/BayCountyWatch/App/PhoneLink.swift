import Foundation
import WatchConnectivity
import WidgetKit
import BayCountyKit

/// Receives the saved home's map point from the iPhone app (WatchSync there) and keeps it for the app and the
/// complications. Nothing else comes over from the phone.
final class PhoneLink: NSObject, WCSessionDelegate {
    static let shared = PhoneLink()
    private var onChange: (() -> Void)?

    func start(onChange: @escaping () -> Void) {
        self.onChange = onChange
        guard WCSession.isSupported(), !WatchData.demo else { return }
        WCSession.default.delegate = self
        WCSession.default.activate()
    }

    func session(_ session: WCSession, activationDidCompleteWith state: WCSessionActivationState, error: Error?) {
        apply(session.receivedApplicationContext)
    }

    func session(_ session: WCSession, didReceiveApplicationContext context: [String: Any]) {
        apply(context)
    }

    private func apply(_ context: [String: Any]) {
        guard let home = WatchBrief.Home.from(message: context), home != WatchData.home else { return }
        WatchData.home = home
        WidgetCenter.shared.reloadAllTimelines()
        DispatchQueue.main.async { self.onChange?() }
    }
}
