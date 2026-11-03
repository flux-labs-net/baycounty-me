import Foundation

/// The site's dataset catalog (`/downloads/index.json`).
public struct Catalog: Codable, Hashable, Sendable {
    public let updated: String?
    public let license: String?
    public let datasets: [DatasetInfo]

    public func dataset(_ id: String) -> DatasetInfo? { datasets.first { $0.id == id } }

    /// The datasets that hold rows for one government (its gov_id column lists it), for a government's "Every record" list.
    /// A dataset with nothing for that government is left off, so the list doesn't open onto empty tables.
    public func records(for govID: String) -> [DatasetInfo] {
        datasets.filter { !DatasetSpec.ownScreens.contains($0.id) && ($0.rows ?? 0) > 0 && ($0.column("gov_id")?.choices.contains(govID) ?? false) }
    }
}

public struct DatasetInfo: Codable, Hashable, Identifiable, Sendable {
    public let id: String
    public let title: String
    public let description: String?
    public let rows: Int?
    public let json: String
    public let csv: String?
    public let columns: [Column]

    public struct Column: Codable, Hashable, Sendable {
        public let name: String
        public let type: String?
        public let values: [JSONValue]?

        /// Allowed values when the catalog lists a short set (used for filters).
        public var choices: [String] {
            (values ?? []).compactMap { $0.stringValue }.filter { !$0.isEmpty }
        }
    }

    public func column(_ name: String) -> Column? { columns.first { $0.name == name } }

    public var csvURL: URL? { csv.flatMap { URL(string: $0, relativeTo: BayCountyClient.site)?.absoluteURL } }
    public var pageURL: URL { DatasetSpec.for(id).pageURL ?? BayCountyClient.site.appendingPathComponent("open-data") }
}
