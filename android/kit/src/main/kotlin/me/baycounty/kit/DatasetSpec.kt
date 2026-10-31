package me.baycounty.kit

/**
 * How the app presents one dataset: which columns make the row title, the headline number, where it sits in
 * Explore, and which site page it belongs to. Datasets the app doesn't know yet still work through the generic
 * fallback, so new site data shows up without an app update.
 */
data class DatasetSpec(
    val section: Section,
    /** An SF Symbol name, shared with iOS. The app maps it to a Material icon. */
    val symbol: String,
    val title: List<String>,
    val subtitle: List<String> = emptyList(),
    val detail: String? = null,
    val amount: List<String> = emptyList(),
    val date: List<String> = emptyList(),
    val badge: String? = null,
    /** True when adding up the amount column is meaningful. */
    val summable: Boolean = false,
    /** Columns that usually make good filters, in order. */
    val filters: List<String> = emptyList(),
    val page: String? = null,
) {
    enum class Section(val label: String) {
        WHAT_YOU_PAY("What you pay"),
        WHERE_IT_GOES("Where it goes"),
        ACCOUNTABILITY("Accountability"),
        PEOPLE_AND_PAY("People and pay"),
        ELECTIONS("Elections and campaigns"),
        MORE("More data"),
    }

    val titleKeys get() = title
    val subtitleKeys get() = subtitle
    val detailKey get() = detail
    val amountKeys get() = amount
    val dateKeys get() = date
    val badgeKey get() = badge
    val filterKeys get() = filters

    val pageURL: String? get() = page?.let { "${BayCountyClient.SITE}/$it" }

    /** The row's title. Organization names that filings write in ALL CAPS read in normal case. */
    fun title(row: Row): String {
        val key = titleKeys.firstOrNull { row.string(it) != null } ?: return "Record"
        val t = row.string(key) ?: return "Record"
        return if (isOrgColumn(key)) Format.orgName(t) else t
    }

    fun isOrgColumn(key: String): Boolean = key in RecordProfile.orgColumns || (key == "name" && page == "connections/nonprofits")

    fun subtitle(row: Row): String =
        subtitleKeys.filter { it !in titleKeys.take(1) }.mapNotNull { key ->
            val v = row[key] ?: return@mapNotNull null
            if (v.isEmptyValue) return@mapNotNull null
            val s = Format.value(v, key)
            if (isOrgColumn(key)) Format.orgName(s) else s
        }.joinToString(" · ")

    fun detail(row: Row): String? = detailKey?.let { row.string(it) }
    fun amount(row: Row): Double? = row.firstNumber(amountKeys)
    fun amountKey(row: Row): String? = amountKeys.firstOrNull { row.number(it) != null }
    fun badge(row: Row): String? {
        val key = badgeKey ?: return null
        val v = row[key] ?: return null
        if (v.isEmptyValue) return null
        return Format.value(v, key)
    }

    /** A sortable date or year string. */
    fun sortDate(row: Row): String? = row.first(dateKeys)

    companion object {
        val known: Map<String, DatasetSpec> = mapOf(
        // What you pay
        "property-tax-rates" to DatasetSpec(Section.WHAT_YOU_PAY, "percent", title = listOf("authority"), subtitle = listOf("tax_year", "kind"),
                                    amount = listOf("levy"), date = listOf("tax_year"), filters = listOf("tax_year", "kind"), page = "public-money/tax-dollars"),
        "fees-assessments" to DatasetSpec(Section.WHAT_YOU_PAY, "doc.plaintext", title = listOf("name"), subtitle = listOf("government"), detail = "rate",
                                  amount = listOf("residential_single_family_amount"), filters = listOf("government", "category"), page = "public-money/fees-and-bills"),
        "utility-providers" to DatasetSpec(Section.WHAT_YOU_PAY, "bolt", title = listOf("provider"), subtitle = listOf("area_name", "service_label"), detail = "notes",
                                   badge = "service_label", filters = listOf("area_name", "service_label"), page = "utilities"),
        "utility-rates" to DatasetSpec(Section.WHAT_YOU_PAY, "drop", title = listOf("charge"), subtitle = listOf("area_name", "provider"), detail = "notes",
                               amount = listOf("amount"), badge = "service_label", filters = listOf("area_name", "service_label"), page = "utilities"),
        "trash-pickup" to DatasetSpec(Section.WHAT_YOU_PAY, "trash", title = listOf("provider"), subtitle = listOf("area_name", "service_label", "zone"), detail = "rule",
                              badge = "pickup_days", filters = listOf("area_name", "service_label"), page = "utilities"),
        "trash-holidays" to DatasetSpec(Section.WHAT_YOU_PAY, "calendar", title = listOf("holiday"), subtitle = listOf("area_name", "when_observed"), detail = "garbage",
                                filters = listOf("area_name"), page = "utilities"),
        "bed-tax-collections" to DatasetSpec(Section.WHAT_YOU_PAY, "bed.double", title = listOf("district"), subtitle = listOf("fy"), amount = listOf("amount"),
                                     date = listOf("date_end", "fy"), filters = listOf("district"), page = "public-money/tourist-tax"),
        "property-tax-exemptions" to DatasetSpec(Section.WHAT_YOU_PAY, "house", title = listOf("exemption"), subtitle = listOf("statute", "applies_to"),
                                         amount = listOf("value_exempted"), page = "public-money/exemptions"),
        // Where it goes
        "budget-detail" to DatasetSpec(Section.WHERE_IT_GOES, "chart.pie", title = listOf("name"), subtitle = listOf("government", "level"), amount = listOf("amount"),
                               filters = listOf("government", "level"), page = "compare"),
        "budget-years" to DatasetSpec(Section.WHERE_IT_GOES, "chart.bar.xaxis", title = listOf("name"), subtitle = listOf("government", "fy", "section"), amount = listOf("amount"),
                              filters = listOf("government", "fy", "basis", "section"), page = "public-money/budget-compare"),
        "checkbook-payments" to DatasetSpec(Section.WHERE_IT_GOES, "checkmark.rectangle", title = listOf("payee"), subtitle = listOf("government", "description"), amount = listOf("amount"),
                                    date = listOf("paid_on"), summable = true, filters = listOf("government", "fiscal_year", "fund", "payee_kind")),
        "budget-actuals" to DatasetSpec(Section.WHERE_IT_GOES, "gauge.with.dots.needle.33percent", title = listOf("description", "account"), subtitle = listOf("government", "department", "as_of"),
                                amount = listOf("actual_ytd"), date = listOf("as_of"), filters = listOf("government", "fiscal_year", "department", "line_type")),
        "government-years" to DatasetSpec(Section.WHERE_IT_GOES, "calendar", title = listOf("government"), subtitle = listOf("fy", "budget_status"), detail = "budget_note",
                                  amount = listOf("budget_total"), filters = listOf("government", "fy"), page = "governments"),
        "budget-per-resident" to DatasetSpec(Section.WHERE_IT_GOES, "person.2", title = listOf("service"), subtitle = listOf("government"),
                                     amount = listOf("per_resident"), filters = listOf("government", "service"), page = "compare"),
        "cra-payments" to DatasetSpec(Section.WHERE_IT_GOES, "building.2", title = listOf("purpose"), subtitle = listOf("cra", "date_or_fy"), detail = "payee",
                              amount = listOf("amount"), date = listOf("date_end", "date_start"), badge = "status",
                              filters = listOf("cra", "status", "category", "district"), page = "public-money/cra-spending"),
        "cra-agencies" to DatasetSpec(Section.WHERE_IT_GOES, "percent", title = listOf("cra"), subtitle = listOf("city", "base_year"), detail = "sunset_basis",
                              amount = listOf("increment_fy2025"), filters = listOf("city"), page = "public-money/cra-tax-increment"),
        "cra-increment-checks" to DatasetSpec(Section.WHERE_IT_GOES, "checkmark.seal", title = listOf("figure"), subtitle = listOf("fiscal_year"),
                                      amount = listOf("official_figure", "estimate"), page = "public-money/cra-tax-increment"),
        "cra-tax-increment" to DatasetSpec(Section.WHERE_IT_GOES, "chart.bar.xaxis", title = listOf("cra"), subtitle = listOf("fy", "basis"),
                                   amount = listOf("increment"), badge = "scenario", filters = listOf("cra", "scenario", "fy"), page = "public-money/cra-tax-increment"),
        "sales-tax-projects" to DatasetSpec(Section.WHERE_IT_GOES, "road.lanes", title = listOf("name"), subtitle = listOf("government", "category"),
                                    amount = listOf("actual_cost", "programmed_cost", "promised_cost"), date = listOf("date_end"), badge = "status",
                                    filters = listOf("government", "category", "status"), page = "public-money/sales-tax-projects"),
        "development-projects" to DatasetSpec(Section.WHERE_IT_GOES, "building.2", title = listOf("name"), subtitle = listOf("government", "description", "location"), detail = "size",
                                      date = listOf("applied_date", "approved_date"), badge = "status", filters = listOf("government", "status"), page = "development"),
        "housing-permits" to DatasetSpec(Section.WHERE_IT_GOES, "house", title = listOf("area"), subtitle = listOf("period"), detail = "summary", amount = listOf("total_value"),
                                 date = listOf("year"), filters = listOf("area", "year"), page = "development"),
        "road-contracts" to DatasetSpec(Section.WHERE_IT_GOES, "road.lanes", title = listOf("description"), subtitle = listOf("contractor", "contract_type"), detail = "roads",
                                amount = listOf("amount"), date = listOf("let_date"), badge = "status", filters = listOf("status", "contract_type"), page = "roads"),
        "road-work-program" to DatasetSpec(Section.WHERE_IT_GOES, "calendar.badge.clock", title = listOf("description"), subtitle = listOf("phase", "work_type"), detail = "project_status",
                                   date = listOf("first_fiscal_year"), badge = "phase", filters = listOf("phase", "work_type", "project_status"), page = "roads"),
        "fema-michael-projects" to DatasetSpec(Section.WHERE_IT_GOES, "hurricane", title = listOf("title"), subtitle = listOf("applicant", "category"),
                                       amount = listOf("federal_share", "eligible_amount"), date = listOf("last_obligated", "first_obligated"),
                                       badge = "status", filters = listOf("applicant", "status", "category"), page = "public-money/hurricane-michael"),
        // Accountability
        "contracts" to DatasetSpec(Section.ACCOUNTABILITY, "signature", title = listOf("vendor"), subtitle = listOf("government", "date"), detail = "purpose",
                           amount = listOf("amount"), date = listOf("date"), filters = listOf("government", "method"), page = "public-money/contracts"),
        "change-orders" to DatasetSpec(Section.ACCOUNTABILITY, "arrow.triangle.2.circlepath", title = listOf("project"), subtitle = listOf("vendor", "date"),
                               detail = "reason", amount = listOf("change_amount"), date = listOf("date"),
                               filters = listOf("government"), page = "public-money/contracts"),
        "emergency-purchases" to DatasetSpec(Section.ACCOUNTABILITY, "exclamationmark.triangle", title = listOf("purpose"), subtitle = listOf("vendor", "date"),
                                     detail = "basis", amount = listOf("amount"), date = listOf("date"),
                                     filters = listOf("government"), page = "public-money/contracts"),
        "accountability-projects" to DatasetSpec(Section.ACCOUNTABILITY, "checklist", title = listOf("project"), subtitle = listOf("government", "stage"),
                                         detail = "flags", amount = listOf("latest_figure", "project_total", "first_figure"), date = listOf("last_date"),
                                         badge = "stage", filters = listOf("government", "kind", "stage"), page = "public-money/accountability"),
        "accountability-events" to DatasetSpec(Section.ACCOUNTABILITY, "calendar.badge.clock", title = listOf("project"), subtitle = listOf("event", "date"),
                                       detail = "description", amount = listOf("amount"), date = listOf("sort_date"),
                                       filters = listOf("government", "event"), page = "public-money/accountability"),
        "savings-opportunities" to DatasetSpec(Section.ACCOUNTABILITY, "dollarsign.arrow.circlepath", title = listOf("title"), subtitle = listOf("government", "lever"),
                                       detail = "next_step", amount = listOf("savings_high", "in_play"), badge = "confidence",
                                       filters = listOf("government", "lever", "confidence"), page = "governments"),
        "savings-evidence" to DatasetSpec(Section.ACCOUNTABILITY, "doc.text.magnifyingglass", title = listOf("label"), subtitle = listOf("group_title"),
                                  detail = "paid_to", amount = listOf("amount", "compare"), filters = listOf("opportunity_id", "kind"),
                                  page = "governments"),
        "votes" to DatasetSpec(Section.ACCOUNTABILITY, "hand.raised", title = listOf("headline"), subtitle = listOf("board", "date"), detail = "summary",
                       amount = listOf("amount"), date = listOf("date"), badge = "tally", filters = listOf("board", "category", "outcome", "split"),
                       page = "public-money/votes"),
        "contract-dollar-totals" to DatasetSpec(Section.ACCOUNTABILITY, "dollarsign.square", title = listOf("member"), subtitle = listOf("gov_id", "yes_votes"),
                              amount = listOf("yes_total"), filters = listOf("gov_id"), page = "people"),
        "member-contract-dollars" to DatasetSpec(Section.ACCOUNTABILITY, "dollarsign.square", title = listOf("headline"), subtitle = listOf("member", "date"),
                              amount = listOf("amount"), date = listOf("date"), badge = "vote", filters = listOf("board", "member", "vote", "kind"), page = "people"),
        "contract-vote-dollars" to DatasetSpec(Section.ACCOUNTABILITY, "dollarsign.square", title = listOf("headline"), subtitle = listOf("board", "date"), detail = "not_counted_reason",
                              amount = listOf("amount"), date = listOf("date"), badge = "kind", filters = listOf("board", "counted", "kind", "outcome"), page = "public-money/votes"),
        "member-votes" to DatasetSpec(Section.ACCOUNTABILITY, "person.crop.square", title = listOf("headline"), subtitle = listOf("member", "date"),
                              date = listOf("date"), badge = "vote", filters = listOf("board", "member", "vote"), page = "public-money/votes"),
        "vendor-payments" to DatasetSpec(Section.ACCOUNTABILITY, "dollarsign.circle", title = listOf("vendor"), subtitle = listOf("government", "payments"),
                                 amount = listOf("total"), filters = listOf("government"), page = "public-money/tourist-tax"),
        "debt" to DatasetSpec(Section.ACCOUNTABILITY, "creditcard", title = listOf("government"), subtitle = listOf("fy"), detail = "total_debt_note",
                      amount = listOf("total_debt"), page = "compare"),
        "bonds" to DatasetSpec(Section.ACCOUNTABILITY, "banknote", title = listOf("series"), subtitle = listOf("issuer", "dated_date"), detail = "purpose",
                       amount = listOf("outstanding", "par_amount"), date = listOf("dated_date"), badge = "type", filters = listOf("gov", "type", "status"),
                       page = "compare"),
        "audit-findings" to DatasetSpec(Section.ACCOUNTABILITY, "magnifyingglass", title = listOf("finding"), subtitle = listOf("government", "fy"),
                                detail = "plain_english", date = listOf("date_end"), badge = "repeat", filters = listOf("government", "fy", "repeat"),
                                page = "governments"),
        // People and pay
        "officials-pay" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.text.rectangle", title = listOf("name", "title"), subtitle = listOf("title", "government"),
                               amount = listOf("annual"), filters = listOf("government"), page = "people"),
        "salary-leaders" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.crop.circle.badge.checkmark", title = listOf("name"), subtitle = listOf("title", "employer"),
                                amount = listOf("salary"), date = listOf("as_of"), filters = listOf("employer", "department"), page = "people"),
        "board-appointments" to DatasetSpec(Section.PEOPLE_AND_PAY, "signature", title = listOf("person"), subtitle = listOf("board", "government"), detail = "seat",
                                  filters = listOf("government", "board"), page = "people"),
        "fee-changes" to DatasetSpec(Section.WHAT_YOU_PAY, "doc.plaintext", title = listOf("fee"), subtitle = listOf("government", "effective_date"), detail = "adopted_by",
                                  amount = listOf("new_amount"), filters = listOf("government", "category"), page = "public-money/fees-and-bills"),
        "salary-positions" to DatasetSpec(Section.PEOPLE_AND_PAY, "briefcase", title = listOf("title"), subtitle = listOf("employer", "department"),
                                  amount = listOf("pay_max", "pay_mid", "pay_min"), filters = listOf("employer", "category", "fiscal_year"),
                                  page = "people"),
        // Elections
        "elections" to DatasetSpec(Section.ELECTIONS, "checkmark.seal", title = listOf("name"), subtitle = listOf("date", "kind"), date = listOf("date"), badge = "status", filters = listOf("kind", "status"), page = "elections/results"),
        "election-results" to DatasetSpec(Section.ELECTIONS, "chart.bar", title = listOf("choice"), subtitle = listOf("office", "election_name"), date = listOf("election_date"), badge = "level", filters = listOf("election_date", "level", "gov_id"), page = "elections/results"),
        "election-dates" to DatasetSpec(Section.ELECTIONS, "calendar", title = listOf("title"), subtitle = listOf("election", "kind"), date = listOf("date"), badge = "kind", filters = listOf("kind"), page = "elections/voting"),
        "voting-locations" to DatasetSpec(Section.ELECTIONS, "mappin.and.ellipse", title = listOf("name"), subtitle = listOf("address", "city"), detail = "hours", badge = "kind", filters = listOf("kind", "city"), page = "elections/voting"),
        "public-notices" to DatasetSpec(Section.MORE, "megaphone", title = listOf("title"), subtitle = listOf("agency", "kind_label"), detail = "text", date = listOf("published"), badge = "kind_label", filters = listOf("agency", "kind"), page = "notices"),
        "job-openings" to DatasetSpec(Section.MORE, "briefcase", title = listOf("title"), subtitle = listOf("employer", "department"), detail = "pay", date = listOf("posted"), badge = "job_type", filters = listOf("employer", "job_type"), page = "jobs"),
        "job-boards" to DatasetSpec(Section.MORE, "building.2", title = listOf("employer"), subtitle = listOf("note"), page = "jobs"),
        "candidates-2026" to DatasetSpec(Section.ELECTIONS, "checkmark.seal", title = listOf("candidate"), subtitle = listOf("office", "party"),
                                 amount = listOf("total_raised"), badge = "status", filters = listOf("office", "government", "status"), page = "elections"),
        "campaign-finance" to DatasetSpec(Section.ELECTIONS, "chart.bar", title = listOf("official"), subtitle = listOf("office", "election"),
                                  amount = listOf("total_raised"), filters = listOf("gov", "election"), page = "connections/campaign-gifts"),
        "campaign-contributions-2026" to DatasetSpec(Section.ELECTIONS, "envelope", title = listOf("contributor"), subtitle = listOf("candidate", "date"),
                                             amount = listOf("amount"), date = listOf("date"), badge = "contributor_type",
                                             filters = listOf("candidate", "contributor_type"), page = "connections/campaign-gifts"),
        "campaign-history" to DatasetSpec(Section.ELECTIONS, "clock.arrow.circlepath", title = listOf("candidate"), subtitle = listOf("office", "election_year"),
                                  amount = listOf("total_raised"), date = listOf("election_date"), badge = "outcome",
                                  filters = listOf("election_year", "government", "outcome"), page = "elections/past"),
        "campaign-contributions-history" to DatasetSpec(Section.ELECTIONS, "envelope", title = listOf("contributor"), subtitle = listOf("candidate", "date"),
                                                amount = listOf("amount"), date = listOf("date"), badge = "contributor_type",
                                                filters = listOf("election_year", "candidate", "contributor_type"), page = "elections/past"),
        "donor-contracts" to DatasetSpec(Section.ELECTIONS, "link", title = listOf("vendor", "contributor"), subtitle = listOf("candidate", "contract_government"),
                                 amount = listOf("contribution_amount"), badge = "match_confidence",
                                 filters = listOf("candidate", "contract_government", "match_confidence"), page = "connections/campaign-gifts"),
        "business-donor-sunbiz" to DatasetSpec(Section.ELECTIONS, "building.2", title = listOf("contributor"), subtitle = listOf("candidate", "sunbiz_entity_name"),
                                       detail = "sunbiz_doc_number", amount = listOf("contribution_amount"), date = listOf("last_date"), badge = "match_method",
                                       filters = listOf("candidate", "sunbiz_status", "match_method"), page = "connections/campaign-gifts"),
        "shared-owner-groups" to DatasetSpec(Section.ELECTIONS, "person.2", title = listOf("business"), subtitle = listOf("candidate", "office"),
                                     detail = "business_dates", badge = "business_status", filters = listOf("candidate"), page = "connections/shared-owners"),
        "over-limit-gifts" to DatasetSpec(Section.ELECTIONS, "exclamationmark.triangle", title = listOf("contributor"), subtitle = listOf("candidate", "election"),
                                  detail = "gift_list", badge = "status", filters = listOf("candidate", "status"), page = "connections/shared-owners"),
        // Where the records overlap
        "vote-mentions" to DatasetSpec(Section.ACCOUNTABILITY, "text.magnifyingglass", title = listOf("entity_name"), subtitle = listOf("board", "date"), detail = "headline", amount = listOf("amount"), date = listOf("date"), badge = "outcome", filters = listOf("board", "entity_kind", "outcome"), page = "public-money/votes"),
        "donor-votes" to DatasetSpec(Section.ACCOUNTABILITY, "link", title = listOf("member"), subtitle = listOf("company", "date"), detail = "headline", amount = listOf("gift_amount"), date = listOf("date"), badge = "member_vote", filters = listOf("board", "member", "gift_timing"), page = "public-money/votes"),
        "agenda-parties" to DatasetSpec(Section.ACCOUNTABILITY, "list.bullet.rectangle", title = listOf("entity_name", "party"), subtitle = listOf("board", "meeting_date"), detail = "title", amount = listOf("amount"), date = listOf("meeting_date"), badge = "kind", filters = listOf("board", "kind"), page = "meetings"),
        "development-companies" to DatasetSpec(Section.ACCOUNTABILITY, "building.2", title = listOf("project"), subtitle = listOf("company", "status"), detail = "description", date = listOf("approved_date", "applied_date"), badge = "status", filters = listOf("status"), page = "development"),
        "bid-trail" to DatasetSpec(Section.ACCOUNTABILITY, "doc.text.magnifyingglass", title = listOf("notice_title"), subtitle = listOf("agency", "stage", "date"), detail = "what", date = listOf("date"), badge = "stage", filters = listOf("agency", "stage"), page = "notices"),
        "shared-owner-vendors" to DatasetSpec(Section.ACCOUNTABILITY, "person.2", title = listOf("company"), subtitle = listOf("officer"), detail = "match", amount = listOf("paid_by_this_government"), filters = listOf("officer"), page = "connections/shared-owners"),
        "chamber-overlaps" to DatasetSpec(Section.ACCOUNTABILITY, "storefront", title = listOf("person"), subtitle = listOf("chamber", "organization"), detail = "title", amount = listOf("organization_paid_by_governments"), badge = "role_group", filters = listOf("chamber", "role_group"), page = "chambers"),
        "emergency-purchase-donors" to DatasetSpec(Section.ACCOUNTABILITY, "exclamationmark.triangle", title = listOf("vendor"), subtitle = listOf("government", "date"), detail = "purpose", amount = listOf("amount"), date = listOf("date"), filters = listOf("government"), page = "public-money/contracts"),
        "campaign-results" to DatasetSpec(Section.ELECTIONS, "chart.bar", title = listOf("candidate"), subtitle = listOf("office", "election_date"), detail = "election", amount = listOf("total_raised"), date = listOf("election_date"), badge = "outcome", filters = listOf("office", "outcome"), page = "elections/past"),
        "schools" to DatasetSpec(Section.MORE, "graduationcap", title = listOf("name"), subtitle = listOf("level", "grades", "city"), amount = listOf("enrollment"),
                                 badge = "latest_grade", filters = listOf("status", "level", "charter", "city"), page = "schools"),
        "school-grades" to DatasetSpec(Section.MORE, "star", title = listOf("school"), subtitle = listOf("year"), badge = "grade",
                                       filters = listOf("year", "grade", "school"), page = "schools"),
        "school-grade-state" to DatasetSpec(Section.MORE, "star", title = listOf("school_type"), subtitle = listOf("school_year"), amount = listOf("schools_graded"),
                                            filters = listOf("school_year", "school_type"), page = "schools"),
        "school-bell-times" to DatasetSpec(Section.MORE, "clock", title = listOf("school", "part"), subtitle = listOf("part", "school_year"), detail = "note", badge = "kind",
                                           filters = listOf("kind", "group_name"), page = "schools"),
        "school-spending" to DatasetSpec(Section.MORE, "dollarsign.circle", title = listOf("school"), subtitle = listOf("year"), amount = listOf("total_per_student"),
                                         filters = listOf("year", "school"), page = "schools"),
        "school-enrollment" to DatasetSpec(Section.MORE, "person.3", title = listOf("school"), subtitle = listOf("school_year"), amount = listOf("enrollment"),
                                           filters = listOf("school_year", "school"), page = "schools"),
        "school-calendar" to DatasetSpec(Section.MORE, "calendar", title = listOf("title"), subtitle = listOf("venue"), date = listOf("starts"), badge = "kind",
                                         filters = listOf("kind", "school_year"), page = "schools"),
        "school-zones" to DatasetSpec(Section.MORE, "map", title = listOf("zone_name"), subtitle = listOf("level", "school"), amount = listOf("area_sq_mi"),
                                      filters = listOf("level"), page = "schools"),
        "volunteer-needs" to DatasetSpec(Section.ACCOUNTABILITY, "hand.raised", title = listOf("title"), subtitle = listOf("organization", "city"), detail = "description",
                                 date = listOf("starts"), badge = "cause", filters = listOf("cause", "board", "city"), page = "volunteer"),
        "volunteer-orgs" to DatasetSpec(Section.ACCOUNTABILITY, "heart.text.square", title = listOf("name"), subtitle = listOf("cause", "city"), detail = "mission",
                                amount = listOf("revenue"), badge = "cause", filters = listOf("cause", "city"), page = "volunteer"),
        "military-installations" to DatasetSpec(Section.ACCOUNTABILITY, "shield", title = listOf("name"), subtitle = listOf("branch", "host_unit"), detail = "mission",
                                                badge = "branch", page = "military"),
        "military-news" to DatasetSpec(Section.ACCOUNTABILITY, "newspaper", title = listOf("title"), subtitle = listOf("installation", "unit"), detail = "summary",
                                       date = listOf("published"), badge = "installation", filters = listOf("installation", "unit"), page = "military"),
        "federal-contracts" to DatasetSpec(Section.ACCOUNTABILITY, "doc.text", title = listOf("recipient"), subtitle = listOf("sub_agency", "recipient_city"), detail = "description",
                                           amount = listOf("obligated"), date = listOf("last_action_date"), badge = "agency", filters = listOf("agency", "sub_agency", "recipient_city"), page = "military"),
        "federal-contract-years" to DatasetSpec(Section.ACCOUNTABILITY, "chart.bar", title = listOf("recipient"), subtitle = listOf("sub_agency"),
                                                amount = listOf("obligated"), badge = "year", filters = listOf("year", "agency", "sub_agency"), page = "military"),
        "safety-agencies" to DatasetSpec(Section.ACCOUNTABILITY, "shield.lefthalf.filled", title = listOf("agency"), subtitle = listOf("government", "service"), detail = "arrangement",
                                         amount = listOf("budget_amount"), badge = "service", filters = listOf("government", "service"), page = "public-safety"),
        "crime-counts" to DatasetSpec(Section.ACCOUNTABILITY, "chart.bar", title = listOf("agency"), subtitle = listOf("offense", "year"), detail = "reporting",
                                      badge = "year", filters = listOf("agency", "offense", "year"), page = "public-safety"),
        "crime-monthly" to DatasetSpec(Section.ACCOUNTABILITY, "calendar", title = listOf("agency"), subtitle = listOf("offense", "period"),
                                       badge = "period", filters = listOf("agency", "offense", "year"), page = "public-safety"),
        "police-staffing" to DatasetSpec(Section.ACCOUNTABILITY, "person.3", title = listOf("agency"), subtitle = listOf("year"),
                                         badge = "year", filters = listOf("agency", "year"), page = "public-safety"),
        "chambers" to DatasetSpec(Section.ACCOUNTABILITY, "storefront", title = listOf("name"), subtitle = listOf("serves"), detail = "about",
                          amount = listOf("revenue"), badge = "tax_status", page = "chambers"),
        "chamber-leaders" to DatasetSpec(Section.ACCOUNTABILITY, "person.3", title = listOf("person_name"), subtitle = listOf("chamber", "title", "organization"),
                                 badge = "role_group", filters = listOf("chamber", "role_group"), page = "chambers"),
        "chamber-events" to DatasetSpec(Section.ACCOUNTABILITY, "calendar", title = listOf("title"), subtitle = listOf("chamber", "venue", "schedule"), detail = "about",
                                date = listOf("starts"), badge = "category", filters = listOf("chamber", "kind", "category"), page = "chambers"),
        "community-events" to DatasetSpec(Section.MORE, "calendar", title = listOf("title"), subtitle = listOf("town", "venue", "source"),
                                  date = listOf("starts"), badge = "category", filters = listOf("town", "category", "source"), page = "events"),
        "restaurants" to DatasetSpec(Section.ACCOUNTABILITY, "fork.knife", title = listOf("business_name"), subtitle = listOf("kind", "city", "licensee"), detail = "last_result",
                             date = listOf("last_inspection"), badge = "last_result_level", filters = listOf("city", "kind", "last_result_level", "licensed_now"), page = "restaurants"),
        "restaurant-inspections" to DatasetSpec(Section.ACCOUNTABILITY, "checklist", title = listOf("business_name"), subtitle = listOf("city", "inspection_type"), detail = "violation_items",
                                        date = listOf("date"), badge = "result", filters = listOf("result_level", "inspection_type", "city"), page = "restaurants"),
        "new-businesses" to DatasetSpec(Section.ACCOUNTABILITY, "storefront", title = listOf("name"), subtitle = listOf("filing_type", "city"), detail = "restaurants",
                                date = listOf("filed_date"), badge = "status", filters = listOf("city", "filing_type", "status", "filed_month"), page = "new-businesses"),
        "weekly-roundup" to DatasetSpec(Section.MORE, "envelope", title = listOf("title"), subtitle = listOf("government", "town", "venue"), detail = "summary",
                                amount = listOf("amount"), date = listOf("starts", "date"), badge = "section", filters = listOf("section", "government"), page = "this-week"),
        "nonprofits" to DatasetSpec(Section.ACCOUNTABILITY, "heart.text.square", title = listOf("name"), subtitle = listOf("kind", "city"), detail = "subsection",
                            amount = listOf("total_revenue", "irs_revenue"), badge = "latest_return_form", filters = listOf("kind", "city", "subsection"), page = "connections/nonprofits"),
        "nonprofit-board-members" to DatasetSpec(Section.ACCOUNTABILITY, "person.3", title = listOf("person"), subtitle = listOf("nonprofit", "titles"), detail = "sources",
                                         badge = "role", filters = listOf("nonprofit", "role"), page = "connections/nonprofits"),
        "nonprofit-board-businesses" to DatasetSpec(Section.ACCOUNTABILITY, "building.2", title = listOf("business"), subtitle = listOf("person", "match"), amount = listOf("campaign_gifts_total"),
                                            badge = "business_status", filters = listOf("person", "business_status"), page = "connections/nonprofits"),
        "nonprofit-payments" to DatasetSpec(Section.ACCOUNTABILITY, "banknote", title = listOf("nonprofit"), subtitle = listOf("payer", "what"), amount = listOf("amount"),
                                    badge = "record_type", filters = listOf("payer", "record_type"), page = "connections/nonprofits"),
        "nonprofit-grants" to DatasetSpec(Section.ACCOUNTABILITY, "gift", title = listOf("recipient"), subtitle = listOf("grantor", "purpose"), amount = listOf("cash"),
                                  filters = listOf("grantor", "tax_year"), page = "connections/nonprofits"),
        "charity-registrations" to DatasetSpec(Section.ACCOUNTABILITY, "checkmark.seal", title = listOf("name"), subtitle = listOf("status", "city"), detail = "fiscal_year_end",
                                       amount = listOf("total_revenue"), badge = "status", filters = listOf("status", "city"), page = "connections/nonprofits"),
        "nonprofit-officials" to DatasetSpec(Section.ACCOUNTABILITY, "person.crop.square", title = listOf("official"), subtitle = listOf("nonprofit", "titles"),
                                     badge = "sources", filters = listOf("official", "nonprofit"), page = "connections/nonprofits"),
        "business-officers" to DatasetSpec(Section.ELECTIONS, "person.text.rectangle", title = listOf("officer"), subtitle = listOf("title", "business"),
                                   detail = "sunbiz_doc_number", badge = "business_status", filters = listOf("business_status", "officer_kind"), page = "connections/business-ties"),
        "official-businesses" to DatasetSpec(Section.ELECTIONS, "briefcase", title = listOf("business"), subtitle = listOf("official", "official_role"),
                                     detail = "titles", badge = "business_status", filters = listOf("official"), page = "connections/business-ties"),
        "official-business-links" to DatasetSpec(Section.ELECTIONS, "link", title = listOf("detail"), subtitle = listOf("official"),
                                         detail = "link_type", badge = "link_type", filters = listOf("official", "link_type"), page = "connections/business-ties"),
        "money-map-gifts" to DatasetSpec(Section.ELECTIONS, "gift", title = listOf("donor"), subtitle = listOf("official", "office"), amount = listOf("amount"),
                                 badge = "donor_type", filters = listOf("official", "donor_type", "donor_holds_contracts_here"), page = "connections"),
        "money-map-contracts" to DatasetSpec(Section.ELECTIONS, "doc.text", title = listOf("donor"), subtitle = listOf("government"),
                                     amount = listOf("awarded_total", "paid_total"), filters = listOf("government", "likely_match_only"), page = "connections"),
        "money-map-votes" to DatasetSpec(Section.ELECTIONS, "hand.raised", title = listOf("item"), subtitle = listOf("official", "vote_date"), detail = "donor",
                                 amount = listOf("amount"), date = listOf("vote_date"), badge = "vote", filters = listOf("official", "vote", "gift_before_or_after_vote"),
                                 page = "connections"),
        // Connections (every government's payees, links and business gifts to officials)
        "connections-payees" to DatasetSpec(Section.WHERE_IT_GOES, "point.3.connected.trianglepath.dotted", title = listOf("name"), subtitle = listOf("kind", "records"),
                                    amount = listOf("dollars_in_records"), badge = "kind", filters = listOf("kind", "gave_to_campaigns"), page = "connections"),
        "connections-payments" to DatasetSpec(Section.WHERE_IT_GOES, "arrow.right", title = listOf("payee"), subtitle = listOf("payer", "record_type"), detail = "what",
                                      amount = listOf("amount"), badge = "record_type", filters = listOf("payer", "record_type"), page = "connections"),
        "connections-links" to DatasetSpec(Section.WHERE_IT_GOES, "arrow.left.arrow.right", title = listOf("name_a"), subtitle = listOf("name_b"), detail = "connection",
                                   page = "connections"),
        "connections-gifts" to DatasetSpec(Section.ELECTIONS, "gift", title = listOf("donor"), subtitle = listOf("official", "office"), amount = listOf("amount"),
                                   badge = "donor_type", filters = listOf("official", "donor_type", "candidate_2026"), page = "connections"),
        "owner-gifts" to DatasetSpec(Section.ELECTIONS, "person.text.rectangle", title = listOf("donor"), subtitle = listOf("candidate", "businesses"), amount = listOf("amount"),
                             date = listOf("last_date"), filters = listOf("candidate", "office"), page = "connections/campaign-gifts"),
        // Entity profiles (every person, company, nonprofit and government, and how they connect)
        // Emergencies and hurricane prep
        "evacuation-zones" to DatasetSpec(Section.MORE, "map", title = listOf("zone"), subtitle = listOf("where_it_is"), detail = "when_ordered", page = "emergency"),
        "emergency-shelters" to DatasetSpec(Section.MORE, "house.lodge", title = listOf("name"), subtitle = listOf("address", "group_name"), detail = "note", badge = "status", filters = listOf("shelter_type", "status", "evacuation_zone"), page = "emergency"),
        "emergency-resources" to DatasetSpec(Section.MORE, "phone", title = listOf("name"), subtitle = listOf("group", "phone"), detail = "about", filters = listOf("group"), page = "emergency"),
        "emergency-notices" to DatasetSpec(Section.MORE, "exclamationmark.triangle", title = listOf("title"), subtitle = listOf("source", "kind"), detail = "summary", date = listOf("issued", "first_seen"), badge = "status", filters = listOf("kind", "source", "status"), page = "emergency"),
        "hurricane-prep" to DatasetSpec(Section.MORE, "checklist", title = listOf("step"), subtitle = listOf("topic", "source"), detail = "text", filters = listOf("topic"), page = "hurricane-prep"),
        "disaster-declarations" to DatasetSpec(Section.MORE, "hurricane", title = listOf("title"), subtitle = listOf("kind", "incident_type"), date = listOf("declared"), badge = "kind", filters = listOf("kind", "incident_type"), page = "hurricane-prep"),
        "rebuild-money" to DatasetSpec(Section.MORE, "house.and.flag", title = listOf("area_name", "zip"), subtitle = listOf("zip", "program", "event"), amount = listOf("amount_paid"), date = listOf("year"), badge = "program", filters = listOf("program", "event", "zip", "year"), page = "hurricane-prep"),
        "entity-profiles" to DatasetSpec(Section.MORE, "person.crop.circle", title = listOf("name"), subtitle = listOf("kind_label", "subtitle"),
                                 amount = listOf("amount_received", "amount_given"), badge = "kind_label", filters = listOf("kind_label"), page = "people"),
        "entity-connections" to DatasetSpec(Section.MORE, "point.3.connected.trianglepath.dotted", title = listOf("from_name"), subtitle = listOf("relation_label", "to_name"),
                                    detail = "detail", amount = listOf("amount"), date = listOf("last_date"), badge = "relation",
                                    filters = listOf("relation", "from_kind", "to_kind"), page = "connections"),
        // Reference
        "tax-districts" to DatasetSpec(Section.WHAT_YOU_PAY, "map", title = listOf("label"), subtitle = listOf("district"), amount = listOf("total_millage"),
                               page = "public-money/tax-dollars"),
        "vendors-directory" to DatasetSpec(Section.MORE, "building.2", title = listOf("name"), subtitle = listOf("vendor_type"), filters = listOf("vendor_type"),
                                   page = "public-money/vendors"),
        "people-directory" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.3", title = listOf("name"), subtitle = listOf("district"), page = "people"),
        // who held each elected seat since 2016 (the site's first year); a row with no name is a vacancy or a stretch nobody could confirm, so it falls back to the seat
        "officeholder-terms" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.badge.clock", title = listOf("person_name", "seat"), subtitle = listOf("government", "seat"), detail = "note",
                                    date = listOf("date_start", "date_end"), badge = "how", filters = listOf("government", "seat", "how"), page = "people"),
        // official headshots its government publishes, one row per person (the photo shows on People rows and person screens)
        "official-photos" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.3", title = listOf("name"), subtitle = listOf("credit"), detail = "source_url", date = listOf("fetched_on"), page = "people"),
        "person-photos" to DatasetSpec(Section.PEOPLE_AND_PAY, "person.crop.circle", title = listOf("name"), subtitle = listOf("credit"), detail = "source_url", date = listOf("fetched_on"),
                               filters = listOf("published_by"), page = "people"),
        "glossary-terms" to DatasetSpec(Section.MORE, "book", title = listOf("term"), subtitle = listOf("group_name"), detail = "simple", filters = listOf("group_name"),
                                page = "glossary"),
        "site-updates" to DatasetSpec(Section.MORE, "sparkles", title = listOf("title"), subtitle = listOf("date"), detail = "text", date = listOf("date"), page = "updates"),
        "site-menu" to DatasetSpec(Section.MORE, "list.bullet", title = listOf("label"), subtitle = listOf("section", "lang"), detail = "description",
                           filters = listOf("section", "lang")),
        "data-sources" to DatasetSpec(Section.MORE, "doc.text.magnifyingglass", title = listOf("source_name"), subtitle = listOf("government", "topic"), detail = "what_we_take",
                              badge = "method", filters = listOf("topic", "government", "method"), page = "data-sources"),
        "data-freshness" to DatasetSpec(Section.MORE, "clock", title = listOf("figure"), subtitle = listOf("topic", "latest_period"), detail = "next_due",
                                        badge = "status", filters = listOf("topic", "status"), page = "data-sources"),
        "data-source-sites" to DatasetSpec(Section.MORE, "globe", title = listOf("website"), subtitle = listOf("topic"), detail = "topic",
                                   filters = listOf("topic"), page = "data-sources"),
        // how much of each government's records since 2016 are on file, per portion; status is complete / partial / missing
        "beach-access" to DatasetSpec(Section.MORE, "beach.umbrella", title = listOf("name"), subtitle = listOf("address", "area"), badge = "area",
                              filters = listOf("area", "wheelchair_access", "vehicle_access"), page = "beaches"),
        "beach-parking" to DatasetSpec(Section.MORE, "parkingsign", title = listOf("nearest_access"), subtitle = listOf("parking_type"), badge = "spaces", page = "beaches"),
        "beach-water-sites" to DatasetSpec(Section.MORE, "drop", title = listOf("name"), subtitle = listOf("latest_date"), badge = "latest_rating",
                                   filters = listOf("latest_rating"), page = "beaches"),
        "beach-water-samples" to DatasetSpec(Section.MORE, "testtube.2", title = listOf("site"), subtitle = listOf("reported"), date = listOf("date"), badge = "rating",
                                     filters = listOf("site", "rating"), page = "beaches"),
        "beach-conditions" to DatasetSpec(Section.MORE, "flag", title = listOf("period", "flag_color"), subtitle = listOf("rip_current_risk", "surf_height", "meaning"),
                                  detail = "summary", badge = "kind", filters = listOf("kind"), page = "beaches"),
        "parks" to DatasetSpec(Section.MORE, "tree", title = listOf("name"), subtitle = listOf("run_by", "address"), detail = "facilities", badge = "kind",
                       filters = listOf("run_by", "kind"), page = "parks"),
        "boat-ramps" to DatasetSpec(Section.MORE, "sailboat", title = listOf("name"), subtitle = listOf("waterbody", "run_by"), badge = "water",
                            filters = listOf("run_by", "water"), page = "parks"),
        "trails" to DatasetSpec(Section.MORE, "figure.hiking", title = listOf("name"), subtitle = listOf("area", "surface"), badge = "skill_level", filters = listOf("area"), page = "parks"),
        "recreation-departments" to DatasetSpec(Section.MORE, "figure.run", title = listOf("name"), subtitle = listOf("run_by"), page = "parks"),
        "data-completeness" to DatasetSpec(Section.MORE, "checklist", title = listOf("portion"), subtitle = listOf("government", "period"), detail = "missing",
                                   badge = "status", filters = listOf("government", "portion", "status"), page = "governments"),
        )

        /** Datasets the app shows in their own tabs rather than in Explore. */
        val ownScreens = setOf("government-profiles", "meetings")

        fun forId(id: String): DatasetSpec = known[id] ?: DatasetSpec(
            Section.MORE, "tablecells", title = listOf("name", "title", "headline", "government", "vendor"),
            subtitle = listOf("government", "date", "fy"), amount = listOf("amount", "total"), date = listOf("date"), page = "open-data",
        )

        /** Identifier and housekeeping columns that aren't useful to read. */
        val hiddenColumns = setOf(
            "gov_id", "vendor_id", "vendor_ids", "person_id", "record_id", "vote_ids", "vote_id", "contract_ids",
            "vote_match_method", "contract_match_method", "schedule_match_method", "date_start", "date_end", "date_precision",
            "lat", "lng", "authority_id", "employer_id", "race_id", "service_id", "members", "page", "id",
            "created_at", "updated_at", "fte_only",
        )

        fun sourceURL(row: Row): String? {
            for (key in listOf("source_url", "report_url", "finance_report_url", "official_statement_url", "detail_url", "agenda_url")) {
                row.url(key)?.let { return it }
            }
            return row.strings("sources").firstOrNull { it.startsWith("http") }
        }

        /** Every readable field, labelled and formatted, in catalog order. */
        fun fields(row: Row, columns: List<DatasetInfo.Column>): List<Pair<String, String>> {
            val names = if (columns.isEmpty()) row.values.keys.sorted() else columns.map { it.name }
            return names.mapNotNull { name ->
                if (name in hiddenColumns || name.endsWith("_url")) return@mapNotNull null
                val v = row[name] ?: return@mapNotNull null
                if (v.isEmptyValue) return@mapNotNull null
                Format.label(name) to Format.value(v, name)
            }
        }
    }
}
