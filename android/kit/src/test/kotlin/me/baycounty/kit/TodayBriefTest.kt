package me.baycounty.kit

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

/** The Today tab's greeting, "right now" cards and weekend picks. Same cases as the Swift TodayBriefTests. */
class TodayBriefTest {
    private fun row(vararg kv: Pair<String, Any>) = Row(0, kv.associate { (k, v) ->
        k to when (v) { is Boolean -> JsonPrimitive(v); is Number -> JsonPrimitive(v); else -> JsonPrimitive(v.toString()) } as JsonElement
    })

    @Test fun greeting() {
        assertEquals("Good morning", TodayBrief.greeting(7))
        assertEquals("Good afternoon", TodayBrief.greeting(13))
        assertEquals("Good evening", TodayBrief.greeting(20))
        assertEquals("Wednesday, Oct 28", TodayBrief.dateLine("2026-10-28"))
    }

    @Test fun beachCard() {
        val c = TodayBrief.beachCard(listOf(row("kind" to "forecast", "sort_order" to 0, "flag_color" to "Yellow", "rip_current_risk" to "Moderate")))
        assertEquals("Yellow beach flag", c.title)
        assertEquals("Moderate rip current risk", c.detail)
        assertEquals("Beach flags", TodayBrief.beachCard(emptyList()).title)
    }

    @Test fun noticesCardCountsActiveByKind() {
        fun n(k: String, s: String) = row("kind" to k, "status" to s)
        val c = TodayBrief.noticesCard(listOf(n("boil-water", "active"), n("utility", "active"), n("boil-water", "active"),
            n("boil-water", "active"), n("utility", "active"), n("shelter", "active"), n("road", "ended")))
        assertEquals("6 active notices", c.title)
        assertEquals("3 boil-water, 2 utility, 1 other", c.detail)
        assertEquals("No active alerts", TodayBrief.noticesCard(emptyList()).title)
    }

    @Test fun trashCard() {
        assertEquals("Trash day: Friday", TodayBrief.trashCard("Friday").title)
        assertEquals("Trash day", TodayBrief.trashCard(null).title)
    }

    @Test fun weekendWindow() {
        assertEquals("2026-10-30" to "2026-11-01", TodayBrief.weekend("2026-10-28"))
        assertEquals("2026-10-31" to "2026-11-01", TodayBrief.weekend("2026-10-31"))
        assertEquals("2026-11-01" to "2026-11-01", TodayBrief.weekend("2026-11-01"))
    }

    @Test fun weekendEventsSkipsRepeatsAndMeetings() {
        fun e(t: String, s: String, cat: String, rec: Boolean) = row("title" to t, "starts" to s, "category" to cat, "recurring" to rec)
        val rows = listOf(e("Fall Festival", "2026-10-31T08:00:00", "Community", false), e("Story time", "2026-10-31T10:00:00", "Library", true),
            e("Commission", "2026-10-30T09:00:00", "Public meeting", false), e("ZooBoo", "2026-10-31T00:00:00", "Community", false),
            e("Next week", "2026-11-05T09:00:00", "Community", false), e("Craft", "2026-10-31T00:00:00", "Library", false))
        assertEquals(listOf("ZooBoo", "Craft", "Fall Festival"), TodayBrief.weekendEvents(rows, "2026-10-28").map { it.string("title") })
    }
}
