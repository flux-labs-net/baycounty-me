package me.baycounty.kit

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.ZoneId
import java.time.ZonedDateTime

/** A government's year: budget lines for the year picked, and the "no data" note naming the nearest years and why.
 *  Same wording as site/gov.js and the Swift GovYearTests. */
class GovYearTest {
    private fun row(vararg kv: Pair<String, Any>) = Row(0, kv.associate { (k, v) ->
        k to when (v) { is Boolean -> JsonPrimitive(v); is Number -> JsonPrimitive(v); else -> JsonPrimitive(v.toString()) } as JsonElement
    })
    private val now = ZonedDateTime.of(2026, 10, 31, 9, 0, 0, 0, ZoneId.of("America/Chicago")).toInstant()

    @Test fun budgetForTheYearOnly() {
        val rows = listOf(
            row("gov_id" to "lh", "fiscal_year" to 2022, "basis" to "adopted", "section" to "total", "line_key" to "total", "name" to "Total budget", "amount" to 57_100_000, "status" to "adopted"),
            row("gov_id" to "lh", "fiscal_year" to 2022, "basis" to "adopted", "section" to "department", "line_key" to "d:pd", "name" to "Police", "amount" to 4_000_000),
            row("gov_id" to "lh", "fiscal_year" to 2022, "basis" to "actual", "section" to "revenue", "line_key" to "r:x", "name" to "Borrowing", "amount" to 9, "in_total" to false),
            row("gov_id" to "lh", "fiscal_year" to 2023, "basis" to "adopted", "section" to "department", "line_key" to "d:pd", "name" to "Police", "amount" to 5_000_000),
        )
        val b = GovYear.budget(rows, "lh", 2022)
        assertEquals(57_100_000.0, b.total!!, 0.1)
        assertEquals(listOf(GovYear.Line("Police", 4_000_000.0)), b.departments)
        assertEquals(emptyList<GovYear.Line>(), b.revenue)
        assertEquals(listOf(2022, 2023), GovYear.budgetYears(rows, "lh", "adopted"))
    }

    @Test fun gapNamesNearestYearAndWhy() {
        assertEquals("No FY2019 audit on file. Earliest we have: FY2023. The state Auditor General posts only the last five years of audits; older ones have to come from Lynn Haven.",
            GovYear.gap("audit", 2019, listOf(2023, 2024, 2025), GovYear.Kind.AUDIT, "lh", "Lynn Haven", now))
        assertEquals("No FY2022 audit on file. Earliest we have: FY2023. We haven't read it in yet; it is among the last five years of audits the state Auditor General posts online.",
            GovYear.gap("audit", 2022, listOf(2023, 2024, 2025), GovYear.Kind.AUDIT, "lh", "Lynn Haven", now))
        assertEquals("No FY2027 audit on file. Latest we have: FY2025. FY2027 runs to Sep 30, 2027; audited figures come only after the year ends.",
            GovYear.gap("audit", 2027, listOf(2025), GovYear.Kind.AUDIT, "lh", "Lynn Haven", now))
        assertEquals("No FY2019 adopted budget on file. Earliest we have: FY2020. Not in Lynn Haven's budget documents online or the state audit reports we have.",
            GovYear.gap("adopted budget", 2019, listOf(2020, 2021), GovYear.Kind.BUDGET, "lh", "Lynn Haven", now))
    }

    @Test fun fiscalYearOfAuditLabel() {
        assertEquals(2024, GovYear.fiscalYearOf("FY2024 (year ended 2024-09-30)"))
        assertEquals(2027, GovYear.years("lh", now).first())
        assertEquals(2016, GovYear.years("lh", now).last())
    }
}
