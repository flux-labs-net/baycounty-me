package me.baycounty.kit

/**
 * How the app covers each page on BayCounty.me. Every page the site lists in /data/app/pages.json must appear
 * here, so a new site page can't ship without a decision about the app: a native screen, or a deliberate web
 * view. SitePagesTest fails, naming the page, when one is missing. Kept in step with the iOS SitePages.swift.
 */
object SitePages {
    sealed class Coverage {
        abstract val note: String
        /** A native app screen (the name is for people reading this file). */
        data class Native(override val note: String) : Coverage()
        /** Shown as the record list for a site dataset. */
        data class Dataset(override val note: String) : Coverage()
        /** Opened in the in-app browser on purpose. */
        data class Web(override val note: String) : Coverage()
    }

    val pages: Map<String, Coverage> = mapOf(
        "/" to Coverage.Native("Home"),
        "/my-address" to Coverage.Native("My Address"),
        "/public-money/cra-spending" to Coverage.Native("CRA Spending"),
        "/public-money/cra-tax-increment" to Coverage.Native("CRA tax increment"),
        "/public-money/tax-dollars" to Coverage.Native("Tax calculator"),
        "/public-money/amendment-3" to Coverage.Native("Amendment 3"),
        "/public-money/hurricane-michael" to Coverage.Dataset("fema-michael-projects"),
        "/public-money/tourist-tax" to Coverage.Dataset("bed-tax-collections"),
        "/public-money/sales-tax-projects" to Coverage.Dataset("sales-tax-projects"),
        "/public-money/fees-and-bills" to Coverage.Dataset("fees-assessments"),
        "/governments" to Coverage.Native("Governments tab"),
        "/compare" to Coverage.Web("side-by-side table; the Governments tab has the comparison charts"),
        "/open-data" to Coverage.Native("Every dataset (Explore)"),
        "/developers" to Coverage.Web("API documentation for developers"),
        "/records-request" to Coverage.Web("records request writer"),
        "/connections/shared-owners" to Coverage.Web("confirmed shared-owner groups and gifts over the limit, read live from /api/v1/datasets/shared-owner-groups and over-limit-gifts"),
        "/connections/nonprofits" to Coverage.Dataset("nonprofits"),
        "/chambers" to Coverage.Native("Chambers of commerce"),
        "/events" to Coverage.Native("Events"),
        "/beaches" to Coverage.Native("Beaches"),
        "/parks" to Coverage.Native("Parks"),
        "/development" to Coverage.Dataset("development-projects"),
        "/roads" to Coverage.Dataset("road-contracts"),
        "/schools" to Coverage.Native("Public schools (SchoolsScreen); zoned schools are on My Address"),
        "/utilities" to Coverage.Native("Utilities and trash day (UtilitiesScreen, from /api/v1/utilities)"),
        "/restaurants" to Coverage.Dataset("restaurants"),
        "/new-businesses" to Coverage.Dataset("new-businesses"),
        "/this-week" to Coverage.Web("the weekly email's page with its sign-up form; the events, meetings, votes and contracts in it are on native screens"),
        "/connections/business-ties" to Coverage.Web("confirmed official-to-business matches, read live from /api/v1/datasets/official-businesses and official-business-links"),
        "/correspondence" to Coverage.Web("published letters to officials, read live from /api/v1/correspondence"),
        "/alerts" to Coverage.Web("email alert sign-up; phone alerts are set on the Emergencies screen"),
        "/emergency" to Coverage.Native("Emergencies and alerts (live feed, zone lookup, shelters, phone alerts)"),
        "/hurricane-prep" to Coverage.Native("Hurricane prep (prep steps, rebuild money by ZIP code, declarations)"),
        "/meetings" to Coverage.Native("Meetings tab"),
        "/connections/campaign-gifts" to Coverage.Dataset("campaign-finance"),
        "/public-money/budget-compare" to Coverage.Native("Budget compare (BudgetCompare, the same rules as /api/v1/budget-compare)"),
        "/elections" to Coverage.Dataset("candidates-2026"),
        "/elections/past" to Coverage.Dataset("campaign-history"),
        "/elections/results" to Coverage.Dataset("election-results"),
        "/elections/voting" to Coverage.Dataset("voting-locations"),
        "/notices" to Coverage.Dataset("public-notices"),
        "/jobs" to Coverage.Dataset("job-openings"),
        "/public-money/exemptions" to Coverage.Dataset("property-tax-exemptions"),
        "/public-money/contracts" to Coverage.Dataset("contracts"),
        "/public-money/accountability" to Coverage.Native("Accountability console"),
        "/public-money/votes" to Coverage.Native("Votes by meeting"),
        "/public-money/vendors" to Coverage.Native("Companies"),
        "/connections" to Coverage.Web("Connections network graph"),
        "/glossary" to Coverage.Native("Glossary"),
        "/updates" to Coverage.Native("What's new"),
        "/search" to Coverage.Native("Search tab"),
        "/ask" to Coverage.Web("Ask chatbot, opened from the Today toolbar and Search; answers stream from /api/chat, which uses the MCP tools"),
        "/about" to Coverage.Native("About"),
        "/data-sources" to Coverage.Dataset("data-sources"),
        "/privacy" to Coverage.Web("privacy page"),
        "/people" to Coverage.Native("People"),
    )

    /** Page families covered by one native screen. */
    val prefixes: Map<String, Coverage> = mapOf(
        "/governments/" to Coverage.Native("Government profile"),
        "/public-money/vendors/" to Coverage.Native("Company detail, opened from the Companies list"),
        "/people/" to Coverage.Native("Person detail, with a link to the web profile and its connection map"),
        "/profile/" to Coverage.Web("entity profile and connection map, read live from /api/v1/entities/{id}"),
    )

    fun coverage(path: String): Coverage? = pages[path] ?: prefixes.entries.firstOrNull { path.startsWith(it.key) }?.value

    val ownScreens: Set<String> get() = DatasetSpec.ownScreens
}
