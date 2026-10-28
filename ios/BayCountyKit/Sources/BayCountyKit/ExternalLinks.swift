import Foundation

/// Links the app hands to another app instead of its in-app browser.
public enum ExternalLinks {
    /// Map and directions links open the Maps app; tel:, mailto:, maps: and other non-web links open their own app.
    public static func opensOutsideApp(_ url: URL) -> Bool {
        let scheme = url.scheme?.lowercased() ?? ""
        guard scheme == "http" || scheme == "https" else { return true }
        let host = url.host?.lowercased() ?? ""
        return host == "maps.apple.com" || host == "maps.google.com"
            || ((host == "google.com" || host == "www.google.com") && url.path.hasPrefix("/maps"))
    }
}
