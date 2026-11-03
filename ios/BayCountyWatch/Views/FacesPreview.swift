import SwiftUI
import WidgetKit
import BayCountyKit

/// Screenshots only (`-screen faces`): the complications drawn side by side, as they look on a watch face.
struct FacesPreview: View {
    let brief: WatchBrief.Brief

    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                Text("10:09").font(.system(size: 40, weight: .semibold, design: .rounded))
                ComplicationView(brief: brief, family: .accessoryInline).font(.footnote)
                HStack(spacing: 10) {
                    ComplicationView(brief: brief, family: .accessoryCircular).frame(width: 52, height: 52)
                    ComplicationView(brief: brief, family: .accessoryRectangular)
                        .padding(6)
                        .background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                }
            }
            .frame(maxWidth: .infinity)
        }
        .background(Color.black)
    }
}
