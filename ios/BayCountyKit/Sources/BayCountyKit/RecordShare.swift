import Foundation

/// What Copy and Share put out for one record: a clean text summary (its name, then each field as "Label: value") and
/// a link to it on BayCounty.me. Same shape as the website's Share / Copy (site/share.js), and the same rules on
/// Android (kit RecordShare.kt).
public enum RecordShare {
    /// How many fields the text lists after the name, so a long record stays readable in a message.
    public static let maxFields = 10

    /// The record's own page when it has one (page_url), else the site page that lists this dataset, else its source.
    public static func url(_ datasetID: String, _ row: Row) -> URL? {
        if let p = row.string("page_url"), p.hasPrefix("/") { return URL(string: BayCountyClient.site.absoluteString + p) }
        if let u = DatasetSpec.for(datasetID).pageURL { return u }
        return DatasetSpec.sourceURL(row)
    }

    /// The text: name, fields, source, where it's from, link.
    public static func text(_ datasetID: String, _ row: Row, columns: [DatasetInfo.Column] = [], listTitle: String? = nil) -> String {
        let spec = DatasetSpec.for(datasetID)
        let title = spec.title(row)
        var lines = [title]
        var seen = Set([title.lowercased()])
        for f in DatasetSpec.fields(row, columns: columns) where lines.count <= maxFields {
            let v = f.value.replacingOccurrences(of: "\n", with: " ").trimmingCharacters(in: .whitespaces)
            guard !v.isEmpty, !seen.contains(v.lowercased()) else { continue }
            seen.insert(v.lowercased())
            lines.append("\(f.label): \(v.count > 160 ? String(v.prefix(157)) + "…" : v)")
        }
        let link = url(datasetID, row)
        if let src = DatasetSpec.sourceURL(row), src != link { lines.append("Source: \(src.absoluteString)") }
        lines.append(listTitle.map { "From “\($0)” on BayCounty.me" } ?? "From BayCounty.me")
        if let link { lines.append(link.absoluteString) }
        return lines.joined(separator: "\n")
    }

    /// A page with its own address (a restaurant, a person, a company): its name, a short summary and the link.
    public static func page(title: String, summary: [String], path: String) -> String {
        ([title] + summary.filter { !$0.isEmpty } + [BayCountyClient.site.absoluteString + path]).joined(separator: "\n")
    }
}
