import SwiftUI
import BayCountyKit

/// First launch (and the Home tab's "Set up your home" tile): where you live and whether you own or rent. Owners'
/// Home tab leads with the tax bill; renters' with utilities and services. Both answers stay on this phone.
struct HomeSetupView: View {
    @Environment(AppStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var results: [AddressMatch] = []
    @State private var picked: AddressMatch?
    @State private var tenure: HomeTiles.Tenure = .own
    @State private var message: String?
    @FocusState private var typing: Bool

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Where do you live?").font(.title.weight(.bold))
                        Text("We use it to show what applies to you: trash day, your officials, your schools. It stays on your phone.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                    addressField
                    VStack(alignment: .leading, spacing: 10) {
                        Text("Do you own or rent this home?").font(.subheadline.weight(.semibold))
                        TenurePicker(selection: $tenure)
                    }
                }
                .padding(.horizontal, 20)
                .padding(.top, 8)
                .padding(.bottom, 24)
            }
            .background(Brand.canvas)
            .safeAreaInset(edge: .bottom) {
                VStack(spacing: 4) {
                    Button { finish(save: true) } label: {
                        Text("Continue").font(.headline).foregroundStyle(.white)
                            .frame(maxWidth: .infinity, minHeight: 52)
                            .background(Brand.navyFill, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    }
                    .buttonStyle(PressScale())
                    .accessibilityIdentifier("setupContinue")
                    Button("Skip for now") { finish(save: false) }
                        .font(.subheadline).frame(minHeight: 44)
                }
                .padding(.horizontal, 20).padding(.top, 8)
                .background(Brand.canvas)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { BayMark().frame(height: 24).accessibilityHidden(true) }
            }
            .task(id: query) { await search() }
            .onAppear {
                picked = store.home
                if let t = store.tenure { tenure = t }
            }
        }
    }

    /// The address: a saved home shows as picked; typing searches Bay County's map server.
    @ViewBuilder private var addressField: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Street address").font(.subheadline.weight(.semibold))
            if let p = picked, query.isEmpty {
                HStack(spacing: 12) {
                    Image(systemName: "house.fill").foregroundStyle(Brand.navy)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(p.display).font(.body.weight(.medium))
                        Text(p.subtitle).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    Button("Change") { picked = nil; typing = true }.font(.subheadline.weight(.semibold))
                }
                .padding(14).card(14)
            } else {
                TextField("e.g. 825 Ohio Ave", text: $query)
                    .textContentType(.fullStreetAddress).autocorrectionDisabled().focused($typing)
                    .padding(.horizontal, 14).frame(minHeight: 50).card(14)
                    .accessibilityLabel("Street address")
                if let message { Text(message).font(.caption).foregroundStyle(.secondary) }
                if !results.isEmpty {
                    CardList {
                        ForEach(results.prefix(5)) { m in
                            Button { picked = m; query = ""; results = []; typing = false } label: {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(m.display).font(.body.weight(.medium)).foregroundStyle(.primary)
                                    Text(m.subtitle).font(.caption).foregroundStyle(.secondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(.horizontal, 14).padding(.vertical, 10).contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            if m.id != results.prefix(5).last?.id { RowDivider(inset: 14) }
                        }
                    }
                }
            }
        }
    }

    private func finish(save: Bool) {
        if save {
            if let picked { store.home = picked }
            store.tenure = tenure
        }
        store.setupSeen = true
        dismiss()
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 3 else { results = []; message = nil; return }
        try? await Task.sleep(for: .milliseconds(300))
        guard !Task.isCancelled else { return }
        guard AddressParser.parse(q).map({ !$0.tokens.isEmpty }) ?? false else {
            results = []; message = "Start with the house number, then the street (for example \"1614 Ohio\")."
            return
        }
        do {
            let r = try await store.gis.search(q)
            guard !Task.isCancelled else { return }
            results = r.matches
            message = r.matches.isEmpty ? "No matching Bay County address. Try just the number and street name." : nil
        } catch {
            guard !Task.isCancelled else { return }
            message = "Bay County's map server didn't answer. Try again in a moment."
        }
    }
}

/// Own, rent, or rather not say: three cards with a check on the picked one. Used on setup and in My home.
struct TenurePicker: View {
    @Binding var selection: HomeTiles.Tenure

    var body: some View {
        VStack(spacing: 10) {
            ForEach(HomeTiles.Tenure.allCases, id: \.self) { t in
                Button { selection = t } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: selection == t ? "largecircle.fill.circle" : "circle")
                            .font(.title3).foregroundStyle(selection == t ? Brand.navy : .secondary)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(t.label).font(.body.weight(.semibold)).foregroundStyle(.primary)
                            Text(t.detail).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(14)
                    .card(14)
                    .overlay {
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .strokeBorder(selection == t ? Brand.navy : .clear, lineWidth: 1.5)
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selection == t ? [.isSelected] : [])
            }
        }
    }
}
