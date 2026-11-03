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

    /** The trash card shows only on pickup day, or from 4 p.m. the day before. Same cases as the site's BCTrashCard. */
    @Test fun trashCardOnlyAroundPickupDay() {
        val at = { m: Int, d: Int, h: Int -> java.time.ZonedDateTime.of(2026, m, d, h, 0, 0, 0, java.time.ZoneId.of("America/Chicago")).toInstant() }
        val holidays = listOf(
            UtilityLookup.Holiday(holiday = "Thanksgiving Day", whenObserved = "4th Thursday in November", garbage = "Moved to the Saturday after"),
            UtilityLookup.Holiday(holiday = "Memorial Day", whenObserved = "Last Monday in May", garbage = "No pickup"),
            UtilityLookup.Holiday(holiday = "Labor Day", whenObserved = "1st Monday in September", garbage = "Normal"),
            UtilityLookup.Holiday(holiday = "Christmas Day", whenObserved = "December 25", garbage = "No pickup; in 2025 Thursday's route moved to Saturday, December 27"),
            UtilityLookup.Holiday(holiday = "New Year's Day", whenObserved = "January 1", garbage = "No pickup; in 2026 Thursday's route moved to Saturday, January 3"),
        )
        val card = { m: Int, d: Int, h: Int -> TodayBrief.trashCard("Monday, Thursday", holidays, at(m, d, h)) }
        assertEquals("Trash pickup today", card(10, 29, 9)?.title)       // Thursday
        assertEquals("At your home", card(10, 29, 9)?.detail)
        assertEquals(null, card(10, 30, 9))                               // Friday
        assertEquals(null, card(11, 1, 14))                               // Sunday afternoon
        assertEquals("Trash pickup tomorrow", card(11, 1, 17)?.title)    // Sunday evening
        assertEquals("Put it out tonight", card(11, 1, 17)?.detail)
        assertEquals("No trash pickup today", card(11, 26, 8)?.title)    // Thanksgiving
        assertEquals("Thanksgiving Day · Moved to the Saturday after", card(11, 26, 8)?.detail)
        assertEquals("No trash pickup tomorrow", card(11, 25, 18)?.title)
        assertEquals("Memorial Day", card(5, 25, 8)?.detail)             // last Monday in May
        assertEquals("Trash pickup today", card(5, 18, 8)?.title)        // not the last Monday
        assertEquals("Trash pickup today", card(9, 7, 8)?.title)         // Labor Day pickup is normal
        assertEquals("Christmas Day", TodayBrief.trashCard("Friday", holidays, at(12, 25, 8))?.detail)   // the 2025 note is left off
        assertEquals("New Year's Day · In 2026 Thursday's route moved to Saturday, January 3",
            TodayBrief.trashCard("Thursday", holidays, java.time.ZonedDateTime.of(2026, 1, 1, 8, 0, 0, 0, java.time.ZoneId.of("America/Chicago")).toInstant())?.detail)
        assertEquals(null, TodayBrief.trashCard(null, emptyList(), at(10, 29, 9)))
        assertEquals(null, TodayBrief.trashCard(null))
    }

    @Test fun cardsLeadWithTrashOnlyOnPickupDay() {
        val home = UtilityLookup.decode(java.io.File(Repo.fixtures, "utilities-lynn-haven.json").readText())   // garbage on Friday
        val fri = java.time.ZonedDateTime.of(2026, 10, 30, 8, 0, 0, 0, java.time.ZoneId.of("America/Chicago")).toInstant()
        val wed = java.time.ZonedDateTime.of(2026, 10, 28, 8, 0, 0, 0, java.time.ZoneId.of("America/Chicago")).toInstant()
        assertEquals(listOf("trash", "beach", "notices", "meeting"), TodayBrief.cards(emptyList(), emptyList(), emptyList(), home, fri).map { it.id })
        assertEquals(listOf("beach", "notices", "meeting"), TodayBrief.cards(emptyList(), emptyList(), emptyList(), home, wed).map { it.id })
        assertEquals(3, TodayBrief.cards(emptyList(), emptyList(), emptyList(), null, fri).size)
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
