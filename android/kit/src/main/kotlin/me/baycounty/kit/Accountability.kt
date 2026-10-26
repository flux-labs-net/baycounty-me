@file:Suppress("PropertyName")

package me.baycounty.kit

import kotlinx.serialization.Serializable

/**
 * The Accountability console (/public-money/accountability), read from /data/accountability.json.
 * A flag is a question for the agency, not a finding of wrongdoing; the app's wording must stay that way.
 */
@Serializable
data class AccountabilityConsole(
    val about: String? = null,
    val rules: List<Rule> = emptyList(),
    val stats: Stats? = null,
    val projects: List<Project> = emptyList(),
) {
    @Serializable data class Rule(val id: String = "", val title: String = "", val `when`: String? = null, val means: String? = null, val not: String? = null)

    @Serializable
    data class Stats(
        val projects: Int? = null, val flagged: Int? = null, val flags: Int? = null, val gaps: Int? = null,
        val replied: Int? = null, val sent: Int? = null, val money: Double? = null,
    )

    @Serializable data class Figure(val a: Double? = null, val t: String? = null)

    @Serializable
    data class Event(
        val d: String? = null, val k: String = "", val a: Double? = null, val approx: Boolean? = null, val t: String = "",
        val payee: String? = null, val u: String? = null, val vid: String? = null, val s: String? = null, val side: Boolean? = null,
    ) {
        val id: String get() = (s ?: d ?: "") + "|" + k + "|" + t
        val url: String? get() = u
    }

    @Serializable data class Flag(val r: String = "", val sev: String? = null, val note: String = "") { val id: String get() = r + note }
    @Serializable data class Gap(val q: String = "") { val id: String get() = q }
    @Serializable data class Reply(val status: String? = null, val sent: String? = null, val date: String? = null, val text: String? = null, val u: String? = null)

    @Serializable
    data class Project(
        val id: String = "",
        val n: String = "",
        val gk: String? = null,
        val g: String? = null,
        val agency: String? = null,
        val where: String? = null,
        val what: String? = null,
        val funding: String? = null,
        val status: String? = null,
        val src: String? = null,
        val ev: List<Event> = emptyList(),
        val flags: List<Flag> = emptyList(),
        val gaps: List<Gap> = emptyList(),
        val base: Figure? = null,
        val now: Figure? = null,
        val total: Figure? = null,
        val growth: Double? = null,
        val late_days: Double? = null,
        val sev: String? = null,
        val reply: Reply? = null,
        val first: String? = null,
        val last: String? = null,
        val money: Double? = null,
        val vendor: String? = null,
    ) {
        /** The latest firm figure: final total, else current contract or estimate. */
        val latest: Figure? get() = total ?: now
        val stageLabel: String get() = stage(status)
        /** Timeline oldest to newest, as the site shows it. */
        val timeline: List<Event> get() = ev.sortedBy { it.s ?: it.d ?: "" }
    }

    fun rule(id: String): Rule? = rules.firstOrNull { it.id == id }

    /** Stages grouped for the list's filter. */
    enum class Phase(val label: String) {
        ACTIVE("In progress"), DONE("Finished"), STOPPED("Removed or sold");

        companion object {
            fun of(status: String?): Phase = when (status) {
                "complete", "closed", "phase-done" -> DONE
                "removed", "sale" -> STOPPED
                else -> ACTIVE
            }
        }
    }

    companion object {
        val stages = mapOf(
            "budgeted" to "Budgeted", "committed" to "Approved", "design" to "In design", "contract" to "Under contract",
            "construction" to "Under construction", "delayed" to "Delayed", "phase-done" to "Phase done", "complete" to "Complete",
            "closed" to "Closed out", "sale" to "Land sale", "removed" to "Removed", "unknown" to "Status unclear",
        )
        fun stage(s: String?): String = stages[s ?: ""] ?: "Status unclear"

        val kinds = mapOf(
            "budget" to "Budget", "estimate" to "Estimate", "approval" to "Approved", "award" to "Contract",
            "change" to "Change order", "vote" to "Vote", "payment" to "Payment", "spent" to "Spent to date", "complete" to "Done",
            "milestone" to "Milestone", "sale" to "Sale",
        )
        fun kind(k: String): String = kinds[k] ?: k.split(" ").joinToString(" ") { it.lowercase().capitalizeFirst() }

        fun source(s: String?): String = mapOf("reviewed" to "Reviewed history", "contracts" to "Contract", "surtax" to "Sales tax project")[s ?: ""] ?: "Project"

        fun reply(s: String?): String = mapOf(
            "not_sent" to "Not yet sent to the agency", "sent" to "Sent to the agency, awaiting a reply", "replied" to "Agency replied",
        )[s ?: ""] ?: "Not yet sent to the agency"
    }
}

suspend fun BayCountyClient.accountability(): Pair<AccountabilityConsole, BayCountyClient.Freshness> {
    val r = get("/data/accountability.json")
    return BCJson.decodeFromString(AccountabilityConsole.serializer(), r.data.decodeToString()) to r.freshness
}
