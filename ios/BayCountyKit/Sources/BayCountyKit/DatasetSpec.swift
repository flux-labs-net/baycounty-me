import Foundation

/// How the app presents one dataset: which columns make the row title, the headline number,
/// where it sits in Explore, and which site page it belongs to. Datasets the app doesn't know
/// yet still work through the generic fallback, so new site data shows up without an app update.
public struct DatasetSpec: Sendable {
    public enum Section: String, CaseIterable, Sendable, Identifiable {
        case whatYouPay = "What you pay"
        case whereItGoes = "Where it goes"
        case accountability = "Accountability"
        case peopleAndPay = "People and pay"
        case elections = "Elections and campaigns"
        case more = "More data"
        public var id: String { rawValue }
    }

    public let section: Section
    public let symbol: String
    public let titleKeys: [String]
    public let subtitleKeys: [String]
    public let detailKey: String?
    public let amountKeys: [String]
    public let dateKeys: [String]
    public let badgeKey: String?
    /// True when adding up the amount column is meaningful. Off everywhere for now: the site warns that contracts,
    /// change orders, FEMA projects and payments can overlap, so the app shows counts, not totals (CRA has its own rules).
    public let summable: Bool
    /// Columns that usually make good filters, in order.
    public let filterKeys: [String]
    public let page: String?

    public var pageURL: URL? { page.map { BayCountyClient.site.appendingPathComponent($0) } }

    init(_ section: Section, _ symbol: String, title: [String], subtitle: [String] = [], detail: String? = nil,
         amount: [String] = [], date: [String] = [], badge: String? = nil, summable: Bool = false,
         filters: [String] = [], page: String? = nil) {
        self.section = section; self.symbol = symbol; self.titleKeys = title; self.subtitleKeys = subtitle
        self.detailKey = detail; self.amountKeys = amount; self.dateKeys = date; self.badgeKey = badge
        self.summable = summable; self.filterKeys = filters; self.page = page
    }

