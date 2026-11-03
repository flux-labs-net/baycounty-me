package me.baycounty.kit

/**
 * The parts of a government screen. The screen itself shows the year, "At a glance" and one row per part that has
 * records for that government; each row opens that part on its own screen, for the same year, so the screen
 * doesn't run on as one long page. Mirrors ios BayCountyKit GovParts.swift.
 */
enum class GovPart(val id: String, val title: String, val symbol: String) {
    WHO("who", "Who's in charge", "person.3"),
    MONEY("money", "Money in, money out", "chart.pie"),
    COMPARE("compare", "Compared with the others", "chart.bar.xaxis"),
    MEETINGS("meetings", "Upcoming meetings", "calendar"),
    DEBT("debt", "Debt", "creditcard"),
    AUDITS("audits", "What the auditors found", "magnifyingglass"),
    SAVINGS("savings", "Where it could spend less", "dollarsign.arrow.circlepath"),
    CRA("cra", "Redevelopment (CRA)", "building.2"),
    RECORDS("records", "Every record", "tray.full");

    companion object {
        fun of(id: String): GovPart? = entries.firstOrNull { it.id == id }

        /** The parts to list, in screen order: only those with records ([has]); "Compared with the others" always. */
        fun shown(has: (GovPart) -> Boolean): List<GovPart> = entries.filter { it == COMPARE || has(it) }
    }
}
