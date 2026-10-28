package me.baycounty.kit

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** The resident account answers decode, and dates show in Bay County time, the same as the Swift AccountTests. */
class AccountTest {
    private val feed = NearbyFeed.decode(File(Repo.fixtures, "nearby-sample.json").readText())

    @Test fun decodesTheNearbyAnswer() {
        assertEquals("lh", feed.govId)
        assertEquals("D", feed.zone)
        assertEquals("825 Ohio Ave", feed.home?.address)
        assertEquals("Friday", feed.todayCard.trash?.first()?.days)
        assertEquals(listOf("alerts", "meetings", "events", "projects", "notices", "food", "business"), feed.sections.map { it.id })
        assertEquals(listOf("county", "schools", "lh"), feed.governments.map { it.govId })
        assertTrue(feed.sections.first { it.id == "meetings" }.items.isNotEmpty())
    }

    @Test fun datesWithoutAnOffsetShowAsWritten() {
        val w = assertNotNull(NearbyFeed.whenOf("2026-10-29T08:00:00"))
        assertEquals("OCT", w.month); assertEquals("29", w.day); assertEquals("Thu 8 AM", w.time)
        assertEquals("Thu 8:30 AM", NearbyFeed.whenOf("2026-10-29T13:30:00Z")?.time)
        val d = assertNotNull(NearbyFeed.whenOf("2026-11-03"))
        assertEquals("3", d.day); assertNull(d.time)
        assertNull(NearbyFeed.whenOf(null))
    }

    @Test fun itemLinksAndTags() {
        val b = NearbyFeed.Item(kind = "business", title = "Gulf Coast Bakery LLC", entityId = "business:L26000012345")
        assertEquals("https://baycounty.me/profile/business/L26000012345", b.link)
        val road = NearbyFeed.Item(kind = "road", title = "Resurfacing", miles = 0.4, date = "2026-11-01")
        assertTrue(road.leadsWithDistance)
        assertEquals("Road", road.tag)
    }

    @Test fun decodesTheAccount() {
        val me = AccountMe.decode("""
            {"user":{"email":"a@example.com","first_name":"Sam"},
             "home":{"label":"Home","address":"825 Ohio Ave","city":"Lynn Haven","zip":"32444","lat":30.24,"lon":-85.65,"gov_id":"lh","zone":"D"},
             "prefs":{"weekly_email":true,"alert_email":["evacuation","water"],"push_topics":["weather"],"radius_mi":1,"topics":["meetings","events"]},
             "devices":0,"choices":{"topics":{"meetings":"Public meetings"},"radius_mi":[0.25,0.5,1,2,5],"push_topics":{"weather":"Weather"},"alert_email":{"water":"Boil water"}},
             "token":"abc"}
        """.trimIndent())
        assertEquals("Sam", me.user.firstName)
        assertEquals("Lynn Haven 32444", me.home?.subtitle)
        assertEquals(1.0, me.prefs?.radiusMi)
        assertEquals("abc", me.token)
        assertEquals("Half a mile", AccountMe.radiusLabel(0.5))
        assertEquals("5 miles", AccountMe.radiusLabel(5.0))
    }

    @Test fun requestsCarryTheTokenAndAction() {
        val r = AccountClient("t1").request("prefs", buildJsonObject { put("radius_mi", 2) })
        assertEquals("https://baycounty.me/api/account?action=prefs", r.url)
        assertEquals("Bearer t1", r.headers["Authorization"])
        assertEquals("""{"radius_mi":2}""", r.body)
        assertNull(AccountClient(null).request("me", null).headers["Authorization"])
    }

    @Test fun savedHomeBecomesThePhonesAddress() {
        val m = assertNotNull(AccountMe.decode("""{"user":{"email":"a@b.co"},"home":{"label":"Home","address":"1200 Beck Ave #4b 32401","city":"Panama City","zip":"32401","parcel_id":"12345-000-000","lat":30.17,"lon":-85.67,"gov_id":"pc","zone":"A"}}""").home).addressMatch
        assertEquals("1200 BECK AVE", m.address); assertEquals("4B", m.unit); assertEquals("32401", m.zip)
        assertEquals("12345-000-000", m.renum); assertEquals("Panama City", m.community)
        assertEquals(GeoPoint(-85.67, 30.17), m.point); assertEquals("1200 Beck Ave #4B", m.display)
        val p = assertNotNull(AccountMe.decode("""{"user":{"email":"a@b.co"},"home":{"address":"825 Ohio Ave","zip":"32444","lat":30.24,"lon":-85.64}}""").home).addressMatch
        assertEquals("825 OHIO AVE", p.address); assertNull(p.unit); assertNull(p.renum)
    }
}