    public static let known: [String: DatasetSpec] = [
        // What you pay
        "property-tax-rates": .init(.whatYouPay, "percent", title: ["authority"], subtitle: ["tax_year", "kind"],
                                    amount: ["levy"], date: ["tax_year"], filters: ["tax_year", "kind"], page: "public-money/tax-dollars"),
        "fees-assessments": .init(.whatYouPay, "doc.plaintext", title: ["name"], subtitle: ["government"], detail: "rate",
                                  amount: ["residential_single_family_amount"], filters: ["government", "category"], page: "public-money/fees-and-bills"),
        "bed-tax-collections": .init(.whatYouPay, "bed.double", title: ["district"], subtitle: ["fy"], amount: ["amount"],
                                     date: ["date_end", "fy"], filters: ["district"], page: "public-money/tourist-tax"),
        "property-tax-exemptions": .init(.whatYouPay, "house", title: ["exemption"], subtitle: ["statute", "applies_to"],
                                         amount: ["value_exempted"], page: "public-money/exemptions"),
        // Where it goes
        "budget-detail": .init(.whereItGoes, "chart.pie", title: ["name"], subtitle: ["government", "level"], amount: ["amount"],
                               filters: ["government", "level"], page: "public-money/budget-explorer"),
        "budget-years": .init(.whereItGoes, "chart.bar.xaxis", title: ["name"], subtitle: ["government", "fy", "section"], amount: ["amount"],
                              filters: ["government", "fy", "basis", "section"], page: "public-money/budget-compare"),
        "checkbook-payments": .init(.whereItGoes, "checkmark.rectangle", title: ["payee"], subtitle: ["government", "description"], amount: ["amount"],
                                    date: ["paid_on"], summable: true, filters: ["government", "fiscal_year", "fund", "payee_kind"], page: "public-money/checkbook"),
        "budget-actuals": .init(.whereItGoes, "gauge.with.dots.needle.33percent", title: ["description", "account"], subtitle: ["government", "department", "as_of"],
                                amount: ["actual_ytd"], date: ["as_of"], filters: ["government", "fiscal_year", "department", "line_type"], page: "public-money/budget-tracker"),
        "government-years": .init(.whereItGoes, "calendar", title: ["government"], subtitle: ["fy", "budget_status"], detail: "budget_note",
                                  amount: ["budget_total"], filters: ["government", "fy"], page: "governments"),
        "budget-per-resident": .init(.whereItGoes, "person.2", title: ["service"], subtitle: ["government"],
                                     amount: ["per_resident"], filters: ["government", "service"], page: "compare"),
        "cra-payments": .init(.whereItGoes, "building.2", title: ["purpose"], subtitle: ["cra", "date_or_fy"], detail: "payee",
                              amount: ["amount"], date: ["date_end", "date_start"], badge: "status",
                              filters: ["cra", "status", "category", "district"], page: "public-money/cra-spending"),
        "sales-tax-projects": .init(.whereItGoes, "road.lanes", title: ["name"], subtitle: ["government", "category"],
                                    amount: ["actual_cost", "programmed_cost", "promised_cost"], date: ["date_end"], badge: "status",
                                    filters: ["government", "category", "status"], page: "public-money/sales-tax-projects"),
        "fema-michael-projects": .init(.whereItGoes, "hurricane", title: ["title"], subtitle: ["applicant", "category"],
                                       amount: ["federal_share", "eligible_amount"], date: ["last_obligated", "first_obligated"],
                                       badge: "status", filters: ["applicant", "status", "category"], page: "public-money/hurricane-michael"),
        // Accountability
        "contracts": .init(.accountability, "signature", title: ["vendor"], subtitle: ["government", "date"], detail: "purpose",
                           amount: ["amount"], date: ["date"], filters: ["government", "method"], page: "public-money/contracts"),
        "change-orders": .init(.accountability, "arrow.triangle.2.circlepath", title: ["project"], subtitle: ["vendor", "date"],
                               detail: "reason", amount: ["change_amount"], date: ["date"],
                               filters: ["government"], page: "public-money/contracts"),
        "emergency-purchases": .init(.accountability, "exclamationmark.triangle", title: ["purpose"], subtitle: ["vendor", "date"],
                                     detail: "basis", amount: ["amount"], date: ["date"],
                                     filters: ["government"], page: "public-money/contracts"),
        "accountability-projects": .init(.accountability, "checklist", title: ["project"], subtitle: ["government", "stage"],
                                         detail: "flags", amount: ["latest_figure", "project_total", "first_figure"], date: ["last_date"],
                                         badge: "stage", filters: ["government", "kind", "stage"], page: "public-money/accountability"),
        "accountability-events": .init(.accountability, "calendar.badge.clock", title: ["project"], subtitle: ["event", "date"],
                                       detail: "description", amount: ["amount"], date: ["sort_date"],
                                       filters: ["government", "event"], page: "public-money/accountability"),
        "savings-opportunities": .init(.accountability, "dollarsign.arrow.circlepath", title: ["title"], subtitle: ["government", "lever"],
                                       detail: "next_step", amount: ["savings_high", "in_play"], badge: "confidence",
                                       filters: ["government", "lever", "confidence"], page: "public-money/savings"),
        "savings-evidence": .init(.accountability, "doc.text.magnifyingglass", title: ["label"], subtitle: ["group_title"],
                                  detail: "paid_to", amount: ["amount", "compare"], filters: ["opportunity_id", "kind"],
                                  page: "public-money/savings"),
        "votes": .init(.accountability, "hand.raised", title: ["headline"], subtitle: ["board", "date"], detail: "summary",
                       amount: ["amount"], date: ["date"], badge: "tally", filters: ["board", "category", "outcome", "split"],
                       page: "public-money/votes"),
        "member-votes": .init(.accountability, "person.crop.square", title: ["headline"], subtitle: ["member", "date"],
                              date: ["date"], badge: "vote", filters: ["board", "member", "vote"], page: "public-money/votes"),
        "vendor-payments": .init(.accountability, "dollarsign.circle", title: ["vendor"], subtitle: ["government", "payments"],
                                 amount: ["total"], filters: ["government"], page: "public-money/who-gets-paid"),
        "debt": .init(.accountability, "creditcard", title: ["government"], subtitle: ["fy"], detail: "total_debt_note",
                      amount: ["total_debt"], page: "public-money/debt"),
        "bonds": .init(.accountability, "banknote", title: ["series"], subtitle: ["issuer", "dated_date"], detail: "purpose",
                       amount: ["outstanding", "par_amount"], date: ["dated_date"], badge: "type", filters: ["gov", "type", "status"],
                       page: "public-money/debt"),
        "audit-findings": .init(.accountability, "magnifyingglass", title: ["finding"], subtitle: ["government", "fy"],
                                detail: "plain_english", date: ["date_end"], badge: "repeat", filters: ["government", "fy", "repeat"],
                                page: "public-money/audits"),
        // People and pay
        "officials-pay": .init(.peopleAndPay, "person.text.rectangle", title: ["name", "title"], subtitle: ["title", "government"],
                               amount: ["annual"], filters: ["government"], page: "who-runs-bay-county"),
        "salary-leaders": .init(.peopleAndPay, "person.crop.circle.badge.checkmark", title: ["name"], subtitle: ["title", "employer"],
                                amount: ["salary"], date: ["as_of"], filters: ["employer", "department"], page: "who-runs-bay-county"),
        "salary-positions": .init(.peopleAndPay, "briefcase", title: ["title"], subtitle: ["employer", "department"],
                                  amount: ["pay_max", "pay_mid", "pay_min"], filters: ["employer", "category", "fiscal_year"],
                                  page: "who-runs-bay-county"),
        // Elections
        "candidates-2026": .init(.elections, "checkmark.seal", title: ["candidate"], subtitle: ["office", "party"],
                                 amount: ["total_raised"], badge: "status", filters: ["office", "government", "status"], page: "elections"),
        "campaign-finance": .init(.elections, "chart.bar", title: ["official"], subtitle: ["office", "election"],
                                  amount: ["total_raised"], filters: ["gov", "election"], page: "connections/campaign-gifts"),
        "campaign-contributions-2026": .init(.elections, "envelope", title: ["contributor"], subtitle: ["candidate", "date"],
                                             amount: ["amount"], date: ["date"], badge: "contributor_type",
                                             filters: ["candidate", "contributor_type"], page: "connections/campaign-gifts"),
        "donor-contracts": .init(.elections, "link", title: ["vendor", "contributor"], subtitle: ["candidate", "contract_government"],
                                 amount: ["contribution_amount"], badge: "match_confidence",
                                 filters: ["candidate", "contract_government", "match_confidence"], page: "connections/campaign-gifts"),
        "business-donor-sunbiz": .init(.elections, "building.2", title: ["contributor"], subtitle: ["candidate", "sunbiz_entity_name"],
                                       detail: "sunbiz_doc_number", amount: ["contribution_amount"], date: ["last_date"], badge: "match_method",
                                       filters: ["candidate", "sunbiz_status", "match_method"], page: "connections/campaign-gifts"),
        "shared-owner-groups": .init(.elections, "person.2", title: ["business"], subtitle: ["candidate", "office"],
                                     detail: "business_dates", badge: "business_status", filters: ["candidate"], page: "connections/shared-owners"),
        "over-limit-gifts": .init(.elections, "exclamationmark.triangle", title: ["contributor"], subtitle: ["candidate", "election"],
                                  detail: "gift_list", badge: "status", filters: ["candidate", "status"], page: "connections/shared-owners"),
        "nonprofits": .init(.accountability, "heart.text.square", title: ["name"], subtitle: ["kind", "city"], detail: "subsection",
                            amount: ["total_revenue", "irs_revenue"], badge: "latest_return_form", filters: ["kind", "city", "subsection"], page: "connections/nonprofits"),
        "nonprofit-board-members": .init(.accountability, "person.3", title: ["person"], subtitle: ["nonprofit", "titles"], detail: "sources",
                                         badge: "role", filters: ["nonprofit", "role"], page: "connections/nonprofits"),
        "nonprofit-board-businesses": .init(.accountability, "building.2", title: ["business"], subtitle: ["person", "match"], amount: ["campaign_gifts_total"],
                                            badge: "business_status", filters: ["person", "business_status"], page: "connections/nonprofits"),
        "nonprofit-payments": .init(.accountability, "banknote", title: ["nonprofit"], subtitle: ["payer", "what"], amount: ["amount"],
                                    badge: "record_type", filters: ["payer", "record_type"], page: "connections/nonprofits"),
        "nonprofit-grants": .init(.accountability, "gift", title: ["recipient"], subtitle: ["grantor", "purpose"], amount: ["cash"],
                                  filters: ["grantor", "tax_year"], page: "connections/nonprofits"),
        "charity-registrations": .init(.accountability, "checkmark.seal", title: ["name"], subtitle: ["status", "city"], detail: "fiscal_year_end",
                                       amount: ["total_revenue"], badge: "status", filters: ["status", "city"], page: "connections/nonprofits"),
        "nonprofit-officials": .init(.accountability, "person.crop.square", title: ["official"], subtitle: ["nonprofit", "titles"],
                                     badge: "sources", filters: ["official", "nonprofit"], page: "connections/nonprofits"),
        "official-businesses": .init(.elections, "briefcase", title: ["business"], subtitle: ["official", "official_role"],
                                     detail: "titles", badge: "business_status", filters: ["official"], page: "connections/business-ties"),
        "official-business-links": .init(.elections, "link", title: ["detail"], subtitle: ["official"],
                                         detail: "link_type", badge: "link_type", filters: ["official", "link_type"], page: "connections/business-ties"),
        "money-map-gifts": .init(.elections, "gift", title: ["donor"], subtitle: ["official", "office"], amount: ["amount"],
                                 badge: "donor_type", filters: ["official", "donor_type", "donor_holds_contracts_here"], page: "connections/money-map"),
        "money-map-contracts": .init(.elections, "doc.text", title: ["donor"], subtitle: ["government"],
                                     amount: ["awarded_total", "paid_total"], filters: ["government", "likely_match_only"], page: "connections/money-map"),
        "money-map-votes": .init(.elections, "hand.raised", title: ["item"], subtitle: ["official", "vote_date"], detail: "donor",
                                 amount: ["amount"], date: ["vote_date"], badge: "vote", filters: ["official", "vote", "gift_before_or_after_vote"],
                                 page: "connections/money-map"),
        // Connections (every government's payees, links and business gifts to officials)
        "connections-payees": .init(.whereItGoes, "point.3.connected.trianglepath.dotted", title: ["name"], subtitle: ["kind", "records"],
                                    amount: ["dollars_in_records"], badge: "kind", filters: ["kind", "gave_to_campaigns"], page: "connections"),
        "connections-payments": .init(.whereItGoes, "arrow.right", title: ["payee"], subtitle: ["payer", "record_type"], detail: "what",
                                      amount: ["amount"], badge: "record_type", filters: ["payer", "record_type"], page: "connections"),
        "connections-links": .init(.whereItGoes, "arrow.left.arrow.right", title: ["name_a"], subtitle: ["name_b"], detail: "connection",
                                   page: "connections"),
        "connections-gifts": .init(.elections, "gift", title: ["donor"], subtitle: ["official", "office"], amount: ["amount"],
                                   badge: "donor_type", filters: ["official", "donor_type", "candidate_2026"], page: "connections"),
        "owner-gifts": .init(.elections, "person.text.rectangle", title: ["donor"], subtitle: ["candidate", "businesses"], amount: ["amount"],
                             date: ["last_date"], filters: ["candidate", "office"], page: "connections/campaign-gifts"),
        // Entity profiles (every person, company, nonprofit and government, and how they connect)
        "entity-profiles": .init(.more, "person.crop.circle", title: ["name"], subtitle: ["kind_label", "subtitle"],
                                 amount: ["amount_received", "amount_given"], badge: "kind_label", filters: ["kind_label"], page: "people"),
        "entity-connections": .init(.more, "point.3.connected.trianglepath.dotted", title: ["from_name"], subtitle: ["relation_label", "to_name"],
                                    detail: "detail", amount: ["amount"], date: ["last_date"], badge: "relation",
                                    filters: ["relation", "from_kind", "to_kind"], page: "connections"),
        // Reference
        "tax-districts": .init(.whatYouPay, "map", title: ["label"], subtitle: ["district"], amount: ["total_millage"],
                               page: "public-money/tax-dollars"),
        "vendors-directory": .init(.more, "building.2", title: ["name"], subtitle: ["vendor_type"], filters: ["vendor_type"],
                                   page: "public-money/vendors"),
        "people-directory": .init(.peopleAndPay, "person.3", title: ["name"], subtitle: ["district"], page: "who-runs-bay-county"),
        "glossary-terms": .init(.more, "book", title: ["term"], subtitle: ["group_name"], detail: "simple", filters: ["group_name"],
                                page: "glossary"),
        "site-updates": .init(.more, "sparkles", title: ["title"], subtitle: ["date"], detail: "text", date: ["date"], page: "updates"),
        "site-menu": .init(.more, "list.bullet", title: ["label"], subtitle: ["section", "lang"], detail: "description",
                           filters: ["section", "lang"]),
    ]

