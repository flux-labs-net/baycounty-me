import Foundation

/// How the app covers each page on BayCounty.me. Every page the site lists in /data/app/pages.json must
/// appear here, so a new site page can't ship without a decision about the app: a native screen, or a
/// deliberate web view. SitePagesTests fails, naming the page, when one is missing.
public enum SitePages {
    public enum Coverage: Sendable, Equatable {
        /// A native app screen (the name is for people reading this file).
        case native(String)
        /// Shown as the record list for a site dataset.
        case dataset(String)
        /// Opened in the in-app browser on purpose (forms, developer docs, the big interactive map).
        case web(String)
    }

    public static let pages: [String: Coverage] = [
        "/": .native("Home"),
        "/my-address": .native("My Address"),
        "/public-money/cra-spending": .native("CRA Spending"),
        "/public-money/tax-dollars": .native("Tax calculator"),
        "/public-money/amendment-3": .native("Amendment 3"),
        "/public-money/hurricane-michael": .dataset("fema-michael-projects"),
        "/public-money/tourist-tax": .dataset("bed-tax-collections"),
        "/public-money/sales-tax-projects": .dataset("sales-tax-projects"),
        "/public-money/fees-and-bills": .dataset("fees-assessments"),
        "/governments": .native("Governments tab"),
        "/compare": .web("side-by-side table; the Governments tab has the comparison charts"),
        "/open-data": .native("Every dataset (Explore)"),
        "/developers": .web("API documentation for developers"),
        "/records-request": .web("records request writer"),
        "/connections/shared-owners": .web("confirmed shared-owner groups, read live from /api/v1/datasets/shared-owner-groups"),
        "/connections/business-ties": .web("confirmed official-to-business matches, read live from /api/v1/datasets/official-businesses and official-business-links"),
        "/correspondence": .web("published letters to officials, read live from /api/v1/correspondence"),
        "/alerts": .web("email alert sign-up; push alerts are planned for the app"),
        "/meetings": .native("Meetings tab"),
        "/connections/campaign-gifts": .dataset("campaign-finance"),
        "/who-runs-bay-county": .native("People"),
        "/public-money/budget-explorer": .dataset("budget-detail"),
        "/elections": .dataset("candidates-2026"),
        "/public-money/exemptions": .dataset("property-tax-exemptions"),
        "/connections/money-map": .native("Money map"),
        "/public-money/who-gets-paid": .dataset("vendor-payments"),
        "/public-money/contracts": .dataset("contracts"),
        "/public-money/accountability": .native("Accountability console"),
        "/public-money/savings": .dataset("savings-opportunities"),
        "/public-money/votes": .native("Votes by meeting"),
        "/public-money/debt": .dataset("debt"),
        "/public-money/audits": .dataset("audit-findings"),
        "/public-money/vendors": .native("Companies"),
        "/public-money/map": .web("combined public money map"),
        "/connections": .web("Connections network graph"),
        "/glossary": .native("Glossary"),
        "/updates": .native("What's new"),
        "/search": .native("Search tab"),
        "/about": .native("About"),
        "/privacy": .web("privacy page"),
    ]

    /// Page families covered by one native screen (each government's profile).
    public static let prefixes: [String: Coverage] = [
        "/governments/": .native("Government profile"),
    ]

    public static func coverage(_ path: String) -> Coverage? {
        if let c = pages[path] { return c }
        return prefixes.first { path.hasPrefix($0.key) }?.value
    }

    /// Datasets the app shows somewhere other than a record list (their own tab or screen).
    public static let ownScreens: Set<String> = DatasetSpec.ownScreens
}
