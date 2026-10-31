package me.baycounty.kit

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DataTest {
    @Test fun jsonValueKeepsTypes() {
        val r = Row.decodeList("""[{"a":true,"b":1.5,"c":null,"d":"x","e":[1,"y"],"f":{"g":2}}]""")[0]
        assertEquals(true, r.bool("a"))
        assertEquals(1.5, r.number("b")!!, 0.0)
        assertNull(r.string("c"))
        assertEquals("x", r.string("d"))
        assertEquals(listOf("1", "y"), r.strings("e"))
        assertNotNull(r["f"])
    }

    @Test fun everyPublishedDatasetDecodesAndReads() {
        val cat = Repo.catalog()
        assertTrue(cat.datasets.size > 20)
        for (d in cat.datasets) {
            val rows = Repo.rows(d.id)
            assertEquals("${d.id} row count", d.rows ?: rows.size, rows.size)
            val spec = DatasetSpec.forId(d.id)
            val titled = rows.count { spec.title(it) != "Record" }
            assertTrue("${d.id}: most rows need a title", titled >= rows.size * 0.95)
            if (rows.isNotEmpty() && spec.amountKeys.isNotEmpty() && d.id !in DatasetSpec.ownScreens) {
                assertTrue("${d.id}: amount column never filled", rows.any { spec.amount(it) != null })
            }
            if (DatasetSpec.known[d.id] != null) {
                for (key in spec.titleKeys + spec.subtitleKeys + spec.amountKeys + spec.filterKeys + spec.dateKeys) {
                    assertNotNull("${d.id}: spec names unknown column $key", d.column(key))
                }
            }
            rows.firstOrNull()?.let { assertFalse(DatasetSpec.fields(it, d.columns).isEmpty()) }
        }
    }

    @Test fun craTotalsFollowCountingRules() {
        val rows = Repo.rows("cra-payments")
        var paid = 0.0; var pending = 0.0
        for (r in rows) if (r.bool("count") == true) {
            val a = r.number("amount") ?: 0.0
            if (r.string("status") == "Spent") paid += a
            if (r.string("status") in listOf("Committed", "Budgeted")) pending += a
        }
        assertEquals(paid, CRALedger.paidOut(rows), 0.01)
        assertEquals(pending, CRALedger.pending(rows), 0.01)
        val s = CRALedger.summaries(rows)
        assertTrue(s.size >= 6)
        assertEquals(paid, s.sumOf { it.paidOut }, 0.01)
        assertEquals(rows.size, s.sumOf { it.records })
        assertTrue(rows.any { it.bool("count") == false && (it.number("amount") ?: 0.0) > 0 })
    }

    @Test fun governmentsAndMeetings() {
        val govs = Repo.rows("government-profiles").map { Government(it) }
        assertEquals(9, govs.size)
        assertTrue(govs.all { it.population != null && it.pageURL != null })
        assertEquals(Governments.names.keys, govs.map { it.govID }.toSet())
        val meetings = Repo.rows("meetings").map { Meeting(it) }
        val dated = meetings.filter { it.row.string("start") != null }
        assertEquals("every start date parses", dated.size, dated.count { it.start != null })
        assertTrue("every board has a name", meetings.all { !it.boardName.contains("-") })
        val upcoming = Meeting.upcoming(meetings, Dates.parse("2026-01-01")!!)
        assertFalse(upcoming.any { it.isPast || it.isCancelled })
        assertEquals(upcoming, upcoming.sortedBy { it.start })
    }

    @Test fun formatting() {
        assertEquals("$1,779,884", Format.money(1779883.75))
        assertEquals("$218.03", Format.money(218.03))
        assertEquals("$90.8M", Format.compactMoney(90_808_899.0))
        assertEquals("$148K", Format.compactMoney(148_377.0))
        assertEquals("$1.2B", Format.compactMoney(1_200_000_000.0))
        assertEquals("When", Format.label("date_or_fy"))
        assertEquals("Total raised", Format.label("total_raised"))
        assertEquals("4.05", Format.value(JsonPrimitive(4.05), "millage"))
        assertEquals("$7,674,166", Format.value(JsonPrimitive(7674166), "property_tax_levy"))
        assertEquals("46,089", Format.value(JsonPrimitive(46089), "parcels"))
        assertEquals("No", Format.value(JsonPrimitive(false), "count"))
        assertEquals("In progress", Format.value(JsonPrimitive("in_progress"), "status"))
        assertEquals("Oct 27, 2026", Format.value(JsonPrimitive("2026-10-27"), "date"))
        assertEquals("Oct 27, 2026 at 6:00 PM", Format.value(JsonPrimitive("2026-10-27T18:00:00-05:00"), "start"))
        assertEquals("Lynn Haven CRA Board", Governments.boardName("lh-cra"))
    }

    private fun rows(ids: List<String>) = ids.associateWith { Repo.rows(it) }

    @Test fun vendorLinksFindContractsAndVotes() {
        val all = rows(RecordLinks.vendorDatasets + "votes")
        val recs = RecordLinks.recordsForVendor("roberts-and-roberts", all)
        assertTrue(recs.any { it.first == "contracts" })
        val votes = RecordLinks.votesForVendor("roberts-and-roberts", all)
        assertFalse(votes.isEmpty())
        assertTrue(votes.all { it.string("vote_id") != null })
    }

    @Test fun contractDollarsAddUpForOneOfficial() {
        val recs = RecordLinks.recordsForPerson("daniel-raffield", rows(RecordLinks.personDatasets)).toMap()
        val c = RecordLinks.contractDollars(recs["contract-dollar-totals"] ?: emptyList())!!
        val yes = (recs["member-contract-dollars"] ?: emptyList()).filter { it.string("vote") == "yes" && it.string("outcome") == "passed" }
        assertEquals(yes.size, c.yesVotes)
        assertEquals(Math.round(yes.sumOf { it.number("amount") ?: 0.0 } * 100) / 100.0, c.yes, 0.01)
        assertTrue(c.yes > 0)
        assertNull(RecordLinks.contractDollars(emptyList()))
    }

    @Test fun personLinksFindVotesAndPay() {
        val all = rows(RecordLinks.personDatasets)
        val recs = RecordLinks.recordsForPerson("clair-pease", all).toMap()
        assertTrue(recs.containsKey("member-votes"))
        assertTrue(recs.containsKey("votes"))
        val mv = recs["member-votes"]!!
        val t = RecordLinks.tally(mv)
        assertEquals(mv.size, t.total)
        assertTrue(t.yes > 0)
        assertNotNull(RecordLinks.voteOf("clair-pease", recs["votes"]!!.first()))
    }
}
