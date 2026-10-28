import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

/// Reads BayCounty.me.
///
/// Datasets come from the static `/downloads/<id>.json` files the site publishes on every build: they're
/// served from the CDN, carry no rate limit and match what the website shows. Search uses `/api/v1/search`
/// (60 requests a minute without a key). Every response is cached on disk with its ETag, revalidated on the
/// next request, and used as-is when the device is offline. A bundled seed covers the very first launch.
public final class BayCountyClient: @unchecked Sendable {
    public static let site = URL(string: "https://baycounty.me")!

    public enum Freshness: Sendable { case live, cached, bundled }

    public struct Response: Sendable {
        public let data: Data
        public let freshness: Freshness
        public let fetchedAt: Date?
    }

    public enum ClientError: LocalizedError {
        case unavailable(String)
        case http(Int)
        public var errorDescription: String? {
            switch self {
            case .unavailable(let path): return "Couldn't load \(path) and there's no saved copy yet."
            case .http(let code): return code == 429 ? "Too many searches this minute. Try again shortly." : "The site returned an error (\(code))."
            }
        }
    }

    private let session: URLSession
    private let baseURL: URL
    private let cacheDirectory: URL?
    private let seedBundle: Bundle?
    private let lock = NSLock()

    public init(session: URLSession = .shared, baseURL: URL = BayCountyClient.site,
                cacheDirectory: URL? = BayCountyClient.defaultCacheDirectory, seedBundle: Bundle? = nil) {
        self.session = session
        self.baseURL = baseURL
        self.cacheDirectory = cacheDirectory
        self.seedBundle = seedBundle
        if let cacheDirectory { try? FileManager.default.createDirectory(at: cacheDirectory, withIntermediateDirectories: true) }
    }

    public static var defaultCacheDirectory: URL? {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?.appendingPathComponent("BayCountyMe", isDirectory: true)
    }

    // MARK: - Endpoints

    public func catalog() async throws -> (Catalog, Freshness) {
        let r = try await get("/downloads/index.json")
        return (try JSONDecoder().decode(Catalog.self, from: r.data), r.freshness)
    }

    public func rows(_ dataset: DatasetInfo) async throws -> ([Row], Freshness) {
        try await rows(path: dataset.json)
    }

    public func rows(datasetID: String) async throws -> ([Row], Freshness) {
        try await rows(path: "/downloads/\(datasetID).json")
    }

    /// One restaurant's inspections, newest first: the API's filtered rows, or (offline) the full download filtered here.
    public func restaurantInspections(license: String) async throws -> [Row] {
        do {
            return Restaurants.inspections(try Row.decodeRows(try await get(Restaurants.inspectionsPath(license)).data), license: license)
        } catch {
            return Restaurants.inspections(try await rows(datasetID: "restaurant-inspections").0, license: license)
        }
    }

    public func governments() async throws -> ([Government], Freshness) {
        let (rows, f) = try await rows(datasetID: "government-profiles")
        return (rows.map(Government.init(row:)), f)
    }

    public func meetings() async throws -> ([Meeting], Freshness) {
        let (rows, f) = try await rows(datasetID: "meetings")
        return (rows.map(Meeting.init(row:)), f)
    }

    public func search(_ query: String, limit: Int = 40) async throws -> [SearchResult] {
        var c = URLComponents(url: baseURL.appendingPathComponent("api/v1/search"), resolvingAgainstBaseURL: false)!
        c.queryItems = [URLQueryItem(name: "q", value: query), URLQueryItem(name: "limit", value: String(limit))]
        let (data, response) = try await session.data(for: URLRequest(url: c.url!))
        let code = (response as? HTTPURLResponse)?.statusCode ?? 0
        guard code == 200 else { throw ClientError.http(code) }
        return try JSONDecoder().decode(SearchResponse.self, from: data).data
    }

    /// Calendar feed of upcoming meetings, for "Subscribe in Calendar".
    public static func meetingsCalendarURL(gov: String? = nil) -> URL {
        var c = URLComponents(string: "webcal://baycounty.me/api/v1/meetings.ics")!
        if let gov { c.queryItems = [URLQueryItem(name: "gov", value: gov)] }
        return c.url!
    }

    private func rows(path: String) async throws -> ([Row], Freshness) {
        let r = try await get(path)
        return (try Row.decodeList(r.data), r.freshness)
    }

    // MARK: - Conditional GET with disk cache

    public func get(_ path: String) async throws -> Response {
        let url = URL(string: path, relativeTo: baseURL)!.absoluteURL
        let cached = readCache(path)
        var request = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 20)
        if let etag = cached?.etag { request.setValue(etag, forHTTPHeaderField: "If-None-Match") }
        do {
            let (data, response) = try await session.data(for: request)
            let http = response as? HTTPURLResponse
            switch http?.statusCode ?? 0 {
            case 200:
                writeCache(path, data: data, etag: http?.value(forHTTPHeaderField: "ETag"))
                return Response(data: data, freshness: .live, fetchedAt: Date())
            case 304 where cached != nil:
                touchCache(path)
                return Response(data: cached!.data, freshness: .live, fetchedAt: Date())
            case let code:
                if let fallback = offlineCopy(path, cached: cached) { return fallback }
                throw ClientError.http(code)
            }
        } catch let error as ClientError {
            throw error
        } catch {
            if let fallback = offlineCopy(path, cached: cached) { return fallback }
            throw ClientError.unavailable(path)
        }
    }

    private func offlineCopy(_ path: String, cached: (data: Data, etag: String?, date: Date?)?) -> Response? {
        if let cached { return Response(data: cached.data, freshness: .cached, fetchedAt: cached.date) }
        let name = (path as NSString).lastPathComponent as NSString
        if let url = seedBundle?.url(forResource: name.deletingPathExtension, withExtension: name.pathExtension),
           let data = try? Data(contentsOf: url) {
            return Response(data: data, freshness: .bundled, fetchedAt: nil)
        }
        return nil
    }

    private func cacheURLs(_ path: String) -> (body: URL, etag: URL)? {
        guard let dir = cacheDirectory else { return nil }
        let key = path.replacingOccurrences(of: "/", with: "_")
        return (dir.appendingPathComponent(key), dir.appendingPathComponent(key + ".etag"))
    }

    private func readCache(_ path: String) -> (data: Data, etag: String?, date: Date?)? {
        lock.lock(); defer { lock.unlock() }
        guard let urls = cacheURLs(path), let data = try? Data(contentsOf: urls.body) else { return nil }
        let etag = (try? String(contentsOf: urls.etag, encoding: .utf8))?.trimmingCharacters(in: .whitespacesAndNewlines)
        let date = (try? FileManager.default.attributesOfItem(atPath: urls.body.path))?[.modificationDate] as? Date
        return (data, etag?.isEmpty == false ? etag : nil, date)
    }

    private func writeCache(_ path: String, data: Data, etag: String?) {
        lock.lock(); defer { lock.unlock() }
        guard let urls = cacheURLs(path) else { return }
        try? data.write(to: urls.body, options: .atomic)
        if let etag { try? etag.write(to: urls.etag, atomically: true, encoding: .utf8) }
        else { try? FileManager.default.removeItem(at: urls.etag) }
    }

    private func touchCache(_ path: String) {
        lock.lock(); defer { lock.unlock() }
        guard let urls = cacheURLs(path) else { return }
        try? FileManager.default.setAttributes([.modificationDate: Date()], ofItemAtPath: urls.body.path)
    }
}
