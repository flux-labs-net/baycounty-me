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
        "/public-money/cra-tax-increment": .native("CRA tax increment"),
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
        "/connections/shared-owners": .web("confirmed shared-owner groups and gifts over the limit, read live from /api/v1/datasets/shared-owner-groups and over-limit-gifts"),
        "/connections/nonprofits": .dataset("nonprofits"),
        "/volunteer": .native("Volunteer"),
        "/chambers": .native("Chambers of commerce"),
        "/events": .native("Events"),
        "/beaches": .native("Beaches"),
        "/parks": .native("Parks"),
        "/development": .dataset("development-projects"),
        "/roads": .dataset("road-contracts"),
        "/schools": .native("Public schools (SchoolsView); zoned schools are on My Address"),
        "/utilities": .native("Utilities and trash day (UtilitiesView, from /api/v1/utilities)"),
        "/restaurants": .dataset("restaurants"),
        "/new-businesses": .dataset("new-businesses"),
        "/this-week": .web("the weekly email's page with its sign-up form; the events, meetings, votes and contracts in it are on native screens"),
        "/connections/business-ties": .web("confirmed official-to-business matches, read live from /api/v1/datasets/official-businesses and official-business-links"),
        "/correspondence": .web("published letters to officials, read live from /api/v1/correspondence"),
        "/alerts": .web("email alert sign-up; phone alerts are set on the Emergencies screen"),
        "/emergency": .native("Emergencies and alerts (live feed, zone lookup, shelters, phone alerts)"),
        "/hurricane-prep": .native("Hurricane prep (prep steps, rebuild money by ZIP code, declarations)"),
        "/meetings": .native("Meetings tab"),
        "/connections/campaign-gifts": .dataset("campaign-finance"),
        "/public-money/budget-compare": .native("Budget compare (BudgetCompare, the same rules as /api/v1/budget-compare)"),
        "/elections": .dataset("candidates-2026"),
        "/elections/past": .dataset("campaign-history"),
        "/elections/results": .dataset("election-results"),
        "/elections/voting": .dataset("voting-locations"),
        "/notices": .dataset("public-notices"),
        "/jobs": .dataset("job-openings"),
        "/public-money/exemptions": .dataset("property-tax-exemptions"),
        "/public-money/contracts": .dataset("contracts"),
        "/public-money/accountability": .native("Accountability console"),
        "/public-money/votes": .native("Votes by meeting"),
        "/public-money/vendors": .native("Companies"),
        "/connections": .web("Connections network graph"),
        "/glossary": .native("Glossary"),
        "/updates": .native("What's new"),
        "/search": .native("Search tab"),
        "/ask": .web("Ask chatbot, opened from the Today toolbar and Search; answers stream from /api/chat, which uses the MCP tools"),
        "/about": .native("About"),
        "/data-sources": .dataset("data-sources"),
        "/privacy": .web("privacy page"),
        "/people": .native("People"),
    ]

    /// Page families covered by one native screen (each government's profile).
    public static let prefixes: [String: Coverage] = [
        "/governments/": .native("Government profile"),
        "/public-money/vendors/": .native("Company detail, opened from the Companies list"),
        "/people/": .native("Person detail, with a link to the web profile and its connection map"),
        "/profile/": .web("entity profile and connection map, read live from /api/v1/entities/{id}"),
    ]

    public static func coverage(_ path: String) -> Coverage? {
        if let c = pages[path] { return c }
        return prefixes.first { path.hasPrefix($0.key) }?.value
    }

    /// Datasets the app shows somewhere other than a record list (their own tab or screen).
    public static let ownScreens: Set<String> = DatasetSpec.ownScreens
}
