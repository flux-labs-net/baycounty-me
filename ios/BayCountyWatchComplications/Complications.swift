import SwiftUI
import WidgetKit
import BayCountyKit

/// Watch face complications: the active alert count (round), alerts plus trash day (rectangle), and one line
/// under the time (inline). They check again about every 15 minutes, and whenever the watch app opens.
@main
struct BayCountyComplications: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "BayCountyToday", provider: BriefProvider()) { entry in
            ComplicationView(brief: entry.brief)
                .containerBackground(for: .widget) { Color.clear }
        }
        .configurationDisplayName("BayCounty.me")
        .description("Active alerts and your trash day.")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline, .accessoryCorner])
    }
}

struct BriefEntry: TimelineEntry {
    let date: Date
    let brief: WatchBrief.Brief
}

struct BriefProvider: TimelineProvider {
    func placeholder(in context: Context) -> BriefEntry { BriefEntry(date: Date(), brief: WatchData.demoBrief()) }

    func getSnapshot(in context: Context, completion: @escaping (BriefEntry) -> Void) {
        if context.isPreview { completion(placeholder(in: context)); return }
        Task { completion(BriefEntry(date: Date(), brief: await WatchData.load())) }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<BriefEntry>) -> Void) {
        Task {
            let entry = BriefEntry(date: Date(), brief: await WatchData.load())
            completion(Timeline(entries: [entry], policy: .after(Date().addingTimeInterval(15 * 60))))
        }
    }
}
