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
        "salary-positions" to DatasetSpec(Section.PEOPLE_AND_PAY, "briefcase", title = listOf("title"), subtitle = listOf("employer", "department"),
                                  amount = listOf("pay_max", "pay_mid", "pay_min"), filters = listOf("employer", "category", "fiscal_year"),
                                  page = "people"),
        // Elections
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
        "glossary-terms" to DatasetSpec(Section.MORE, "book", title = listOf("term"), subtitle = listOf("group_name"), detail = "simple", filters = listOf("group_name"),
                                page = "glossary"),
        "site-updates" to DatasetSpec(Section.MORE, "sparkles", title = listOf("title"), subtitle = listOf("date"), detail = "text", date = listOf("date"), page = "updates"),
        "site-menu" to DatasetSpec(Section.MORE, "list.bullet", title = listOf("label"), subtitle = listOf("section", "lang"), detail = "description",
                           filters = listOf("section", "lang")),
        "data-sources" to DatasetSpec(Section.MORE, "doc.text.magnifyingglass", title = listOf("source_name"), subtitle = listOf("government", "topic"), detail = "what_we_take",
                              badge = "method", filters = listOf("topic", "government", "method"), page = "data-sources"),
        "data-source-sites" to DatasetSpec(Section.MORE, "globe", title = listOf("website"), subtitle = listOf("topic"), detail = "topic",
                                   filters = listOf("topic"), page = "data-sources"),
        // how much of each government's records since 2016 are on file, per portion; status is complete / partial / missing
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
