package me.baycounty.kit

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

class AgendaPeriodTest {
    private fun meeting(json: String) = Meeting(Row.decodeList(json)[0])

    @Test fun agendaJoinsAmountsAndDropsHeadings() {
        val m = meeting("""
        [{"board":"pc","title":"City Commission","start":"2026-10-27T16:30:00-05:00",
          "items":[{"title":"Consideration to purchase a Kaiser S8 Walking Telescopic Excavator for a cost of ${'$'}693,834.87.","amount":"${'$'}693,834.87"},
                   {"title":"Consideration of approval of eleven firms for Bid PC25-052.","amount":null}],
          "agenda_items":["Agenda - 10/27/2026 AGENDA CITY COMMISSION","Opening Prayer with Rev. Matt Thompson, Lead Pastor.","Consent Agenda",
                          "Consideration to purchase a Kaiser S8 Walking Telescopic Excavator for a cost of ${'$'}693,834.87.",
                          "Second and final of two public hearings on Ordinance 3315, an ordinance amending sec. 104-39.B.",
                          "Consideration and approval of a Right-of-Way Use Agreement with the Port Authority."]}]
        """)
        val a = m.agenda
        assertEquals(a.joinToString(" | ") { it.title }, 3, a.size)
        assertEquals(693_834.87, a[0].amount!!, 0.01)
        assertEquals(AgendaItem.Kind.SPENDING, a[0].kind)
        assertEquals(AgendaItem.Kind.HEARING, a[1].kind)
        assertEquals(AgendaItem.Kind.OTHER, a[2].kind)
        assertEquals("A Right-of-Way Use Agreement with the Port Authority", a[2].shortTitle)
        assertEquals(693_834.87, m.moneyTotal, 0.01)
    }

    @Test fun agendaFallsBackToMoneyItems() {
        val m = meeting("""[{"board":"lh","start":"2026-10-27","items":[{"title":"Award of bid to Mainline Construction in the amount of ${'$'}6,173,449.43.","amount":"${'$'}6,173,449.43"}]}]""")
        assertEquals(1, m.agenda.size)
        assertEquals("Award of bid to Mainline Construction in the amount of $6,173,449.43", m.agenda[0].shortTitle)
    }

    @Test fun parseAmount() {
        assertEquals(8020.66, AgendaItem.parseAmount("$8,020.66")!!, 0.001)
        assertEquals(1_200_000.0, AgendaItem.parseAmount("$1.2 million")!!, 0.001)
        assertNull(AgendaItem.parseAmount("TBD"))
    }

    @Test fun amendment3ReminderEndsAfterElectionDay() {
        val json = """{"districts":[],"auth":{},"groups":[],"second":0,"govs":[{"n":"A","levy":1,"imp":[1,30]},{"n":"B","levy":1,"imp":[2,13.7]}],"state":[],"vote":"2026-11-03"}"""
        val m = BCJson.decodeFromString(Amendment3Model.serializer(), json)
        assertEquals(43.7, m.localImpact(1), 0.001)
        assertTrue(m.isBeforeVote(Dates.parse("2026-11-03T20:00:00-06:00")!!))
        assertFalse(m.isBeforeVote(Dates.parse("2026-11-04T08:00:00-06:00")!!))
    }

    private fun row(vararg kv: Pair<String, String>) = Row(0, kv.associate { it.first to JsonPrimitive(it.second) })
    private val oct22 = Instant.parse("2026-10-22T12:00:00Z")

    @Test fun recordYears() {
        assertEquals(Period(2026, false), Period.of(row("date" to "2026-03-10")))
        assertEquals(Period(2026, true), Period.of(row("date_start" to "2025-10-01", "date_end" to "2026-09-30", "fy" to "FY2026")))
        assertEquals(Period(2026, false), Period.of(row("date_start" to "2026-10-21", "date_end" to "2026-10-21")))
        assertEquals(Period(2026, true), Period.of(row("fiscal_year" to "FY2025-26")))
        assertEquals(Period(2025, false), Period.of(row("tax_year" to "2025")))
        assertEquals(Period(2024, false), Period.of(row("election" to "2024 primary/general")))
        assertNull(Period.of(row("name" to "No date")))
        assertEquals(Period(2027, true), Period.of(row("as_of" to "FY2026-27")))
        val idx = Period.Index(listOf(
            row("date_end" to "2026-09-30", "date_start" to "2025-10-01"), row("date_end" to "2025-09-30", "date_start" to "2024-10-01"), row("date" to "2025-11-04"),
        ))
        assertTrue(idx.fiscal)
        assertEquals(listOf("FY2026", "FY2025"), idx.periods.map { it.label })
    }

    @Test fun defaultPeriod() {
        assertEquals(2026, Period.defaultPeriod(listOf(2026, 2025, 2024).map { Period(it, false) }, oct22)?.year)
        assertEquals(2025, Period.defaultPeriod(listOf(2025, 2024).map { Period(it, false) }, oct22)?.year)
        assertEquals("FY2027", Period.defaultPeriod(listOf(2027, 2026, 2025).map { Period(it, true) }, oct22)?.label)
        assertEquals(2026, Period.defaultPeriod(listOf(2030, 2026, 2025).map { Period(it, false) }, oct22)?.year)
    }

    @Test fun publishedDatasets() {
        for (id in listOf("contracts", "votes", "member-votes", "change-orders")) {
            assertEquals(id, Period(2026, false), Period.defaultPeriodFor(Repo.rows(id), oct22))
        }
        for (id in listOf("cra-payments", "audit-findings", "salary-positions", "officials-pay")) {
            val rows = Repo.rows(id)
            assertTrue(id, Period.all(rows).all { it.fiscal })
            assertEquals(id, true, Period.defaultPeriodFor(rows, oct22)?.fiscal)
            assertTrue(id, Period.all(rows).size > 1)
        }
        assertEquals(Period(2026, false), Period.defaultPeriodFor(Repo.rows("salary-leaders"), oct22))
        assertNull(Period.defaultPeriodFor(Repo.rows("sales-tax-projects"), oct22))
        assertNull(Period.defaultPeriodFor(Repo.rows("budget-detail"), oct22))
    }

    @Test fun chartTicks() {
        assertEquals(listOf(0, 1, 2), ChartTicks.labelIndices(3))
        val twelve = ChartTicks.labelIndices(12)
        assertTrue(twelve.size <= ChartTicks.PHONE_LABELS)
        assertEquals(11, twelve.last())
        assertEquals(listOf(2016, 2018, 2020, 2022, 2024, 2026), ChartTicks.yearTicks((2016..2026).toList()))
        assertEquals(listOf(2016, 2020), ChartTicks.sinceCutoff(listOf(2010, 2015, 2016, 2020)) { it })
        assertEquals(2024, ChartTicks.yearOf("FY2024"))
    }
}