    /// Datasets the app shows in their own tabs rather than in Explore.
    public static let ownScreens: Set<String> = ["government-profiles", "meetings"]

    public static func `for`(_ id: String) -> DatasetSpec {
        known[id] ?? .init(.more, "tablecells", title: ["name", "title", "headline", "government", "vendor"],
                           subtitle: ["government", "date", "fy"], amount: ["amount", "total"], date: ["date"], page: "open-data")
    }

    /// Identifier and housekeeping columns that aren't useful to read.
    public static let hiddenColumns: Set<String> = [
        "gov_id", "vendor_id", "vendor_ids", "person_id", "record_id", "vote_ids", "vote_id", "contract_ids",
        "vote_match_method", "contract_match_method", "schedule_match_method", "date_start", "date_end", "date_precision",
        "lat", "lng", "authority_id", "employer_id", "race_id", "service_id", "members", "page", "id",
        "created_at", "updated_at", "fte_only",
    ]

    // MARK: - Reading a row

    /// The row's title. Organization names that filings write in ALL CAPS read in normal case.
    public func title(_ row: Row) -> String {
        guard let key = titleKeys.first(where: { row.string($0) != nil }), let t = row.string(key) else { return "Record" }
        return isOrgColumn(key) ? Format.orgName(t) : t
    }

