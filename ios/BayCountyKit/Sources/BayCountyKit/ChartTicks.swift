import Foundation

/// Rules shared by the app's charts: few enough axis labels to read, and nothing before the site's first year.
public enum ChartTicks {
    /// Most labels that fit under a phone-width chart.
    public static let phoneLabels = 6

    /// Which of `count` evenly spaced bars get a label, so at most `maxLabels` show. The last bar is always labelled.
    public static func labelIndices(count: Int, maxLabels: Int = phoneLabels) -> [Int] {
        guard count > 0 else { return [] }
        let step = max(1, Int((Double(count) / Double(max(maxLabels, 1))).rounded(.up)))
        return (0..<count).filter { (count - 1 - $0) % step == 0 }
    }

    /// The labels to show from a list of category labels (oldest first).
    public static func shownLabels(_ labels: [String], maxLabels: Int = phoneLabels) -> [String] {
        labelIndices(count: labels.count, maxLabels: maxLabels).map { labels[$0] }
    }

    /// Round years to label on a year axis (every 1, 2, 5 or 10 years), at most `maxLabels`.
    public static func yearTicks(_ years: [Int], maxLabels: Int = phoneLabels) -> [Int] {
        guard let lo = years.min(), let hi = years.max() else { return [] }
        for step in [1, 2, 5, 10, 20] {
            let ticks = (lo...hi).filter { $0 % step == 0 }
            if ticks.count <= maxLabels && !ticks.isEmpty { return ticks }
        }
        return [lo, hi]
    }

    /// Drops anything dated before the site's first year (2016).
    public static func sinceCutoff<T>(_ items: [T], year: (T) -> Int?) -> [T] {
        items.filter { (year($0) ?? Cutoff.firstYear) >= Cutoff.firstYear }
    }

    /// The year in a label like "FY2024", "2024" or "'24".
    public static func year(of label: String) -> Int? {
        let digits = label.filter(\.isNumber)
        if digits.count == 4 { return Int(digits) }
        if digits.count == 2, label.hasPrefix("'"), let n = Int(digits) { return 2000 + n }
        return nil
    }
}
