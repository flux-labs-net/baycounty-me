package me.baycounty.kit

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import java.time.ZoneId

/** The watch apps' brief and complication lines. Same cases as the Swift WatchBriefTests. */
class WatchBriefTest {
    private val feedJSON = """
    {"headline":"No weather warnings or evacuation orders right now.","checked_at":"2026-10-29T14:00:00Z","counts":{},
     "notices":[
      {"notice_id":"a","kind":"road","gov_id":"pc","title":"Harrison Ave closed","summary":"Closed  between\n4th and 5th.","source":"City of Panama City","severity":"minor","issued":"2026-10-29T14:00:00Z","status":"active"},
      {"notice_id":"b","kind":"boil-water","gov_id":"lh","title":"Boil-water notice on Ohio Ave","summary":"Boil water before drinking.","source":"City of Lynn Haven","severity":"moderate","issued":"2026-10-29T13:00:00Z","status":"active"},
      {"notice_id":"c","kind":"road","gov_id":"pc","title":"Old closure","status":"ended"},
      {"notice_id":"d","kind":"road","gov_id":"pc","title":"Same post again","status":"active","same_as":"a"}
     ],"shelters":[],"zones":[]}
    """.trimIndent()

    private val utilitiesJSON = """
    {"data":{"area":"lh","area_name":"Lynn Haven","services":[],"rates":[],"holidays":[],
     "pickup":[{"service":"garbage","service_label":"Garbage","provider":"City of Lynn Haven","days":"Thursday"}]}}
    """.trimIndent()

    private fun at(m: Int, d: Int, h: Int) = LocalDateTime.of(2026, m, d, h, 0).atZone(ZoneId.of("America/Chicago")).toInstant()
    private fun meeting(board: String, start: String) = Meeting(Row(0, mapOf("board" to JsonPrimitive(board),
        "gov_id" to JsonPrimitive(board.substringBefore("-")), "start" to JsonPrimitive(start))))

    @Test fun alertsAreActiveOnlyAndMostSeriousFirst() {
        val b = WatchBrief.make(Emergency.parseFeed(feedJSON.toByteArray()), UtilityLookup.decode(utilitiesJSON), emptyList(), emptyList(), at(10, 30, 9))
        assertEquals(listOf("b", "a"), b.alerts.map { it.id })
        assertEquals("2 active alerts", b.alertTitle)
        assertEquals("Boil-water notice", b.alerts[0].label)
        assertTrue(b.alerts[0].nearHome)
        assertFalse(b.alerts[1].nearHome)
        assertEquals("Closed between 4th and 5th.", b.alerts[1].summary)
        assertEquals("Lynn Haven", b.place)
        assertEquals("2 active alerts", b.inline)
        assertEquals("2", b.circular)
    }

    @Test fun trashReminderOnlyAroundPickupDay() {
        val u = UtilityLookup.decode(utilitiesJSON)
        val thursday = WatchBrief.make(null, u, emptyList(), emptyList(), at(10, 29, 8))
        assertEquals("Trash pickup today", thursday.trash?.title)
        assertNull(thursday.nextPickup)
        assertEquals("Trash pickup today", thursday.inline)
        assertEquals("–", thursday.circular)
        assertEquals("Alerts didn't load", thursday.alertTitle)
        val friday = WatchBrief.make(null, u, emptyList(), emptyList(), at(10, 30, 8))
        assertNull(friday.trash)
        assertEquals("Next pickup Thursday", friday.nextPickup)
        val wednesdayEvening = WatchBrief.make(null, u, emptyList(), emptyList(), at(11, 4, 18))
        assertEquals("Trash pickup tomorrow", wednesdayEvening.trash?.title)
        assertEquals("Trash pickup tomorrow", wednesdayEvening.rectangularDetail)
    }

    @Test fun noHomeIsCountyWide() {
        val feed = Emergency.parseFeed("""{"headline":"No weather warnings or evacuation orders right now.","notices":[]}""".toByteArray())
        val b = WatchBrief.make(feed, null, emptyList(), emptyList(), at(10, 30, 9))
        assertEquals("Bay County", b.place)
        assertFalse(b.hasHome)
        assertNull(b.trash); assertNull(b.nextPickup)
        assertEquals("No active alerts", b.inline)
        assertEquals("0", b.circular)
        assertEquals("Beach flags", b.rectangularDetail)
    }

    @Test fun nextMeetingPrefersTheHomeGovernment() {
        val u = UtilityLookup.decode(utilitiesJSON)
        val ms = listOf(meeting("county-commission", "2026-11-03T09:00:00-06:00"), meeting("lh-commission", "2026-11-10T17:00:00-06:00"))
        assertTrue(WatchBrief.make(null, u, emptyList(), ms, at(10, 30, 9)).meeting.title.endsWith("Nov 10"))
        assertTrue(WatchBrief.make(null, null, emptyList(), ms, at(10, 30, 9)).meeting.title.endsWith("Nov 3"))
    }

    @Test fun homeMessageRoundTrip() {
        val h = WatchBrief.Home(30.2449, -85.6483)
        assertEquals(h, WatchBrief.Home.from(WatchBrief.Home.message(h))?.getOrNull())
        assertNull(WatchBrief.Home.from(WatchBrief.Home.message(null))?.getOrThrow())
        assertNull(WatchBrief.Home.from(mapOf("other" to 1)))
    }
}