    /// Columns holding an organization's name (and `name` in the nonprofit lists).
    func isOrgColumn(_ key: String) -> Bool {
        RecordProfile.orgColumns.contains(key) || (key == "name" && page == "connections/nonprofits")
    }

    public func subtitle(_ row: Row) -> String {
        subtitleKeys.filter { !titleKeys.prefix(1).contains($0) }
            .compactMap { key -> String? in
                guard let v = row[key], !v.isEmpty else { return nil }
                let s = Format.value(v, column: key)
                return isOrgColumn(key) ? Format.orgName(s) : s
            }
            .joined(separator: " · ")
    }

    public func detail(_ row: Row) -> String? { detailKey.flatMap { row.string($0) } }
    public func amount(_ row: Row) -> Double? { row.firstNumber(amountKeys) }
    public func amountKey(_ row: Row) -> String? { amountKeys.first { row.number($0) != nil } }
    public func badge(_ row: Row) -> String? {
        guard let key = badgeKey, let v = row[key], !v.isEmpty else { return nil }
        return Format.value(v, column: key)
    }

    /// A sortable date or year string (ISO dates and "FY2024"-style years both sort correctly as text).
    public func sortDate(_ row: Row) -> String? { row.first(dateKeys) }

    public static func sourceURL(_ row: Row) -> URL? {
        for key in ["source_url", "report_url", "finance_report_url", "official_statement_url", "detail_url", "agenda_url"] {
            if let u = row.url(key) { return u }
        }
        if let first = row.strings("sources").first(where: { $0.hasPrefix("http") }) { return URL(string: first) }
        return nil
    }

    /// Every readable field, labelled and formatted, in catalog order.
    public static func fields(_ row: Row, columns: [DatasetInfo.Column]) -> [(label: String, value: String)] {
        let names = columns.isEmpty ? row.values.keys.sorted() : columns.map(\.name)
        return names.compactMap { name in
            guard !hiddenColumns.contains(name), !name.hasSuffix("_url"), let v = row[name], !v.isEmpty else { return nil }
            return (Format.label(name), Format.value(v, column: name))
        }
    }
}
